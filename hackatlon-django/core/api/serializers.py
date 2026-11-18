"""Plain dict builders for the API (camelCase, ISO-8601 local time). Inputs must be prefetched
(see views) to avoid N+1 queries."""
from django.utils import timezone

from core.views import can_change_status, can_edit_task, is_handover


def iso(dt):
    return timezone.localtime(dt).isoformat() if dt else None


def user_ref(user):
    if user is None:
        return None
    return {'id': user.pk, 'username': user.username, 'displayName': user.display_name}


def me(user):
    return {
        'id': user.pk,
        'username': user.username,
        'displayName': user.display_name,
        'title': user.title or None,
        'permissions': sorted(user.permission_codes()),
        'managerId': user.manager_id,
        'isManager': user.is_manager,
        'isDirector': user.is_director,
        'isOnLeave': user.is_on_leave,
    }


def task_summary(task, user):
    """Needs `assignees` prefetched and `backup_assignee` selected."""
    return {
        'id': task.pk,
        'code': task.code,
        'title': task.task_title,
        'status': task.task_status,
        'severity': task.task_severity,
        'assignees': [user_ref(a) for a in task.assignees.all()],
        'backupAssignee': user_ref(task.backup_assignee),
        'dueDate': iso(task.due_date),
        'isOverdue': task.is_overdue,
        'handover': is_handover(task, user),
        'modifiedDate': iso(task.modified_date),
    }


def history_entry(entry):
    return {
        'id': entry.pk,
        'actionType': entry.action_type,
        'actionDescription': entry.action_description,
        'actionBy': user_ref(entry.action_by),
        'actionDate': iso(entry.action_date),
    }


def history_with_task(entry):
    data = history_entry(entry)
    data['task'] = {'id': entry.task.pk, 'code': entry.task.code, 'title': entry.task.task_title}
    return data


def task_detail(task, user):
    """Needs `history` prefetched (with action_by) plus created_by/modified_by selected."""
    data = task_summary(task, user)
    data.update({
        'description': task.task_description,
        'createdBy': user_ref(task.created_by),
        'createDate': iso(task.create_date),
        'modifiedBy': user_ref(task.modified_by),
        'canEdit': can_edit_task(user, task),
        'canChangeStatus': can_change_status(user, task),
        'history': [history_entry(h) for h in task.history.all()],
    })
    return data


def activity_summary(activity, user):
    """Needs contact_person/created_by selected and attendees prefetched."""
    attendees = list(activity.attendees.all())
    return {
        'id': activity.pk,
        'name': activity.activity_name,
        'description': activity.activity_description,
        'date': iso(activity.activity_date),
        'location': activity.location or None,
        'type': activity.activity_type,
        'participationType': activity.participation_type,
        'contactPerson': user_ref(activity.contact_person),
        'createdBy': user_ref(activity.created_by),
        'attendees': [user_ref(a) for a in attendees],
        'joined': any(a.pk == user.pk for a in attendees),
    }


def team_member(member):
    """`member` comes from team_with_stats(...) with `permissions` prefetched."""
    return {
        'user': user_ref(member),
        'title': member.title or None,
        'isOnLeave': member.is_on_leave,
        'permissions': sorted(p.code for p in member.permissions.all()),
        'openCount': member.open_count,
        'progressCount': member.progress_count,
        'doneCount': member.done_count,
        'overdueCount': member.overdue_count,
    }
