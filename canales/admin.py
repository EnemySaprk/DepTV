from django.contrib import admin
from .models import Liga, Canal, Video, EnlaceVideo, CanalBolaloca, EventoBolaloca, ConfigStreaming, BannerImagen, MapeoLigaCanal, Partido


class EnlaceVideoInline(admin.TabularInline):
    model = EnlaceVideo
    extra = 1


@admin.register(Liga)
class LigaAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'pais', 'activa']
    prepopulated_fields = {'slug': ('nombre',)}
    list_filter = ['activa', 'pais']


@admin.register(Canal)
class CanalAdmin(admin.ModelAdmin):
    list_display = ['nombre', 'url_sitio', 'activo', 'fecha_creacion']
    prepopulated_fields = {'slug': ('nombre',)}
    list_filter = ['activo']
    search_fields = ['nombre']


@admin.register(Video)
class VideoAdmin(admin.ModelAdmin):
    list_display = ['titulo', 'canal', 'bolaloca_canal', 'stream_id', 'tvtvhd_id', 'destacado', 'fecha_publicacion']
    list_filter = ['canal', 'ligas', 'destacado', 'activo']
    search_fields = ['titulo', 'descripcion']
    list_editable = ['destacado']
    filter_horizontal = ['ligas']
    inlines = [EnlaceVideoInline]
    actions = ['generar_enlaces_streaming', 'limpiar_enlaces_streaming', 'actualizar_dominios_streaming']

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
    list_display = ['liga_nombre', 'liga_api_id', 'activo']
    list_editable = ['activo']
    filter_horizontal = ['canales']


@admin.register(Partido)
class PartidoAdmin(admin.ModelAdmin):
    list_display = ['equipo_local', 'equipo_visitante', 'liga_nombre', 'fecha', 'hora', 'estado']
    list_filter = ['liga_nombre', 'fecha', 'estado']
    search_fields = ['equipo_local', 'equipo_visitante', 'liga_nombre']
