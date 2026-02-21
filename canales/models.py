from django.db import models

# Create your models here.
from django.db import models


class Liga(models.Model):
    nombre = models.CharField(max_length=100)  # Liga MX, Premier League...
    slug = models.SlugField(unique=True)
    logo = models.ImageField(upload_to='ligas/', blank=True, null=True)
    pais = models.CharField(max_length=50, blank=True)
    activa = models.BooleanField(default=True)

    class Meta:
        ordering = ['nombre']
        verbose_name_plural = 'Ligas'

    def __str__(self):
        return self.nombre


class Canal(models.Model):
    nombre = models.CharField(max_length=100)  # ESPN, Fox Sports, TUDN...
    slug = models.SlugField(unique=True)
    logo = models.ImageField(upload_to='canales/', blank=True, null=True)
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
    youtube_id = models.CharField(max_length=20, blank=True,
                                  help_text='Se extrae automáticamente si es YouTube')
    canal = models.ForeignKey(Canal, on_delete=models.CASCADE, related_name='videos')
    liga = models.ForeignKey(Liga, on_delete=models.SET_NULL,
                             null=True, blank=True, related_name='videos')
    descripcion = models.TextField(blank=True)
    thumbnail_custom = models.ImageField(upload_to='thumbnails/', blank=True, null=True,
                                         help_text='Thumbnail personalizado (para videos no YouTube)')
    fecha_publicacion = models.DateTimeField(auto_now_add=True)
    destacado = models.BooleanField(default=False)
    activo = models.BooleanField(default=True)

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