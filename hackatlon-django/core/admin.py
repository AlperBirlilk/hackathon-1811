from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import Activity, PermissionType, Task, TaskHistory, User, UserPermission, UserSkill


class UserPermissionInline(admin.TabularInline):
    model = UserPermission
    fk_name = 'user'
    extra = 0


class UserSkillInline(admin.TabularInline):
    model = UserSkill
    extra = 0


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    fieldsets = BaseUserAdmin.fieldsets + (
        ('Portal', {'fields': ('auth_source', 'ldap_dn', 'title', 'department', 'phone', 'location', 'bio',
                               'manager')}),
    )
    readonly_fields = ('ldap_dn',)
    list_display = ('username', 'first_name', 'last_name', 'auth_source', 'manager', 'last_login', 'is_active')
    list_filter = ('auth_source', 'is_active', 'is_superuser')
    inlines = [UserPermissionInline, UserSkillInline]


class TaskHistoryInline(admin.TabularInline):
    model = TaskHistory
    extra = 0
    readonly_fields = ('action_type', 'action_description', 'action_by', 'action_date')


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ('id', 'task_title', 'task_status', 'task_severity', 'created_by', 'modified_date')
    list_filter = ('task_status', 'task_severity')
    search_fields = ('task_title',)
    filter_horizontal = ('assignees',)
    inlines = [TaskHistoryInline]


admin.site.register(PermissionType)
admin.site.register(UserPermission)
admin.site.register(UserSkill)
admin.site.register(TaskHistory)


@admin.register(Activity)
class ActivityAdmin(admin.ModelAdmin):
    list_display = ('activity_name', 'activity_date', 'created_by')
    filter_horizontal = ('attendees',)
