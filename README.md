# DepTV

Plataforma web de streaming deportivo. Permite ver fútbol en vivo con agenda de partidos, canales por liga y soporte para múltiples fuentes de video.

## Tecnologías

- **Backend:** Django 6.0 + Python 3.13
- **Base de datos:** PostgreSQL (producción) / SQLite (desarrollo)
- **Deploy:** Render
- **Archivos estáticos:** WhiteNoise
- **Almacenamiento de media:** Cloudinary

## Características

- Agenda de partidos en vivo con estado (en vivo / finalizado / próximo)
- Canales organizados por liga
- Soporte para YouTube, URL directa (MP4/M3U8) e iFrame
- Múltiples fuentes de video por partido
- Modo claro / oscuro
- PWA (instalable en móvil)
- Panel de administración personalizado
- Sincronización automática de partidos vía API-Football

## Instalación local

```bash
# Clonar el repositorio
git clone https://github.com/EnemySaprk/DepTV.git
cd DepTV

# Crear entorno virtual
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# Instalar dependencias
pip install -r requirements.txt

# Migraciones y servidor
python manage.py migrate
python manage.py runserver
```

## Variables de entorno

Crea un archivo `.env` en la raíz con:

```env
SECRET_KEY=tu-secret-key
DEBUG=True
DATABASE_URL=           # Solo en producción
```

## Comandos de gestión

```bash
# Sincronizar agenda de partidos desde API-Football
python manage.py sincronizar_agenda

# Sincronizar partidos
python manage.py sincronizar_partidos

# Cargar canales bolaloca
python manage.py cargar_canales_bolaloca
```

## Deploy en Render

El archivo `render.yaml` contiene la configuración lista para desplegar en [Render](https://render.com). El script `build.sh` instala dependencias, recolecta estáticos y aplica migraciones automáticamente.
