"""
Importa partidos desde un email enviado a tu cuenta de Gmail.

── CÓMO USAR ────────────────────────────────────────────────────────────────
1. Abre Gmail y redacta un email A TI MISMO con asunto: Partidos
2. En el cuerpo escribe los partidos con este formato:

   Champions League
   Arsenal vs PSG - 01/05/2026 20:00 - ESPN 1, Win Sports+
   Manchester City vs Real Madrid - 07/05/2026 21:00 - ESPN 2

   Liga BetPlay
   Millonarios vs Nacional - 28/04/2026 18:00 - Win Sports
   América vs Junior - 29/04/2026 17:30 - Win Sports+

3. Envía el email y ejecuta:
   python manage.py importar_desde_email

── REGLAS DE FORMATO ────────────────────────────────────────────────────────
- Una línea por partido: Local vs Visitante - Fecha - Hora - Canal1, Canal2
- La fecha puede ser DD/MM/YYYY, DD/MM o YYYY-MM-DD
- La hora debe ser HH:MM (24h) o HH:MM AM/PM
- Los separadores pueden ser " - ", " | " o espacios
- La liga es la última línea de solo texto antes del grupo de partidos
- Los canales al final son opcionales; si no se ponen, se asignan desde el admin
─────────────────────────────────────────────────────────────────────────────

REQUISITO: En Gmail activa el acceso IMAP (Configuración → Ver toda la conf.
→ Reenvío e IMAP/POP → Habilitar IMAP) y usa una Contraseña de Aplicación
(myaccount.google.com/apppasswords) en EMAIL_HOST_PASSWORD del settings.py.
"""
import re
import imaplib
import email
from email.header import decode_header
from datetime import datetime, timedelta, date
from zoneinfo import ZoneInfo
from django.conf import settings
from django.core.management.base import BaseCommand
from canales.models import Partido, Canal, Liga

COL_TZ = ZoneInfo('America/Bogota')
IMAP_HOST = 'imap.gmail.com'
ASUNTO_CLAVE = 'partidos'   # El asunto del email debe contener esta palabra (sin mayúsculas)

PALABRAS_IGNORAR = {'de', 'del', 'la', 'las', 'los', 'the', 'a', 'en', 'el', 'y'}


# ── Helpers de matching de ligas y canales ──────────────────────────────────

def _construir_filtro(ligas_db):
    filtros = []
    for liga in ligas_db:
        nombre = liga.nombre.lower().strip()
        sin_espacios = re.sub(r'\s+', '', nombre)
        palabras = {p for p in nombre.split() if len(p) > 4 and p not in PALABRAS_IGNORAR}
        filtros.append((nombre, sin_espacios, palabras, liga))
    return filtros


def _buscar_liga(texto, filtros):
    """Devuelve el nombre de la Liga de DB más parecido al texto, o el texto tal cual."""
    t = texto.lower().strip()
    t_norm = re.sub(r'\s+', '', t)
    for nombre, sin_espacios, palabras, liga in filtros:
        if nombre in t or t in nombre:
            return liga.nombre
        if sin_espacios and (sin_espacios in t_norm or t_norm in sin_espacios):
            return liga.nombre
        if any(p in t for p in palabras):
            return liga.nombre
    return texto.strip()   # Si no hay match, usar el texto tal cual


def _mapear_canales(nombres_raw, canales_db):
    """Cruza nombres de canales del email con Canal objetos en DB."""
    encontrados = []
    vistos = set()
    for nombre in nombres_raw:
        nombre_lower = nombre.lower().strip()
        if not nombre_lower:
            continue
        # Exact match
        canal = canales_db.get(nombre_lower)
        if not canal:
            # Partial match
            for clave, c in canales_db.items():
                if clave in nombre_lower or nombre_lower in clave:
                    canal = c
                    break
        if canal and canal.pk not in vistos:
            encontrados.append(canal)
            vistos.add(canal.pk)
    return encontrados


# ── Parser de cuerpo de email ───────────────────────────────────────────────

def _parsear_cuerpo(texto, filtros_liga):
    """
    Extrae lista de dicts con claves:
    liga, local, visitante, fecha, hora, canales_texto
    """
    hoy = datetime.now(tz=COL_TZ).date()
    lineas = [l.strip() for l in texto.splitlines() if l.strip()]

    partidos = []
    liga_actual = 'Sin liga'

    for i, linea in enumerate(lineas):
        # ── Detectar partido ──────────────────────────────────────────────
        m = re.search(r'(.+?)\s+vs\s+(.+)', linea, re.IGNORECASE)
        if not m:
            # Esta línea no es un partido → candidata a nombre de liga
            if (not re.search(r'\d{1,2}:\d{2}', linea)
                    and len(linea) > 4 and len(linea) < 80):
                liga_actual = _buscar_liga(linea, filtros_liga)
            continue

        local_y_resto = m.group(1).strip()
        visitante_y_resto = m.group(2).strip()

        # Separar visitante del resto (fecha, hora, canales)
        # El visitante termina donde empieza una fecha o un separador " - "
        partes = re.split(
            r'\s*[-–|]\s*|\s{2,}',
            visitante_y_resto,
            maxsplit=3
        )
        visitante = partes[0].strip()
        resto = partes[1:]   # [fecha?, hora?, canales?] u otras combinaciones

        if not local_y_resto or not visitante:
            continue

        # ── Extraer fecha ─────────────────────────────────────────────────
        fecha_obj = hoy
        texto_resto = ' '.join(resto)

        # Formatos soportados: DD/MM/YYYY, DD/MM, YYYY-MM-DD, DD-MM-YYYY
        fecha_match = (
            re.search(r'(\d{1,2})[/\-](\d{1,2})[/\-](\d{4})', texto_resto)
            or re.search(r'(\d{4})[/\-](\d{1,2})[/\-](\d{1,2})', texto_resto)
            or re.search(r'(\d{1,2})[/\-](\d{1,2})(?!\d)', texto_resto)
        )
        if fecha_match:
            grupos = fecha_match.groups()
            try:
                if len(grupos) == 3 and len(grupos[0]) == 4:
                    # YYYY-MM-DD
                    fecha_obj = date(int(grupos[0]), int(grupos[1]), int(grupos[2]))
                elif len(grupos) == 3:
                    # DD/MM/YYYY
                    fecha_obj = date(int(grupos[2]), int(grupos[1]), int(grupos[0]))
                else:
                    # DD/MM → año actual o siguiente
                    dia, mes = int(grupos[0]), int(grupos[1])
                    anio = hoy.year
                    candidato = date(anio, mes, dia)
                    if candidato < hoy:
                        candidato = date(anio + 1, mes, dia)
                    fecha_obj = candidato
            except ValueError:
                fecha_obj = hoy

        # ── Extraer hora ──────────────────────────────────────────────────
        hora_obj = None
        hora_match = re.search(r'(\d{1,2}):(\d{2})\s*(AM|PM|am|pm)?', texto_resto)
        if hora_match:
            h, m_min = int(hora_match.group(1)), int(hora_match.group(2))
            ampm = (hora_match.group(3) or '').upper()
            if ampm == 'PM' and h < 12:
                h += 12
            elif ampm == 'AM' and h == 12:
                h = 0
            try:
                hora_obj = datetime(2000, 1, 1, h, m_min).time()
            except ValueError:
                hora_obj = None

        # ── Extraer canales ───────────────────────────────────────────────
        canales_texto = []
        # Los canales van al final, después de la hora y la fecha
        texto_sin_fecha_hora = texto_resto
        if fecha_match:
            texto_sin_fecha_hora = texto_sin_fecha_hora[fecha_match.end():]
        if hora_match:
            texto_sin_fecha_hora = re.sub(
                r'\d{1,2}:\d{2}\s*(AM|PM|am|pm)?', '', texto_sin_fecha_hora
            )
        texto_sin_fecha_hora = re.sub(r'^[\s\-–|]+', '', texto_sin_fecha_hora).strip()
        if texto_sin_fecha_hora:
            canales_texto = [c.strip() for c in re.split(r',\s*|;\s*', texto_sin_fecha_hora) if c.strip()]

        partidos.append({
            'liga': liga_actual,
            'local': local_y_resto,
            'visitante': visitante,
            'fecha': fecha_obj,
            'hora': hora_obj,
            'canales_texto': canales_texto,
        })

    return partidos


# ── Leer emails desde Gmail IMAP ────────────────────────────────────────────

def _leer_emails_gmail(usuario, password, asunto_clave, solo_no_leidos=True):
    """
    Conecta a Gmail por IMAP y devuelve lista de (uid, texto_cuerpo).
    Marca los emails leídos como 'Seen' después de procesarlos.
    """
    resultados = []
    try:
        mail = imaplib.IMAP4_SSL(IMAP_HOST)
        mail.login(usuario, password)
        mail.select('INBOX')

        criterio = f'({"UNSEEN " if solo_no_leidos else ""}SUBJECT "{asunto_clave}")'
        status, data = mail.search(None, criterio)
        if status != 'OK' or not data[0]:
            return resultados, mail

        ids = data[0].split()
        for uid in ids:
            status, msg_data = mail.fetch(uid, '(RFC822)')
            if status != 'OK':
                continue

            raw = msg_data[0][1]
            msg = email.message_from_bytes(raw)

            # Decodificar asunto
            asunto_raw = msg.get('Subject', '')
            partes = decode_header(asunto_raw)
            asunto = ''.join(
                p.decode(enc or 'utf-8') if isinstance(p, bytes) else p
                for p, enc in partes
            )

            # Extraer cuerpo plain text
            cuerpo = ''
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == 'text/plain':
                        charset = part.get_content_charset() or 'utf-8'
                        try:
                            cuerpo = part.get_payload(decode=True).decode(charset, errors='replace')
                        except Exception:
                            cuerpo = part.get_payload(decode=True).decode('utf-8', errors='replace')
                        break
            else:
                charset = msg.get_content_charset() or 'utf-8'
                cuerpo = msg.get_payload(decode=True).decode(charset, errors='replace')

            resultados.append((uid, asunto, cuerpo))

        return resultados, mail

    except imaplib.IMAP4.error as e:
        raise RuntimeError(f'Error IMAP: {e}')


# ── Comando Django ───────────────────────────────────────────────────────────

class Command(BaseCommand):
    help = (
        'Importa partidos desde un email enviado a tu cuenta de Gmail.\n'
        'Asunto del email: "Partidos"\n'
        'Ejecuta con --ayuda para ver el formato completo.'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--solo-vista', action='store_true',
            help='Muestra los partidos del email sin guardar en la base de datos',
        )
        parser.add_argument(
            '--todos', action='store_true',
            help='Procesa también emails ya leídos (por defecto solo no leídos)',
        )
        parser.add_argument(
            '--borrar-viejos', action='store_true',
            help='Borra partidos anteriores a ayer antes de importar',
        )
        parser.add_argument(
            '--ayuda', action='store_true',
            help='Muestra el formato de email aceptado',
        )

    def handle(self, *args, **options):
        if options['ayuda']:
            self.stdout.write(__doc__)
            return

        usuario = settings.EMAIL_HOST_USER
        password = getattr(settings, 'EMAIL_HOST_PASSWORD', '')

        if not usuario or not password or 'contraseña' in password.lower():
            self.stdout.write(self.style.ERROR(
                'Configura EMAIL_HOST_USER y EMAIL_HOST_PASSWORD en settings.py\n'
                'Necesitas una Contraseña de Aplicación de Google:\n'
                'myaccount.google.com/apppasswords'
            ))
            return

        solo_vista = options['solo_vista']
        solo_no_leidos = not options['todos']

        # Cargar ligas y canales de DB
        ligas_db = list(Liga.objects.filter(activa=True))
        filtros_liga = _construir_filtro(ligas_db)
        canales_db = {c.nombre.lower(): c for c in Canal.objects.filter(activo=True)}

        self.stdout.write(f'Ligas activas: {len(ligas_db)} | Canales activos: {len(canales_db)}')
        self.stdout.write(f'Conectando a Gmail ({usuario})...')

        try:
            emails, mail_conn = _leer_emails_gmail(
                usuario, password, ASUNTO_CLAVE, solo_no_leidos
            )
        except RuntimeError as e:
            self.stdout.write(self.style.ERROR(str(e)))
            return

        if not emails:
            self.stdout.write(self.style.WARNING(
                f'No hay emails {"no leídos " if solo_no_leidos else ""}con asunto "{ASUNTO_CLAVE}".\n'
                'Envíate un email con asunto "Partidos" y el listado de partidos en el cuerpo.'
            ))
            return

        self.stdout.write(f'{len(emails)} email(s) encontrados.')

        if options['borrar_viejos'] and not solo_vista:
            ayer = (datetime.now(tz=COL_TZ) - timedelta(days=1)).date()
            borrados = Partido.objects.filter(fecha__lt=ayer).delete()[0]
            if borrados:
                self.stdout.write(f'Partidos viejos borrados: {borrados}')

        total_creados = total_actualizados = 0
        ids_procesados = []

        for uid, asunto, cuerpo in emails:
            self.stdout.write(f'\n── Email: "{asunto}" ──')
            partidos_email = _parsear_cuerpo(cuerpo, filtros_liga)

            if not partidos_email:
                self.stdout.write(self.style.WARNING('  No se encontraron partidos en este email.'))
                continue

            self.stdout.write(f'  {len(partidos_email)} partido(s) encontrados:')

            for p in partidos_email:
                canales_obj = _mapear_canales(p['canales_texto'], canales_db)
                canal_str = ', '.join(c.nombre for c in canales_obj) or '(sin canal — asignar en admin)'
                hora_str = p['hora'].strftime('%H:%M') if p['hora'] else '??:??'

                self.stdout.write(
                    f'  {"[VISTA] " if solo_vista else ""}'
                    f'[{p["liga"]}]  {p["local"]} vs {p["visitante"]}  '
                    f'{p["fecha"].strftime("%d/%m/%Y")} {hora_str}  →  {canal_str}'
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
                            'estado': 'NS',
                            'goles_local': None,
                            'goles_visitante': None,
                            'minuto': None,
                        }
                    )
                    if canales_obj:
                        partido.canales.set(canales_obj)

                    if created:
                        total_creados += 1
                    else:
                        total_actualizados += 1

            ids_procesados.append(uid)

        # Marcar emails como leídos
        if not solo_vista and ids_procesados:
            for uid in ids_procesados:
                mail_conn.store(uid, '+FLAGS', '\\Seen')
            self.stdout.write(f'\n{len(ids_procesados)} email(s) marcados como leídos.')

        try:
            mail_conn.logout()
        except Exception:
            pass

        if solo_vista:
            self.stdout.write(self.style.SUCCESS('\n[SOLO VISTA] Nada guardado.'))
        else:
            self.stdout.write(self.style.SUCCESS(
                f'\nListo. Creados: {total_creados} | Actualizados: {total_actualizados}'
            ))
            if total_creados or total_actualizados:
                self.stdout.write('Ve al admin → Partidos para revisar y ajustar canales.')
