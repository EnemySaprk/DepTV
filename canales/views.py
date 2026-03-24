from datetime import date, timedelta

from django.db.models import Q
from django.shortcuts import render, get_object_or_404

from .models import Liga, Canal, Video, BannerImagen, Partido


# ──────────────────────────────────────────────────────────────
# HOME
# ──────────────────────────────────────────────────────────────
def home(request):
    banners = BannerImagen.objects.filter(activo=True, canal__isnull=True, liga__isnull=True)
    if not banners.exists():
        banners = BannerImagen.objects.filter(activo=True)[:5]

    canales_con_videos = []
    for canal in Canal.objects.filter(activo=True):
        videos = (
            Video.objects
            .filter(canal=canal, activo=True)
            .select_related('canal')
            .prefetch_related('ligas')
        )
        if videos.exists():
            canales_con_videos.append({'canal': canal, 'videos': videos})

    ligas_con_videos = []
    for liga in Liga.objects.filter(activa=True):
        videos = (
            Video.objects
            .filter(ligas=liga, activo=True)
            .select_related('canal')
            .prefetch_related('ligas')
            .distinct()
        )
        if videos.exists():
            ligas_con_videos.append({'liga': liga, 'videos': videos})

    partidos_hoy = Partido.objects.filter(fecha=date.today()).order_by('hora')[:12]

    context = {
        'banners': banners,
        'canales_con_videos': canales_con_videos,
        'ligas_con_videos': ligas_con_videos,
        'partidos_hoy': partidos_hoy,
    }
    return render(request, 'home.html', context)


# ──────────────────────────────────────────────────────────────
# DETALLE VIDEO
# ──────────────────────────────────────────────────────────────
def detalle_video(request, pk):
    video = get_object_or_404(
        Video.objects.select_related('canal').prefetch_related('ligas', 'enlaces'),
        pk=pk, activo=True,
    )
    video_ligas = video.ligas.all()
    relacionados = (
        Video.objects
        .filter(activo=True)
        .exclude(pk=pk)
        .filter(Q(ligas__in=video_ligas) | Q(canal=video.canal))
        .select_related('canal')
        .prefetch_related('ligas')
        .distinct()[:8]
    )

    context = {'video': video, 'relacionados': relacionados}
    return render(request, 'detalle_video.html', context)


# ──────────────────────────────────────────────────────────────
# CANAL
# ──────────────────────────────────────────────────────────────
def lista_canal(request, slug):
    canal = get_object_or_404(Canal, slug=slug, activo=True)
    banners = BannerImagen.objects.filter(canal=canal, activo=True)
    videos = (
        Video.objects
        .filter(canal=canal, activo=True)
        .select_related('canal')
        .prefetch_related('ligas')
    )

    context = {'canal': canal, 'banners': banners, 'videos': videos}
    return render(request, 'canal.html', context)


# ──────────────────────────────────────────────────────────────
# LIGA
# ──────────────────────────────────────────────────────────────
def lista_liga(request, slug):
    liga = get_object_or_404(Liga, slug=slug, activa=True)
    banners = BannerImagen.objects.filter(liga=liga, activo=True)
    videos = (
        Video.objects
        .filter(ligas=liga, activo=True)
        .select_related('canal')
        .prefetch_related('ligas')
        .distinct()
    )

    context = {'liga': liga, 'banners': banners, 'videos': videos}
    return render(request, 'liga.html', context)


# ──────────────────────────────────────────────────────────────
# AGENDA
# ──────────────────────────────────────────────────────────────
def agenda(request):
    fecha_str = request.GET.get('fecha')
    if fecha_str:
        try:
            fecha_sel = date.fromisoformat(fecha_str)
        except ValueError:
            fecha_sel = date.today()
    else:
        fecha_sel = date.today()

    partidos = Partido.objects.filter(fecha=fecha_sel).order_by('hora')

    ligas_partidos = {}
    for partido in partidos:
        key = partido.liga_nombre
        if key not in ligas_partidos:
            ligas_partidos[key] = {'logo': partido.liga_logo, 'partidos': []}
        ligas_partidos[key]['partidos'].append(partido)

    dias = [
        {
            'fecha': date.today() + timedelta(days=i),
            'es_hoy': i == 0,
            'es_seleccionado': date.today() + timedelta(days=i) == fecha_sel,
        }
        for i in range(-3, 4)
    ]

    context = {
        'fecha_sel': fecha_sel,
        'ligas_partidos': ligas_partidos,
        'dias': dias,
        'total_partidos': partidos.count(),
    }
    return render(request, 'agenda.html', context)


# ──────────────────────────────────────────────────────────────
# MUNDIAL 2026
# ──────────────────────────────────────────────────────────────

# Grupos con estructura correcta para el template:
#   {{ info.sede }}   →  clase CSS  sede-mexico / sede-usa / sede-canada
#   {{ info.equipos }} → lista de tuplas (nombre, bandera)
GRUPOS_MUNDIAL = {
    # ── Sede México (Grupos A–D) ──────────────────────────────
    # El segundo valor de cada tupla es el código ISO para flagcdn.com
    'A': {
        'sede': 'mexico',
        'sede_label': 'México',
        'equipos': [
            ('México',        'mx'),
            ('Sudáfrica',     'za'),
            ('Corea del Sur', 'kr'),
            ('Rep. UEFA D',   'un'),   # placeholder: bandera ONU
        ],
    },
    'B': {
        'sede': 'mexico',
        'sede_label': 'México',
        'equipos': [
            ('Canadá',        'ca'),
            ('Suiza',         'ch'),
            ('Catar',         'qa'),
            ('Rep. UEFA A',   'un'),
        ],
    },
    'C': {
        'sede': 'mexico',
        'sede_label': 'México',
        'equipos': [
            ('Brasil',        'br'),
            ('Marruecos',     'ma'),
            ('Escocia',       'gb-sct'),
            ('Haití',         'ht'),
        ],
    },
    'D': {
        'sede': 'mexico',
        'sede_label': 'México',
        'equipos': [
            ('Estados Unidos', 'us'),
            ('Paraguay',       'py'),
            ('Australia',      'au'),
            ('Rep. UEFA C',    'un'),
        ],
    },
    # ── Sede USA (Grupos E–H) ─────────────────────────────────
    'E': {
        'sede': 'usa',
        'sede_label': 'USA',
        'equipos': [
            ('Alemania',        'de'),
            ('Costa de Marfil', 'ci'),
            ('Ecuador',         'ec'),
            ('Curazao',         'cw'),
        ],
    },
    'F': {
        'sede': 'usa',
        'sede_label': 'USA',
        'equipos': [
            ('Países Bajos', 'nl'),
            ('Japón',        'jp'),
            ('Túnez',        'tn'),
            ('Rep. UEFA B',  'un'),
        ],
    },
    'G': {
        'sede': 'usa',
        'sede_label': 'USA',
        'equipos': [
            ('Bélgica',       'be'),
            ('Egipto',        'eg'),
            ('Irán',          'ir'),
            ('Nueva Zelanda', 'nz'),
        ],
    },
    'H': {
        'sede': 'usa',
        'sede_label': 'USA',
        'equipos': [
            ('España',         'es'),
            ('Uruguay',        'uy'),
            ('Arabia Saudita', 'sa'),
            ('Cabo Verde',     'cv'),
        ],
    },
    # ── Sede Canadá (Grupos I–L) ──────────────────────────────
    'I': {
        'sede': 'canada',
        'sede_label': 'Canadá',
        'equipos': [
            ('Francia',        'fr'),
            ('Noruega',        'no'),
            ('Senegal',        'sn'),
            ('Rep. Interconf.','un'),
        ],
    },
    'J': {
        'sede': 'canada',
        'sede_label': 'Canadá',
        'equipos': [
            ('Argentina', 'ar'),
            ('Argelia',   'dz'),
            ('Austria',   'at'),
            ('Jordania',  'jo'),
        ],
    },
    'K': {
        'sede': 'canada',
        'sede_label': 'Canadá',
        'equipos': [
            ('Portugal',       'pt'),
            ('Colombia',       'co'),
            ('Uzbekistán',     'uz'),
            ('Rep. Interconf.','un'),
        ],
    },
    'L': {
        'sede': 'canada',
        'sede_label': 'Canadá',
        'equipos': [
            ('Inglaterra', 'gb-eng'),
            ('Croacia',    'hr'),
            ('Ghana',      'gh'),
            ('Panamá',     'pa'),
        ],
    },
}


def mundial(request):
    # Filtrar partidos relacionados con el mundial
    ligas_mundial = [
        'world cup', 'mundial', 'eliminatorias',
        'qualif', 'fifa', 'amistoso', 'friendly',
    ]
    query = Q()
    for liga in ligas_mundial:
        query |= Q(liga_nombre__icontains=liga)

    partidos = Partido.objects.filter(query).order_by('fecha', 'hora')

    # Agrupar por fecha
    fechas_partidos = {}
    for partido in partidos:
        fechas_partidos.setdefault(partido.fecha, []).append(partido)

    # Canales desde MapeoLigaCanal (configurados en el admin)
    # Canales que transmiten el mundial (agrupados por canal)
    from canales.models import MapeoLigaCanal
    canales_mundial = {}
    try:
        mapeos = MapeoLigaCanal.objects.filter(
            activo=True,
            liga_nombre__icontains='mundial'
        ) | MapeoLigaCanal.objects.filter(
            activo=True,
            liga_nombre__icontains='world cup'
        ) | MapeoLigaCanal.objects.filter(
            activo=True,
            liga_nombre__icontains='fifa'
        )
        for mapeo in mapeos:
            for video in mapeo.canales.filter(activo=True).select_related('canal'):
                canal = video.canal
                if canal.nombre not in canales_mundial:
                    canales_mundial[canal.nombre] = {
                        'canal': canal,
                        'videos': []
                    }
                canales_mundial[canal.nombre]['videos'].append(video)
    except Exception:
        pass

    context = {
        'grupos': GRUPOS_MUNDIAL,
        'fechas_partidos': fechas_partidos,
        'total_partidos': partidos.count(),
        'canales_mundial': canales_mundial,
    }
    return render(request, 'mundial.html', context)