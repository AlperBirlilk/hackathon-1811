from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_POST

from .models import Notification
from .views import safe_next, visible_tasks


@login_required
@require_GET
def notification_list(request):
    items = Notification.objects.filter(user=request.user).select_related('task')[:50]
    return render(request, 'core/notifications.html', {'notifications': items})


@login_required
@require_POST
def notification_read(request, pk):
    notification = get_object_or_404(Notification.objects.filter(user=request.user), pk=pk)
    if not notification.is_read:
        notification.is_read = True
        notification.save(update_fields=['is_read'])
    # Task sonradan görünmez olduysa (ör. atama kaldırıldı) 404 yerine listeye dön.
    if notification.task_id and visible_tasks(request.user).filter(pk=notification.task_id).exists():
        return redirect('task_detail', notification.task_id)
    return safe_next(request, 'notification_list')


@login_required
@require_POST
def notification_read_all(request):
    count = Notification.objects.filter(user=request.user, is_read=False).update(is_read=True)
    if count:
        messages.success(request, f'{count} bildirim okundu olarak işaretlendi.')
    else:
        messages.info(request, 'Okunmamış bildirim yok.')
    return safe_next(request, 'notification_list')
