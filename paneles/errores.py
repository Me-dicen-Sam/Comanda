from django.shortcuts import render


def prohibido(request, exception=None):
    return render(request, '403.html', {'detalle': str(exception) if exception else ''}, status=403)
