from django import template

register = template.Library()

LABELS = {
    'status': {'OPEN': 'Açık', 'IN_PROGRESS': 'Devam Ediyor', 'DONE': 'Tamamlandı'},
    'severity': {'LOW': 'Düşük', 'MEDIUM': 'Orta', 'HIGH': 'Yüksek', 'CRITICAL': 'Kritik'},
    'activity_type': {'TRAINING': 'Eğitim', 'CONFERENCE': 'Konferans', 'OTHER': 'Diğer'},
    'participation': {'INDIVIDUAL': 'Bireysel', 'CORPORATE': 'Kurumsal'},
    'skill_kind': {'SKILL': 'Yetenek', 'CERTIFICATE': 'Sertifika'},
    'perm': {
        'TASK_MANAGEMENT': 'Task Yönetimi', 'ACTIVITY_MANAGEMENT': 'Etkinlik Yönetimi',
        'ROLE_MANAGEMENT': 'Rol Yönetimi', 'REPORT_ANALYSIS': 'Rapor ve Analiz',
        'DATA_ACCESS': 'Veri Erişimi',
    },
}

STATUS_CHOICES = list(LABELS['status'].items())
SEVERITY_CHOICES = list(LABELS['severity'].items())


@register.filter
def label(value, kind):
    return LABELS.get(kind, {}).get(value, value or '')


@register.filter
def initials(user):
    if not user:
        return '?'
    name = (user.get('displayName') if isinstance(user, dict) else str(user)) or user.get('username', '?')
    return ''.join(p[0] for p in name.split()[:2]).upper() or '?'
