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

USERS = [
    # username, first, last, title, perms, skills, certs
    ('direktor', 'Deniz', 'Aksoy', 'Siber Güvenlik Direktörü', [p[0] for p in PERMISSIONS], [], []),
    ('yonetici', 'Selin', 'Kaya', 'SOC Manager', [p[0] for p in PERMISSIONS],
     ['Incident Response', 'Risk Yönetimi'], ['CISSP', 'CISM']),
    ('mert', 'Mert', 'Demir', 'SOC Analyst L2', [PermissionType.DATA_ACCESS],
     ['SIEM', 'Splunk', 'Threat Hunting'], ['CySA+']),
    ('alper', 'Alper', 'Çalbırlık', 'Penetration Tester', [PermissionType.TASK_MANAGEMENT],
     ['Web App Pentest', 'Burp Suite', 'Python'], ['OSCP', 'eWPTX']),
    ('berkay', 'Berkay', 'Yıldız', 'Malware Analyst', [PermissionType.REPORT_ANALYSIS],
     ['Reverse Engineering', 'IDA Pro', 'YARA'], ['GREM']),
    ('aykun', 'Aykun', 'Arslan', 'Cloud Security Engineer', [PermissionType.ACTIVITY_MANAGEMENT],
     ['AWS Security', 'Kubernetes', 'Terraform'], ['CCSP', 'AWS Security Specialty']),
]

TASKS = [
    ('Phishing kampanyası analizi', 'Finans birimine gelen şüpheli e-postaların IOC çıkarımı.',
     Task.SEVERITY_CRITICAL, Task.STATUS_IN_PROGRESS, ['mert', 'berkay']),
    ('CVE-2026-1123 yama takibi', 'Edge cihazlarda kritik RCE açığı için yama doğrulaması.',
     Task.SEVERITY_HIGH, Task.STATUS_OPEN, ['aykun']),
    ('Web uygulaması sızma testi', 'Müşteri portalı için OWASP Top 10 kapsamında test.',
     Task.SEVERITY_HIGH, Task.STATUS_IN_PROGRESS, ['alper']),
    ('SIEM korelasyon kuralları', 'Brute-force ve impossible travel kurallarının iyileştirilmesi.',
     Task.SEVERITY_MEDIUM, Task.STATUS_OPEN, ['mert']),
    ('Ransomware örneği tersine mühendislik', 'Karantinadaki örneğin C2 adreslerinin çıkarılması.',
     Task.SEVERITY_CRITICAL, Task.STATUS_OPEN, ['berkay']),
    ('S3 bucket erişim denetimi', 'Public erişime açık bucket taraması.',
     Task.SEVERITY_MEDIUM, Task.STATUS_DONE, ['aykun']),
    ('Firewall kural temizliği', 'Kullanılmayan any-any kuralların kaldırılması.',
     Task.SEVERITY_LOW, Task.STATUS_DONE, ['mert', 'alper']),
    ('Güvenlik farkındalık eğitimi içeriği', 'Q4 eğitim modüllerinin hazırlanması.',
     Task.SEVERITY_LOW, Task.STATUS_OPEN, ['yonetici']),
    ('API rate-limit bypass bulgusu', 'Pentest bulgusunun raporlanması ve retest.',
     Task.SEVERITY_HIGH, Task.STATUS_DONE, ['alper']),
    ('EDR ajan kapsama raporu', 'Ajanı olmayan uç noktaların tespiti.',
     Task.SEVERITY_MEDIUM, Task.STATUS_IN_PROGRESS, ['yonetici', 'aykun']),
]

ACTIVITIES = [
    ('CTF Takım Antrenmanı', 'Haftalık CTF çalışması — web & pwn kategorileri.', 2, 'Lab-3',
     ['mert', 'alper', 'berkay', 'aykun']),
    ('Tehdit İstihbaratı Brifingi', 'Haftalık APT aktiviteleri değerlendirmesi.', 4, 'Toplantı Odası A',
     ['yonetici', 'mert', 'berkay']),
    ('Red Team vs Blue Team Tatbikatı', 'Purple team senaryosu ile tatbikat.', 9, 'SOC',
     ['yonetici', 'mert', 'alper', 'berkay', 'aykun']),
    ('Bulut Güvenliği Workshop', 'AWS IAM misconfiguration örnekleri.', 14, 'Online',
     ['aykun', 'alper']),
    ('Olay Müdahale Retrospektifi', 'Geçen ayki olayın lessons-learned toplantısı.', -5, 'SOC',
     ['yonetici', 'mert']),
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
        for username, first, last, title, perm_codes, skills, certs in USERS:
            user, created = User.objects.get_or_create(username=username, defaults={
                'first_name': first, 'last_name': last, 'title': title,
                'department': 'Siber Güvenlik Operasyonları',
                'email': f'{username}@cyberops.local', 'phone': '+90 555 000 00 00',
                'location': 'İstanbul',
            })
            if created:
                user.set_password(DEMO_PASSWORD)
                user.save()
            users[username] = user
            for code in perm_codes:
                UserPermission.objects.get_or_create(user=user, permission_type=perms[code])
            for s in skills:
                UserSkill.objects.get_or_create(user=user, skill_name=s, kind=UserSkill.SKILL)
            for c in certs:
                UserSkill.objects.get_or_create(user=user, skill_name=c, kind=UserSkill.CERTIFICATE)

        manager = users['yonetici']
        for u in ('mert', 'alper', 'berkay', 'aykun'):
            users[u].manager = manager
            users[u].save(update_fields=['manager'])

        if not User.objects.filter(username='admin').exists():
            User.objects.create_superuser('admin', 'admin@cyberops.local', DEMO_PASSWORD,
                                          first_name='Sistem', last_name='Admin', title='Administrator')

        if not Task.objects.exists():
            for title, desc, sev, status, assignees in TASKS:
                task = services.create_task(
                    user=manager, title=title, description=desc, severity=sev,
                    status=Task.STATUS_OPEN, assignees=[users[a] for a in assignees])
                if status != Task.STATUS_OPEN:
                    actor = users[assignees[0]]
                    if status == Task.STATUS_DONE:
                        services.update_task(task, user=actor, status=Task.STATUS_IN_PROGRESS)
                    services.update_task(task, user=actor, status=status)

        if not Activity.objects.exists():
            now = timezone.now().replace(minute=0, second=0, microsecond=0)
            for name, desc, days, loc, attendees in ACTIVITIES:
                a = Activity.objects.create(
                    activity_name=name, activity_description=desc, location=loc,
                    activity_date=now + timedelta(days=days, hours=2), created_by=manager)
                a.attendees.set([users[x] for x in attendees])

        self.stdout.write(self.style.SUCCESS(
            f'Seed OK. Users: admin, {", ".join(users)} | password: {DEMO_PASSWORD}'))
