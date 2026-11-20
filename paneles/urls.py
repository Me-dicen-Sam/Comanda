from django.urls import path

from . import views

urlpatterns = [
    path('tienda/', views.cafeteria, name='panel_cafeteria'),
    path('tienda/estado/', views.cafeteria_estado, name='cafeteria_estado'),
    path('tienda/datos/', views.cafeteria_tienda, name='cafeteria_tienda'),
    path('tienda/pedido/<int:pk>/', views.cafeteria_pedido, name='cafeteria_pedido'),
    path('tienda/producto/nuevo/', views.producto_crear, name='producto_crear'),
    path('tienda/producto/<int:pk>/', views.producto_editar, name='producto_editar'),
    path('tienda/producto/<int:pk>/rapido/', views.producto_rapido, name='producto_rapido'),
    path('reparto/', views.repartidor, name='panel_repartidor'),
    path('reparto/disponibilidad/', views.repartidor_disponibilidad, name='repartidor_disponibilidad'),
    path('reparto/pedido/<int:pk>/', views.repartidor_pedido, name='repartidor_pedido'),
]
