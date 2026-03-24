from django.db import models


class ConfigStreaming(models.Model):
    nombre = models.CharField(max_length=50, unique=True)
    dominio = models.CharField(max_length=200, help_text='Ej: streamx10.cloud, bolaloca.my')
    ruta = models.CharField(max_length=200, blank=True, help_text='Ej: global1.php?channel=, player/1/')
    activo = models.BooleanField(default=True)

    class Meta:
        verbose_name = 'Configuracion Streaming'
        verbose_name_plural = 'Configuracion Streaming'

    def __str__(self):
        return f'{self.nombre} ({self.dominio})'


class Liga(models.Model):
    nombre = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    logo = models.ImageField(upload_to='ligas/', blank=True, null=True)
    pais = models.CharField(max_length=50, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ['nombre']
        verbose_name_plural = 'Ligas'

    def __str__(self):
        return self.nombre


class CanalBolaloca(models.Model):
    numero = models.PositiveIntegerField(unique=True)
    nombre = models.CharField(max_length=100)
    pais = models.CharField(max_length=10, blank=True)
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['numero']
        verbose_name = 'Bolaloca - Canal'
        verbose_name_plural = 'Bolaloca - Canales'

    def __str__(self):
        return f'CH{self.numero} - {self.nombre}'

    @property
    def url_wigi(self):
        return f'https://bolaloca.my/player/1/{self.numero}'

    @property
    def url_hoca(self):
        return f'https://bolaloca.my/player/2/{self.numero}'

    @property
    def url_cast(self):
        return f'https://bolaloca.my/player/3/{self.numero}'


class Canal(models.Model):
    nombre = models.CharField(max_length=100)
    slug = models.SlugField(unique=True)
    logo = models.ImageField(upload_to='canales/', blank=True, null=True)
    url_sitio = models.URLField(blank=True)
    descripcion = models.TextField(blank=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['nombre']
        verbose_name_plural = 'Canales'

    def __str__(self):
        return self.nombre


class Video(models.Model):
    TIPO_CHOICES = [
        ('youtube', 'YouTube'),
        ('url_directa', 'URL Directa (MP4/M3U8)'),
        ('iframe', 'iFrame Personalizado'),
    ]

    titulo = models.CharField(max_length=200)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='youtube')
    url_video = models.URLField()
    youtube_id = models.CharField(max_length=20, blank=True)
    canal = models.ForeignKey(Canal, on_delete=models.CASCADE, related_name='videos')
    ligas = models.ManyToManyField(Liga, blank=True, related_name='videos')
    descripcion = models.TextField(blank=True)
    thumbnail_custom = models.ImageField(upload_to='thumbnails/', blank=True, null=True)
    fecha_publicacion = models.DateTimeField(auto_now_add=True)
    destacado = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)
    bolaloca_canal = models.ForeignKey(CanalBolaloca, on_delete=models.SET_NULL, null=True, blank=True)
    stream_id = models.CharField(max_length=50, blank=True)
    tvtvhd_id = models.CharField(max_length=50, blank=True)

    class Meta:
        ordering = ['-fecha_publicacion']
        verbose_name_plural = 'Videos'

    def __str__(self):
        return self.titulo

    @staticmethod
    def extraer_youtube_id(url):
        import re
        patrones = [
            r'(?:youtube\.com/watch\?v=)([\w-]+)',
            r'(?:youtu\.be/)([\w-]+)',
            r'(?:youtube\.com/embed/)([\w-]+)',
        ]
        for patron in patrones:
            match = re.search(patron, url)
            if match:
                return match.group(1)
        return ''

    @property
    def thumbnail_url(self):
        if self.thumbnail_custom:
            return self.thumbnail_custom.url
        if self.youtube_id:
            return f'https://img.youtube.com/vi/{self.youtube_id}/hqdefault.jpg'
        return ''

    @property
    def embed_url(self):
        if self.tipo == 'youtube' and self.youtube_id:
            return f'https://www.youtube.com/embed/{self.youtube_id}'
        return self.url_video


class EnlaceVideo(models.Model):
    TIPO_CHOICES = [
        ('youtube', 'YouTube'),
        ('url_directa', 'URL Directa (MP4/M3U8)'),
        ('iframe', 'iFrame Personalizado'),
    ]

    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='enlaces')
    nombre = models.CharField(max_length=100)
    tipo = models.CharField(max_length=20, choices=TIPO_CHOICES, default='iframe')
    url = models.URLField()
    activo = models.BooleanField(default=True)
    orden = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ['orden']
        verbose_name = 'Enlace'
        verbose_name_plural = 'Enlaces'

    def __str__(self):
        return f'{self.nombre} - {self.video.titulo}'

    @property
    def youtube_id(self):
        if self.tipo == 'youtube':
            return Video.extraer_youtube_id(self.url)
        return ''

    @property
    def embed_url(self):
        if self.tipo == 'youtube' and self.youtube_id:
            return f'https://www.youtube.com/embed/{self.youtube_id}'
        return self.url


class BannerImagen(models.Model):
    titulo = models.CharField(max_length=200, blank=True)
    descripcion = models.TextField(blank=True, help_text='Descripcion corta del banner')
    imagen = models.FileField(upload_to='banners/')
    canal = models.ForeignKey(Canal, on_delete=models.CASCADE, null=True, blank=True, related_name='banners')
    liga = models.ForeignKey(Liga, on_delete=models.SET_NULL, null=True, blank=True, related_name='banners')
    orden = models.PositiveIntegerField(default=0)
    activo = models.BooleanField(default=True)

    BANNER_WIDTH = 1920
    BANNER_HEIGHT = 1080

    class Meta:
        ordering = ['orden']
        verbose_name = 'Banner'
        verbose_name_plural = 'Banners'

    def __str__(self):
        return self.titulo or f'Banner {self.pk}'

    def save(self, *args, **kwargs):
        super().save(*args, **kwargs)
        if self.imagen:
            self.redimensionar_imagen()

    def redimensionar_imagen(self):
        from PIL import Image

        try:
            img_path = self.imagen.path
            img = Image.open(img_path)

            if img.mode in ('RGBA', 'P'):
                img = img.convert('RGB')

            img_width, img_height = img.size
            target_w = self.BANNER_WIDTH
            target_h = self.BANNER_HEIGHT
            target_ratio = target_w / target_h
            img_ratio = img_width / img_height

            if img_ratio > target_ratio:
                new_height = img_height
                new_width = int(img_height * target_ratio)
                left = (img_width - new_width) // 2
                img = img.crop((left, 0, left + new_width, new_height))
            else:
                new_width = img_width
                new_height = int(img_width / target_ratio)
                top = (img_height - new_height) // 2
                img = img.crop((0, top, new_width, top + new_height))

            img = img.resize((target_w, target_h), Image.LANCZOS)
            img.save(img_path, 'JPEG', quality=90)
        except Exception as e:
            print(f'Error redimensionando banner: {e}')


class MapeoLigaCanal(models.Model):
    """Mapeo automático: cuando un partido es de X liga, se transmite por Y canales."""
    liga_api_id = models.PositiveIntegerField(unique=True, help_text='ID de la liga en API-Football')
    liga_nombre = models.CharField(max_length=100, help_text='Nombre de la liga (ej: La Liga, Premier League)')
    canales = models.ManyToManyField('Video', blank=True, help_text='Videos/canales que transmiten esta liga')
    activo = models.BooleanField(default=True)

    class Meta:
        ordering = ['liga_nombre']
        verbose_name = 'Mapeo Liga-Canal'
        verbose_name_plural = 'Mapeos Liga-Canal'

    def __str__(self):
        return self.liga_nombre


class Partido(models.Model):
    ESTADO_CHOICES = [
        ('NS',   'No iniciado'),
        ('1H',   'Primer tiempo'),
        ('HT',   'Entretiempo'),
        ('2H',   'Segundo tiempo'),
        ('FT',   'Finalizado'),
        ('AET',  'Tiempo extra'),
        ('PEN',  'Penales'),
        ('SUSP', 'Suspendido'),
        ('PST',  'Pospuesto'),
        ('CANC', 'Cancelado'),
        ('LIVE', 'En vivo'),
    ]

    api_id              = models.PositiveIntegerField(unique=True, help_text='ID del fixture en API-Football')
    liga_nombre         = models.CharField(max_length=100)
    liga_logo           = models.URLField(blank=True)
    liga_api_id         = models.PositiveIntegerField(default=0)
    equipo_local        = models.CharField(max_length=100)
    equipo_local_logo   = models.URLField(blank=True)
    equipo_visitante    = models.CharField(max_length=100)
    equipo_visitante_logo = models.URLField(blank=True)
    fecha               = models.DateField()
    hora                = models.TimeField()
    estado              = models.CharField(max_length=10, choices=ESTADO_CHOICES, default='NS')
    goles_local         = models.PositiveIntegerField(null=True, blank=True)
    goles_visitante     = models.PositiveIntegerField(null=True, blank=True)
    fecha_actualizacion = models.DateTimeField(auto_now=True)
    canales_bolaloca    = models.CharField(
        max_length=200, blank=True,
        help_text='Números de canales bolaloca separados por coma (ej: 81,87,94)',
    )

    # tvtvhd_id → bolaloca número
    _MAPEO_TVTVHD = {
        56: 'dazn1',
        57: 'dazn2',
        58: 'dazn_laliga',
        49: 'daznf1',
        51: 'dazn_laliga',
        44: 'm_laligatv',
        46: 'ligadecampeones1',
        47: 'ligadecampeones2',
        81: 'winsportsplus',
        82: 'winsports2',
        50: 'm_laligatv2',
    }

    class Meta:
        ordering = ['fecha', 'hora']
        verbose_name = 'Partido'
        verbose_name_plural = 'Partidos'

    def __str__(self):
        return f'{self.equipo_local} vs {self.equipo_visitante} ({self.liga_nombre})'

    @property
    def canales_transmision(self):
        """
        Retorna SIEMPRE un QuerySet de Video con los canales que transmiten
        este partido. Nunca retorna una lista (evita errores con .all() en templates).

        Prioridad:
          1. Videos vinculados por bolaloca_canal__numero
          2. Videos vinculados por tvtvhd_id
          3. MapeoLigaCanal para la liga del partido
          4. QuerySet vacío
        """
        from canales.models import Video, MapeoLigaCanal

        pks = set()

        if self.canales_bolaloca:
            numeros = [
                int(n.strip())
                for n in self.canales_bolaloca.split(',')
                if n.strip().isdigit()
            ]

            # 1) Por bolaloca_canal
            pks.update(
                Video.objects
                .filter(activo=True, bolaloca_canal__numero__in=numeros)
                .values_list('pk', flat=True)
            )

            # 2) Por tvtvhd_id
            tvtvhd_ids = [self._MAPEO_TVTVHD[n] for n in numeros if n in self._MAPEO_TVTVHD]
            if tvtvhd_ids:
                pks.update(
                    Video.objects
                    .filter(activo=True, tvtvhd_id__in=tvtvhd_ids)
                    .values_list('pk', flat=True)
                )

        if pks:
            return (
                Video.objects
                .filter(pk__in=pks, activo=True)
                .select_related('canal')
                .order_by('canal__nombre', 'titulo')
            )

        # 3) Fallback: MapeoLigaCanal
        try:
            mapeo = MapeoLigaCanal.objects.get(liga_api_id=self.liga_api_id, activo=True)
            return mapeo.canales.filter(activo=True).select_related('canal')
        except MapeoLigaCanal.DoesNotExist:
            return Video.objects.none()  # ← siempre QuerySet, nunca lista


class EventoBolaloca(models.Model):
    fecha   = models.DateField()
    hora    = models.TimeField()
    liga    = models.CharField(max_length=100)
    partido = models.CharField(max_length=200)
    canales = models.ManyToManyField(CanalBolaloca, blank=True)
    activo  = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha', 'hora']
        verbose_name = 'Bolaloca - Evento'
        verbose_name_plural = 'Bolaloca - Eventos'

    def __str__(self):
        return f'{self.partido} ({self.hora})'