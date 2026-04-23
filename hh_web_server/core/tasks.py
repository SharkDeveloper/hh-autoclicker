from celery import shared_task
import logging
import sys
import os

logger = logging.getLogger(__name__)


@shared_task(bind=True)
def run_auto_apply_task(self, account_id: int, dry_run: bool = False):
    """
    Запуск автоотклика для конкретного аккаунта через hh_auto_apply ядро.
    
    Args:
        account_id: ID аккаунта HHAccount в БД
        dry_run: Если True - симуляция без реальных откликов
    """
    from accounts.models import HHAccount, RunLog
    from django.utils import timezone
    
    try:
        account = HHAccount.objects.get(id=account_id)
    except HHAccount.DoesNotExist:
        logger.error(f"Аккаунт {account_id} не найден")
        return {'success': 0, 'failed': 0, 'error': 'Account not found'}
    
    # Создаём запись лога запуска
    run_log = RunLog.objects.create(
        account=account,
        status='running'
    )
    
    try:
        # Добавляем путь к hh_auto_apply
        hh_core_path = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'hh_auto_apply')
        if hh_core_path not in sys.path:
            sys.path.insert(0, hh_core_path)
        
        from src.core.application import HHAutoApply
        
        # Определяем режим поиска и параметры
        search_filters = account.search_filters or {}
        search_mode = search_filters.get('search_mode', 'manual')
        
        # Определяем режим для приложения
        if search_mode == 'recommendations':
            app_mode = 'recommendations'
            search_criteria = None
        elif search_mode == 'auto' and search_filters.get('vacancy_url'):
            # Авто-подбор по вакансии: извлекаем ключевые слова из URL или используем рекомендации
            app_mode = 'recommendations'  # Пока используем рекомендации как fallback
            search_criteria = None
        else:
            # Ручной режим с фильтрами
            app_mode = 'auto'
            # Преобразуем фильтры в формат, понятный search_module
            search_criteria = {k: v for k, v in search_filters.items() 
                             if k not in ['search_mode', 'vacancy_url']}
        
        # Формируем конфигурацию для запуска
        account_override = {
            'username': account.username,
            'password': account.password,
            'resume_id': account.resume_id,
            'cover_letter': account.cover_letter,
            'search_filters': search_criteria,
        }
        
        # Используем временный конфиг или дефолтный
        config_path = os.path.join(hh_core_path, 'config', 'default.json')
        
        app = HHAutoApply(config_path)
        results = app.run(
            mode=app_mode,
            search_criteria=search_criteria,
            dry_run=dry_run,
            account_override=account_override,
        )
        
        # Обновляем лог
        run_log.success_count = results.get('success', 0)
        run_log.failed_count = results.get('failed', 0)
        run_log.skipped_count = results.get('skipped', 0)
        run_log.status = 'completed'
        run_log.finished_at = timezone.now()
        
        # Обновляем last_run у аккаунта
        account.last_run = timezone.now()
        account.save()
        
        logger.info(f"Завершён запуск для аккаунта {account.username}: успешно={results.get('success', 0)}, ошибок={results.get('failed', 0)}")
        
    except Exception as e:
        logger.exception(f"Ошибка при запуске автоотклика для аккаунта {account_id}: {e}")
        run_log.status = 'failed'
        run_log.error_message = str(e)
        run_log.finished_at = timezone.now()
        results = {'success': 0, 'failed': 1, 'error': str(e)}
    
    finally:
        run_log.save()
    
    return results


@shared_task(bind=True)
def run_all_enabled_accounts(self, dry_run: bool = False):
    """
    Запуск автооткликов для всех активных аккаунтов всех пользователей.
    """
    from accounts.models import HHAccount
    from django.utils import timezone
    
    enabled_accounts = HHAccount.objects.filter(enabled=True, auto_apply=True)
    
    if not enabled_accounts.exists():
        logger.info("Нет активных аккаунтов с включенным автооткликом")
        return {'total': 0, 'results': []}
    
    results = []
    for account in enabled_accounts:
        # Запускаем задачу для каждого аккаунта с небольшой задержкой
        result = run_auto_apply_task.delay(account.id, dry_run=dry_run)
        results.append({'account_id': account.id, 'task_id': result.id})
    
    logger.info(f"Запущено {len(results)} задач автоотклика")
    
    return {'total': len(results), 'results': results}
