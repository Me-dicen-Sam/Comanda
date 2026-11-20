"""Pruebas de punta a punta: el flujo completo del cliente, los bots, los viajes y el dinero."""
import io

from django.core.management import call_command
from django.test import Client
from django.test import TestCase, override_settings
from django.urls import reverse

from accounts.models import Usuario
from catalogo.models import Bloque, Establecimiento, Producto
from pedidos.models import Pedido, Repartidor, Viaje
from simulacion.models import Billetera, ConfiguracionSimulacion, Movimiento, Pago
from simulacion.motor import avanzar

E = Pedido.Estado


def instantaneo(**cambios):
    """Todo ocurre al instante, salvo lo que se indique."""
    cfg = ConfiguracionSimulacion.obtener()
    for campo in ('seg_aceptar', 'seg_preparar', 'seg_asignar', 'seg_en_camino', 'seg_entrega'):
        setattr(cfg, campo, 0)
    for k, v in cambios.items():
        setattr(cfg, k, v)
    cfg.save()


class FlujoBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command('cargar_demo', stdout=io.StringIO())
        cls.cafe = Establecimiento.objects.get(nombre='Cafetería 1')
        cls.dedito = Producto.objects.get(nombre='Dedito de queso')
        cls.b1 = Bloque.objects.get(nombre='Bloque 1')

    def setUp(self):
        instantaneo()

    def usuario(self, n=1):
        return Usuario.objects.create_user(f'u{n}@uniguajira.edu.co', 'clave12345', nombre=f'Usuario {n}')

    def cliente(self, user, piso=2, bloque=None):
        self.client.force_login(user)
        self.client.post(reverse('ubicacion'), {'bloque': (bloque or self.b1).pk, 'piso': piso})
        return self.client

    def cliente_nuevo(self, user, piso):
        c = Client()
        c.force_login(user)
        c.post(reverse('ubicacion'), {'bloque': self.b1.pk, 'piso': piso})
        return c

    def pedir_y_pagar(self, user, cantidad=2, piso=2, numero='3001234567', client=None):
        c = client or self.cliente(user, piso)
        for _ in range(cantidad):
            c.post(reverse('carrito_accion'), {'producto': self.dedito.pk, 'accion': 'sumar'})
        c.post(reverse('crear_pedido'), {'referencia': 'aula 304'})
        pedido = Pedido.objects.filter(usuario=user).latest('id')
        c.post(reverse('pago', args=[pedido.pk]), {'numero': numero})
        return c, Pedido.objects.get(pk=pedido.pk)


class RegistroYUbicacion(FlujoBase):
    @override_settings(CAPTCHA_ENABLED=False)
    def test_registro_solo_correo_institucional(self):
        datos = {'nombre': 'X', 'telefono': '', 'password1': 'clave12345', 'password2': 'clave12345'}
        r = self.client.post(reverse('registro'), {**datos, 'email': 'x@gmail.com'})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Usuario.objects.filter(email='x@gmail.com').exists())
        r = self.client.post(reverse('registro'), {**datos, 'email': 'ana@uniguajira.edu.co'})
        self.assertRedirects(r, reverse('verificacion_enviada'))     # la cuenta queda esperando la confirmación del correo
        self.assertFalse(Usuario.objects.get(email='ana@uniguajira.edu.co').is_active)

    def test_sin_ubicacion_no_se_ve_nada(self):
        self.client.force_login(self.usuario())
        self.assertRedirects(self.client.get(reverse('inicio')), reverse('ubicacion'))
        self.client.post(reverse('ubicacion'), {'bloque': self.b1.pk, 'piso': 3})
        r = self.client.get(reverse('inicio'))
        self.assertContains(r, 'Cafetería 1')
        self.assertContains(r, '$2.000')


class FlujoCompleto(FlujoBase):
    def test_pedido_de_punta_a_punta_y_reparto_del_dinero(self):
        u = self.usuario()
        c, p = self.pedir_y_pagar(u)
        self.assertEqual((p.subtotal, p.domicilio, p.total), (5000, 2000, 7000))
        c.get(reverse('seguimiento', args=[p.pk]))
        p.refresh_from_db()
        self.assertEqual(p.estado, E.ENTREGADO)
        self.assertTrue(p.viaje.repartidor.estado == 'disponible')    # ya quedó libre
        c.post(reverse('recibido', args=[p.pk]))
        c.post(reverse('recibido', args=[p.pk]))                      # doble clic
        p.refresh_from_db()
        self.assertEqual(p.estado, E.RECIBIDO)
        self.assertEqual(p.pago.estado, Pago.Estado.LIQUIDADO)
        saldos = {b.tipo: b.saldo for b in Billetera.objects.exclude(saldo=0)}
        self.assertEqual(saldos, {'cafeteria': 4600, 'repartidor': 1600, 'comanda': 800})
        self.assertEqual(Movimiento.objects.filter(tipo='reparto').count(), 3)
        c.post(reverse('calificar', args=[p.pk]), {'puntaje_cafeteria': 5, 'puntaje_repartidor': 4})
        p.refresh_from_db()
        self.assertEqual(p.estado, E.CALIFICADO)
        self.assertEqual(float(p.viaje.repartidor.promedio), 4.0)

    def test_pago_rechazado_cancela_el_pedido(self):
        _, p = self.pedir_y_pagar(self.usuario(), numero='3001230000')
        self.assertEqual(p.estado, E.CANCELADO)
        self.assertEqual(p.pago.estado, Pago.Estado.RECHAZADO)

    def test_doble_clic_en_pagar_cobra_una_sola_vez(self):
        u = self.usuario()
        c, p = self.pedir_y_pagar(u)
        c.post(reverse('pago', args=[p.pk]), {'numero': '3001234567'})
        self.assertEqual(Pago.objects.filter(pedido=p).count(), 1)
        self.assertEqual(Movimiento.objects.filter(pedido=p, tipo='pago').count(), 1)

    def test_otro_usuario_no_ve_el_pedido(self):
        _, p = self.pedir_y_pagar(self.usuario(1))
        self.client.force_login(self.usuario(2))
        self.assertEqual(self.client.get(reverse('seguimiento', args=[p.pk])).status_code, 404)

    def test_el_precio_no_viene_del_navegador(self):
        u = self.usuario()
        c = self.cliente(u)
        c.post(reverse('carrito_accion'), {'producto': self.dedito.pk, 'accion': 'sumar', 'precio': '1'})
        c.post(reverse('crear_pedido'), {'subtotal': '1', 'total': '1'})
        self.assertEqual(Pedido.objects.get(usuario=u).total, 4500)


class Cancelaciones(FlujoBase):
    def test_cancelar_antes_de_salir_reembolsa(self):
        instantaneo(seg_aceptar=9999)
        c, p = self.pedir_y_pagar(self.usuario())
        c.post(reverse('cancelar', args=[p.pk]))
        p.refresh_from_db()
        self.assertEqual(p.estado, E.CANCELADO)
        self.assertEqual(p.pago.estado, Pago.Estado.REEMBOLSADO)
        self.assertEqual(Movimiento.objects.filter(pedido=p, tipo='reembolso').count(), 1)

    def test_en_camino_ya_no_se_cancela(self):
        instantaneo(seg_entrega=9999)
        c, p = self.pedir_y_pagar(self.usuario())
        c.get(reverse('seguimiento', args=[p.pk]))
        p.refresh_from_db()
        self.assertEqual(p.estado, E.EN_CAMINO)
        c.post(reverse('cancelar', args=[p.pk]))
        p.refresh_from_db()
        self.assertEqual(p.estado, E.EN_CAMINO)

    def test_cargo_por_cancelar_va_a_la_cafeteria(self):
        instantaneo(seg_en_camino=9999, cargo_cancelar=500)
        c, p = self.pedir_y_pagar(self.usuario())
        c.get(reverse('seguimiento', args=[p.pk]))
        c.post(reverse('cancelar', args=[p.pk]))
        self.assertEqual(Billetera.objects.get(establecimiento=self.cafe).saldo, 500)
        self.assertEqual(Movimiento.objects.get(pedido=p, tipo='reembolso').monto, 6500)

    def test_bot_de_la_cafeteria_cancela_si_no_hay_producto(self):
        instantaneo(seg_aceptar=9999)
        c, p = self.pedir_y_pagar(self.usuario())
        Producto.objects.filter(pk=self.dedito.pk).update(disponible=False)
        Pedido.objects.filter(pk=p.pk).update(prog_aceptado=p.creado_at)
        p = avanzar(p.pk)
        self.assertEqual((p.estado, p.cancelado_por), (E.CANCELADO, 'cafeteria'))
        self.assertEqual(p.pago.estado, Pago.Estado.REEMBOLSADO)


class Repartidores(FlujoBase):
    def test_viaje_compartido(self):
        instantaneo(seg_en_camino=9999)
        _, p1 = self.pedir_y_pagar(self.usuario(1), piso=2)
        c2, p2 = self.pedir_y_pagar(self.usuario(2), piso=3)
        avanzar(p1.pk)
        p2 = avanzar(p2.pk)
        self.assertEqual(p2.estado, E.PENDIENTE_DECISION)             # hay un viaje compatible
        c2.post(reverse('decidir', args=[p2.pk]), {'opcion': 'compartir'})
        p1.refresh_from_db(); p2.refresh_from_db()
        self.assertEqual(p2.estado, E.ASIGNADO)
        self.assertEqual(p1.viaje_id, p2.viaje_id)
        self.assertEqual(p1.prog_en_camino, p2.prog_en_camino)         # salen y llegan juntos
        self.assertEqual(Viaje.objects.count(), 1)

    def test_pedir_otro_repartidor(self):
        instantaneo(seg_en_camino=9999)
        _, p1 = self.pedir_y_pagar(self.usuario(1), piso=2)
        c2, p2 = self.pedir_y_pagar(self.usuario(2), piso=2)
        avanzar(p1.pk); avanzar(p2.pk)
        c2.post(reverse('decidir', args=[p2.pk]), {'opcion': 'otro'})
        p1.refresh_from_db(); p2.refresh_from_db()
        self.assertNotEqual(p1.viaje.repartidor_id, p2.viaje.repartidor_id)

    def test_pisos_lejanos_no_comparten(self):
        instantaneo(seg_en_camino=9999)
        _, p1 = self.pedir_y_pagar(self.usuario(1), piso=1)
        _, p2 = self.pedir_y_pagar(self.usuario(2), piso=4)
        avanzar(p1.pk)
        self.assertIn(avanzar(p2.pk).estado, (E.ASIGNADO, E.LISTO))   # no pasa por decisión
        self.assertEqual(Viaje.objects.count(), 2)

    def test_sin_repartidores_el_pedido_espera(self):
        Repartidor.objects.update(estado='en_servicio')
        c, p = self.pedir_y_pagar(self.usuario())
        self.assertEqual(avanzar(p.pk).estado, E.PREPARANDO)
        Repartidor.objects.filter(pk=Repartidor.objects.first().pk).update(estado='disponible')
        self.assertEqual(avanzar(p.pk).estado, E.ENTREGADO)

    def test_veinte_pedidos_a_la_vez_nadie_repite_repartidor(self):
        instantaneo(seg_en_camino=9999)
        pedidos = []
        for i in range(1, 21):
            u = self.usuario(i)
            pedidos.append(self.pedir_y_pagar(u, piso=(i % 4) + 1, client=self.cliente_nuevo(u, (i % 4) + 1))[1])
        for p in pedidos:
            avanzar(p.pk)
        activos = Viaje.objects.filter(activo=True)
        self.assertEqual(len({v.repartidor_id for v in activos}), activos.count())
