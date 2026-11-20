import math

from .models import TarifaDomicilio

ZONAS = ['Cerca', 'Media', 'Lejos']
TIEMPOS = {'Cerca': '10-15 min', 'Media': '15-20 min', 'Lejos': '20-25 min'}   # estimado mostrado al cliente


def distancia_m(b1, b2):
    """Distancia en metros entre dos bloques (fórmula de Haversine con sus coordenadas)."""
    r = 6371000
    f1, f2 = math.radians(float(b1.latitud)), math.radians(float(b2.latitud))
    df, dl = f2 - f1, math.radians(float(b2.longitud) - float(b1.longitud))
    a = math.sin(df / 2) ** 2 + math.cos(f1) * math.cos(f2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def tarifa_para(bloque_cliente, bloque_cafeteria):
    """Devuelve distancia, zona (Cerca/Media/Lejos) y valor del domicilio ($2.000, $3.000 o $4.000)."""
    d = distancia_m(bloque_cliente, bloque_cafeteria)
    tarifas = list(TarifaDomicilio.objects.all())
    if not tarifas:
        return {'distancia': round(d), 'zona': ZONAS[0], 'valor': 2000, 'tiempo': TIEMPOS[ZONAS[0]]}
    for i, t in enumerate(tarifas):
        if d <= t.distancia_maxima_m:
            return {'distancia': round(d), 'zona': ZONAS[min(i, 2)], 'valor': t.valor, 'tiempo': TIEMPOS[ZONAS[min(i, 2)]]}
    zona = ZONAS[min(len(tarifas) - 1, 2)]
    return {'distancia': round(d), 'zona': zona, 'valor': tarifas[-1].valor, 'tiempo': TIEMPOS[zona]}
