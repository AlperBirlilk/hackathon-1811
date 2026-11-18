from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from core import notifications
from core.models import Activity, Task, User


class Command(BaseCommand):
    help = ('Ornek bir task atama mailini kullaniciya gonderir (SMTP ve sablon testi). '
            'Ornek: python manage.py send_test_mail tcalbirlik [--activity]')

    def add_arguments(self, parser):
        parser.add_argument('username')
        parser.add_argument('--activity', action='store_true', help='Etkinlik daveti ornegi gonder')

    def handle(self, username, **opts):
        user = User.objects.filter(username=username).first()
        if not user:
            raise CommandError(f'"{username}" bulunamadi.')
        if not user.email:
            raise CommandError(f'"{username}" icin e-posta yok. Kullanici once LDAP ile giris yapmali.')

        # Senkron gonder ki hata varsa burada gorulsun
        settings.MAIL_ASYNC = False
        if opts['activity']:
            item = Activity.objects.order_by('-activity_date').first()
            if not item:
                raise CommandError('Ornek icin en az bir etkinlik olmali (seed calistirin).')
            notifications.notify_activity_invited(item, [user], actor=None)
        else:
            item = Task.objects.order_by('-id').first()
            if not item:
                raise CommandError('Ornek icin en az bir task olmali (seed calistirin).')
            notifications.notify_task_assigned(item, [user], actor=None)
        self.stdout.write(f'Gonderim denendi: {user.email} (from: {settings.DEFAULT_FROM_EMAIL}). '
                          'Sonuc icin yukaridaki "Mail sent" / "could not be sent" log satirina bakin.')
