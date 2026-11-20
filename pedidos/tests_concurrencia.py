"""Concurrencia real con hilos. Solo corre sobre MySQL (SQLite no admite bloqueo de filas)."""
import io
import threading
import unittest

from django.core.management import call_command
from django.db import connection, connections
from django.test import TransactionTestCase

from accounts.models import Usuario
from catalogo.models import Bloque, Establecimiento, Producto
from pedidos.estados import TransicionInvalida, cambiar_estado
from pedidos.models import Pedido, Viaje
from pedidos.servicios import crear_pedido
from pedidos.tests_flujo import instantaneo
from simulacion.models import Movimiento, Pago
from simulacion.motor import avanzar
from simulacion.servicios import cancelar_pedido, pagar_pedido

E = Pedido.Estado


def en_hilos(funcion, argumentos):
    errores = []

    def corre(a):
        try:
            funcion(*a)
        except Exception as exc:       # noqa
            errores.append(exc)
        finally:
            connections.close_all()

    hilos = [threading.Thread(target=corre, args=(a,)) for a in argumentos]
    [h.start() for h in hilos]
    [h.join() for h in hilos]
    return errores


@unittest.skipUnless(connection.vendor == 'mysql', 'requiere MySQL')
class Concurrencia(TransactionTestCase):
    def setUp(self):
        call_command('cargar_demo', stdout=io.StringIO())
        instantaneo(seg_en_camino=9999)
        self.cafe = Establecimiento.objects.get(nombre='Cafetería 1')
        self.dedito = Producto.objects.get(nombre='Dedito de queso')
        self.bloque = Bloque.objects.get(nombre='Bloque 1')

    def pedido_pagado(self, n):
        u = Usuario.objects.create_user(f'c{n}@uniguajira.edu.co', 'clave12345', nombre=f'C{n}')
        p = crear_pedido(u, self.bloque, (n % 4) + 1, self.cafe.pk, {str(self.dedito.pk): 1})
        pagar_pedido(p.pk, '3001234567')
        return p

    def test_doble_pago_simultaneo_cobra_una_vez(self):
        p = self.pedido_pagado(1) if False else None
        u = Usuario.objects.create_user('dp@uniguajira.edu.co', 'clave12345', nombre='DP')
        p = crear_pedido(u, self.bloque, 1, self.cafe.pk, {str(self.dedito.pk): 1})
        en_hilos(pagar_pedido, [(p.pk, '3001234567')] * 6)
        self.assertEqual(Pago.objects.filter(pedido=p).count(), 1)
        self.assertEqual(Movimiento.objects.filter(pedido=p, tipo='pago').count(), 1)

    def test_cancelar_y_salir_a_la_vez_gana_solo_uno(self):
        instantaneo(seg_en_camino=0, seg_entrega=9999)
        p = self.pedido_pagado(2)
        avanzar(p.pk)                      # llega hasta listo/en_camino
        Pedido.objects.filter(pk=p.pk).update(estado=E.LISTO)
        resultados = []

        def cancelar():
            try:
                cancelar_pedido(p.pk, 'cliente')
                resultados.append('cancelado')
            except TransicionInvalida:
                resultados.append('rechazado')

        def salir():
            try:
                cambiar_estado(p.pk, E.EN_CAMINO, 'bot_repartidor')
                resultados.append('en_camino')
            except TransicionInvalida:
                resultados.append('rechazado')

        hilos = [threading.Thread(target=lambda f=f: (f(), connections.close_all())) for f in (cancelar, salir)]
        [h.start() for h in hilos]; [h.join() for h in hilos]
        self.assertEqual(sorted(resultados).count('rechazado'), 1)         # solo uno gana
        p.refresh_from_db()
        self.assertIn(p.estado, (E.CANCELADO, E.EN_CAMINO))

    def test_quince_pedidos_en_paralelo_ningun_repartidor_doble(self):
        pedidos = [self.pedido_pagado(i + 10) for i in range(15)]
        en_hilos(avanzar, [(p.pk,) for p in pedidos])
        en_hilos(avanzar, [(p.pk,) for p in pedidos])
        activos = Viaje.objects.filter(activo=True)
        self.assertEqual(len({v.repartidor_id for v in activos}), activos.count())
        for p in Pedido.objects.filter(pk__in=[p.pk for p in pedidos]):
            self.assertIn(p.estado, (E.ASIGNADO, E.LISTO, E.PENDIENTE_DECISION))
            if p.estado != E.PENDIENTE_DECISION:
                self.assertIsNotNone(p.viaje_id)
        for v in activos:
            self.assertLessEqual(v.pedidos.exclude(estado=E.CANCELADO).count(), 2)   # cupo por viaje
