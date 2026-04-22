from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required
from django.contrib.auth import login, logout
from django.contrib import messages
from django.utils import timezone
import json

from accounts.models import HHAccount, RunLog
from accounts.forms import RegisterForm, HHAccountForm, SearchFiltersForm
from core.tasks import run_auto_apply_task, run_all_enabled_accounts


@login_required
def account_list(request):
    """Список аккаунтов пользователя"""
    accounts = HHAccount.objects.filter(user=request.user)
    return render(request, 'account_list.html', {'accounts': accounts})


@login_required
def account_create(request):
    """Создание нового аккаунта HH.ru"""
    if request.method == 'POST':
        form = HHAccountForm(request.POST)
        filters_form = SearchFiltersForm(request.POST)
        
        if form.is_valid() and filters_form.is_valid():
            account = form.save(commit=False)
            account.user = request.user
            
            # Сохраняем фильтры в JSON формате
            search_filters = filters_form.to_json()
            account.search_filters = search_filters
            
            account.save()
            messages.success(request, f"Аккаунт '{account.name}' успешно создан")
            return redirect('account_list')
    else:
        form = HHAccountForm()
        filters_form = SearchFiltersForm()
    
    return render(request, 'account_form.html', {
        'form': form, 
        'filters_form': filters_form,
        'title': 'Добавить аккаунт'
    })


@login_required
def account_edit(request, pk):
    """Редактирование аккаунта HH.ru"""
    account = get_object_or_404(HHAccount, pk=pk, user=request.user)
    
    if request.method == 'POST':
        form = HHAccountForm(request.POST, instance=account)
        filters_form = SearchFiltersForm(request.POST)
        
        if form.is_valid() and filters_form.is_valid():
            account = form.save(commit=False)
            
            # Сохраняем фильтры в JSON формате
            search_filters = filters_form.to_json()
            account.search_filters = search_filters
            
            account.save()
            messages.success(request, f"Аккаунт '{account.name}' успешно обновлён")
            return redirect('account_list')
    else:
        form = HHAccountForm(instance=account)
        # Инициализируем форму фильтров существующими данными
        initial_filters = account.search_filters if account.search_filters else {}
        filters_form = SearchFiltersForm(initial_filters=initial_filters)
    
    return render(request, 'account_form.html', {
        'form': form, 
        'filters_form': filters_form,
        'title': f'Редактировать: {account.name}'
    })


@login_required
def account_delete(request, pk):
    """Удаление аккаунта HH.ru"""
    account = get_object_or_404(HHAccount, pk=pk, user=request.user)
    
    if request.method == 'POST':
        account.delete()
        messages.success(request, f"Аккаунт '{account.name}' удалён")
        return redirect('account_list')
    
    return render(request, 'account_confirm_delete.html', {'account': account})


@login_required
def account_run(request, pk):
    """Запуск автоотклика для конкретного аккаунта"""
    account = get_object_or_404(HHAccount, pk=pk, user=request.user)
    dry_run = request.POST.get('dry_run', 'false').lower() == 'true'
    
    result = run_auto_apply_task.delay(account.id, dry_run=dry_run)
    
    mode = "Тестовый" if dry_run else ""
    messages.success(request, f"{mode} Запущена задача автоотклика для аккаунта '{account.name}'")
    
    return redirect('account_list')
