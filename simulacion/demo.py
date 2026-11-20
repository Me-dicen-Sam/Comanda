"""Generador de pedidos de demostración. Todos llevan es_demo=True, así reiniciar no toca pedidos reales."""
import random

from django.db import transaction
from django.db.models import F

from accounts.models import Usuario
from catalogo.models import Bloque, Establecimiento
from pedidos.models import Pedido, Repartidor, Viaje
from pedidos.servicios import crear_pedido

from .models import Billetera, Movimiento
from .servicios import pagar_pedido

CORREO_DEMO = 'demo@uniguajira.edu.co'


def generar_demo(n=15):
    """Crea n pedidos casi simultáneos, ya pagados, para ver el flujo completo."""
    usuario = Usuario.objects.filter(email=CORREO_DEMO).first()
    if not usuario:
        usuario = Usuario(email=CORREO_DEMO, nombre='Usuario demo')
        usuario.set_unusable_password()
        usuario.save()
    cafes = [e for e in Establecimiento.objects.filter(activo=True) if e.productos.filter(disponible=True).exists()]
    bloques = list(Bloque.objects.all()[:3])      # pocos bloques, para que haya viajes compartidos
    if not cafes or not bloques:
        return 0
    creados = 0
    for _ in range(n):
        est = random.choice(cafes)
        prods = list(est.productos.filter(disponible=True))
        items = {str(p.pk): random.randint(1, 2) for p in random.sample(prods, k=min(len(prods), random.randint(1, 3)))}
        pedido = crear_pedido(usuario, random.choice(bloques), random.choice([1, 2, 3]), est.pk, items, es_demo=True)
        pagar_pedido(pedido.pk, '3' + ''.join(random.choice('123456789') for _ in range(9)))
        creados += 1
    return creados


def reiniciar_demo():
    """Borra solo los pedidos demo y deshace su efecto en las billeteras."""
    with transaction.atomic():
        ids = list(Pedido.objects.filter(es_demo=True).values_list('pk', flat=True))
        for m in Movimiento.objects.filter(pedido_id__in=ids, billetera__isnull=False):
            Billetera.objects.filter(pk=m.billetera_id).update(saldo=F('saldo') - m.monto)
        Movimiento.objects.filter(pedido_id__in=ids).delete()
        Pedido.objects.filter(pk__in=ids).delete()
        Viaje.objects.filter(pedidos__isnull=True).delete()
        ocupados = Viaje.objects.filter(activo=True).values_list('repartidor_id', flat=True)
        Repartidor.objects.exclude(pk__in=ocupados).update(estado=Repartidor.Estado.DISPONIBLE)
    return len(ids)
