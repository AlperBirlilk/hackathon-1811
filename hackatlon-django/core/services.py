"""Task iş kuralları: oluşturma / güncelleme ve otomatik task_history kaydı."""
from django.db import transaction

from . import notifications
from .models import Task, TaskHistory


def _names(users):
    return ', '.join(sorted(u.display_name for u in users)) or '—'


@transaction.atomic
def create_task(*, user, title, description, severity, status, assignees,
                due_date=None, backup_assignee=None):
    task = Task.objects.create(
        task_title=title,
        task_description=description,
        task_severity=severity,
        task_status=status,
        due_date=due_date or Task.sla_due_date(severity),
        backup_assignee=backup_assignee,
        created_by=user,
        modified_by=user,
    )
    task.assignees.set(assignees)
    TaskHistory.objects.create(
        task=task, action_by=user, action_type=TaskHistory.CREATED,
        action_description=f'Task oluşturuldu. Atananlar: {_names(assignees)}',
    )
    notifications.notify_task_assigned(task, assignees, actor=user)
    return task


@transaction.atomic
def update_task(task, *, user, **changes):
    """Değişen her alan için history kaydı oluşturur."""
    logs = []

    if 'status' in changes and changes['status'] != task.task_status:
        old = task.get_task_status_display()
        task.task_status = changes['status']
        logs.append((TaskHistory.STATUS_CHANGE, f'Durum: {old} → {task.get_task_status_display()}'))

    if 'severity' in changes and changes['severity'] != task.task_severity:
        old = task.get_task_severity_display()
        task.task_severity = changes['severity']
        logs.append((TaskHistory.SEVERITY_CHANGE, f'Önem: {old} → {task.get_task_severity_display()}'))

    if 'title' in changes and changes['title'] != task.task_title:
        logs.append((TaskHistory.DESCRIPTION_CHANGE, f'Başlık: "{task.task_title}" → "{changes["title"]}"'))
        task.task_title = changes['title']

    if 'description' in changes and changes['description'] != task.task_description:
        task.task_description = changes['description']
        logs.append((TaskHistory.DESCRIPTION_CHANGE, 'Açıklama güncellendi.'))

    assignees_changed = False
    added = set()
    if 'assignees' in changes:
        old = set(task.assignees.all())
        new = set(changes['assignees'])
        if old != new:
            assignees_changed = True
            added, removed = new - old, old - new
            parts = []
            if added:
                parts.append(f'Eklenen: {_names(added)}')
            if removed:
                parts.append(f'Çıkarılan: {_names(removed)}')
            logs.append((TaskHistory.ASSIGNMENT_CHANGE, ' | '.join(parts)))

    if not logs:
        return False

    task.modified_by = user
    task.save()
    if assignees_changed:
        task.assignees.set(changes['assignees'])
    TaskHistory.objects.bulk_create([
        TaskHistory(task=task, action_by=user, action_type=t, action_description=d) for t, d in logs
    ])
    if added:
        notifications.notify_task_assigned(task, added, actor=user)
    return True
