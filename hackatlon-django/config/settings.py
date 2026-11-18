"""
CyberOps Portal - Django settings (monolith, SQLite).
"""

import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

# Production'da ortam değişkeninden okunmalı.
SECRET_KEY = os.environ.get(
    'DJANGO_SECRET_KEY',
    'django-insecure-dev-only-change-me-j2+rj#aq7lzy*0hwo%u++kq%04',
)
DEBUG = os.environ.get('DJANGO_DEBUG', '1') == '1'
ALLOWED_HOSTS = os.environ.get('DJANGO_ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.humanize',
    'rest_framework',
    'rest_framework.authtoken',
    'core',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.context_processors.portal',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
        'OPTIONS': {
            # Kilitli DB'de hemen hata vermek yerine bekle (DB Browser vb. açıkken).
            'timeout': 20,
            # DB dosyası WAL moduna alındı (bkz. README): okuyucular yazanı engellemez.
            'init_command': 'PRAGMA synchronous=NORMAL;',
        },
    }
}

AUTH_USER_MODEL = 'core.User'

# --- LDAP: sadece kimlik doğrulama. Yetkiler DB'deki user_permission tablosundan gelir.
LDAP_ENABLED = os.environ.get('LDAP_ENABLED', '1') == '1'
LDAP_URL = os.environ.get('LDAP_URL', 'ldaps://ldapTESTssl1.turkcell.com.tr:1636')
LDAP_USER_SEARCH_BASE = os.environ.get('LDAP_USER_SEARCH_BASE', 'ou=People,o=Turkcell,dc=entp,dc=tgc')
LDAP_TLS_VERIFY = os.environ.get('LDAP_TLS_VERIFY', '1') == '1'   # sertifika doğrulaması (kapatmayın)
LDAP_CA_CERT_FILE = os.environ.get('LDAP_CA_CERT_FILE', '')       # özel CA gerekiyorsa
LDAP_TIMEOUT = int(os.environ.get('LDAP_TIMEOUT', '5'))

# Yerel (seed/admin) hesaplarla giriş: demo/dev için açık, prod'da LOCAL_AUTH_ENABLED=0 yapın.
LOCAL_AUTH_ENABLED = os.environ.get('LOCAL_AUTH_ENABLED', '1' if DEBUG else '0') == '1'

AUTHENTICATION_BACKENDS = ['core.ldap_backend.LDAPBackend']
if LOCAL_AUTH_ENABLED:
    AUTHENTICATION_BACKENDS.append('django.contrib.auth.backends.ModelBackend')

# --- E-posta bildirimleri (saportal-be ile aynı SMTP: smtp.turkcell.com.tr:25, auth/TLS yok)
EMAIL_BACKEND = os.environ.get('EMAIL_BACKEND', 'django.core.mail.backends.smtp.EmailBackend')
EMAIL_HOST = os.environ.get('MAIL_HOST', 'smtp.turkcell.com.tr')
EMAIL_PORT = int(os.environ.get('MAIL_PORT', '25'))
EMAIL_HOST_USER = os.environ.get('MAIL_USERNAME', '')
EMAIL_HOST_PASSWORD = os.environ.get('MAIL_PASSWORD', '')
EMAIL_USE_TLS = os.environ.get('MAIL_STARTTLS', '0') == '1'
EMAIL_TIMEOUT = int(os.environ.get('MAIL_TIMEOUT', '15'))
DEFAULT_FROM_EMAIL = os.environ.get('MAIL_FROM', 'TEAM-SMA@smtp.turkcell.com.tr')
SERVER_EMAIL = DEFAULT_FROM_EMAIL

MAIL_ENABLED = os.environ.get('MAIL_ENABLED', '1') == '1'
MAIL_ASYNC = os.environ.get('MAIL_ASYNC', '1') == '1'            # SMTP'yi arka planda çağır
MAIL_NOTIFY_SELF = os.environ.get('MAIL_NOTIFY_SELF', '1') == '1'  # kendini atayana da mail gitsin
# Doluysa tüm mailler bu adrese yönlendirilir (test modu, saportal-be'deki test-recipient gibi)
MAIL_TEST_RECIPIENT = os.environ.get('MAIL_TEST_RECIPIENT', '')
# Sadece bu domainlere mail gönderilir (demo hesapları / dış adreslere sızıntıyı engeller)
MAIL_ALLOWED_DOMAINS = [d.strip().lower() for d in
                        os.environ.get('MAIL_ALLOWED_DOMAINS', 'turkcell.com.tr').split(',') if d.strip()]
MAIL_BRAND_NAME = os.environ.get('MAIL_BRAND_NAME', 'Hackatlon Bilgilendirme')
MAIL_BRAND_TAGLINE = os.environ.get('MAIL_BRAND_TAGLINE', '')      # boşsa gösterilmez
MAIL_FOOTER_OWNER = os.environ.get('MAIL_FOOTER_OWNER', '')        # boşsa telif satırı gösterilmez
# Maillerdeki linklerin başına eklenir
PORTAL_BASE_URL = os.environ.get('PORTAL_BASE_URL', 'http://127.0.0.1:8000')

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {'console': {'class': 'logging.StreamHandler'}},
    'loggers': {'core': {'handlers': ['console'], 'level': 'INFO'}},
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'dashboard'
LOGOUT_REDIRECT_URL = 'login'

# Brute-force koruması: art arda başarısız giriş limiti
LOGIN_MAX_ATTEMPTS = 5
LOGIN_LOCKOUT_SECONDS = 300

# Güvenlik başlıkları / oturum sertleştirme
SESSION_COOKIE_HTTPONLY = True
SESSION_COOKIE_SAMESITE = 'Lax'
SESSION_COOKIE_AGE = 60 * 60 * 8
SESSION_EXPIRE_AT_BROWSER_CLOSE = True
CSRF_COOKIE_SAMESITE = 'Lax'
X_FRAME_OPTIONS = 'DENY'
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
if not DEBUG:
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_SSL_REDIRECT = True
    SECURE_HSTS_SECONDS = 31536000

CACHES = {
    'default': {'BACKEND': 'django.core.cache.backends.locmem.LocMemCache'},
}

LANGUAGE_CODE = 'tr'
TIME_ZONE = 'Europe/Istanbul'
USE_I18N = True
USE_TZ = True

STATIC_URL = 'static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# --- Read-only REST API (/api/...) used by the MCP server
REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'core.api.auth.BearerTokenAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': ['rest_framework.permissions.IsAuthenticated'],
    'DEFAULT_RENDERER_CLASSES': ['rest_framework.renderers.JSONRenderer'],
    'DEFAULT_PARSER_CLASSES': ['rest_framework.parsers.JSONParser'],
    'EXCEPTION_HANDLER': 'core.api.exceptions.api_exception_handler',
    'UNAUTHENTICATED_USER': 'django.contrib.auth.models.AnonymousUser',
}
# API token lifetime (hours); older tokens are rejected with 401.
API_TOKEN_TTL_HOURS = int(os.environ.get('API_TOKEN_TTL_HOURS', '24'))
