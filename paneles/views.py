from django.contrib import messages
from django.db.models import Avg, Count, Sum
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from catalogo.models import Producto
from pedidos.estados import TransicionInvalida
from pedidos.models import Calificacion, Pedido, Repartidor
from simulacion.motor import avanzar

from . import acciones
from .forms import ProductoForm, TiendaForm
from .permisos import rol_requerido

E = Pedido.Estado
ACTIVOS = [E.PAGADO, E.ACEPTADO, E.PREPARANDO, E.PENDIENTE_DECISION, E.ASIGNADO, E.LISTO, E.EN_CAMINO]
FINALES = [E.ENTREGADO, E.RECIBIDO, E.CALIFICADO, E.CANCELADO]
FILTROS = {'todos': None, 'nuevos': [E.PAGADO], 'preparando': [E.ACEPTADO, E.PREPARANDO, E.PENDIENTE_DECISION, E.ASIGNADO],
           'listos': [E.LISTO, E.EN_CAMINO], 'finalizados': FINALES}


CANCELABLES = {E.PAGADO, E.ACEPTADO, E.PREPARANDO, E.PENDIENTE_DECISION, E.ASIGNADO, E.LISTO}


def _con_flags(pedidos):
    lista = list(pedidos)
    for p in lista:
        p.cancelable = p.estado in CANCELABLES
    return lista


# ------------------------------------------------------------------ cafetería / papelería
@rol_requerido('cafeteria')
def cafeteria(request):
    est = request.user.establecimiento
    for pk in Pedido.objects.filter(establecimiento=est, estado__in=ACTIVOS).values_list('pk', flat=True)[:100]:
        avanzar(pk)
    vista = request.GET.get('vista', 'pedidos')
    filtro = request.GET.get('filtro', 'todos')
    pedidos = (Pedido.objects.filter(establecimiento=est).exclude(estado=E.PENDIENTE_PAGO)
               .select_related('usuario', 'bloque', 'viaje__repartidor').prefetch_related('detalles__producto'))
    if FILTROS.get(filtro):
        pedidos = pedidos.filter(estado__in=FILTROS[filtro])
    hoy = timezone.localdate()
    base = Pedido.objects.filter(establecimiento=est)
    ventas = base.filter(estado__in=[E.ENTREGADO, E.RECIBIDO, E.CALIFICADO], creado_at__date=hoy).aggregate(v=Sum('subtotal'))['v'] or 0
    metricas = [
        ('Nuevos', base.filter(estado=E.PAGADO).count(), 'esperando tu aceptación' if est.modo_manual else 'los acepta el bot'),
        ('En preparación', base.filter(estado__in=[E.ACEPTADO, E.PREPARANDO, E.PENDIENTE_DECISION, E.ASIGNADO]).count(), 'pedidos activos'),
        ('Listos / en camino', base.filter(estado__in=[E.LISTO, E.EN_CAMINO]).count(), 'ya con el repartidor'),
        ('Ventas de hoy', f'${ventas:,}'.replace(',', '.'), 'productos entregados'),
    ]
    return render(request, 'paneles/cafeteria.html', {
        'est': est, 'vista': vista, 'filtro': filtro, 'secciones': [('pedidos', 'Pedidos'), ('catalogo', 'Catálogo'), ('ajustes', 'Mi tienda')], 'filtros': list(FILTROS), 'metricas': metricas,
        'pedidos': _con_flags(pedidos[:60]), 'productos': est.productos.select_related('categoria').order_by('nombre'),
        'form': ProductoForm(), 'form_tienda': TiendaForm(instance=est), 'promedio': Calificacion.objects.filter(pedido__establecimiento=est).aggregate(m=Avg('puntaje_cafeteria'))['m']})


@rol_requerido('cafeteria')
@require_POST
def cafeteria_estado(request):
    est = request.user.establecimiento
    campo = request.POST.get('campo')
    if campo == 'abierto':
        est.abierto = not est.abierto
        est.save(update_fields=['abierto'])
        messages.success(request, 'Tu tienda ahora está ' + ('abierta.' if est.abierto else 'cerrada: no recibirá pedidos nuevos.'))
    elif campo == 'modo_manual':
        est.modo_manual = not est.modo_manual
        est.save(update_fields=['modo_manual'])
        messages.success(request, 'Atención manual ' + ('activada: tú aceptas y marcas listo cada pedido.' if est.modo_manual
                                                      else 'desactivada: el bot atiende los pedidos.'))
    return redirect('panel_cafeteria')


@rol_requerido('cafeteria')
@require_POST
def cafeteria_tienda(request):
    form = TiendaForm(request.POST, request.FILES, instance=request.user.establecimiento)
    if form.is_valid():
        form.save()
        messages.success(request, 'Los datos de tu tienda se actualizaron.')
    else:
        messages.error(request, 'No se pudo guardar: ' + ' '.join(e for errs in form.errors.values() for e in errs))
    return redirect('/tienda/?vista=ajustes')


@rol_requerido('cafeteria')
@require_POST
def cafeteria_pedido(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk, establecimiento=request.user.establecimiento)   # solo los de su tienda
    accion = request.POST.get('accion')
    try:
        if accion == 'aceptar':
            acciones.aceptar_pedido(pedido)
            messages.success(request, f'Pedido #{pk} aceptado.')
        elif accion == 'listo':
            acciones.marcar_listo(pedido)
            messages.success(request, f'Pedido #{pk} marcado como listo.')
        elif accion == 'rechazar':
            acciones.rechazar_pedido(pedido, request.POST.get('motivo'))
            messages.success(request, f'Pedido #{pk} rechazado y reembolsado (simulado).')
    except TransicionInvalida as exc:
        messages.error(request, str(exc) or 'Ese pedido ya cambió de estado.')
    return redirect('panel_cafeteria')


@rol_requerido('cafeteria')
@require_POST
def producto_crear(request):
    form = ProductoForm(request.POST, request.FILES)
    if form.is_valid():
        producto = form.save(commit=False)
        producto.establecimiento = request.user.establecimiento
        producto.save()
        messages.success(request, f'«{producto.nombre}» se agregó a tu catálogo.')
    else:
        messages.error(request, 'No se pudo guardar el producto: ' + ' '.join(e for errs in form.errors.values() for e in errs))
    return redirect('/tienda/?vista=catalogo')


@rol_requerido('cafeteria')
def producto_editar(request, pk):
    producto = get_object_or_404(Producto, pk=pk, establecimiento=request.user.establecimiento)
    form = ProductoForm(request.POST or None, request.FILES or None, instance=producto)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Producto actualizado.')
        return redirect('/tienda/?vista=catalogo')
    return render(request, 'paneles/producto_form.html', {'form': form, 'producto': producto, 'est': request.user.establecimiento})


@rol_requerido('cafeteria')
@require_POST
def producto_rapido(request, pk):
    """Cambia precio o disponibilidad desde la fila del catálogo."""
    producto = get_object_or_404(Producto, pk=pk, establecimiento=request.user.establecimiento)
    if request.POST.get('accion') == 'disponibilidad':
        producto.disponible = not producto.disponible
        producto.save(update_fields=['disponible'])
    else:
        try:
            precio = int(request.POST.get('precio', ''))
            assert 0 <= precio <= 1_000_000
            producto.precio = precio
            producto.save(update_fields=['precio'])
            messages.success(request, f'Precio de «{producto.nombre}» actualizado.')
        except (ValueError, AssertionError):
            messages.error(request, 'Escribe un precio válido (0 a 1.000.000).')
    return redirect('/tienda/?vista=catalogo')


# ------------------------------------------------------------------ repartidor
@rol_requerido('repartidor')
def repartidor(request):
    rep = request.user.perfil_repartidor
    activos = Pedido.objects.filter(viaje__repartidor=rep, estado__in=[E.ASIGNADO, E.LISTO, E.EN_CAMINO])
    for pk in activos.values_list('pk', flat=True):
        avanzar(pk)
    rep.refresh_from_db()
    asignados = (Pedido.objects.filter(viaje__repartidor=rep, estado__in=[E.ASIGNADO, E.LISTO, E.EN_CAMINO])
                 .select_related('establecimiento__bloque', 'bloque', 'usuario').prefetch_related('detalles__producto'))
    historial = (Pedido.objects.filter(viaje__repartidor=rep, estado__in=[E.ENTREGADO, E.RECIBIDO, E.CALIFICADO])
                 .select_related('establecimiento').order_by('-creado_at')[:10])
    entregados = Pedido.objects.filter(viaje__repartidor=rep, estado__in=[E.ENTREGADO, E.RECIBIDO, E.CALIFICADO])
    metricas = [('Estado', rep.get_estado_display(), 'tu disponibilidad'),
                ('Por entregar', asignados.count(), 'pedidos asignados'),
                ('Entregados', entregados.count(), 'en total'),
                ('Calificación', f'{rep.promedio:.1f}' if rep.promedio else '—', 'promedio de clientes')]
    return render(request, 'paneles/repartidor.html', {'rep': rep, 'asignados': asignados, 'historial': historial, 'metricas': metricas})


@rol_requerido('repartidor')
@require_POST
def repartidor_disponibilidad(request):
    try:
        rep = acciones.alternar_disponibilidad(request.user.perfil_repartidor)
        messages.success(request, 'Ahora estás ' + ('disponible: te asignaremos pedidos.' if rep.estado == 'disponible' else 'en pausa.'))
    except TransicionInvalida as exc:
        messages.error(request, str(exc))
    return redirect('panel_repartidor')


@rol_requerido('repartidor')
@require_POST
def repartidor_pedido(request, pk):
    pedido = get_object_or_404(Pedido, pk=pk, viaje__repartidor=request.user.perfil_repartidor)   # solo los suyos
    try:
        if request.POST.get('accion') == 'recoger':
            acciones.recoger_pedido(pedido)
            messages.success(request, f'Pedido #{pk} recogido. ¡Buen camino!')
        elif request.POST.get('accion') == 'entregar':
            acciones.entregar_pedido(pedido)
            messages.success(request, f'Pedido #{pk} entregado. El cliente debe confirmarlo.')
    except TransicionInvalida as exc:
        messages.error(request, str(exc) or 'Ese pedido ya cambió de estado.')
    return redirect('panel_repartidor')
