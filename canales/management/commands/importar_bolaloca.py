import re
from django.core.management.base import BaseCommand
from canales.models import Liga, Canal, Video, EnlaceVideo

# Mapeo de canales de bolaloca.my
CANALES_BOLALOCA = {
    1: 'beIN SPORT 1', 2: 'beIN SPORT 2', 3: 'beIN SPORT 3',
    49: 'M. LaLiga', 50: 'M. LaLiga 2',
    68: 'TUDN USA', 69: 'beIN En Espanol',
    70: 'FOX Deportes', 71: 'ESPN Deportes', 72: 'NBC Universo',
    75: 'TNT Sport ARG', 76: 'ESPN Premium', 77: 'TyC Sports',
    78: 'FOX Sport 1 ARG', 81: 'Win Sport+', 82: 'Win Sport',
    84: 'Liga 1 MAX', 85: 'GolPeru',
    87: 'ESPN 1', 88: 'ESPN 2', 89: 'ESPN 3', 90: 'ESPN 4',
    91: 'ESPN 5', 92: 'ESPN 6', 93: 'ESPN 7',
    94: 'DirecTV', 95: 'DirecTV 2', 96: 'DirecTV+',
    97: 'ESPN 1 MX', 98: 'ESPN 2 MX', 99: 'ESPN 3 MX', 100: 'ESPN 4 MX',
    101: 'FOX Sport 1 MX', 102: 'FOX Sport 2 MX', 103: 'FOX Sport 3 MX',
    104: 'FOX Sports Premium', 106: 'TUDN MX', 107: 'Canal 5 MX', 108: 'Azteca 7',
    110: 'Sky Bundesliga 10', 111: 'Sky Bundesliga 1',
    126: 'TNT Sport UK', 127: 'Sky Main UK', 128: 'Sky Football UK',
    137: 'Zona DAZN IT', 138: 'Sky Calcio IT',
    141: 'ESPN 1 NL', 142: 'ESPN 2 NL', 143: 'ESPN 3 NL',
}

# Mapeo de ligas por palabras clave
LIGAS_MAP = {
    'Premier League': 'Premier League',
    'LaLiga': 'LaLiga',
    'Laliga': 'LaLiga',
    'Laliga 2': 'LaLiga 2',
    'Serie A': 'Serie A',
    'Bundesliga': 'Bundesliga',
    'Ligue 1': 'Ligue 1',
    'Liga MX': 'Liga MX',
    'Liga BetPlay': 'Liga BetPlay',
    'Liga Profesional': 'Liga Argentina',
    'Championship': 'Championship',
    'MLS': 'MLS',
    'Eredivisie': 'Eredivisie',
    'Liga 1': 'Liga 1 Peru',
    'Copa': 'Copa',
    'Champions': 'Champions League',
    'Europa League': 'Europa League',
}

BASE_URL = 'https://bolaloca.my/player'
SERVIDORES = {1: 'WIGI', 2: 'HOCA', 3: 'CAST'}


class Command(BaseCommand):
    help = 'Importar agenda desde bolaloca.my'

    def add_arguments(self, parser):
        parser.add_argument('--agenda', type=str, help='Texto de la agenda')
        parser.add_argument('--archivo', type=str, help='Archivo con la agenda')

    def handle(self, *args, **options):
        if options['archivo']:
            with open(options['archivo'], 'r', encoding='utf-8') as f:
                agenda_text = f.read()
        elif options['agenda']:
            agenda_text = options['agenda']
        else:
            self.stdout.write('Pega la agenda (termina con linea vacia):')
            lines = []
            while True:
                try:
                    line = input()
                    if line == '':
                        break
                    lines.append(line)
                except EOFError:
                    break
            agenda_text = '\n'.join(lines)

        eventos = self.parsear_agenda(agenda_text)
        self.stdout.write(f'\nEncontrados {len(eventos)} eventos\n')

        for evento in eventos:
            self.crear_video(evento)

        self.stdout.write(self.style.SUCCESS('\nImportacion completada!'))

    def parsear_agenda(self, text):
        eventos = []
        pattern = r'(\d{2}-\d{2}-\d{4})\s*\((\d{2}:\d{2})\)\s*(.+?):\s*(.+?)\s+((?:\(CH\d+\w*\)\s*)+)'
        
        for match in re.finditer(pattern, text):
            fecha = match.group(1)
            hora = match.group(2)
            liga_raw = match.group(3).strip()
            partido = match.group(4).strip()
            canales_raw = match.group(5)
            
            canales_nums = re.findall(r'CH(\d+)(\w*)', canales_raw)
            
            eventos.append({
                'fecha': fecha,
                'hora': hora,
                'liga': liga_raw,
                'partido': partido,
                'canales': [(int(num), sufijo) for num, sufijo in canales_nums],
            })

        return eventos

    def crear_video(self, evento):
        titulo = f"{evento['partido']} ({evento['hora']})"
        liga_nombre = evento['liga']
        
        # Buscar o crear liga
        liga_obj = None
        for key, nombre in LIGAS_MAP.items():
            if key.lower() in liga_nombre.lower():
                liga_obj, _ = Liga.objects.get_or_create(
                    nombre=nombre,
                    defaults={'slug': nombre.lower().replace(' ', '-'), 'activa': True}
                )
                break

        if not liga_obj:
            liga_obj, _ = Liga.objects.get_or_create(
                nombre=liga_nombre,
                defaults={'slug': liga_nombre.lower().replace(' ', '-'), 'activa': True}
            )

        # Buscar canal principal
        primer_canal_num = evento['canales'][0][0] if evento['canales'] else None
        canal_nombre = CANALES_BOLALOCA.get(primer_canal_num, f'Canal {primer_canal_num}')
        
        canal_obj, _ = Canal.objects.get_or_create(
            nombre=canal_nombre,
            defaults={'slug': canal_nombre.lower().replace(' ', '-'), 'activo': True}
        )

        # Crear video
        primer_url = f"{BASE_URL}/1/{primer_canal_num}" if primer_canal_num else ''
        
        video, created = Video.objects.get_or_create(
            titulo=titulo,
            defaults={
                'tipo': 'iframe',
                'url_video': primer_url,
                'canal': canal_obj,
                'activo': True,
                'destacado': False,
            }
        )

        if created:
            video.ligas.add(liga_obj)
            self.stdout.write(f'  + {titulo}')

            # Crear enlaces para cada canal y servidor
            orden = 0
            for canal_num, sufijo in evento['canales']:
                nombre_canal = CANALES_BOLALOCA.get(canal_num, f'CH{canal_num}')
                for server_id, server_name in SERVIDORES.items():
                    url = f"{BASE_URL}/{server_id}/{canal_num}"
                    EnlaceVideo.objects.create(
                        video=video,
                        nombre=f"{nombre_canal} ({server_name})",
                        tipo='iframe',
                        url=url,
                        activo=True,
                        orden=orden,
                    )
                    orden += 1
        else:
            self.stdout.write(f'  = {titulo} (ya existe)')
