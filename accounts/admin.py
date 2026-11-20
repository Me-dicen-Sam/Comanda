from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import Usuario


@admin.register(Usuario)
class UsuarioAdmin(UserAdmin):
    ordering = ('email',)
    list_display = ('email', 'nombre', 'rol', 'establecimiento', 'email_verificado', 'is_active')
    list_filter = ('rol', 'email_verificado', 'is_active')
    search_fields = ('email', 'nombre')
    fieldsets = ((None, {'fields': ('email', 'password')}),
                 ('Perfil', {'fields': ('nombre', 'telefono', 'bloque_habitual')}),
                 ('Rol', {'fields': ('rol', 'establecimiento', 'email_verificado')}),
                 ('Permisos', {'fields': ('is_active', 'is_staff', 'is_superuser', 'groups', 'user_permissions')}))
    add_fieldsets = ((None, {'classes': ('wide',), 'fields': ('email', 'nombre', 'rol', 'establecimiento', 'email_verificado', 'password1', 'password2')}),)
