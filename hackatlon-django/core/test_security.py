"""Güvenlik incelemesinde bulunan açıkların regresyon testleri (H1: hiyerarşi, H2: atama kısıtı)."""
import os

from django.core.cache import cache
from django.core.management import call_command
from django.test import TestCase, override_settings

from core import services
from core.models import Notification, PermissionType, Task, User, UserPermission
from core.views import can_manage_member

PW = 'Cyber2026!'


@override_settings(MAIL_ENABLED=False)
class HierarchyProtectionTests(TestCase):
    """H1: yönetici, direktörü veya kendi üstünü ekibine alıp yetkilerini düşüremez."""

    @classmethod
    def setUpTestData(cls):
        call_command('seed', stdout=open(os.devnull, 'w'))
        cls.direktor = User.objects.get(username='direktor')
        cls.yonetici = User.objects.get(username='yonetici')   # direktor'e bağlı, ROLE_MANAGEMENT var
        # Yöneticisi olmayan, ROLE_MANAGEMENT sahibi ikinci bir yönetici (ör. yeni LDAP kullanıcısı)
        cls.other_mgr = User.objects.create_user('ayse', password=PW, first_name='Ayşe')
        UserPermission.objects.create(
            user=cls.other_mgr, permission_type=PermissionType.objects.get(code=PermissionType.ROLE_MANAGEMENT))

    def setUp(self):
        cache.clear()

    def test_manager_cannot_adopt_director(self):
        self.client.login(username='yonetici', password=PW)
        self.assertNotIn(self.direktor, self.client.get('/team/').context['candidates'])
        r = self.client.post('/team/add/', {'user_id': self.direktor.pk})
        self.assertEqual(r.status_code, 403)
        self.direktor.refresh_from_db()
        self.assertIsNone(self.direktor.manager)

    def test_manager_cannot_adopt_own_boss(self):
        # ayse, yonetici'nin ekibine bağlanır; sonra ayse yöneticisini (yonetici) almaya çalışır.
        # yonetici'nin yöneticisi var (direktor) ama zincir kontrolü üst kademeyi de korumalı:
        self.other_mgr.manager = self.yonetici
        self.other_mgr.save(update_fields=['manager'])
        self.assertFalse(can_manage_member(self.other_mgr, self.yonetici))
        self.assertFalse(can_manage_member(self.other_mgr, self.direktor))

    def test_director_cannot_be_demoted_by_manager(self):
        # Eski açık: direktörün yöneticisi olmadığında ROLE_MANAGEMENT sahibi biri onu ekibine alıp
        # yetkilerini boşaltabiliyordu.
        self.client.login(username='ayse', password=PW)
        self.assertEqual(self.client.post('/team/add/', {'user_id': self.direktor.pk}).status_code, 403)
        self.direktor.manager = self.other_mgr          # zorla bağlansa bile...
        self.direktor.save(update_fields=['manager'])
        r = self.client.post(f'/team/{self.direktor.pk}/permissions/', {'permissions': []})
        self.assertEqual(r.status_code, 403)
        self.assertTrue(User.objects.get(pk=self.direktor.pk).is_director)

    def test_director_and_normal_flow_still_work(self):
        mert = User.objects.get(username='mert')
        self.assertTrue(can_manage_member(self.direktor, self.yonetici))
        self.assertTrue(can_manage_member(self.yonetici, mert))
        self.assertFalse(can_manage_member(self.yonetici, self.yonetici))
        self.client.login(username='yonetici', password=PW)
        self.assertEqual(self.client.get(f'/team/{mert.pk}/permissions/').status_code, 200)


@override_settings(MAIL_ENABLED=False)
class AssignmentRestrictionTests(TestCase):
    """H2: Task Management yetkisi olmayan kullanıcı başkasını atayamaz (düzenleme ve toplu işlem dahil)."""

    @classmethod
    def setUpTestData(cls):
        call_command('seed', stdout=open(os.devnull, 'w'))
        cls.mert = User.objects.get(username='mert')        # yalnızca DATA_ACCESS
        cls.berkay = User.objects.get(username='berkay')
        cls.alper = User.objects.get(username='alper')      # TASK_MANAGEMENT

    def setUp(self):
        cache.clear()
        self.task = services.create_task(user=self.mert, title='Kendi işim', description='', severity='LOW',
                                         status='OPEN', assignees=[self.mert])

    def _edit(self, **overrides):
        data = {'title': 'Kendi işim', 'description': '', 'severity': 'LOW', 'status': 'OPEN',
                'assignees': [self.mert.pk], 'due_date': ''}
        data.update(overrides)
        return self.client.post(f'/tasks/{self.task.pk}/', data)

    def test_creator_without_perm_cannot_assign_others_via_edit(self):
        self.client.login(username='mert', password=PW)
        r = self._edit(assignees=[self.mert.pk, self.berkay.pk], title='Phish: click http://evil')
        self.assertEqual(r.status_code, 200)                 # form geçersiz, kaydedilmedi
        self.task.refresh_from_db()
        self.assertEqual(list(self.task.assignees.all()), [self.mert])
        self.assertEqual(self.task.task_title, 'Kendi işim')
        self.assertFalse(Notification.objects.filter(user=self.berkay, task=self.task).exists())

    def test_creator_without_perm_cannot_set_backup(self):
        self.client.login(username='mert', password=PW)
        self.assertNotIn('backup_assignee', self.client.get(f'/tasks/{self.task.pk}/').context['form'].fields)
        self._edit(backup_assignee=self.berkay.pk)
        self.task.refresh_from_db()
        self.assertIsNone(self.task.backup_assignee)

    def test_creator_without_perm_can_still_edit_own_task(self):
        self.client.login(username='mert', password=PW)
        r = self._edit(title='Kendi işim (güncel)', severity='HIGH')
        self.assertEqual(r.status_code, 302)
        self.task.refresh_from_db()
        self.assertEqual((self.task.task_title, self.task.task_severity), ('Kendi işim (güncel)', 'HIGH'))

    def test_bulk_assign_requires_task_management(self):
        self.client.login(username='mert', password=PW)
        self.client.post('/tasks/bulk/', {'ids': [self.task.pk], 'op': 'assign', 'user': self.berkay.pk})
        self.assertFalse(self.task.assignees.filter(pk=self.berkay.pk).exists())

    def test_task_manager_can_assign_anyone(self):
        self.client.login(username='alper', password=PW)
        r = self._edit(assignees=[self.mert.pk, self.berkay.pk], backup_assignee=self.alper.pk)
        self.assertEqual(r.status_code, 302)
        self.task.refresh_from_db()
        self.assertEqual(set(self.task.assignees.all()), {self.mert, self.berkay})
        self.assertEqual(self.task.backup_assignee, self.alper)
