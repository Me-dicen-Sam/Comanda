from django.conf import settings
from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core import signing
from django.core.cache import cache
from django.http import HttpResponse
from django.shortcuts import redirect, render
from django.urls import reverse
from django.views.decorators.cache import never_cache

from catalogo.models import Bloque

from . import captcha
from .forms import LoginForm, PerfilForm, RegistroForm, ReenviarForm
from .models import Usuario
from .verificacion import enviar_verificacion, leer_token


def destino_por_rol(user):
    return {'cafeteria': 'panel_cafeteria', 'repartidor': 'panel_repartidor'}.get(user.rol, 'ubicacion')


@never_cache
def captcha_imagen(request):
    resp = HttpResponse(captcha.imagen_png(captcha.nuevo_texto(request)), content_type='image/png')
    resp['Cache-Control'] = 'no-store'
    return resp


def registro(request):
    if request.user.is_authenticated:
        return redirect(destino_por_rol(request.user))
    form = RegistroForm(request.POST or None, request=request)
    if request.method == 'POST' and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, f'¡Bienvenido a COMANDA, {user.nombre}!')
        return redirect(destino_por_rol(user))
    return render(request, 'accounts/registro.html', {'form': form})


def verificacion_enviada(request):
    return render(request, 'accounts/verificacion_enviada.html', {'email': request.session.get('verificacion_email', '')})


def verificar(request, token):
    try:
        user = leer_token(token)
    except signing.SignatureExpired:
        return render(request, 'accounts/verificacion_resultado.html', {'ok': False, 'caducado': True})
    except signing.BadSignature:
        return render(request, 'accounts/verificacion_resultado.html', {'ok': False})
    if user is None:
        return render(request, 'accounts/verificacion_resultado.html', {'ok': False})
    if not user.email_verificado:
        user.is_active, user.email_verificado = True, True
        user.save(update_fields=['is_active', 'email_verificado'])
    return render(request, 'accounts/verificacion_resultado.html', {'ok': True})


def reenviar(request):
    form = ReenviarForm(request.POST or None, request=request)
    if request.method == 'POST' and form.is_valid():
        email = form.cleaned_data['email'].lower()
        user = Usuario.objects.filter(email=email, email_verificado=False).first()
        if user and cache.add(f'reenvio:{email}', 1, 60):
            enviar_verificacion(request, user)
        request.session['verificacion_email'] = email
        return redirect('verificacion_enviada')
    return render(request, 'accounts/reenviar.html', {'form': form})


class Ingresar(LoginView):
    template_name = 'accounts/login.html'
    authentication_form = LoginForm
    redirect_authenticated_user = True

    def get_success_url(self):
        return self.get_redirect_url() or reverse(destino_por_rol(self.request.user))


@login_required
def perfil(request):
    usuario = Usuario.objects.get(pk=request.user.pk)
    form = PerfilForm(request.POST or None, request.FILES or None, instance=usuario)
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Perfil actualizado.')
        return redirect('perfil')
    return render(request, 'accounts/perfil.html', {'form': form, 'ubicacion_actual': ubicacion_de(request)})


def ubicacion_de(request):
    """La ubicación que el usuario eligió al entrar (bloque y piso, guardada en su sesión)."""
    datos = request.session.get('ubicacion')
    bloque = Bloque.objects.filter(pk=datos['bloque_id']).first() if datos else None
    return {'bloque': bloque, 'piso': datos['piso']} if bloque else None