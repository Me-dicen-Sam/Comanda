from django import forms
from django.core.files.storage import default_storage
from django.core.files.uploadedfile import UploadedFile

from catalogo import imagenes
from catalogo.models import Establecimiento, Producto


class _ConFoto:
    """Valida la foto y la guarda reducida; borra la anterior para no dejar archivos huérfanos."""
    prefijo, max_lado = 'f', 800

    def clean_foto(self):
        return imagenes.validar(self.cleaned_data.get('foto'))

    def save(self, commit=True):
        obj = super().save(commit=False)
        nueva = self.cleaned_data.get('foto')
        if isinstance(nueva, UploadedFile):
            anterior = type(obj).objects.filter(pk=obj.pk).values_list('foto', flat=True).first() if obj.pk else None
            obj.foto.save(imagenes.nombre(self.prefijo), imagenes.reducir(nueva, self.max_lado), save=False)
            if anterior and anterior != obj.foto.name:
                default_storage.delete(anterior)
        if commit:
            obj.save()
        return obj


class ProductoForm(_ConFoto, forms.ModelForm):
    prefijo = 'p'

    class Meta:
        model = Producto
        fields = ['nombre', 'categoria', 'precio', 'emoji', 'disponible', 'foto']
        labels = {'emoji': 'Ícono (si no hay foto)', 'precio': 'Precio (COP)'}

    def clean_precio(self):
        precio = self.cleaned_data['precio']
        if precio > 1_000_000:
            raise forms.ValidationError('El precio máximo es $1.000.000.')
        return precio


class TiendaForm(_ConFoto, forms.ModelForm):
    prefijo, max_lado = 't', 1200

    class Meta:
        model = Establecimiento
        fields = ['descripcion', 'emoji', 'foto']
        labels = {'descripcion': 'Descripción corta', 'emoji': 'Ícono (si no hay foto)'}
