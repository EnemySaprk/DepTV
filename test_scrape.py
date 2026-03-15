import requests
from bs4 import BeautifulSoup

# Probar con la agenda de ESPN para Colombia
urls = [
    'https://www.espn.com/soccer/schedule',
    'https://www.espn.com.co/futbol/programacion',
    'https://bolaloca.my',
]

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Accept-Language': 'es-CO,es;q=0.9,en;q=0.8',
}

for url in urls:
    print(f'\n=== {url} ===')
    try:
        response = requests.get(url, headers=headers, timeout=15)
        print(f'Status: {response.status_code}')
        if response.status_code == 200:
            print(f'Tamano: {len(response.text)} caracteres')
            # Guardar
            nombre = url.replace('https://', '').replace('/', '_').replace('.', '_') + '.html'
            with open(nombre, 'w', encoding='utf-8') as f:
                f.write(response.text)
            print(f'Guardado en: {nombre}')
    except Exception as e:
        print(f'Error: {e}')
