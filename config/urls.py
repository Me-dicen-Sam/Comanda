from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from . import pwa

handler403 = 'paneles.errores.prohibido'

urlpatterns = [
    path('manifest.webmanifest', pwa.manifest, name='manifest'),
    path('service-worker.js', pwa.service_worker, name='service_worker'),
    path('admin/', admin.site.urls),
    path('', include('accounts.urls')),
    path('', include('catalogo.urls')),
    path('', include('pedidos.urls')),
    path('', include('simulacion.urls')),
    path('', include('paneles.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
