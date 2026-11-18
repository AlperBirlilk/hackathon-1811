from django.urls import path, re_path

from . import views

# No trailing slashes: the MCP server calls e.g. /api/me and /api/tasks/12.
urlpatterns = [
    path('me', views.me, name='api_me'),
    path('users', views.users, name='api_users'),
    path('tasks', views.tasks, name='api_tasks'),
    path('tasks/<int:pk>', views.task_detail, name='api_task_detail'),
    path('dashboard', views.dashboard, name='api_dashboard'),
    path('team', views.team, name='api_team'),
    path('activities', views.activities, name='api_activities'),
    # Unknown /api/... paths return the JSON error format instead of an HTML 404.
    re_path(r'^.*$', views.not_found, name='api_not_found'),
]
