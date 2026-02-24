from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from django.contrib.auth.models import User
from .models import UserProfile, MakeUpClass, Course
from datetime import date


class CustomLoginForm(AuthenticationForm):
    username = forms.CharField(
        widget=forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Username'})
    )
    password = forms.CharField(
        widget=forms.PasswordInput(attrs={'class': 'form-control', 'placeholder': 'Password'})
    )


class RegisterForm(UserCreationForm):
    ROLE_CHOICES = [('faculty', 'Faculty'), ('student', 'Student')]
    first_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    last_name = forms.CharField(max_length=100, widget=forms.TextInput(attrs={'class': 'form-control'}))
    email = forms.EmailField(widget=forms.EmailInput(attrs={'class': 'form-control'}))
    role = forms.ChoiceField(choices=ROLE_CHOICES, widget=forms.Select(attrs={'class': 'form-control'}))
    department = forms.CharField(max_length=100, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    student_id = forms.CharField(max_length=50, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))
    phone = forms.CharField(max_length=20, required=False, widget=forms.TextInput(attrs={'class': 'form-control'}))

    class Meta:
        model = User
        fields = ['username', 'first_name', 'last_name', 'email', 'password1', 'password2']
        widgets = {
            'username': forms.TextInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields['password1'].widget.attrs['class'] = 'form-control'
        self.fields['password2'].widget.attrs['class'] = 'form-control'


class MakeUpClassForm(forms.ModelForm):
    class Meta:
        model = MakeUpClass
        fields = ['course', 'title', 'description', 'scheduled_date', 'start_time', 'end_time',
                  'venue', 'reason', 'max_attendance']
        widgets = {
            'course': forms.Select(attrs={'class': 'form-control'}),
            'title': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Session Title'}),
            'description': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
            'scheduled_date': forms.DateInput(attrs={'class': 'form-control', 'type': 'date'}),
            'start_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'end_time': forms.TimeInput(attrs={'class': 'form-control', 'type': 'time'}),
            'venue': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Room / Online Link'}),
            'reason': forms.Textarea(attrs={'class': 'form-control', 'rows': 2}),
            'max_attendance': forms.NumberInput(attrs={'class': 'form-control'}),
        }

    def __init__(self, *args, **kwargs):
        faculty = kwargs.pop('faculty', None)
        super().__init__(*args, **kwargs)
        if faculty:
            self.fields['course'].queryset = Course.objects.filter(faculty=faculty)

    def clean(self):
        cleaned = super().clean()
        sd = cleaned.get('scheduled_date')
        if sd and sd < date.today():
            raise forms.ValidationError("Scheduled date cannot be in the past.")
        st = cleaned.get('start_time')
        et = cleaned.get('end_time')
        if st and et and st >= et:
            raise forms.ValidationError("End time must be after start time.")
        return cleaned


class AttendanceCodeForm(forms.Form):
    remedial_code = forms.CharField(
        max_length=20,
        widget=forms.TextInput(attrs={
            'class': 'form-control form-control-lg text-center text-uppercase',
            'placeholder': 'Enter Remedial Code',
            'style': 'letter-spacing: 6px; font-size: 1.5rem; font-weight: bold;',
            'autocomplete': 'off',
        })
    )

    def clean_remedial_code(self):
        return self.cleaned_data['remedial_code'].strip().upper()


class CourseForm(forms.ModelForm):
    class Meta:
        model = Course
        fields = ['name', 'code', 'department', 'semester']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'code': forms.TextInput(attrs={'class': 'form-control'}),
            'department': forms.TextInput(attrs={'class': 'form-control'}),
            'semester': forms.TextInput(attrs={'class': 'form-control'}),
        }
