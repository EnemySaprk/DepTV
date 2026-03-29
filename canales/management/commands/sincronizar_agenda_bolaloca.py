import requests
import re
import time
from datetime import datetime, timedelta, timezone
from django.core.management.base import BaseCommand
from canales.models import Partido


API_TOKEN = 'f432574001814e25b223b4e91e796fa3'
API_URL = 'https://api.football-data.org/v4'
COL_TZ = timezone(timedelta(hours=-5))

LIGAS = {
    'PL': {'nombre': 'Premier League', 'id': 2021},
    'PD': {'nombre': 'La Liga', 'id': 2014},
    'SA': {'nombre': 'Serie A', 'id': 2019},
    'BL1': {'nombre': 'Bundesliga', 'id': 2002},
    'FL1': {'nombre': 'Ligue 1', 'id': 2015},
    'CL': {'nombre': 'Champions League', 'id': 2001},
    'WC': {'nombre': 'FIFA World Cup', 'id': 2000},
}

# Ligas que se cargan solo de bolaloca
LIGAS_BOLALOCA = [
    'liga betplay',
    'copa libertadores',
    'copa sudamericana',
    'eliminatorias',
    'europa league',
    'conference league',
    'amistoso',
    'friendly',
    'world cup qualif',
    'uefa nations league',
    'conmebol',
    'copa america',
]

EQUIPOS_MAP = {
    'manchester utd': 'manchester united',
    'tottenham': 'tottenham hotspur',
    'newcastle': 'newcastle united',
    'nottingham': 'nottingham forest',
    'wolves': 'wolverhampton',
    'leeds': 'leeds united',
    'west ham': 'west ham',
    'brighton': 'brighton',
    'crystal palace': 'crystal palace',
    'atl. madrid': 'atlético',
    'atletico madrid': 'atlético',
    'betis': 'betis',
    'celta vigo': 'celta',
    'inter milan': 'internazionale',
    'ac milan': 'ac milan',
    'as roma': 'roma',
    'bayern': 'bayern',
    'dortmund': 'dortmund',
    'rb leipzig': 'leipzig',
    'werder bremen': 'werder bremen',
    'psg': 'paris saint-germain',
    'lyon': 'lyonnais',
    'rennes': 'rennais',
    'strasbourg': 'strasbourg',
    'bilbao': 'athletic club',
    'villarreal': 'villarreal',
    'getafe': 'getafe',
    'sevilla': 'sevilla',
    'valencia': 'valencia',
    'real sociedad': 'real sociedad',
    'napoli': 'napoli',
    'juventus': 'juventus',
    'fiorentina': 'fiorentina',
    'bologna': 'bologna',
    'atalanta': 'atalanta',
    'torino': 'torino',
    'monaco': 'monaco',
    'lille': 'lille',
    'marseille': 'marseille',
    'nantes': 'nantes',
    'hoffenheim': 'hoffenheim',
    'wolfsburg': 'wolfsburg',
    'mainz': 'mainz',
    'union berlin': 'union berlin',
    'freiburg': 'freiburg',
    'augsburg': 'augsburg',
    'frankfurt': 'eintracht frankfurt',
    'leverkusen': 'leverkusen',
    'liverpool': 'liverpool',
    'arsenal': 'arsenal',
    'chelsea': 'chelsea',
    'everton': 'everton',
    'fulham': 'fulham',
    'brentford': 'brentford',
    'bournemouth': 'bournemouth',
    'burnley': 'burnley',
    'sunderland': 'sunderland',
}


def normalizar(nombre):
    return nombre.lower().strip()


def nombres_coinciden(nombre1, nombre2):
    n1 = normalizar(nombre1)
    n2 = normalizar(nombre2)
    if n1 in n2 or n2 in n1:
        return True
    for corto, largo in EQUIPOS_MAP.items():
        if corto in n1 and largo in n2:
            return True
        if corto in n2 and largo in n1:
            return True
    return False


class Command(BaseCommand):
    help = 'Sincronizar agenda: logos de football-data.org + canales de bolaloca + ligas extra'

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=7, help='Dias a sincronizar')

    def handle(self, *args, **options):
        dias = options['dias']

        # Limpiar partidos viejos
        ayer = (datetime.now() - timedelta(days=1)).date()
        borrados = Partido.objects.filter(fecha__lt=ayer).delete()[0]
        if borrados:
            self.stdout.write(f'Partidos viejos borrados: {borrados}')

        # Paso 1: Cargar bolaloca
        self.stdout.write('\n=== BOLALOCA (canales + ligas extra) ===')
        agenda_bolaloca = self.cargar_bolaloca()

        # Paso 2: Cargar ligas extra de bolaloca
        self.stdout.write('\n=== LIGAS EXTRA (bolaloca) ===')
        extra_creados = self.cargar_ligas_extra_bolaloca(agenda_bolaloca)

        # Paso 3: Cargar partidos con logos desde football-data.org
        self.stdout.write('\n=== FOOTBALL-DATA.ORG (logos) ===')
        self.cargar_football_data(dias)

        # Paso 4: Cruzar canales
        self.stdout.write('\n=== CRUZANDO CANALES ===')
        asignados = 0
        for partido in Partido.objects.filter(canales_bolaloca=''):
            for bl in agenda_bolaloca:
                if (partido.fecha == bl['fecha'] and
                    nombres_coinciden(partido.equipo_local, bl['local']) and
                    nombres_coinciden(partido.equipo_visitante, bl['visitante'])):
                    partido.canales_bolaloca = bl['canales']
                    partido.save(update_fields=['canales_bolaloca'])
                    asignados += 1
                    self.stdout.write(f'  = {partido.equipo_local} vs {partido.equipo_visitante} -> CH{bl["canales"]}')
                    break

        self.stdout.write(self.style.SUCCESS(
            f'\nResumen:'
            f'\n  Canales asignados: {asignados}'
            f'\n  Ligas extra: {extra_creados}'
            f'\n  Total partidos en DB: {Partido.objects.count()}'
        ))

    def cargar_bolaloca(self):
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        agenda = []

        try:
            response = requests.get('https://bolaloca.my', headers=headers, timeout=15)
            if response.status_code != 200:
                self.stdout.write(self.style.ERROR(f'  Error HTTP: {response.status_code}'))
                return agenda
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  Error: {e}'))
            return agenda

        for linea in response.text.split('\n'):
            linea = linea.strip()
            match = re.match(r'(\d{2}-\d{2}-\d{4}) \((\d{2}:\d{2})\) (.+?) : (.+)', linea)
            if not match:
                continue

            fecha_str = match.group(1)
            hora_str = match.group(2)
            liga = match.group(3).strip()
            resto = match.group(4).strip()

            canales_match = re.findall(r'\(CH(\d+)(es|fr|de|uk|it|pt|us)\)', resto)
            canales_es = [ch[0] for ch in canales_match if ch[1] == 'es']
            canales_todos = [ch[0] for ch in canales_match]
            canales_usar = canales_es if canales_es else canales_todos

            equipos_texto = re.sub(r'\s*\(CH\d+\w+\)', '', resto).strip()
            partes = equipos_texto.split(' - ', 1)
            if len(partes) != 2:
                continue

            try:
                fecha = datetime.strptime(fecha_str, '%d-%m-%Y').date()
                hora = datetime.strptime(hora_str, '%H:%M').time()
            except ValueError:
                continue

            # Bolaloca usa CET (UTC+1), convertir a Colombia (UTC-5) = restar 6 horas
            dt_cet = datetime.combine(fecha, hora)
            dt_col = dt_cet - timedelta(hours=6)

            agenda.append({
                'fecha': dt_col.date(),
                'hora': dt_col.time(),
                'liga': liga,
                'local': partes[0].strip(),
                'visitante': partes[1].strip(),
                'canales': ','.join(canales_usar),
            })

        self.stdout.write(f'  {len(agenda)} eventos encontrados')
        return agenda

    def cargar_ligas_extra_bolaloca(self, agenda):
        creados = 0
        for evento in agenda:
            es_extra = any(lb in evento['liga'].lower() for lb in LIGAS_BOLALOCA)
            if not es_extra:
                continue

            api_id = abs(hash(f'{evento["fecha"]}_{evento["local"]}_{evento["visitante"]}')) % 2147483647

            partido, created = Partido.objects.update_or_create(
                api_id=api_id,
                defaults={
                    'liga_nombre': evento['liga'],
                    'liga_logo': '',
                    'liga_api_id': 0,
                    'equipo_local': evento['local'],
                    'equipo_local_logo': '',
                    'equipo_visitante': evento['visitante'],
                    'equipo_visitante_logo': '',
                    'fecha': evento['fecha'],
                    'hora': evento['hora'],
                    'estado': 'NS',
                    'goles_local': None,
                    'goles_visitante': None,
                    'canales_bolaloca': evento['canales'],
                }
            )

            if created:
                creados += 1
                self.stdout.write(f'  + {evento["local"]} vs {evento["visitante"]} ({evento["liga"]}) [CH{evento["canales"]}]')

        return creados

    def cargar_football_data(self, dias):
        headers = {'X-Auth-Token': API_TOKEN}
        fecha_desde = datetime.now().strftime('%Y-%m-%d')
        fecha_hasta = (datetime.now() + timedelta(days=dias)).strftime('%Y-%m-%d')
        total = 0

        for codigo, liga_info in LIGAS.items():
            self.stdout.write(f'  {liga_info["nombre"]}...')
            url = f'{API_URL}/competitions/{codigo}/matches?dateFrom={fecha_desde}&dateTo={fecha_hasta}'

            try:
                response = requests.get(url, headers=headers, timeout=15)
                if response.status_code == 429:
                    self.stdout.write(self.style.WARNING('  Rate limit, esperando 60s...'))
                    time.sleep(60)
                    response = requests.get(url, headers=headers, timeout=15)

                if response.status_code != 200:
                    self.stdout.write(self.style.ERROR(f'  Error {response.status_code}'))
                    continue

                data = response.json()
                matches = data.get('matches', [])
                self.stdout.write(f'    {len(matches)} partidos')

                for match in matches:
                    fecha_utc = match.get('utcDate', '')
                    if not fecha_utc:
                        continue

                    dt = datetime.fromisoformat(fecha_utc.replace('Z', '+00:00'))
                    dt_col = dt.astimezone(COL_TZ)

                    estado_map = {
                        'SCHEDULED': 'NS', 'TIMED': 'NS', 'IN_PLAY': 'LIVE',
                        'PAUSED': 'HT', 'FINISHED': 'FT', 'SUSPENDED': 'SUSP',
                        'POSTPONED': 'PST', 'CANCELLED': 'CANC', 'AWARDED': 'FT',
                    }

                    score = match.get('score', {}).get('fullTime', {})
                    home = match.get('homeTeam', {})
                    away = match.get('awayTeam', {})
                    competition = match.get('competition', {})

                    Partido.objects.update_or_create(
                        api_id=match['id'],
                        defaults={
                            'liga_nombre': competition.get('name', liga_info['nombre']),
                            'liga_logo': competition.get('emblem', ''),
                            'liga_api_id': liga_info['id'],
                            'equipo_local': home.get('name', 'TBD'),
                            'equipo_local_logo': home.get('crest', ''),
                            'equipo_visitante': away.get('name', 'TBD'),
                            'equipo_visitante_logo': away.get('crest', ''),
                            'fecha': dt_col.date(),
                            'hora': dt_col.time(),
                            'estado': estado_map.get(match.get('status', 'SCHEDULED'), 'NS'),
                            'goles_local': score.get('home'),
                            'goles_visitante': score.get('away'),
                        }
                    )
                    total += 1

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Error: {e}'))


            time.sleep(7)

        self.stdout.write(self.style.SUCCESS(f'  Total: {total}'))