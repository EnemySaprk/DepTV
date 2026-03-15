import requests
from datetime import datetime, timedelta
from django.core.management.base import BaseCommand
from canales.models import Partido, MapeoLigaCanal


API_TOKEN = 'f432574001814e25b223b4e91e796fa3'
API_URL = 'https://api.football-data.org/v4'

# Ligas gratis en football-data.org
LIGAS = {
    'PL': {'nombre': 'Premier League', 'id': 2021},
    'PD': {'nombre': 'La Liga', 'id': 2014},
    'SA': {'nombre': 'Serie A', 'id': 2019},
    'BL1': {'nombre': 'Bundesliga', 'id': 2002},
    'FL1': {'nombre': 'Ligue 1', 'id': 2015},
    'CL': {'nombre': 'Champions League', 'id': 2001},
}


class Command(BaseCommand):
    help = 'Sincronizar partidos desde football-data.org'

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=7, help='Dias a sincronizar (hoy + N dias)')
        parser.add_argument('--crear-mapeos', action='store_true', help='Crear mapeos liga-canal si no existen')

    def handle(self, *args, **options):
        if options['crear_mapeos']:
            self.crear_mapeos_iniciales()
            return

        dias = options['dias']
        headers = {'X-Auth-Token': API_TOKEN}
        total_creados = 0
        total_actualizados = 0

        fecha_desde = datetime.now().strftime('%Y-%m-%d')
        fecha_hasta = (datetime.now() + timedelta(days=dias)).strftime('%Y-%m-%d')

        for codigo, liga_info in LIGAS.items():
            liga_nombre = liga_info['nombre']
            liga_id = liga_info['id']
            self.stdout.write(f'\n{liga_nombre}...')

            url = f'{API_URL}/competitions/{codigo}/matches?dateFrom={fecha_desde}&dateTo={fecha_hasta}'

            try:
                response = requests.get(url, headers=headers, timeout=15)

                if response.status_code == 429:
                    self.stdout.write(self.style.WARNING('  Rate limit alcanzado, esperando...'))
                    import time
                    time.sleep(60)
                    response = requests.get(url, headers=headers, timeout=15)

                if response.status_code != 200:
                    self.stdout.write(self.style.ERROR(f'  Error HTTP {response.status_code}: {response.text[:200]}'))
                    continue

                data = response.json()
                matches = data.get('matches', [])
                self.stdout.write(f'  {len(matches)} partidos encontrados')

                for match in matches:
                    fecha_utc = match.get('utcDate', '')
                    if not fecha_utc:
                        continue

                    dt = datetime.fromisoformat(fecha_utc.replace('Z', '+00:00'))
                    # Convertir a hora Colombia (UTC-5)
                    from datetime import timezone
                    dt_col = dt.astimezone(timezone(timedelta(hours=-5)))

                    estado_map = {
                        'SCHEDULED': 'NS',
                        'TIMED': 'NS',
                        'IN_PLAY': 'LIVE',
                        'PAUSED': 'HT',
                        'FINISHED': 'FT',
                        'SUSPENDED': 'SUSP',
                        'POSTPONED': 'PST',
                        'CANCELLED': 'CANC',
                        'AWARDED': 'FT',
                    }
                    estado = estado_map.get(match.get('status', 'SCHEDULED'), 'NS')

                    score = match.get('score', {})
                    full_time = score.get('fullTime', {})
                    goles_local = full_time.get('home')
                    goles_visitante = full_time.get('away')

                    home = match.get('homeTeam', {})
                    away = match.get('awayTeam', {})
                    competition = match.get('competition', {})

                    partido, created = Partido.objects.update_or_create(
                        api_id=match['id'],
                        defaults={
                            'liga_nombre': competition.get('name', liga_nombre),
                            'liga_logo': competition.get('emblem', ''),
                            'liga_api_id': liga_id,
                            'equipo_local': home.get('name', 'TBD'),
                            'equipo_local_logo': home.get('crest', ''),
                            'equipo_visitante': away.get('name', 'TBD'),
                            'equipo_visitante_logo': away.get('crest', ''),
                            'fecha': dt_col.date(),
                            'hora': dt_col.time(),
                            'estado': estado,
                            'goles_local': goles_local,
                            'goles_visitante': goles_visitante,
                        }
                    )

                    if created:
                        total_creados += 1
                    else:
                        total_actualizados += 1

                    self.stdout.write(f'    {"+" if created else "="} {home.get("name")} vs {away.get("name")} ({dt_col.strftime("%d/%m %H:%M")})')

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Error: {e}'))

            # Respetar rate limit (10 req/min)
            import time
            time.sleep(7)

        self.stdout.write(self.style.SUCCESS(
            f'\nResultado: {total_creados} creados, {total_actualizados} actualizados'
        ))

    def crear_mapeos_iniciales(self):
        for codigo, liga_info in LIGAS.items():
            mapeo, created = MapeoLigaCanal.objects.get_or_create(
                liga_api_id=liga_info['id'],
                defaults={'liga_nombre': liga_info['nombre']}
            )
            if created:
                self.stdout.write(self.style.SUCCESS(f'  + {liga_info["nombre"]} (ID: {liga_info["id"]})'))
            else:
                self.stdout.write(f'  = {liga_info["nombre"]} ya existe')

        self.stdout.write(self.style.SUCCESS('\nMapeos creados. Ve al admin y asigna los canales a cada liga.'))
