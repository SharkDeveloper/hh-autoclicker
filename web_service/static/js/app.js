/*
 * Основной JavaScript файл для веб-интерфейса HH Auto Apply
 * Содержит общие функции и утилиты
 */

// Глобальные переменные
let currentJobSocket = null;
let notificationTimeout = null;

/**
 * Показывает уведомление на странице
 * @param {string} message - Текст уведомления
 * @param {string} type - Тип уведомления (success, danger, warning, info)
 * @param {number} duration - Длительность показа в миллисекундах (по умолчанию 5000)
 */
function showNotification(message, type = 'info', duration = 5000) {
    const container = document.getElementById('notifications-container');
    if (!container) {
        console.warn('Контейнер для уведомлений не найден');
        return;
    }
    
    const alert = document.createElement('div');
    alert.className = `alert alert-${type} alert-dismissible fade show fade-in`;
    alert.innerHTML = `
        <div class="d-flex align-items-center">
            <i class="bi ${getNotificationIcon(type)} me-2"></i>
            <div>${message}</div>
        </div>
        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
    `;
    
    container.appendChild(alert);
    
    // Автоматическое скрытие
    if (duration > 0) {
        setTimeout(() => {
            if (alert.parentNode) {
                alert.classList.remove('show');
                setTimeout(() => alert.remove(), 150);
            }
        }, duration);
    }
    
    return alert;
}

/**
 * Возвращает иконку для типа уведомления
 */
function getNotificationIcon(type) {
    switch(type) {
        case 'success': return 'bi-check-circle-fill';
        case 'danger': return 'bi-exclamation-triangle-fill';
        case 'warning': return 'bi-exclamation-circle-fill';
        case 'info': return 'bi-info-circle-fill';
        default: return 'bi-info-circle';
    }
}

/**
 * Форматирует дату в читаемый вид
 */
function formatDate(dateString) {
    if (!dateString) return 'Неизвестно';
    
    const date = new Date(dateString);
    if (isNaN(date.getTime())) return dateString;
    
    return date.toLocaleString('ru-RU', {
        day: '2-digit',
        month: '2-digit',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * Форматирует продолжительность в секундах в читаемый вид
 */
function formatDuration(seconds) {
    if (!seconds) return '0 сек';
    
    const hours = Math.floor(seconds / 3600);
    const minutes = Math.floor((seconds % 3600) / 60);
    const secs = Math.floor(seconds % 60);
    
    const parts = [];
    if (hours > 0) parts.push(`${hours} ч`);
    if (minutes > 0) parts.push(`${minutes} мин`);
    if (secs > 0 || parts.length === 0) parts.push(`${secs} сек`);
    
    return parts.join(' ');
}

/**
 * Форматирует число с разделителями тысяч
 */
function formatNumber(num) {
    return num.toString().replace(/\B(?=(\d{3})+(?!\d))/g, ' ');
}

/**
 * Загружает данные с API с обработкой ошибок
 */
async function fetchData(url, options = {}) {
    try {
        const response = await fetch(url, {
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            },
            ...options
        });
        
        if (!response.ok) {
            const error = await response.json().catch(() => ({ detail: `HTTP ${response.status}` }));
            throw new Error(error.detail || `Ошибка ${response.status}`);
        }
        
        return await response.json();
    } catch (error) {
        console.error('Ошибка загрузки данных:', error);
        showNotification(`Ошибка загрузки данных: ${error.message}`, 'danger');
        throw error;
    }
}

/**
 * Отправляет данные на API
 */
async function postData(url, data) {
    return fetchData(url, {
        method: 'POST',
        body: JSON.stringify(data)
    });
}

/**
 * Обновляет данные на API
 */
async function putData(url, data) {
    return fetchData(url, {
        method: 'PUT',
        body: JSON.stringify(data)
    });
}

/**
 * Удаляет данные через API
 */
async function deleteData(url) {
    return fetchData(url, { method: 'DELETE' });
}

/**
 * Подключается к WebSocket для получения обновлений задачи
 */
function connectJobWebSocket(jobId, onUpdate) {
    if (currentJobSocket) {
        currentJobSocket.close();
    }
    
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:';
    const wsUrl = `${protocol}//${window.location.host}/ws`;
    
    const socket = new WebSocket(wsUrl);
    currentJobSocket = socket;
    
    socket.onopen = () => {
        console.log(`WebSocket подключен для задачи ${jobId}`);
        socket.send(JSON.stringify({ type: 'subscribe', job_id: jobId }));
    };
    
    socket.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (onUpdate && typeof onUpdate === 'function') {
                onUpdate(data);
            }
        } catch (error) {
            console.error('Ошибка парсинга WebSocket сообщения:', error);
        }
    };
    
    socket.onerror = (error) => {
        console.error('WebSocket ошибка:', error);
    };
    
    socket.onclose = () => {
        console.log('WebSocket соединение закрыто');
        currentJobSocket = null;
    };
    
    return socket;
}

/**
 * Создает индикатор загрузки
 */
function createLoader(text = 'Загрузка...') {
    const loader = document.createElement('div');
    loader.className = 'text-center py-4';
    loader.innerHTML = `
        <div class="spinner-border text-primary" role="status">
            <span class="visually-hidden">${text}</span>
        </div>
        <p class="mt-2">${text}</p>
    `;
    return loader;
}

/**
 * Создает пустое состояние
 */
function createEmptyState(icon = 'bi-inbox', title = 'Данные отсутствуют', message = 'Нет данных для отображения') {
    const emptyState = document.createElement('div');
    emptyState.className = 'text-center py-5';
    emptyState.innerHTML = `
        <i class="bi ${icon} display-4 text-muted"></i>
        <h5 class="mt-3">${title}</h5>
        <p class="text-muted">${message}</p>
    `;
    return emptyState;
}

/**
 * Создает пагинацию
 */
function createPagination(total, limit, currentPage, onPageChange) {
    if (total <= limit) return null;
    
    const totalPages = Math.ceil(total / limit);
    const pagination = document.createElement('nav');
    pagination.setAttribute('aria-label', 'Навигация по страницам');
    
    let html = '<ul class="pagination justify-content-center">';
    
    // Кнопка "Назад"
    html += `
        <li class="page-item ${currentPage === 1 ? 'disabled' : ''}">
            <a class="page-link" href="#" ${currentPage > 1 ? `onclick="event.preventDefault(); ${onPageChange}(${currentPage - 1})"` : ''}>
                <i class="bi bi-chevron-left"></i>
            </a>
        </li>
    `;
    
    // Номера страниц
    const startPage = Math.max(1, currentPage - 2);
    const endPage = Math.min(totalPages, currentPage + 2);
    
    for (let i = startPage; i <= endPage; i++) {
        html += `
            <li class="page-item ${i === currentPage ? 'active' : ''}">
                <a class="page-link" href="#" ${i !== currentPage ? `onclick="event.preventDefault(); ${onPageChange}(${i})"` : ''}>
                    ${i}
                </a>
            </li>
        `;
    }
    
    // Кнопка "Вперед"
    html += `
        <li class="page-item ${currentPage === totalPages ? 'disabled' : ''}">
            <a class="page-link" href="#" ${currentPage < totalPages ? `onclick="event.preventDefault(); ${onPageChange}(${currentPage + 1})"` : ''}>
                <i class="bi bi-chevron-right"></i>
            </a>
        </li>
    `;
    
    html += '</ul>';
    pagination.innerHTML = html;
    
    return pagination;
}

/**
 * Копирует текст в буфер обмена
 */
function copyToClipboard(text) {
    navigator.clipboard.writeText(text).then(() => {
        showNotification('Текст скопирован в буфер обмена', 'success', 2000);
    }).catch(err => {
        console.error('Ошибка копирования:', err);
        showNotification('Не удалось скопировать текст', 'danger');
    });
}

/**
 * Создает модальное окно подтверждения
 */
function showConfirmationModal(title, message, confirmText = 'Подтвердить', cancelText = 'Отмена') {
    return new Promise((resolve) => {
        const modalId = 'confirmationModal';
        let modal = document.getElementById(modalId);
        
        if (!modal) {
            modal = document.createElement('div');
            modal.id = modalId;
            modal.className = 'modal fade';
            modal.tabIndex = -1;
            modal.innerHTML = `
                <div class="modal-dialog">
                    <div class="modal-content bg-dark">
                        <div class="modal-header">
                            <h5 class="modal-title">${title}</h5>
                            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal"></button>
                        </div>
                        <div class="modal-body">
                            <p>${message}</p>
                        </div>
                        <div class="modal-footer">
                            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">${cancelText}</button>
                            <button type="button" class="btn btn-primary" id="confirmButton">${confirmText}</button>
                        </div>
                    </div>
                </div>
            `;
            document.body.appendChild(modal);
        }
        
        const bsModal = new bootstrap.Modal(modal);
        
        const confirmButton = modal.querySelector('#confirmButton');
        const handleConfirm = () => {
            bsModal.hide();
            resolve(true);
        };
        
        const handleCancel = () => {
            bsModal.hide();
            resolve(false);
        };
        
        confirmButton.onclick = handleConfirm;
        modal.addEventListener('hidden.bs.modal', handleCancel);
        
        bsModal.show();
    });
}

/**
 * Проверяет статус системы
 */
async function checkSystemStatus() {
    try {
        const response = await fetch('/api/status');
        const statusElement = document.getElementById('footer-status');
        const indicatorElement = document.getElementById('status-indicator');
        
        if (!statusElement || !indicatorElement) return;
        
        if (response.ok) {
            statusElement.textContent = 'Активен';
            indicatorElement.className = 'badge bg-success';
            indicatorElement.innerHTML = '<i class="bi bi-check-circle"></i> Система активна';
        } else {
            statusElement.textContent = 'Ошибка';
            indicatorElement.className = 'badge bg-danger';
            indicatorElement.innerHTML = '<i class="bi bi-exclamation-triangle"></i> Ошибка системы';
        }
    } catch (error) {
        const statusElement = document.getElementById('footer-status');
        const indicatorElement = document.getElementById('status-indicator');
        
        if (statusElement && indicatorElement) {
            statusElement.textContent = 'Нет связи';
            indicatorElement.className = 'badge bg-warning';
            indicatorElement.innerHTML = '<i class="bi bi-wifi-off"></i> Нет связи';
        }
    }
}

/**
 * Инициализация при загрузке страницы
 */
document.addEventListener('DOMContentLoaded', function() {
    // Проверка статуса системы каждые 30 секунд
    setInterval(checkSystemStatus, 30000);
    checkSystemStatus();
    
    // Инициализация tooltips
    const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
    tooltipTriggerList.map(function (tooltipTriggerEl) {
        return new bootstrap.Tooltip(tooltipTriggerEl);
    });
    
    // Инициализация popovers
    const popoverTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="popover"]'));
    popoverTriggerList.map(function (popoverTriggerEl) {
        return new bootstrap.Popover(popoverTriggerEl);
    });
    
    // Обработка форм с валидацией
    const forms = document.querySelectorAll('.needs-validation');
    Array.from(forms).forEach(form => {
        form.addEventListener('submit', event => {
            if (!form.checkValidity()) {
                event.preventDefault();
                event.stopPropagation();
            }
            form.classList.add('was-validated');
        }, false);
    });
    
    // Автоматическое скрытие уведомлений при клике
    document.addEventListener('click', function(event) {
        if (event.target.matches('.alert .btn-close')) {
            const alert = event.target.closest('.alert');
            if (alert) {
                alert.classList.remove('show');
                setTimeout(() => alert.remove(), 150);
            }
        }
    });
    
    console.log('HH Auto Apply Web Interface initialized');
});

/**
 * Глобальный объект для доступа к функциям из консоли
 */
window.HHAutoApply = {
    showNotification,
    formatDate,
    formatDuration,
    fetchData,
    postData,
    putData,
    deleteData,
    copyToClipboard,
    showConfirmationModal,
    checkSystemStatus
};