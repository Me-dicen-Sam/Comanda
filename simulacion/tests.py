from django.test import SimpleTestCase

from .reparto import calcular_reparto


class RepartoTests(SimpleTestCase):
    def test_ejemplo_del_resumen(self):
        r = calcular_reparto(15000, 3000)
        self.assertEqual(r, {'cafeteria': 13800, 'repartidor': 2400, 'comanda': 1800})

    def test_siempre_suma_el_total(self):
        for subtotal, dom in [(8000, 2000), (12500, 4000), (9990, 3000)]:
            self.assertEqual(sum(calcular_reparto(subtotal, dom).values()), subtotal + dom)
