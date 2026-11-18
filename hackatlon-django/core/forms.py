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


class TaskStatusForm(forms.Form):
    status = forms.ChoiceField(choices=Task.STATUS_CHOICES)


class ActivityForm(forms.ModelForm):
    activity_date = forms.DateTimeField(
        label='Tarih', widget=forms.DateTimeInput(attrs={'type': 'datetime-local'}, format='%Y-%m-%dT%H:%M'),
        input_formats=['%Y-%m-%dT%H:%M'],
    )

    class Meta:
        model = Activity
        fields = ['activity_name', 'activity_description', 'activity_date', 'location', 'attendees']
        labels = {
            'activity_name': 'Etkinlik Adı', 'activity_description': 'Açıklama',
            'location': 'Lokasyon', 'attendees': 'Katılımcılar',
        }
        widgets = {
            'activity_description': forms.Textarea(attrs={'rows': 3}),
            'attendees': forms.SelectMultiple(attrs={'size': 6}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['attendees'].queryset = User.objects.filter(is_active=True).order_by('first_name')


class ProfileForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ['first_name', 'last_name', 'title', 'department', 'location', 'email', 'phone', 'bio']
        labels = {'first_name': 'Ad', 'last_name': 'Soyad', 'email': 'E-posta'}
        widgets = {'bio': forms.Textarea(attrs={'rows': 3})}


class SkillForm(forms.ModelForm):
    class Meta:
        model = UserSkill
        fields = ['skill_name', 'kind']
        labels = {'skill_name': 'Yetenek / Sertifika', 'kind': 'Tür'}
