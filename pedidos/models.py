from django.conf import settings
from django.db import models


class Repartidor(models.Model):
    """Repartidor ficticio (pool de 20 o más)."""
    class Estado(models.TextChoices):
        DISPONIBLE = 'disponible', 'Disponible'
        EN_SERVICIO = 'en_servicio', 'En servicio'
        PAUSADO = 'pausado', 'No disponible'

    class Vehiculo(models.TextChoices):
        MOTO = 'moto', 'Moto'
        BICICLETA = 'bicicleta', 'Bicicleta'
        A_PIE = 'a_pie', 'A pie'

    usuario = models.OneToOneField(settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
                                   related_name='perfil_repartidor')
    nombre = models.CharField(max_length=120)
    foto = models.ImageField(upload_to='repartidores/', blank=True)
    vehiculo = models.CharField(max_length=20, choices=Vehiculo.choices, default=Vehiculo.A_PIE)
    telefono = models.CharField(max_length=20, blank=True)
    promedio = models.DecimalField(max_digits=3, decimal_places=2, default=0)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.DISPONIBLE, db_index=True)

    class Meta:
        db_table = 'repartidor'

    def __str__(self):
        return self.nombre


class Viaje(models.Model):
    """Agrupa 1 o 2 pedidos de un mismo repartidor."""
    repartidor = models.ForeignKey(Repartidor, on_delete=models.PROTECT, related_name='viajes')
    activo = models.BooleanField(default=True, db_index=True)
    creado_at = models.DateTimeField(auto_now_add=True)
    cerrado_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = 'viaje'


class Pedido(models.Model):
    class Estado(models.TextChoices):
        PENDIENTE_PAGO = 'pendiente_pago', 'Pendiente de pago'
        PAGADO = 'pagado', 'Pagado'
        ACEPTADO = 'aceptado', 'Aceptado'
        PREPARANDO = 'preparando', 'Preparando'
        PENDIENTE_DECISION = 'pendiente_decision', 'Pendiente de decisión'
        ASIGNADO = 'asignado', 'Asignado'
        LISTO = 'listo', 'Listo'
        EN_CAMINO = 'en_camino', 'En camino'
        ENTREGADO = 'entregado', 'Entregado'
        RECIBIDO = 'recibido', 'Recibido'
        CALIFICADO = 'calificado', 'Calificado'
        CANCELADO = 'cancelado', 'Cancelado'

    class CanceladoPor(models.TextChoices):
        CLIENTE = 'cliente', 'Cliente'
        CAFETERIA = 'cafeteria', 'Cafetería (bot)'
        SISTEMA = 'sistema', 'Sistema (pago rechazado)'

    usuario = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.PROTECT, related_name='pedidos')
    establecimiento = models.ForeignKey('catalogo.Establecimiento', on_delete=models.PROTECT, related_name='pedidos')
    viaje = models.ForeignKey(Viaje, null=True, blank=True, on_delete=models.SET_NULL, related_name='pedidos')
    bloque = models.ForeignKey('catalogo.Bloque', on_delete=models.PROTECT, related_name='+')
    piso = models.PositiveSmallIntegerField()
    referencia_entrega = models.CharField(max_length=120, blank=True)
    archivo_impresion = models.FileField(upload_to='impresiones/', blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE_PAGO, db_index=True)
    subtotal = models.PositiveIntegerField()
    domicilio = models.PositiveIntegerField()
    total = models.PositiveIntegerField()
    prog_aceptado = models.DateTimeField(null=True, blank=True)
    prog_preparado = models.DateTimeField(null=True, blank=True)
    prog_asignado = models.DateTimeField(null=True, blank=True)
    prog_en_camino = models.DateTimeField(null=True, blank=True)
    prog_entregado = models.DateTimeField(null=True, blank=True)
    cancelado_por = models.CharField(max_length=20, choices=CanceladoPor.choices, blank=True)
    motivo_cancelacion = models.CharField(max_length=255, blank=True)
    recibido_at = models.DateTimeField(null=True, blank=True)
    es_demo = models.BooleanField(default=False, db_index=True)
    creado_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'pedido'
        ordering = ['-creado_at']
        indexes = [models.Index(fields=['usuario', '-creado_at'])]

    def __str__(self):
        return f'Pedido #{self.pk} ({self.estado})'


class DetallePedido(models.Model):
    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='detalles')
    producto = models.ForeignKey('catalogo.Producto', on_delete=models.PROTECT, related_name='+')
    opcion = models.CharField(max_length=80, blank=True)
    cantidad = models.PositiveSmallIntegerField()
    precio_unitario = models.PositiveIntegerField(help_text='Precio al momento de pedir')

    class Meta:
        db_table = 'detalle_pedido'


class HistorialEstado(models.Model):
    """Registro de cada cambio de estado. No se edita ni se borra."""
    class Actor(models.TextChoices):
        CLIENTE = 'cliente', 'Cliente'
        BOT_CAFETERIA = 'bot_cafeteria', 'Bot de la cafetería'
        BOT_REPARTIDOR = 'bot_repartidor', 'Bot del repartidor'
        CAFETERIA = 'cafeteria', 'Personal de la cafetería'
        REPARTIDOR = 'repartidor', 'Repartidor'
        SISTEMA = 'sistema', 'Sistema'

    pedido = models.ForeignKey(Pedido, on_delete=models.CASCADE, related_name='historial')
    estado_anterior = models.CharField(max_length=20, blank=True)
    estado_nuevo = models.CharField(max_length=20)
    actor = models.CharField(max_length=20, choices=Actor.choices)
    creado_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'historial_estado'
        ordering = ['creado_at', 'id']


class Calificacion(models.Model):
    pedido = models.OneToOneField(Pedido, on_delete=models.CASCADE, related_name='calificacion')
    puntaje_cafeteria = models.PositiveSmallIntegerField()   # 1 a 5
    puntaje_repartidor = models.PositiveSmallIntegerField()  # 1 a 5
    comentario = models.CharField(max_length=255, blank=True)
    creado_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'calificacion'