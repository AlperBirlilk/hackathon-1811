import io
import os
from datetime import timedelta

from django.core.management import call_command
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from openpyxl import load_workbook

from core import services
from core.models import Activity, Task, User
from core.reports import HEADERS, filter_tasks, sanitize_cell

XLSX_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def seed():
    with open(os.devnull, 'w') as devnull:
        call_command('seed', stdout=devnull)


@override_settings(MAIL_ENABLED=False)
class ReportTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed()
        cls.berkay = User.objects.get(username='berkay')
        cls.mert = User.objects.get(username='mert')
        cls.yonetici = User.objects.get(username='yonetici')
        cls.aykun = User.objects.get(username='aykun')
        # berkay'ın göremeyeceği task: başkası oluşturdu, başkasına atandı
        cls.hidden = services.create_task(
            user=cls.yonetici, title='Gizli rapor dışı task', description='', severity=Task.SEVERITY_LOW,
            status=Task.STATUS_OPEN, assignees=[cls.aykun])
        # berkay'ın gördüğü, formül enjeksiyonu içeren task
        cls.evil = services.create_task(
            user=cls.yonetici, title='=HYPERLINK("http://x")', description='', severity=Task.SEVERITY_LOW,
            status=Task.STATUS_OPEN, assignees=[cls.berkay])

    def xlsx_rows(self, response):
        ws = load_workbook(io.BytesIO(response.content)).active
        return [[c.value for c in row] for row in ws.iter_rows()]

    def test_requires_report_permission(self):
        self.client.force_login(self.mert)
        for name in ('report_tasks_xlsx', 'report_tasks_pdf'):
            self.assertEqual(self.client.get(reverse(name)).status_code, 403)

    def test_anonymous_redirected_to_login(self):
        r = self.client.get(reverse('report_tasks_xlsx'))
        self.assertEqual(r.status_code, 302)
        self.assertIn('/login/', r['Location'])

    def test_post_not_allowed(self):
        self.client.force_login(self.berkay)
        self.assertEqual(self.client.post(reverse('report_tasks_xlsx')).status_code, 405)

    def test_xlsx_content_type_filename_and_scope(self):
        self.client.force_login(self.berkay)
        r = self.client.get(reverse('report_tasks_xlsx'))
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], XLSX_TYPE)
        today = timezone.localdate().strftime('%Y%m%d')
        self.assertEqual(r['Content-Disposition'], f'attachment; filename="gorev-raporu-{today}.xlsx"')

        rows = self.xlsx_rows(r)
        self.assertEqual(rows[0], HEADERS)
        codes = {row[0] for row in rows[1:]}
        expected = {t.code for t in filter_tasks(self.berkay, {})}
        self.assertEqual(codes, expected)
        self.assertNotIn(self.hidden.code, codes)
        self.assertIn(self.evil.code, codes)

    def test_formula_injection_escaped(self):
        self.client.force_login(self.berkay)
        rows = self.xlsx_rows(self.client.get(reverse('report_tasks_xlsx')))
        evil_row = next(row for row in rows if row[0] == self.evil.code)
        self.assertEqual(evil_row[1], '\'=HYPERLINK("http://x")')
        for prefix in ('=', '+', '-', '@', '\t', '\r'):
            self.assertEqual(sanitize_cell(prefix + 'x'), "'" + prefix + 'x')
        self.assertEqual(sanitize_cell('normal'), 'normal')
        self.assertEqual(sanitize_cell(5), 5)

    def test_overdue_filter_limits_rows(self):
        self.client.force_login(self.berkay)
        all_rows = self.xlsx_rows(self.client.get(reverse('report_tasks_xlsx')))[1:]
        overdue_rows = self.xlsx_rows(self.client.get(reverse('report_tasks_xlsx') + '?overdue=1'))[1:]
        self.assertTrue(overdue_rows)
        self.assertLess(len(overdue_rows), len(all_rows))
        self.assertTrue(all(row[7] == 'Evet' for row in overdue_rows))
        self.assertIn('Ransomware örneği tersine mühendislik', {row[1] for row in overdue_rows})

    def test_status_severity_and_search_filters(self):
        self.client.force_login(self.berkay)
        url = reverse('report_tasks_xlsx')
        rows = self.xlsx_rows(self.client.get(url + '?severity=CRITICAL'))[1:]
        self.assertTrue(rows)
        self.assertTrue(all(row[3] == 'Kritik' for row in rows))
        rows = self.xlsx_rows(self.client.get(url + '?q=phishing'))[1:]
        self.assertEqual([row[1] for row in rows], ['Phishing kampanyası analizi'])
        rows = self.xlsx_rows(self.client.get(url + '?status=DONE'))[1:]
        self.assertEqual(rows, [])

    def test_seed_has_two_overdue_tasks_for_director(self):
        director = User.objects.get(username='direktor')
        self.assertEqual(filter_tasks(director, {'overdue': 'true'}).count(), 2)

    def test_pdf(self):
        self.client.force_login(self.berkay)
        r = self.client.get(reverse('report_tasks_pdf') + '?overdue=1&q=Ransomware')
        self.assertEqual(r.status_code, 200)
        self.assertEqual(r['Content-Type'], 'application/pdf')
        today = timezone.localdate().strftime('%Y%m%d')
        self.assertEqual(r['Content-Disposition'], f'attachment; filename="gorev-raporu-{today}.pdf"')
        self.assertTrue(r.content.startswith(b'%PDF'))

    def test_pdf_empty_result(self):
        self.client.force_login(self.berkay)
        r = self.client.get(reverse('report_tasks_pdf') + '?q=yokboylebirtask')
        self.assertEqual(r.status_code, 200)
        self.assertTrue(r.content.startswith(b'%PDF'))


@override_settings(MAIL_ENABLED=False)
class ActivityFieldsTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        seed()
        cls.aykun = User.objects.get(username='aykun')
        cls.yonetici = User.objects.get(username='yonetici')
        cls.mert = User.objects.get(username='mert')

    def test_form_renders_new_fields(self):
        for user in (self.aykun, self.yonetici):
            self.client.force_login(user)
            r = self.client.get(reverse('activity_create'))
            self.assertEqual(r.status_code, 200)
            for name in ('activity_type', 'participation_type', 'contact_person'):
                self.assertContains(r, f'name="{name}"')
            self.assertContains(r, 'Etkinlik türü')
            self.assertContains(r, 'Konferans')
            self.assertContains(r, 'Kurumsal')
            self.assertContains(r, '>Yok<')

    def test_create_with_new_fields(self):
        self.client.force_login(self.aykun)
        date = (timezone.localtime() + timedelta(days=3)).strftime('%Y-%m-%dT%H:%M')
        r = self.client.post(reverse('activity_create'), {
            'activity_name': 'Yeni Konferans', 'activity_description': '', 'activity_date': date,
            'location': 'Online', 'activity_type': Activity.TYPE_CONFERENCE,
            'participation_type': Activity.PARTICIPATION_CORPORATE, 'contact_person': self.mert.pk,
            'attendees': [self.mert.pk],
        })
        self.assertRedirects(r, reverse('activity_list'), fetch_redirect_response=False)
        a = Activity.objects.get(activity_name='Yeni Konferans')
        self.assertEqual(a.activity_type, Activity.TYPE_CONFERENCE)
        self.assertEqual(a.participation_type, Activity.PARTICIPATION_CORPORATE)
        self.assertEqual(a.contact_person, self.mert)

        r = self.client.get(reverse('activity_list'))
        self.assertContains(r, f'id="activity-{a.pk}"')
        self.assertContains(r, 'Konferans')
        self.assertContains(r, 'Kurumsal')
        self.assertContains(r, f'İletişim: {self.mert.display_name}')

    def test_contact_person_optional(self):
        self.client.force_login(self.aykun)
        date = (timezone.localtime() + timedelta(days=3)).strftime('%Y-%m-%dT%H:%M')
        self.client.post(reverse('activity_create'), {
            'activity_name': 'İletişimsiz', 'activity_date': date, 'activity_type': Activity.TYPE_OTHER,
            'participation_type': Activity.PARTICIPATION_INDIVIDUAL,
        })
        self.assertIsNone(Activity.objects.get(activity_name='İletişimsiz').contact_person)

    def test_type_fields_default_when_omitted(self):
        self.client.force_login(self.aykun)
        date = (timezone.localtime() + timedelta(days=3)).strftime('%Y-%m-%dT%H:%M')
        r = self.client.post(reverse('activity_create'), {'activity_name': 'Eski istemci', 'activity_date': date})
        self.assertEqual(r.status_code, 302)
        a = Activity.objects.get(activity_name='Eski istemci')
        self.assertEqual(a.activity_type, Activity.TYPE_OTHER)
        self.assertEqual(a.participation_type, Activity.PARTICIPATION_INDIVIDUAL)

    def test_invalid_type_rejected(self):
        self.client.force_login(self.aykun)
        date = (timezone.localtime() + timedelta(days=3)).strftime('%Y-%m-%dT%H:%M')
        r = self.client.post(reverse('activity_create'), {
            'activity_name': 'Hatalı', 'activity_date': date, 'activity_type': 'HACK'})
        self.assertEqual(r.status_code, 200)
        self.assertFalse(Activity.objects.filter(activity_name='Hatalı').exists())
