"""Una sola función valida y aplica TODOS los cambios de estado de un pedido.

Los bots, el cliente y el administrador deben usar `cambiar_estado`; nadie
modifica `pedido.estado` directamente. Así las reglas viven en un único lugar.
"""
from django.db import transaction
from django.utils import timezone

from .models import HistorialEstado, Pedido

E = Pedido.Estado

TRANSICIONES = {
    E.PENDIENTE_PAGO: {E.PAGADO, E.CANCELADO},          # pago rechazado -> cancelado
    E.PAGADO: {E.ACEPTADO, E.CANCELADO},
    E.ACEPTADO: {E.PREPARANDO, E.CANCELADO},
    E.PREPARANDO: {E.PENDIENTE_DECISION, E.ASIGNADO, E.CANCELADO},
    E.PENDIENTE_DECISION: {E.ASIGNADO, E.CANCELADO},
    E.ASIGNADO: {E.LISTO, E.EN_CAMINO, E.CANCELADO},
    E.LISTO: {E.EN_CAMINO, E.CANCELADO},
    E.EN_CAMINO: {E.ENTREGADO},                          # desde aquí ya no se cancela
    E.ENTREGADO: {E.RECIBIDO},
    E.RECIBIDO: {E.CALIFICADO},
    E.CALIFICADO: set(),
    E.CANCELADO: set(),
}


class TransicionInvalida(Exception):
    pass


def cambiar_estado(pedido_id, nuevo, actor, cancelado_por='', motivo=''):
    """Devuelve (pedido, cambio_aplicado).

    - Bloquea la fila (select_for_update): si el cliente cancela justo cuando el bot
      pasa a "en camino", gana solo uno y el otro recibe TransicionInvalida.
    - Es idempotente: repetir el mismo cambio (doble clic) no hace nada ni falla.
    """
    with transaction.atomic():
        pedido = Pedido.objects.select_for_update().get(pk=pedido_id)
        if pedido.estado == nuevo:
            return pedido, False
        if nuevo not in TRANSICIONES[pedido.estado]:
            raise TransicionInvalida(f'No se puede pasar de {pedido.estado} a {nuevo}')
        anterior = pedido.estado
        pedido.estado = nuevo
        campos = ['estado']
        if nuevo == E.CANCELADO:
            pedido.cancelado_por, pedido.motivo_cancelacion = cancelado_por, motivo
            campos += ['cancelado_por', 'motivo_cancelacion']
        if nuevo == E.RECIBIDO:
            pedido.recibido_at = timezone.now()
            campos.append('recibido_at')
        pedido.save(update_fields=campos)
        HistorialEstado.objects.create(pedido=pedido, estado_anterior=anterior, estado_nuevo=nuevo, actor=actor)
        return pedido, True
