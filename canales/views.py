from datetime import date, timedelta

from django.db.models import Q
from django.shortcuts import render, get_object_or_404

from .models import Liga, Canal, Video, BannerImagen, Partido, MapeoLigaCanal


# ──────────────────────────────────────────────────────────────
# HOME
# ──────────────────────────────────────────────────────────────
ESTADOS_VIVO = {'1H', '2H', 'HT', 'ET', 'P', 'LIVE'}


def _build_video_partido_map(partidos):
    """
    Devuelve {video_id: partido} con el partido más relevante por canal.
    Prioridad: en vivo > próximo. Usa 3-4 queries en total.
    """
    if not partidos:
        return {}

    # Lookup: bolaloca número → video_id
    num_a_vid = {}
    titulo_a_vid = {}
    for v in Video.objects.filter(activo=True).select_related('bolaloca_canal'):
        titulo_a_vid[v.titulo] = v.id
        if v.bolaloca_canal_id:
            num_a_vid[v.bolaloca_canal.numero] = v.id

    # Lookup: liga_api_id → set de video_ids (vía MapeoLigaCanal)
    liga_a_vids = {}
    for mapa in MapeoLigaCanal.objects.filter(activo=True).prefetch_related('canales'):
        ids = set(mapa.canales.values_list('id', flat=True))
        liga_a_vids[mapa.liga_api_id] = ids

    video_partido = {}

    def _asignar(vid_id, partido):
        existing = video_partido.get(vid_id)
        if existing is None:
            video_partido[vid_id] = partido
        elif partido.estado in ESTADOS_VIVO and existing.estado not in ESTADOS_VIVO:
            video_partido[vid_id] = partido

    for partido in partidos:
        matched = set()
        if partido.canales_bolaloca:
            valores = [v.strip() for v in partido.canales_bolaloca.split(',') if v.strip()]
            if valores and valores[0].isdigit():
                for n in valores:
                    if n.isdigit() and int(n) in num_a_vid:
                        matched.add(num_a_vid[int(n)])
            else:
                for titulo in valores:
                    if titulo in titulo_a_vid:
                        matched.add(titulo_a_vid[titulo])
        if partido.liga_api_id in liga_a_vids:
            matched.update(liga_a_vids[partido.liga_api_id])
        for vid_id in matched:
            _asignar(vid_id, partido)

    return video_partido


def home(request):
    banners = BannerImagen.objects.filter(activo=True, canal__isnull=True, liga__isnull=True)
    if not banners.exists():
        banners = BannerImagen.objects.filter(activo=True)[:5]

    hoy = date.today()
    partidos_hoy = list(Partido.objects.filter(fecha=hoy).order_by('hora')[:20])
    partidos_vivo = [p for p in partidos_hoy if p.estado in ESTADOS_VIVO]

    # Mapa video_id → partido más relevante del día
    video_partido = _build_video_partido_map(partidos_hoy)

    def _anotar(videos):
        videos = list(videos)
        for v in videos:
            v.partido_ahora = video_partido.get(v.id)
        return videos

    canales_con_videos = []
    for canal in Canal.objects.filter(activo=True):
        videos = _anotar(
            Video.objects.filter(canal=canal, activo=True).select_related('canal', 'bolaloca_canal').prefetch_related('ligas')
        )
        if videos:
            canales_con_videos.append({'canal': canal, 'videos': videos})

    ligas_con_videos = []
    for liga in Liga.objects.filter(activa=True):
        videos = _anotar(
            Video.objects.filter(ligas=liga, activo=True).select_related('canal', 'bolaloca_canal').prefetch_related('ligas').distinct()
        )
        if videos:
            ligas_con_videos.append({'liga': liga, 'videos': videos})

    context = {
        'banners': banners,
        'canales_con_videos': canales_con_videos,
        'ligas_con_videos': ligas_con_videos,
        'partidos_hoy': partidos_hoy,
        'partidos_vivo': partidos_vivo,
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
    from .models import MapeoLigaCanal

    canal = get_object_or_404(Canal, slug=slug, activo=True)
    banners = BannerImagen.objects.filter(canal=canal, activo=True)
    videos = (
        Video.objects
        .filter(canal=canal, activo=True)
        .select_related('canal')
        .prefetch_related('ligas')
    )

    # ── Partidos de hoy transmitidos por este canal ──────────────
    partidos_hoy_canal = []
    canal_video_ids = set(videos.values_list('id', flat=True))

    if canal_video_ids:
        # Liga IDs que mapean a videos de este canal
        liga_api_ids = set(
            MapeoLigaCanal.objects.filter(canales__in=canal_video_ids, activo=True)
            .values_list('liga_api_id', flat=True)
        )
        # Títulos de los videos de este canal (para formato bolaloca nuevo)
        video_titles = set(videos.values_list('titulo', flat=True))
        # Números bolaloca de los videos de este canal (para formato bolaloca viejo)
        bolaloca_nums = set(
            videos.filter(bolaloca_canal__isnull=False)
            .values_list('bolaloca_canal__numero', flat=True)
        )

        hoy = date.today()
        for partido in Partido.objects.filter(fecha=hoy).order_by('hora'):
            if partido.canales_bolaloca:
                valores = [v.strip() for v in partido.canales_bolaloca.split(',') if v.strip()]
                if valores:
                    if valores[0].isdigit():
                        nums = {int(n) for n in valores if n.isdigit()}
                        if nums & bolaloca_nums:
                            partidos_hoy_canal.append(partido)
                    else:
                        if set(valores) & video_titles:
                            partidos_hoy_canal.append(partido)
            elif partido.liga_api_id in liga_api_ids:
                partidos_hoy_canal.append(partido)

    context = {
        'canal': canal,
        'banners': banners,
        'videos': videos,
        'partidos_hoy_canal': partidos_hoy_canal,
    }
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