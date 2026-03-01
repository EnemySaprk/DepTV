from django.core.management.base import BaseCommand
from canales.models import CanalBolaloca

CANALES = [
    (1, 'beIN SPORT 1', 'fr'), (2, 'beIN SPORT 2', 'fr'), (3, 'beIN SPORT 3', 'fr'),
    (4, 'beIN SPORT max 4', 'fr'), (5, 'beIN SPORT max 5', 'fr'), (6, 'beIN SPORT max 6', 'fr'),
    (7, 'beIN SPORT max 7', 'fr'), (8, 'beIN SPORT max 8', 'fr'), (9, 'beIN SPORT max 9', 'fr'),
    (10, 'beIN SPORT max 10', 'fr'),
    (11, 'Canal+', 'fr'), (12, 'Canal+ Foot', 'fr'), (13, 'Canal+ Sport', 'fr'),
    (14, 'Canal+ Sport360', 'fr'), (15, 'Eurosport 1', 'fr'), (16, 'Eurosport 2', 'fr'),
    (17, 'RMC Sport 1', 'fr'), (18, 'Ligue 1 FR 6', 'fr'), (19, 'Equipe', 'fr'),
    (20, 'Ligue 1 FR 1', 'fr'), (21, 'Ligue 1 FR 4', 'fr'), (22, 'Ligue 1 FR 5', 'fr'),
    (49, 'M. LaLiga', 'es'), (50, 'M. LaLiga 2', 'es'),
    (51, 'DAZN Liga', 'es'), (52, 'DAZN Liga 2', 'es'),
    (68, 'TUDN USA', 'us'), (69, 'beIN En Espanol', 'us'),
    (70, 'FOX Deportes', 'us'), (71, 'ESPN Deportes', 'us'),
    (72, 'NBC Universo', 'us'), (73, 'Telemundo', 'us'),
    (75, 'TNT Sport ARG', 'ar'), (76, 'ESPN Premium', 'ar'), (77, 'TyC Sports', 'ar'),
    (78, 'FOX Sport 1 ARG', 'ar'), (79, 'FOX Sport 2 ARG', 'ar'), (80, 'FOX Sport 3 ARG', 'ar'),
    (81, 'Win Sport+', 'co'), (82, 'Win Sport', 'co'),
    (83, 'TNT Chile Premium', 'cl'), (84, 'Liga 1 MAX', 'pe'), (85, 'GolPeru', 'pe'),
    (87, 'ESPN 1', 'lat'), (88, 'ESPN 2', 'lat'), (89, 'ESPN 3', 'lat'),
    (90, 'ESPN 4', 'lat'), (91, 'ESPN 5', 'lat'), (92, 'ESPN 6', 'lat'), (93, 'ESPN 7', 'lat'),
    (94, 'DirecTV', 'lat'), (95, 'DirecTV 2', 'lat'), (96, 'DirecTV+', 'lat'),
    (97, 'ESPN 1 MX', 'mx'), (98, 'ESPN 2 MX', 'mx'), (99, 'ESPN 3 MX', 'mx'), (100, 'ESPN 4 MX', 'mx'),
    (101, 'FOX Sport 1 MX', 'mx'), (102, 'FOX Sport 2 MX', 'mx'), (103, 'FOX Sport 3 MX', 'mx'),
    (104, 'FOX Sports Premium', 'mx'), (106, 'TUDN MX', 'mx'), (107, 'Canal 5 MX', 'mx'), (108, 'Azteca 7', 'mx'),
    (110, 'Sky Bundesliga 10', 'de'), (111, 'Sky Bundesliga 1', 'de'),
    (112, 'Sky Bundesliga 2', 'de'), (113, 'Sky Bundesliga 3', 'de'),
    (126, 'TNT Sport UK', 'uk'), (127, 'Sky Main UK', 'uk'), (128, 'Sky Football UK', 'uk'),
    (137, 'Zona DAZN IT', 'it'), (138, 'Sky Calcio IT', 'it'),
    (141, 'ESPN 1 NL', 'nl'), (142, 'ESPN 2 NL', 'nl'), (143, 'ESPN 3 NL', 'nl'),
    (144, 'Sport 1 PT', 'pt'), (145, 'Sport 2 PT', 'pt'), (146, 'Sport 3 PT', 'pt'),
]

class Command(BaseCommand):
    help = 'Cargar canales de bolaloca.my'

    def handle(self, *args, **options):
        creados = 0
        for num, nombre, pais in CANALES:
            obj, created = CanalBolaloca.objects.get_or_create(
                numero=num,
                defaults={'nombre': nombre, 'pais': pais}
            )
            if created:
                creados += 1
        self.stdout.write(self.style.SUCCESS(f'Canales creados: {creados}'))
        self.stdout.write(self.style.SUCCESS(f'Total: {CanalBolaloca.objects.count()}'))
