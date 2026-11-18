from django import forms

from .templatetags.portal_tags import LABELS, SEVERITY_CHOICES, STATUS_CHOICES

DT_WIDGET = forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M')
DT_FORMATS = ['%Y-%m-%dT%H:%M']


def user_choices(users):
    return [(str(u['id']), u.get('displayName') or u['username']) for u in users]


class TaskForm(forms.Form):
    title = forms.CharField(label='Başlık', max_length=200)
    description = forms.CharField(label='Açıklama', widget=forms.Textarea(attrs={'rows': 4}), required=False)
    severity = forms.ChoiceField(label='Önem', choices=SEVERITY_CHOICES, initial='MEDIUM')
    status = forms.ChoiceField(label='Durum', choices=STATUS_CHOICES, initial='OPEN')
    assignees = forms.MultipleChoiceField(
        label='Atananlar', choices=[], required=False, widget=forms.SelectMultiple(attrs={'size': 6}),
    )
    backup_assignee = forms.ChoiceField(label='Yedek sorumlu', choices=[], required=False)
    due_date = forms.DateTimeField(label='Son tarih', required=False, widget=DT_WIDGET, input_formats=DT_FORMATS,
                                   help_text='Boş bırakılırsa önem derecesine göre SLA uygulanır.')

    def __init__(self, *args, users=(), **kwargs):
        super().__init__(*args, **kwargs)
        choices = user_choices(users)
        self.fields['assignees'].choices = choices
        self.fields['backup_assignee'].choices = [('', '— Yok —')] + choices

    def to_api(self):
        d = self.cleaned_data
        return {
            'title': d['title'], 'description': d['description'], 'severity': d['severity'],
            'status': d['status'], 'assigneeIds': [int(i) for i in d['assignees']],
            'backupAssigneeId': int(d['backup_assignee']) if d.get('backup_assignee') else None,
            'dueDate': d['due_date'].isoformat() if d.get('due_date') else None,
        }


class TaskStatusForm(forms.Form):
    status = forms.ChoiceField(choices=STATUS_CHOICES)


class ActivityForm(forms.Form):
    name = forms.CharField(label='Etkinlik Adı', max_length=200)
    description = forms.CharField(label='Açıklama', widget=forms.Textarea(attrs={'rows': 3}), required=False)
    date = forms.DateTimeField(label='Tarih', widget=DT_WIDGET, input_formats=DT_FORMATS)
    location = forms.CharField(label='Lokasyon', max_length=200, required=False)
    type = forms.ChoiceField(label='Tür', choices=list(LABELS['activity_type'].items()), initial='TRAINING')
    participation_type = forms.ChoiceField(label='Katılım türü', choices=list(LABELS['participation'].items()),
                                           initial='INDIVIDUAL')
    contact_person = forms.ChoiceField(label='İrtibat kişisi', choices=[], required=False)
    attendees = forms.MultipleChoiceField(label='Katılımcılar', choices=[], required=False,
                                          widget=forms.SelectMultiple(attrs={'size': 6}))

    def __init__(self, *args, users=(), **kwargs):
        super().__init__(*args, **kwargs)
        choices = user_choices(users)
        self.fields['attendees'].choices = choices
        self.fields['contact_person'].choices = [('', '— Yok —')] + choices

    def to_api(self):
        d = self.cleaned_data
        return {
            'name': d['name'], 'description': d['description'], 'date': d['date'].isoformat(),
            'location': d['location'], 'type': d['type'], 'participationType': d['participation_type'],
            'contactPersonId': int(d['contact_person']) if d.get('contact_person') else None,
            'attendeeIds': [int(i) for i in d['attendees']],
        }


class ProfileForm(forms.Form):
    first_name = forms.CharField(label='Ad', max_length=150, required=False)
    last_name = forms.CharField(label='Soyad', max_length=150, required=False)
    title = forms.CharField(label='Ünvan', max_length=150, required=False)
    department = forms.CharField(label='Birim', max_length=150, required=False)
    email = forms.EmailField(label='E-posta', required=False)
    phone = forms.CharField(label='Telefon', max_length=50, required=False)
    location = forms.CharField(label='Lokasyon', max_length=150, required=False)
    bio = forms.CharField(label='Hakkımda', widget=forms.Textarea(attrs={'rows': 3}), required=False)
    is_on_leave = forms.BooleanField(label='İzinliyim', required=False)

    API_KEYS = {'first_name': 'firstName', 'last_name': 'lastName', 'is_on_leave': 'isOnLeave'}

    @classmethod
    def initial_from(cls, profile):
        return {f: profile.get(cls.API_KEYS.get(f, f)) for f in cls.base_fields}

    def to_api(self):
        return {self.API_KEYS.get(k, k): v for k, v in self.cleaned_data.items()}


class SkillForm(forms.Form):
    skill_name = forms.CharField(label='Yetenek / Sertifika', max_length=100)
    kind = forms.ChoiceField(label='Tür', choices=list(LABELS['skill_kind'].items()), initial='SKILL')
