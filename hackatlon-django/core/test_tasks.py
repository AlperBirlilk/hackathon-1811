"""Task özellikleri: son tarih / SLA, yedek sorumlu, uygulama içi bildirim, izin/devir, direktör görünümü."""
import os
from datetime import datetime, timedelta

from django.core import mail
from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings
from django.utils import timezone

from core import services
from core.forms import TaskForm
from core.models import Notification, Task, TaskHistory, User

AJAX = {'HTTP_X_REQUESTED_WITH': 'XMLHttpRequest'}
MAIL = dict(MAIL_ENABLED=True, MAIL_ASYNC=False, MAIL_TEST_RECIPIENT='', MAIL_NOTIFY_SELF=True,
            MAIL_ALLOWED_DOMAINS=['cyberops.local'], PORTAL_BASE_URL='http://portal.test',
            EMAIL_BACKEND='django.core.mail.backends.locmem.EmailBackend')


@override_settings(**MAIL)
class TaskFeatureTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        with open(os.devnull, 'w') as devnull:
            call_command('seed', stdout=devnull)
        cls.u = {u.username: u for u in User.objects.all()}

    def setUp(self):
        cache.clear()

    def login(self, username):
        self.client.login(username=username, password='Cyber2026!')
        return self.u[username]

    def _create(self, **kw):
        defaults = dict(user=self.u['yonetici'], title='Test task', description='', severity='HIGH',
                        status='OPEN', assignees=[self.u['alper']])
        defaults.update(kw)
        return services.create_task(**defaults)

    # ------------------------------------------------------------------ due date / SLA

    def test_sla_default_per_severity(self):
        for sev, days in Task.SLA_DAYS.items():
            with self.subTest(sev=sev):
                before = timezone.now()
                task = self._create(severity=sev)
                expected = before + timedelta(days=days)
                self.assertLess(abs((task.due_date - expected).total_seconds()), 60)

    def test_explicit_due_date_kept(self):
        due = timezone.now() + timedelta(days=30)
        task = self._create(severity='CRITICAL', due_date=due)
        task.refresh_from_db()
        self.assertEqual(task.due_date, due)

    def test_is_overdue(self):
        task = self._create(due_date=timezone.now() - timedelta(hours=1))
        self.assertTrue(task.is_overdue)
        services.update_task(task, user=self.u['yonetici'], status='DONE')
        self.assertFalse(task.is_overdue)
        self.assertFalse(self._create(due_date=timezone.now() + timedelta(hours=1)).is_overdue)
        self.assertTrue(Task.objects.get(task_title='CVE-2026-1123 yama takibi').is_overdue)

    def test_history_for_due_date_and_backup(self):
        tz = timezone.get_current_timezone()
        task = self._create(due_date=timezone.make_aware(datetime(2026, 11, 20, 14, 0), tz))
        services.update_task(task, user=self.u['yonetici'],
                             due_date=timezone.make_aware(datetime(2026, 11, 22, 18, 0), tz),
                             backup_assignee=self.u['mert'])
        due_log = task.history.get(action_type=TaskHistory.DUE_DATE_CHANGE)
        self.assertEqual(due_log.action_description, 'Son tarih: 20.11.2026 14:00 → 22.11.2026 18:00')
        backup_log = task.history.get(action_type=TaskHistory.BACKUP_CHANGE)
        self.assertEqual(backup_log.action_description, 'Yedek sorumlu: — → Mert Demir')
        # aynı dakika (saniye farkı) değişiklik sayılmaz
        self.assertFalse(services.update_task(task, user=self.u['yonetici'],
                                              due_date=task.due_date + timedelta(seconds=20),
                                              backup_assignee=self.u['mert']))
        services.update_task(task, user=self.u['yonetici'], due_date=None, backup_assignee=None)
        self.assertTrue(task.history.filter(action_description='Son tarih: 22.11.2026 18:00 → —').exists())
        self.assertTrue(task.history.filter(action_description='Yedek sorumlu: Mert Demir → —').exists())

    def test_create_history_mentions_backup(self):
        task = self._create(backup_assignee=self.u['mert'])
        self.assertIn('Yedek sorumlu: Mert Demir', task.history.get(action_type=TaskHistory.CREATED).action_description)

    # ------------------------------------------------------------------ backup assignee access

    def test_backup_can_see_and_change_status(self):
        task = self._create(assignees=[self.u['alper']], backup_assignee=self.u['berkay'])
        self.login('berkay')
        self.assertEqual(self.client.get(f'/tasks/{task.pk}/').status_code, 200)
        self.assertContains(self.client.get('/tasks/'), task.task_title)
        r = self.client.post(f'/tasks/{task.pk}/status/', {'status': 'IN_PROGRESS'}, **AJAX)
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.json()['ok'])
        self.assertIn('is_overdue', r.json()['task'])
        self.assertIn('due_date', r.json()['task'])
        task.refresh_from_db()
        self.assertEqual(task.task_status, 'IN_PROGRESS')

    def test_backup_status_form_on_detail(self):
        task = Task.objects.get(task_title='CVE-2026-1123 yama takibi')
        self.login('mert')
        r = self.client.get(f'/tasks/{task.pk}/')
        self.assertContains(r, 'Durumu güncelle')
        self.assertContains(r, 'Mert Demir')
        self.assertContains(r, 'Gecikmiş')

    # ------------------------------------------------------------------ notifications

    def test_in_app_notifications_for_assignee_and_backup_not_actor(self):
        actor = self.u['yonetici']
        Notification.objects.all().delete()
        with self.captureOnCommitCallbacks(execute=True):
            task = self._create(user=actor, assignees=[self.u['alper'], actor], backup_assignee=self.u['berkay'])
        notes = Notification.objects.filter(task=task)
        self.assertEqual(set(notes.values_list('user__username', flat=True)), {'alper', 'berkay'})
        self.assertEqual(notes.get(user=self.u['alper']).message, f'Selin Kaya size {task.code} işini atadı')
        self.assertEqual(notes.get(user=self.u['berkay']).message,
                         f'Selin Kaya sizi {task.code} işine yedek sorumlu olarak atadı')
        subjects = {m.to[0]: m for m in mail.outbox}
        self.assertIn('berkay@cyberops.local', subjects)
        backup_mail = subjects['berkay@cyberops.local']
        self.assertIn('YEDEK SORUMLU ATAMASI', backup_mail.alternatives[0][0])
        self.assertIn('YEDEK SORUMLU ATAMASI', backup_mail.body)
        self.assertIn(task.task_title, backup_mail.body)
        self.assertIn(f'http://portal.test/tasks/{task.pk}/', backup_mail.body)

    def test_update_notifies_new_backup_and_new_assignee_once(self):
        task = self._create()
        Notification.objects.all().delete()
        with self.captureOnCommitCallbacks(execute=True):
            services.update_task(task, user=self.u['yonetici'], backup_assignee=self.u['mert'],
                                 assignees=[self.u['alper'], self.u['berkay']])
        self.assertEqual(sorted(Notification.objects.values_list('user__username', flat=True)), ['berkay', 'mert'])
        # aynı yedek tekrar kaydedilirse bildirim yok
        services.update_task(task, user=self.u['yonetici'], backup_assignee=self.u['mert'])
        self.assertEqual(Notification.objects.count(), 2)

    def test_actor_backup_gets_no_in_app(self):
        actor = self.u['yonetici']
        Notification.objects.all().delete()
        self._create(user=actor, assignees=[self.u['alper']], backup_assignee=actor)
        self.assertFalse(Notification.objects.filter(user=actor).exists())

    @override_settings(MAIL_ENABLED=False)
    def test_in_app_works_when_mail_disabled(self):
        Notification.objects.all().delete()
        self._create(assignees=[self.u['alper']])
        self.assertTrue(Notification.objects.filter(user=self.u['alper']).exists())

    # ------------------------------------------------------------------ dashboard / list

    def test_handover_panel_for_backup(self):
        self.login('mert')
        r = self.client.get('/')
        self.assertContains(r, 'Devralınan işler')
        handover = [t.task_title for t in r.context['handover']]
        self.assertIn('CVE-2026-1123 yama takibi', handover)

    def test_handover_panel_hidden_when_empty(self):
        self.login('berkay')
        self.assertNotContains(self.client.get('/'), 'Devralınan işler')

    def test_overdue_filter(self):
        self.login('yonetici')
        r = self.client.get('/tasks/?overdue=1')
        titles = {t.task_title for t in r.context['tasks']}
        self.assertEqual(titles, {'CVE-2026-1123 yama takibi', 'Ransomware örneği tersine mühendislik'})
        self.assertContains(r, 'badge overdue')

    def test_dashboard_overdue_count(self):
        self.login('berkay')  # Ransomware örneği berkay'a atanmış ve gecikmiş
        r = self.client.get('/')
        self.assertEqual(r.context['stats']['overdue'], 1)
        self.assertContains(r, 'data-stat="overdue"')
        self.assertContains(r, 'Gecikmiş')

    # ------------------------------------------------------------------ form

    def test_form_rejects_backup_equal_assignee(self):
        alper = self.u['alper']
        form = TaskForm({'title': 'x', 'severity': 'LOW', 'status': 'OPEN',
                         'assignees': [alper.pk], 'backup_assignee': alper.pk})
        self.assertFalse(form.is_valid())
        self.assertIn('backup_assignee', form.errors)

    def test_create_view_with_due_date_and_backup(self):
        me = self.login('yonetici')
        r = self.client.post('/tasks/new/', {'title': 'Formdan', 'severity': 'LOW', 'status': 'OPEN',
                                             'assignees': [me.pk], 'due_date': '2026-12-01T09:30',
                                             'backup_assignee': self.u['mert'].pk}, **AJAX)
        self.assertEqual(r.status_code, 200)
        task = Task.objects.get(task_title='Formdan')
        self.assertEqual(task.backup_assignee, self.u['mert'])
        self.assertEqual(timezone.localtime(task.due_date).strftime('%Y-%m-%d %H:%M'), '2026-12-01 09:30')

    def test_member_without_task_mgmt_cannot_set_backup(self):
        me = self.login('mert')
        self.assertNotContains(self.client.get('/tasks/new/'), 'name="backup_assignee"')
        self.client.post('/tasks/new/', {'title': 'Kendime', 'severity': 'LOW', 'status': 'OPEN',
                                         'assignees': [me.pk], 'backup_assignee': self.u['alper'].pk})
        self.assertIsNone(Task.objects.get(task_title='Kendime').backup_assignee)

    def test_detail_edit_keeps_due_date_without_spurious_history(self):
        me = self.login('yonetici')
        task = self._create(assignees=[me])
        form = self.client.get(f'/tasks/{task.pk}/').context['form']
        data = {'title': task.task_title, 'description': '', 'severity': task.task_severity,
                'status': task.task_status, 'assignees': [me.pk],
                'due_date': form['due_date'].value(), 'backup_assignee': ''}
        self.client.post(f'/tasks/{task.pk}/', data)
        self.assertFalse(task.history.filter(action_type=TaskHistory.DUE_DATE_CHANGE).exists())

    # ------------------------------------------------------------------ director / team / profile

    def test_director_sees_everyone_on_team(self):
        self.login('direktor')
        r = self.client.get('/team/')
        names = {m.username for m in r.context['team']}
        self.assertTrue({'yonetici', 'mert', 'alper', 'berkay', 'aykun'} <= names)
        self.assertNotIn('direktor', names)
        self.assertContains(r, 'İzinli')

    def test_director_can_open_any_member(self):
        self.login('direktor')
        for name in ('mert', 'yonetici'):
            with self.subTest(name=name):
                self.assertEqual(self.client.get(f'/team/{self.u[name].pk}/permissions/').status_code, 200)
                self.assertEqual(self.client.get(f'/profile/{self.u[name].pk}/').status_code, 200)

    def test_manager_blocked_for_non_team_user(self):
        self.login('yonetici')
        direktor = self.u['direktor']
        self.assertEqual(self.client.get(f'/team/{direktor.pk}/permissions/').status_code, 404)
        self.assertEqual(self.client.get(f'/profile/{direktor.pk}/').status_code, 403)
        self.assertEqual(self.client.get(f'/team/{self.u["mert"].pk}/permissions/').status_code, 200)

    def test_nobody_edits_own_permissions(self):
        for name in ('direktor', 'yonetici'):
            with self.subTest(name=name):
                me = self.login(name)
                self.assertEqual(self.client.get(f'/team/{me.pk}/permissions/').status_code, 404)
                self.assertEqual(self.client.post(f'/team/{me.pk}/permissions/', {}).status_code, 404)

    def test_director_cannot_remove_non_team_member(self):
        self.login('direktor')
        r = self.client.post(f'/team/{self.u["mert"].pk}/remove/')
        self.assertEqual(r.status_code, 404)
        self.assertEqual(User.objects.get(username='mert').manager, self.u['yonetici'])

    def test_profile_leave_saves(self):
        me = self.login('berkay')
        r = self.client.post('/profile/', {'first_name': 'Berkay', 'last_name': 'Yıldız',
                                           'email': 'berkay@cyberops.local', 'is_on_leave': 'on'})
        self.assertEqual(r.status_code, 302)
        me.refresh_from_db()
        self.assertTrue(me.is_on_leave)
        self.assertContains(self.client.get('/profile/'), 'İzinli')
