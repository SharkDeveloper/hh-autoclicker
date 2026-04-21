from django import forms
from django.contrib.auth.models import User
from accounts.models import HHAccount


class RegisterForm(forms.ModelForm):
    """Форма регистрации пользователя"""
    password = forms.CharField(widget=forms.PasswordInput, label="Пароль")
    password2 = forms.CharField(widget=forms.PasswordInput, label="Подтверждение пароля")

    class Meta:
        model = User
        fields = ['username', 'email']

    def clean_password2(self):
        password = self.cleaned_data.get('password')
        password2 = self.cleaned_data.get('password2')
        if password and password2 and password != password2:
            raise forms.ValidationError("Пароли не совпадают")
        return password2

    def save(self, commit=True):
        user = super().save(commit=False)
        user.set_password(self.cleaned_data['password'])
        if commit:
            user.save()
        return user


class HHAccountForm(forms.ModelForm):
    """Форма управления аккаунтом HH.ru"""
    
    class Meta:
        model = HHAccount
        fields = ['name', 'username', 'password', 'resume_id', 'cover_letter', 
                  'search_filters', 'enabled', 'auto_apply', 'max_applications_per_day']
        widgets = {
            'cover_letter': forms.Textarea(attrs={'rows': 4}),
            'search_filters': forms.Textarea(attrs={'rows': 6, 'placeholder': '{"text": "Python разработчик", "area": {"id": "1"}}'}),
        }
        labels = {
            'name': 'Название аккаунта',
            'username': 'Email (логин) HH.ru',
            'password': 'Пароль HH.ru',
            'resume_id': 'ID резюме',
            'cover_letter': 'Сопроводительное письмо',
            'search_filters': 'Фильтры поиска (JSON)',
            'enabled': 'Активен',
            'auto_apply': 'Автоотклик',
            'max_applications_per_day': 'Макс. откликов в день',
        }
