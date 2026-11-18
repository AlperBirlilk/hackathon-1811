from .models import Notification, PermissionType


def portal(request):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated:
        return {}
    return {
        'perm': {
            'task': user.has_portal_perm(PermissionType.TASK_MANAGEMENT),
            'activity': user.has_portal_perm(PermissionType.ACTIVITY_MANAGEMENT),
            'role': user.has_portal_perm(PermissionType.ROLE_MANAGEMENT),
            'report': user.has_portal_perm(PermissionType.REPORT_ANALYSIS),
            'data': user.has_portal_perm(PermissionType.DATA_ACCESS),
        },
        'unread_notifications': Notification.objects.filter(user=user, is_read=False).count(),
    }
