from django.contrib import admin
from .models import Liga, RedCanal, Canal, Video, EnlaceVideo, CanalBolaloca, EventoBolaloca, ConfigStreaming, BannerImagen, MapeoLigaCanal, Partido


class EnlaceVideoInline(admin.TabularInline):
    model = EnlaceVideo
    extra = 1


class CanalInline(admin.TabularInline):
    model = Canal
    fields = ['nombre', 'slug', 'activo']
    prepopulated_fields = {'slug': ('nombre',)}
    extra = 1
    show_change_link = True


@admin.register(Liga)
class LigaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'pais', 'activa']
    prepopulated_fields = {'slug': ('nombre',)}
    list_filter = ['activa', 'pais']


@admin.register(RedCanal)
class RedCanalAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'num_canales', 'activa']
    prepopulated_fields = {'slug': ('nombre',)}
    list_filter = ['activa']
    search_fields = ['nombre']
    inlines = [CanalInline]

    @admin.display(description='# Canales')
    def num_canales(self, obj):
        return obj.canales.count()


@admin.register(Canal)
class CanalAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'red', 'ligas_display', 'url_sitio', 'activo', 'fecha_creacion']
    prepopulated_fields = {'slug': ('nombre',)}
    list_filter = ['activo', 'red', 'ligas']
    search_fields = ['nombre']
    filter_horizontal = ['ligas']

    @admin.display(description='Competiciones')
    def ligas_display(self, obj):
        nombres = list(obj.ligas.values_list('nombre', flat=True))
        return ', '.join(nombres) if nombres else '—'


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'red_canal', 'canal', 'bolaloca_canal', 'stream_id', 'tvtvhd_id', 'destacado', 'fecha_publicacion']
    list_filter = ['canal__red', 'canal', 'ligas', 'destacado', 'activo']
    search_fields = ['titulo', 'descripcion']
    list_editable = ['destacado']
    filter_horizontal = ['ligas']
    inlines = [EnlaceVideoInline]
    actions = ['generar_enlaces_streaming', 'limpiar_enlaces_streaming', 'actualizar_dominios_streaming']

    @admin.display(description='Red', ordering='canal__red__nombre')
    def red_canal(self, obj):
        return obj.canal.red or '—'

    @admin.action(description='Generar enlaces de streaming (Bolaloca + Streamx + TvtvHD)')
    def generar_enlaces_streaming(self, request, queryset):
        total = 0
        for video in queryset:
            total += video.generar_enlaces_streaming()
        self.message_user(request, f'Se crearon {total} enlaces nuevos.')

    @admin.action(description='Limpiar enlaces de streaming (borrar auto-generados)')
    def limpiar_enlaces_streaming(self, request, queryset):
        total = 0
        for video in queryset:
            total += video.enlaces.filter(url__contains='bolaloca').delete()[0]
            total += video.enlaces.filter(url__contains='streamx').delete()[0]
            total += video.enlaces.filter(url__contains='tvtvhd').delete()[0]
        self.message_user(request, f'Se eliminaron {total} enlaces.')

    @admin.action(description='Actualizar dominios de streaming (regenerar enlaces)')
    def actualizar_dominios_streaming(self, request, queryset):
        total_borrados = 0
        total_creados = 0
        for video in queryset:
            total_borrados += video.enlaces.filter(url__contains='bolaloca').delete()[0]
            total_borrados += video.enlaces.filter(url__contains='streamx').delete()[0]
            total_borrados += video.enlaces.filter(url__contains='tvtvhd').delete()[0]
            total_creados += video.generar_enlaces_streaming()
        self.message_user(request, f'Se eliminaron {total_borrados} viejos y se crearon {total_creados} nuevos.')


@admin.register(CanalBolaloca)
class CanalBolalocaAdmin(admin.ModelAdmin):
    list_display = ['numero', 'nombre', 'pais', 'activo']
    list_filter = ['pais', 'activo']
    search_fields = ['nombre', 'numero']
    list_editable = ['activo']
    ordering = ['numero']


@admin.register(EventoBolaloca)
class EventoBolalocaAdmin(admin.ModelAdmin):
    list_display = ['partido', 'liga', 'fecha', 'hora', 'activo']
    list_filter = ['liga', 'fecha', 'activo']
    search_fields = ['partido', 'liga']
    filter_horizontal = ['canales']
    list_editable = ['activo']


@admin.register(ConfigStreaming)
class ConfigStreamingAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'dominio', 'ruta', 'activo']
    list_editable = ['dominio', 'ruta', 'activo']

@admin.register(BannerImagen)
class BannerImagenAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'canal', 'liga', 'orden', 'activo']
    list_filter = ['canal', 'liga', 'activo']
    list_editable = ['orden', 'activo']

@admin.register(MapeoLigaCanal)
class MapeoLigaCanalAdmin(admin.ModelAdmin):
    list_display = ['liga_nombre', 'liga_api_id', 'num_canales', 'activo']
    list_editable = ['activo']
    filter_horizontal = ['canales']
    search_fields = ['liga_nombre']

    @admin.display(description='# Canales')
    def num_canales(self, obj):
        return obj.canales.count()


@admin.register(Partido)
class PartidoAdmin(admin.ModelAdmin):
    list_display = [
        'fecha', 'hora', 'estado',
        'equipo_local', 'equipo_visitante',
        'liga_nombre', 'canales_display',
    ]
    list_filter = ['fecha', 'estado', 'liga_nombre', 'canales']
    search_fields = ['equipo_local', 'equipo_visitante', 'liga_nombre']
    filter_horizontal = ['canales']
    ordering = ['-fecha', 'hora']
    list_per_page = 50
    fieldsets = [
        ('Partido', {
            'fields': [
                ('equipo_local', 'equipo_visitante'),
                ('fecha', 'hora', 'estado'),
                'liga_nombre',
            ]
        }),
        ('Canales que transmiten', {
            'fields': ['canales'],
            'description': 'Selecciona los canales que transmitirán este partido.',
        }),
        ('Datos técnicos (legacy)', {
            'fields': ['liga_api_id', 'canales_bolaloca', 'minuto'],
            'classes': ['collapse'],
        }),
    ]

    @admin.display(description='Canales')
    def canales_display(self, obj):
        nombres = list(obj.canales.values_list('nombre', flat=True))
        return ', '.join(nombres) if nombres else '—'

    def get_queryset(self, request):
        qs = super().get_queryset(request)
        from datetime import date
        hoy = date.today()
        from django.db.models import Case, When, IntegerField
        return qs.annotate(
            es_hoy=Case(When(fecha=hoy, then=0), default=1, output_field=IntegerField())
        ).order_by('es_hoy', '-fecha', 'hora')
