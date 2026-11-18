from django.core.management.base import BaseCommand, CommandError

from core.models import PermissionType, User, UserPermission


class Command(BaseCommand):
    help = ('Kullaniciya DB yetkisi verir/alir. Ornek: '
            'python manage.py grant_perm alper.birlik ROLE_MANAGEMENT TASK_MANAGEMENT  |  --all  |  --revoke')

    def add_arguments(self, parser):
        parser.add_argument('username')
        parser.add_argument('codes', nargs='*', help=', '.join(c for c, _ in PermissionType.CODE_CHOICES))
        parser.add_argument('--all', action='store_true', help='Tum yetkileri ver')
        parser.add_argument('--revoke', action='store_true', help='Verilen yetkileri geri al')

    def handle(self, username, codes, **opts):
        user = User.objects.filter(username=username.lower()).first() or User.objects.filter(username=username).first()
        if not user:
            raise CommandError(f'"{username}" bulunamadi. LDAP kullanicisi once portala bir kez giris yapmali.')
        perms = PermissionType.objects.all() if opts['all'] else PermissionType.objects.filter(code__in=codes)
        unknown = set(codes) - set(perms.values_list('code', flat=True))
        if unknown or not perms:
            raise CommandError(f'Gecersiz/eksik yetki kodu: {", ".join(unknown) or "-"}. Once "seed" calistirin.')
        for p in perms:
            if opts['revoke']:
                UserPermission.objects.filter(user=user, permission_type=p).delete()
            else:
                UserPermission.objects.get_or_create(user=user, permission_type=p)
        now = ', '.join(user.permissions.values_list('code', flat=True)) or '-'
        self.stdout.write(self.style.SUCCESS(f'{user.username}: {now}'))
