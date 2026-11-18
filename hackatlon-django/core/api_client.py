"""Java backend'e tek HTTP kapısı.

Session'daki JWT'yi `Authorization: Bearer` olarak ekler, `{"error": {...}}` formatını
`ApiError`'a çevirir. 401 → `ApiUnauthorized` (middleware logout + login'e yönlendirir).
JWT asla loglanmaz veya template'e konmaz.
"""
import logging
from datetime import timedelta

import jwt
import requests
from django.conf import settings
from django.utils import timezone
from django.utils.dateparse import parse_datetime

log = logging.getLogger(__name__)

TIMEOUT = 10
SESSION_JWT = 'portal_jwt'
SESSION_ME = 'portal_me'

# API yanıtlarında datetime'a çevrilen alanlar (template'te |date kullanılabilsin diye)
DATE_KEYS = {'dueDate', 'modifiedDate', 'createDate', 'actionDate', 'date'}


class ApiError(Exception):
    def __init__(self, status, code, message):
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message


class ApiUnauthorized(Exception):
    """401: bilerek ApiError'dan türemez; view'lar yutmasın, middleware logout + login'e yönlendirsin."""

    def __init__(self, status=401, code='UNAUTHORIZED', message=''):
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def _convert_dates(obj):
    if isinstance(obj, list):
        return [_convert_dates(x) for x in obj]
    if isinstance(obj, dict):
        out = {}
        for k, v in obj.items():
            if k in DATE_KEYS and isinstance(v, str):
                out[k] = parse_datetime(v) or v
            else:
                out[k] = _convert_dates(v)
        return out
    return obj


def _raise_for(resp):
    if resp.status_code < 400:
        return
    code, message = 'INTERNAL', 'Beklenmeyen bir hata oluştu.'
    try:
        err = resp.json().get('error') or {}
        code = err.get('code') or code
        message = err.get('message') or message
    except ValueError:
        pass
    if resp.status_code == 401:
        raise ApiUnauthorized(401, 'UNAUTHORIZED', 'Oturumunuzun süresi doldu, lütfen tekrar giriş yapın.')
    if resp.status_code == 404 and code == 'INTERNAL':
        code, message = 'NOT_FOUND', 'Kayıt bulunamadı.'
    if resp.status_code == 403 and code == 'INTERNAL':
        code, message = 'FORBIDDEN', 'Bu işlem için yetkiniz yok.'
    raise ApiError(resp.status_code, code, message)


def _send(method, path, *, headers, params=None, json=None, stream=False):
    if params:
        params = {k: v for k, v in params.items() if v not in (None, '', False)}
    try:
        resp = requests.request(method, f'{settings.PORTAL_API_URL}{path}', headers=headers,
                                params=params, json=json, timeout=TIMEOUT, stream=stream)
    except requests.RequestException:
        log.warning('Backend erişilemedi: %s %s', method, path)
        raise ApiError(503, 'UNAVAILABLE', "Backend'e ulaşılamıyor")
    _raise_for(resp)
    return resp


def _request(request, method, path, *, params=None, json=None, stream=False):
    token = request.session.get(SESSION_JWT)
    if not token:
        raise ApiUnauthorized(401, 'UNAUTHORIZED', 'Oturumunuzun süresi doldu, lütfen tekrar giriş yapın.')
    resp = _send(method, path, headers={'Authorization': f'Bearer {token}', 'Accept': 'application/json'},
                 params=params, json=json, stream=stream)
    if stream:
        return resp
    if resp.status_code == 204 or not resp.content:
        return None
    return _convert_dates(resp.json())


def _get(request, path, **params):
    return _request(request, 'GET', path, params=params)


# --------------------------------------------------------------------------- auth / JWT

def sync_user(user):
    resp = _send('POST', '/internal/users/sync',
                 headers={'X-Service-Key': settings.PORTAL_SERVICE_KEY, 'Accept': 'application/json'},
                 json={
                     'username': user.username, 'firstName': user.first_name, 'lastName': user.last_name,
                     'email': user.email, 'authSource': getattr(user, 'auth_source', None) or 'LOCAL',
                 })
    return resp.json()


def issue_jwt(me, hours=None, days=None):
    lifetime = timedelta(days=days) if days else timedelta(hours=hours or settings.PORTAL_JWT_HOURS)
    now = timezone.now()
    payload = {
        'sub': str(me['id']), 'username': me['username'], 'perms': me.get('permissions', []),
        'iat': int(now.timestamp()), 'exp': int((now + lifetime).timestamp()),
    }
    return jwt.encode(payload, settings.PORTAL_JWT_SECRET, algorithm='HS256')


def login_session(request, user):
    """sync + JWT + session. Backend'e ulaşılamazsa ApiError fırlatır."""
    me = sync_user(user)
    request.session[SESSION_JWT] = issue_jwt(me)
    request.session[SESSION_ME] = me
    return me


def session_me(request):
    return request.session.get(SESSION_ME) or {}


def has_perm(request, code):
    return code in (session_me(request).get('permissions') or [])


# --------------------------------------------------------------------------- users / profile

def get_me(request):
    return _get(request, '/api/me')


def list_users(request):
    return _get(request, '/api/users') or []


def get_profile(request, user_id):
    return _get(request, f'/api/users/{user_id}')


def update_me(request, data):
    return _request(request, 'PATCH', '/api/users/me', json=data)


def list_skills(request, user_id):
    return _get(request, f'/api/users/{user_id}/skills') or []


def add_skill(request, skill_name, kind):
    return _request(request, 'POST', '/api/users/me/skills', json={'skillName': skill_name, 'kind': kind})


def delete_skill(request, skill_id):
    return _request(request, 'DELETE', f'/api/users/me/skills/{skill_id}')


# --------------------------------------------------------------------------- team

def list_team(request):
    return _get(request, '/api/team') or []


def list_team_candidates(request):
    return _get(request, '/api/team/candidates') or []


def add_team_member(request, user_id):
    return _request(request, 'POST', '/api/team/members', json={'userId': user_id})


def remove_team_member(request, user_id):
    return _request(request, 'DELETE', f'/api/team/members/{user_id}')


def get_member_permissions(request, user_id):
    return _get(request, f'/api/team/members/{user_id}/permissions') or []


def set_member_permissions(request, user_id, codes):
    return _request(request, 'PUT', f'/api/team/members/{user_id}/permissions', json={'codes': list(codes)})


# --------------------------------------------------------------------------- tasks

def list_tasks(request, status=None, severity=None, q=None, assignee_id=None, overdue=None):
    return _get(request, '/api/tasks', status=status, severity=severity, q=q,
                assigneeId=assignee_id, overdue='true' if overdue else None) or []


def create_task(request, data):
    return _request(request, 'POST', '/api/tasks', json=data)


def get_task(request, task_id):
    return _get(request, f'/api/tasks/{task_id}')


def update_task(request, task_id, data):
    return _request(request, 'PATCH', f'/api/tasks/{task_id}', json=data)


def set_task_status(request, task_id, status):
    return _request(request, 'POST', f'/api/tasks/{task_id}/status', json={'status': status})


def task_history(request, task_id):
    return _get(request, f'/api/tasks/{task_id}/history') or []


def dashboard(request):
    return _get(request, '/api/dashboard') or {}


# --------------------------------------------------------------------------- activities

def list_activities(request, scope='upcoming'):
    return _get(request, '/api/activities', scope=scope) or []


def create_activity(request, data):
    return _request(request, 'POST', '/api/activities', json=data)


def toggle_join_activity(request, activity_id):
    return _request(request, 'POST', f'/api/activities/{activity_id}/join') or {}


# --------------------------------------------------------------------------- notifications

def list_notifications(request, unread=False):
    return _get(request, '/api/notifications', unread='true' if unread else None) or []


def unread_notification_count(request):
    return (_get(request, '/api/notifications/unread-count') or {}).get('count', 0)


def mark_notification_read(request, notification_id):
    return _request(request, 'POST', f'/api/notifications/{notification_id}/read')


def mark_all_notifications_read(request):
    return _request(request, 'POST', '/api/notifications/read-all')


# --------------------------------------------------------------------------- reports

def stream_task_report(request, fmt, status=None, severity=None, assignee_id=None, overdue=None, q=None):
    """`requests.Response` (stream=True) döner; çağıran içeriği tarayıcıya akıtır ve kapatır."""
    if fmt not in ('xlsx', 'pdf'):
        raise ApiError(400, 'VALIDATION', 'Geçersiz rapor biçimi.')
    params = {'status': status, 'severity': severity, 'assigneeId': assignee_id,
              'overdue': 'true' if overdue else None, 'q': q}
    return _request(request, 'GET', f'/api/reports/tasks.{fmt}', params=params, stream=True)
