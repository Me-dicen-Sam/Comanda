from django.contrib import admin
from .models import Bloque, Categoria, Establecimiento, Producto, TarifaDomicilio

admin.site.register([Bloque, Categoria, TarifaDomicilio])


@admin.register(Establecimiento)
class EstablecimientoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'tipo', 'bloque', 'activo', 'abierto', 'modo_manual')


@admin.register(Producto)
class ProductoAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'establecimiento', 'categoria', 'precio', 'disponible')
    list_filter = ('establecimiento', 'categoria', 'disponible')
