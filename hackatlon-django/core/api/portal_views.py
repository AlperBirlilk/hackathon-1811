"""Veri Paylaşımı page: personal API token management for the MCP server (DATA_ACCESS)."""
import json

from django.conf import settings
from django.contrib import messages
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.cache import never_cache
from django.views.decorators.http import require_GET, require_POST
from rest_framework.authtoken.models import Token

from core.models import PermissionType
from core.views import portal_perm_required

from .auth import token_expires_at, token_is_expired

ENDPOINTS = [
    ('GET', '/api/me', 'Token sahibi, yetkileri', 'Giriş yeterli'),
    ('GET', '/api/users', 'Aktif kullanıcılar', 'DATA_ACCESS'),
    ('GET', '/api/tasks?status=&severity=&q=&assigneeId=&overdue=true', 'Görünür işler (Kritik önce)', 'DATA_ACCESS'),
    ('GET', '/api/tasks/{id}', 'İş detayı ve değişiklik geçmişi', 'DATA_ACCESS'),
    ('GET', '/api/dashboard', 'Pano özeti', 'DATA_ACCESS'),
    ('GET', '/api/team', 'Ekip üyeleri ve iş sayıları', 'DATA_ACCESS + ROLE_MANAGEMENT'),
    ('GET', '/api/activities?scope=upcoming|past|mine', 'Etkinlikler', 'DATA_ACCESS'),
]


def _api_base_url():
    return getattr(settings, 'PORTAL_BASE_URL', 'http://127.0.0.1:8000').rstrip('/')


def _context(request, new_token=None):
    token = Token.objects.filter(user=request.user).first()
    info = None
    if token:
        info = {
            'masked': f'{token.key[:4]}…',
            'created': token.created,
            'expires': token_expires_at(token),
            'expired': token_is_expired(token),
        }
    base = _api_base_url()
    mcp_json = json.dumps({'mcpServers': {'cyberops-portal': {
        'command': 'uv',
        'args': ['run', '--directory', 'mcp', 'server.py'],
        'env': {'PORTAL_API_URL': base, 'PORTAL_API_TOKEN': '${PORTAL_API_TOKEN}'},
    }}}, indent=2)
    return {
        'token_info': info,
        'new_token': new_token,
        'ttl_hours': settings.API_TOKEN_TTL_HOURS,
        'endpoints': ENDPOINTS,
        'api_base_url': base,
        'mcp_json': mcp_json,
    }


@require_GET
@portal_perm_required(PermissionType.DATA_ACCESS)
def data_sharing(request):
    return render(request, 'core/data_sharing.html', _context(request))


@never_cache
@require_POST
@portal_perm_required(PermissionType.DATA_ACCESS)
def api_token_generate(request):
    """Replaces the user's token; the plaintext is rendered once in this response only
    (never stored in messages/session, no redirect)."""
    with transaction.atomic():
        Token.objects.filter(user=request.user).delete()
        token = Token.objects.create(user=request.user)
    response = render(request, 'core/data_sharing.html', _context(request, new_token=token.key))
    response['Cache-Control'] = 'no-store, no-cache, must-revalidate, private, max-age=0'
    return response


@require_POST
@portal_perm_required(PermissionType.DATA_ACCESS)
def api_token_revoke(request):
    deleted, _ = Token.objects.filter(user=request.user).delete()
    if deleted:
        messages.success(request, 'API token silindi. Bu token ile yapılan istekler artık reddedilecek.')
    else:
        messages.info(request, 'Silinecek bir API token bulunmuyor.')
    return redirect('data_sharing')
