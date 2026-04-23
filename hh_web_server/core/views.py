from django.shortcuts import render, redirect
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone

from accounts.models import HHAccount, RunLog
from accounts.forms import RegisterForm
from core.tasks import run_auto_apply_task


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
    
    return render(request, 'dashboard.html', context)


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


def register(request):
    """Регистрация нового пользователя"""
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            user = form.save()
            login(request, user)
            messages.success(request, "Регистрация успешна! Добро пожаловать.")
            return redirect('dashboard')
    else:
        form = RegisterForm()
    
    return render(request, 'register.html', {'form': form})


def login_view(request):
    """Вход в систему"""
    from django.contrib.auth import authenticate
    
    if request.method == 'POST':
        username = request.POST.get('username')
        password = request.POST.get('password')
        user = authenticate(request, username=username, password=password)
        
        if user is not None:
            login(request, user)
            messages.success(request, "Вы успешно вошли в систему")
            return redirect('dashboard')
        else:
            messages.error(request, "Неверное имя пользователя или пароль")
    
    return render(request, 'login.html')


@login_required
def logout_view(request):
    """Выход из системы"""
    logout(request)
    messages.info(request, "Вы вышли из системы")
    return redirect('login')
