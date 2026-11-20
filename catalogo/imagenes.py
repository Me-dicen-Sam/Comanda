"""Validación y reducción de fotos subidas (perfil, productos, tiendas, bloques)."""
import io
import secrets

from django.core.exceptions import ValidationError
from django.core.files.base import ContentFile
from django.core.files.uploadedfile import UploadedFile
from PIL import Image, ImageOps

MAX_BYTES = 2 * 1024 * 1024


def validar(foto):
    """Para usar dentro de clean_<campo>: formato real (no solo la extensión) y peso."""
    if isinstance(foto, UploadedFile):
        if foto.size > MAX_BYTES:
            raise ValidationError('La foto no puede pesar más de 2 MB.')
        if getattr(getattr(foto, 'image', None), 'format', None) not in ('JPEG', 'PNG', 'WEBP'):
            raise ValidationError('Usa una imagen JPG, PNG o WEBP.')
    return foto


def reducir(archivo, max_lado=512):
    """Devuelve un JPEG reducido, sin metadatos (EXIF/GPS) y con la orientación corregida."""
    img = ImageOps.exif_transpose(Image.open(archivo))
    if img.mode in ('RGBA', 'LA', 'P'):
        fondo = Image.new('RGB', img.size, (255, 255, 255))
        img = img.convert('RGBA')
        fondo.paste(img, mask=img.split()[-1])
        img = fondo
    img = img.convert('RGB')
    img.thumbnail((max_lado, max_lado))
    salida = io.BytesIO()
    img.save(salida, 'JPEG', quality=85, optimize=True)
    return ContentFile(salida.getvalue())


def nombre(prefijo):
    return f'{prefijo}-{secrets.token_hex(4)}.jpg'
