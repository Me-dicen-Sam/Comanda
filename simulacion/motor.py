"""Simulación perezosa: los bots no corren en segundo plano. Cada pedido guarda las horas en que
debe cambiar de estado, y cuando alguien lo consulta el servidor lo avanza hasta el presente."""
from django.conf import settings
from django.utils import timezone

from pedidos import asignacion
from pedidos.estados import TransicionInvalida, cambiar_estado
from pedidos.models import Pedido

from .servicios import cancelar_pedido

E = Pedido.Estado
ACTIVOS = [E.PAGADO, E.ACEPTADO, E.PREPARANDO, E.PENDIENTE_DECISION, E.ASIGNADO, E.LISTO, E.EN_CAMINO]


def _paso(p):
    """Aplica UN cambio pendiente. Devuelve True si algo cambió."""
    ahora = timezone.now()
    e = p.estado
    manual_cafeteria = p.establecimiento.modo_manual                       # el personal atiende
    rep_real = bool(p.viaje_id and p.viaje.repartidor.usuario_id)          # el repartidor marca sus pasos
    if e == E.PAGADO and manual_cafeteria:
        return False
    if e == E.PAGADO and p.prog_aceptado and ahora >= p.prog_aceptado:
        agotado = p.detalles.filter(producto__disponible=False).select_related('producto').first()
        if agotado:   # el bot de la cafetería cancela si falta un producto
            cancelar_pedido(p.pk, 'cafeteria', f'Producto agotado: {agotado.producto.nombre}')
        else:
            cambiar_estado(p.pk, E.ACEPTADO, 'bot_cafeteria')
            cambiar_estado(p.pk, E.PREPARANDO, 'bot_cafeteria')
        return True
    if e == E.ACEPTADO:
        cambiar_estado(p.pk, E.PREPARANDO, 'bot_cafeteria')
        return True
    if e == E.PREPARANDO and p.prog_asignado and ahora >= p.prog_asignado:
        if asignacion.buscar_viaje_compatible(p):
            from datetime import timedelta
            p.prog_asignado = ahora + timedelta(seconds=settings.DECISION_TIMEOUT_SEG)   # plazo para decidir
            p.save(update_fields=['prog_asignado'])
            cambiar_estado(p.pk, E.PENDIENTE_DECISION, 'sistema')
            return True
        return asignacion.asignar_nuevo(p.pk)
    if e == E.PENDIENTE_DECISION and (p.es_demo or (p.prog_asignado and ahora >= p.prog_asignado)):
        return asignacion.decidir(p.pk, 'compartir' if p.es_demo else 'otro')
    if e == E.ASIGNADO and not manual_cafeteria and p.prog_preparado and ahora >= p.prog_preparado:
        cambiar_estado(p.pk, E.LISTO, 'bot_cafeteria')
        return True
    if e == E.LISTO and not rep_real and p.prog_en_camino and ahora >= p.prog_en_camino:
        cambiar_estado(p.pk, E.EN_CAMINO, 'bot_repartidor')
        return True
    if e == E.EN_CAMINO and not rep_real and p.prog_entregado and ahora >= p.prog_entregado:
        cambiar_estado(p.pk, E.ENTREGADO, 'bot_repartidor')
        asignacion.liberar_viaje(p.viaje_id)
        return True
    return False


def avanzar(pedido_id):
    for _ in range(14):
        try:
            if not _paso(Pedido.objects.select_related('establecimiento', 'viaje__repartidor').get(pk=pedido_id)):
                break
        except TransicionInvalida:   # otro proceso ya lo movió (por ejemplo, el cliente canceló primero)
            break
    return Pedido.objects.get(pk=pedido_id)


def avanzar_todos():
    for pk in Pedido.objects.filter(estado__in=ACTIVOS).values_list('pk', flat=True)[:300]:
        avanzar(pk)
