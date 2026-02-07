"""
Скрипт для мониторинга нарушений лицензии проекта hh-autoclicker
Использует GitHub API для поиска потенциальных нарушений
"""
import requests
import json
from datetime import datetime
from typing import List, Dict
import time

# Конфигурация
GITHUB_TOKEN = ""  # Получите токен на https://github.com/settings/tokens
PROJECT_NAME = "hh-autoclicker"
UNIQUE_CODE_SNIPPETS = [
    "hh_auto_apply",
    "HHAutoApply",
    "expand-login-by-password",
    "vacancy_response",
    "serp-item__title",
    "applicant-login-input-email"
]

def search_github_code(query: str, token: str = None) -> List[Dict]:
    """Поиск кода на GitHub"""
    url = f"https://api.github.com/search/code"
    headers = {
        "Accept": "application/vnd.github.v3+json"
    }
    if token:
        headers["Authorization"] = f"token {token}"
    
    params = {
        "q": query,
        "per_page": 100
    }
    
    try:
        response = requests.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json().get("items", [])
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при поиске: {e}")
        return []

def check_repository(repo_url: str, token: str = None) -> Dict:
    """Проверка репозитория на коммерческое использование"""
    # Извлекаем owner/repo из URL
    parts = repo_url.replace("https://github.com/", "").split("/")
    if len(parts) < 2:
        return None
    
    owner, repo = parts[0], parts[1]
    api_url = f"https://api.github.com/repos/{owner}/{repo}"
    
    headers = {
        "Accept": "application/vnd.github.v3+json"
    }
    if token:
        headers["Authorization"] = f"token {token}"
    
    try:
        response = requests.get(api_url, headers=headers)
        response.raise_for_status()
        repo_data = response.json()
        
        # Проверяем признаки коммерческого использования
        commercial_indicators = []
        
        # Проверка описания
        description = repo_data.get("description", "").lower()
        if any(word in description for word in ["paid", "commercial", "service", "sell", "buy"]):
            commercial_indicators.append("Описание содержит коммерческие термины")
        
        # Проверка тегов
        topics = repo_data.get("topics", [])
        if any(topic in ["commercial", "paid", "service"] for topic in topics):
            commercial_indicators.append("Теги указывают на коммерческое использование")
        
        # Проверка лицензии
        license_info = repo_data.get("license")
        if license_info and "mit" not in license_info.get("spdx_id", "").lower():
            commercial_indicators.append("Используется другая лицензия")
        
        return {
            "name": repo_data.get("full_name"),
            "url": repo_data.get("html_url"),
            "description": repo_data.get("description"),
            "license": license_info.get("spdx_id") if license_info else "Не указана",
            "stars": repo_data.get("stargazers_count", 0),
            "forks": repo_data.get("forks_count", 0),
            "created": repo_data.get("created_at"),
            "updated": repo_data.get("updated_at"),
            "commercial_indicators": commercial_indicators,
            "is_fork": repo_data.get("fork", False)
        }
    except requests.exceptions.RequestException as e:
        print(f"Ошибка при проверке репозитория {repo_url}: {e}")
        return None

def monitor_violations(token: str = None):
    """Основная функция мониторинга"""
    print("=" * 60)
    print("МОНИТОРИНГ НАРУШЕНИЙ ЛИЦЕНЗИИ")
    print("=" * 60)
    print(f"Дата проверки: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print()
    
    all_found_repos = set()
    violations = []
    
    # Поиск по уникальным фрагментам кода
    for snippet in UNIQUE_CODE_SNIPPETS:
        print(f"Поиск по фрагменту: '{snippet}'...")
        results = search_github_code(f'"{snippet}"', token)
        
        for item in results:
            repo_url = item.get("repository", {}).get("html_url", "")
            if repo_url:
                all_found_repos.add(repo_url)
        
        print(f"  Найдено репозиториев: {len(results)}")
        time.sleep(1)  # Задержка для соблюдения rate limit
    
    print(f"\nВсего найдено уникальных репозиториев: {len(all_found_repos)}")
    print("\nПроверка репозиториев на коммерческое использование...")
    print()
    
    # Проверка каждого репозитория
    for i, repo_url in enumerate(all_found_repos, 1):
        print(f"[{i}/{len(all_found_repos)}] Проверка: {repo_url}")
        repo_info = check_repository(repo_url, token)
        
        if repo_info:
            # Пропускаем форки оригинального репозитория
            if repo_info["is_fork"] and PROJECT_NAME.lower() in repo_info["name"].lower():
                print("  ⏭️  Пропущено (форк оригинального репозитория)")
                continue
            
            # Проверяем на признаки коммерческого использования
            if repo_info["commercial_indicators"]:
                violations.append(repo_info)
                print(f"  ⚠️  ПОДОЗРЕНИЕ НА НАРУШЕНИЕ!")
                for indicator in repo_info["commercial_indicators"]:
                    print(f"      - {indicator}")
            else:
                print("  ✓ Нет явных признаков коммерческого использования")
        
        time.sleep(0.5)  # Задержка для соблюдения rate limit
    
    # Вывод результатов
    print("\n" + "=" * 60)
    print("РЕЗУЛЬТАТЫ МОНИТОРИНГА")
    print("=" * 60)
    
    if violations:
        print(f"\n⚠️  Найдено потенциальных нарушений: {len(violations)}\n")
        for i, violation in enumerate(violations, 1):
            print(f"{i}. {violation['name']}")
            print(f"   URL: {violation['url']}")
            print(f"   Лицензия: {violation['license']}")
            print(f"   Звезды: {violation['stars']}, Форков: {violation['forks']}")
            print(f"   Признаки нарушения:")
            for indicator in violation['commercial_indicators']:
                print(f"     - {indicator}")
            print()
        
        # Сохранение результатов
        report_file = f"license_violations_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(report_file, 'w', encoding='utf-8') as f:
            json.dump(violations, f, ensure_ascii=False, indent=2)
        print(f"📄 Отчет сохранен в: {report_file}")
    else:
        print("\n✅ Нарушений не обнаружено")
    
    print("\n" + "=" * 60)
    print("Мониторинг завершен")
    print("=" * 60)

if __name__ == "__main__":
    import sys
    
    # Проверка наличия токена
    if len(sys.argv) > 1:
        token = sys.argv[1]
    else:
        token = GITHUB_TOKEN
        if not token:
            print("⚠️  ВНИМАНИЕ: GitHub токен не указан!")
            print("   Без токена количество запросов ограничено (60/час)")
            print("   Для получения токена: https://github.com/settings/tokens")
            print("   Использование: python monitor_license_violations.py YOUR_TOKEN")
            print()
            response = input("Продолжить без токена? (y/n): ")
            if response.lower() != 'y':
                sys.exit(0)
    
    monitor_violations(token)

