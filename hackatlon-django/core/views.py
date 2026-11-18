import hashlib
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.db.models import Case, Count, IntegerField, Q, Value, When
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import services
from .forms import ActivityForm, ProfileForm, SkillForm, TaskForm, TaskStatusForm
from .models import Activity, PermissionType, Task, TaskHistory, User, UserPermission, UserSkill


# --------------------------------------------------------------------------- helpers

SEVERITY_RANK = Case(
    When(task_severity=Task.SEVERITY_CRITICAL, then=Value(0)),
    When(task_severity=Task.SEVERITY_HIGH, then=Value(1)),
    When(task_severity=Task.SEVERITY_MEDIUM, then=Value(2)),
    default=Value(3), output_field=IntegerField(),
)

def portal_perm_required(code):
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(request, *args, **kwargs):
            if not request.user.has_portal_perm(code):
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return wrapper
    return decorator


def visible_tasks(user):
    qs = Task.objects.all()
    if not user.has_portal_perm(PermissionType.TASK_MANAGEMENT):
        qs = qs.filter(Q(assignees=user) | Q(created_by=user)).distinct()
    return qs


def can_edit_task(user, task):
    return user.has_portal_perm(PermissionType.TASK_MANAGEMENT) or task.created_by_id == user.id


def team_with_stats(manager):
    return (
        manager.team_members.filter(is_active=True)
        .annotate(
            open_count=Count('assigned_tasks', filter=Q(assigned_tasks__task_status=Task.STATUS_OPEN)),
            progress_count=Count('assigned_tasks', filter=Q(assigned_tasks__task_status=Task.STATUS_IN_PROGRESS)),
            done_count=Count('assigned_tasks', filter=Q(assigned_tasks__task_status=Task.STATUS_DONE)),
        )
        .order_by('first_name')
    )


# --------------------------------------------------------------------------- auth

def _client_ip(request):
    return request.META.get('REMOTE_ADDR', 'unknown')


class PortalLoginView(LoginView):
    """Login + basit brute-force koruması (IP + kullanıcı adı bazlı kilitleme)."""

    template_name = 'registration/login.html'
    redirect_authenticated_user = True

    def _key(self):
        username = (self.request.POST.get('username') or '').strip().lower()
        digest = hashlib.sha256(f'{_client_ip(self.request)}|{username}'.encode()).hexdigest()
        return f'login-fail:{digest}'

    def post(self, request, *args, **kwargs):
        if cache.get(self._key(), 0) >= settings.LOGIN_MAX_ATTEMPTS:
            form = self.get_form()
            form.errors.clear()
            form.add_error(None, 'Çok fazla hatalı deneme yapıldı. Hesap geçici olarak kilitlendi; '
                                 f'{settings.LOGIN_LOCKOUT_SECONDS // 60} dakika sonra tekrar deneyin.')
            return self.render_to_response(self.get_context_data(form=form, locked=True))
        return super().post(request, *args, **kwargs)

    def form_invalid(self, form):
        key = self._key()
        attempts = cache.get(key, 0) + 1
        cache.set(key, attempts, settings.LOGIN_LOCKOUT_SECONDS)
        form.errors.clear()
        remaining = max(settings.LOGIN_MAX_ATTEMPTS - attempts, 0)
        form.add_error(None, f'Kullanıcı adı veya parola hatalı. Kalan deneme hakkınız: {remaining}.')
        return super().form_invalid(form)

    def form_valid(self, form):
        cache.delete(self._key())
        return super().form_valid(form)


@require_POST
def logout_view(request):
    logout(request)
    return redirect('login')


# --------------------------------------------------------------------------- dashboard

@login_required
def dashboard(request):
    user = request.user
    my_tasks = user.assigned_tasks.all()
    ctx = {
        'pending_tasks': my_tasks.filter(task_status__in=Task.PENDING_STATUSES)
                                 .annotate(sev_rank=SEVERITY_RANK).order_by('sev_rank', '-modified_date')[:8],
        'done_tasks': my_tasks.filter(task_status=Task.STATUS_DONE)[:8],
        'my_activities': user.activities.filter(activity_date__gte=timezone.now())[:6],
        'stats': {
            'pending': my_tasks.filter(task_status__in=Task.PENDING_STATUSES).count(),
            'done': my_tasks.filter(task_status=Task.STATUS_DONE).count(),
            'critical': my_tasks.filter(task_status__in=Task.PENDING_STATUSES,
                                        task_severity=Task.SEVERITY_CRITICAL).count(),
            'activities': user.activities.filter(activity_date__gte=timezone.now()).count(),
        },
    }
    if user.is_manager:
        ctx['team'] = team_with_stats(user)
    if user.has_portal_perm(PermissionType.REPORT_ANALYSIS):
        total = Task.objects.count() or 1
        sev = dict(Task.objects.values_list('task_severity').annotate(c=Count('id')))
        sta = dict(Task.objects.values_list('task_status').annotate(c=Count('id')))
        ctx['report'] = {
            'severity': [(k, label, sev.get(k, 0), round(sev.get(k, 0) * 100 / total))
                         for k, label in Task.SEVERITY_CHOICES],
            'status': [(k, label, sta.get(k, 0), round(sta.get(k, 0) * 100 / total))
                       for k, label in Task.STATUS_CHOICES],
        }
    ctx['recent_history'] = (
        TaskHistory.objects.filter(task__in=visible_tasks(user))
        .select_related('task', 'action_by')[:8]
    )
    return render(request, 'core/dashboard.html', ctx)


# --------------------------------------------------------------------------- tasks

@login_required
def task_list(request):
    qs = visible_tasks(request.user).prefetch_related('assignees')
    status = request.GET.get('status')
    severity = request.GET.get('severity')
    q = request.GET.get('q', '').strip()
    if status:
        qs = qs.filter(task_status=status)
    if severity:
        qs = qs.filter(task_severity=severity)
    if q:
        qs = qs.filter(Q(task_title__icontains=q) | Q(task_description__icontains=q))
    return render(request, 'core/task_list.html', {
        'tasks': qs, 'status_choices': Task.STATUS_CHOICES, 'severity_choices': Task.SEVERITY_CHOICES,
        'f_status': status, 'f_severity': severity, 'q': q,
    })


@login_required
def task_create(request):
    form = TaskForm(request.POST or None)
    if not request.user.has_portal_perm(PermissionType.TASK_MANAGEMENT):
        # Yetkisi olmayan kullanıcı yalnızca kendine task açabilir
        form.fields['assignees'].queryset = User.objects.filter(pk=request.user.pk)
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        task = services.create_task(
            user=request.user, title=d['title'], description=d['description'],
            severity=d['severity'], status=d['status'], assignees=list(d['assignees']),
        )
        messages.success(request, f'{task.code} oluşturuldu.')
        return redirect('task_detail', pk=task.pk)
    return render(request, 'core/task_form.html', {'form': form, 'is_new': True})


@login_required
def task_detail(request, pk):
    task = get_object_or_404(visible_tasks(request.user).prefetch_related('assignees'), pk=pk)
    editable = can_edit_task(request.user, task)
    form = None
    if editable:
        initial = {
            'title': task.task_title, 'description': task.task_description,
            'severity': task.task_severity, 'status': task.task_status,
            'assignees': task.assignees.all(),
        }
        form = TaskForm(request.POST or None, initial=initial)
        if request.method == 'POST' and form.is_valid():
            d = form.cleaned_data
            changed = services.update_task(
                task, user=request.user, title=d['title'], description=d['description'],
                severity=d['severity'], status=d['status'], assignees=list(d['assignees']),
            )
            messages.success(request, 'Task güncellendi.' if changed else 'Değişiklik yok.')
            return redirect('task_detail', pk=task.pk)
    elif request.method == 'POST':
        raise PermissionDenied
    return render(request, 'core/task_detail.html', {
        'task': task, 'form': form, 'editable': editable,
        'history': task.history.select_related('action_by'),
        'is_assignee': task.assignees.filter(pk=request.user.pk).exists(),
        'status_choices': Task.STATUS_CHOICES,
    })


@login_required
@require_POST
def task_status(request, pk):
    task = get_object_or_404(visible_tasks(request.user), pk=pk)
    if not (can_edit_task(request.user, task) or task.assignees.filter(pk=request.user.pk).exists()):
        raise PermissionDenied
    form = TaskStatusForm(request.POST)
    if form.is_valid():
        if services.update_task(task, user=request.user, status=form.cleaned_data['status']):
            messages.success(request, f'{task.code} durumu güncellendi: {task.get_task_status_display()}')
    nxt = request.POST.get('next')
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return redirect(nxt)
    return redirect('task_detail', pk=task.pk)


# --------------------------------------------------------------------------- activities

@login_required
def activity_list(request):
    now = timezone.now()
    base = Activity.objects.prefetch_related('attendees').select_related('created_by')
    return render(request, 'core/activity_list.html', {
        'upcoming': base.filter(activity_date__gte=now),
        'past': base.filter(activity_date__lt=now).order_by('-activity_date')[:10],
        'my_ids': set(request.user.activities.values_list('id', flat=True)),
    })


@portal_perm_required(PermissionType.ACTIVITY_MANAGEMENT)
def activity_create(request):
    form = ActivityForm(request.POST or None)
    if request.method == 'POST' and form.is_valid():
        activity = form.save(commit=False)
        activity.created_by = request.user
        activity.save()
        form.save_m2m()
        messages.success(request, f'"{activity.activity_name}" etkinliği oluşturuldu.')
        return redirect('activity_list')
    return render(request, 'core/activity_form.html', {'form': form})


@login_required
@require_POST
def activity_toggle_join(request, pk):
    activity = get_object_or_404(Activity, pk=pk)
    if activity.attendees.filter(pk=request.user.pk).exists():
        activity.attendees.remove(request.user)
        messages.info(request, f'"{activity.activity_name}" katılımınız iptal edildi.')
    else:
        activity.attendees.add(request.user)
        messages.success(request, f'"{activity.activity_name}" etkinliğine katıldınız.')
    return redirect('activity_list')


# --------------------------------------------------------------------------- data sharing

@portal_perm_required(PermissionType.DATA_ACCESS)
def data_sharing(request):
    return render(request, 'core/data_sharing.html')


# --------------------------------------------------------------------------- team (yönetici)

@portal_perm_required(PermissionType.ROLE_MANAGEMENT)
def team(request):
    candidates = (User.objects.filter(is_active=True, manager__isnull=True)
                  .exclude(pk=request.user.pk).order_by('first_name'))
    return render(request, 'core/team.html', {
        'team': team_with_stats(request.user).prefetch_related('permissions'),
        'candidates': candidates,
    })


@portal_perm_required(PermissionType.ROLE_MANAGEMENT)
@require_POST
def team_add(request):
    member = get_object_or_404(User, pk=request.POST.get('user_id'), is_active=True, manager__isnull=True)
    if member.pk == request.user.pk:
        raise PermissionDenied
    member.manager = request.user
    member.save(update_fields=['manager'])
    messages.success(request, f'{member.display_name} ekibinize eklendi.')
    return redirect('team')


@portal_perm_required(PermissionType.ROLE_MANAGEMENT)
@require_POST
def team_remove(request, user_id):
    member = get_object_or_404(User, pk=user_id, manager=request.user)
    member.manager = None
    member.save(update_fields=['manager'])
    messages.info(request, f'{member.display_name} ekibinizden çıkarıldı.')
    return redirect('team')


@portal_perm_required(PermissionType.ROLE_MANAGEMENT)
def member_permissions(request, user_id):
    member = get_object_or_404(User, pk=user_id, manager=request.user)
    all_perms = PermissionType.objects.all()
    if request.method == 'POST':
        selected = set(int(i) for i in request.POST.getlist('permissions') if i.isdigit())
        # Yönetici, sahip olmadığı bir yetkiyi başkasına veremez (privilege escalation koruması)
        grantable = {p.id for p in all_perms if request.user.has_portal_perm(p.code)}
        current = set(member.permissions.values_list('id', flat=True))
        to_add = (selected - current) & grantable
        to_remove = (current - selected) & grantable
        UserPermission.objects.filter(user=member, permission_type_id__in=to_remove).delete()
        UserPermission.objects.bulk_create([
            UserPermission(user=member, permission_type_id=pid, granted_by=request.user) for pid in to_add
        ])
        messages.success(request, f'{member.display_name} yetkileri güncellendi '
                                  f'(+{len(to_add)} / -{len(to_remove)}).')
        return redirect('team')
    current = set(member.permissions.values_list('id', flat=True))
    rows = [(p, p.id in current, request.user.has_portal_perm(p.code)) for p in all_perms]
    return render(request, 'core/member_permissions.html', {'member': member, 'rows': rows})


# --------------------------------------------------------------------------- profile

@login_required
def profile(request, user_id=None):
    if user_id and user_id != request.user.pk:
        target = get_object_or_404(User, pk=user_id)
        if not (request.user.is_superuser or target.manager_id == request.user.pk):
            raise PermissionDenied
        own = False
    else:
        target, own = request.user, True

    profile_form = ProfileForm(instance=target)
    skill_form = SkillForm()
    if own and request.method == 'POST':
        if 'add_skill' in request.POST:
            skill_form = SkillForm(request.POST)
            if skill_form.is_valid():
                skill = skill_form.save(commit=False)
                skill.user = target
                skill.save()
                messages.success(request, f'"{skill.skill_name}" eklendi.')
                return redirect('profile')
        else:
            profile_form = ProfileForm(request.POST, instance=target)
            if profile_form.is_valid():
                profile_form.save()
                messages.success(request, 'Profil güncellendi.')
                return redirect('profile')

    return render(request, 'core/profile.html', {
        'target': target, 'own': own, 'profile_form': profile_form, 'skill_form': skill_form,
        'skills': target.skills.filter(kind=UserSkill.SKILL),
        'certs': target.skills.filter(kind=UserSkill.CERTIFICATE),
        'perms': target.permissions.all(),
    })


@login_required
@require_POST
def skill_delete(request, skill_id):
    skill = get_object_or_404(UserSkill, pk=skill_id, user=request.user)
    skill.delete()
    messages.info(request, f'"{skill.skill_name}" silindi.')
    return redirect('profile')
