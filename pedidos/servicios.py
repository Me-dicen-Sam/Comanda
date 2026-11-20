from django.db import transaction

from catalogo.geo import tarifa_para
from catalogo.models import Establecimiento, Producto

from .models import DetallePedido, Pedido


class PedidoInvalido(Exception):
    pass


def crear_pedido(usuario, bloque, piso, establecimiento_id, items, referencia='', es_demo=False, archivo_impresion=None):
    """Crea el pedido. Los precios salen SIEMPRE de la base de datos, nunca del navegador."""
    est = Establecimiento.objects.select_related('bloque').filter(pk=establecimiento_id, activo=True).first()
    if not est or not items:
        raise PedidoInvalido('Tu carrito está vacío.')
    if not est.abierto and not es_demo:
        raise PedidoInvalido(f'{est.nombre} está cerrada en este momento.')

    pks = []
    for k in items.keys():
        prod_id_str = str(k).partition(':')[0]
        if prod_id_str.isdigit():
            pks.append(int(prod_id_str))

    productos = {p.pk: p for p in Producto.objects.filter(pk__in=pks, establecimiento=est)}
    detalles, subtotal = [], 0
    for k, q in items.items():
        prod_id_str, _, opcion = str(k).partition(':')
        if not prod_id_str.isdigit():
            continue
        p = productos.get(int(prod_id_str))
        if p is None or not p.disponible:
            raise PedidoInvalido('Un producto de tu carrito ya no está disponible.')
        cant = int(q)
        detalles.append((p, opcion[:80], cant))
        subtotal += p.precio * cant

    domicilio = tarifa_para(bloque, est.bloque)['valor']
    with transaction.atomic():
        pedido = Pedido.objects.create(
            usuario=usuario,
            establecimiento=est,
            bloque=bloque,
            piso=piso,
            referencia_entrega=referencia[:120],
            archivo_impresion=archivo_impresion,
            subtotal=subtotal,
            domicilio=domicilio,
            total=subtotal + domicilio,
            es_demo=es_demo,
        )
        DetallePedido.objects.bulk_create([
            DetallePedido(pedido=pedido, producto=p, opcion=op, cantidad=q, precio_unitario=p.precio)
            for p, op, q in detalles
        ])
    return pedido