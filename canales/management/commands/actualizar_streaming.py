import requests
import re
from django.core.management.base import BaseCommand
from canales.models import ConfigStreaming, Video


class Command(BaseCommand):
    help = 'Detectar cambios de dominio en fuentes de streaming y actualizar enlaces'

    def handle(self, *args, **options):
        self.stdout.write('\n=== Verificando dominios de streaming ===\n')

        cambios = False

        # Verificar streamx desde su pagina
        cambios |= self.verificar_streamx()

        # Verificar streamgo desde rusticotv
        cambios |= self.verificar_rusticotv()

        if cambios:
            self.stdout.write(self.style.WARNING('\nSe detectaron cambios. Actualizando enlaces...'))
            self.actualizar_enlaces()
        else:
            self.stdout.write(self.style.SUCCESS('\nTodo actualizado. No hay cambios.'))

    def verificar_streamx(self):
        self.stdout.write('Verificando streamx...')
        try:
            # Intentar acceder a la pagina actual
            config = ConfigStreaming.objects.filter(nombre='streamx', activo=True).first()
            if not config:
                self.stdout.write('  No hay config de streamx')
                return False

            dominio_actual = config.dominio

            # Probar si el dominio actual responde
            try:
                r = requests.get(f'https://{dominio_actual}/', timeout=10)
                if r.status_code == 200:
                    self.stdout.write(self.style.SUCCESS(f'  {dominio_actual} OK'))

                    # Buscar si hay redireccion a otro dominio
                    if r.url and dominio_actual not in r.url:
                        nuevo = re.search(r'https?://([^/]+)', r.url)
                        if nuevo:
                            nuevo_dominio = nuevo.group(1)
                            self.stdout.write(self.style.WARNING(f'  Redirige a: {nuevo_dominio}'))
                            config.dominio = nuevo_dominio
                            config.save()
                            return True
                    return False
            except:
                pass

            # Si no responde, probar variaciones
            base = re.match(r'(\D+)(\d+)(\..*)', dominio_actual)
            if base:
                prefijo = base.group(1)
                numero = int(base.group(2))
                sufijo = base.group(3)

                for i in range(numero - 2, numero + 5):
                    if i <= 0:
                        continue
                    test_dominio = f'{prefijo}{i}{sufijo}'
                    if test_dominio == dominio_actual:
                        continue
                    try:
                        r = requests.get(f'https://{test_dominio}/', timeout=5)
                        if r.status_code == 200:
                            self.stdout.write(self.style.SUCCESS(f'  Nuevo dominio encontrado: {test_dominio}'))
                            config.dominio = test_dominio
                            config.save()
                            return True
                    except:
                        continue

            self.stdout.write(self.style.ERROR(f'  {dominio_actual} no responde y no se encontro alternativa'))
            return False

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  Error: {e}'))
            return False

    def verificar_rusticotv(self):
        self.stdout.write('Verificando fuentes desde rusticotv...')
        try:
            r = requests.get('https://rusticotv.cc/agenda.html', timeout=10)
            if r.status_code != 200:
                self.stdout.write(self.style.ERROR('  No se pudo acceder a rusticotv'))
                return False

            cambios = False
            html = r.text

            # Buscar dominios de streamgo
            streamgo_match = re.search(r'https?://(streamgo\d+\.[^/]+)/', html)
            if streamgo_match:
                nuevo_dominio = streamgo_match.group(1)
                config = ConfigStreaming.objects.filter(nombre='streamgo', activo=True).first()
                if config:
                    if config.dominio != nuevo_dominio:
                        self.stdout.write(self.style.WARNING(f'  streamgo cambio: {config.dominio} -> {nuevo_dominio}'))
                        config.dominio = nuevo_dominio
                        config.save()
                        cambios = True
                    else:
                        self.stdout.write(self.style.SUCCESS(f'  streamgo OK: {nuevo_dominio}'))
                else:
                    self.stdout.write(f'  streamgo detectado: {nuevo_dominio} (no hay config)')

            # Buscar dominios de streamx
            streamx_match = re.search(r'https?://(streamx\d+\.[^/]+)/', html)
            if streamx_match:
                nuevo_dominio = streamx_match.group(1)
                config = ConfigStreaming.objects.filter(nombre='streamx', activo=True).first()
                if config:
                    if config.dominio != nuevo_dominio:
                        self.stdout.write(self.style.WARNING(f'  streamx cambio: {config.dominio} -> {nuevo_dominio}'))
                        config.dominio = nuevo_dominio
                        config.save()
                        cambios = True
                    else:
                        self.stdout.write(self.style.SUCCESS(f'  streamx OK: {nuevo_dominio}'))

            # Buscar dominio de tvtvhd
            tvtvhd_match = re.search(r'https?://(tvtvhd\.[^/]+)/', html)
            if tvtvhd_match:
                nuevo_dominio = tvtvhd_match.group(1)
                config = ConfigStreaming.objects.filter(nombre='tvtvhd', activo=True).first()
                if config:
                    if config.dominio != nuevo_dominio:
                        self.stdout.write(self.style.WARNING(f'  tvtvhd cambio: {config.dominio} -> {nuevo_dominio}'))
                        config.dominio = nuevo_dominio
                        config.save()
                        cambios = True
                    else:
                        self.stdout.write(self.style.SUCCESS(f'  tvtvhd OK: {nuevo_dominio}'))

            return cambios

        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  Error: {e}'))
            return False

    def actualizar_enlaces(self):
        videos = Video.objects.filter(activo=True)
        total_borrados = 0
        total_creados = 0

        for video in videos:
            if video.bolaloca_canal or video.stream_id:
                total_borrados += video.enlaces.filter(url__contains='bolaloca').delete()[0]
                total_borrados += video.enlaces.filter(url__contains='streamx').delete()[0]
                total_borrados += video.enlaces.filter(url__contains='streamgo').delete()[0]
                total_borrados += video.enlaces.filter(url__contains='tvtvhd').delete()[0]
                total_creados += video.generar_enlaces_streaming()

        self.stdout.write(self.style.SUCCESS(f'\nResultado: {total_borrados} eliminados, {total_creados} creados'))
