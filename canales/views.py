from django.db import models
from django.shortcuts import render, get_object_or_404
from .models import Liga, Canal, Video

def home(request):
    """Página principal con videos destacados y últimos videos"""
    destacados = Video.objects.filter(destacado=True, activo=True)[:6]
    ultimos = Video.objects.filter(activo=True)[:12]
    ligas = Liga.objects.filter(activa=True)
    canales = Canal.objects.filter(activo=True)

    context = {
        'destacados': destacados,
        'ultimos': ultimos,
        'ligas': ligas,
        'canales': canales,
    }
    return render(request, 'home.html', context)


def detalle_video(request, pk):
    """Página de reproducción de un video"""
    video = get_object_or_404(Video, pk=pk, activo=True)
    # Videos relacionados: misma liga o mismo canal
    relacionados = Video.objects.filter(activo=True).exclude(pk=pk).filter(
        models.Q(liga=video.liga) | models.Q(canal=video.canal)
    )[:8]

    context = {
        'video': video,
        'relacionados': relacionados,
    }
    return render(request, 'detalle_video.html', context)


def lista_canal(request, slug):
    """Videos de un canal específico"""
    canal = get_object_or_404(Canal, slug=slug, activo=True)
    videos = Video.objects.filter(canal=canal, activo=True)

    context = {
        'canal': canal,
        'videos': videos,
    }
    return render(request, 'canal.html', context)


def lista_liga(request, slug):
    """Videos de una liga específica"""
    liga = get_object_or_404(Liga, slug=slug, activa=True)
    videos = Video.objects.filter(liga=liga, activo=True)

    context = {
        'liga': liga,
        'videos': videos,
    }
    return render(request, 'liga.html', context)