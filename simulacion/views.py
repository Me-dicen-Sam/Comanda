from django.contrib import messages
from django.contrib.auth.decorators import user_passes_test
from django.db.models import Count, Sum
from django.forms import ModelForm
from django.shortcuts import redirect, render
from django.views.decorators.http import require_http_methods

from pedidos.models import HistorialEstado, Pedido, Repartidor, Viaje

from .demo import generar_demo, reiniciar_demo
from .models import Billetera, ConfiguracionSimulacion, Movimiento, Pago, SmsSimulado
from .motor import avanzar_todos

solo_staff = user_passes_test(lambda u: u.is_authenticated and u.is_staff, login_url='login')


@solo_staff
@require_http_methods(['GET', 'POST'])
def panel(request):
    if request.method == 'POST':
        if request.POST.get('accion') == 'generar':
            messages.success(request, f'Se generaron {generar_demo(15)} pedidos de demostración.')
        elif request.POST.get('accion') == 'reiniciar':
            messages.success(request, f'Se borraron {reiniciar_demo()} pedidos de demostración.')
        return redirect('panel')
    avanzar_todos()
    por_estado = {r['estado']: r['n'] for r in Pedido.objects.values('estado').annotate(n=Count('id'))}
    viajes = Viaje.objects.filter(activo=True).select_related('repartidor').prefetch_related('pedidos')
    return render(request, 'panel/panel.html', {
        'por_estado': [(label, por_estado.get(val, 0)) for val, label in Pedido.Estado.choices],
        'bitacora': HistorialEstado.objects.select_related('pedido').order_by('-creado_at', '-id')[:40],
        'viajes': viajes, 'sms': SmsSimulado.objects.all()[:12],
        'disponibles': Repartidor.objects.filter(estado='disponible').count(),
        'total_repartidores': Repartidor.objects.count()})


@solo_staff
def billeteras(request):
    wallets = Billetera.objects.select_related('establecimiento', 'repartidor').order_by('tipo', 'id')
    total_wallets = wallets.aggregate(s=Sum('saldo'))['s'] or 0
    liquidado = Pago.objects.filter(estado=Pago.Estado.LIQUIDADO).aggregate(s=Sum('monto'))['s'] or 0
    cargos = Movimiento.objects.filter(tipo=Movimiento.Tipo.REPARTO, pedido__pago__estado=Pago.Estado.REEMBOLSADO).aggregate(s=Sum('monto'))['s'] or 0
    doble = Viaje.objects.filter(activo=True).values('repartidor').annotate(n=Count('id')).filter(n__gt=1).count()
    return render(request, 'panel/billeteras.html', {
        'wallets': wallets, 'movimientos': Movimiento.objects.select_related('billetera', 'pedido')[:60],
        'total_wallets': total_wallets, 'esperado': liquidado + cargos, 'cuadra': total_wallets == liquidado + cargos,
        'doble': doble})


class ConfigForm(ModelForm):
    class Meta:
        model = ConfiguracionSimulacion
        fields = '__all__'


@solo_staff
def configuracion(request):
    form = ConfigForm(request.POST or None, instance=ConfiguracionSimulacion.obtener())
    if request.method == 'POST' and form.is_valid():
        form.save()
        messages.success(request, 'Configuración guardada.')
        return redirect('configuracion')
    return render(request, 'panel/configuracion.html', {'form': form})
