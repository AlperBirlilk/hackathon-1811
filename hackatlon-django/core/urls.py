from django.urls import path

from . import views

urlpatterns = [
    path('login/', views.PortalLoginView.as_view(), name='login'),
    path('logout/', views.logout_view, name='logout'),

    path('', views.dashboard, name='dashboard'),

    path('tasks/', views.task_list, name='task_list'),
    path('tasks/new/', views.task_create, name='task_create'),
    path('tasks/<int:pk>/', views.task_detail, name='task_detail'),
    path('tasks/<int:pk>/status/', views.task_status, name='task_status'),

    path('activities/', views.activity_list, name='activity_list'),
    path('activities/new/', views.activity_create, name='activity_create'),
    path('activities/<int:pk>/join/', views.activity_toggle_join, name='activity_toggle_join'),

    path('data-sharing/', views.data_sharing, name='data_sharing'),

    path('team/', views.team, name='team'),
    path('team/add/', views.team_add, name='team_add'),
    path('team/<int:user_id>/remove/', views.team_remove, name='team_remove'),
    path('team/<int:user_id>/permissions/', views.member_permissions, name='member_permissions'),

    path('profile/', views.profile, name='profile'),
    path('profile/<int:user_id>/', views.profile, name='member_profile'),
    path('profile/skills/<int:skill_id>/delete/', views.skill_delete, name='skill_delete'),
]
