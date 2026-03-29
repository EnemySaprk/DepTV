import requests
import re
import time
from datetime import datetime, timedelta, timezone
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from canales.models import Partido, Video


API_TOKEN = 'f432574001814e25b223b4e91e796fa3'
API_URL = 'https://api.football-data.org/v4'
COL_TZ = timezone(timedelta(hours=-5))

LIGAS_API = {
    'PL': {'nombre': 'Premier League', 'id': 2021},
    'PD': {'nombre': 'La Liga', 'id': 2014},
    'SA': {'nombre': 'Serie A', 'id': 2019},
    'BL1': {'nombre': 'Bundesliga', 'id': 2002},
    'FL1': {'nombre': 'Ligue 1', 'id': 2015},
    'CL': {'nombre': 'Champions League', 'id': 2001},
    'WC': {'nombre': 'FIFA World Cup', 'id': 2000},
}

# Mapeo de nombre de canal en RusticoTV -> titulo de Video en FutbolTube
CANAL_MAP = {
    'espn': 'ESPN 1',
    'espn 2': 'ESPN 2',
    'espn 3': 'ESPN 3',
    'espn 4': 'ESPN 4',
    'espn premium': 'ESPN Premium',
    'espn deportes': 'ESPN Deportes',
    'dsports': 'DSports',
    'dsports 2': 'DSports 2',
    'dsports+': 'DSports Plus',
    'win sports+': 'Win Sports+',
    'win sports': 'Win Sports+',
    'dazn 1': 'DAZN 1',
    'dazn 2': 'DAZN 2',
    'dazn laliga': 'DAZN LaLiga',
    'dazn f1': 'DAZN F1',
    'movistar laliga': 'Movistar LaLiga',
    'm+ laliga': 'M+ LaLiga TV',
    'liga de campeones': 'Liga de Campeones 1',
    'liga de campeones 1': 'Liga de Campeones 1',
    'liga de campeones 2': 'Liga de Campeones 2',
    'liga de campeones 3': 'Liga de Campeones 3',
}


class Command(BaseCommand):
    help = 'Sincronizar agenda: football-data.org (logos) + RusticoTV (canales extra)'

    def add_arguments(self, parser):
        parser.add_argument('--dias', type=int, default=7, help='Dias a sincronizar')
        parser.add_argument('--solo-api', action='store_true', help='Solo usar football-data.org')
        parser.add_argument('--solo-rustico', action='store_true', help='Solo usar RusticoTV')

    def handle(self, *args, **options):
        dias = options['dias']

        # Limpiar partidos viejos (excepto Mundial)
        ayer = (datetime.now() - timedelta(days=1)).date()
        borrados = Partido.objects.filter(fecha__lt=ayer).exclude(liga_api_id=2000).delete()[0]
        if borrados:
            self.stdout.write(f'Partidos viejos borrados: {borrados}')

        if not options.get('solo_rustico'):
            self.stdout.write('\n=== FOOTBALL-DATA.ORG ===')
            self.cargar_football_data(dias)

        if not options.get('solo_api'):
            self.stdout.write('\n=== RUSTICOTV (canales + ligas extra) ===')
            agenda_rustico = self.cargar_rusticotv()

            if agenda_rustico:
                self.stdout.write('\n=== CRUZANDO CANALES ===')
                self.cruzar_canales(agenda_rustico)

                self.stdout.write('\n=== LIGAS EXTRA ===')
                self.cargar_ligas_extra(agenda_rustico)

        self.stdout.write(self.style.SUCCESS(
            f'\nTotal partidos en DB: {Partido.objects.count()}'
        ))

    def cargar_rusticotv(self):
        """Scrapea la agenda de RusticoTV"""
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        agenda = []

        try:
            response = requests.get('https://rusticotv.cc/agenda.html', headers=headers, timeout=15)
            response.encoding = 'utf-8'
            if response.status_code != 200:
                self.stdout.write(self.style.ERROR(f'  Error HTTP: {response.status_code}'))
                return agenda
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  Error: {e}'))
            return agenda

        soup = BeautifulSoup(response.text, 'html.parser')
        todos_li = soup.find_all('li')

        partido_actual = None
        hoy = datetime.now().date()

        for li in todos_li:
            clases = li.get('class', [])

            if 'subitem1' in clases:
                if partido_actual:
                    canal_texto = li.get_text(strip=True)
                    canal_nombre = re.split(r'Calidad', canal_texto)[0].strip()
                    canal_limpio = re.sub(r'\s*\(OP\d+\)\s*', '', canal_nombre).strip().lower()
                    if canal_limpio:
                        partido_actual['canales_rustico'].append(canal_nombre)
                        video_titulo = CANAL_MAP.get(canal_limpio)
                        if video_titulo and video_titulo not in partido_actual['canales_mapeados']:
                            partido_actual['canales_mapeados'].append(video_titulo)
                continue

            texto = li.get_text(separator='|', strip=True)
            if not texto or ':' not in texto:
                continue

            match = re.match(r'(.+?):\s*(.+?)\s*\|\s*(\d{2}:\d{2})', texto)
            if not match:
                continue

            liga = match.group(1).strip()
            equipos_texto = match.group(2).strip()
            hora_str = match.group(3).strip()

            separadores = [' vs ', ' Vs ', ' VS ', ' v ', ' - ']
            local = visitante = ''
            for sep in separadores:
                if sep in equipos_texto:
                    partes = equipos_texto.split(sep, 1)
                    local = partes[0].strip()
                    visitante = partes[1].strip()
                    break

            if not local or not visitante:
                continue

            try:
                hora = datetime.strptime(hora_str, '%H:%M').time()
            except ValueError:
                continue

            if partido_actual:
                agenda.append(partido_actual)

            partido_actual = {
                'liga': liga,
                'local': local,
                'visitante': visitante,
                'fecha': hoy,
                'hora': hora,
                'canales_rustico': [],
                'canales_mapeados': [],
            }

        if partido_actual:
            agenda.append(partido_actual)

        self.stdout.write(f'  {len(agenda)} partidos encontrados')
        for p in agenda[:15]:
            canales = ', '.join(p['canales_mapeados']) if p['canales_mapeados'] else 'sin mapeo local'
            self.stdout.write(f'    {p["local"]} vs {p["visitante"]} ({p["liga"]}) -> [{canales}]')
        if len(agenda) > 15:
            self.stdout.write(f'    ... y {len(agenda) - 15} mas')

        return agenda

    def cruzar_canales(self, agenda):
        """Asigna canales de RusticoTV a partidos existentes"""
        asignados = 0

        for evento in agenda:
            if not evento['canales_mapeados']:
                continue

            canales_str = ','.join(evento['canales_mapeados'])

            partidos = Partido.objects.filter(
                fecha=evento['fecha'],
                canales_bolaloca='',
            )

            for partido in partidos:
                if (self._nombres_similares(partido.equipo_local, evento['local']) and
                    self._nombres_similares(partido.equipo_visitante, evento['visitante'])):
                    partido.canales_bolaloca = canales_str
                    partido.save(update_fields=['canales_bolaloca'])
                    asignados += 1
                    self.stdout.write(f'  = {partido.equipo_local} vs {partido.equipo_visitante} -> {canales_str}')
                    break

        self.stdout.write(self.style.SUCCESS(f'  Canales asignados: {asignados}'))

    def cargar_ligas_extra(self, agenda):
        """Carga partidos de ligas extra (amistosos, betplay, etc.)"""
        creados = 0
        ligas_extra = [
            'amistoso', 'friendly', 'eliminatoria',
            'categoria primera', 'liga betplay', 'primera a',
            'copa libertadores', 'copa sudamericana',
            'europa league', 'conference league',
            'copa argentina', 'nations league',
        ]

        for evento in agenda:
            liga_lower = evento['liga'].lower()
            es_extra = any(lf in liga_lower for lf in ligas_extra)
            if not es_extra:
                continue

            # ID determinístico basado en fecha + equipos
            id_str = f'{evento["fecha"]}_{evento["local"]}_{evento["visitante"]}'
            api_id = int.from_bytes(id_str.encode('utf-8')[:8], 'big') % 2147483647
            canales_str = ','.join(evento['canales_mapeados']) if evento['canales_mapeados'] else ''

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
                    'canales_bolaloca': canales_str,
                }
            )

            if created:
                creados += 1
                self.stdout.write(f'  + {evento["local"]} vs {evento["visitante"]} ({evento["liga"]}) [{canales_str}]')

        self.stdout.write(self.style.SUCCESS(f'  Ligas extra creadas: {creados}'))

    def cargar_football_data(self, dias):
        """Carga partidos con logos desde football-data.org"""
        headers = {'X-Auth-Token': API_TOKEN}
        fecha_desde = datetime.now().strftime('%Y-%m-%d')
        fecha_hasta = (datetime.now() + timedelta(days=dias)).strftime('%Y-%m-%d')
        total = 0

        for codigo, liga_info in LIGAS_API.items():
            self.stdout.write(f'  {liga_info["nombre"]}...')

            if codigo == 'WC':
                url = f'{API_URL}/competitions/{codigo}/matches?season=2026'
            else:
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
                            'liga_logo': competition.get('emblem') or '',
                            'liga_api_id': liga_info['id'],
                            'equipo_local': home.get('name') or 'Por definir',
                            'equipo_local_logo': home.get('crest') or '',
                            'equipo_visitante': away.get('name') or 'Por definir',
                            'equipo_visitante_logo': away.get('crest') or '',
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

    def _nombres_similares(self, nombre1, nombre2):
        """Compara nombres de equipos de forma flexible"""
        n1 = nombre1.lower().strip()
        n2 = nombre2.lower().strip()
        if n1 in n2 or n2 in n1:
            return True
        palabras1 = set(n1.split())
        palabras2 = set(n2.split())
        comunes = palabras1 & palabras2
        if len(comunes) >= 1 and any(len(p) > 3 for p in comunes):
            return True
        return False