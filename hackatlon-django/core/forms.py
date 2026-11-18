from django import forms

from .models import Activity, Task, User, UserSkill


class TaskForm(forms.Form):
    title = forms.CharField(label='Başlık', max_length=200)
    description = forms.CharField(label='Açıklama', widget=forms.Textarea(attrs={'rows': 4}), required=False)
    severity = forms.ChoiceField(label='Önem', choices=Task.SEVERITY_CHOICES, initial=Task.SEVERITY_MEDIUM,
                                 widget=forms.RadioSelect)
    status = forms.ChoiceField(label='Durum', choices=Task.STATUS_CHOICES, initial=Task.STATUS_OPEN)
    assignees = forms.ModelMultipleChoiceField(
        label='Atananlar', queryset=User.objects.filter(is_active=True).order_by('first_name'),
        required=False, widget=forms.SelectMultiple(attrs={'size': 6}),
    )
    due_date = forms.DateTimeField(
        label='Son tarih', required=False, input_formats=['%Y-%m-%dT%H:%M'],
        widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        help_text='Boş bırakılırsa önem derecesine göre SLA uygulanır (Kritik 1, Yüksek 3, Orta 7, Düşük 14 gün)',
    )
    backup_assignee = forms.ModelChoiceField(
        label='Yedek sorumlu', queryset=User.objects.filter(is_active=True).order_by('first_name'),
        required=False, empty_label='Yok',
    )

    def clean(self):
        cleaned = super().clean()
        backup = cleaned.get('backup_assignee')
        if backup and backup in (cleaned.get('assignees') or []):
            self.add_error('backup_assignee', 'Yedek sorumlu aynı zamanda ana sorumlu olamaz.')
        return cleaned


class TaskStatusForm(forms.Form):
    status = forms.ChoiceField(choices=Task.STATUS_CHOICES)


class ActivityForm(forms.ModelForm):
    activity_date = forms.DateTimeField(
        label='Tarih', widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        input_formats=['%Y-%m-%dT%H:%M'],
    )

    class Meta:
        model = Activity
        fields = ['activity_name', 'activity_description', 'activity_date', 'location',
                  'activity_type', 'participation_type', 'contact_person', 'attendees']
        labels = {
            'activity_name': 'Etkinlik Adı', 'activity_description': 'Açıklama',
            'location': 'Lokasyon', 'attendees': 'Katılımcılar',
            'activity_type': 'Etkinlik türü', 'participation_type': 'Katılım şekli',
            'contact_person': 'İletişim kişisi',
        }
        widgets = {
            'activity_description': forms.Textarea(attrs={'rows': 3}),
            'attendees': forms.SelectMultiple(attrs={'size': 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['attendees'].queryset = User.objects.filter(is_active=True).order_by('first_name')
        contact = self.fields['contact_person']
        contact.queryset = User.objects.filter(is_active=True).order_by('first_name', 'last_name')
        contact.required = False
        contact.empty_label = 'Yok'
        contact.label_from_instance = lambda u: u.display_name
        # Alan gönderilmezse (eski istemciler) model varsayılanı kullanılır
        for name in ('activity_type', 'participation_type'):
            self.fields[name].required = False

    def clean_activity_type(self):
        return self.cleaned_data.get('activity_type') or Activity.TYPE_OTHER

    def clean_participation_type(self):
        return self.cleaned_data.get('participation_type') or Activity.PARTICIPATION_INDIVIDUAL


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'title', 'department', 'location', 'email', 'phone', 'bio',
                  'is_on_leave']
        labels = {'first_name': 'Ad', 'last_name': 'Soyad', 'email': 'E-posta', 'is_on_leave': 'İzinliyim'}
        help_texts = {'is_on_leave': 'İzinliyken ana sorumlusu olduğunuz açık işler, yedek sorumlularının '
                                     '"Devralınan işler" paneline düşer.'}
        widgets = {'bio': forms.Textarea(attrs={'rows': 3})}


class SkillForm(forms.ModelForm):
    class Meta:
        model = UserSkill
        fields = ['skill_name', 'kind']
        labels = {'skill_name': 'Yetenek / Sertifika', 'kind': 'Tür'}
