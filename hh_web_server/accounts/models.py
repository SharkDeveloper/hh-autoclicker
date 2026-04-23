from django.db import models
from django.contrib.auth.models import User


class HHAccount(models.Model):
    """Модель аккаунта HeadHunter для пользователя"""
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='hh_accounts')
    name = models.CharField(max_length=255, verbose_name="Название аккаунта")
    username = models.EmailField(verbose_name="Email (логин) HH.ru")
    password = models.CharField(max_length=255, verbose_name="Пароль HH.ru")
    resume_id = models.CharField(max_length=255, blank=True, verbose_name="ID резюме")
    cover_letter = models.TextField(blank=True, verbose_name="Сопроводительное письмо")
    
    # Поисковые фильтры как JSON
    search_filters = models.JSONField(default=dict, blank=True, verbose_name="Фильтры поиска")
    
    # Настройки
    enabled = models.BooleanField(default=True, verbose_name="Активен")
    auto_apply = models.BooleanField(default=False, verbose_name="Автоотклик")
    max_applications_per_day = models.PositiveIntegerField(default=20, verbose_name="Макс. откликов в день")
    
    # Метаданные
    created_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата создания")
    updated_at = models.DateTimeField(auto_now=True, verbose_name="Дата обновления")
    last_run = models.DateTimeField(null=True, blank=True, verbose_name="Последний запуск")
    
    class Meta:
        verbose_name = "Аккаунт HH.ru"
        verbose_name_plural = "Аккаунты HH.ru"
        ordering = ['name']
    
    def __str__(self):
        return f"{self.name} ({self.username})"


class AppliedVacancy(models.Model):
    """Модель откликнутых вакансий"""
    
    account = models.ForeignKey(HHAccount, on_delete=models.CASCADE, related_name='applied_vacancies')
    vacancy_id = models.CharField(max_length=255, verbose_name="ID вакансии")
    vacancy_url = models.URLField(verbose_name="URL вакансии")
    vacancy_title = models.CharField(max_length=500, verbose_name="Название вакансии")
    company_name = models.CharField(max_length=255, blank=True, verbose_name="Компания")
    
    # Статус отклика
    STATUS_CHOICES = [
        ('pending', 'Ожидает'),
        ('success', 'Успешно'),
        ('failed', 'Ошибка'),
        ('skipped', 'Пропущено'),
    ]
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='pending', verbose_name="Статус")
    
    applied_at = models.DateTimeField(auto_now_add=True, verbose_name="Дата отклика")
    error_message = models.TextField(blank=True, verbose_name="Сообщение об ошибке")
    
    class Meta:
        verbose_name = "Отклик на вакансию"
        verbose_name_plural = "Отклики на вакансии"
        ordering = ['-applied_at']
        unique_together = ['account', 'vacancy_id']
    
    def __str__(self):
        return f"{self.vacancy_title} - {self.account.name} ({self.status})"


class RunLog(models.Model):
    """Лог запусков автооткликов"""
    
    account = models.ForeignKey(HHAccount, on_delete=models.CASCADE, related_name='run_logs')
    started_at = models.DateTimeField(auto_now_add=True, verbose_name="Начало")
    finished_at = models.DateTimeField(null=True, blank=True, verbose_name="Окончание")
    
    success_count = models.PositiveIntegerField(default=0, verbose_name="Успешных откликов")
    failed_count = models.PositiveIntegerField(default=0, verbose_name="Ошибок")
    skipped_count = models.PositiveIntegerField(default=0, verbose_name="Пропущено")
    
    status = models.CharField(max_length=20, default='running', verbose_name="Статус")
    error_message = models.TextField(blank=True, verbose_name="Сообщение об ошибке")
    
    class Meta:
        verbose_name = "Лог запуска"
        verbose_name_plural = "Логи запусков"
        ordering = ['-started_at']
    
    def __str__(self):
        return f"{self.account.name} - {self.started_at}"

