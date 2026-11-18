"""Uniform API error body: {"error": {"code": "...", "message": "<Türkçe>"}}."""
import logging

from django.core.exceptions import PermissionDenied as DjangoPermissionDenied
from django.http import Http404
from rest_framework import exceptions, status
from rest_framework.response import Response
from rest_framework.views import set_rollback

from .auth import PortalAuthFailed

logger = logging.getLogger('core.api')

CODES = {
    400: 'VALIDATION',
    401: 'UNAUTHORIZED',
    403: 'FORBIDDEN',
    404: 'NOT_FOUND',
    405: 'METHOD_NOT_ALLOWED',
    406: 'NOT_ACCEPTABLE',
    415: 'UNSUPPORTED_MEDIA_TYPE',
    429: 'THROTTLED',
    500: 'INTERNAL',
}

DEFAULT_MESSAGES = {
    400: 'Geçersiz istek.',
    401: 'Kimlik doğrulaması gerekli (Authorization: Bearer <token>).',
    403: 'Bu işlem için yetkiniz yok.',
    404: 'Kayıt bulunamadı veya görüntüleme yetkiniz yok.',
    405: 'Bu metot desteklenmiyor; API salt okunurdur (yalnızca GET).',
    406: 'İstenen yanıt biçimi desteklenmiyor (yalnızca JSON).',
    415: 'Desteklenmeyen içerik türü.',
    429: 'Çok fazla istek. Lütfen daha sonra tekrar deneyin.',
    500: 'Beklenmeyen bir sunucu hatası oluştu.',
}


class ApiValidationError(exceptions.ValidationError):
    """400 with a ready-made Turkish message (shown verbatim)."""

    def __init__(self, message):
        super().__init__(message)
        self.message = message


def error_response(status_code, message=None, headers=None):
    body = {'error': {'code': CODES.get(status_code, 'ERROR'),
                      'message': message or DEFAULT_MESSAGES.get(status_code, 'Hata.')}}
    return Response(body, status=status_code, headers=headers)


def _message_for(exc, status_code):
    if isinstance(exc, PortalAuthFailed):
        return str(exc.detail)
    if isinstance(exc, ApiValidationError):
        return exc.message
    if isinstance(exc, exceptions.PermissionDenied):
        detail = str(exc.detail)
        # Our permission classes carry Turkish messages; DRF's generic default does not.
        if detail and detail != str(exceptions.PermissionDenied.default_detail):
            return detail
        return DEFAULT_MESSAGES[403]
    return DEFAULT_MESSAGES.get(status_code)


def api_exception_handler(exc, context):
    if isinstance(exc, Http404):
        exc = exceptions.NotFound()
    elif isinstance(exc, DjangoPermissionDenied):
        exc = exceptions.PermissionDenied()

    if isinstance(exc, exceptions.APIException):
        headers = {}
        if getattr(exc, 'auth_header', None):
            headers['WWW-Authenticate'] = exc.auth_header
        if getattr(exc, 'wait', None):
            headers['Retry-After'] = str(int(exc.wait))
        set_rollback()
        code = exc.status_code
        return error_response(code, _message_for(exc, code), headers=headers)

    logger.exception('Unhandled API error')
    set_rollback()
    return error_response(status.HTTP_500_INTERNAL_SERVER_ERROR)
