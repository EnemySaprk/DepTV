"""
Importa la agenda semanal de fútbol desde SofaScore.

Uso normal (ejecutar una vez por semana):
    python manage.py importar_sofascore

Opciones avanzadas:
    python manage.py importar_sofascore --dias 14         # dos semanas
    python manage.py importar_sofascore --solo-vista      # ver sin guardar
    python manage.py importar_sofascore --todo            # sin filtro de ligas
"""
import re
import time
import requests
from datetime import datetime, timedelta, timezone
from zoneinfo import ZoneInfo
from django.core.management.base import BaseCommand
from canales.models import Partido, Liga

COL_TZ = ZoneInfo('America/Bogota')
SOFASCORE_API = 'https://api.sofascore.com/api/v1'
SOFASCORE_HOME = 'https://www.sofascore.com'


def _crear_sesion():
    session = requests.Session()
    session.headers.update({
        'User-Agent': (
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36'
        ),
        'Accept': '*/*',
        'Accept-Language': 'es-CO,es;q=0.9',
        'Origin': SOFASCORE_HOME,
        'Referer': f'{SOFASCORE_HOME}/',
        'sec-fetch-dest': 'empty',
        'sec-fetch-mode': 'cors',
        'sec-fetch-site': 'same-site',
    })
    try:
        session.get(SOFASCORE_HOME, timeout=15)
        time.sleep(1.5)
    except Exception:
        pass
    return session

STATUS_MAP = {
    'notstarted': 'NS',
    'inprogress': 'LIVE',
    'finished': 'FT',
    'postponed': 'PST',
    'canceled': 'CANC',
    'cancelled': 'CANC',
    'interrupted': 'SUSP',
    'pause': 'HT',
    'halftime': 'HT',
    'awaitingextratime': 'HT',
    'extratime': 'AET',
    'penalties': 'PEN',
}

PALABRAS_IGNORAR = {'de', 'del', 'la', 'las', 'los', 'the', 'a', 'en', 'el', 'y'}


def _construir_filtro(ligas_db):
    """
    Construye pares (nombre_completo, palabras_clave) para cada liga en DB.
    Se usa para matching flexible contra nombres de SofaScore.
    """
    filtros = []
    for liga in ligas_db:
        nombre = liga.nombre.lower().strip()
        sin_espacios = re.sub(r'\s+', '', nombre)
        palabras = {
            p for p in nombre.split()
            if len(p) > 4 and p not in PALABRAS_IGNORAR
        }
        filtros.append((nombre, sin_espacios, palabras))
    return filtros


def _es_relevante(liga_nombre: str, filtros: list) -> bool:
    liga_lower = liga_nombre.lower()
    liga_norm = re.sub(r'\s+', '', liga_lower)

    for nombre_completo, sin_espacios, palabras in filtros:
        # Coincidencia de nombre completo (en cualquier dirección)
        if nombre_completo in liga_lower or liga_lower in nombre_completo:
            return True
        # Coincidencia sin espacios: "la liga" ↔ "laliga"
        if sin_espacios and (sin_espacios in liga_norm or liga_norm in sin_espacios):
            return True
        # Coincidencia por palabras clave significativas
        if any(p in liga_lower for p in palabras):
            return True
    return False


class Command(BaseCommand):
    help = 'Importa la agenda semanal de fútbol desde SofaScore (ejecutar una vez por semana).'

    def add_arguments(self, parser):
        parser.add_argument(
            '--dias', type=int, default=7,
            help='Días a importar desde hoy (default: 7)',
        )
        parser.add_argument(
            '--solo-vista', action='store_true',
            help='Muestra los partidos sin guardar en la base de datos',
        )
        parser.add_argument(
            '--todo', action='store_true',
            help='Importa todos los deportes sin filtrar por liga',
        )

    def handle(self, *args, **options):
        dias = options['dias']
        solo_vista = options['solo_vista']
        sin_filtro = options['todo']

        fecha_inicio = datetime.now(tz=COL_TZ).date()

        # Cargar ligas activas de la base de datos
        ligas_db = list(Liga.objects.filter(activa=True))
        if not ligas_db:
            self.stdout.write(self.style.WARNING(
                'No hay ligas activas en la base de datos. '
                'Ve al admin → Ligas y crea las competencias que quieres seguir, '
                'o usa --todo para importar sin filtro.'
            ))
            if not sin_filtro:
                return

        filtros = _construir_filtro(ligas_db)
        self.stdout.write(
            f'Filtrando por {len(ligas_db)} ligas de la DB: '
            + ', '.join(l.nombre for l in ligas_db)
        )

        # Borrar partidos anteriores a ayer automáticamente
        if not solo_vista:
            ayer = (datetime.now(tz=COL_TZ) - timedelta(days=1)).date()
            borrados = Partido.objects.filter(fecha__lt=ayer).delete()[0]
            if borrados:
                self.stdout.write(f'Partidos viejos borrados: {borrados}')

        total_creados = 0
        total_actualizados = 0
        total_omitidos = 0

        self.stdout.write('Conectando con SofaScore...')
        scraper = _crear_sesion()  # noqa: variable reutilizada como session

        for i in range(dias):
            fecha = fecha_inicio + timedelta(days=i)
            fecha_str = fecha.strftime('%Y-%m-%d')
            self.stdout.write(f'\n── {fecha_str} ──')

            try:
                url = f'{SOFASCORE_API}/sport/football/scheduled-events/{fecha_str}'
                response = scraper.get(url, timeout=20)

                if response.status_code != 200:
                    self.stdout.write(self.style.ERROR(f'  HTTP {response.status_code} — omitiendo día'))
                    continue

                eventos = response.json().get('events', [])
                guardados_dia = 0

                for evento in eventos:
                    torneo = evento.get('tournament', {})
                    liga_nombre = torneo.get('name', '')
                    pais_nombre = torneo.get('category', {}).get('name', '')

                    # Filtro por ligas de la DB (se salta si --todo)
                    if not sin_filtro and not _es_relevante(liga_nombre, filtros):
                        total_omitidos += 1
                        continue

                    home = evento.get('homeTeam', {})
                    away = evento.get('awayTeam', {})
                    home_nombre = home.get('name', 'Por definir')
                    away_nombre = away.get('name', 'Por definir')

                    timestamp = evento.get('startTimestamp', 0)
                    dt_col = datetime.fromtimestamp(timestamp, tz=timezone.utc).astimezone(COL_TZ)

                    status_type = evento.get('status', {}).get('type', 'notstarted')
                    estado = STATUS_MAP.get(status_type, 'NS')

                    goles_local = goles_visitante = None
                    if estado not in ('NS', 'PST', 'CANC'):
                        goles_local = evento.get('homeScore', {}).get('current')
                        goles_visitante = evento.get('awayScore', {}).get('current')

                    home_id = home.get('id', '')
                    away_id = away.get('id', '')
                    torneo_id = (
                        torneo.get('uniqueTournament', {}).get('id')
                        or torneo.get('id', '')
                    )
                    home_logo = f'{SOFASCORE_API}/team/{home_id}/image' if home_id else ''
                    away_logo = f'{SOFASCORE_API}/team/{away_id}/image' if away_id else ''
                    liga_logo = (
                        f'{SOFASCORE_API}/unique-tournament/{torneo_id}/image/dark'
                        if torneo_id else ''
                    )

                    # Offset para no colisionar con IDs de football-data.org
                    api_id = 9_000_000 + evento.get('id', 0)

                    self.stdout.write(
                        f'  {"[VISTA] " if solo_vista else ""}'
                        f'[{pais_nombre} / {liga_nombre}]  '
                        f'{home_nombre} vs {away_nombre}  '
                        f'{dt_col.strftime("%H:%M")} COL'
                    )

                    if not solo_vista:
                        _, created = Partido.objects.update_or_create(
                            api_id=api_id,
                            defaults={
                                'liga_nombre': liga_nombre,
                                'liga_logo': liga_logo,
                                'liga_api_id': 0,
                                'equipo_local': home_nombre,
                                'equipo_local_logo': home_logo,
                                'equipo_visitante': away_nombre,
                                'equipo_visitante_logo': away_logo,
                                'fecha': dt_col.date(),
                                'hora': dt_col.time(),
                                'estado': estado,
                                'goles_local': goles_local,
                                'goles_visitante': goles_visitante,
                                'minuto': None,
                            }
                        )
                        guardados_dia += 1
                        if created:
                            total_creados += 1
                        else:
                            total_actualizados += 1

                if not solo_vista:
                    self.stdout.write(f'  → {guardados_dia} guardados')

            except Exception as e:
                self.stdout.write(self.style.ERROR(f'  Error: {e}'))

            time.sleep(1.5)

        self.stdout.write('')
        if solo_vista:
            self.stdout.write(self.style.SUCCESS(
                f'[VISTA] Nada guardado. '
                f'Omitidos por filtro: {total_omitidos}'
            ))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'Listo. Creados: {total_creados} | '
                f'Actualizados: {total_actualizados} | '
                f'Omitidos: {total_omitidos}'
            ))
            self.stdout.write(
                'Entra al admin → Partidos y asigna los canales a cada partido.'
            )
