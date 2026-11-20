from django.core.exceptions import ValidationError
from django.test import TestCase

from .models import Usuario, validar_correo_institucional


class CorreoInstitucionalTests(TestCase):
    def test_acepta_correo_de_la_universidad(self):
        validar_correo_institucional('ana@uniguajira.edu.co')

    def test_rechaza_otros_dominios(self):
        with self.assertRaises(ValidationError):
            validar_correo_institucional('ana@gmail.com')

    def test_crear_usuario_con_correo(self):
        u = Usuario.objects.create_user('Ana@uniguajira.edu.co', 'clave12345', nombre='Ana')
        self.assertEqual(u.email, 'ana@uniguajira.edu.co')
