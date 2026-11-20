from django.core.management.base import BaseCommand
from django.db import transaction

from catalogo.models import Bloque, Categoria, Establecimiento, Producto, TarifaDomicilio
from pedidos.models import DetallePedido


class Command(BaseCommand):
    help = 'Limpia productos anteriores y crea 5 cafeterías, 3 papelerías y productos con imágenes .jpg y variantes'

    @transaction.atomic
    def handle(self, *args, **options):
        # Borrar detalles y productos anteriores para dejar solo el catálogo nuevo limpio
        DetallePedido.objects.all().delete()
        Producto.objects.all().delete()

        # 1. Bloques base (si no existen)
        bloques_data = [
            ('Bloque A', '11.544400', '-72.907200'),
            ('Bloque B', '11.545100', '-72.906800'),
            ('Bloque C', '11.543900', '-72.906100'),
            ('Bloque D', '11.545800', '-72.905900'),
        ]
        bloques = {}
        for nombre, lat, lon in bloques_data:
            b, _ = Bloque.objects.get_or_create(
                nombre=nombre,
                defaults={'latitud': lat, 'longitud': lon},
            )
            bloques[nombre] = b

        # 2. Tarifas base de domicilio (si no existen)
        for dist, val in [(150, 2000), (350, 3000), (1000, 4000)]:
            TarifaDomicilio.objects.get_or_create(
                distancia_maxima_m=dist,
                defaults={'valor': val},
            )

        # 3. Categorías
        cats = {}
        for nombre in [
            'Bebidas',
            'Cafés y calientes',
            'Fritos y amasijos',
            'Comidas y snacks',
            'Combos',
            'Papelería',
            'Impresión',
        ]:
            c, _ = Categoria.objects.get_or_create(nombre=nombre)
            cats[nombre] = c

        # Opciones desplegables por producto
        opciones_por_producto = {
            'Gaseosa personal': 'Pepsi,Manzana,Uva,Cola,Coca-Cola',
            'Fritos': 'Papa de carne,Papa de pollo,Patacón,Buñuelo,Pastelito de pollo',
            'Empanada': 'Pollo,Carne',
            'Dedito': 'Queso,Queso + salchicha,Queso + bocadillo',
        }

        # 4. 5 Cafeterías (solo 2 tienen combos; empanada solo en Cafetería Central)
        cafeterias_cfg = [
            {
                'nombre': 'Cafetería Central',
                'bloque': bloques['Bloque A'],
                'descripcion': 'Desayunos, fritos, empanadas y combos rápidos.',
                'tipo': 'Cafetería',
                'emoji': '☕',
                'combos': [
                    ('Combo Panas', 10000, 'panas.jpg'),
                    ('Combo Mañanero', 4000, 'mananero.jpg'),
                    ('Combo Frito', 6500, 'cfrito.jpg'),
                ],
                'incluye_empanada': True,
            },
            {
                'nombre': 'Cafetería del Bloque B',
                'bloque': bloques['Bloque B'],
                'descripcion': 'Almuerzos, bebidas frías, sándwiches y combos.',
                'tipo': 'Cafetería',
                'emoji': '🍽️',
                'combos': [
                    ('Combo Estudio', 7500, 'estudio.jpg'),
                    ('Combo Tarde', 6000, 'tarde.jpg'),
                    ('Combo Almuerzo', 12000, 'calmuerzo.jpg'),
                ],
                'incluye_empanada': False,
            },
            {
                'nombre': 'Cooperativa Universitaria',
                'bloque': bloques['Bloque C'],
                'descripcion': 'Bebidas, amasijos y snacks estudiantiles.',
                'tipo': 'Cafetería',
                'emoji': '🥤',
                'combos': [],
                'incluye_empanada': False,
            },
            {
                'nombre': 'Rincón del Café',
                'bloque': bloques['Bloque D'],
                'descripcion': 'Café, chocolate, panadería y fritos variados.',
                'tipo': 'Cafetería',
                'emoji': '🥐',
                'combos': [],
                'incluye_empanada': False,
            },
            {
                'nombre': 'Punto Rápido Campus',
                'bloque': bloques['Bloque A'],
                'descripcion': 'Snacks, jugos, gaseosas y comidas ligeras.',
                'tipo': 'Cafetería',
                'emoji': '🥪',
                'combos': [],
                'incluye_empanada': False,
            },
        ]

        papelerias_cfg = [
            ('Papelería Central', bloques['Bloque A'], 'Útiles, cuadernos y servicio de impresión.', True),
            ('Papelería del Norte', bloques['Bloque B'], 'Útiles escolares y material de oficina.', False),
            ('Papelería Sur', bloques['Bloque C'], 'Cuadernos, carpetas, reglas y marcadores.', False),
        ]

        nombres_nuevos = [c['nombre'] for c in cafeterias_cfg] + [p[0] for p in papelerias_cfg]
        Establecimiento.objects.exclude(nombre__in=nombres_nuevos).update(activo=False, abierto=False)

        productos_base = [
            ('Agua pequeña', 1800, 'Bebidas', 'agua-pequena.jpg'),
            ('Agua grande', 2800, 'Bebidas', 'agua-grande.jpg'),
            ('Gaseosa personal', 3000, 'Bebidas', 'gaseosa.personal.jpg'),
            ('Jugo natural', 3500, 'Bebidas', 'jugo.jpg'),
            ('Chicha', 3000, 'Bebidas', 'chicha.jpg'),
            ('Frappé', 5500, 'Bebidas', 'frappe.jpg'),
            ('Café', 2000, 'Cafés y calientes', 'cafe.jpg'),
            ('Café con leche', 2500, 'Cafés y calientes', 'cafe-leche.jpg'),
            ('Fritos', 3500, 'Fritos y amasijos', 'fritos.jpg'),
            ('Dedito', 2500, 'Fritos y amasijos', 'dedito.jpg'),
            ('Arepa', 2500, 'Fritos y amasijos', 'arepa.jpg'),
            ('Panes', 2000, 'Fritos y amasijos', 'panes.jpg'),
            ('Sándwich', 5500, 'Comidas y snacks', 'sandwich.jpg'),
            ('Salchipapa', 8000, 'Comidas y snacks', 'salchipapa.jpg'),
            ('Sopa', 7000, 'Comidas y snacks', 'sopa.jpg'),
            ('Almuerzo 1', 11000, 'Comidas y snacks', 'almuerzo1.jpg'),
            ('Almuerzo 2', 11500, 'Comidas y snacks', 'almuerzo2.jpg'),
            ('Chocolatina', 2000, 'Comidas y snacks', 'chocolatina.jpg'),
            ('Papas Margarita', 2500, 'Comidas y snacks', 'papas-margarita.jpg'),
            ('Detodito', 3000, 'Comidas y snacks', 'detodito.jpg'),
            ('Amper', 3500, 'Bebidas', 'amper.jpg'),
        ]

        def crear_producto(est, prod_nombre, precio, cat_nombre, img_name):
            Producto.objects.create(
                establecimiento=est,
                categoria=cats[cat_nombre],
                nombre=prod_nombre,
                precio=precio,
                disponible=True,
                foto=f'img/productos/{img_name}',
                opciones=opciones_por_producto.get(prod_nombre, ''),
            )

        for cfg in cafeterias_cfg:
            est, created = Establecimiento.objects.get_or_create(
                nombre=cfg['nombre'],
                defaults={
                    'bloque': cfg['bloque'],
                    'descripcion': cfg['descripcion'],
                    'tipo': cfg['tipo'],
                    'emoji': cfg['emoji'],
                    'activo': True,
                    'abierto': True,
                },
            )
            if not created:
                est.bloque = cfg['bloque']
                est.descripcion = cfg['descripcion']
                est.tipo = cfg['tipo']
                est.emoji = cfg['emoji']
                est.activo = True
                est.abierto = True
                est.save(update_fields=['bloque', 'descripcion', 'tipo', 'emoji', 'activo', 'abierto'])

            for prod_nombre, precio, cat_nombre, img_name in productos_base:
                crear_producto(est, prod_nombre, precio, cat_nombre, img_name)

            if cfg['incluye_empanada']:
                crear_producto(est, 'Empanada', 2800, 'Fritos y amasijos', 'empanada.jpg')

            for combo_nombre, precio, img_name in cfg['combos']:
                crear_producto(est, combo_nombre, precio, 'Combos', img_name)

        productos_papeleria = [
            ('Agenda', 14000, 'Papelería', 'agenda.jpg'),
            ('Bloc', 6000, 'Papelería', 'bloc.jpg'),
            ('Carpetas', 3500, 'Papelería', 'carpetas.jpg'),
            ('Corrector', 3000, 'Papelería', 'corrector.jpg'),
            ('Cuaderno', 7500, 'Papelería', 'cuaderno.jpg'),
            ('Lapicero', 1500, 'Papelería', 'lapicero.jpg'),
            ('Regla', 2500, 'Papelería', 'regla.jpg'),
            ('Sacapunta', 1500, 'Papelería', 'sacapunta.jpg'),
        ]

        for nombre, bloque, desc, imprime in papelerias_cfg:
            pap, created = Establecimiento.objects.get_or_create(
                nombre=nombre,
                defaults={
                    'bloque': bloque,
                    'descripcion': desc,
                    'tipo': 'Papelería',
                    'emoji': '🖨️' if imprime else '📚',
                    'activo': True,
                    'abierto': True,
                },
            )
            if not created:
                pap.bloque = bloque
                pap.descripcion = desc
                pap.tipo = 'Papelería'
                pap.emoji = '🖨️' if imprime else '📚'
                pap.activo = True
                pap.abierto = True
                pap.save(update_fields=['bloque', 'descripcion', 'tipo', 'emoji', 'activo', 'abierto'])

            for prod_nombre, precio, cat_nombre, img_name in productos_papeleria:
                crear_producto(pap, prod_nombre, precio, cat_nombre, img_name)

            if imprime:
                crear_producto(pap, 'Servicio de impresión', 500, 'Impresión', 'impresion.jpg')

        self.stdout.write(self.style.SUCCESS('Catálogo limpiado y repoblado: 5 cafeterías, 3 papelerías y productos limpios.'))