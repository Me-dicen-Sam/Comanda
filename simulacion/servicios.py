"""Pagos simulados, reembolsos y reparto del dinero. Los saldos usan F() dentro de atomic()
para que no se pierdan sumas cuando hay varios usuarios a la vez."""
import random
import re

from django.conf import settings
from django.db import transaction
from django.db.models import F

from pedidos.asignacion import liberar_viaje
from pedidos.estados import cambiar_estado
from pedidos.models import Pedido

from .models import Billetera, ConfiguracionSimulacion, Movimiento, Pago, SmsSimulado
from .reparto import calcular_reparto
from .tiempos import programar

E = Pedido.Estado
PREFIJO_SMS = '(Mensaje simulado: no tocamos tu dinero) COMANDA'


class PagoInvalido(Exception):
    pass


def _pesos(valor):
    return '$' + f'{valor:,}'.replace(',', '.')


def _sms(pedido, numero, texto):
    SmsSimulado.objects.create(pedido=pedido, numero=numero, texto=texto)


def billetera_de(tipo, obj=None):
    T = Billetera.Tipo
    if tipo == T.CAFETERIA:
        return Billetera.objects.get_or_create(establecimiento=obj, defaults={'tipo': T.CAFETERIA})[0]
    if tipo == T.REPARTIDOR:
        return Billetera.objects.get_or_create(repartidor=obj, defaults={'tipo': T.REPARTIDOR})[0]
    return Billetera.objects.filter(tipo=T.COMANDA).first() or Billetera.objects.create(tipo=T.COMANDA)


def _abonar(billetera, monto, pedido, tipo=Movimiento.Tipo.REPARTO):
    Billetera.objects.filter(pk=billetera.pk).update(saldo=F('saldo') + monto)
    Movimiento.objects.create(tipo=tipo, pedido=pedido, billetera=billetera, monto=monto)


def pagar_pedido(pedido_id, numero):
    """Pago simulado tipo Nequi. Devuelve (pago, es_nuevo). Repetirlo (doble clic) no cobra dos veces.
    Un número que termina en 0000 simula un pago rechazado."""
    numero = re.sub(r'\D', '', numero or '')
    if not re.fullmatch(r'3\d{9}', numero):
        raise PagoInvalido('Escribe un celular de 10 dígitos que empiece por 3.')
    with transaction.atomic():
        pedido = Pedido.objects.select_for_update().get(pk=pedido_id)
        existente = Pago.objects.filter(pedido=pedido).first()
        if existente:
            return existente, False
        if pedido.estado != E.PENDIENTE_PAGO:
            raise PagoInvalido('Este pedido ya no está pendiente de pago.')
        if numero.endswith('0000'):
            pago = Pago.objects.create(pedido=pedido, numero_nequi=numero, monto=pedido.total, estado=Pago.Estado.RECHAZADO)
            cambiar_estado(pedido.pk, E.CANCELADO, 'sistema', cancelado_por='sistema', motivo='Pago rechazado')
            _sms(pedido, numero, f'{PREFIJO_SMS}: tu pago de {_pesos(pedido.total)} fue rechazado.')
            return pago, True
        pago = Pago.objects.create(pedido=pedido, numero_nequi=numero, monto=pedido.total,
                                   codigo_confirmacion=f'{random.randint(0, 999999):06d}', estado=Pago.Estado.RETENIDO)
        Movimiento.objects.create(tipo=Movimiento.Tipo.PAGO, pedido=pedido, billetera=None, monto=pedido.total)
        cambiar_estado(pedido.pk, E.PAGADO, 'cliente')
        programar(pedido)
        _sms(pedido, numero, f'{PREFIJO_SMS} – {settings.SLOGAN_COMANDA}: hemos descontado {_pesos(pedido.total)} de tu cuenta como pago de tu pedido.')
        return pago, True


def _reembolsar(pedido, cargo=0):
    pago = Pago.objects.select_for_update().filter(pedido=pedido).first()
    if not pago or pago.estado != Pago.Estado.RETENIDO:
        return
    cargo = min(cargo, pago.monto)
    pago.estado = Pago.Estado.REEMBOLSADO
    pago.save(update_fields=['estado'])
    Movimiento.objects.create(tipo=Movimiento.Tipo.REEMBOLSO, pedido=pedido, billetera=None, monto=pago.monto - cargo)
    if cargo:   # cargo por cancelar: queda para la cafetería, que ya estaba preparando
        _abonar(billetera_de(Billetera.Tipo.CAFETERIA, pedido.establecimiento), cargo, pedido)
    _sms(pedido, pago.numero_nequi, f'{PREFIJO_SMS}: hemos devuelto {_pesos(pago.monto - cargo)} a tu cuenta por tu pedido cancelado.')


def cancelar_pedido(pedido_id, quien, motivo=''):
    """quien: 'cliente' o 'cafeteria'. Lanza TransicionInvalida si el pedido ya salió de la cafetería."""
    actor = 'cliente' if quien == 'cliente' else 'bot_cafeteria'
    with transaction.atomic():
        anterior = Pedido.objects.select_for_update().get(pk=pedido_id).estado
        pedido, cambio = cambiar_estado(pedido_id, E.CANCELADO, actor, cancelado_por=quien, motivo=motivo)
        if cambio:
            cargo = 0
            if quien == 'cliente' and anterior in (E.PREPARANDO, E.PENDIENTE_DECISION, E.ASIGNADO, E.LISTO):
                cargo = ConfiguracionSimulacion.obtener().cargo_cancelar
            _reembolsar(pedido, cargo)
            liberar_viaje(pedido.viaje_id)
        return pedido, cambio


def liquidar(pedido_id):
    """Reparte el dinero retenido entre cafetería, repartidor y COMANDA. Idempotente."""
    with transaction.atomic():
        pedido = Pedido.objects.select_related('viaje__repartidor', 'establecimiento').get(pk=pedido_id)
        pago = Pago.objects.select_for_update().filter(pedido=pedido).first()
        if not pago or pago.estado != Pago.Estado.RETENIDO:
            return False
        r = calcular_reparto(pedido.subtotal, pedido.domicilio)
        _abonar(billetera_de(Billetera.Tipo.CAFETERIA, pedido.establecimiento), r['cafeteria'], pedido)
        _abonar(billetera_de(Billetera.Tipo.REPARTIDOR, pedido.viaje.repartidor), r['repartidor'], pedido)
        _abonar(billetera_de(Billetera.Tipo.COMANDA), r['comanda'], pedido)
        pago.estado = Pago.Estado.LIQUIDADO
        pago.save(update_fields=['estado'])
        return True


def confirmar_recibido(pedido_id):
    with transaction.atomic():
        pedido, cambio = cambiar_estado(pedido_id, E.RECIBIDO, 'cliente')
        liquidar(pedido_id)
        return pedido, cambio
