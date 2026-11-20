from django.urls import path

from . import views

urlpatterns = [
    path('pedido/crear/', views.crear, name='crear_pedido'),
    path('pedidos/', views.mis_pedidos, name='mis_pedidos'),
    path('pedido/<int:pk>/pago/', views.pago, name='pago'),
    path('pedido/<int:pk>/', views.seguimiento, name='seguimiento'),
    path('pedido/<int:pk>/estado/', views.estado_json, name='estado'),
    path('pedido/<int:pk>/cancelar/', views.cancelar, name='cancelar'),
    path('pedido/<int:pk>/decidir/', views.decidir, name='decidir'),
    path('pedido/<int:pk>/recibido/', views.recibido, name='recibido'),
    path('pedido/<int:pk>/calificar/', views.calificar, name='calificar'),
]
