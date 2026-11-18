"""
LDAP kimlik doğrulama backend'i (saportal-be loginWithLdapLogin akışının Django karşılığı).

- LDAP yalnızca KİMLİK DOĞRULAMA için kullanılır: kullanıcı kendi DN'i ile bind olur.
- Kullanıcı bilgileri (ad, soyad, mail) LDAP'tan okunup `user` tablosuna yazılır (upsert).
- YETKİLER LDAP gruplarından ALINMAZ; `user_permission` tablosundan gelir.
"""
import logging
import re
import ssl

from django.conf import settings
from django.contrib.auth import get_user_model
from django.contrib.auth.backends import BaseBackend
from ldap3 import NONE, SIMPLE, SUBTREE, Connection, Server, Tls
from ldap3.core.exceptions import LDAPBindError, LDAPException, LDAPInvalidCredentialsResult
from ldap3.utils.conv import escape_filter_chars
from ldap3.utils.dn import escape_rdn

logger = logging.getLogger(__name__)

USERNAME_RE = re.compile(r'^[a-zA-Z0-9._-]{1,64}$')
LDAP_ATTRIBUTES = ['mail', 'givenName', 'sn', 'turkishlastname']


class LDAPUnavailable(Exception):
    """LDAP sunucusuna ulaşılamadı / beklenmeyen hata."""


def _server():
    tls = Tls(validate=ssl.CERT_REQUIRED if settings.LDAP_TLS_VERIFY else ssl.CERT_NONE,
              ca_certs_file=settings.LDAP_CA_CERT_FILE or None)
    return Server(settings.LDAP_URL, use_ssl=settings.LDAP_URL.lower().startswith('ldaps://'),
                  tls=tls, get_info=NONE, connect_timeout=settings.LDAP_TIMEOUT)


def _first(entry, attr):
    value = entry.get(attr)
    if isinstance(value, (list, tuple)):
        value = value[0] if value else ''
    return (value or '').strip() if isinstance(value, str) else ''


def ldap_authenticate(username, password):
    """
    Kullanıcı DN'i ile bind olur. Başarılıysa {'dn', 'first_name', 'last_name', 'email'} döner,
    parola hatalıysa None döner, LDAP'a ulaşılamazsa LDAPUnavailable fırlatır.
    """
    # Boş parola ile simple bind = anonymous bind → LDAP "başarılı" döner. Kesinlikle engellenmeli.
    if not password:
        return None

    user_dn = f'uid={escape_rdn(username)},{settings.LDAP_USER_SEARCH_BASE}'
    conn = Connection(_server(), user=user_dn, password=password, authentication=SIMPLE,
                      receive_timeout=settings.LDAP_TIMEOUT, raise_exceptions=True, read_only=True)
    try:
        conn.bind()
    except (LDAPInvalidCredentialsResult, LDAPBindError):
        return None
    except LDAPException as exc:
        raise LDAPUnavailable(str(exc)) from exc

    try:
        conn.search(settings.LDAP_USER_SEARCH_BASE, f'(uid={escape_filter_chars(username)})',
                    search_scope=SUBTREE, attributes=LDAP_ATTRIBUTES, size_limit=1)
        attrs = conn.response[0].get('attributes', {}) if conn.response else {}
        return {
            'dn': conn.response[0].get('dn', user_dn) if conn.response else user_dn,
            'first_name': _first(attrs, 'givenName'),
            'last_name': _first(attrs, 'turkishlastname') or _first(attrs, 'sn'),
            'email': _first(attrs, 'mail'),
        }
    except LDAPException:
        # Bind başarılı → kimlik doğrulandı; profil bilgisi okunamasa da giriş yapılabilir.
        logger.warning('LDAP attributes could not be read: %s', username, exc_info=True)
        return {'dn': user_dn, 'first_name': '', 'last_name': '', 'email': ''}
    finally:
        conn.unbind()


class LDAPBackend(BaseBackend):

    def authenticate(self, request, username=None, password=None, **kwargs):
        if not settings.LDAP_ENABLED or not username or not password:
            return None
        username = username.strip().lower()
        if not USERNAME_RE.fullmatch(username):
            return None

        User = get_user_model()
        existing = User.objects.filter(username=username).first()
        # Yerel (seed/admin) hesaplar LDAP ile eşleştirilmez; parolaları LDAP'a da gönderilmez.
        if existing and existing.auth_source != User.AUTH_LDAP:
            return None

        try:
            info = ldap_authenticate(username, password)
        except LDAPUnavailable:
            logger.error('LDAP unreachable (%s)', settings.LDAP_URL, exc_info=True)
            return None
        if info is None:
            return None

        user = existing or User(username=username, auth_source=User.AUTH_LDAP)
        if user.pk is None:
            user.set_unusable_password()
        if not user.is_active:
            return None
        for field in ('first_name', 'last_name', 'email'):
            if info[field]:
                setattr(user, field, info[field])
        user.ldap_dn = info['dn']
        user.save()
        logger.info('LDAP login: %s (%s)', username, 'new' if existing is None else 'existing')
        return user

    def get_user(self, user_id):
        User = get_user_model()
        user = User.objects.filter(pk=user_id).first()
        return user if user and user.is_active else None
