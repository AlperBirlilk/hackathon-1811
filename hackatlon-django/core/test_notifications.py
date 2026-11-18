import os

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse

from core.models import Notification, Task, User


@override_settings(MAIL_ENABLED=False)
class NotificationPageTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        with open(os.devnull, 'w') as devnull:
            call_command('seed', stdout=devnull)
        cls.berkay = User.objects.get(username='berkay')
        cls.mert = User.objects.get(username='mert')
        Notification.objects.all().delete()
        cls.task = Task.objects.filter(assignees=cls.berkay).first()
        cls.n1 = Notification.objects.create(user=cls.berkay, task=cls.task, message='Berkay bildirimi 1')
        cls.n2 = Notification.objects.create(user=cls.berkay, message='Berkay bildirimi 2 (tasksız)')
        cls.other = Notification.objects.create(user=cls.mert, task=cls.task, message='Mert bildirimi')

    def setUp(self):
        self.client.force_login(self.berkay)

    def test_list_shows_only_own(self):
        r = self.client.get(reverse('notification_list'))
        self.assertEqual(r.status_code, 200)
        self.assertContains(r, 'Berkay bildirimi 1')
        self.assertContains(r, 'Berkay bildirimi 2')
        self.assertNotContains(r, 'Mert bildirimi')
        self.assertContains(r, 'Tümünü okundu işaretle')

    def test_empty_state(self):
        self.client.force_login(User.objects.get(username='aykun'))
        r = self.client.get(reverse('notification_list'))
        self.assertContains(r, 'Henüz bildiriminiz yok.')
        self.assertNotContains(r, 'Tümünü okundu işaretle')

    def test_unread_badge_in_sidebar(self):
        r = self.client.get(reverse('dashboard'))
        self.assertEqual(r.context['unread_notifications'], 2)
        self.assertContains(r, 'data-unread="2"')
        self.client.force_login(User.objects.get(username='aykun'))
        r = self.client.get(reverse('dashboard'))
        self.assertEqual(r.context['unread_notifications'], 0)
        self.assertNotContains(r, 'data-unread=')

    def test_read_marks_and_redirects_to_task(self):
        r = self.client.post(reverse('notification_read', args=[self.n1.pk]))
        self.assertRedirects(r, reverse('task_detail', args=[self.task.pk]), fetch_redirect_response=False)
        self.n1.refresh_from_db()
        self.assertTrue(self.n1.is_read)

    def test_read_without_task_uses_safe_next(self):
        r = self.client.post(reverse('notification_read', args=[self.n2.pk]), {'next': 'https://evil.example/'})
        self.assertRedirects(r, reverse('notification_list'), fetch_redirect_response=False)
        self.n2.refresh_from_db()
        self.assertTrue(self.n2.is_read)

    def test_read_other_users_notification_404(self):
        r = self.client.post(reverse('notification_read', args=[self.other.pk]))
        self.assertEqual(r.status_code, 404)
        self.other.refresh_from_db()
        self.assertFalse(self.other.is_read)

    def test_get_not_allowed(self):
        self.assertEqual(self.client.get(reverse('notification_read', args=[self.n1.pk])).status_code, 405)
        self.assertEqual(self.client.get(reverse('notification_read_all')).status_code, 405)

    def test_read_all(self):
        r = self.client.post(reverse('notification_read_all'))
        self.assertRedirects(r, reverse('notification_list'), fetch_redirect_response=False)
        self.assertFalse(Notification.objects.filter(user=self.berkay, is_read=False).exists())
        self.other.refresh_from_db()
        self.assertFalse(self.other.is_read)

    def test_anonymous_redirected(self):
        self.client.logout()
        r = self.client.get(reverse('notification_list'))
        self.assertEqual(r.status_code, 302)
