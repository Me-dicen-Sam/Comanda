from django.urls import path

from . import views

urlpatterns = [
    path('simulacion/', views.panel, name='panel'),
    path('simulacion/billeteras/', views.billeteras, name='billeteras'),
    path('simulacion/configuracion/', views.configuracion, name='configuracion'),
]
