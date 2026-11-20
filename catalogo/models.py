from django.db import models


class Bloque(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    latitud = models.DecimalField(max_digits=9, decimal_places=6)
    longitud = models.DecimalField(max_digits=9, decimal_places=6)
    foto = models.ImageField(upload_to='bloques/', blank=True)

    class Meta:
        db_table = 'bloque'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class TarifaDomicilio(models.Model):
    """Si la distancia es <= distancia_maxima_m se cobra `valor` (2.000, 3.000 o 4.000)."""
    distancia_maxima_m = models.PositiveIntegerField(unique=True)
    valor = models.PositiveIntegerField(help_text='Pesos colombianos')

    class Meta:
        db_table = 'tarifa_domicilio'
        ordering = ['distancia_maxima_m']

    def __str__(self):
        return f'hasta {self.distancia_maxima_m} m: ${self.valor}'


class Establecimiento(models.Model):
    nombre = models.CharField(max_length=120)
    bloque = models.ForeignKey(Bloque, on_delete=models.PROTECT, related_name='establecimientos')
    descripcion = models.CharField(max_length=255, blank=True)
    tipo = models.CharField(max_length=50, default='Cafetería', help_text='Cafetería, papelería...')
    emoji = models.CharField(max_length=12, default='🏪', blank=True)
    foto = models.ImageField(upload_to='tiendas/', blank=True)
    activo = models.BooleanField(default=True, help_text='Visible para los clientes')
    abierto = models.BooleanField(default=True, help_text='Recibe pedidos ahora mismo')
    modo_manual = models.BooleanField(default=False, help_text='Si está activo, el personal acepta y marca listo cada pedido; si no, lo hace el bot')

    class Meta:
        db_table = 'establecimiento'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Categoria(models.Model):
    nombre = models.CharField(max_length=80, unique=True)

    class Meta:
        db_table = 'categoria'
        ordering = ['nombre']

    def __str__(self):
        return self.nombre


class Producto(models.Model):
    establecimiento = models.ForeignKey(Establecimiento, on_delete=models.CASCADE, related_name='productos')
    categoria = models.ForeignKey(Categoria, on_delete=models.PROTECT, related_name='productos')
    nombre = models.CharField(max_length=120)
    precio = models.PositiveIntegerField(help_text='Pesos colombianos')
    disponible = models.BooleanField(default=True)
    emoji = models.CharField(max_length=12, default='🍽️', blank=True)
    foto = models.ImageField(upload_to='productos/', blank=True)
    opciones = models.CharField(
        max_length=255,
        blank=True,
        help_text='Opciones separadas por coma, ej: Pepsi,Manzana,Uva,Cola,Coca-Cola',
    )

    class Meta:
        db_table = 'producto'
        ordering = ['nombre']

    def lista_opciones(self):
        return [o.strip() for o in self.opciones.split(',') if o.strip()]

    def __str__(self):
        return f'{self.nombre} (${self.precio})'