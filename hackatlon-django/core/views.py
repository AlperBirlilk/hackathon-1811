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
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils import timezone
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import notifications, services
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
    """TASK_MANAGEMENT: tüm task'lar; diğerleri: ana/yedek sorumlusu olduğu veya oluşturduğu task'lar."""
    qs = Task.objects.all()
    if not user.has_portal_perm(PermissionType.TASK_MANAGEMENT):
        qs = qs.filter(Q(assignees=user) | Q(backup_assignee=user) | Q(created_by=user)).distinct()
    return qs


def my_tasks_for(user):
    """Dashboard 'İşlerim': bana atanan veya benim oluşturduğum task'lar."""
    return Task.objects.filter(pk__in=Task.objects.filter(Q(assignees=user) | Q(created_by=user)).values('pk'))


def handover_tasks_for(user):
    """Devralınan işler: yedek sorumlusu olduğum, ana sorumlularından biri izinli, tamamlanmamış task'lar."""
    return Task.objects.filter(pk__in=Task.objects.filter(
        backup_assignee=user, assignees__is_on_leave=True,
    ).exclude(task_status=Task.STATUS_DONE).values('pk'))


def is_handover(task, user):
    """Task, bu kullanıcı için yedek sorumlu olarak devralınmış mı (prefetch edilmiş assignees ile çalışır)."""
    return (task.backup_assignee_id == user.id and task.task_status != Task.STATUS_DONE
            and any(a.is_on_leave for a in task.assignees.all()))


def can_edit_task(user, task):
    return user.has_portal_perm(PermissionType.TASK_MANAGEMENT) or task.created_by_id == user.id


def can_change_status(user, task):
    return (can_edit_task(user, task) or task.backup_assignee_id == user.id
            or task.assignees.filter(pk=user.pk).exists())


def wants_json(request):
    return request.headers.get('x-requested-with') == 'XMLHttpRequest'


def safe_next(request, fallback, *args):
    nxt = request.POST.get('next') or request.GET.get('next')
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()},
                                               require_https=request.is_secure()):
        return redirect(nxt)
    return redirect(fallback, *args)


def task_json(task):
    return {
        'id': task.pk, 'code': task.code, 'title': task.task_title,
        'severity': task.task_severity, 'severity_label': task.get_task_severity_display(),
        'status': task.task_status, 'status_label': task.get_task_status_display(),
        'due_date': timezone.localtime(task.due_date).isoformat() if task.due_date else None,
        'is_overdue': task.is_overdue,
        'url': reverse('task_detail', args=[task.pk]),
    }


def overdue_q():
    """Gecikmiş: tamamlanmamış ve son tarihi geçmiş task'lar."""
    return Q(task_status__in=Task.PENDING_STATUSES, due_date__lt=timezone.now())


def can_manage_member(caller, target):
    """Ekibe alma / yetki düzenleme izni (hiyerarşi koruması).

    Kimse kendini yönetemez; superuser'ı yalnızca superuser yönetir. Direktör herkesi yönetir.
    Direktör olmayan biri direktörleri ve kendi yönetici zincirindeki kişileri (üstlerini) yönetemez.
    """
    if target.pk == caller.pk or (target.is_superuser and not caller.is_superuser):
        return False
    if caller.is_director:
        return True
    if target.is_director:
        return False
    boss, seen = caller.manager, set()
    while boss is not None and boss.pk not in seen:
        if boss.pk == target.pk:
            return False
        seen.add(boss.pk)
        boss = boss.manager
    return True


def restrict_task_form(form, user, task=None):
    """TASK_MANAGEMENT yoksa: yalnızca kendini atayabilir; mevcut atananları/yedeği koruyabilir
    veya kaldırabilir ama başka birini ekleyemez (task_create ile aynı kural, düzenlemede de)."""
    if user.has_portal_perm(PermissionType.TASK_MANAGEMENT):
        return
    allowed = Q(pk=user.pk)
    if task is not None:
        allowed |= Q(pk__in=task.assignees.values('pk'))
    form.fields['assignees'].queryset = User.objects.filter(allowed, is_active=True).order_by('first_name')
    if task is not None and task.backup_assignee_id:
        form.fields['backup_assignee'].queryset = User.objects.filter(pk=task.backup_assignee_id)
    else:
        del form.fields['backup_assignee']


def team_queryset_for(user):
    """Ekibim: direktör (tüm yetkiler) herkesi, yönetici kendi ekibini görür."""
    if user.is_director:
        return User.objects.filter(is_active=True).exclude(pk=user.pk)
    return user.team_members.filter(is_active=True)


def team_with_stats(manager):
    now = timezone.now()
    return (
        team_queryset_for(manager)
        .annotate(
            open_count=Count('assigned_tasks', filter=Q(assigned_tasks__task_status=Task.STATUS_OPEN),
                             distinct=True),
            progress_count=Count('assigned_tasks', filter=Q(assigned_tasks__task_status=Task.STATUS_IN_PROGRESS),
                                 distinct=True),
            done_count=Count('assigned_tasks', filter=Q(assigned_tasks__task_status=Task.STATUS_DONE),
                             distinct=True),
            overdue_count=Count('assigned_tasks', filter=Q(assigned_tasks__task_status__in=Task.PENDING_STATUSES,
                                                           assigned_tasks__due_date__lt=now), distinct=True),
        )
        .order_by('first_name', 'username')
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
    # İşlerim: bana atanan veya benim oluşturduğum tasklar
    my_tasks = my_tasks_for(user)
    by_priority = my_tasks.annotate(sev_rank=SEVERITY_RANK).order_by('sev_rank', '-modified_date')
    lanes = [
        (Task.STATUS_OPEN, 'Yapılacak', by_priority.filter(task_status=Task.STATUS_OPEN)),
        (Task.STATUS_IN_PROGRESS, 'Devam ediyor', by_priority.filter(task_status=Task.STATUS_IN_PROGRESS)),
        (Task.STATUS_DONE, 'Tamamlandı', my_tasks.filter(task_status=Task.STATUS_DONE)
         .order_by('-modified_date')[:15]),
    ]
    ctx = {
        'lanes': [(key, label, list(qs.prefetch_related('assignees'))) for key, label, qs in lanes],
        'my_activities': user.activities.filter(activity_date__gte=timezone.now())[:6],
        'stats': {
            'pending': my_tasks.filter(task_status__in=Task.PENDING_STATUSES).count(),
            'done': my_tasks.filter(task_status=Task.STATUS_DONE).count(),
            'critical': my_tasks.filter(task_status__in=Task.PENDING_STATUSES,
                                        task_severity=Task.SEVERITY_CRITICAL).count(),
            'activities': user.activities.filter(activity_date__gte=timezone.now()).count(),
            'overdue': my_tasks.filter(overdue_q()).count(),
        },
        'handover': list(
            handover_tasks_for(user).annotate(sev_rank=SEVERITY_RANK).order_by('sev_rank', 'due_date')
            .prefetch_related('assignees')
        ),
    }
    if user.is_manager:
        ctx['team'] = team_with_stats(user)
    if user.has_portal_perm(PermissionType.REPORT_ANALYSIS):
        task_count = Task.objects.count()
        total = task_count or 1
        sev = dict(Task.objects.values_list('task_severity').annotate(c=Count('id')))
        sta = dict(Task.objects.values_list('task_status').annotate(c=Count('id')))
        ctx['report'] = {
            'total': task_count,
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
    qs = visible_tasks(request.user).select_related('backup_assignee').prefetch_related('assignees')
    status = request.GET.get('status')
    severity = request.GET.get('severity')
    overdue = request.GET.get('overdue') == '1'
    q = request.GET.get('q', '').strip()
    if status:
        qs = qs.filter(task_status=status)
    if severity:
        qs = qs.filter(task_severity=severity)
    if overdue:
        qs = qs.filter(overdue_q())
    if q:
        qs = qs.filter(Q(task_title__icontains=q) | Q(task_description__icontains=q))
    return render(request, 'core/task_list.html', {
        'tasks': qs, 'status_choices': Task.STATUS_CHOICES, 'severity_choices': Task.SEVERITY_CHOICES,
        'f_status': status, 'f_severity': severity, 'f_overdue': overdue, 'q': q,
        'users': User.objects.filter(is_active=True).order_by('first_name', 'username'),
    })


@login_required
def task_create(request):
    form = TaskForm(request.POST or None, initial={'assignees': [request.user.pk]})
    # Yetkisi olmayan kullanıcı yalnızca kendine task açabilir ve yedek atayamaz
    restrict_task_form(form, request.user)
    if request.method == 'POST' and form.is_valid():
        d = form.cleaned_data
        task = services.create_task(
            user=request.user, title=d['title'], description=d['description'],
            severity=d['severity'], status=d['status'], assignees=list(d['assignees']),
            due_date=d.get('due_date'), backup_assignee=d.get('backup_assignee'),
        )
        if wants_json(request):
            return JsonResponse({'ok': True, 'message': f'{task.code} oluşturuldu.', 'task': task_json(task)})
        messages.success(request, f'{task.code} oluşturuldu.')
        return redirect('task_create')
    if request.method == 'POST' and wants_json(request):
        return JsonResponse({'ok': False, 'errors': form.errors.get_json_data()}, status=400)
    return render(request, 'core/task_form.html', {
        'form': form,
        'recent': Task.objects.filter(created_by=request.user).order_by('-id')[:8],
    })


@login_required
def task_detail(request, pk):
    task = get_object_or_404(
        visible_tasks(request.user).select_related('backup_assignee').prefetch_related('assignees'), pk=pk)
    editable = can_edit_task(request.user, task)
    form = None
    if editable:
        initial = {
            'title': task.task_title, 'description': task.task_description,
            'severity': task.task_severity, 'status': task.task_status,
            'assignees': task.assignees.all(),
            'due_date': (timezone.localtime(task.due_date).strftime('%Y-%m-%dT%H:%M')
                         if task.due_date else None),
            'backup_assignee': task.backup_assignee_id,
        }
        form = TaskForm(request.POST or None, initial=initial)
        restrict_task_form(form, request.user, task)
        if request.method == 'POST' and form.is_valid():
            d = form.cleaned_data
            changes = dict(title=d['title'], description=d['description'], severity=d['severity'],
                           status=d['status'], assignees=list(d['assignees']), due_date=d['due_date'])
            if 'backup_assignee' in form.fields:
                changes['backup_assignee'] = d['backup_assignee']
            changed = services.update_task(task, user=request.user, **changes)
            messages.success(request, 'Task güncellendi.' if changed else 'Değişiklik yok.')
            return redirect('task_detail', pk=task.pk)
    elif request.method == 'POST':
        raise PermissionDenied
    return render(request, 'core/task_detail.html', {
        'task': task, 'form': form, 'editable': editable,
        'history': task.history.select_related('action_by'),
        'is_assignee': task.assignees.filter(pk=request.user.pk).exists(),
        'can_status': can_change_status(request.user, task),
        'is_handover': is_handover(task, request.user),
        'status_choices': Task.STATUS_CHOICES,
    })


@login_required
@require_POST
def task_status(request, pk):
    task = get_object_or_404(visible_tasks(request.user), pk=pk)
    if not can_change_status(request.user, task):
        if wants_json(request):
            return JsonResponse({'ok': False, 'error': 'Bu taskın durumunu değiştirme yetkiniz yok.'}, status=403)
        raise PermissionDenied
    form = TaskStatusForm(request.POST)
    if not form.is_valid():
        if wants_json(request):
            return JsonResponse({'ok': False, 'error': 'Geçersiz durum.'}, status=400)
        return redirect('task_detail', pk=task.pk)
    changed = services.update_task(task, user=request.user, status=form.cleaned_data['status'])
    if wants_json(request):
        return JsonResponse({'ok': True, 'changed': changed, 'task': task_json(task)})
    if changed:
        messages.success(request, f'{task.code} durumu güncellendi: {task.get_task_status_display()}')
    return safe_next(request, 'task_detail', task.pk)


BULK_LABELS = {'status': 'durum', 'severity': 'önem', 'assign': 'atama', 'unassign': 'atama'}


@login_required
@require_POST
def task_bulk(request):
    """Seçili tasklara toplu işlem: status:<X>, severity:<X>, assign, unassign."""
    user = request.user
    ids = [int(i) for i in request.POST.getlist('ids') if i.isdigit()]
    kind, _, value = request.POST.get('op', '').partition(':')
    valid = {'status': dict(Task.STATUS_CHOICES), 'severity': dict(Task.SEVERITY_CHOICES)}
    target = None
    if kind in ('assign', 'unassign'):
        uid = request.POST.get('user', '')
        target = User.objects.filter(pk=int(uid), is_active=True).first() if uid.isdigit() else None
    if (not ids or kind not in BULK_LABELS or (kind in valid and value not in valid[kind])
            or (kind in ('assign', 'unassign') and target is None)):
        messages.error(request, 'Toplu işlem için en az bir task ve geçerli bir işlem seçin.')
        return safe_next(request, 'task_list')
    if kind in ('assign', 'unassign') and not user.has_portal_perm(PermissionType.TASK_MANAGEMENT):
        # Atama kısıtı task_create / task_detail ile aynı: başkasını yalnızca Task Management atayabilir
        messages.error(request, 'Kişi ekleme/çıkarma için Task Management yetkisi gerekir.')
        return safe_next(request, 'task_list')

    changed = skipped = 0
    for task in visible_tasks(user).filter(pk__in=ids).prefetch_related('assignees'):
        if kind == 'status':
            if not can_change_status(user, task):
                skipped += 1
                continue
            changed += services.update_task(task, user=user, status=value)
            continue
        if not can_edit_task(user, task):
            skipped += 1
            continue
        if kind == 'severity':
            changed += services.update_task(task, user=user, severity=value)
        else:
            current = set(task.assignees.all())
            new = current | {target} if kind == 'assign' else current - {target}
            changed += services.update_task(task, user=user, assignees=list(new))

    msg = f'{changed} taskın {BULK_LABELS[kind]} bilgisi güncellendi.'
    if skipped:
        msg += f' Yetkiniz olmadığı için {skipped} task atlandı.'
    (messages.warning if skipped else messages.success)(request, msg)
    return safe_next(request, 'task_list')


# --------------------------------------------------------------------------- activities

@login_required
def activity_list(request):
    now = timezone.now()
    base = Activity.objects.prefetch_related('attendees').select_related('created_by', 'contact_person')
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
        notifications.notify_activity_invited(activity, activity.attendees.all(), actor=request.user)
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


# --------------------------------------------------------------------------- team (yönetici)

@portal_perm_required(PermissionType.ROLE_MANAGEMENT)
def team(request):
    candidates = [u for u in User.objects.filter(is_active=True, manager__isnull=True)
                  .exclude(pk=request.user.pk).prefetch_related('permissions').order_by('first_name')
                  if can_manage_member(request.user, u)]
    return render(request, 'core/team.html', {
        'team': team_with_stats(request.user).prefetch_related('permissions'),
        'candidates': candidates,
    })


@portal_perm_required(PermissionType.ROLE_MANAGEMENT)
@require_POST
def team_add(request):
    member = get_object_or_404(User, pk=request.POST.get('user_id'), is_active=True, manager__isnull=True)
    if not can_manage_member(request.user, member):
        raise PermissionDenied   # direktör / üst yönetici / kendisi ekibe alınamaz
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
    # Yönetici kendi ekibini, direktör herkesi düzenler; kimse kendi yetkilerini düzenleyemez
    member = get_object_or_404(team_queryset_for(request.user), pk=user_id)
    if not can_manage_member(request.user, member):
        raise PermissionDenied   # kendi yetkileri, direktör veya üst yönetici düzenlenemez
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
        if not (request.user.is_director or target.manager_id == request.user.pk):
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
