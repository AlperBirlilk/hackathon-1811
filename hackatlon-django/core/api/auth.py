from datetime import timedelta

from django.conf import settings
from django.utils import timezone
from rest_framework.authentication import TokenAuthentication
from rest_framework.exceptions import AuthenticationFailed


class PortalAuthFailed(AuthenticationFailed):
    """AuthenticationFailed whose message is already Turkish and safe to show."""


def token_ttl():
    return timedelta(hours=settings.API_TOKEN_TTL_HOURS)


def token_expires_at(token):
    return token.created + token_ttl()


def token_is_expired(token):
    return timezone.now() >= token_expires_at(token)


class BearerTokenAuthentication(TokenAuthentication):
    """`Authorization: Bearer <token>`; tokens older than API_TOKEN_TTL_HOURS are rejected."""

    keyword = 'Bearer'

    def authenticate(self, request):
        try:
            return super().authenticate(request)
        except PortalAuthFailed:
            raise
        except AuthenticationFailed:
            raise PortalAuthFailed('Geçersiz Authorization başlığı. Biçim: "Authorization: Bearer <token>".')

    def authenticate_credentials(self, key):
        model = self.get_model()
        try:
            token = model.objects.select_related('user').get(key=key)
        except model.DoesNotExist:
            raise PortalAuthFailed('Geçersiz token.')
        if not token.user.is_active:
            raise PortalAuthFailed('Kullanıcı pasif veya silinmiş.')
        if token_is_expired(token):
            raise PortalAuthFailed('Token süresi dolmuş. Veri Paylaşımı sayfasından yeni token üretin.')
        return token.user, token

    def authenticate_header(self, request):
        return f'{self.keyword} realm="api"'
