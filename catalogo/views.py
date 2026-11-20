from functools import wraps

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.db.models import Avg, Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from .geo import tarifa_para
from .models import Bloque, Categoria, Establecimiento, Producto

PISOS = [1, 2, 3, 4]


def ubicacion_requerida(vista):
    """Antes de cualquier otra cosa el usuario debe decir dónde está (bloque y piso).
    Las cuentas de tienda y de repartidor no compran: van directo a su panel."""
    @wraps(vista)
    @login_required
    def envoltura(request, *args, **kwargs):
        if request.user.rol == 'cafeteria':
            return redirect('panel_cafeteria')
        if request.user.rol == 'repartidor':
            return redirect('panel_repartidor')
        u = request.session.get('ubicacion')
        bloque = Bloque.objects.filter(pk=u['bloque_id']).first() if u else None
        if not bloque:
            return redirect('ubicacion')
        request.bloque, request.piso = bloque, u['piso']
        return vista(request, *args, **kwargs)
    return envoltura


@login_required
def ubicacion(request):
    if request.user.rol in ('cafeteria', 'repartidor'):
        return redirect('panel_cafeteria' if request.user.rol == 'cafeteria' else 'panel_repartidor')
    if request.method == 'POST':
        bloque = Bloque.objects.filter(pk=request.POST.get('bloque')).first()
        try:
            piso = int(request.POST.get('piso', ''))
        except ValueError:
            piso = 0
        if not bloque or piso not in PISOS:
            messages.error(request, 'Elige tu bloque y tu piso.')
        else:
            request.session['ubicacion'] = {'bloque_id': bloque.pk, 'piso': piso}
            if request.user.bloque_habitual_id != bloque.pk:
                request.user.bloque_habitual = bloque
                request.user.save(update_fields=['bloque_habitual'])
            return redirect('inicio')
    actual = request.session.get('ubicacion') or {}
    bloques_qs = Bloque.objects.all()
    bloques_data = []
    for idx, b in enumerate(bloques_qs, start=1):
        digitos = ''.join(ch for ch in b.nombre if ch.isdigit())
        cod_bloque = digitos if digitos else str(idx)
        bloques_data.append({'obj': b, 'cod': cod_bloque})
    return render(request, 'cliente/ubicacion.html', {
        'bloques': bloques_qs,
        'bloques_data': bloques_data,
        'pisos': PISOS,
        'bloque_sel': actual.get('bloque_id') or request.user.bloque_habitual_id,
        'piso_sel': actual.get('piso'),
    })


def _tiendas(request, **filtros):
    """Tiendas con distancia, zona, domicilio, tiempo estimado y calificación promedio."""
    tiendas = {}
    for est in (Establecimiento.objects.filter(activo=True, **filtros).select_related('bloque')
                .annotate(rating=Avg('pedidos__calificacion__puntaje_cafeteria'))):
        tiendas[est.pk] = {'est': est, **tarifa_para(request.bloque, est.bloque)}
    return tiendas


def _productos(tiendas, q='', cat=''):
    productos = Producto.objects.filter(disponible=True, establecimiento_id__in=tiendas.keys()).select_related('categoria')
    if q:
        por_tienda = [k for k, t in tiendas.items() if q.lower() in t['est'].nombre.lower()]
        productos = productos.filter(Q(nombre__icontains=q) | Q(establecimiento_id__in=por_tienda))
    if cat.isdigit():
        productos = productos.filter(categoria_id=int(cat))
    lista = [{'p': p, 'tienda': tiendas[p.establecimiento_id]} for p in productos]
    lista.sort(key=lambda x: (x['tienda']['distancia'], x['p'].nombre))
    return lista


@ubicacion_requerida
def inicio(request):
    q, cat = (request.GET.get('q') or '').strip(), request.GET.get('cat') or ''
    tiendas = _tiendas(request)
    abiertas = {k: t for k, t in tiendas.items() if t['est'].abierto}

    productos_filtrados = Producto.objects.filter(
        disponible=True,
        establecimiento_id__in=abiertas.keys(),
    ).select_related('categoria', 'establecimiento').order_by('nombre')

    if q:
        por_tienda = [k for k, t in abiertas.items() if q.lower() in t['est'].nombre.lower()]
        productos_filtrados = productos_filtrados.filter(Q(nombre__icontains=q) | Q(establecimiento_id__in=por_tienda))
    if cat.isdigit():
        productos_filtrados = productos_filtrados.filter(categoria_id=int(cat))

    por_est = {k: [] for k in abiertas.keys()}
    for p in productos_filtrados:
        por_est[p.establecimiento_id].append({'p': p, 'tienda': abiertas[p.establecimiento_id]})

    tiendas_ordenadas = sorted(tiendas.values(), key=lambda t: t['distancia'])
    secciones = []
    for t in tiendas_ordenadas:
        est_id = t['est'].pk
        prods = por_est.get(est_id, [])
        if (q or cat) and not prods:
            continue
        secciones.append({
            'tienda': t,
            'est': t['est'],
            'productos': prods,
        })

    return render(request, 'cliente/inicio.html', {
        'secciones': secciones,
        'productos': [item for s in secciones for item in s['productos']],
        'q': q,
        'cat': cat,
        'categorias': Categoria.objects.filter(productos__establecimiento__in=abiertas.keys()).distinct(),
        'bloque': request.bloque,
        'piso': request.piso,
    })


@ubicacion_requerida
def catalogo(request, establecimiento_id):
    tiendas = _tiendas(request, pk=establecimiento_id)
    if establecimiento_id not in tiendas:
        return redirect('inicio')
    tienda, q, cat = tiendas[establecimiento_id], (request.GET.get('q') or '').strip(), request.GET.get('cat') or ''
    est = tienda['est']
    return render(request, 'cliente/catalogo.html', {
        'tienda': tienda, 'est': est, 'productos': _productos(tiendas, q, cat) if est.abierto else [],
        'categorias': Categoria.objects.filter(productos__establecimiento=est).distinct(), 'q': q, 'cat': cat})


def _carrito(request):
    return request.session.get('carrito') or {'est': None, 'items': {}}


@ubicacion_requerida
@require_POST
def carrito_accion(request):
    es_ajax = request.headers.get('x-requested-with') == 'XMLHttpRequest'
    accion = request.POST.get('accion')
    carrito = _carrito(request)
    aviso = ''
    ok = True

    if accion == 'vaciar':
        request.session['carrito'] = {'est': None, 'items': {}}
        carrito = {'est': None, 'items': {}}
        aviso = 'Canasta vaciada.'
    else:
        prod = get_object_or_404(
            Producto.objects.select_related('establecimiento'),
            pk=request.POST.get('producto'),
            establecimiento__activo=True,
        )

        if accion == 'sumar' and not prod.establecimiento.abierto:
            aviso = f'{prod.establecimiento.nombre} está cerrada en este momento.'
            ok = False
        elif accion == 'sumar' and not prod.disponible:
            aviso = f'{prod.nombre} no está disponible en este momento.'
            ok = False
        elif accion == 'sumar' and carrito['est'] and carrito['est'] != prod.establecimiento_id and carrito['items']:
            tienda_actual = Establecimiento.objects.filter(pk=carrito['est']).first()
            nombre_actual = tienda_actual.nombre if tienda_actual else 'otra cafetería/papelería'
            aviso = (
                f'No puedes mezclar productos de distintas tiendas en el mismo domicilio. '
                f'Tu canasta actual es de {nombre_actual}: vacíala o finaliza ese pedido antes de agregar de {prod.establecimiento.nombre}.'
            )
            ok = False
        else:
            if carrito['est'] != prod.establecimiento_id:
                carrito = {'est': prod.establecimiento_id, 'items': {}}

            opciones_validas = prod.lista_opciones()
            opcion_elegida = (request.POST.get('opcion') or '').strip()
            if opciones_validas and opcion_elegida not in opciones_validas:
                opcion_elegida = opciones_validas[0]

            k = f'{prod.pk}:{opcion_elegida}' if opcion_elegida else str(prod.pk)
            q = carrito['items'].get(k, 0)
            if accion == 'sumar':
                q = min(q + 1, 20)
                aviso = f'Agregado: {prod.nombre}' + (f' ({opcion_elegida})' if opcion_elegida else '')
            elif accion == 'restar':
                q = max(q - 1, 0)
                if q:
                    aviso = f'Actualizado: {prod.nombre}' + (f' ({opcion_elegida})' if opcion_elegida else '')
                else:
                    aviso = f'Quitado: {prod.nombre}' + (f' ({opcion_elegida})' if opcion_elegida else '')

            if q:
                carrito['items'][k] = q
            else:
                carrito['items'].pop(k, None)
            if not carrito['items']:
                carrito['est'] = None
            request.session['carrito'] = carrito

    total_n = sum(carrito.get('items', {}).values())

    if es_ajax:
        items_canasta, subtotal_canasta = [], 0
        if carrito.get('items'):
            pks = []
            for key in carrito['items'].keys():
                prod_id_str = str(key).partition(':')[0]
                if prod_id_str.isdigit():
                    pks.append(int(prod_id_str))
            productos_map = {
                p.pk: p for p in Producto.objects.filter(pk__in=pks).select_related('establecimiento')
            }
            for key, cant in carrito['items'].items():
                prod_id_str, _, opc = str(key).partition(':')
                if not prod_id_str.isdigit():
                    continue
                p_obj = productos_map.get(int(prod_id_str))
                if not p_obj:
                    continue
                nombre_mostrar = f'{p_obj.nombre} ({opc})' if opc else p_obj.nombre
                items_canasta.append({
                    'p': p_obj,
                    'opcion': opc,
                    'nombre_mostrar': nombre_mostrar,
                    'q': cant,
                    'sub': p_obj.precio * cant,
                })
                subtotal_canasta += p_obj.precio * cant

        canasta_tienda = items_canasta[0]['p'].establecimiento if items_canasta else None
        canasta_html = render_to_string(
            'includes/canasta.html',
            {
                'canasta': items_canasta,
                'canasta_total': subtotal_canasta,
                'canasta_n': total_n,
                'canasta_tienda': canasta_tienda,
                'abrir_canasta': False,
            },
            request=request,
        )
        return JsonResponse({
            'ok': ok,
            'mensaje': aviso,
            'canasta_n': total_n,
            'canasta_html': canasta_html,
        })

    if aviso:
        if ok:
            messages.success(request, aviso)
        else:
            messages.error(request, aviso)

    if request.POST.get('desde') == 'canasta':
        request.session['abrir_canasta'] = True
    destino = request.POST.get('next') or ''
    if not url_has_allowed_host_and_scheme(destino, allowed_hosts={request.get_host()}):
        destino = '/'
    return redirect(destino)

@ubicacion_requerida
def carrito(request):
    c = _carrito(request)
    est = Establecimiento.objects.filter(pk=c['est']).select_related('bloque').first()
    if not est or not c['items']:
        messages.error(request, 'Tu canasta está vacía.')
        return redirect('inicio')
    items, subtotal = [], 0
    for k, q in c['items'].items():
        prod_id_str, _, opcion = str(k).partition(':')
        if not prod_id_str.isdigit():
            continue
        p = Producto.objects.filter(pk=int(prod_id_str), establecimiento=est).first()
        if not p:
            continue
        nombre_mostrar = f'{p.nombre} ({opcion})' if opcion else p.nombre
        items.append({'p': p, 'opcion': opcion, 'nombre_mostrar': nombre_mostrar, 'q': q, 'sub': p.precio * q})
        subtotal += p.precio * q
    if not items:
        messages.error(request, 'Tu canasta está vacía.')
        return redirect('inicio')
    t = tarifa_para(request.bloque, est.bloque)
    permite_impresion = est.productos.filter(nombre__icontains='impresión').exists()
    return render(request, 'cliente/carrito.html', {
        'est': est, 'items': items, 'subtotal': subtotal, 'domicilio': t['valor'], 'zona': t['zona'],
        'tiempo': t['tiempo'], 'total': subtotal + t['valor'], 'bloque': request.bloque, 'piso': request.piso,
        'permite_impresion': permite_impresion})