from django.contrib import messages
from django.contrib.auth import logout
from django.shortcuts import redirect

from . import api_client

EXEMPT_PREFIXES = ('/login/', '/logout/', '/admin/', '/static/')


class ApiSessionMiddleware:
    """JWT'siz oturumları ve API 401 yanıtlarını logout + login'e yönlendirmeye çevirir."""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, 'user', None)
        if (user is not None and user.is_authenticated
                and not request.path.startswith(EXEMPT_PREFIXES)
                and not request.session.get(api_client.SESSION_JWT)):
            return self._kick(request)
        return self.get_response(request)

    def process_exception(self, request, exception):
        if isinstance(exception, api_client.ApiUnauthorized):
            return self._kick(request)
        return None

    @staticmethod
    def _kick(request):
        logout(request)
        messages.info(request, 'Oturumunuzun süresi doldu, lütfen tekrar giriş yapın.')
        return redirect('login')
