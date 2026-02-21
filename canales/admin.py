from django.contrib import admin
from .models import Liga, Canal, Video


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
    list_display = ['titulo', 'canal', 'liga', 'destacado', 'fecha_publicacion']
    list_filter = ['canal', 'liga', 'destacado', 'activo']
    search_fields = ['titulo', 'descripcion']
    list_editable = ['destacado']