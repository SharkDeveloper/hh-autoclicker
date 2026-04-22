from django import forms
from django.contrib.auth.models import User
from accounts.models import HHAccount
import json


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


class SearchFiltersForm(forms.Form):
    """Удобная форма для настройки поисковых фильтров"""
    
    # Основные параметры
    text = forms.CharField(
        required=False,
        label="Ключевые слова",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Например: Python разработчик'
        })
    )
    
    area = forms.CharField(
        required=False,
        label="Город/Регион",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Например: Москва'
        })
    )
    
    salary = forms.IntegerField(
        required=False,
        label="Минимальная зарплата (руб.)",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': 'Например: 100000'
        })
    )
    
    # Опыт работы
    EXPERIENCE_CHOICES = [
        ('', 'Не важно'),
        ('noExperience', 'Нет опыта'),
        ('between1And3', 'От 1 года до 3 лет'),
        ('between3And6', 'От 3 до 6 лет'),
        ('moreThan6', 'Более 6 лет'),
    ]
    experience = forms.ChoiceField(
        required=False,
        choices=EXPERIENCE_CHOICES,
        label="Опыт работы",
        widget=forms.Select(attrs={'class': 'form-select'})
    )
    
    # Тип занятости
    EMPLOYMENT_CHOICES = [
        ('full', 'Полная занятость'),
        ('part', 'Частичная занятость'),
        ('project', 'Проектная работа'),
        ('internship', 'Стажировка'),
    ]
    employment = forms.MultipleChoiceField(
        required=False,
        choices=EMPLOYMENT_CHOICES,
        label="Тип занятости",
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    
    # График работы
    SCHEDULE_CHOICES = [
        ('fullDay', 'Полный день'),
        ('shift', 'Сменный график'),
        ('flexible', 'Гибкий график'),
        ('remote', 'Удалённая работа'),
        ('vacation', 'Вахтовый метод'),
    ]
    schedule = forms.MultipleChoiceField(
        required=False,
        choices=SCHEDULE_CHOICES,
        label="График работы",
        widget=forms.CheckboxSelectMultiple(attrs={'class': 'form-check-input'})
    )
    
    # Дополнительные опции
    only_with_salary = forms.BooleanField(
        required=False,
        label="Только с указанной зарплатой",
        widget=forms.CheckboxInput(attrs={'class': 'form-check-input'})
    )
    
    # Режим поиска
    SEARCH_MODE_CHOICES = [
        ('manual', 'По фильтрам'),
        ('auto', 'Авто-подбор по вакансии'),
        ('recommendations', 'Рекомендации HH'),
    ]
    search_mode = forms.ChoiceField(
        required=False,
        choices=SEARCH_MODE_CHOICES,
        initial='manual',
        label="Режим поиска",
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    
    # URL вакансии для авто-подбора
    vacancy_url = forms.URLField(
        required=False,
        label="URL вакансии для авто-подбора",
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://hh.ru/vacancy/...'
        })
    )

    def __init__(self, *args, **kwargs):
        """Инициализация формы с существующими фильтрами"""
        initial_filters = kwargs.pop('initial_filters', {})
        super().__init__(*args, **kwargs)
        
        if initial_filters:
            # Заполняем форму существующими значениями
            self.fields['text'].initial = initial_filters.get('text', '')
            self.fields['area'].initial = initial_filters.get('area', '')
            self.fields['salary'].initial = initial_filters.get('salary', '')
            self.fields['experience'].initial = initial_filters.get('experience', '')
            
            # Обрабатываем множественные поля
            employment = initial_filters.get('employment', [])
            if isinstance(employment, str):
                employment = [employment]
            self.fields['employment'].initial = employment
            
            schedule = initial_filters.get('schedule', [])
            if isinstance(schedule, str):
                schedule = [schedule]
            self.fields['schedule'].initial = schedule
            
            self.fields['only_with_salary'].initial = initial_filters.get('only_with_salary', False)
            self.fields['search_mode'].initial = initial_filters.get('search_mode', 'manual')
            self.fields['vacancy_url'].initial = initial_filters.get('vacancy_url', '')

    def to_json(self):
        """Конвертация данных формы в JSON формат"""
        cleaned = self.cleaned_data
        
        filters = {}
        
        # Основной режим поиска
        search_mode = cleaned.get('search_mode', 'manual')
        
        if search_mode == 'recommendations':
            # Режим рекомендаций - пустые фильтры
            return {'search_mode': 'recommendations'}
        
        elif search_mode == 'auto' and cleaned.get('vacancy_url'):
            # Авто-подбор по вакансии
            return {
                'search_mode': 'auto',
                'vacancy_url': cleaned['vacancy_url']
            }
        
        else:
            # Ручной режим с фильтрами
            if cleaned.get('text'):
                filters['text'] = cleaned['text']
            if cleaned.get('area'):
                # Если область - строка, оставляем как есть, иначе преобразуем
                area = cleaned['area']
                if isinstance(area, str) and area.strip():
                    filters['area'] = area
            if cleaned.get('salary') and cleaned['salary'] > 0:
                filters['salary'] = cleaned['salary']
                filters['only_with_salary'] = True
            elif cleaned.get('only_with_salary'):
                filters['only_with_salary'] = True
            if cleaned.get('experience'):
                filters['experience'] = cleaned['experience']
            if cleaned.get('employment'):
                filters['employment'] = cleaned['employment']
            if cleaned.get('schedule'):
                filters['schedule'] = cleaned['schedule']
            
            filters['search_mode'] = 'manual'
            return filters
