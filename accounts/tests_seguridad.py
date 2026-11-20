"""Captcha, trampa para bots, registro directo y bloqueo por intentos."""
import time

from django.core.cache import cache
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Usuario

DATOS = {
    'nombre': 'Ana',
    'email': 'ana@uniguajira.edu.co',
    'telefono': '3001112233',
    'password1': 'clave-segura-123',
    'password2': 'clave-segura-123',
}


class Base(TestCase):
    def setUp(self):
        cache.clear()

    def captcha(self):
        r = self.client.get(reverse('captcha'))
        self.assertEqual(r['Content-Type'], 'image/png')
        return self.client.session['captcha']['t']

    def registrar(self, **extra):
        return self.client.post(reverse('registro'), {**DATOS, **extra})


class CaptchaTests(Base):
    def test_la_imagen_no_revela_la_respuesta(self):
        r = self.client.get(reverse('registro'))
        self.assertNotIn(
            b'captcha',
            r.content.lower()
            .replace(b'captcha-img', b'')
            .replace(b'/captcha/', b'')
            .replace(b'id_captcha', b'')
            .replace(b'name="captcha"', b''),
        )
        texto = self.captcha()
        self.assertEqual(len(texto), 5)

    def test_respuesta_incorrecta_no_crea_cuenta(self):
        self.captcha()
        r = self.registrar(captcha='XXXXX', sitio_web='')
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Las letras no coinciden')
        self.assertFalse(Usuario.objects.filter(email=DATOS['email']).exists())

    def test_respuesta_correcta_crea_cuenta_activa_y_redirige(self):
        texto = self.captcha()
        r = self.registrar(captcha=texto.lower(), sitio_web='')
        self.assertRedirects(r, reverse('ubicacion'))
        u = Usuario.objects.get(email=DATOS['email'])
        self.assertTrue(u.is_active)
        self.assertTrue(u.email_verificado)

    def test_cada_imagen_sirve_una_sola_vez(self):
        texto = self.captcha()
        self.registrar(captcha=texto, nombre='')
        r = self.registrar(captcha=texto)
        self.assertContains(r, 'Las letras no coinciden')

    def test_el_captcha_caduca(self):
        texto = self.captcha()
        sesion = self.client.session
        sesion['captcha'] = {'t': texto, 'e': time.time() - 1}
        sesion.save()
        self.assertContains(self.registrar(captcha=texto), 'Las letras no coinciden')

    def test_sin_pedir_imagen_no_hay_respuesta_valida(self):
        self.assertContains(self.registrar(captcha='ABCDE'), 'Las letras no coinciden')

    def test_la_trampa_para_bots_bloquea(self):
        texto = self.captcha()
        r = self.registrar(captcha=texto, sitio_web='http://spam.example')
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Usuario.objects.filter(email=DATOS['email']).exists())


@override_settings(CAPTCHA_ENABLED=False)
class RegistroYAccesoTests(Base):
    def test_registro_permite_ingresar_luego(self):
        self.registrar()
        self.client.post(reverse('logout'))
        r = self.client.post(
            reverse('login'),
            {'username': DATOS['email'], 'password': DATOS['password1']},
        )
        self.assertRedirects(r, reverse('ubicacion'))

    def test_clave_incorrecta_no_inicia_sesion(self):
        self.registrar()
        self.client.post(reverse('logout'))
        r = self.client.post(
            reverse('login'),
            {'username': DATOS['email'], 'password': 'otra-clave-123'},
        )
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_enlace_alterado_o_ajeno_no_sirve(self):
        r = self.client.get(reverse('verificar', kwargs={'token': 'token-invalido-abc'}))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Enlace no válido')

    def test_reenviar_responde_sin_error(self):
        r = self.client.post(reverse('reenviar'), {'email': 'nadie@uniguajira.edu.co'})
        self.assertIn(r.status_code, (200, 302))


@override_settings(CAPTCHA_ENABLED=False)
class BloqueoPorIntentosTests(Base):
    def setUp(self):
        super().setUp()
        Usuario.objects.create_user(
            'lis@uniguajira.edu.co',
            'clave-correcta-1',
            nombre='Lis',
            email_verificado=True,
        )

    def test_cinco_fallos_bloquean_incluso_con_la_clave_correcta(self):
        for _ in range(5):
            self.client.post(
                reverse('login'),
                {'username': 'lis@uniguajira.edu.co', 'password': 'mala'},
            )
        r = self.client.post(
            reverse('login'),
            {'username': 'lis@uniguajira.edu.co', 'password': 'clave-correcta-1'},
        )
        self.assertContains(r, 'Demasiados intentos')
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_un_ingreso_correcto_reinicia_el_contador(self):
        for _ in range(3):
            self.client.post(
                reverse('login'),
                {'username': 'lis@uniguajira.edu.co', 'password': 'mala'},
            )
        self.client.post(
            reverse('login'),
            {'username': 'lis@uniguajira.edu.co', 'password': 'clave-correcta-1'},
        )
        self.client.post(reverse('logout'))
        for _ in range(4):
            self.client.post(
                reverse('login'),
                {'username': 'lis@uniguajira.edu.co', 'password': 'mala'},
            )
        r = self.client.post(
            reverse('login'),
            {'username': 'lis@uniguajira.edu.co', 'password': 'clave-correcta-1'},
        )
        self.assertEqual(r.status_code, 302)