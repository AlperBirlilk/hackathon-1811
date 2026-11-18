from unittest import mock

from django.core.cache import cache
from django.test import TestCase, override_settings

from core.ldap_backend import LDAPUnavailable, ldap_authenticate
from core import services
from core.models import PermissionType, Task, TaskHistory, User, UserPermission

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
                                             ('/data-sharing/', 403)])   # yonetici'de DATA_ACCESS yok

    def test_director_pages(self):
        self._get_all('direktor', lambda m: [('/team/', 200), ('/data-sharing/', 200),
                                             ('/activities/new/', 200)])
        self.assertTrue(User.objects.get(username='direktor').is_director)
        self.assertFalse(User.objects.get(username='yonetici').is_director)

    def test_member_pages(self):
        self._get_all('mert', lambda m: [('/team/', 403), ('/activities/new/', 403), ('/data-sharing/', 200)])

    def test_login_page(self):
        r = self.client.get('/login/')
        self.assertContains(r, 'theme-toggle corner')


class DashboardTaskTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        call_command('seed', stdout=open(__import__('os').devnull, 'w'))

    def setUp(self):
        cache.clear()
        self.client.login(username='yonetici', password='Cyber2026!')

    def test_task_created_for_others_appears_on_creators_dashboard(self):
        other = User.objects.get(username='mert')
        r = self.client.post('/tasks/new/', {'title': 'Dashboard görünürlük testi', 'description': '',
                                             'severity': 'HIGH', 'status': 'OPEN', 'assignees': [other.pk]})
        self.assertEqual(r.status_code, 302)
        self.assertContains(self.client.get('/'), 'Dashboard görünürlük testi')

    def test_create_form_preselects_current_user(self):
        me = User.objects.get(username='yonetici')
        form = self.client.get('/tasks/new/').context['form']
        self.assertEqual(form['assignees'].value(), [me.pk])


class TaskWorkflowTests(TestCase):
    """Aynı sayfada task oluşturma, kanban durum değişikliği ve toplu işlemler."""

    AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}

    @classmethod
    def setUpTestData(cls):
        from django.core.management import call_command
        call_command('seed', stdout=open(__import__('os').devnull, 'w'))

    def setUp(self):
        cache.clear()

    def login(self, username):
        self.client.login(username=username, password='Cyber2026!')
        return User.objects.get(username=username)

    def test_ajax_create_returns_json_and_stays(self):
        me = self.login('yonetici')
        r = self.client.post('/tasks/new/', {'title': 'AJAX task', 'severity': 'CRITICAL', 'status': 'OPEN',
                                             'assignees': [me.pk]}, **self.AJAX)
        self.assertEqual(r.status_code, 200)
        data = r.json()
        self.assertTrue(data['ok'])
        self.assertEqual(data['task']['severity'], 'CRITICAL')
        self.assertTrue(Task.objects.filter(task_title='AJAX task').exists())

    def test_ajax_create_validation_errors(self):
        self.login('yonetici')
        r = self.client.post('/tasks/new/', {'title': '', 'severity': 'NOPE', 'status': 'OPEN'}, **self.AJAX)
        self.assertEqual(r.status_code, 400)
        self.assertIn('title', r.json()['errors'])
        self.assertIn('severity', r.json()['errors'])

    def test_non_ajax_create_redirects_back_to_form(self):
        me = self.login('yonetici')
        r = self.client.post('/tasks/new/', {'title': 'Klasik', 'severity': 'LOW', 'status': 'OPEN',
                                             'assignees': [me.pk]})
        self.assertRedirects(r, '/tasks/new/', fetch_redirect_response=False)

    def test_create_page_renders_colored_severity_picker(self):
        self.login('yonetici')
        r = self.client.get('/tasks/new/')
        for sev in ('low', 'medium', 'high', 'critical'):
            self.assertContains(r, f'sev-opt-{sev}')

    def test_kanban_status_change_persists_and_logs(self):
        me = self.login('yonetici')
        task = Task.objects.filter(assignees=me, task_status=Task.STATUS_OPEN).first()
        r = self.client.post(f'/tasks/{task.pk}/status/', {'status': 'DONE'}, **self.AJAX)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['changed'])
        task.refresh_from_db()
        self.assertEqual(task.task_status, Task.STATUS_DONE)
        self.assertTrue(task.history.filter(action_type='status_change').exists())

    def test_kanban_status_change_on_hidden_task_is_404(self):
        self.login('mert')
        other = User.objects.get(username='alper')
        task = services.create_task(user=other, title='Başkasının', description='', severity='LOW',
                                    status='OPEN', assignees=[other])
        r = self.client.post(f'/tasks/{task.pk}/status/', {'status': 'DONE'}, **self.AJAX)
        self.assertEqual(r.status_code, 404)
        task.refresh_from_db()
        self.assertEqual(task.task_status, 'OPEN')

    def test_kanban_invalid_status(self):
        me = self.login('yonetici')
        task = Task.objects.filter(assignees=me).first()
        r = self.client.post(f'/tasks/{task.pk}/status/', {'status': 'HACKED'}, **self.AJAX)
        self.assertEqual(r.status_code, 400)

    def test_dashboard_has_three_lanes(self):
        self.login('yonetici')
        r = self.client.get('/')
        for status in ('OPEN', 'IN_PROGRESS', 'DONE'):
            self.assertContains(r, f'data-status="{status}"')

    def test_bulk_status_severity_and_assignment(self):
        me = self.login('yonetici')
        ids = list(Task.objects.values_list('pk', flat=True)[:3])
        mert = User.objects.get(username='mert')
        self.client.post('/tasks/bulk/', {'ids': ids, 'op': 'status:DONE'})
        self.assertEqual(Task.objects.filter(pk__in=ids, task_status='DONE').count(), 3)
        self.client.post('/tasks/bulk/', {'ids': ids, 'op': 'severity:CRITICAL'})
        self.assertEqual(Task.objects.filter(pk__in=ids, task_severity='CRITICAL').count(), 3)
        self.client.post('/tasks/bulk/', {'ids': ids, 'op': 'assign', 'user': mert.pk})
        self.assertEqual(Task.objects.filter(pk__in=ids, assignees=mert).count(), 3)
        self.client.post('/tasks/bulk/', {'ids': ids, 'op': 'unassign', 'user': mert.pk})
        self.assertEqual(Task.objects.filter(pk__in=ids, assignees=mert).count(), 0)
        self.assertTrue(TaskHistory.objects.filter(task_id__in=ids, action_type='assignment_change').exists())

    def test_bulk_respects_permissions(self):
        mert = self.login('mert')
        own = services.create_task(user=mert, title='Kendi taskım', description='', severity='LOW',
                                   status='OPEN', assignees=[mert])
        assigned_only = Task.objects.filter(assignees=mert).exclude(created_by=mert).first()
        hidden = Task.objects.exclude(assignees=mert).exclude(created_by=mert).first()
        r = self.client.post('/tasks/bulk/', {'ids': [own.pk, assigned_only.pk, hidden.pk],
                                              'op': 'severity:CRITICAL'}, follow=True)
        own.refresh_from_db(); assigned_only.refresh_from_db(); hidden.refresh_from_db()
        self.assertEqual(own.task_severity, 'CRITICAL')           # oluşturan -> düzenleyebilir
        self.assertNotEqual(assigned_only.task_severity, 'CRITICAL')  # sadece atanan -> önem değiştiremez
        self.assertNotEqual(hidden.task_severity, 'CRITICAL')     # görünmeyen -> dokunulmaz
        self.assertContains(r, 'atlandı')

    def test_bulk_invalid_op_and_open_redirect(self):
        self.login('yonetici')
        r = self.client.post('/tasks/bulk/', {'ids': [1], 'op': 'status:HACKED', 'next': 'https://evil.com'})
        self.assertEqual(r['Location'], '/tasks/')


@override_settings(MAIL_ENABLED=True, MAIL_ASYNC=False, MAIL_TEST_RECIPIENT='', MAIL_NOTIFY_SELF=False,
                   MAIL_ALLOWED_DOMAINS=['turkcell.com.tr'], PORTAL_BASE_URL='http://portal.test',
                   EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')
class MailNotificationTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.actor = User.objects.create_user('ali', email='ali@turkcell.com.tr', first_name='Ali', password='x')
        cls.ayse = User.objects.create_user('ayse', email='ayse@turkcell.com.tr', first_name='AYŞE', password='x')
        cls.can = User.objects.create_user('can', email='can@turkcell.com.tr', first_name='Can', password='x')
        cls.external = User.objects.create_user('ext', email='ext@gmail.com', password='x')
        cls.noemail = User.objects.create_user('nomail', email='', password='x')

    def _create(self, assignees, title='Phishing analizi'):
        with self.captureOnCommitCallbacks(execute=True):
            return services.create_task(user=self.actor, title=title, description='IOC çıkar',
                                        severity='CRITICAL', status='OPEN', assignees=assignees)

    def test_task_assignment_mail(self):
        from django.core import mail
        task = self._create([self.ayse, self.actor])
        self.assertEqual(len(mail.outbox), 1)               # actor kendine mail almaz
        m = mail.outbox[0]
        self.assertEqual(m.to, ['ayse@turkcell.com.tr'])
        self.assertEqual(m.from_email, 'TEAM-SMA@smtp.turkcell.com.tr')
        self.assertIn('Phishing analizi', m.subject)
        html = m.alternatives[0][0]
        self.assertIn('Merhaba Ayşe,', html)
        self.assertIn(f'http://portal.test/tasks/{task.pk}/', html)
        self.assertIn('Kritik', html)
        self.assertIn('Hackatlon Bilgilendirme', html)
        self.assertNotIn('Bozok', html)
        self.assertNotIn('BOZOK', html)
        self.assertIn('Phishing analizi', m.body)          # düz metin alternatifi

    def test_only_newly_added_assignees_get_mail(self):
        from django.core import mail
        task = self._create([self.ayse])
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            services.update_task(task, user=self.actor, assignees=[self.ayse, self.can])
        self.assertEqual([m.to for m in mail.outbox], [['can@turkcell.com.tr']])
        mail.outbox.clear()
        with self.captureOnCommitCallbacks(execute=True):
            services.update_task(task, user=self.actor, status='DONE')   # atama yok -> mail yok
        self.assertEqual(mail.outbox, [])

    def test_skips_external_domain_and_missing_email(self):
        from django.core import mail
        self._create([self.external, self.noemail])
        self.assertEqual(mail.outbox, [])

    @override_settings(MAIL_TEST_RECIPIENT='test@turkcell.com.tr')
    def test_test_mode_redirects(self):
        from django.core import mail
        self._create([self.ayse])
        self.assertEqual(mail.outbox[0].to, ['test@turkcell.com.tr'])
        self.assertIn('ayse@turkcell.com.tr', mail.outbox[0].subject)

    @override_settings(MAIL_ENABLED=False)
    def test_disabled(self):
        from django.core import mail
        self._create([self.ayse])
        self.assertEqual(mail.outbox, [])

    def test_activity_invitation_mail(self):
        from django.core import mail
        PermissionType.objects.create(code=PermissionType.ACTIVITY_MANAGEMENT, permission_name='Activity')
        UserPermission.objects.create(user=self.actor, permission_type=PermissionType.objects.get())
        cache.clear()
        self.client.force_login(self.actor)
        with self.captureOnCommitCallbacks(execute=True):
            r = self.client.post('/activities/new/', {
                'activity_name': 'CTF Antrenmanı', 'activity_date': '2026-12-01T10:00',
                'location': 'Lab-3', 'attendees': [self.ayse.pk, self.can.pk, self.actor.pk]})
        self.assertEqual(r.status_code, 302)
        self.assertEqual(sorted(m.to[0] for m in mail.outbox), ['ayse@turkcell.com.tr', 'can@turkcell.com.tr'])
        html = mail.outbox[0].alternatives[0][0]
        self.assertIn('ETKİNLİK DAVETİ', html)
        self.assertIn('Lab-3', html)
        self.assertIn('/activities/#activity-', html)

    def test_smtp_failure_does_not_break_request(self):
        from django.core import mail
        with mock.patch('django.core.mail.EmailMultiAlternatives.send', side_effect=OSError('smtp down')):
            task = self._create([self.ayse])
        self.assertTrue(Task.objects.filter(pk=task.pk).exists())

    @override_settings(MAIL_NOTIFY_SELF=True)
    def test_self_assignment_sends_mail_by_default(self):
        from django.core import mail
        self._create([self.actor])
        self.assertEqual([m.to for m in mail.outbox], [['ali@turkcell.com.tr']])
