from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from accounts.models import HHAccount, RunLog
from core.tasks import run_auto_apply_task, run_all_enabled_accounts


@login_required
def dashboard(request):
    """Панель управления пользователя"""
    # Получаем все аккаунты пользователя
    accounts = HHAccount.objects.filter(user=request.user)
    accounts_count = accounts.count()
    
    # Получаем последние логи запусков для аккаунтов пользователя
    recent_logs = RunLog.objects.filter(
        account__user=request.user
    ).select_related('account').order_by('-started_at')[:10]
    
    context = {
        'accounts_count': accounts_count,
        'recent_logs': recent_logs,
    }
    
    return render(request, 'core/dashboard.html', context)


@login_required
def run_auto_apply_all(request):
    """Запуск автооткликов для всех активных аккаунтов пользователя"""
    dry_run = request.POST.get('dry_run', 'false').lower() == 'true'
    
    # Получаем только активные аккаунты с включенным автооткликом
    enabled_accounts = HHAccount.objects.filter(
        user=request.user,
        enabled=True,
        auto_apply=True
    )
    
    if not enabled_accounts.exists():
        messages.warning(request, "Нет активных аккаунтов с включенным автооткликом")
        return redirect('dashboard')
    
    # Запускаем задачи для каждого аккаунта
    task_ids = []
    for account in enabled_accounts:
        result = run_auto_apply_task.delay(account.id, dry_run=dry_run)
        task_ids.append(result.id)
    
    mode = "Тестовый" if dry_run else ""
    messages.success(request, f"{mode} Запущено {len(task_ids)} задач автоотклика")
    
    return redirect('dashboard')
