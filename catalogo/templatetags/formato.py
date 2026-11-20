from django import template

register = template.Library()

# Clases completas (Tailwind las encuentra al escanear este archivo)
ESTADO_CLASES = {
    'pendiente_pago': 'bg-gray-100 text-gray-700',
    'pagado': 'bg-amber-100 text-amber-800',
    'aceptado': 'bg-amber-100 text-amber-800',
    'preparando': 'bg-orange-100 text-orange-800',
    'pendiente_decision': 'bg-purple-100 text-purple-800',
    'asignado': 'bg-blue-100 text-blue-800',
    'listo': 'bg-sky-100 text-sky-800',
    'en_camino': 'bg-indigo-100 text-indigo-800',
    'entregado': 'bg-green-100 text-green-800',
    'recibido': 'bg-green-100 text-green-800',
    'calificado': 'bg-emerald-100 text-emerald-800',
    'cancelado': 'bg-red-100 text-red-700',
}


@register.filter
def cop(valor):
    try:
        return '$' + f'{int(valor):,}'.replace(',', '.')
    except (TypeError, ValueError):
        return valor


@register.filter
def iniciales(nombre):
    return ''.join(p[0] for p in str(nombre).split()[:2]).upper() or '?'


@register.filter
def chip_estado(estado):
    return ESTADO_CLASES.get(estado, 'bg-gray-100 text-gray-700')
