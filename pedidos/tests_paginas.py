"""Humo: todas las páginas cargan sin error para quien corresponde."""
from django.urls import reverse

from accounts.models import Usuario
from pedidos.models import Pedido
from pedidos.tests_flujo import FlujoBase
from simulacion.demo import generar_demo, reiniciar_demo


class Paginas(FlujoBase):
    def test_paginas_del_cliente(self):
        u = self.usuario()
        c, p = self.pedir_y_pagar(u)
        c.post(reverse('carrito_accion'), {'producto': self.dedito.pk, 'accion': 'sumar'})
        for nombre, args in [('inicio', []), ('catalogo', [self.cafe.pk]), ('carrito', []), ('mis_pedidos', []),
                             ('perfil', []), ('ubicacion', []), ('seguimiento', [p.pk]), ('estado', [p.pk])]:
            self.assertEqual(c.get(reverse(nombre, args=args)).status_code, 200, nombre)

    def test_pagina_de_pago_y_calificacion(self):
        u = self.usuario()
        c = self.cliente(u)
        c.post(reverse('carrito_accion'), {'producto': self.dedito.pk, 'accion': 'sumar'})
        c.post(reverse('crear_pedido'))
        p = Pedido.objects.get(usuario=u)
        self.assertContains(c.get(reverse('pago', args=[p.pk])), '$4.500')
        c.post(reverse('pago', args=[p.pk]), {'numero': '3001234567'})
        c.get(reverse('seguimiento', args=[p.pk]))
        c.post(reverse('recibido', args=[p.pk]))
        self.assertEqual(c.get(reverse('calificar', args=[p.pk])).status_code, 200)

    def test_paginas_y_demo_del_administrador(self):
        admin = Usuario.objects.get(email='admin@uniguajira.edu.co')
        self.client.force_login(admin)
        self.assertEqual(generar_demo(15), 15)
        for nombre in ('panel', 'billeteras', 'configuracion'):
            self.assertEqual(self.client.get(reverse(nombre)).status_code, 200, nombre)
        self.assertContains(self.client.get(reverse('billeteras')), 'Ningún repartidor con dos viajes activos')
        self.client.get(reverse('panel'))
        self.assertTrue(self.client.get(reverse('billeteras')).context['cuadra'])
        self.assertEqual(reiniciar_demo(), 15)
        self.assertEqual(Pedido.objects.filter(es_demo=True).count(), 0)
        self.assertTrue(self.client.get(reverse('billeteras')).context['cuadra'])

    def test_cliente_no_entra_al_panel(self):
        self.client.force_login(self.usuario())
        self.assertEqual(self.client.get(reverse('panel')).status_code, 302)

    def test_login_y_registro(self):
        self.assertEqual(self.client.get(reverse('login')).status_code, 200)
        self.assertEqual(self.client.get(reverse('registro')).status_code, 200)
