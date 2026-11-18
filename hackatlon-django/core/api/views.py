"""Read-only API endpoints. Every query goes through the same scoping helpers as the HTML views."""
import re

from django.db.models import Count, Prefetch, Q
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework.decorators import api_view, permission_classes
from rest_framework.exceptions import NotFound
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from core.models import Activity, PermissionType, Task, TaskHistory, User
from core.views import (
    SEVERITY_RANK, handover_tasks_for, my_tasks_for, team_with_stats, visible_tasks,
)

from . import serializers as s
from .exceptions import ApiValidationError
from .permissions import HasDataAccess, HasRoleManagement

DATA = [IsAuthenticated, HasDataAccess]
CODE_RE = re.compile(r'^TSK-?0*(\d{1,9})$', re.IGNORECASE)
TRUE_VALUES = {'true', '1', 'yes'}
FALSE_VALUES = {'false', '0', 'no'}


def _task_qs(qs):
    return qs.select_related('backup_assignee').prefetch_related('assignees')


def _by_priority(qs):
    return qs.annotate(sev_rank=SEVERITY_RANK).order_by('sev_rank', '-modified_date')


def _activity_qs():
    return Activity.objects.select_related('contact_person', 'created_by').prefetch_related('attendees')


def _choice_param(request, name, choices, label):
    value = (request.query_params.get(name) or '').strip()
    if not value:
        return None
    value = value.upper()
    if value not in dict(choices):
        allowed = ', '.join(k for k, _ in choices)
        raise ApiValidationError(f'Geçersiz {label} değeri. Geçerli değerler: {allowed}.')
    return value


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def me(request):
    return Response(s.me(request.user))


@api_view(['GET'])
@permission_classes(DATA)
def users(request):
    qs = User.objects.filter(is_active=True).order_by('first_name', 'last_name', 'username')
    return Response([s.user_ref(u) for u in qs])


@api_view(['GET'])
@permission_classes(DATA)
def tasks(request):
    user = request.user
    qs = visible_tasks(user)

    status = _choice_param(request, 'status', Task.STATUS_CHOICES, 'durum (status)')
    severity = _choice_param(request, 'severity', Task.SEVERITY_CHOICES, 'önem (severity)')
    if status:
        qs = qs.filter(task_status=status)
    if severity:
        qs = qs.filter(task_severity=severity)

    assignee = (request.query_params.get('assigneeId') or '').strip()
    if assignee:
        if not assignee.isdigit():
            raise ApiValidationError('assigneeId pozitif bir tam sayı olmalı.')
        qs = qs.filter(pk__in=Task.objects.filter(assignees__pk=int(assignee)).values('pk'))

    overdue = (request.query_params.get('overdue') or '').strip().lower()
    if overdue and overdue not in TRUE_VALUES | FALSE_VALUES:
        raise ApiValidationError('overdue yalnızca true veya false olabilir.')
    if overdue in TRUE_VALUES:
        qs = qs.exclude(task_status=Task.STATUS_DONE).filter(due_date__lt=timezone.now())

    q = (request.query_params.get('q') or '').strip()[:200]
    if q:
        qs = qs.filter(_text_query(q))

    rows = _by_priority(_task_qs(qs))
    return Response([s.task_summary(t, user) for t in rows])


def _text_query(q):
    cond = Q(task_title__icontains=q) | Q(task_description__icontains=q)
    m = CODE_RE.match(q)
    if m:
        cond |= Q(pk=int(m.group(1)))
    return cond


@api_view(['GET'])
@permission_classes(DATA)
def task_detail(request, pk):
    qs = _task_qs(visible_tasks(request.user)).select_related('created_by', 'modified_by').prefetch_related(
        Prefetch('history', queryset=TaskHistory.objects.select_related('action_by')))
    task = get_object_or_404(qs, pk=pk)  # not visible -> 404 (existence not leaked)
    return Response(s.task_detail(task, request.user))


@api_view(['GET'])
@permission_classes(DATA)
def dashboard(request):
    user = request.user
    now = timezone.now()
    mine = my_tasks_for(user)
    pending = mine.filter(task_status__in=Task.PENDING_STATUSES)
    upcoming = user.activities.filter(activity_date__gte=now)

    stats = {
        'pending': pending.count(),
        'inProgress': mine.filter(task_status=Task.STATUS_IN_PROGRESS).count(),
        'done': mine.filter(task_status=Task.STATUS_DONE).count(),
        'overdue': pending.filter(due_date__lt=now).count(),
        'critical': pending.filter(task_severity=Task.SEVERITY_CRITICAL).count(),
        'upcomingActivities': upcoming.count(),
    }
    pending_tasks = _by_priority(_task_qs(pending))[:8]
    done_tasks = _task_qs(mine.filter(task_status=Task.STATUS_DONE)).order_by('-modified_date')[:8]
    handover = _by_priority(_task_qs(handover_tasks_for(user)))
    activities = (Activity.objects.filter(pk__in=upcoming.values('pk'))
                  .select_related('contact_person', 'created_by').prefetch_related('attendees')
                  .order_by('activity_date')[:6])

    team = None
    if user.is_manager:
        team = [s.team_member(m) for m in team_with_stats(user).prefetch_related('permissions')]

    report = None
    if user.has_portal_perm(PermissionType.REPORT_ANALYSIS):
        # HTML dashboard ile aynı: dağılım görünürlük kuralına göre scope edilir
        base = Task.objects.filter(pk__in=visible_tasks(user).values('pk'))
        total = base.count() or 1
        sev = dict(base.values_list('task_severity').annotate(c=Count('id')))
        sta = dict(base.values_list('task_status').annotate(c=Count('id')))
        report = {
            'bySeverity': [{'key': k, 'count': sev.get(k, 0), 'percent': round(sev.get(k, 0) * 100 / total)}
                           for k, _ in Task.SEVERITY_CHOICES],
            'byStatus': [{'key': k, 'count': sta.get(k, 0), 'percent': round(sta.get(k, 0) * 100 / total)}
                         for k, _ in Task.STATUS_CHOICES],
        }

    recent = (TaskHistory.objects.filter(task__in=visible_tasks(user))
              .select_related('task', 'action_by')[:8])

    return Response({
        'stats': stats,
        'pendingTasks': [s.task_summary(t, user) for t in pending_tasks],
        'doneTasks': [s.task_summary(t, user) for t in done_tasks],
        'handoverTasks': [s.task_summary(t, user) for t in handover],
        'myActivities': [s.activity_summary(a, user) for a in activities],
        'team': team,
        'report': report,
        'recentHistory': [s.history_with_task(h) for h in recent],
    })


@api_view(['GET'])
@permission_classes([IsAuthenticated, HasDataAccess, HasRoleManagement])
def team(request):
    members = team_with_stats(request.user).prefetch_related('permissions')
    return Response([s.team_member(m) for m in members])


@api_view(['GET'])
@permission_classes(DATA)
def activities(request):
    user = request.user
    now = timezone.now()
    scope = (request.query_params.get('scope') or 'upcoming').strip().lower()
    base = _activity_qs()
    if scope == 'upcoming':
        qs = base.filter(activity_date__gte=now).order_by('activity_date')
    elif scope == 'past':
        qs = base.filter(activity_date__lt=now).order_by('-activity_date')[:10]
    elif scope == 'mine':
        qs = base.filter(pk__in=user.activities.values('pk')).order_by('activity_date')
    else:
        raise ApiValidationError('Geçersiz scope değeri. Geçerli değerler: upcoming, past, mine.')
    return Response([s.activity_summary(a, user) for a in qs])


@api_view(['GET'])
@permission_classes([IsAuthenticated])
def not_found(request, *args, **kwargs):
    raise NotFound()
