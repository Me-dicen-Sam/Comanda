from django.contrib.auth.views import LogoutView
from django.urls import path

from . import views

urlpatterns = [
    path('registro/', views.registro, name='registro'),
    path('registro/enviado/', views.verificacion_enviada, name='verificacion_enviada'),
    path('verificar/<str:token>/', views.verificar, name='verificar'),
    path('reenviar-verificacion/', views.reenviar, name='reenviar'),
    path('captcha/', views.captcha_imagen, name='captcha'),
    path('ingresar/', views.Ingresar.as_view(), name='login'),
    path('salir/', LogoutView.as_view(), name='logout'),
    path('perfil/', views.perfil, name='perfil'),
]