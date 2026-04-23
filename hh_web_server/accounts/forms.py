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
    """Форма управления аккаунтом HH.ru с удобным интерфейсом"""
    
    # Дополнительные поля для удобного редактирования фильтров
    search_text = forms.CharField(
        required=False,
        label="Ключевые слова",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Например: Python разработчик'
        })
    )
    search_area = forms.CharField(
        required=False,
        label="Город",
        widget=forms.TextInput(attrs={
            'class': 'form-control',
            'placeholder': 'Например: Москва'
        })
    )
    search_salary = forms.IntegerField(
        required=False,
        label="Зарплата от (руб.)",
        widget=forms.NumberInput(attrs={
            'class': 'form-control',
            'placeholder': '100000'
        })
    )
    
    # Сопроводительное письмо (исправление бага - явное поле)
    cover_letter = forms.CharField(
        required=False,
        label="Сопроводительное письмо",
        widget=forms.Textarea(attrs={
            'class': 'form-control',
            'rows': 4,
            'placeholder': 'Введите текст сопроводительного письма. Оставьте пустым для авто-генерации из вакансии.'
        })
    )
    
    # Режим поиска
    SEARCH_MODE_CHOICES = [
        ('manual', '🔍 По фильтрам ниже'),
        ('auto', '🎯 Авто-подбор по вакансии (HH сам подбирает)'),
        ('recommendations', '⭐ Рекомендации HH (без фильтров)'),
    ]
    search_mode = forms.ChoiceField(
        required=False,
        choices=SEARCH_MODE_CHOICES,
        initial='manual',
        label="Режим поиска вакансий",
        widget=forms.RadioSelect(attrs={'class': 'form-check-input'})
    )
    
    # URL вакансии для авто-подбора
    vacancy_url = forms.URLField(
        required=False,
        label="URL примера вакансии (для авто-подбора)",
        widget=forms.URLInput(attrs={
            'class': 'form-control',
            'placeholder': 'https://hh.ru/vacancy/12345678'
        })
    )

    class Meta:
        model = HHAccount
        fields = ['name', 'username', 'password', 'resume_id', 'cover_letter', 
                  'search_filters', 'enabled', 'auto_apply', 'max_applications_per_day',
                  'search_text', 'search_area', 'search_salary', 'search_mode', 'vacancy_url']
        widgets = {
            'name': forms.TextInput(attrs={'class': 'form-control'}),
            'username': forms.TextInput(attrs={'class': 'form-control', 'type': 'email'}),
            'password': forms.PasswordInput(attrs={'class': 'form-control'}),
            'resume_id': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Например: HZ1234567'}),
            'search_filters': forms.HiddenInput(),  # Скрываем JSON поле, работаем через форму
            'enabled': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'auto_apply': forms.CheckboxInput(attrs={'class': 'form-check-input'}),
            'max_applications_per_day': forms.NumberInput(attrs={'class': 'form-control', 'min': 1, 'max': 500}),
        }
        labels = {
            'name': 'Название аккаунта',
            'username': 'Email (логин) HH.ru',
            'password': 'Пароль HH.ru',
            'resume_id': 'ID резюме',
            'enabled': 'Активен',
            'auto_apply': 'Включить автоотклик',
            'max_applications_per_day': 'Макс. откликов в день',
        }

    def __init__(self, *args, **kwargs):
        """Инициализация формы с распаковкой фильтров из JSON"""
        super().__init__(*args, **kwargs)
        
        # Если редактируем существующий аккаунт, распарсиваем search_filters
        if self.instance.pk and self.instance.search_filters:
            try:
                filters = json.loads(self.instance.search_filters)
                
                # Заполняем простые поля
                self.fields['search_text'].initial = filters.get('text', '')
                
                # Область может быть строкой или объектом
                area = filters.get('area', '')
                if isinstance(area, dict):
                    area = area.get('name', '')
                self.fields['search_area'].initial = area
                
                self.fields['search_salary'].initial = filters.get('salary', None)
                self.fields['search_mode'].initial = filters.get('search_mode', 'manual')
                self.fields['vacancy_url'].initial = filters.get('vacancy_url', '')
                
            except (json.JSONDecodeError, TypeError, AttributeError):
                pass
        
        # Порядок полей для лучшего UX
        self.order_fields([
            'name', 'username', 'password', 'resume_id',
            'enabled', 'auto_apply', 'max_applications_per_day',
            'search_mode', 'vacancy_url',  # Режим поиска
            'search_text', 'search_area', 'search_salary',  # Фильтры
            'cover_letter',  # Письмо
            'search_filters',  # Скрытое поле
        ])

    def save(self, commit=True):
        """Сохранение с упаковкой фильтров в JSON"""
        instance = super().save(commit=False)
        
        # Получаем режим поиска
        search_mode = self.cleaned_data.get('search_mode', 'manual')
        
        # Формируем JSON фильтров в зависимости от режима
        filters_data = {}
        
        if search_mode == 'recommendations':
            # Режим рекомендаций HH - минимальные фильтры
            filters_data = {
                'search_mode': 'recommendations',
                'text': self.cleaned_data.get('search_text', ''),
            }
            
        elif search_mode == 'auto' and self.cleaned_data.get('vacancy_url'):
            # Авто-подбор по примеру вакансии
            filters_data = {
                'search_mode': 'auto',
                'vacancy_url': self.cleaned_data['vacancy_url'],
                'text': self.cleaned_data.get('search_text', ''),
            }
            
        else:
            # Ручной режим с фильтрами
            filters_data = {'search_mode': 'manual'}
            
            if self.cleaned_data.get('search_text'):
                filters_data['text'] = self.cleaned_data['search_text']
            
            if self.cleaned_data.get('search_area'):
                filters_data['area'] = self.cleaned_data['search_area']
            
            if self.cleaned_data.get('search_salary') and self.cleaned_data['search_salary'] > 0:
                filters_data['salary'] = self.cleaned_data['search_salary']
                filters_data['only_with_salary'] = True
        
        # Сохраняем JSON
        instance.search_filters = json.dumps(filters_data, ensure_ascii=False)
        
        if commit:
            instance.save()
        return instance


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
