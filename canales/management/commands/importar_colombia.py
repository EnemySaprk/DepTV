"""
Importa partidos desde colombia.com/futbol/partidos-hoy/
y asigna automáticamente los canales encontrados en la página.

Uso normal (ejecutar una vez):
    python manage.py importar_colombia

Opciones:
    python manage.py importar_colombia --solo-vista
"""
import re
import time
import requests
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from bs4 import BeautifulSoup
from django.core.management.base import BaseCommand
from canales.models import Partido, Canal, Liga

COL_TZ = ZoneInfo('America/Bogota')

BASE_URL = 'https://www.colombia.com'
URLS_PAGINAS = [
    f'{BASE_URL}/futbol/partidos-hoy/',
    f'{BASE_URL}/futbol/partidos-manana/',
]

HEADERS = {
    'User-Agent': (
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) '
        'AppleWebKit/537.36 (KHTML, like Gecko) '
        'Chrome/124.0.0.0 Safari/537.36'
    ),
    'Accept-Language': 'es-CO,es;q=0.9',
    'Accept': 'text/html,application/xhtml+xml',
}

DIAS_ES = {
    'lunes': 0, 'martes': 1, 'miércoles': 2, 'miercoles': 2,
    'jueves': 3, 'viernes': 4, 'sábado': 5, 'sabado': 5, 'domingo': 6,
}

ESTADO_MAP = {
    'no iniciado': 'NS', 'programado': 'NS',
    'primer tiempo': '1H', '1er tiempo': '1H', '1t': '1H',
    'medio tiempo': 'HT', 'descanso': 'HT', 'entretiempo': 'HT',
    'segundo tiempo': '2H', '2t': '2H',
    'finalizado': 'FT', 'jugado': 'FT', 'terminado': 'FT',
    'suspendido': 'SUSP', 'postergado': 'PST', 'aplazado': 'PST',
    'cancelado': 'CANC',
    'en juego': 'LIVE', 'en vivo': 'LIVE',
    'tiempo extra': 'AET', 'penales': 'PEN',
}


PALABRAS_IGNORAR = {'de', 'del', 'la', 'las', 'los', 'the', 'a', 'en', 'el', 'y'}


def _construir_filtro(ligas_db):
    filtros = []
    for liga in ligas_db:
        nombre = liga.nombre.lower().strip()
        sin_espacios = re.sub(r'\s+', '', nombre)
        palabras = {p for p in nombre.split() if len(p) > 4 and p not in PALABRAS_IGNORAR}
        filtros.append((nombre, sin_espacios, palabras))
    return filtros


def _es_relevante(liga_nombre: str, filtros: list) -> bool:
    liga_lower = liga_nombre.lower()
    liga_norm = re.sub(r'\s+', '', liga_lower)
    for nombre_completo, sin_espacios, palabras in filtros:
        if nombre_completo in liga_lower or liga_lower in nombre_completo:
            return True
        if sin_espacios and (sin_espacios in liga_norm or liga_norm in sin_espacios):
            return True
        if any(p in liga_lower for p in palabras):
            return True
    return False


class Command(BaseCommand):
    help = (
        'Importa partidos de colombia.com y asigna canales automáticamente.\n'
        'Scrapea "Partidos Hoy" y "Partidos Mañana".'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--solo-vista', action='store_true',
            help='Muestra los partidos sin guardar en la base de datos',
        )

    def handle(self, *args, **options):
        solo_vista = options['solo_vista']

        # Cargar ligas activas de la DB para filtrar
        ligas_db = list(Liga.objects.filter(activa=True))
        if not ligas_db:
            self.stdout.write(self.style.WARNING(
                'No hay ligas activas en la base de datos. '
                'Ve al admin → Ligas y crea las competencias que quieres seguir.'
            ))
            return

        filtros_liga = _construir_filtro(ligas_db)
        self.stdout.write(
            f'Filtrando por {len(ligas_db)} ligas: '
            + ', '.join(l.nombre for l in ligas_db)
        )

        # Borrar partidos viejos automáticamente
        if not solo_vista:
            ayer = (datetime.now(tz=COL_TZ) - timedelta(days=1)).date()
            borrados = Partido.objects.filter(fecha__lt=ayer).delete()[0]
            if borrados:
                self.stdout.write(f'Partidos viejos borrados: {borrados}')

        # Cargar todos los canales activos una vez para el mapeo
        canales_db = {c.nombre.lower(): c for c in Canal.objects.filter(activo=True)}
        self.stdout.write(f'Canales en DB: {len(canales_db)}')

        total_creados = 0
        total_actualizados = 0

        for url in URLS_PAGINAS:
            self.stdout.write(f'\n=== {url} ===')
            partidos = self._scrapear_pagina(url)

            if not partidos:
                self.stdout.write(self.style.WARNING('  Sin partidos o no se pudo cargar.'))
                continue

            self.stdout.write(f'  {len(partidos)} partidos en la página')

            omitidos = 0
            for p in partidos:
                # Filtrar por ligas de la DB
                if not _es_relevante(p['liga'], filtros_liga):
                    omitidos += 1
                    continue

                canales_encontrados = self._mapear_canales(p['canales_texto'], canales_db)
                indicador = '[VISTA] ' if solo_vista else ''
                canal_str = ', '.join(c.nombre for c in canales_encontrados) or '(sin canal)'
                self.stdout.write(
                    f'  {indicador}[{p["liga"]}] '
                    f'{p["local"]} vs {p["visitante"]}  '
                    f'{p["hora"].strftime("%H:%M") if p["hora"] else "?"} COL  '
                    f'→ {canal_str}'
                )

                if not solo_vista:
                    import hashlib
                    id_str = f'{p["fecha"]}_{p["local"]}_{p["visitante"]}'
                    api_id = int(hashlib.md5(id_str.encode()).hexdigest(), 16) % 2_000_000_000

                    partido, created = Partido.objects.update_or_create(
                        api_id=api_id,
                        defaults={
                            'liga_nombre': p['liga'],
                            'liga_logo': '',
                            'liga_api_id': 0,
                            'equipo_local': p['local'],
                            'equipo_local_logo': '',
                            'equipo_visitante': p['visitante'],
                            'equipo_visitante_logo': '',
                            'fecha': p['fecha'],
                            'hora': p['hora'] or datetime.now(tz=COL_TZ).time(),
                            'estado': p['estado'],
                            'goles_local': p.get('goles_local'),
                            'goles_visitante': p.get('goles_visitante'),
                            'minuto': None,
                        }
                    )

                    if canales_encontrados:
                        partido.canales.set(canales_encontrados)

                    if created:
                        total_creados += 1
                    else:
                        total_actualizados += 1

            self.stdout.write(f'  Omitidos (no están en tus ligas): {omitidos}')
            time.sleep(1)

        if solo_vista:
            self.stdout.write(self.style.SUCCESS('\n[SOLO VISTA] Nada guardado.'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\nListo. Creados: {total_creados} | Actualizados: {total_actualizados}'
            ))
            self.stdout.write('Revisa el admin → Partidos para ajustar canales manualmente.')

    # ------------------------------------------------------------------

    # Palabras clave para detectar líneas de canal
    _CANAL_KEYWORDS = {
        'espn', 'win sports', 'dazn', 'disney', 'fox', 'directv', 'dgo',
        'tigo', 'movistar', 'claro', 'rcn', 'caracol', 'amazon', 'youtube',
        'hbo', 'star+', 'star plus', 'paramount', 'peacock', 'apple tv',
        'canal+', 'mediapro', 'viaplay', 'sky', 'bein', 'eleven', 'onefootball',
        'telecaribe', 'telepacifico', 'telelibertad', 'canal 13', 'canal rcn',
    }

    def _scrapear_pagina(self, url):
        try:
            r = requests.get(url, headers=HEADERS, timeout=20)
            if r.status_code != 200:
                self.stdout.write(self.style.ERROR(f'  HTTP {r.status_code}'))
                return []
            r.encoding = 'utf-8'
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'  Error de conexión: {e}'))
            return []

        soup = BeautifulSoup(r.text, 'html.parser')
        return self._parsear_texto(soup, url)

    def _parsear_texto(self, soup, url):
        """
        Parser principal basado en ventana de contexto.
        Colombia.com estructura cada partido como:
          [Línea de liga]
          Equipo Local vs Equipo Visitante
          Día - HH:MM AM/PM
          Canal(es)
          Marcador / Estado
        """
        hoy = datetime.now(tz=COL_TZ).date()
        es_manana = 'manana' in url or 'mañana' in url
        fecha_base = hoy + timedelta(days=1) if es_manana else hoy

        texto_completo = soup.get_text(separator='\n')
        lineas = [l.strip() for l in texto_completo.splitlines() if l.strip()]

        partidos = []

        for i, linea in enumerate(lineas):
            # Identificar línea de partido: contiene " vs " con texto en ambos lados
            local = visitante = None
            for sep in (' vs ', ' Vs ', ' VS '):
                if sep in linea:
                    partes = linea.split(sep, 1)
                    candidato_local = partes[0].strip()
                    candidato_vis = re.split(r'\s+\d{1,2}[:\-]\d{2}', partes[1])[0].strip()
                    # Descartar líneas que son claramente navegación o títulos largos
                    if (candidato_local and candidato_vis
                            and 2 < len(candidato_local) < 60
                            and 2 < len(candidato_vis) < 60):
                        local = candidato_local
                        visitante = candidato_vis
                    break

            if not local:
                continue

            # ── Liga: buscar en las 5 líneas anteriores ──────────────────────
            liga = 'Sin liga'
            for l in reversed(lineas[max(0, i - 5):i]):
                # Formato colombia.com: "LaLiga de España - 2025/2026"
                if re.search(r'(de\s+\w+\s+-\s+\d{4}/\d{4}|\d{4}/\d{4})', l):
                    liga = re.sub(r'\s*-\s*\d{4}/\d{4}.*$', '', l).strip()
                    break
                # Línea de torneo genérico (no es hora ni canal ni equipo)
                if (len(l) > 8 and
                        not re.search(r'\d{1,2}:\d{2}', l) and
                        not any(kw in l.lower() for kw in self._CANAL_KEYWORDS) and
                        local.split()[0] not in l and visitante.split()[0] not in l):
                    liga = re.sub(r'\s*-\s*\d{4}/\d{4}.*$', '', l).strip()
                    break

            # ── Contexto siguiente: hora, canales, marcador ───────────────────
            hora_obj = None
            fecha_obj = fecha_base
            canales_texto = []
            goles_local = goles_visitante = None
            estado = 'NS'

            for l in lineas[i + 1: i + 7]:
                # Si encontramos otro partido, parar
                if any(sep in l for sep in (' vs ', ' Vs ', ' VS ')):
                    break

                # Hora: "Domingo - 03:00 PM" o "3:00 PM"
                if hora_obj is None and re.search(r'\d{1,2}:\d{2}\s*(AM|PM|am|pm)', l):
                    fecha_obj, hora_obj = self._parsear_tiempo(l, url)
                    continue

                # Marcador: "2-1" o "2 - 1"
                score_match = re.fullmatch(r'(\d+)\s*[-–]\s*(\d+)', l)
                if score_match:
                    goles_local = int(score_match.group(1))
                    goles_visitante = int(score_match.group(2))
                    continue

                # Estado
                l_lower = l.lower()
                if l_lower in ESTADO_MAP:
                    estado = ESTADO_MAP[l_lower]
                    continue

                # Canal: línea que contenga una palabra clave de canal
                if any(kw in l_lower for kw in self._CANAL_KEYWORDS):
                    # Eliminar prefijo "CANAL:" si existe
                    canal_raw = re.sub(r'^canales?\s*[:\-]\s*', '', l, flags=re.IGNORECASE)
                    for c in re.split(r',\s*', canal_raw):
                        c = c.strip()
                        if c and len(c) > 2:
                            canales_texto.append(c)

            partidos.append({
                'liga': liga,
                'local': local,
                'visitante': visitante,
                'fecha': fecha_obj,
                'hora': hora_obj,
                'estado': estado,
                'goles_local': goles_local if estado != 'NS' else None,
                'goles_visitante': goles_visitante if estado != 'NS' else None,
                'canales_texto': canales_texto,
            })

        return partidos

    def _parsear_tiempo(self, texto, url):
        """Convierte 'Domingo - 03:00 PM' en (date, time) en zona Colombia."""
        hoy = datetime.now(tz=COL_TZ).date()
        es_manana = 'manana' in url or 'mañana' in url
        fecha_base = hoy + timedelta(days=1) if es_manana else hoy

        if not texto:
            return fecha_base, None

        # Detectar día de la semana para calcular la fecha exacta
        texto_lower = texto.lower()
        dia_semana = None
        for nombre, num in DIAS_ES.items():
            if nombre in texto_lower:
                dia_semana = num
                break

        if dia_semana is not None:
            # Buscar el próximo día que coincida con el día de semana
            for delta in range(7):
                candidato = hoy + timedelta(days=delta)
                if candidato.weekday() == dia_semana:
                    fecha_base = candidato
                    break

        # Extraer hora
        match_hora = re.search(r'(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)?', texto)
        if not match_hora:
            return fecha_base, None

        hora_h = int(match_hora.group(1))
        hora_m = int(match_hora.group(2))
        ampm = (match_hora.group(3) or '').upper()

        if ampm == 'PM' and hora_h < 12:
            hora_h += 12
        elif ampm == 'AM' and hora_h == 12:
            hora_h = 0

        try:
            hora_obj = datetime(2000, 1, 1, hora_h, hora_m).time()
        except ValueError:
            return fecha_base, None

        return fecha_base, hora_obj

    def _mapear_canales(self, canales_texto, canales_db):
        """Intenta hacer match entre nombres de canales de colombia.com y Canal en DB."""
        encontrados = []
        for nombre_raw in canales_texto:
            nombre_lower = nombre_raw.lower().strip()

            # Match exacto primero
            if nombre_lower in canales_db:
                encontrados.append(canales_db[nombre_lower])
                continue

            # Match parcial: buscar si algún canal de DB está contenido en el texto
            for clave, canal in canales_db.items():
                if clave in nombre_lower or nombre_lower in clave:
                    encontrados.append(canal)
                    break

        # Eliminar duplicados manteniendo orden
        vistos = set()
        unicos = []
        for c in encontrados:
            if c.pk not in vistos:
                vistos.add(c.pk)
                unicos.append(c)
        return unicos
