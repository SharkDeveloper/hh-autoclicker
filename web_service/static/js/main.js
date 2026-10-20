/*
 * main.js — точка входа SPA: state, роуты, навбар, футер-статус.
 */

import { router } from './router.js';
import { api } from './api.js';
import { state, safeApi } from './state.js';
import { escapeHtml } from './helpers.js';
import { renderLogin } from './pages/login.js';
import { renderDashboard } from './pages/dashboard.js';
import { renderJobDetail } from './pages/job-detail.js';
import { renderSettings } from './pages/settings.js';
import { renderStats } from './pages/stats.js';

export function renderNavbar() {
  const nav = document.getElementById('app-navbar');
  if (!nav) return;
  const brand = `<a class="navbar-brand" href="#/login"><i class="bi bi-briefcase text-primary"></i> HH AutoApply</a>`;

  if (!state.user) {
    nav.innerHTML = `<div class="container-fluid px-3">${brand}</div>`;
    return;
  }

  nav.innerHTML = `
    <div class="container-fluid px-3 d-flex justify-content-between align-items-center flex-wrap gap-2">
      ${brand.replace('href="#/login"', 'href="#/dashboard"')}
      <button class="navbar-toggler border-0" type="button" data-bs-toggle="collapse" data-bs-target="#nav-menu" aria-label="Меню">
        <span class="navbar-toggler-icon"></span>
      </button>
      <div class="collapse navbar-collapse" id="nav-menu">
        <ul class="navbar-nav ms-auto align-items-lg-center flex-lg-row gap-lg-1">
          <li class="nav-item"><a class="nav-link" data-route="#/dashboard" href="#/dashboard">Задачи</a></li>
          <li class="nav-item"><a class="nav-link" data-route="#/stats" href="#/stats">Статистика</a></li>
          <li class="nav-item"><a class="nav-link" data-route="#/settings" href="#/settings">Настройки</a></li>
          <li class="nav-item d-lg-none"><span class="nav-link text-secondary">${escapeHtml(state.user.email)}</span></li>
          <li class="nav-item ms-lg-2 d-none d-lg-flex align-items-center">
            <span class="text-secondary small me-2">${escapeHtml(state.user.email)}</span>
          </li>
          <li class="nav-item">
            <a class="btn btn-outline-secondary btn-sm ms-lg-2" href="#" id="logout-btn">
              <i class="bi bi-box-arrow-right"></i> Выход
            </a>
          </li>
        </ul>
      </div>
    </div>`;

  const hash = location.hash || '#/dashboard';
  nav.querySelectorAll('[data-route]').forEach((a) => {
    if (hash.startsWith(a.dataset.route)) a.classList.add('active-route');
    else a.classList.remove('active-route');
  });

  const logoutBtn = nav.querySelector('#logout-btn');
  if (logoutBtn) {
    logoutBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      try { await api.logout(); } catch { /* игнорируем — всё равно разлогиниваем */ }
      state.user = null;
      state.settings = null;
      router.go('#/login');
    });
  }
}

let statusTimer = null;
async function pollStatus() {
  const dot = document.getElementById('status-indicator');
  const label = document.getElementById('footer-status');
  if (!dot || !label) return;
  dot.innerHTML = '<span class="status-dot checking"></span>';
  label.textContent = 'Проверка...';
  try {
    await api.health();
    dot.innerHTML = '<span class="status-dot online"></span>';
    label.textContent = 'Система активна';
  } catch {
    dot.innerHTML = '<span class="status-dot offline"></span>';
    label.textContent = 'Нет связи';
  }
}

router.register('#/login', renderLogin);
router.register('#/dashboard', renderDashboard);
router.register('#/jobs/:id', renderJobDetail);
router.register('#/settings', renderSettings);
router.register('#/stats', renderStats);

renderNavbar();
pollStatus();
statusTimer = setInterval(pollStatus, 30000);
window.addEventListener('beforeunload', () => clearInterval(statusTimer));

router.start();

// debug-хук: доступ к api/state из консоли F12
window.HHSPA = { api, state, safeApi, router };
