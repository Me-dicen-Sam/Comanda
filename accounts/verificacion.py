from django.conf import settings
from django.core import signing
from django.core.mail import send_mail
from django.urls import reverse

from .models import Usuario

SALT = 'comanda.verificacion.correo'


def generar_token(user):
    return signing.dumps({'uid': user.pk, 'email': user.email}, salt=SALT)


def leer_token(token, max_age=None):
    horas = getattr(settings, 'EMAIL_VERIFICACION_HORAS', 24)
    limite = max_age if max_age is not None else int(horas) * 3600
    datos = signing.loads(token, salt=SALT, max_age=limite)
    uid = datos.get('uid')
    email = (datos.get('email') or '').lower()
    user = Usuario.objects.filter(pk=uid, email=email).first()
    return user


def enviar_verificacion(request, user):
    if not getattr(settings, 'EMAIL_VERIFICACION_OBLIGATORIA', False):
        return False
    token = generar_token(user)
    ruta = reverse('verificar', kwargs={'token': token})
    enlace = request.build_absolute_uri(ruta) if request else ruta
    asunto = 'Confirmación de cuenta - COMANDA'
    mensaje = (
        f'Hola {user.nombre},\n\n'
        f'Activa tu cuenta en COMANDA desde este enlace:\n{enlace}\n'
    )
    send_mail(
        subject=asunto,
        message=mensaje,
        from_email=getattr(settings, 'DEFAULT_FROM_EMAIL', 'no-responder@comanda.local'),
        recipient_list=[user.email],
        fail_silently=True,
    )
    return True