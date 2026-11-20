"""Acciones del personal de la cafetería y del repartidor real. Todo pasa por `cambiar_estado`."""
from pedidos.asignacion import liberar_viaje
from pedidos.estados import TransicionInvalida, cambiar_estado
from pedidos.models import Pedido, Repartidor
from simulacion.servicios import cancelar_pedido

E = Pedido.Estado


def aceptar_pedido(pedido):
    """Cafetería (modo manual): pagado -> aceptado -> preparando."""
    cambiar_estado(pedido.pk, E.ACEPTADO, 'cafeteria')
    cambiar_estado(pedido.pk, E.PREPARANDO, 'cafeteria')


def rechazar_pedido(pedido, motivo):
    return cancelar_pedido(pedido.pk, 'cafeteria', (motivo or 'La cafetería no puede atender el pedido')[:255])


def marcar_listo(pedido):
    """Cafetería: solo cuando ya hay repartidor asignado."""
    if pedido.estado != E.ASIGNADO:
        raise TransicionInvalida('Aún no hay repartidor asignado.')
    cambiar_estado(pedido.pk, E.LISTO, 'cafeteria')


def recoger_pedido(pedido):
    """Repartidor real: listo -> en camino."""
    if pedido.estado != E.LISTO:
        raise TransicionInvalida('La cafetería aún no marca el pedido como listo.')
    cambiar_estado(pedido.pk, E.EN_CAMINO, 'repartidor')


def entregar_pedido(pedido):
    """Repartidor real: en camino -> entregado, y se libera si ya no le quedan pedidos."""
    cambiar_estado(pedido.pk, E.ENTREGADO, 'repartidor')
    liberar_viaje(pedido.viaje_id)


def alternar_disponibilidad(rep):
    """Disponible <-> No disponible. No se puede cambiar mientras lleva un pedido."""
    if rep.estado == Repartidor.Estado.EN_SERVICIO:
        raise TransicionInvalida('Estás en servicio: termina tus entregas primero.')
    rep.estado = (Repartidor.Estado.PAUSADO if rep.estado == Repartidor.Estado.DISPONIBLE
                  else Repartidor.Estado.DISPONIBLE)
    rep.save(update_fields=['estado'])
    return rep
