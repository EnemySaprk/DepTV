import requests
from bs4 import BeautifulSoup

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
}

# Analizar bolaloca
print('=== BOLALOCA ===')
with open('bolaloca_my.html', 'r', encoding='utf-8') as f:
    soup = BeautifulSoup(f.read(), 'html.parser')

# Buscar tablas, divs con partidos
tables = soup.find_all('table')
print(f'Tablas encontradas: {len(tables)}')
for i, table in enumerate(tables):
    rows = table.find_all('tr')
    print(f'\nTabla {i} ({len(rows)} filas):')
    for row in rows[:10]:
        cells = row.find_all(['td', 'th'])
        texto = ' | '.join(c.get_text(strip=True) for c in cells)
        if texto.strip():
            print(f'  {texto}')

# Buscar divs con clase que contenga "match" o "event" o "partido"
print('\n--- Divs relevantes ---')
for div in soup.find_all(['div', 'section'], class_=True):
    clases = ' '.join(div.get('class', []))
    if any(k in clases.lower() for k in ['match', 'event', 'game', 'fixture', 'agenda', 'schedule', 'partido']):
        print(f'  div.{clases}: {div.get_text(strip=True)[:150]}')

# Mostrar todo el texto
print('\n--- TEXTO COMPLETO (primeros 3000 chars) ---')
print(soup.get_text(separator='\n', strip=True)[:3000])
