from django.conf import settings
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models


def validar_correo_institucional(valor):
    if not valor.lower().endswith(settings.DOMINIO_INSTITUCIONAL):
        raise ValidationError(f'Solo se permiten correos {settings.DOMINIO_INSTITUCIONAL}')


class UsuarioManager(BaseUserManager):
    def create_user(self, email, password=None, **extra):
        if not email:
            raise ValueError('El correo es obligatorio')
        user = self.model(email=self.normalize_email(email).lower(), **extra)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra):
        extra.setdefault('is_staff', True)
        extra.setdefault('is_superuser', True)
        extra.setdefault('rol', 'admin')
        extra.setdefault('email_verificado', True)
        return self.create_user(email, password, **extra)


class Usuario(AbstractBaseUser, PermissionsMixin):
    """Tabla `usuario`. El correo institucional es el identificador único."""
    class Rol(models.TextChoices):
        CLIENTE = 'cliente', 'Cliente'
        CAFETERIA = 'cafeteria', 'Cafetería / papelería'
        REPARTIDOR = 'repartidor', 'Repartidor'
        ADMIN = 'admin', 'Administrador'

    email = models.EmailField('correo institucional', unique=True, validators=[validar_correo_institucional])
    nombre = models.CharField(max_length=120)
    telefono = models.CharField('teléfono', max_length=20, blank=True)
    foto = models.ImageField(upload_to='perfiles/', blank=True)
    bloque_habitual = models.ForeignKey('catalogo.Bloque', null=True, blank=True,
                                        on_delete=models.SET_NULL, related_name='+')
    rol = models.CharField(max_length=20, choices=Rol.choices, default=Rol.CLIENTE)
    # Solo para el rol "cafeteria": el establecimiento que administra.
    establecimiento = models.ForeignKey('catalogo.Establecimiento', null=True, blank=True,
                                        on_delete=models.SET_NULL, related_name='gestores')
    email_verificado = models.BooleanField(default=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    creado_at = models.DateTimeField(auto_now_add=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = ['nombre']
    objects = UsuarioManager()

    class Meta:
        db_table = 'usuario'

    def __str__(self):
        return self.email