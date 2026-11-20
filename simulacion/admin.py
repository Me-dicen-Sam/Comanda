from django.contrib import admin
from .models import Billetera, ConfiguracionSimulacion, Movimiento, Pago, SmsSimulado


class SoloLectura(admin.ModelAdmin):
    def has_add_permission(self, request): return False
    def has_change_permission(self, request, obj=None): return False
    def has_delete_permission(self, request, obj=None): return False


admin.site.register([Pago, Billetera, ConfiguracionSimulacion])
admin.site.register([Movimiento, SmsSimulado], SoloLectura)
