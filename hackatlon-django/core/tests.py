from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings

from core.ldap_backend import LDAPUnavailable, ldap_authenticate
from core.models import PermissionType, User, UserPermission

LDAP_OK = {'dn': 'uid=ali.veli,ou=People,o=Turkcell,dc=entp,dc=tgc',
           'first_name': 'Ali', 'last_name': 'Veli', 'email': 'ali.veli@turkcell.com.tr'}
PATCH = 'core.ldap_backend.ldap_authenticate'


@override_settings(LDAP_ENABLED=True)
class LDAPLoginTests(TestCase):

    def setUp(self):
        cache.clear()
        self.perm = PermissionType.objects.create(code=PermissionType.TASK_MANAGEMENT,
                                                  permission_name='Task Management')

    def login(self, username='ali.veli', password='secret'):
        return self.client.post('/login/', {'username': username, 'password': password})

    def test_first_login_creates_user_from_ldap_without_permissions(self):
        with mock.patch(PATCH, return_value=LDAP_OK) as m:
            r = self.login('Ali.Veli')
        self.assertRedirects(r, '/', fetch_redirect_response=False)
        m.assert_called_once_with('ali.veli', 'secret')
        u = User.objects.get(username='ali.veli')
        self.assertEqual((u.first_name, u.last_name, u.email, u.auth_source),
                         ('Ali', 'Veli', 'ali.veli@turkcell.com.tr', User.AUTH_LDAP))
        self.assertFalse(u.has_usable_password())
        self.assertIsNotNone(u.last_login)
        self.assertEqual(u.permission_codes(), set())

    def test_permissions_come_from_db(self):
        with mock.patch(PATCH, return_value=LDAP_OK):
            self.login()
        self.assertEqual(self.client.get('/activities/new/').status_code, 403)
        u = User.objects.get(username='ali.veli')
        UserPermission.objects.create(user=u, permission_type=PermissionType.objects.create(
            code=PermissionType.ACTIVITY_MANAGEMENT, permission_name='Activity'))
        self.assertEqual(self.client.get('/activities/new/').status_code, 200)

    def test_second_login_updates_existing_user_and_keeps_permissions(self):
        with mock.patch(PATCH, return_value=LDAP_OK):
            self.login()
        u = User.objects.get(username='ali.veli')
        UserPermission.objects.create(user=u, permission_type=self.perm)
        self.client.logout()
        with mock.patch(PATCH, return_value={**LDAP_OK, 'last_name': 'Yeni'}):
            self.login()
        u.refresh_from_db()
        self.assertEqual(u.last_name, 'Yeni')
        self.assertEqual(User.objects.filter(username='ali.veli').count(), 1)
        self.assertEqual(u.permission_codes(), {PermissionType.TASK_MANAGEMENT})

    def test_wrong_password_rejected(self):
        with mock.patch(PATCH, return_value=None):
            r = self.login()
        self.assertEqual(r.status_code, 200)
        self.assertFalse(User.objects.filter(username='ali.veli').exists())

    def test_ldap_down_rejected(self):
        with mock.patch(PATCH, side_effect=LDAPUnavailable('timeout')):
            r = self.login()
        self.assertEqual(r.status_code, 200)
        self.assertNotIn('_auth_user_id', self.client.session)

    def test_inactive_user_blocked(self):
        User.objects.create(username='ali.veli', auth_source=User.AUTH_LDAP, is_active=False)
        with mock.patch(PATCH, return_value=LDAP_OK):
            r = self.login()
        self.assertEqual(r.status_code, 200)

    def test_local_account_never_linked_to_ldap(self):
        User.objects.create_superuser('admin', 'a@a.com', 'Local-Pass-123')
        with mock.patch(PATCH, return_value=LDAP_OK) as m:
            r = self.login('admin', 'whatever')
        m.assert_not_called()
        self.assertEqual(r.status_code, 200)

    def test_injection_usernames_rejected_before_ldap(self):
        with mock.patch(PATCH, return_value=LDAP_OK) as m:
            for bad in ['*', 'a)(uid=*', 'admin,ou=x', 'a b', 'ç' * 3]:
                self.login(bad)
        m.assert_not_called()

    @override_settings(LOCAL_AUTH_ENABLED=False,
                       AUTHENTICATION_BACKENDS=['core.ldap_backend.LDAPBackend'])
    def test_local_login_disabled(self):
        User.objects.create_user('demo', password='Cyber2026!')
        r = self.login('demo', 'Cyber2026!')
        self.assertEqual(r.status_code, 200)


class LDAPBindTests(TestCase):

    def test_empty_password_never_reaches_ldap(self):
        # Boş parola = anonymous bind; LDAP'a hiç gönderilmemeli
        with mock.patch('core.ldap_backend.Connection') as conn:
            self.assertIsNone(ldap_authenticate('ali.veli', ''))
        conn.assert_not_called()

    def test_bind_dn_is_escaped(self):
        with mock.patch('core.ldap_backend.Connection') as conn:
            conn.return_value.response = []
            ldap_authenticate('ali.veli', 'pw')
        self.assertTrue(conn.call_args.kwargs['user'].startswith('uid=ali.veli,ou=People'))


class PageRenderTests(TestCase):
    """Seed verisiyle tüm sayfaların iki rol için hatasız render edildiğini doğrular."""

    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        call_command('seed', stdout=open(__import__('os').devnull, 'w'))

    def _get_all(self, username, expect):
        cache.clear()
        self.client.login(username=username, password='Cyber2026!')
        from core.models import Task
        member = User.objects.get(username='mert')
        task = Task.objects.filter(assignees=member).first()
        for url, code in [('/', 200), ('/tasks/', 200), ('/tasks/?q=a&status=OPEN', 200), ('/tasks/new/', 200),
                          (f'/tasks/{task.pk}/', 200), ('/activities/', 200), ('/profile/', 200)] + expect(member):
            with self.subTest(user=username, url=url):
                r = self.client.get(url)
                self.assertEqual(r.status_code, code)
                if code == 200:
                    self.assertContains(r, 'theme-toggle')

    def test_manager_pages(self):
        self._get_all('yonetici', lambda m: [('/team/', 200), (f'/team/{m.pk}/permissions/', 200),
                                             (f'/profile/{m.pk}/', 200), ('/activities/new/', 200),
                                             ('/data-sharing/', 200)])

    def test_member_pages(self):
        self._get_all('mert', lambda m: [('/team/', 403), ('/activities/new/', 403), ('/data-sharing/', 200)])

    def test_login_page(self):
        r = self.client.get('/login/')
        self.assertContains(r, 'theme-toggle corner')
