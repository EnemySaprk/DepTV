import requests
import re
from datetime import datetime
from django.core.management.base import BaseCommand
from canales.models import Partido


class Command(BaseCommand):
    help = 'Sincronizar agenda de partidos desde bolaloca.my'

    def add_arguments(self, parser):
        parser.add_argument('--solo-futbol', action='store_true', help='Solo importar partidos de futbol')
        parser.add_argument('--todo', action='store_true', help='Importar todos los deportes')

    def handle(self, *args, **options):
        solo_futbol = not options.get('todo', False)

        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
        }

        self.stdout.write('Descargando agenda de bolaloca.my...')
        try:
            response = requests.get('https://bolaloca.my', headers=headers, timeout=15)
            if response.status_code != 200:
                self.stdout.write(self.style.ERROR(f'Error HTTP: {response.status_code}'))
                return
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'Error de conexion: {e}'))
            return

        texto = response.text
        lineas = texto.split('\n')
        total_creados = 0
        total_actualizados = 0
        total_saltados = 0

        ligas_futbol = [
            'liga betplay', 'premier league', 'la liga', 'serie a', 'bundesliga',
            'ligue 1', 'champions league', 'europa league', 'conference league',
            'copa libertadores', 'copa sudamericana', 'liga mx', 'mls',
            'torneo lpf', 'ligapro', 'liga auf', 'campeonato', 'liga 1',
            'copa del rey', 'fa cup', 'carabao cup', 'dfb pokal',
            'copa italia', 'coupe de france', 'super liga', 'eredivisie',
            'primeira liga', 'liga portugal', 'caf ligue', 'concacaf',
            'laliga', 'serie a bresil', 'liga de expansion',
            'conmebol', 'world cup', 'eliminatorias',
        ]

        for linea in lineas:
            linea = linea.strip()
            if not linea:
                continue

            match_basico = re.match(r'(\d{2}-\d{2}-\d{4}) \((\d{2}:\d{2})\) (.+?) : (.+)', linea)
            if not match_basico:
                continue

            fecha_str = match_basico.group(1)
            hora_str = match_basico.group(2)
            liga = match_basico.group(3).strip()
            resto = match_basico.group(4).strip()

            if solo_futbol:
                es_futbol = any(lf in liga.lower() for lf in ligas_futbol)
                if not es_futbol:
                    total_saltados += 1
                    continue

            # Extraer canales
            canales_match = re.findall(r'\(CH(\d+)(es|fr|de|uk|it|pt|us)\)', resto)
            canales_es = [ch[0] for ch in canales_match if ch[1] == 'es']
            canales_todos = [ch[0] for ch in canales_match]

            # Usar canales en español si hay, si no todos
            canales_usar = canales_es if canales_es else canales_todos
            canales_str = ','.join(canales_usar)

            # Limpiar equipos
            equipos_texto = re.sub(r'\s*\(CH\d+\w+\)', '', resto).strip()
            partes = equipos_texto.split(' - ', 1)
            if len(partes) != 2:
                continue

            equipo_local = partes[0].strip()
            equipo_visitante = partes[1].strip()

            try:
                fecha = datetime.strptime(fecha_str, '%d-%m-%Y').date()
                hora = datetime.strptime(hora_str, '%H:%M').time()
            except ValueError:
                continue

            api_id = abs(hash(f'{fecha_str}_{equipo_local}_{equipo_visitante}')) % 2147483647

            partido, created = Partido.objects.update_or_create(
                api_id=api_id,
                defaults={
                    'liga_nombre': liga,
                    'liga_logo': '',
                    'liga_api_id': 0,
                    'equipo_local': equipo_local,
                    'equipo_local_logo': '',
                    'equipo_visitante': equipo_visitante,
                    'equipo_visitante_logo': '',
                    'fecha': fecha,
                    'hora': hora,
                    'estado': 'NS',
                    'goles_local': None,
                    'goles_visitante': None,
                    'canales_bolaloca': canales_str,
                }
            )

            if created:
                total_creados += 1
                self.stdout.write(f'  + {equipo_local} vs {equipo_visitante} ({liga}) [CH{",CH".join(canales_usar)}]')
            else:
                total_actualizados += 1

        self.stdout.write(self.style.SUCCESS(
            f'\nResultado: {total_creados} creados, {total_actualizados} actualizados, {total_saltados} saltados'
        ))
