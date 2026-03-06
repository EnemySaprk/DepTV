from django.core.management.base import BaseCommand
from canales.models import BannerImagen


class Command(BaseCommand):
    help = 'Redimensionar todos los banners existentes a 1920x600'

    def handle(self, *args, **options):
        banners = BannerImagen.objects.all()
        total = 0
        for banner in banners:
            if banner.imagen:
                try:
                    banner.redimensionar_imagen()
                    total += 1
                    self.stdout.write(self.style.SUCCESS(f'  + {banner}'))
                except Exception as e:
                    self.stdout.write(self.style.ERROR(f'  x {banner}: {e}'))
        self.stdout.write(self.style.SUCCESS(f'\n{total} banners redimensionados'))
