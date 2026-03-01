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
    logo = models.FileField(upload_to='ligas/', blank=True, null=True)
    pais = models.CharField(max_length=50, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ['nombre']
        verbose_name_plural = 'Ligas'

    def __str__(self):
        return self.nombre


class CanalBolaloca(models.Model):
    numero = models.PositiveIntegerField(unique=True, help_text='Numero del canal (CH1, CH2...)')
    nombre = models.CharField(max_length=100)
    pais = models.CharField(max_length=10, blank=True, help_text='es, fr, de, uk, it, etc.')
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
    logo = models.FileField(upload_to='canales/', blank=True, null=True)
    url_sitio = models.URLField(blank=True, help_text='Link al sitio oficial del canal')
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
    url_video = models.URLField(help_text='Link del video (YouTube, MP4, o URL del streaming)')
    youtube_id = models.CharField(max_length=20, blank=True, help_text='Se extrae automaticamente si es YouTube')
    canal = models.ForeignKey(Canal, on_delete=models.CASCADE, related_name='videos')
    ligas = models.ManyToManyField(Liga, blank=True, related_name='videos')
    descripcion = models.TextField(blank=True)
    thumbnail_custom = models.FileField(upload_to='thumbnails/', blank=True, null=True, help_text='Thumbnail personalizado')
    fecha_publicacion = models.DateTimeField(auto_now_add=True)
    destacado = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)
    bolaloca_canal = models.ForeignKey(CanalBolaloca, on_delete=models.SET_NULL, null=True, blank=True, help_text='Canal de bolaloca asociado')
    stream_id = models.CharField(max_length=50, blank=True, help_text='ID en streamx (ej: espn, espn2, winplus)')
    tvtvhd_id = models.CharField(max_length=50, blank=True, help_text='ID en tvtvhd (ej: espn, winsportsplus)')

    class Meta:
        ordering = ['-fecha_publicacion']
        verbose_name_plural = 'Videos'

    def __str__(self):
        return self.titulo

    def save(self, *args, **kwargs):
        if self.tipo == 'youtube' and self.url_video and not self.youtube_id:
            self.youtube_id = self.extraer_youtube_id(self.url_video)
        super().save(*args, **kwargs)

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

    def generar_enlaces_streaming(self):
        creados = 0
        orden = self.enlaces.count()

        # 1. TvtvHD (principal)
        if self.tvtvhd_id:
            try:
                config_tv = ConfigStreaming.objects.get(nombre='tvtvhd', activo=True)
                dominio_tv = config_tv.dominio
                ruta_tv = config_tv.ruta
            except ConfigStreaming.DoesNotExist:
                dominio_tv = 'tvtvhd.com'
                ruta_tv = 'vivo/canales.php?stream='

            url = f'https://{dominio_tv}/{ruta_tv}{self.tvtvhd_id}'
            _, created = EnlaceVideo.objects.get_or_create(
                video=self, url=url,
                defaults={'nombre': f'Opcion 1', 'tipo': 'iframe', 'activo': True, 'orden': orden}
            )
            if created:
                creados += 1
                orden += 1

        # 2. Bolaloca (solo servidor WIGI)
        if self.bolaloca_canal:
            bl = self.bolaloca_canal
            try:
                config_bl = ConfigStreaming.objects.get(nombre='bolaloca', activo=True)
                dominio_bl = config_bl.dominio
            except ConfigStreaming.DoesNotExist:
                dominio_bl = 'bolaloca.my'

            url = f'https://{dominio_bl}/player/1/{bl.numero}'
            _, created = EnlaceVideo.objects.get_or_create(
                video=self, url=url,
                defaults={'nombre': f'Opcion 2', 'tipo': 'iframe', 'activo': True, 'orden': orden}
            )
            if created:
                creados += 1

        return creados
class EnlaceVideo(models.Model):
    TIPO_CHOICES = [
        ('youtube', 'YouTube'),
        ('url_directa', 'URL Directa (MP4/M3U8)'),
        ('iframe', 'iFrame Personalizado'),
    ]

    video = models.ForeignKey(Video, on_delete=models.CASCADE, related_name='enlaces')
    nombre = models.CharField(max_length=100, help_text='Ej: Opcion 1, ESPN HD, Fox Sports')
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
        if self.tipo == 'youtube':
            yt_id = self.youtube_id
            if yt_id:
                return f'https://www.youtube.com/embed/{yt_id}'
        return self.url


class EventoBolaloca(models.Model):
    fecha = models.DateField()
    hora = models.TimeField()
    liga = models.CharField(max_length=100)
    partido = models.CharField(max_length=200)
    canales = models.ManyToManyField(CanalBolaloca, blank=True)
    activo = models.BooleanField(default=True)
    fecha_creacion = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['fecha', 'hora']
        verbose_name = 'Bolaloca - Evento'
        verbose_name_plural = 'Bolaloca - Eventos'

    def __str__(self):
        return f'{self.partido} ({self.hora})'
