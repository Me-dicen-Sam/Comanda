from datetime import timedelta

from django.utils import timezone

from .models import ConfiguracionSimulacion

TOTAL_SIMULACION_SEGUNDOS = 59
VENTANA_SIN_CANCELAR_SEGUNDOS = 30


def duracion(segundos, cfg=None):
    cfg = cfg or ConfiguracionSimulacion.obtener()
    factor = float(cfg.factor_velocidad) or 1.0
    return timedelta(seconds=segundos / factor)


def programar(pedido, desde=None):
    """Programa los hitos del pedido para completar el ciclo en 59 segundos."""
    cfg = ConfiguracionSimulacion.obtener()
    ahora = desde or timezone.now()

    # Reparto exacto = 59 segundos
    seg_aceptar = 5
    seg_asignar = 9
    seg_preparar = 15
    seg_en_camino = 20
    seg_entregado = 10  # 5 + 9 + 15 + 20 + 10 = 59s

    t_aceptado = ahora + duracion(seg_aceptar, cfg)
    t_asignado = t_aceptado + duracion(seg_asignar, cfg)
    t_preparado = t_asignado + duracion(seg_preparar, cfg)
    t_en_camino = t_preparado + duracion(seg_en_camino, cfg)
    t_entregado = t_en_camino + duracion(seg_entregado, cfg)

    pedido.prog_aceptado = t_aceptado
    pedido.prog_asignado = t_asignado
    pedido.prog_preparado = t_preparado
    pedido.prog_en_camino = t_en_camino
    pedido.prog_entregado = t_entregado
    pedido.save(
        update_fields=[
            "prog_aceptado",
            "prog_asignado",
            "prog_preparado",
            "prog_en_camino",
            "prog_entregado",
        ]
    )


def puede_cancelar_pedido(pedido, ahora=None):
    """Permite cancelar solo si faltan más de 30 segundos para la entrega programada."""
    if not getattr(pedido, "prog_entregado", None):
        return True
    ahora = ahora or timezone.now()
    segundos_restantes = (pedido.prog_entregado - ahora).total_seconds()
    return segundos_restantes > VENTANA_SIN_CANCELAR_SEGUNDOS