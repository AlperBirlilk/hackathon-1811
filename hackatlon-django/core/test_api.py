import os
from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.authtoken.models import Token

from core.models import Task, User
from core.views import visible_tasks

PASSWORD = 'Cyber2026!'


class ApiTestBase(TestCase):
    @classmethod
    def setUpTestData(cls):
        with open(os.devnull, 'w') as devnull:
            call_command('seed', stdout=devnull)
        cls.users = {u.username: u for u in User.objects.all()}

    def token_for(self, username):
        return Token.objects.get_or_create(user=self.users[username])[0].key

    def api(self, path, username=None, token=None, method='get', **params):
        headers = {}
        if username:
            token = self.token_for(username)
        if token:
            headers['HTTP_AUTHORIZATION'] = f'Bearer {token}'
        return getattr(self.client, method)(path, params or None, **headers)

    def assertError(self, resp, status, code):
        self.assertEqual(resp.status_code, status, resp.content)
        self.assertEqual(resp['Content-Type'], 'application/json')
        body = resp.json()
        self.assertEqual(set(body), {'error'})
        self.assertEqual(body['error']['code'], code)
        self.assertTrue(body['error']['message'])


class ApiAuthTests(ApiTestBase):
    def test_no_token_is_401(self):
        for path in ('/api/me', '/api/tasks', '/api/team', '/api/does-not-exist'):
            self.assertError(self.api(path), 401, 'UNAUTHORIZED')

    def test_bad_token_is_401(self):
        self.assertError(self.api('/api/me', token='nope'), 401, 'UNAUTHORIZED')
        resp = self.client.get('/api/me', HTTP_AUTHORIZATION='Bearer a b')
        self.assertError(resp, 401, 'UNAUTHORIZED')

    def test_expired_token_is_401(self):
        token = Token.objects.create(user=self.users['mert'])
        Token.objects.filter(pk=token.pk).update(created=timezone.now() - timedelta(hours=25))
        resp = self.api('/api/me', token=token.key)
        self.assertError(resp, 401, 'UNAUTHORIZED')
        self.assertIn('süresi dolmuş', resp.json()['error']['message'])

    @override_settings(API_TOKEN_TTL_HOURS=48)
    def test_ttl_is_configurable(self):
        token = Token.objects.create(user=self.users['mert'])
        Token.objects.filter(pk=token.pk).update(created=timezone.now() - timedelta(hours=25))
        self.assertEqual(self.api('/api/me', token=token.key).status_code, 200)

    def test_inactive_user_is_401(self):
        key = self.token_for('mert')
        User.objects.filter(username='mert').update(is_active=False)
        self.assertError(self.api('/api/me', token=key), 401, 'UNAUTHORIZED')

    def test_missing_data_access_is_403_but_me_works(self):
        self.assertError(self.api('/api/tasks', 'alper'), 403, 'FORBIDDEN')
        self.assertError(self.api('/api/dashboard', 'yonetici'), 403, 'FORBIDDEN')
        resp = self.api('/api/me', 'alper')
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.json()['permissions'], ['TASK_MANAGEMENT'])

    def test_session_auth_works(self):
        self.client.login(username='mert', password=PASSWORD)
        self.assertEqual(self.client.get('/api/tasks').status_code, 200)

    def test_post_is_405(self):
        self.assertError(self.api('/api/tasks', 'mert', method='post'), 405, 'METHOD_NOT_ALLOWED')
        self.assertError(self.api('/api/me', 'mert', method='delete'), 405, 'METHOD_NOT_ALLOWED')

    def test_unknown_path_is_json_404(self):
        self.assertError(self.api('/api/nothing', 'mert'), 404, 'NOT_FOUND')


class ApiDataTests(ApiTestBase):
    def test_me_shape(self):
        data = self.api('/api/me', 'direktor').json()
        self.assertEqual(set(data), {'id', 'username', 'displayName', 'title', 'permissions', 'managerId',
                                     'isManager', 'isDirector', 'isOnLeave'})
        self.assertTrue(data['isDirector'])
        self.assertEqual(len(data['permissions']), 5)

    def test_users(self):
        data = self.api('/api/users', 'mert').json()
        self.assertEqual(set(data[0]), {'id', 'username', 'displayName'})
        self.assertIn('mert', {u['username'] for u in data})

    def test_mert_sees_only_visible_tasks(self):
        mert = self.users['mert']
        data = self.api('/api/tasks', 'mert').json()
        expected = set(visible_tasks(mert).values_list('pk', flat=True))
        self.assertEqual({t['id'] for t in data}, expected)
        self.assertLess(len(expected), Task.objects.count())
        # Critical first
        ranks = {'CRITICAL': 0, 'HIGH': 1, 'MEDIUM': 2, 'LOW': 3}
        self.assertEqual([ranks[t['severity']] for t in data], sorted(ranks[t['severity']] for t in data))

    def test_task_summary_keys_camel_case(self):
        task = self.api('/api/tasks', 'direktor').json()[0]
        self.assertEqual(set(task), {'id', 'code', 'title', 'status', 'severity', 'assignees', 'backupAssignee',
                                     'dueDate', 'isOverdue', 'handover', 'modifiedDate'})
        self.assertRegex(task['code'], r'^TSK-\d{4}$')
        self.assertEqual(set(task['assignees'][0]), {'id', 'username', 'displayName'})

    def test_task_detail_and_idor(self):
        mert = self.users['mert']
        hidden = Task.objects.exclude(pk__in=visible_tasks(mert)).first()
        visible = visible_tasks(mert).first()
        self.assertError(self.api(f'/api/tasks/{hidden.pk}', 'mert'), 404, 'NOT_FOUND')
        self.assertError(self.api('/api/tasks/999999', 'mert'), 404, 'NOT_FOUND')
        data = self.api(f'/api/tasks/{visible.pk}', 'mert').json()
        for key in ('description', 'createdBy', 'createDate', 'modifiedBy', 'canEdit', 'canChangeStatus', 'history'):
            self.assertIn(key, data)
        self.assertTrue(data['history'])
        self.assertEqual(set(data['history'][0]), {'id', 'actionType', 'actionDescription', 'actionBy', 'actionDate'})
        dates = [h['actionDate'] for h in data['history']]
        self.assertEqual(dates, sorted(dates, reverse=True))

    def test_no_n_plus_one(self):
        from django.db import connection
        from django.test.utils import CaptureQueriesContext
        key = self.token_for('direktor')
        for path in ('/api/tasks', '/api/dashboard', '/api/team', '/api/activities'):
            self.api(path, token=key)  # warm up
            with CaptureQueriesContext(connection) as ctx:
                self.assertEqual(self.api(path, token=key).status_code, 200)
            self.assertLessEqual(len(ctx), 25, f'{path}: {len(ctx)} queries')
        with CaptureQueriesContext(connection) as small:
            self.api('/api/tasks', token=key, severity='LOW')
        with CaptureQueriesContext(connection) as full:
            self.api('/api/tasks', token=key)
        self.assertEqual(len(small), len(full))

    def test_overdue_filter(self):
        data = self.api('/api/tasks', 'direktor', overdue='true').json()
        self.assertEqual(len(data), 2)
        self.assertTrue(all(t['isOverdue'] and t['status'] != 'DONE' for t in data))

    def test_handover_flag(self):
        # mert is backup on the CVE task whose assignee (aykun) is on leave
        data = self.api('/api/tasks', 'mert', q='CVE-2026').json()
        self.assertEqual(len(data), 1)
        self.assertTrue(data[0]['handover'])

    def test_filters_and_code_search(self):
        task = Task.objects.order_by('pk').first()
        data = self.api('/api/tasks', 'direktor', q=task.code).json()
        self.assertIn(task.pk, [t['id'] for t in data])
        data = self.api('/api/tasks', 'direktor', status='done').json()
        self.assertTrue(data and all(t['status'] == 'DONE' for t in data))
        mert = self.users['mert']
        data = self.api('/api/tasks', 'direktor', assigneeId=mert.pk).json()
        self.assertTrue(data and all(mert.pk in [a['id'] for a in t['assignees']] for t in data))

    def test_invalid_params_are_400(self):
        self.assertError(self.api('/api/tasks', 'mert', status='BOGUS'), 400, 'VALIDATION')
        self.assertError(self.api('/api/tasks', 'mert', severity='x'), 400, 'VALIDATION')
        self.assertError(self.api('/api/tasks', 'mert', assigneeId='abc'), 400, 'VALIDATION')
        self.assertError(self.api('/api/activities', 'mert', scope='all'), 400, 'VALIDATION')

    def test_team_permissions(self):
        self.assertError(self.api('/api/team', 'mert'), 403, 'FORBIDDEN')
        data = self.api('/api/team', 'direktor').json()
        others = User.objects.filter(is_active=True).exclude(username='direktor').count()
        self.assertEqual(len(data), others)
        self.assertEqual(set(data[0]), {'user', 'title', 'isOnLeave', 'permissions', 'openCount',
                                        'progressCount', 'doneCount', 'overdueCount'})

    def test_dashboard(self):
        data = self.api('/api/dashboard', 'direktor').json()
        self.assertEqual(set(data), {'stats', 'pendingTasks', 'doneTasks', 'handoverTasks', 'myActivities',
                                     'team', 'report', 'recentHistory'})
        self.assertEqual(set(data['stats']), {'pending', 'inProgress', 'done', 'overdue', 'critical',
                                              'upcomingActivities'})
        self.assertIsNotNone(data['team'])
        self.assertEqual(set(data['report']), {'bySeverity', 'byStatus'})
        self.assertEqual(set(data['recentHistory'][0]['task']), {'id', 'code', 'title'})
        mert = self.api('/api/dashboard', 'mert').json()
        self.assertIsNone(mert['team'])
        self.assertIsNone(mert['report'])
        self.assertTrue(mert['handoverTasks'])
        self.assertTrue(all(a['joined'] for a in mert['myActivities']))

    def test_activities(self):
        up = self.api('/api/activities', 'mert').json()
        self.assertTrue(up)
        self.assertEqual(set(up[0]), {'id', 'name', 'description', 'date', 'location', 'type', 'participationType',
                                      'contactPerson', 'createdBy', 'attendees', 'joined'})
        dates = [a['date'] for a in up]
        self.assertEqual(dates, sorted(dates))
        past = self.api('/api/activities', 'mert', scope='past').json()
        self.assertTrue(past and all(a['date'] < up[0]['date'] for a in past))
        mine = self.api('/api/activities', 'mert', scope='mine').json()
        self.assertTrue(mine and all(a['joined'] for a in mine))


class DataSharingPageTests(ApiTestBase):
    def login(self, username):
        self.client.login(username=username, password=PASSWORD)

    def test_access(self):
        self.login('mert')
        self.assertEqual(self.client.get(reverse('data_sharing')).status_code, 200)
        self.client.logout()
        self.login('alper')
        self.assertEqual(self.client.get(reverse('data_sharing')).status_code, 403)
        self.assertEqual(self.client.post(reverse('api_token_generate')).status_code, 403)

    def test_generate_shows_token_once_and_replaces(self):
        self.login('mert')
        old = self.token_for('mert')
        resp = self.client.post(reverse('api_token_generate'))
        self.assertEqual(resp.status_code, 200)
        self.assertIn('no-store', resp['Cache-Control'])
        new = Token.objects.get(user=self.users['mert']).key
        self.assertNotEqual(old, new)
        self.assertContains(resp, new)
        self.assertFalse(Token.objects.filter(key=old).exists())
        # Old token no longer works; new one does
        self.assertError(self.api('/api/me', token=old), 401, 'UNAUTHORIZED')
        page = self.client.get(reverse('data_sharing'))
        self.assertNotContains(page, new)
        self.assertContains(page, new[:4] + '…')

    def test_revoke(self):
        self.login('mert')
        key = self.token_for('mert')
        resp = self.client.post(reverse('api_token_revoke'))
        self.assertRedirects(resp, reverse('data_sharing'))
        self.assertFalse(Token.objects.filter(user=self.users['mert']).exists())
        self.assertError(self.api('/api/me', token=key), 401, 'UNAUTHORIZED')

    def test_generate_requires_post(self):
        self.login('mert')
        self.assertEqual(self.client.get(reverse('api_token_generate')).status_code, 405)
        self.assertEqual(self.client.get(reverse('api_token_revoke')).status_code, 405)
