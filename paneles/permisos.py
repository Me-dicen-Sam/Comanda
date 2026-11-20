from functools import wraps

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied


def rol_requerido(rol):
    """Solo entra quien tiene ese rol (y su vínculo: establecimiento o perfil de repartidor)."""
    def decorador(vista):
        @wraps(vista)
        @login_required
        def envoltura(request, *args, **kwargs):
            u = request.user
            if u.rol != rol:
                raise PermissionDenied
            if rol == 'cafeteria' and not u.establecimiento_id:
                raise PermissionDenied('Tu cuenta aún no tiene una cafetería asignada.')
            if rol == 'repartidor' and not hasattr(u, 'perfil_repartidor'):
                raise PermissionDenied('Tu cuenta aún no tiene un perfil de repartidor.')
            return vista(request, *args, **kwargs)
        return envoltura
    return decorador
