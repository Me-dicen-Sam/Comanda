from django.conf import settings


def calcular_reparto(subtotal, domicilio):
    """Reparte el dinero de un pedido entre las tres cuentas (pesos enteros).

    Cafetería: productos menos 8 %. Repartidor: 80 % del domicilio. COMANDA: el resto
    (8 % de comisión + 20 % del domicilio). Ejemplo: 15.000 + 3.000 -> 13.800 / 2.400 / 1.800.
    """
    comision = (subtotal * settings.COMISION_CAFETERIA_PCT + 50) // 100
    repartidor = (domicilio * settings.REPARTIDOR_PCT_DOMICILIO + 50) // 100
    cafeteria = subtotal - comision
    comanda = (subtotal + domicilio) - cafeteria - repartidor
    return {'cafeteria': cafeteria, 'repartidor': repartidor, 'comanda': comanda}
