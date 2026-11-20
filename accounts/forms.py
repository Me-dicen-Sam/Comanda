import io
import secrets

from django import forms
from django.conf import settings
from django.contrib.auth import password_validation
from django.contrib.auth.forms import AuthenticationForm
from django.core.cache import cache
from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile

from PIL import Image, ImageOps

from catalogo import imagenes

from . import captcha
from .models import Usuario


CLASE_CAMPO = ('w-full rounded-xl border border-gray-300 bg-white px-4 py-3 text-base text-gray-900 '
               'focus:outline-none focus:ring-2 focus:ring-[#FF441F] focus:border-[#FF441F]')


class ProtegidoMixin:
    """Captcha de imagen + trampa para bots (campo invisible que una persona nunca llena)."""
    def _proteger(self, request):
        self.request = request
        self.fields['captcha'] = forms.CharField(
            label='Escribe las letras de la imagen',
            max_length=10,
            required=settings.CAPTCHA_ENABLED,
            widget=forms.TextInput(attrs={'autocomplete': 'off', 'autocapitalize': 'characters'}),
        )
        self.fields['sitio_web'] = forms.CharField(
            required=False,
            label='Sitio web',
            widget=forms.TextInput(attrs={'tabindex': '-1', 'autocomplete': 'off'}),
        )
        for campo in self.fields.values():
            campo.widget.attrs.setdefault('class', CLASE_CAMPO)

    def clean_sitio_web(self):
        if self.cleaned_data.get('sitio_web'):
            raise ValidationError('No pudimos verificar que seas una persona.')
        return ''

    def clean_captcha(self):
        if not captcha.verificar(self.request, self.cleaned_data.get('captcha')):
            raise ValidationError('Las letras no coinciden. Prueba con la nueva imagen.')
        return ''


class RegistroForm(ProtegidoMixin, forms.ModelForm):
    password1 = forms.CharField(label='Contraseña (mínimo 8 caracteres)', widget=forms.PasswordInput, min_length=8)
    password2 = forms.CharField(label='Repite la contraseña', widget=forms.PasswordInput)

    class Meta:
        model = Usuario
        fields = ['nombre', 'email', 'telefono']

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._proteger(request)

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if not email.endswith(settings.DOMINIO_INSTITUCIONAL):
            raise ValidationError(f'Solo se permiten correos {settings.DOMINIO_INSTITUCIONAL}')
        return email

    def clean(self):
        data = super().clean()
        if data.get('password1') and data.get('password1') != data.get('password2'):
            self.add_error('password2', 'Las contraseñas no coinciden.')
        if data.get('password1'):
            password_validation.validate_password(data['password1'])
        return data

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password1'])
        user.is_active = True
        user.email_verificado = True
        if commit:
            user.save()
        return user


class LoginForm(ProtegidoMixin, AuthenticationForm):
    username = forms.EmailField(label='Correo institucional')

    def __init__(self, request=None, *args, **kwargs):
        super().__init__(request, *args, **kwargs)
        self._proteger(request)

    def _clave_bloqueo(self):
        ip = (self.request.META.get('REMOTE_ADDR') if self.request else '') or ''
        return f'login:{(self.data.get("username") or "").strip().lower()}:{ip}'

    def clean_username(self):
        email = (self.cleaned_data.get('username') or '').strip().lower()
        if not email.endswith(settings.DOMINIO_INSTITUCIONAL):
            raise ValidationError(f'Solo se permiten correos {settings.DOMINIO_INSTITUCIONAL}')
        return email

    def clean(self):
        clave = self._clave_bloqueo()
        if cache.get(clave, 0) >= settings.LOGIN_MAX_INTENTOS:
            raise ValidationError(
                'Demasiados intentos fallidos. Espera 15 minutos o recupera tu acceso con el administrador.',
                code='bloqueado',
            )
        try:
            return super().clean()
        except ValidationError:
            cache.set(clave, cache.get(clave, 0) + 1, settings.LOGIN_BLOQUEO_SEG)
            raise

    def confirm_login_allowed(self, user):
        super().confirm_login_allowed(user)
        cache.delete(self._clave_bloqueo())


class ReenviarForm(ProtegidoMixin, forms.Form):
    email = forms.EmailField(label='Correo institucional')

    def __init__(self, *args, request=None, **kwargs):
        super().__init__(*args, **kwargs)
        self._proteger(request)

    def clean_email(self):
        email = (self.cleaned_data.get('email') or '').strip().lower()
        if not email.endswith(settings.DOMINIO_INSTITUCIONAL):
            raise ValidationError(f'Solo se permiten correos {settings.DOMINIO_INSTITUCIONAL}')
        return email


class PerfilForm(forms.ModelForm):
    """Nombre, teléfono y foto. La foto se valida en el servidor y se reduce a 512 px sin metadatos."""
    class Meta:
        model = Usuario
        fields = ['nombre', 'telefono', 'foto']

    def clean_foto(self):
        return imagenes.validar(self.cleaned_data.get('foto'))

    def save(self, commit=True):
        usuario = super().save(commit=False)
        nueva = self.cleaned_data.get('foto')
        if isinstance(nueva, UploadedFile):
            anterior = Usuario.objects.filter(pk=usuario.pk).values_list('foto', flat=True).first()
            usuario.foto.save(imagenes.nombre(f'u{usuario.pk}'), imagenes.reducir(nueva, 512), save=False)
            if anterior and anterior != usuario.foto.name:
                default_storage.delete(anterior)
        if commit:
            usuario.save()
        return usuario