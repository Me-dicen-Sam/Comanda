from django.contrib import admin
from .models import Calificacion, DetallePedido, HistorialEstado, Pedido, Repartidor, Viaje


class SoloLectura(admin.ModelAdmin):
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False


class DetalleInline(admin.TabularInline):
    model = DetallePedido
    extra = 0


@admin.register(Pedido)
class PedidoAdmin(admin.ModelAdmin):
    list_display = ('id', 'usuario', 'establecimiento', 'estado', 'total', 'es_demo', 'creado_at')
    list_filter = ('estado', 'es_demo', 'establecimiento')
    inlines = [DetalleInline]


@admin.register(Repartidor)
class RepartidorAdmin(admin.ModelAdmin):
    list_display = ('nombre', 'vehiculo', 'estado', 'promedio')
    list_filter = ('estado',)


admin.site.register([Viaje, Calificacion])
admin.site.register(HistorialEstado, SoloLectura)  # el historial no se edita ni se borra
