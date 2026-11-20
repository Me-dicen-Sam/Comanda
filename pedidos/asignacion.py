"""Asignación de repartidores y viajes compartidos. Todo con bloqueo de filas para evitar
servicios duplicados: el estado del repartidor cambia en la misma transacción que la asignación."""
from datetime import timedelta
import random

from django.db import transaction
from django.utils import timezone

from simulacion.models import ConfiguracionSimulacion
from simulacion.tiempos import duracion

from .estados import cambiar_estado
from .models import Pedido, Repartidor, Viaje

E = Pedido.Estado
ACTIVOS_VIAJE = (E.ASIGNADO, E.LISTO, E.EN_CAMINO)


def buscar_viaje_compatible(pedido, bloquear=False):
    """Un viaje sirve si se cumplen TODAS las condiciones del resumen del proyecto."""
    cfg = ConfiguracionSimulacion.obtener()
    ventana = timedelta(seconds=cfg.ventana_compartir_seg)
    qs = Viaje.objects.filter(activo=True)
    if bloquear:
        qs = qs.select_for_update()
    for viaje in qs:
        activos = list(viaje.pedidos.filter(estado__in=ACTIVOS_VIAJE))
        if not activos or len(activos) >= cfg.cupo_por_viaje:            # cupo
            continue
        if any(a.estado == E.EN_CAMINO for a in activos):                # el primero aún no sale
            continue
        if all(a.establecimiento_id == pedido.establecimiento_id        # misma cafetería
               and a.bloque_id == pedido.bloque_id                      # mismo bloque
               and abs(a.piso - pedido.piso) <= cfg.diferencia_max_pisos  # pisos cercanos
               and abs(a.creado_at - pedido.creado_at) <= ventana       # casi al mismo tiempo
               for a in activos):
            return viaje
    return None


def _programar_salida(pedido, otros):
    cfg = ConfiguracionSimulacion.obtener()
    ahora = timezone.now()
    salida = max(pedido.prog_preparado or ahora, ahora) + duracion(cfg.seg_en_camino, cfg)
    for o in otros:
        salida = max(salida, o.prog_en_camino or salida)
    entrega = salida + duracion(cfg.seg_entrega, cfg)
    for p in [pedido, *otros]:      # los pedidos de un viaje salen y llegan juntos
        p.prog_en_camino, p.prog_entregado = salida, entrega
        p.save(update_fields=['prog_en_camino', 'prog_entregado'])


def asignar_nuevo(pedido_id):
    """Toma un repartidor disponible. False si no hay (se reintenta en la próxima consulta)."""
    with transaction.atomic():
        pedido = Pedido.objects.select_for_update().get(pk=pedido_id)
        if pedido.estado not in (E.PREPARANDO, E.PENDIENTE_DECISION):
            return False
        candidatos_qs = Repartidor.objects.filter(estado=Repartidor.Estado.DISPONIBLE)
        if pedido.es_demo:                      # los pedidos demo nunca dependen de una persona real
            candidatos_qs = candidatos_qs.filter(usuario__isnull=True)

        candidatos_ids = list(candidatos_qs.values_list('pk', flat=True))
        if not candidatos_ids:
            return False

        elegido_id = random.choice(candidatos_ids)
        rep = (Repartidor.objects.filter(pk=elegido_id, estado=Repartidor.Estado.DISPONIBLE)
               .select_for_update(skip_locked=True)
               .first())
        if rep is None:
            rep = (candidatos_qs.exclude(pk=elegido_id)
                   .select_for_update(skip_locked=True)
                   .first())
        if rep is None:
            return False

        rep.estado = Repartidor.Estado.EN_SERVICIO
        rep.save(update_fields=['estado'])
        viaje = Viaje.objects.create(repartidor=rep)
        pedido.viaje = viaje
        pedido.save(update_fields=['viaje'])
        _programar_salida(pedido, [])
        cambiar_estado(pedido.pk, E.ASIGNADO, 'bot_repartidor')
        return True


def asignar_a_viaje(pedido_id, viaje_id):
    with transaction.atomic():
        pedido = Pedido.objects.select_for_update().get(pk=pedido_id)
        if pedido.estado != E.PENDIENTE_DECISION:
            return False
        compat = buscar_viaje_compatible(pedido, bloquear=True)
        if compat is None or compat.pk != viaje_id:      # ya no sirve: se asigna otro repartidor
            return asignar_nuevo(pedido_id)
        otros = list(compat.pedidos.filter(estado__in=ACTIVOS_VIAJE))
        pedido.viaje = compat
        pedido.save(update_fields=['viaje'])
        _programar_salida(pedido, otros)
        cambiar_estado(pedido.pk, E.ASIGNADO, 'bot_repartidor')
        return True


def decidir(pedido_id, opcion):
    """opcion: 'compartir' (esperar un poco más compartiendo repartidor) u 'otro'."""
    pedido = Pedido.objects.get(pk=pedido_id)
    if opcion == 'compartir':
        viaje = buscar_viaje_compatible(pedido)
        if viaje:
            return asignar_a_viaje(pedido_id, viaje.pk)
    return asignar_nuevo(pedido_id)


def liberar_viaje(viaje_id):
    """Cierra el viaje y libera al repartidor cuando ya no le quedan pedidos por entregar."""
    if not viaje_id:
        return
    with transaction.atomic():
        viaje = Viaje.objects.select_for_update().get(pk=viaje_id)
        if viaje.activo and not viaje.pedidos.filter(estado__in=ACTIVOS_VIAJE).exists():
            viaje.activo = False
            viaje.cerrado_at = timezone.now()
            viaje.save(update_fields=['activo', 'cerrado_at'])
            rep = Repartidor.objects.select_for_update().get(pk=viaje.repartidor_id)
            rep.estado = Repartidor.Estado.DISPONIBLE
            rep.save(update_fields=['estado'])