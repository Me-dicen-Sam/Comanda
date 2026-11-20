from django.core.management.base import BaseCommand

from accounts.models import Usuario
from catalogo.models import Bloque, Categoria, Establecimiento, Producto, TarifaDomicilio
from pedidos.models import Repartidor
from simulacion.models import Billetera, ConfiguracionSimulacion

NOMBRES = ['Carlos', 'Luis', 'Andrés', 'Jorge', 'Camilo', 'Daniel', 'Miguel', 'Juan', 'Sergio', 'Felipe',
           'Valentina', 'Laura', 'Camila', 'Sofía', 'Mariana', 'Daniela', 'Paola', 'Natalia', 'Karen', 'Isabel',
           'Esteban', 'Mateo']
APELLIDOS = ['Pérez', 'Gómez', 'Epieyú', 'Uriana', 'Ipuana', 'Pushaina', 'Barros', 'Fuentes', 'Mejía', 'Redondo']
VEHICULOS = ['moto', 'bicicleta', 'a_pie']


EMOJIS = {'Café tinto': '☕', 'Jugo natural': '🧃', 'Dedito de queso': '🧀', 'Empanada': '🥟', 'Galletas': '🍪',
          'Gaseosa': '🥤', 'Sándwich': '🥪', 'Arepa con queso': '🫓', 'Cuaderno': '📒', 'Esfero': '🖊️', 'Fotocopia': '📄'}


class Command(BaseCommand):
    help = 'Carga datos de demostración (bloques, cafeterías, productos, tarifas y 22 repartidores ficticios).'

    def handle(self, *args, **opts):
        base_lat, base_lon = 11.5200, -72.9150   # PROVISIONAL: reemplazar por las coordenadas reales de los bloques
        bloques = []
        for i in range(1, 9):
            b, _ = Bloque.objects.get_or_create(nombre=f'Bloque {i}', defaults={
                'latitud': base_lat + (i % 3) * 0.0009, 'longitud': base_lon + (i // 3) * 0.0011})
            bloques.append(b)
        for dist, valor in [(120, 2000), (260, 3000), (100000, 4000)]:
            TarifaDomicilio.objects.get_or_create(distancia_maxima_m=dist, defaults={'valor': valor})
        bebidas, comidas, papel, snacks = [Categoria.objects.get_or_create(nombre=n)[0] for n in ('Bebidas', 'Comidas', 'Papelería', 'Snacks')]
        menu = {
            ('Cafetería 1', bloques[0]): [(bebidas, 'Café tinto', 2000), (bebidas, 'Jugo natural', 3500), (comidas, 'Dedito de queso', 2500), (comidas, 'Empanada', 2500), (snacks, 'Galletas', 1500)],
            ('Cafetería 2', bloques[4]): [(bebidas, 'Gaseosa', 2500), (comidas, 'Sándwich', 6000), (comidas, 'Arepa con queso', 4000)],
            ('Papelería 1', bloques[7]): [(papel, 'Cuaderno', 5000), (papel, 'Esfero', 1000), (papel, 'Fotocopia', 200)],
        }
        for (nombre, bloque), prods in menu.items():
            est, _ = Establecimiento.objects.get_or_create(nombre=nombre, defaults={
                'bloque': bloque, 'tipo': 'Papelería' if 'Papel' in nombre else 'Cafetería',
                'emoji': '✏️' if 'Papel' in nombre else '☕'})
            Billetera.objects.get_or_create(establecimiento=est, defaults={'tipo': 'cafeteria'})
            for cat, pn, precio in prods:
                Producto.objects.get_or_create(establecimiento=est, nombre=pn, defaults={
                    'categoria': cat, 'precio': precio, 'emoji': EMOJIS.get(pn, '🍽️')})
        if Repartidor.objects.count() < 20:
            for i in range(22):
                r = Repartidor.objects.create(nombre=f'{NOMBRES[i]} {APELLIDOS[i % len(APELLIDOS)]}', vehiculo=VEHICULOS[i % 3],
                                              telefono=f'3{100000000 + i * 7919:09d}')
                Billetera.objects.get_or_create(repartidor=r, defaults={'tipo': 'repartidor'})
        if not Billetera.objects.filter(tipo='comanda').exists():
            Billetera.objects.create(tipo='comanda')
        ConfiguracionSimulacion.obtener()
        cuentas = [('tienda.demo@uniguajira.edu.co', 'tienda12345', 'Tienda demo', 'cafeteria'),
                   ('domiciliario.demo@uniguajira.edu.co', 'reparto12345', 'Domiciliario demo', 'repartidor')]
        for correo, clave, nombre, rol in cuentas:
            if not Usuario.objects.filter(email=correo).exists():
                u = Usuario.objects.create_user(correo, clave, nombre=nombre, rol=rol, email_verificado=True)
                if rol == 'cafeteria':
                    u.establecimiento = Establecimiento.objects.get(nombre='Cafetería 1')
                    u.save(update_fields=['establecimiento'])
                else:   # empieza en pausa: así los pedidos demo siguen su curso con los repartidores ficticios
                    r = Repartidor.objects.create(usuario=u, nombre=nombre, vehiculo='a_pie', telefono='3000000000', estado='pausado')
                    Billetera.objects.get_or_create(repartidor=r, defaults={'tipo': 'repartidor'})
                self.stdout.write(f'Cuenta demo: {correo} / {clave}  (CÁMBIALA)')
        if not Usuario.objects.filter(email='admin@uniguajira.edu.co').exists():
            Usuario.objects.create_superuser('admin@uniguajira.edu.co', 'admin12345', nombre='Administrador')
            self.stdout.write('Superusuario: admin@uniguajira.edu.co / admin12345  (CÁMBIALA)')
        self.stdout.write(self.style.SUCCESS('Datos de demostración listos.'))
