from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from core import services
from core.models import Activity, PermissionType, Task, User, UserPermission, UserSkill

DEMO_PASSWORD = 'Cyber2026!'

PERMISSIONS = [
    (PermissionType.TASK_MANAGEMENT, 'Task Management', 'Tüm taskları görme / oluşturma / atama'),
    (PermissionType.ACTIVITY_MANAGEMENT, 'Activity Management', 'Etkinlik oluşturma ve yönetme'),
    (PermissionType.ROLE_MANAGEMENT, 'Role Management', 'Ekip ve yetki yönetimi (Yönetici)'),
    (PermissionType.REPORT_ANALYSIS, 'Report & Analysis', 'Rapor ve analiz panellerine erişim'),
    (PermissionType.DATA_ACCESS, 'Data Access', 'Veri paylaşımı alanına erişim'),
]
ALL_PERMS = [p[0] for p in PERMISSIONS]

USERS = [
    # username, first, last, title, perms, skills, certs, manager, is_on_leave
    ('direktor', 'Kemal', 'Aydın', 'Siber Güvenlik Direktörü', ALL_PERMS,
     ['Güvenlik Stratejisi', 'Bütçe Yönetimi'], ['CISSP', 'CISO'], None, False),
    # yonetici: Data Access hariç tüm yetkiler (direktör = tüm yetkiler)
    ('yonetici', 'Selin', 'Kaya', 'SOC Manager', [c for c in ALL_PERMS if c != PermissionType.DATA_ACCESS],
     ['Incident Response', 'Risk Yönetimi'], ['CISSP', 'CISM'], 'direktor', False),
    ('mert', 'Mert', 'Demir', 'SOC Analyst L2', [PermissionType.DATA_ACCESS],
     ['SIEM', 'Splunk', 'Threat Hunting'], ['CySA+'], 'yonetici', False),
    ('alper', 'Alper', 'Çalbırlık', 'Penetration Tester', [PermissionType.TASK_MANAGEMENT],
     ['Web App Pentest', 'Burp Suite', 'Python'], ['OSCP', 'eWPTX'], 'yonetici', False),
    ('berkay', 'Berkay', 'Yıldız', 'Malware Analyst', [PermissionType.REPORT_ANALYSIS],
     ['Reverse Engineering', 'IDA Pro', 'YARA'], ['GREM'], 'yonetici', False),
    # aykun izinli: yedek sorumlusu olduğu işler "Devralınan işler"de görünür
    ('aykun', 'Aykun', 'Arslan', 'Cloud Security Engineer', [PermissionType.ACTIVITY_MANAGEMENT],
     ['AWS Security', 'Kubernetes', 'Terraform'], ['CCSP', 'AWS Security Specialty'], 'yonetici', True),
]

# title, desc, severity, final status, assignees, backup, due_offset_days (None = SLA, negatif = gecikmiş)
TASKS = [
    ('Phishing kampanyası analizi', 'Finans birimine gelen şüpheli e-postaların IOC çıkarımı.',
     Task.SEVERITY_CRITICAL, Task.STATUS_IN_PROGRESS, ['mert', 'berkay'], 'alper', None),
    ('CVE-2026-1123 yama takibi', 'Edge cihazlarda kritik RCE açığı için yama doğrulaması.',
     Task.SEVERITY_HIGH, Task.STATUS_OPEN, ['aykun'], 'mert', -2),
    ('Web uygulaması sızma testi', 'Müşteri portalı için OWASP Top 10 kapsamında test.',
     Task.SEVERITY_HIGH, Task.STATUS_IN_PROGRESS, ['alper'], None, None),
    ('SIEM korelasyon kuralları', 'Brute-force ve impossible travel kurallarının iyileştirilmesi.',
     Task.SEVERITY_MEDIUM, Task.STATUS_OPEN, ['mert'], 'alper', None),
    ('Ransomware örneği tersine mühendislik', 'Karantinadaki örneğin C2 adreslerinin çıkarılması.',
     Task.SEVERITY_CRITICAL, Task.STATUS_OPEN, ['berkay'], None, -1),
    ('S3 bucket erişim denetimi', 'Public erişime açık bucket taraması.',
     Task.SEVERITY_MEDIUM, Task.STATUS_DONE, ['aykun'], None, None),
    ('Firewall kural temizliği', 'Kullanılmayan any-any kuralların kaldırılması.',
     Task.SEVERITY_LOW, Task.STATUS_DONE, ['mert', 'alper'], None, None),
    ('Güvenlik farkındalık eğitimi içeriği', 'Q4 eğitim modüllerinin hazırlanması.',
     Task.SEVERITY_LOW, Task.STATUS_OPEN, ['yonetici'], None, None),
    ('API rate-limit bypass bulgusu', 'Pentest bulgusunun raporlanması ve retest.',
     Task.SEVERITY_HIGH, Task.STATUS_DONE, ['alper'], None, None),
    ('EDR ajan kapsama raporu', 'Ajanı olmayan uç noktaların tespiti.',
     Task.SEVERITY_MEDIUM, Task.STATUS_IN_PROGRESS, ['yonetici', 'aykun'], 'mert', None),
]

# name, desc, day offset, location, type, participation, contact, attendees
ACTIVITIES = [
    ('CTF Takım Antrenmanı', 'Haftalık CTF çalışması — web & pwn kategorileri.', 2, 'Lab-3',
     Activity.TYPE_TRAINING, Activity.PARTICIPATION_INDIVIDUAL, 'alper', ['mert', 'alper', 'berkay', 'aykun']),
    ('Tehdit İstihbaratı Brifingi', 'Haftalık APT aktiviteleri değerlendirmesi.', 4, 'Toplantı Odası A',
     Activity.TYPE_OTHER, Activity.PARTICIPATION_CORPORATE, 'yonetici', ['yonetici', 'mert', 'berkay']),
    ('Red Team vs Blue Team Tatbikatı', 'Purple team senaryosu ile tatbikat.', 9, 'SOC',
     Activity.TYPE_TRAINING, Activity.PARTICIPATION_CORPORATE, 'yonetici',
     ['yonetici', 'mert', 'alper', 'berkay', 'aykun']),
    ('Bulut Güvenliği Workshop', 'AWS IAM misconfiguration örnekleri.', 14, 'Online',
     Activity.TYPE_TRAINING, Activity.PARTICIPATION_INDIVIDUAL, 'aykun', ['aykun', 'alper']),
    ('OWASP İstanbul Konferansı', 'Uygulama güvenliği konferansı; kurumsal katılım.', 20, 'Haliç Kongre Merkezi',
     Activity.TYPE_CONFERENCE, Activity.PARTICIPATION_CORPORATE, 'berkay', ['alper', 'berkay', 'direktor']),
    ('Olay Müdahale Retrospektifi', 'Geçen ayki olayın lessons-learned toplantısı.', -5, 'SOC',
     Activity.TYPE_OTHER, Activity.PARTICIPATION_CORPORATE, 'yonetici', ['yonetici', 'mert']),
]


class Command(BaseCommand):
    help = 'Demo verilerini (yetki tipleri, kullanıcılar, task, etkinlik) oluşturur.'

    def add_arguments(self, parser):
        parser.add_argument('--reset', action='store_true', help='Mevcut task/etkinlik verisini sil.')

    @transaction.atomic
    def handle(self, *args, **opts):
        if opts['reset']:
            Task.objects.all().delete()
            Activity.objects.all().delete()

        perms = {}
        for code, name, desc in PERMISSIONS:
            perms[code], _ = PermissionType.objects.update_or_create(
                code=code, defaults={'permission_name': name, 'description': desc})

        users = {}
        for username, first, last, title, perm_codes, skills, certs, _mgr, on_leave in USERS:
            user, created = User.objects.get_or_create(username=username, defaults={
                'first_name': first, 'last_name': last, 'title': title,
                'department': 'Siber Güvenlik Operasyonları',
                'email': f'{username}@cyberops.local', 'phone': '+90 555 000 00 00',
                'location': 'İstanbul',
            })
            if created:
                user.set_password(DEMO_PASSWORD)
            user.is_on_leave = on_leave
            user.save()
            users[username] = user
            # Demo kullanıcılarının yetkileri seed'deki tanımla senkron tutulur
            UserPermission.objects.filter(user=user).exclude(permission_type__code__in=perm_codes).delete()
            for code in perm_codes:
                UserPermission.objects.get_or_create(user=user, permission_type=perms[code])
            for s in skills:
                UserSkill.objects.get_or_create(user=user, skill_name=s, kind=UserSkill.SKILL)
            for c in certs:
                UserSkill.objects.get_or_create(user=user, skill_name=c, kind=UserSkill.CERTIFICATE)

        for row in USERS:
            username, manager_username = row[0], row[7]
            users[username].manager = users[manager_username] if manager_username else None
            users[username].save(update_fields=['manager'])

        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@cyberops.local', DEMO_PASSWORD,
                                          first_name='Sistem', last_name='Admin', title='Administrator')

        manager = users['yonetici']
        now = timezone.now().replace(second=0, microsecond=0)
        if not Task.objects.exists():
            for title, desc, sev, status, assignees, backup, due_offset in TASKS:
                due = now + timedelta(days=due_offset) if due_offset is not None else None
                task = services.create_task(
                    user=manager, title=title, description=desc, severity=sev,
                    status=Task.STATUS_OPEN, assignees=[users[a] for a in assignees],
                    due_date=due, backup_assignee=users[backup] if backup else None)
                if status != Task.STATUS_OPEN:
                    actor = users[assignees[0]]
                    if status == Task.STATUS_DONE:
                        services.update_task(task, user=actor, status=Task.STATUS_IN_PROGRESS)
                    services.update_task(task, user=actor, status=status)

        hour = now.replace(minute=0)
        for name, desc, days, loc, a_type, part, contact, attendees in ACTIVITIES:
            fields = {'activity_description': desc, 'location': loc, 'activity_type': a_type,
                      'participation_type': part, 'contact_person': users[contact]}
            activity, created = Activity.objects.update_or_create(
                activity_name=name, defaults=fields,
                create_defaults={**fields, 'created_by': manager,
                                 'activity_date': hour + timedelta(days=days, hours=2)})
            if created:
                activity.attendees.set([users[x] for x in attendees])

        self.stdout.write(self.style.SUCCESS(
            f'Seed OK. Users: admin, {", ".join(users)} | password: {DEMO_PASSWORD}'))
