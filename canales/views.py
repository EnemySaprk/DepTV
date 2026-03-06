from django.db.models import Q
from django.shortcuts import render, get_object_or_404
from .models import Liga, Canal, Video, BannerImagen


def home(request):
    banners = BannerImagen.objects.filter(activo=True, canal__isnull=True, liga__isnull=True)
    if not banners.exists():
        banners = BannerImagen.objects.filter(activo=True)[:5]

    canales_con_videos = []
    for canal in Canal.objects.filter(activo=True):
        videos = Video.objects.filter(canal=canal, activo=True)\
            .select_related('canal').prefetch_related('ligas')
        if videos.exists():
            canales_con_videos.append({
                'canal': canal,
                'videos': videos,
            })

    ligas_con_videos = []
    for liga in Liga.objects.filter(activa=True):
        videos = Video.objects.filter(ligas=liga, activo=True)\
            .select_related('canal').prefetch_related('ligas').distinct()
        if videos.exists():
            ligas_con_videos.append({
                'liga': liga,
                'videos': videos,
            })

    context = {
        'banners': banners,
        'canales_con_videos': canales_con_videos,
        'ligas_con_videos': ligas_con_videos,
    }
    return render(request, 'home.html', context)


def detalle_video(request, pk):
    video = get_object_or_404(
        Video.objects.select_related('canal').prefetch_related('ligas', 'enlaces'),
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
    banners = BannerImagen.objects.filter(canal=canal, activo=True)
    videos = Video.objects.filter(canal=canal, activo=True)\
        .select_related('canal')\
        .prefetch_related('ligas')

    context = {
        'canal': canal,
        'banners': banners,
        'videos': videos,
    }
    return render(request, 'canal.html', context)


def lista_liga(request, slug):
    liga = get_object_or_404(Liga, slug=slug, activa=True)
    banners = BannerImagen.objects.filter(liga=liga, activo=True)
    videos = Video.objects.filter(ligas=liga, activo=True)\
        .select_related('canal')\
        .prefetch_related('ligas').distinct()

    context = {
        'liga': liga,
        'banners': banners,
        'videos': videos,
    }
    return render(request, 'liga.html', context)
