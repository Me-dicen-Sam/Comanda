from django.db import models


class Pago(models.Model):
    """Pago simulado tipo Nequi. OneToOne con pedido: un pedido no puede pagarse dos veces."""
    class Estado(models.TextChoices):
        PENDIENTE = 'pendiente', 'Pendiente'
        RETENIDO = 'retenido', 'Retenido (esperando el check de recibido)'
        LIQUIDADO = 'liquidado', 'Liquidado (repartido en las tres cuentas)'
        RECHAZADO = 'rechazado', 'Rechazado'
        REEMBOLSADO = 'reembolsado', 'Reembolsado'

    pedido = models.OneToOneField('pedidos.Pedido', on_delete=models.CASCADE, related_name='pago')
    numero_nequi = models.CharField(max_length=15)
    monto = models.PositiveIntegerField()
    codigo_confirmacion = models.CharField(max_length=12, blank=True)
    estado = models.CharField(max_length=20, choices=Estado.choices, default=Estado.PENDIENTE)
    creado_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'pago'


class Billetera(models.Model):
    """Saldo ficticio. Hay una por cafetería, una por repartidor y una de COMANDA."""
    class Tipo(models.TextChoices):
        CAFETERIA = 'cafeteria', 'Cafetería'
        REPARTIDOR = 'repartidor', 'Repartidor'
        COMANDA = 'comanda', 'COMANDA'

    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    establecimiento = models.OneToOneField('catalogo.Establecimiento', null=True, blank=True,
                                           on_delete=models.CASCADE, related_name='billetera')
    repartidor = models.OneToOneField('pedidos.Repartidor', null=True, blank=True,
                                      on_delete=models.CASCADE, related_name='billetera')
    saldo = models.BigIntegerField(default=0)

    class Meta:
        db_table = 'billetera'

    def __str__(self):
        return f'{self.get_tipo_display()} ({self.saldo})'


class Movimiento(models.Model):
    class Tipo(models.TextChoices):
        PAGO = 'pago', 'Pago (queda retenido)'
        REPARTO = 'reparto', 'Reparto'
        REEMBOLSO = 'reembolso', 'Reembolso'

    tipo = models.CharField(max_length=20, choices=Tipo.choices)
    pedido = models.ForeignKey('pedidos.Pedido', on_delete=models.PROTECT, related_name='movimientos')
    # En el movimiento tipo "pago" el dinero está retenido, por eso no hay billetera destino.
    billetera = models.ForeignKey(Billetera, null=True, blank=True, on_delete=models.PROTECT, related_name='movimientos')
    monto = models.BigIntegerField()
    creado_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'movimiento'
        ordering = ['-creado_at']


class ConfiguracionSimulacion(models.Model):
    """Una sola fila. Todos los valores se pueden cambiar desde el panel de administración."""
    seg_aceptar = models.PositiveIntegerField(default=5, help_text='Segundos hasta que la cafetería acepta')
    seg_preparar = models.PositiveIntegerField(default=20, help_text='Segundos de preparación')
    seg_asignar = models.PositiveIntegerField(default=5, help_text='Segundos hasta asignar repartidor')
    seg_en_camino = models.PositiveIntegerField(default=10, help_text='Segundos hasta salir de la cafetería')
    seg_entrega = models.PositiveIntegerField(default=90, help_text='Segundos en camino (1 a 2 minutos)')
    factor_velocidad = models.DecimalField(max_digits=5, decimal_places=2, default=1,
                                           help_text='2 = el doble de rápido')
    ventana_compartir_seg = models.PositiveIntegerField(default=120)
    diferencia_max_pisos = models.PositiveSmallIntegerField(default=1)
    cupo_por_viaje = models.PositiveSmallIntegerField(default=2)
    cargo_cancelar = models.PositiveIntegerField(default=0, help_text='Pesos; 0 = sin cargo')

    class Meta:
        db_table = 'configuracion_simulacion'
        verbose_name_plural = 'configuración de simulación'

    @classmethod
    def obtener(cls):
        return cls.objects.first() or cls.objects.create()


class SmsSimulado(models.Model):
    pedido = models.ForeignKey('pedidos.Pedido', on_delete=models.CASCADE, related_name='sms')
    numero = models.CharField(max_length=15)
    texto = models.CharField(max_length=300)
    creado_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'sms_simulado'
        ordering = ['-creado_at']
