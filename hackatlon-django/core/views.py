import hashlib
from functools import wraps

from django.conf import settings
from django.contrib import messages
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required
from django.contrib.auth.views import LoginView
from django.core.cache import cache
from django.core.exceptions import PermissionDenied
from django.http import Http404, StreamingHttpResponse
from django.shortcuts import redirect, render
from django.utils.http import url_has_allowed_host_and_scheme
from django.views.decorators.http import require_POST

from . import api_client
from .api_client import ApiError
from .forms import ActivityForm, ProfileForm, SkillForm, TaskForm, TaskStatusForm
from .templatetags.portal_tags import LABELS, SEVERITY_CHOICES, STATUS_CHOICES


# --------------------------------------------------------------------------- helpers

def portal_perm_required(code):
    """login + session'daki Me yetkileri (Java'dan). Asıl kontrol yine Java'da."""
    def decorator(view):
        @wraps(view)
        @login_required
        def wrapper(request, *args, **kwargs):
            if not api_client.has_perm(request, code):
                raise PermissionDenied
            return view(request, *args, **kwargs)
        return wrapper
    return decorator


def raise_for_api(e):
    """404 → Http404, 403 → PermissionDenied; diğerleri çağırana bırakılır."""
    if e.status == 404:
        raise Http404(e.message)
    if e.status == 403:
        raise PermissionDenied(e.message)


def _safe_next(request, default):
    nxt = request.POST.get('next')
    if nxt and url_has_allowed_host_and_scheme(nxt, allowed_hosts={request.get_host()}):
        return redirect(nxt)
    return redirect(default)


def _users(request):
    try:
        return api_client.list_users(request)
    except ApiError as e:
        messages.error(request, e.message)
        return []


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
        # Önce Java ile senkronize ol; backend'e ulaşılamıyorsa oturum açma.
        try:
            me = api_client.sync_user(form.get_user())
        except api_client.ApiError as e:
            form.add_error(None, e.message if e.status != 403 else 'Hesabınız pasif durumda.')
            return self.render_to_response(self.get_context_data(form=form))
        cache.delete(self._key())
        response = super().form_valid(form)   # login() session'ı yeniler; JWT ondan sonra yazılır
        self.request.session[api_client.SESSION_JWT] = api_client.issue_jwt(me)
        self.request.session[api_client.SESSION_ME] = me
        return response



@require_POST
def logout_view(request):
    logout(request)
    return redirect('login')


# --------------------------------------------------------------------------- dashboard

@login_required
def dashboard(request):
    try:
        data = api_client.dashboard(request)
    except ApiError as e:
        messages.error(request, e.message)
        data = {}
    return render(request, 'core/dashboard.html', {
        'stats': data.get('stats') or {},
        'pending_tasks': data.get('pendingTasks') or [],
        'done_tasks': data.get('doneTasks') or [],
        'handover_tasks': data.get('handoverTasks') or [],
        'my_activities': data.get('myActivities') or [],
        'team': data.get('team'),
        'report': data.get('report'),
        'recent_history': data.get('recentHistory') or [],
    })


# --------------------------------------------------------------------------- tasks

def _task_filters(request):
    return {
        'status': request.GET.get('status') or None,
        'severity': request.GET.get('severity') or None,
        'q': request.GET.get('q', '').strip() or None,
        'assignee_id': request.GET.get('assignee') or None,
        'overdue': request.GET.get('overdue') == '1',
    }


@login_required
def task_list(request):
    f = _task_filters(request)
    try:
        tasks = api_client.list_tasks(request, **f)
    except ApiError as e:
        messages.error(request, e.message)
        tasks = []
    return render(request, 'core/task_list.html', {
        'tasks': tasks, 'status_choices': STATUS_CHOICES, 'severity_choices': SEVERITY_CHOICES,
        'f_status': f['status'], 'f_severity': f['severity'], 'q': f['q'] or '', 'f_overdue': f['overdue'],
        'filter_query': request.GET.urlencode(),
    })


@login_required
def task_create(request):
    users = _users(request)
    if not api_client.has_perm(request, 'TASK_MANAGEMENT'):
        # Yetkisi olmayan kullanıcı yalnızca kendine task açabilir (Java da zorlar)
        my_id = api_client.session_me(request).get('id')
        assignable = [u for u in users if u['id'] == my_id]
    else:
        assignable = users
    form = TaskForm(request.POST or None, users=assignable)
    form.fields['backup_assignee'].choices = [('', '— Yok —')] + [
        (str(u['id']), u.get('displayName') or u['username']) for u in users]
    if request.method == 'POST' and form.is_valid():
        try:
            task = api_client.create_task(request, form.to_api())
        except ApiError as e:
            raise_for_api(e)
            messages.error(request, e.message)
        else:
            messages.success(request, f"{task['code']} oluşturuldu.")
            return redirect('task_detail', pk=task['id'])
    return render(request, 'core/task_form.html', {'form': form, 'is_new': True})


@login_required
def task_detail(request, pk):
    try:
        task = api_client.get_task(request, pk)
    except ApiError as e:
        raise_for_api(e)
        messages.error(request, e.message)
        return redirect('task_list')
    editable = bool(task.get('canEdit'))
    form = None
    if editable:
        due = task.get('dueDate')
        initial = {
            'title': task.get('title'), 'description': task.get('description'),
            'severity': task.get('severity'), 'status': task.get('status'),
            'assignees': [str(u['id']) for u in task.get('assignees') or []],
            'backup_assignee': str(task['backupAssignee']['id']) if task.get('backupAssignee') else '',
            'due_date': due if not isinstance(due, str) else None,
        }
        form = TaskForm(request.POST or None, initial=initial, users=_users(request))
        if request.method == 'POST' and form.is_valid():
            try:
                api_client.update_task(request, pk, form.to_api())
            except ApiError as e:
                raise_for_api(e)
                messages.error(request, e.message)
            else:
                messages.success(request, 'Task güncellendi.')
                return redirect('task_detail', pk=pk)
    elif request.method == 'POST':
        raise PermissionDenied
    history = task.get('history')
    if history is None:
        try:
            history = api_client.task_history(request, pk)
        except ApiError:
            history = []
    return render(request, 'core/task_detail.html', {
        'task': task, 'form': form, 'editable': editable, 'history': history,
        'can_change_status': bool(task.get('canChangeStatus')),
        'status_choices': STATUS_CHOICES,
    })


@login_required
@require_POST
def task_status(request, pk):
    form = TaskStatusForm(request.POST)
    if form.is_valid():
        status = form.cleaned_data['status']
        try:
            task = api_client.set_task_status(request, pk, status)
        except ApiError as e:
            raise_for_api(e)
            messages.error(request, e.message)
        else:
            messages.success(request, f"{(task or {}).get('code', 'Task')} durumu güncellendi: "
                                      f"{LABELS['status'].get(status, status)}")
    return _safe_next(request, f'/tasks/{pk}/')


# --------------------------------------------------------------------------- reports

@portal_perm_required('REPORT_ANALYSIS')
def task_report(request, fmt):
    f = _task_filters(request)
    try:
        resp = api_client.stream_task_report(request, fmt, **f)
    except ApiError as e:
        raise_for_api(e)
        messages.error(request, e.message)
        return redirect('task_list')
    content_type = resp.headers.get('Content-Type') or (
        'application/pdf' if fmt == 'pdf'
        else 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet')

    def chunks():
        try:
            yield from resp.iter_content(chunk_size=8192)
        finally:
            resp.close()

    out = StreamingHttpResponse(chunks(), content_type=content_type)
    out['Content-Disposition'] = resp.headers.get(
        'Content-Disposition', f'attachment; filename="gorev-raporu.{fmt}"')
    return out


# --------------------------------------------------------------------------- notifications

@login_required
def notification_list(request):
    try:
        items = api_client.list_notifications(request)
    except ApiError as e:
        messages.error(request, e.message)
        items = []
    return render(request, 'core/notifications.html', {'notifications': items})


@login_required
@require_POST
def notification_read(request, pk):
    try:
        api_client.mark_notification_read(request, pk)
    except ApiError as e:
        raise_for_api(e)
        messages.error(request, e.message)
    return _safe_next(request, 'notification_list')


@login_required
@require_POST
def notification_read_all(request):
    try:
        api_client.mark_all_notifications_read(request)
        messages.success(request, 'Tüm bildirimler okundu olarak işaretlendi.')
    except ApiError as e:
        messages.error(request, e.message)
    return redirect('notification_list')


# --------------------------------------------------------------------------- activities

@login_required
def activity_list(request):
    try:
        upcoming = api_client.list_activities(request, 'upcoming')
        past = api_client.list_activities(request, 'past')
    except ApiError as e:
        messages.error(request, e.message)
        upcoming, past = [], []
    return render(request, 'core/activity_list.html', {'upcoming': upcoming, 'past': past})


@portal_perm_required('ACTIVITY_MANAGEMENT')
def activity_create(request):
    form = ActivityForm(request.POST or None, users=_users(request))
    if request.method == 'POST' and form.is_valid():
        try:
            activity = api_client.create_activity(request, form.to_api())
        except ApiError as e:
            raise_for_api(e)
            messages.error(request, e.message)
        else:
            messages.success(request, f"\"{(activity or {}).get('name', '')}\" etkinliği oluşturuldu.")
            return redirect('activity_list')
    return render(request, 'core/activity_form.html', {'form': form})


@login_required
@require_POST
def activity_toggle_join(request, pk):
    try:
        res = api_client.toggle_join_activity(request, pk)
    except ApiError as e:
        raise_for_api(e)
        messages.error(request, e.message)
    else:
        if res.get('joined'):
            messages.success(request, 'Etkinliğe katıldınız.')
        else:
            messages.info(request, 'Etkinlik katılımınız iptal edildi.')
    return redirect('activity_list')


# --------------------------------------------------------------------------- data sharing

@portal_perm_required('DATA_ACCESS')
def data_sharing(request):
    token = None
    if request.method == 'POST':
        # Uzun ömürlü token yalnızca istek üzerine ve yalnızca bu sayfada gösterilir.
        token = api_client.issue_jwt(api_client.session_me(request), days=7)
    return render(request, 'core/data_sharing.html', {
        'token': token, 'api_url': settings.PORTAL_API_URL,
        'endpoints': ['/api/tasks', '/api/tasks?overdue=true', '/api/team', '/api/activities'],
    })


# --------------------------------------------------------------------------- team (yönetici)

@portal_perm_required('ROLE_MANAGEMENT')
def team(request):
    try:
        members = api_client.list_team(request)
        candidates = api_client.list_team_candidates(request)
    except ApiError as e:
        raise_for_api(e)
        messages.error(request, e.message)
        members, candidates = [], []
    return render(request, 'core/team.html', {'team': members, 'candidates': candidates})


@portal_perm_required('ROLE_MANAGEMENT')
@require_POST
def team_add(request):
    user_id = request.POST.get('user_id', '')
    if not user_id.isdigit():
        messages.error(request, 'Geçersiz kullanıcı.')
        return redirect('team')
    try:
        api_client.add_team_member(request, int(user_id))
        messages.success(request, 'Kullanıcı ekibinize eklendi.')
    except ApiError as e:
        raise_for_api(e)
        messages.error(request, e.message)
    return redirect('team')


@portal_perm_required('ROLE_MANAGEMENT')
@require_POST
def team_remove(request, user_id):
    try:
        api_client.remove_team_member(request, user_id)
        messages.info(request, 'Kullanıcı ekibinizden çıkarıldı.')
    except ApiError as e:
        raise_for_api(e)
        messages.error(request, e.message)
    return redirect('team')


@portal_perm_required('ROLE_MANAGEMENT')
def member_permissions(request, user_id):
    try:
        if request.method == 'POST':
            api_client.set_member_permissions(request, user_id, request.POST.getlist('permissions'))
            messages.success(request, 'Yetkiler güncellendi.')
            return redirect('team')
        rows = api_client.get_member_permissions(request, user_id)
        member = api_client.get_profile(request, user_id)
    except ApiError as e:
        raise_for_api(e)
        messages.error(request, e.message)
        return redirect('team')
    return render(request, 'core/member_permissions.html', {'member': member, 'rows': rows})


# --------------------------------------------------------------------------- profile

@login_required
def profile(request, user_id=None):
    my_id = api_client.session_me(request).get('id')
    own = user_id is None or user_id == my_id
    target_id = my_id if own else user_id

    profile_form = None
    skill_form = SkillForm()
    if own and request.method == 'POST':
        try:
            if 'add_skill' in request.POST:
                skill_form = SkillForm(request.POST)
                if skill_form.is_valid():
                    d = skill_form.cleaned_data
                    api_client.add_skill(request, d['skill_name'], d['kind'])
                    messages.success(request, f"\"{d['skill_name']}\" eklendi.")
                    return redirect('profile')
            else:
                profile_form = ProfileForm(request.POST)
                if profile_form.is_valid():
                    api_client.update_me(request, profile_form.to_api())
                    messages.success(request, 'Profil güncellendi.')
                    return redirect('profile')
        except ApiError as e:
            raise_for_api(e)
            messages.error(request, e.message)

    try:
        target = api_client.get_profile(request, target_id)
        skills = api_client.list_skills(request, target_id)
    except ApiError as e:
        raise_for_api(e)
        messages.error(request, e.message)
        return redirect('dashboard')
    if profile_form is None:
        profile_form = ProfileForm(initial=ProfileForm.initial_from(target))
    return render(request, 'core/profile.html', {
        'target': target, 'own': own, 'profile_form': profile_form, 'skill_form': skill_form,
        'skills': [s for s in skills if s.get('kind') == 'SKILL'],
        'certs': [s for s in skills if s.get('kind') == 'CERTIFICATE'],
        'perms': target.get('permissions') or [],
    })


@login_required
@require_POST
def skill_delete(request, skill_id):
    try:
        api_client.delete_skill(request, skill_id)
        messages.info(request, 'Kayıt silindi.')
    except ApiError as e:
        raise_for_api(e)
        messages.error(request, e.message)
    return redirect('profile')
