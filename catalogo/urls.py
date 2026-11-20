from django.urls import path

from . import views

urlpatterns = [
    path('', views.inicio, name='inicio'),
    path('ubicacion/', views.ubicacion, name='ubicacion'),
    path('cafeteria/<int:establecimiento_id>/', views.catalogo, name='catalogo'),
    path('carrito/', views.carrito, name='carrito'),
    path('carrito/accion/', views.carrito_accion, name='carrito_accion'),
]
