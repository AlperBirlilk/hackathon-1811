from . import api_client


def portal(request):
    user = getattr(request, 'user', None)
    if not user or not user.is_authenticated or not request.session.get(api_client.SESSION_JWT):
        return {}
    me = api_client.session_me(request)
    perms = set(me.get('permissions') or [])
    unread = 0
    try:
        unread = api_client.unread_notification_count(request)
    except api_client.ApiError:
        unread = 0
    return {
        'me': me,
        'is_manager': bool(me.get('isManager')) or 'ROLE_MANAGEMENT' in perms,
        'unread_count': unread,
        'perm': {
            'task': 'TASK_MANAGEMENT' in perms,
            'activity': 'ACTIVITY_MANAGEMENT' in perms,
            'role': 'ROLE_MANAGEMENT' in perms,
            'report': 'REPORT_ANALYSIS' in perms,
            'data': 'DATA_ACCESS' in perms,
        },
    }
