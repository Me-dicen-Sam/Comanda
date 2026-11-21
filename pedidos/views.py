from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db import transaction
from django.db.models import Avg
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from catalogo.geo import tarifa_para
from catalogo.models import Bloque, Establecimiento, Producto
from simulacion.motor import avanzar
from simulacion.servicios import PagoInvalido, cancelar_pedido, confirmar_recibido, pagar_pedido

from . import asignacion
from .estados import TransicionInvalida, cambiar_estado
from .models import Calificacion, Pedido
from .servicios import PedidoInvalido, crear_pedido

E = Pedido.Estado
CANCELABLES = {E.PAGADO, E.ACEPTADO, E.PREPARANDO, E.PENDIENTE_DECISION, E.ASIGNADO, E.LISTO}
ETAPAS = {E.PENDIENTE_PAGO: 1, E.PAGADO: 2, E.ACEPTADO: 2, E.PREPARANDO: 2, E.PENDIENTE_DECISION: 2, E.ASIGNADO: 2,
          E.LISTO: 2, E.EN_CAMINO: 3, E.ENTREGADO: 4, E.RECIBIDO: 4, E.CALIFICADO: 4}
PASOS = ['Pedido creado', 'Pedido confirmado', 'Pedido en camino', 'Pedido entregado']


def _mio(request, pk):
    """Cada usuario solo ve sus propios pedidos."""
    return get_object_or_404(Pedido.objects.select_related('establecimiento', 'bloque', 'viaje__repartidor'),
                             pk=pk, usuario=request.user)


def _eta(p):
    if p.estado in (E.CANCELADO, E.ENTREGADO, E.RECIBIDO, E.CALIFICADO) or not p.prog_entregado:
        return 0
    return max(0, int((p.prog_entregado - timezone.now()).total_seconds()))


@login_required
@require_POST
def crear(request):
    u = request.session.get('ubicacion') or {}
    bloque = Bloque.objects.filter(pk=u.get('bloque_id')).first()
    piso = u.get('piso')
    if not bloque or not piso:
        messages.error(request, 'Primero elige tu bloque y tu piso.')
        return redirect('ubicacion')

    aula_codigo = (request.POST.get('aula_codigo') or '').strip()
    metodo_pago = (request.POST.get('metodo_pago') or 'nequi').strip().lower()
    billete_raw = (request.POST.get('billete_efectivo') or '').strip()

    if not aula_codigo:
        messages.error(request, 'Debes seleccionar el aula o espacio de entrega.')
        return redirect('carrito')

    if metodo_pago == 'efectivo':
        messages.error(request, 'Pago no disponible en este momento.')
        return redirect('carrito')

    c = request.session.get('carrito') or {}
    est = Establecimiento.objects.filter(pk=c.get('est'), activo=True).select_related('bloque').first()
    if not est or not (c.get('items') or {}):
        messages.error(request, 'Tu canasta está vacía.')
        return redirect('inicio')

    subtotal_est = 0
    productos_map = {p.pk: p for p in Producto.objects.filter(establecimiento=est, disponible=True)}
    for k, q in (c.get('items') or {}).items():
        prod_id_str = str(k).partition(':')[0]
        if prod_id_str.isdigit() and int(prod_id_str) in productos_map:
            subtotal_est += productos_map[int(prod_id_str)].precio * int(q)
    total_estimado = subtotal_est + tarifa_para(bloque, est.bloque)['valor']

    detalle_pago = 'Nequi'

    dig_bloque = ''.join(ch for ch in bloque.nombre if ch.isdigit()) or '1'
    prefijo_bp = f'{dig_bloque}{piso}'
    if aula_codigo in ('Sala múltiple', 'Auditorio'):
        destino_texto = aula_codigo
    else:
        destino_texto = f'Aula {prefijo_bp}{aula_codigo}'

    referencia_final = f'{destino_texto} · Pago: {detalle_pago}'[:120]

    try:
        pedido = crear_pedido(
            request.user,
            bloque,
            piso,
            c.get('est'),
            c.get('items') or {},
            referencia_final,
            archivo_impresion=request.FILES.get('archivo_impresion'),
        )
    except PedidoInvalido as exc:
        messages.error(request, str(exc))
        return redirect('inicio')

    request.session.pop('carrito', None)
    return redirect('pago', pk=pedido.pk)


@login_required
def pago(request, pk):
    pedido = _mio(request, pk)
    if pedido.estado != E.PENDIENTE_PAGO:
        return redirect('seguimiento', pk=pk)
    error = ''
    if request.method == 'POST':
        try:
            pagar_pedido(pk, request.POST.get('numero'))
            return redirect('seguimiento', pk=pk)
        except PagoInvalido as exc:
            error = str(exc)
    return render(request, 'cliente/pago.html', {'p': pedido, 'error': error})


@login_required
def seguimiento(request, pk):
    _mio(request, pk)
    avanzar(pk)
    p = _mio(request, pk)
    etapa = ETAPAS.get(p.estado, 0)
    pasos = [{'n': i + 1, 'nombre': t, 'clase': 'ok' if i + 1 < etapa or (i + 1 == etapa and etapa == 4) else ('act' if i + 1 == etapa else '')}
             for i, t in enumerate(PASOS)]
    return render(request, 'cliente/seguimiento.html', {
        'p': p, 'pasos': pasos, 'rep': p.viaje.repartidor if p.viaje_id else None, 'eta': _eta(p),
        'cancelable': p.estado in CANCELABLES, 'pago': getattr(p, 'pago', None),
        'sms': p.sms.all()[:3], 'detalles': p.detalles.select_related('producto')})


@login_required
def estado_json(request, pk):
    _mio(request, pk)
    p = avanzar(pk)
    return JsonResponse({'estado': p.estado, 'eta': _eta(p)})


@login_required
@require_POST
def cancelar(request, pk):
    _mio(request, pk)
    try:
        cancelar_pedido(pk, 'cliente', request.POST.get('motivo', 'Cancelado por el cliente')[:255])
        messages.success(request, 'Pedido cancelado. Tu pago fue reembolsado (simulado).')
    except TransicionInvalida:
        messages.error(request, 'Ya no se puede cancelar: el pedido salió de la cafetería.')
    return redirect('seguimiento', pk=pk)


@login_required
@require_POST
def decidir(request, pk):
    _mio(request, pk)
    asignacion.decidir(pk, 'compartir' if request.POST.get('opcion') == 'compartir' else 'otro')
    return redirect('seguimiento', pk=pk)


@login_required
@require_POST
def recibido(request, pk):
    _mio(request, pk)
    try:
        confirmar_recibido(pk)
        messages.success(request, '¡Gracias! Confirmaste que recibiste tu pedido.')
    except TransicionInvalida:
        messages.error(request, 'Este pedido todavía no se puede confirmar.')
    return redirect('seguimiento', pk=pk)


@login_required
def calificar(request, pk):
    p = _mio(request, pk)
    if p.estado == E.CALIFICADO:
        messages.success(request, 'Ya calificaste este pedido.')
        return redirect('seguimiento', pk=pk)
    if p.estado != E.RECIBIDO:
        return redirect('seguimiento', pk=pk)
    if request.method == 'POST':
        try:
            pc, pr = int(request.POST.get('puntaje_cafeteria')), int(request.POST.get('puntaje_repartidor'))
        except (TypeError, ValueError):
            pc = pr = 0
        if not (1 <= pc <= 5 and 1 <= pr <= 5):
            messages.error(request, 'Elige un puntaje de 1 a 5.')
        else:
            with transaction.atomic():
                Calificacion.objects.get_or_create(pedido=p, defaults={
                    'puntaje_cafeteria': pc, 'puntaje_repartidor': pr, 'comentario': request.POST.get('comentario', '')[:255]})
                cambiar_estado(pk, E.CALIFICADO, 'cliente')
                rep = p.viaje.repartidor
                rep.promedio = Calificacion.objects.filter(pedido__viaje__repartidor=rep).aggregate(m=Avg('puntaje_repartidor'))['m'] or 0
                rep.save(update_fields=['promedio'])
            messages.success(request, '¡Gracias por calificar!')
            return redirect('mis_pedidos')
    return render(request, 'cliente/calificar.html', {'p': p, 'rep': p.viaje.repartidor})


@login_required
def mis_pedidos(request):
    pedidos = list(Pedido.objects.filter(usuario=request.user).select_related('establecimiento')[:30])
    for p in pedidos:
        if p.estado not in (E.CANCELADO, E.CALIFICADO, E.RECIBIDO, E.ENTREGADO, E.PENDIENTE_PAGO):
            avanzar(p.pk)
    pedidos = Pedido.objects.filter(usuario=request.user).select_related('establecimiento')[:30]
    return render(request, 'cliente/mis_pedidos.html', {'pedidos': pedidos})
