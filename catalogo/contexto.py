from .models import Bloque, Producto


def comanda(request):
    """Datos que necesita la cabecera y la canasta lateral en todas las páginas del cliente."""
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}
    ctx = {'es_cliente': user.rol in ('cliente', 'admin')}
    if not ctx['es_cliente']:
        return ctx
    u = request.session.get('ubicacion')
    bloque = Bloque.objects.filter(pk=u['bloque_id']).first() if u else None
    ctx['ubicacion_label'] = f'{bloque.nombre} · Piso {u["piso"]}' if bloque else 'Elige tu ubicación'
    c = request.session.get('carrito') or {}
    items, total = [], 0
    if c.get('items'):
        pks = []
        for k in c['items'].keys():
            prod_id_str = str(k).partition(':')[0]
            if prod_id_str.isdigit():
                pks.append(int(prod_id_str))
        productos_map = {
            p.pk: p for p in Producto.objects.filter(pk__in=pks).select_related('establecimiento')
        }
        for k, q in c['items'].items():
            prod_id_str, _, opcion = str(k).partition(':')
            if not prod_id_str.isdigit():
                continue
            p = productos_map.get(int(prod_id_str))
            if not p:
                continue
            nombre_mostrar = f'{p.nombre} ({opcion})' if opcion else p.nombre
            items.append({'p': p, 'opcion': opcion, 'nombre_mostrar': nombre_mostrar, 'q': q, 'sub': p.precio * q})
            total += p.precio * q
    ctx.update(canasta=items, canasta_total=total, canasta_n=sum(i['q'] for i in items),
               canasta_tienda=items[0]['p'].establecimiento if items else None,
               abrir_canasta=request.session.pop('abrir_canasta', False))
    return ctx