from django.contrib import admin
from .models import HHAccount, AppliedVacancy, RunLog


@admin.register(HHAccount)
class HHAccountAdmin(admin.ModelAdmin):
    list_display = ['name', 'username', 'user', 'enabled', 'auto_apply', 'created_at']
    list_filter = ['enabled', 'auto_apply', 'user']
    search_fields = ['name', 'username', 'user__username']
    readonly_fields = ['created_at', 'updated_at', 'last_run']
    fieldsets = (
        ('Основная информация', {
            'fields': ('user', 'name', 'username', 'password')
        }),
        ('Настройки отклика', {
            'fields': ('resume_id', 'cover_letter', 'search_filters')
        }),
        ('Статус', {
            'fields': ('enabled', 'auto_apply', 'max_applications_per_day')
        }),
        ('Метаданные', {
            'fields': ('created_at', 'updated_at', 'last_run'),
            'classes': ('collapse',)
        }),
    )


@admin.register(AppliedVacancy)
class AppliedVacancyAdmin(admin.ModelAdmin):
    list_display = ['vacancy_title', 'account', 'status', 'applied_at']
    list_filter = ['status', 'account', 'applied_at']
    search_fields = ['vacancy_title', 'company_name', 'account__name']
    readonly_fields = ['applied_at']


@admin.register(RunLog)
class RunLogAdmin(admin.ModelAdmin):
    list_display = ['account', 'started_at', 'finished_at', 'success_count', 'failed_count', 'status']
    list_filter = ['status', 'account', 'started_at']
    search_fields = ['account__name', 'account__username']
    readonly_fields = ['started_at', 'finished_at']

