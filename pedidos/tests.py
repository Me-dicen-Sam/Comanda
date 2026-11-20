from django.test import TestCase

from accounts.models import Usuario
from catalogo.models import Bloque, Establecimiento

from .estados import TransicionInvalida, cambiar_estado
from .models import HistorialEstado, Pedido

E = Pedido.Estado


class EstadosTests(TestCase):
    def setUp(self):
        bloque = Bloque.objects.create(nombre='Bloque 6', latitud=11.5, longitud=-72.9)
        cafe = Establecimiento.objects.create(nombre='Cafetería 1', bloque=bloque)
        user = Usuario.objects.create_user('ana@uniguajira.edu.co', 'clave12345', nombre='Ana')
        self.pedido = Pedido.objects.create(usuario=user, establecimiento=cafe, bloque=bloque, piso=3,
                                            subtotal=15000, domicilio=3000, total=18000)

    def avanzar(self, *estados):
        for e in estados:
            cambiar_estado(self.pedido.pk, e, 'bot_cafeteria')

    def test_flujo_completo(self):
        self.avanzar(E.PAGADO, E.ACEPTADO, E.PREPARANDO, E.ASIGNADO, E.EN_CAMINO, E.ENTREGADO, E.RECIBIDO, E.CALIFICADO)
        self.pedido.refresh_from_db()
        self.assertEqual(self.pedido.estado, E.CALIFICADO)
        self.assertIsNotNone(self.pedido.recibido_at)
        self.assertEqual(HistorialEstado.objects.filter(pedido=self.pedido).count(), 8)

    def test_no_se_puede_saltar_estados(self):
        with self.assertRaises(TransicionInvalida):
            cambiar_estado(self.pedido.pk, E.ENTREGADO, 'cliente')

    def test_cancelar_antes_de_salir_de_la_cafeteria(self):
        self.avanzar(E.PAGADO, E.ACEPTADO)
        pedido, cambio = cambiar_estado(self.pedido.pk, E.CANCELADO, 'cliente', cancelado_por='cliente', motivo='Ya no quiero')
        self.assertTrue(cambio)
        self.assertEqual(pedido.cancelado_por, 'cliente')

    def test_no_se_puede_cancelar_en_camino(self):
        self.avanzar(E.PAGADO, E.ACEPTADO, E.PREPARANDO, E.ASIGNADO, E.EN_CAMINO)
        with self.assertRaises(TransicionInvalida):
            cambiar_estado(self.pedido.pk, E.CANCELADO, 'cliente')

    def test_doble_clic_no_duplica(self):
        cambiar_estado(self.pedido.pk, E.PAGADO, 'cliente')
        _, cambio = cambiar_estado(self.pedido.pk, E.PAGADO, 'cliente')
        self.assertFalse(cambio)
        self.assertEqual(HistorialEstado.objects.filter(pedido=self.pedido).count(), 1)
