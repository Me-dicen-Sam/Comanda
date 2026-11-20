import io
import os

from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse
from PIL import Image
import tempfile

from catalogo.models import Bloque

from .models import Usuario

MEDIA = tempfile.mkdtemp()


def imagen(formato='PNG', tamano=(900, 600), modo='RGB'):
    buf = io.BytesIO()
    Image.new(modo, tamano, (200, 120, 60)).save(buf, formato)
    buf.seek(0)
    buf.name = 'foto.' + formato.lower()
    return buf


@override_settings(MEDIA_ROOT=MEDIA)
class PerfilTests(TestCase):
    def setUp(self):
        self.b = Bloque.objects.create(nombre='Bloque 6', latitud=11.5, longitud=-72.9)
        self.u = Usuario.objects.create_user('ana@uniguajira.edu.co', 'clave12345', nombre='Ana')
        self.client.force_login(self.u)

    def guardar(self, **extra):
        datos = {'nombre': 'Ana Pérez', 'telefono': '3001112233'}
        datos.update(extra)
        return self.client.post(reverse('perfil'), datos)

    def test_foto_se_guarda_reducida_y_se_muestra(self):
        r = self.guardar(foto=imagen('PNG', (2000, 1500)))
        self.assertRedirects(r, reverse('perfil'))
        self.u.refresh_from_db()
        self.assertTrue(self.u.foto.name.startswith('perfiles/'))
        self.assertTrue(os.path.exists(self.u.foto.path))
        with Image.open(self.u.foto.path) as im:
            self.assertLessEqual(max(im.size), 512)                 # se reduce
        self.assertContains(self.client.get(reverse('perfil')), self.u.foto.url)

    def test_nombre_y_telefono_se_guardan_sin_tocar_la_foto(self):
        self.guardar(foto=imagen())
        self.u.refresh_from_db()
        antes = self.u.foto.name
        self.guardar(nombre='Ana María', telefono='3109998877')     # sin foto nueva
        self.u.refresh_from_db()
        self.assertEqual((self.u.nombre, self.u.telefono, self.u.foto.name), ('Ana María', '3109998877', antes))

    def test_foto_nueva_borra_la_anterior(self):
        self.guardar(foto=imagen())
        self.u.refresh_from_db()
        vieja = self.u.foto.path
        self.guardar(foto=imagen('JPEG', (400, 400)))
        self.u.refresh_from_db()
        self.assertNotEqual(self.u.foto.path, vieja)
        self.assertFalse(os.path.exists(vieja))

    def test_png_con_transparencia_funciona(self):
        self.guardar(foto=imagen('PNG', (300, 300), 'RGBA'))
        self.u.refresh_from_db()
        self.assertTrue(self.u.foto)

    def test_archivo_que_no_es_imagen_se_rechaza(self):
        falso = io.BytesIO(b'esto no es una imagen')
        falso.name = 'virus.png'
        r = self.guardar(foto=falso)
        self.assertEqual(r.status_code, 200)
        self.u.refresh_from_db()
        self.assertFalse(self.u.foto)

    def test_foto_muy_pesada_se_rechaza(self):
        grande = io.BytesIO(b'\x89PNG' + os.urandom(2 * 1024 * 1024 + 10))
        grande.name = 'grande.png'
        self.guardar(foto=grande)
        self.u.refresh_from_db()
        self.assertFalse(self.u.foto)

    def test_ubicacion_actual_sale_de_la_que_elegiste(self):
        self.assertContains(self.client.get(reverse('perfil')), 'Aún no has elegido tu ubicación')
        self.client.post(reverse('ubicacion'), {'bloque': self.b.pk, 'piso': 3})
        r = self.client.get(reverse('perfil'))
        self.assertContains(r, 'Bloque 6 · Piso 3')
        self.assertNotContains(r, 'Aún no has elegido')
        self.u.refresh_from_db()
        self.assertEqual(self.u.bloque_habitual_id, self.b.pk)      # se recuerda para el próximo ingreso

    def test_otro_usuario_no_cambia_mi_foto(self):
        otro = Usuario.objects.create_user('luis@uniguajira.edu.co', 'clave12345', nombre='Luis')
        self.client.force_login(otro)
        self.guardar(foto=imagen())
        self.u.refresh_from_db(); otro.refresh_from_db()
        self.assertFalse(self.u.foto)
        self.assertTrue(otro.foto)
