"""Captcha propio de imagen, sin servicios externos. La respuesta vive solo en la sesión del servidor
(nunca en la página), caduca en 5 minutos y sirve una sola vez. Para producción se puede cambiar por
Cloudflare Turnstile o reCAPTCHA sin tocar el resto del código: solo `verificar`."""
import io
import random
import secrets
import time

from django.conf import settings
from PIL import Image, ImageDraw, ImageFilter, ImageFont

ALFABETO = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'   # sin O, 0, I, 1: se confunden
VIDA_SEG = 300


def nuevo_texto(request, largo=5):
    texto = ''.join(secrets.choice(ALFABETO) for _ in range(largo))
    request.session['captcha'] = {'t': texto, 'e': time.time() + VIDA_SEG}
    return texto


def imagen_png(texto):
    ancho, alto = 190, 64
    img = Image.new('RGB', (ancho, alto), (255, 253, 248))
    d = ImageDraw.Draw(img)
    rnd = random.SystemRandom()
    for _ in range(7):                                   # líneas de ruido
        d.line([(rnd.randint(0, ancho), rnd.randint(0, alto)), (rnd.randint(0, ancho), rnd.randint(0, alto))],
               fill=(rnd.randint(150, 210),) * 3, width=rnd.randint(1, 2))
    fuente = ImageFont.load_default(size=40)
    paso = ancho // (len(texto) + 1)
    for i, letra in enumerate(texto):                    # cada letra rotada y a distinta altura
        capa = Image.new('RGBA', (56, 56), (0, 0, 0, 0))
        ImageDraw.Draw(capa).text((10, 2), letra, font=fuente, fill=(41 + rnd.randint(0, 40), 37, 31, 255))
        capa = capa.rotate(rnd.randint(-22, 22), expand=False, resample=Image.BICUBIC)
        img.paste(capa, (10 + i * paso, rnd.randint(0, 8)), capa)
    for _ in range(140):                                 # puntos de ruido
        d.point((rnd.randint(0, ancho), rnd.randint(0, alto)), fill=(rnd.randint(90, 200),) * 3)
    img = img.filter(ImageFilter.SMOOTH)
    salida = io.BytesIO()
    img.save(salida, 'PNG')
    return salida.getvalue()


def verificar(request, respuesta):
    """True si la respuesta coincide. Siempre consume el captcha (un solo intento por imagen)."""
    if not settings.CAPTCHA_ENABLED:
        return True
    dato = request.session.pop('captcha', None)
    if not dato or time.time() > dato['e']:
        return False
    return secrets.compare_digest(dato['t'], (respuesta or '').strip().upper().replace(' ', ''))
