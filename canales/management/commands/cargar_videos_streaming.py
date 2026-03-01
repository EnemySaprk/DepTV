from django.core.management.base import BaseCommand
from canales.models import Canal, Video, CanalBolaloca, Liga


class Command(BaseCommand):
    help = 'Cargar videos de streaming para ESPN, DSports, Win Sports, DAZN, Movistar'

    def handle(self, *args, **options):
        # Crear canales si no existen
        canales_data = ['ESPN', 'DSports', 'Win Sports', 'DAZN', 'Movistar']
        canales = {}
        for nombre in canales_data:
            slug = nombre.lower().replace(' ', '-')
            canal, created = Canal.objects.get_or_create(
                slug=slug,
                defaults={'nombre': nombre, 'activo': True}
            )
            canales[nombre] = canal
            if created:
                self.stdout.write(self.style.SUCCESS(f'Canal creado: {nombre}'))

        # Videos a crear: (titulo, canal, bolaloca_numero, tvtvhd_id)
        videos_data = [
            # ESPN
            ('ESPN 1', 'ESPN', 87, 'espn'),
            ('ESPN 2', 'ESPN', 88, 'espn2'),
            ('ESPN 3', 'ESPN', 71, 'espn3'),
            ('ESPN 4', 'ESPN', 97, 'espn4'),
            ('ESPN 5', 'ESPN', None, 'espn5'),
            ('ESPN 6', 'ESPN', None, 'espn6'),
            ('ESPN 7', 'ESPN', None, 'espn7'),
            ('ESPN Premium', 'ESPN', 89, 'espnpremium'),
            ('ESPN Deportes', 'ESPN', 90, 'espndeportes'),
            # DSports
            ('DSports', 'DSports', 94, 'dsports'),
            ('DSports 2', 'DSports', 95, 'dsports2'),
            ('DSports Plus', 'DSports', None, 'dsportsplus'),
            # Win Sports
            ('Win Sports+', 'Win Sports', 81, 'winsportsplus'),
            ('Win Sports+ (2)', 'Win Sports', 82, 'winsports2'),
            ('Win Sports', 'Win Sports', None, 'winsports'),
            # DAZN
            ('DAZN 1', 'DAZN', 56, 'dazn1'),
            ('DAZN 2', 'DAZN', 57, 'dazn2'),
            ('DAZN 3', 'DAZN', None, 'dazn3'),
            ('DAZN 4', 'DAZN', None, 'dazn4'),
            ('DAZN LaLiga', 'DAZN', 58, 'dazn_laliga'),
            # Movistar
            ('M+ LaLiga TV', 'Movistar', 44, 'm_laligatv'),
            ('LaLigaTV BAR', 'Movistar', None, 'laligatvbar'),
            ('Liga de Campeones 1', 'Movistar', 46, 'ligadecampeones1'),
            ('Liga de Campeones 2', 'Movistar', 47, 'ligadecampeones2'),
            ('Liga de Campeones 3', 'Movistar', None, 'ligadecampeones3'),
        ]

        total_creados = 0
        total_enlaces = 0

        for titulo, canal_nombre, bl_numero, tvtvhd_id in videos_data:
            canal = canales[canal_nombre]

            # Buscar bolaloca canal
            bl_canal = None
            if bl_numero:
                try:
                    bl_canal = CanalBolaloca.objects.get(numero=bl_numero)
                except CanalBolaloca.DoesNotExist:
                    pass

            url_placeholder = f'https://tvtvhd.com/vivo/canales.php?stream={tvtvhd_id}'

            video, created = Video.objects.get_or_create(
                titulo=titulo,
                canal=canal,
                defaults={
                    'tipo': 'iframe',
                    'url_video': url_placeholder,
                    'bolaloca_canal': bl_canal,
                    'stream_id': tvtvhd_id,
                    'tvtvhd_id': tvtvhd_id,
                    'activo': True,
                    'destacado': False,
                }
            )

            if created:
                total_creados += 1
                enlaces = video.generar_enlaces_streaming()
                total_enlaces += enlaces
                self.stdout.write(self.style.SUCCESS(f'  + {titulo} ({canal_nombre}) - {enlaces} enlaces'))
            else:
                self.stdout.write(f'  = {titulo} ya existe')

        self.stdout.write(self.style.SUCCESS(f'\nResultado: {total_creados} videos creados, {total_enlaces} enlaces generados'))
