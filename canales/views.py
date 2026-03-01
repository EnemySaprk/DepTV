from django.db.models import Q
from django.shortcuts import render, get_object_or_404
from .models import Liga, Canal, Video


def home(request):
    destacados = Video.objects.filter(destacado=True, activo=True)\
        .select_related('canal')\
        .prefetch_related('ligas')[:6]

    ultimos = Video.objects.filter(activo=True)\
        .select_related('canal')\
        .prefetch_related('ligas')[:12]

    context = {
        'destacados': destacados,
        'ultimos': ultimos,
    }
    return render(request, 'home.html', context)


def detalle_video(request, pk):
    video = get_object_or_404(
        Video.objects.select_related('canal').prefetch_related('ligas'),
        pk=pk, activo=True
    )
    video_ligas = video.ligas.all()
    relacionados = Video.objects.filter(activo=True).exclude(pk=pk).filter(
        Q(ligas__in=video_ligas) | Q(canal=video.canal)
    ).select_related('canal').prefetch_related('ligas').distinct()[:8]

    context = {
        'video': video,
        'relacionados': relacionados,
    }
    return render(request, 'detalle_video.html', context)


def lista_canal(request, slug):
    canal = get_object_or_404(Canal, slug=slug, activo=True)
    videos = Video.objects.filter(canal=canal, activo=True)\
        .select_related('canal')\
        .prefetch_related('ligas')

    context = {
        'canal': canal,
        'videos': videos,
    }
    return render(request, 'canal.html', context)


def lista_liga(request, slug):
    liga = get_object_or_404(Liga, slug=slug, activa=True)
    videos = Video.objects.filter(ligas=liga, activo=True)\
        .select_related('canal')\
        .prefetch_related('ligas').distinct()

    context = {
        'liga': liga,
        'videos': videos,
    }
    return render(request, 'liga.html', context)