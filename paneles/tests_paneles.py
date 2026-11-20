"""Paneles de tienda y de repartidor: permisos, modo manual, repartidor real, fotos y catálogo."""
import io
import os
import tempfile

from django.test import override_settings
from django.urls import reverse
from PIL import Image

from accounts.models import Usuario
from catalogo.models import Categoria, Establecimiento, Producto
from pedidos.models import Pedido, Repartidor, Viaje
from pedidos.tests_flujo import FlujoBase, instantaneo
from simulacion.demo import generar_demo
from simulacion.models import Billetera, Pago
from simulacion.motor import avanzar

E = Pedido.Estado
MEDIA = tempfile.mkdtemp()


def png(tam=(900, 700)):
    b = io.BytesIO()
    Image.new('RGB', tam, (200, 90, 40)).save(b, 'PNG')
    b.seek(0)
    b.name = 'f.png'
    return b


@override_settings(MEDIA_ROOT=MEDIA)
class PanelBase(FlujoBase):
    def setUp(self):
        super().setUp()
        self.tienda_u = Usuario.objects.get(email='tienda.demo@uniguajira.edu.co')
        self.rep_u = Usuario.objects.get(email='domiciliario.demo@uniguajira.edu.co')
        self.rep = self.rep_u.perfil_repartidor
        self.cafe2 = Establecimiento.objects.get(nombre='Cafetería 2')

    def como(self, usuario):
        self.client.force_login(usuario)
        return self.client

    def tienda2(self):
        u = Usuario.objects.create_user('tienda2@uniguajira.edu.co', 'clave12345', nombre='T2', rol='cafeteria', establecimiento=self.cafe2)
        return u


class Permisos(PanelBase):
    def test_cliente_no_entra_a_los_paneles(self):
        c = self.como(self.usuario())
        self.assertEqual(c.get(reverse('panel_cafeteria')).status_code, 403)
        self.assertEqual(c.get(reverse('panel_repartidor')).status_code, 403)

    def test_tienda_no_entra_al_panel_del_repartidor_ni_al_de_admin(self):
        c = self.como(self.tienda_u)
        self.assertEqual(c.get(reverse('panel_repartidor')).status_code, 403)
        self.assertEqual(c.get(reverse('panel')).status_code, 302)

    def test_cuenta_de_tienda_sin_establecimiento_no_entra(self):
        u = Usuario.objects.create_user('sin@uniguajira.edu.co', 'clave12345', nombre='S', rol='cafeteria')
        self.assertEqual(self.como(u).get(reverse('panel_cafeteria')).status_code, 403)

    def test_tienda_y_repartidor_van_a_su_panel_desde_el_inicio(self):
        self.assertRedirects(self.como(self.tienda_u).get('/'), reverse('panel_cafeteria'), fetch_redirect_response=False)
        self.assertRedirects(self.como(self.rep_u).get('/'), reverse('panel_repartidor'), fetch_redirect_response=False)

    def test_el_ingreso_lleva_a_cada_panel(self):
        from django.test import override_settings as o
        with o(CAPTCHA_ENABLED=False):
            self.client.logout()
            r = self.client.post(reverse('login'), {'username': 'tienda.demo@uniguajira.edu.co', 'password': 'tienda12345'})
            self.assertRedirects(r, reverse('panel_cafeteria'), fetch_redirect_response=False)
            self.client.logout()
            r = self.client.post(reverse('login'), {'username': 'domiciliario.demo@uniguajira.edu.co', 'password': 'reparto12345'})
            self.assertRedirects(r, reverse('panel_repartidor'), fetch_redirect_response=False)


class PanelTienda(PanelBase):
    def test_solo_ve_los_pedidos_de_su_tienda(self):
        _, p1 = self.pedir_y_pagar(self.usuario(1))
        # pedido de la otra tienda
        u2 = self.usuario(2)
        c2 = self.cliente(u2)
        prod = Producto.objects.filter(establecimiento=self.cafe2).first()
        c2.post(reverse('carrito_accion'), {'producto': prod.pk, 'accion': 'sumar'})
        c2.post(reverse('crear_pedido'))
        p2 = Pedido.objects.get(usuario=u2)
        c2.post(reverse('pago', args=[p2.pk]), {'numero': '3001234567'})
        r = self.como(self.tienda_u).get(reverse('panel_cafeteria'))
        self.assertContains(r, f'Pedido #{p1.pk}')
        self.assertNotContains(r, f'Pedido #{p2.pk} ')

    def test_no_puede_actuar_sobre_pedidos_ni_productos_de_otra_tienda(self):
        instantaneo(seg_aceptar=9999)
        _, p = self.pedir_y_pagar(self.usuario())
        c = self.como(self.tienda2())
        self.assertEqual(c.post(reverse('cafeteria_pedido', args=[p.pk]), {'accion': 'rechazar'}).status_code, 404)
        self.assertEqual(c.post(reverse('producto_rapido', args=[self.dedito.pk]), {'precio': '1'}).status_code, 404)
        self.assertEqual(c.get(reverse('producto_editar', args=[self.dedito.pk])).status_code, 404)
        self.dedito.refresh_from_db(); p.refresh_from_db()
        self.assertEqual((self.dedito.precio, p.estado), (2500, E.PAGADO))

    def test_cerrar_la_tienda_bloquea_pedidos_nuevos(self):
        c = self.como(self.tienda_u)
        c.post(reverse('cafeteria_estado'), {'campo': 'abierto'})
        self.cafe.refresh_from_db()
        self.assertFalse(self.cafe.abierto)
        cl = self.cliente(self.usuario())
        cl.post(reverse('carrito_accion'), {'producto': self.dedito.pk, 'accion': 'sumar'})
        self.assertFalse(cl.session.get('carrito', {}).get('items'))
        self.assertNotContains(cl.get(reverse('inicio')), 'Dedito de queso')

    def test_modo_manual_aceptar_marcar_listo_y_entrega(self):
        self.como(self.tienda_u).post(reverse('cafeteria_estado'), {'campo': 'modo_manual'})
        _, p = self.pedir_y_pagar(self.usuario())
        self.assertEqual(avanzar(p.pk).estado, E.PAGADO)                 # el bot no lo acepta
        c = self.como(self.tienda_u)
        c.post(reverse('cafeteria_pedido', args=[p.pk]), {'accion': 'aceptar'})
        self.assertEqual(avanzar(p.pk).estado, E.ASIGNADO)               # se asigna repartidor, pero no sale solo
        c.post(reverse('cafeteria_pedido', args=[p.pk]), {'accion': 'listo'})
        self.assertEqual(avanzar(p.pk).estado, E.ENTREGADO)              # el repartidor del bot lo lleva

    def test_marcar_listo_sin_repartidor_se_rechaza(self):
        self.como(self.tienda_u).post(reverse('cafeteria_estado'), {'campo': 'modo_manual'})
        Repartidor.objects.update(estado='en_servicio')
        _, p = self.pedir_y_pagar(self.usuario())
        c = self.como(self.tienda_u)
        c.post(reverse('cafeteria_pedido', args=[p.pk]), {'accion': 'aceptar'})
        avanzar(p.pk)
        c.post(reverse('cafeteria_pedido', args=[p.pk]), {'accion': 'listo'})
        self.assertEqual(Pedido.objects.get(pk=p.pk).estado, E.PREPARANDO)

    def test_rechazar_cancela_y_reembolsa(self):
        self.como(self.tienda_u).post(reverse('cafeteria_estado'), {'campo': 'modo_manual'})
        _, p = self.pedir_y_pagar(self.usuario())
        self.como(self.tienda_u).post(reverse('cafeteria_pedido', args=[p.pk]), {'accion': 'rechazar', 'motivo': 'Se acabó'})
        p.refresh_from_db()
        self.assertEqual((p.estado, p.cancelado_por, p.motivo_cancelacion), (E.CANCELADO, 'cafeteria', 'Se acabó'))
        self.assertEqual(p.pago.estado, Pago.Estado.REEMBOLSADO)

    def test_crear_editar_y_cambiar_precio_de_productos(self):
        c = self.como(self.tienda_u)
        cat = Categoria.objects.first()
        r = c.post(reverse('producto_crear'), {'nombre': 'Arepa nueva', 'categoria': cat.pk, 'precio': 4200, 'emoji': '🫓', 'disponible': 'on', 'foto': png()})
        self.assertEqual(r.status_code, 302)
        nuevo = Producto.objects.get(nombre='Arepa nueva')
        self.assertEqual(nuevo.establecimiento, self.cafe)
        with Image.open(nuevo.foto.path) as im:
            self.assertLessEqual(max(im.size), 800)
        c.post(reverse('producto_rapido', args=[nuevo.pk]), {'precio': '4500'})
        c.post(reverse('producto_rapido', args=[nuevo.pk]), {'accion': 'disponibilidad'})
        nuevo.refresh_from_db()
        self.assertEqual((nuevo.precio, nuevo.disponible), (4500, False))

    def test_validaciones_del_producto(self):
        c = self.como(self.tienda_u)
        cat = Categoria.objects.first()
        c.post(reverse('producto_crear'), {'nombre': 'Caro', 'categoria': cat.pk, 'precio': 9_999_999})
        self.assertFalse(Producto.objects.filter(nombre='Caro').exists())
        falso = io.BytesIO(b'no soy imagen'); falso.name = 'x.png'
        c.post(reverse('producto_crear'), {'nombre': 'Falso', 'categoria': cat.pk, 'precio': 1000, 'foto': falso})
        self.assertFalse(Producto.objects.filter(nombre='Falso').exists())
        c.post(reverse('producto_rapido', args=[self.dedito.pk]), {'precio': 'abc'})
        self.dedito.refresh_from_db()
        self.assertEqual(self.dedito.precio, 2500)

    def test_foto_de_la_tienda_aparece_en_el_carrusel(self):
        self.como(self.tienda_u).post(reverse('cafeteria_tienda'), {'descripcion': 'Café de la U', 'emoji': '☕', 'foto': png()})
        self.cafe.refresh_from_db()
        self.assertTrue(self.cafe.foto)
        cl = self.cliente(self.usuario())
        self.assertContains(cl.get(reverse('inicio')), self.cafe.foto.url)

    def test_paginas_de_la_tienda(self):
        c = self.como(self.tienda_u)
        for vista in ('pedidos', 'catalogo', 'ajustes'):
            self.assertEqual(c.get(reverse('panel_cafeteria') + f'?vista={vista}').status_code, 200, vista)
        self.assertEqual(c.get(reverse('producto_editar', args=[self.dedito.pk])).status_code, 200)


class PanelRepartidor(PanelBase):
    def disponible(self):
        Repartidor.objects.filter(pk=self.rep.pk).update(estado='disponible')

    def test_el_repartidor_real_recibe_el_pedido_antes_que_los_ficticios(self):
        self.disponible()
        _, p = self.pedir_y_pagar(self.usuario())
        p = avanzar(p.pk)
        self.assertEqual(p.viaje.repartidor_id, self.rep.pk)
        self.assertEqual(p.estado, E.LISTO)                              # y el bot ya no lo mueve

    def test_flujo_completo_marcado_por_el_repartidor(self):
        self.disponible()
        cl, p = self.pedir_y_pagar(self.usuario())
        avanzar(p.pk)
        c = self.como(self.rep_u)
        self.assertContains(c.get(reverse('panel_repartidor')), f'Pedido #{p.pk}')
        c.post(reverse('repartidor_pedido', args=[p.pk]), {'accion': 'entregar'})        # aún no recogió
        self.assertEqual(Pedido.objects.get(pk=p.pk).estado, E.LISTO)
        c.post(reverse('repartidor_pedido', args=[p.pk]), {'accion': 'recoger'})
        self.assertEqual(avanzar(p.pk).estado, E.EN_CAMINO)              # los bots no lo entregan por él
        c.post(reverse('repartidor_pedido', args=[p.pk]), {'accion': 'entregar'})
        p.refresh_from_db(); self.rep.refresh_from_db()
        self.assertEqual(p.estado, E.ENTREGADO)
        self.assertEqual(self.rep.estado, 'disponible')                  # quedó libre
        self.assertFalse(Viaje.objects.get(pk=p.viaje_id).activo)
        self.client.force_login(p.usuario)
        self.client.post(reverse('recibido', args=[p.pk]))
        self.assertEqual(Billetera.objects.get(repartidor=self.rep).saldo, 1600)    # 80 % del domicilio de $2.000

    def test_solo_actua_sobre_sus_propios_pedidos(self):
        _, p = self.pedir_y_pagar(self.usuario())
        avanzar(p.pk)                                                    # lo toma un repartidor ficticio
        self.assertEqual(self.como(self.rep_u).post(reverse('repartidor_pedido', args=[p.pk]), {'accion': 'recoger'}).status_code, 404)

    def test_pausarse_y_no_poder_hacerlo_en_servicio(self):
        self.disponible()
        c = self.como(self.rep_u)
        c.post(reverse('repartidor_disponibilidad'))
        self.rep.refresh_from_db()
        self.assertEqual(self.rep.estado, 'pausado')
        c.post(reverse('repartidor_disponibilidad'))
        self.rep.refresh_from_db()
        self.assertEqual(self.rep.estado, 'disponible')
        Repartidor.objects.filter(pk=self.rep.pk).update(estado='en_servicio')
        c.post(reverse('repartidor_disponibilidad'))
        self.rep.refresh_from_db()
        self.assertEqual(self.rep.estado, 'en_servicio')

    def test_en_pausa_no_recibe_pedidos(self):
        _, p = self.pedir_y_pagar(self.usuario())                        # el demo arranca en pausa
        self.assertNotEqual(avanzar(p.pk).viaje.repartidor_id, self.rep.pk)

    def test_los_pedidos_demo_nunca_van_al_repartidor_real(self):
        self.disponible()
        generar_demo(6)
        for p in Pedido.objects.filter(es_demo=True):
            avanzar(p.pk)
        self.assertFalse(Pedido.objects.filter(es_demo=True, viaje__repartidor=self.rep).exists())

    def test_pagina_del_repartidor(self):
        self.assertEqual(self.como(self.rep_u).get(reverse('panel_repartidor')).status_code, 200)


class PaginasDelCliente(PanelBase):
    def test_carruseles_y_busqueda(self):
        c = self.cliente(self.usuario())
        r = c.get(reverse('ubicacion'))
        self.assertContains(r, 'carrusel-bloques')
        self.assertContains(r, 'Bloque 8')
        r = c.get(reverse('inicio'))
        self.assertContains(r, 'carrusel-tiendas')
        self.assertContains(r, 'COMANDA S.A.S.')                          # barra inferior
        self.assertContains(c.get(reverse('inicio') + '?q=dedito'), 'Dedito de queso')
        self.assertNotContains(c.get(reverse('inicio') + '?q=dedito'), 'Cuaderno')
        self.assertContains(c.get(reverse('inicio') + '?q=papeler'), 'Cuaderno')    # busca también por tienda
        self.assertContains(c.get(reverse('catalogo', args=[self.cafe.pk])), 'Dedito de queso')

    def test_agregar_desde_el_inicio_y_cambiar_de_tienda(self):
        c = self.cliente(self.usuario())
        c.post(reverse('carrito_accion'), {'producto': self.dedito.pk, 'accion': 'sumar', 'next': '/'})
        otro = Producto.objects.filter(establecimiento=self.cafe2).first()
        r = c.post(reverse('carrito_accion'), {'producto': otro.pk, 'accion': 'sumar', 'next': '/'}, follow=True)
        self.assertContains(r, 'canasta nueva')
        self.assertEqual(list(c.session['carrito']['items']), [str(otro.pk)])

    def test_la_canasta_lateral_se_mantiene_abierta_y_next_es_seguro(self):
        c = self.cliente(self.usuario())
        r = c.post(reverse('carrito_accion'), {'producto': self.dedito.pk, 'accion': 'sumar', 'desde': 'canasta', 'next': 'http://malo.example/'})
        self.assertRedirects(r, '/', fetch_redirect_response=False)       # no redirige a sitios externos
        self.assertNotIn('hidden', c.get('/').content.decode().split('id="cart-drawer"')[1].split('>')[0])
