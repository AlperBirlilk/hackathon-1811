from django.http import HttpResponse
from django.utils import timezone
from django.views.decorators.http import require_GET

from . import reports
from .models import PermissionType
from .views import portal_perm_required

XLSX_TYPE = 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'


def _attachment(content, content_type, ext):
    filename = f'gorev-raporu-{timezone.localdate():%Y%m%d}.{ext}'
    response = HttpResponse(content, content_type=content_type)
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    response['X-Content-Type-Options'] = 'nosniff'
    return response


@portal_perm_required(PermissionType.REPORT_ANALYSIS)
@require_GET
def report_tasks_xlsx(request):
    tasks = reports.filter_tasks(request.user, request.GET)
    return _attachment(reports.build_xlsx(tasks), XLSX_TYPE, 'xlsx')


@portal_perm_required(PermissionType.REPORT_ANALYSIS)
@require_GET
def report_tasks_pdf(request):
    tasks = reports.filter_tasks(request.user, request.GET)
    pdf = reports.build_pdf(tasks, reports.filters_summary(request.GET))
    return _attachment(pdf, 'application/pdf', 'pdf')
