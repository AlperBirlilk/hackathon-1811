"""
Entity yapısı (docs/prototype-erd.png):
  User, User_Permission, Permission_Type, User_Skill, task, task_history, activity
"""
from datetime import timedelta

from django.conf import settings
from django.contrib.auth.models import AbstractUser
from django.db import models
from django.utils import timezone


class PermissionType(models.Model):
    """Permission_Type: id, permission_name"""

    TASK_MANAGEMENT = 'TASK_MANAGEMENT'
    ACTIVITY_MANAGEMENT = 'ACTIVITY_MANAGEMENT'
    ROLE_MANAGEMENT = 'ROLE_MANAGEMENT'
    REPORT_ANALYSIS = 'REPORT_ANALYSIS'
    DATA_ACCESS = 'DATA_ACCESS'

    CODE_CHOICES = [
        (TASK_MANAGEMENT, 'Task Management'),
        (ACTIVITY_MANAGEMENT, 'Activity Management'),
        (ROLE_MANAGEMENT, 'Role Management'),
        (REPORT_ANALYSIS, 'Report & Analysis'),
        (DATA_ACCESS, 'Data Access'),
    ]

    code = models.CharField(max_length=50, unique=True, choices=CODE_CHOICES)
    permission_name = models.CharField(max_length=100)
    description = models.CharField(max_length=255, blank=True)

    class Meta:
        db_table = 'permission_type'
        ordering = ['id']

    def __str__(self):
        return self.permission_name


class User(AbstractUser):
    """User: username, login ... (LDAP ile doğrulanır, yetkiler user_permission'dan gelir)"""

    AUTH_LDAP = 'LDAP'
    AUTH_LOCAL = 'LOCAL'
    AUTH_SOURCE_CHOICES = [(AUTH_LDAP, 'LDAP'), (AUTH_LOCAL, 'Yerel')]

    auth_source = models.CharField('Kimlik Kaynağı', max_length=10, choices=AUTH_SOURCE_CHOICES,
                                   default=AUTH_LOCAL)
    ldap_dn = models.CharField('LDAP DN', max_length=255, blank=True)
    title = models.CharField('Ünvan', max_length=100, blank=True)
    department = models.CharField('Birim', max_length=100, blank=True)
    phone = models.CharField('Telefon', max_length=30, blank=True)
    location = models.CharField('Lokasyon', max_length=100, blank=True)
    bio = models.TextField('Hakkında', blank=True)
    is_on_leave = models.BooleanField('İzinli', default=False)
    manager = models.ForeignKey(
        'self', null=True, blank=True, on_delete=models.SET_NULL,
        related_name='team_members', verbose_name='Yönetici',
    )
    permissions = models.ManyToManyField(
        PermissionType, through='UserPermission', through_fields=('user', 'permission_type'),
        related_name='users', blank=True,
    )

    class Meta:
        db_table = 'user'

    def __str__(self):
        return self.get_full_name() or self.username

    @property
    def display_name(self):
        return self.get_full_name() or self.username

    @property
    def initials(self):
        name = self.display_name.split()
        return ''.join(p[0] for p in name[:2]).upper()

    def permission_codes(self):
        if not hasattr(self, '_perm_codes'):
            self._perm_codes = set(self.permissions.values_list('code', flat=True))
        return self._perm_codes

    def has_portal_perm(self, code):
        return self.is_superuser or code in self.permission_codes()

    @property
    def is_manager(self):
        return self.has_portal_perm(PermissionType.ROLE_MANAGEMENT)

    @property
    def is_director(self):
        """Direktör: tüm portal yetkilerine sahip kullanıcı (veya superuser). Ekibim'de herkesi görür."""
        if self.is_superuser:
            return True
        all_codes = {code for code, _ in PermissionType.CODE_CHOICES}
        return all_codes <= self.permission_codes()


class UserPermission(models.Model):
    """User_Permission: user_id, permission_type_id"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE)
    permission_type = models.ForeignKey(PermissionType, on_delete=models.CASCADE)
    granted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True,
        on_delete=models.SET_NULL, related_name='granted_permissions',
    )
    granted_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'user_permission'
        unique_together = ('user', 'permission_type')

    def __str__(self):
        return f'{self.user} -> {self.permission_type}'


class UserSkill(models.Model):
    """User_Skill: id, user_id, skill_name, create_date"""

    SKILL = 'SKILL'
    CERTIFICATE = 'CERTIFICATE'
    KIND_CHOICES = [(SKILL, 'Yetenek'), (CERTIFICATE, 'Sertifika')]

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='skills')
    skill_name = models.CharField(max_length=100)
    kind = models.CharField(max_length=20, choices=KIND_CHOICES, default=SKILL)
    create_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'user_skill'
        ordering = ['kind', 'skill_name']

    def __str__(self):
        return self.skill_name


class Task(models.Model):
    """task: id, task_status, task_severity, task_title, task_description, assignees,
    create_date, created_by, modified_date, modified_by"""

    STATUS_OPEN = 'OPEN'
    STATUS_IN_PROGRESS = 'IN_PROGRESS'
    STATUS_DONE = 'DONE'
    STATUS_CHOICES = [
        (STATUS_OPEN, 'Açık'),
        (STATUS_IN_PROGRESS, 'Devam Ediyor'),
        (STATUS_DONE, 'Tamamlandı'),
    ]
    PENDING_STATUSES = [STATUS_OPEN, STATUS_IN_PROGRESS]

    SEVERITY_LOW = 'LOW'
    SEVERITY_MEDIUM = 'MEDIUM'
    SEVERITY_HIGH = 'HIGH'
    SEVERITY_CRITICAL = 'CRITICAL'
    SEVERITY_CHOICES = [
        (SEVERITY_LOW, 'Düşük'),
        (SEVERITY_MEDIUM, 'Orta'),
        (SEVERITY_HIGH, 'Yüksek'),
        (SEVERITY_CRITICAL, 'Kritik'),
    ]
    # Son tarih verilmezse oluşturma anına eklenecek gün sayısı (SLA)
    SLA_DAYS = {SEVERITY_CRITICAL: 1, SEVERITY_HIGH: 3, SEVERITY_MEDIUM: 7, SEVERITY_LOW: 14}

    task_status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_OPEN)
    task_severity = models.CharField(max_length=20, choices=SEVERITY_CHOICES, default=SEVERITY_MEDIUM)
    task_title = models.CharField(max_length=200)
    task_description = models.TextField(blank=True)
    assignees = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='assigned_tasks', blank=True)
    backup_assignee = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='backup_tasks', verbose_name='Yedek sorumlu',
    )
    due_date = models.DateTimeField('Son tarih', null=True, blank=True)

    create_date = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='created_tasks',
    )
    modified_date = models.DateTimeField(auto_now=True)
    modified_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='modified_tasks',
    )

    class Meta:
        db_table = 'task'
        ordering = ['-modified_date']

    def __str__(self):
        return f'#{self.pk} {self.task_title}'

    @property
    def code(self):
        return f'TSK-{self.pk:04d}'

    @classmethod
    def sla_due_date(cls, severity, start=None):
        start = start or timezone.now()
        return start + timedelta(days=cls.SLA_DAYS.get(severity, 7))

    @property
    def is_overdue(self):
        return bool(self.due_date and self.task_status != self.STATUS_DONE and self.due_date < timezone.now())


class TaskHistory(models.Model):
    """task_history: id, task_id, action_type, action_description (log)"""

    CREATED = 'created'
    STATUS_CHANGE = 'status_change'
    DESCRIPTION_CHANGE = 'description_change'
    ASSIGNMENT_CHANGE = 'assignment_change'
    SEVERITY_CHANGE = 'severity_change'
    DUE_DATE_CHANGE = 'due_date_change'
    BACKUP_CHANGE = 'backup_change'
    ACTION_CHOICES = [
        (CREATED, 'Oluşturuldu'),
        (STATUS_CHANGE, 'Durum Değişikliği'),
        (DESCRIPTION_CHANGE, 'Açıklama Değişikliği'),
        (ASSIGNMENT_CHANGE, 'Atama Değişikliği'),
        (SEVERITY_CHANGE, 'Önem Derecesi Değişikliği'),
        (DUE_DATE_CHANGE, 'Son Tarih Değişikliği'),
        (BACKUP_CHANGE, 'Yedek Sorumlu Değişikliği'),
    ]

    task = models.ForeignKey(Task, on_delete=models.CASCADE, related_name='history')
    action_type = models.CharField(max_length=30, choices=ACTION_CHOICES)
    action_description = models.TextField()
    action_by = models.ForeignKey(settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL)
    action_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'task_history'
        ordering = ['-action_date', '-id']

    def __str__(self):
        return f'{self.task_id} {self.action_type}'


class Activity(models.Model):
    """activity: id, activity_name, activity_date, create_date, created_by, attendees"""

    TYPE_TRAINING = 'TRAINING'
    TYPE_CONFERENCE = 'CONFERENCE'
    TYPE_OTHER = 'OTHER'
    TYPE_CHOICES = [(TYPE_TRAINING, 'Eğitim'), (TYPE_CONFERENCE, 'Konferans'), (TYPE_OTHER, 'Diğer')]

    PARTICIPATION_INDIVIDUAL = 'INDIVIDUAL'
    PARTICIPATION_CORPORATE = 'CORPORATE'
    PARTICIPATION_CHOICES = [(PARTICIPATION_INDIVIDUAL, 'Bireysel'), (PARTICIPATION_CORPORATE, 'Kurumsal')]

    activity_name = models.CharField(max_length=200)
    activity_description = models.TextField(blank=True)
    activity_date = models.DateTimeField()
    location = models.CharField(max_length=150, blank=True)
    activity_type = models.CharField('Tür', max_length=20, choices=TYPE_CHOICES, default=TYPE_OTHER)
    participation_type = models.CharField('Katılım şekli', max_length=20, choices=PARTICIPATION_CHOICES,
                                          default=PARTICIPATION_INDIVIDUAL)
    contact_person = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, blank=True, on_delete=models.SET_NULL,
        related_name='contact_activities', verbose_name='İletişim kişisi',
    )
    create_date = models.DateTimeField(auto_now_add=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL, null=True, on_delete=models.SET_NULL, related_name='created_activities',
    )
    attendees = models.ManyToManyField(settings.AUTH_USER_MODEL, related_name='activities', blank=True)

    class Meta:
        db_table = 'activity'
        ordering = ['activity_date']

    def __str__(self):
        return self.activity_name


class Notification(models.Model):
    """Uygulama içi bildirim (task ataması vb.). Oluşturma: core/notifications.py"""

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name='notifications')
    task = models.ForeignKey(Task, null=True, blank=True, on_delete=models.CASCADE, related_name='notifications')
    message = models.CharField(max_length=300)
    is_read = models.BooleanField(default=False)
    create_date = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'notification'
        ordering = ['-create_date', '-id']
        indexes = [models.Index(fields=['user', 'is_read'], name='notification_user_read_idx')]

    def __str__(self):
        return f'{self.user_id}: {self.message}'
