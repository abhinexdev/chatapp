"""
accounts/forms.py — Registration, login, profile update forms with validation
"""
from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User

# Blocked disposable email domains
BLOCKED_DOMAINS = {
    'mailinator.com', 'tempmail.com', 'guerrillamail.com', '10minutemail.com',
    'throwaway.email', 'fakeinbox.com', 'yopmail.com', 'trashmail.com',
    'sharklasers.com', 'guerrillamailblock.com', 'grr.la', 'guerrillamail.info',
    'spam4.me', 'temp-mail.org', 'dispostable.com', 'mailnull.com',
}


class RegisterForm(UserCreationForm):
    email = forms.EmailField(
        required=True,
        widget=forms.EmailInput(attrs={'placeholder': 'your@email.com', 'autocomplete': 'email'})
    )
    avatar = forms.ImageField(required=False, widget=forms.FileInput(attrs={'accept': 'image/*'}))

    class Meta:
        model = User
        fields = ('username', 'email', 'avatar', 'password1', 'password2')

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if User.objects.filter(username__iexact=username).exists():
            raise forms.ValidationError('This username is already taken.')
        return username

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if not email:
            raise forms.ValidationError('Email is required.')

        # Block disposable email domains
        domain = email.split('@')[-1] if '@' in email else ''
        if domain in BLOCKED_DOMAINS:
            raise forms.ValidationError('Disposable email addresses are not allowed.')

        # Unique email check
        if User.objects.filter(email__iexact=email).exists():
            raise forms.ValidationError('An account with this email already exists.')

        return email


class LoginForm(AuthenticationForm):
    username = forms.CharField(widget=forms.TextInput(attrs={'autofocus': True, 'placeholder': 'Username'}))
    password = forms.CharField(widget=forms.PasswordInput(attrs={'placeholder': 'Password'}))


class ProfileUpdateForm(forms.ModelForm):
    class Meta:
        model = User
        fields = ('avatar', 'bio', 'email')
        widgets = {
            'bio': forms.TextInput(attrs={'placeholder': 'A short bio...'}),
            'avatar': forms.FileInput(attrs={'accept': 'image/*'}),
        }

    def clean_email(self):
        email = self.cleaned_data.get('email', '').strip().lower()
        if email and User.objects.filter(email__iexact=email).exclude(pk=self.instance.pk).exists():
            raise forms.ValidationError('This email is already used by another account.')
        return email
