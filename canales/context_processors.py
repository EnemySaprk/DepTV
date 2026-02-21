from .models import Liga, Canal


def sidebar_data(request):
    return {
        'canales_sidebar': Canal.objects.filter(activo=True)[:10],
        'ligas_sidebar': Liga.objects.filter(activa=True)[:10],
    }