"""
E-posta bildirimleri (mailTemplate.msg şablonu → templates/emails/notification.html).

- Task'a atanan kullanıcıya ve etkinliğe davet edilen kullanıcıya mail gönderilir.
- Alıcı adresi, LDAP girişinde `user.email` alanına yazılan adrestir.
- İşlemi yapan kişi kendini atadıysa ona da mail gider (MAIL_NOTIFY_SELF=0 ile kapatılabilir).
- Mailler DB işlemi commit edildikten sonra arka planda gönderilir; SMTP hatası isteği bozmaz.
"""
import logging
import threading

from django.conf import settings
from django.core.mail import EmailMultiAlternatives
from django.db import transaction
from django.template.loader import render_to_string
from django.urls import reverse
from django.utils import timezone
from django.utils.formats import date_format
from django.utils.text import Truncator

logger = logging.getLogger(__name__)


def _absolute(path):
    return settings.PORTAL_BASE_URL.rstrip('/') + path


def _base_context():
    return {
        'brand_name': settings.MAIL_BRAND_NAME,
        'brand_tagline': settings.MAIL_BRAND_TAGLINE,
        'footer_owner': settings.MAIL_FOOTER_OWNER,
        'footer_note': 'Bu e-posta Operasyon Portalı tarafından otomatik olarak gönderilmiştir. Lütfen yanıtlamayın.',
        'year': timezone.localtime().year,
        'details_title': 'Detaylar',
        'info_title': 'Bilgilendirme',
    }


def _allowed(email):
    domains = settings.MAIL_ALLOWED_DOMAINS
    return not domains or email.rsplit('@', 1)[-1].lower() in domains


def _recipients(users, actor):
    result = []
    for user in users:
        if actor is not None and user.pk == actor.pk and not settings.MAIL_NOTIFY_SELF:
            logger.info('Mail skipped: %s is the actor (MAIL_NOTIFY_SELF=0)', user.username)
            continue
        email = (user.email or '').strip()
        if not email:
            logger.warning('Mail skipped: %s has no email address', user.username)
            continue
        if not _allowed(email):
            logger.warning('Mail skipped: %s domain not allowed (%s)', user.username, email)
            continue
        result.append(user)
    return result


def _build_message(subject, to, context):
    ctx = {**_base_context(), **context}
    recipients = [settings.MAIL_TEST_RECIPIENT] if settings.MAIL_TEST_RECIPIENT else [to]
    if settings.MAIL_TEST_RECIPIENT:
        subject = f'[TEST: {to}] {subject}'
    msg = EmailMultiAlternatives(
        subject=' '.join(subject.split())[:200],
        body=render_to_string('emails/notification.txt', ctx),
        from_email=settings.DEFAULT_FROM_EMAIL,
        to=recipients,
    )
    msg.attach_alternative(render_to_string('emails/notification.html', ctx), 'text/html')
    return msg


def _send_all(messages):
    for msg in messages:
        try:
            msg.send(fail_silently=False)
            logger.info('Mail sent: to=%s subject=%s', msg.to, msg.subject)
        except Exception:
            logger.exception('Mail could not be sent: to=%s subject=%s', msg.to, msg.subject)


def _dispatch(messages):
    if not messages:
        return
    if settings.MAIL_ASYNC:
        transaction.on_commit(lambda: threading.Thread(target=_send_all, args=(messages,), daemon=True).start())
    else:
        transaction.on_commit(lambda: _send_all(messages))


def _first_name(user):
    return user.first_name.title() if user.first_name else user.username


# --------------------------------------------------------------------------- public API

def notify_task_assigned(task, users, actor):
    """Task'a yeni atanan kullanıcılara bildirim gönderir."""
    if not settings.MAIL_ENABLED:
        return
    actor_name = actor.display_name if actor else 'Sistem'
    details = [
        ('Task', f'{task.code} · {task.task_title}'),
        ('Önem derecesi', task.get_task_severity_display()),
        ('Durum', task.get_task_status_display()),
        ('Atayan', actor_name),
        ('Atanma zamanı', date_format(timezone.localtime(), 'j F Y, H:i')),
    ]
    if task.task_description:
        details.append(('Açıklama', Truncator(task.task_description).chars(400)))

    messages = []
    for user in _recipients(users, actor):
        messages.append(_build_message(
            subject=f'Size yeni bir task atandı: {task.task_title}',
            to=user.email,
            context={
                'eyebrow': 'TASK ATAMASI',
                'title': task.task_title,
                'greeting': f'Merhaba {_first_name(user)},',
                'intro': f'{actor_name} size Operasyon Portalı üzerinden yeni bir task atadı. '
                         'Taskın detayları aşağıdadır.',
                'details': details,
                'cta_url': _absolute(reverse('task_detail', args=[task.pk])),
                'cta_label': 'Taskı görüntüle',
                'info_text': 'Taskın durumunu portaldaki İşlerim panosunda kartı sürükleyerek güncelleyebilirsiniz.',
            },
        ))
    _dispatch(messages)


def notify_activity_invited(activity, users, actor):
    """Etkinliğe davet edilen kullanıcılara bildirim gönderir."""
    if not settings.MAIL_ENABLED:
        return
    actor_name = actor.display_name if actor else 'Sistem'
    when = timezone.localtime(activity.activity_date)
    details = [
        ('Etkinlik', activity.activity_name),
        ('Tarih', date_format(when, 'j F Y, l')),
        ('Saat', date_format(when, 'H:i')),
        ('Lokasyon', activity.location or 'Belirtilmedi'),
        ('Düzenleyen', actor_name),
    ]
    if activity.activity_description:
        details.append(('Açıklama', Truncator(activity.activity_description).chars(400)))

    messages = []
    for user in _recipients(users, actor):
        messages.append(_build_message(
            subject=f'Etkinlik daveti: {activity.activity_name}',
            to=user.email,
            context={
                'eyebrow': 'ETKİNLİK DAVETİ',
                'title': activity.activity_name,
                'greeting': f'Merhaba {_first_name(user)},',
                'intro': f'{actor_name} sizi bir etkinliğe davet etti. Etkinlik bilgileri aşağıdadır.',
                'details': details,
                'cta_url': _absolute(reverse('activity_list') + f'#activity-{activity.pk}'),
                'cta_label': 'Etkinliği görüntüle',
                'info_text': 'Katılamayacaksanız portaldaki Etkinlikler sayfasından katılımınızı iptal edebilirsiniz.',
            },
        ))
    _dispatch(messages)
