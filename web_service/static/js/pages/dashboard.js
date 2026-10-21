/*
 * pages/dashboard.js — список задач (#/dashboard): карточки, модалка создания,
 * отмена, polling запущенных задач, пагинация.
 */

import { api } from '../api.js';
import { state, safeApi } from '../state.js';
import { router } from '../router.js';
import {
  escapeHtml, truncate, shortId, fmtDate,
  modeBadge, statusBadge, skeletonCards, emptyState, renderPagination,
} from '../helpers.js';

const PAGE_SIZE = 20;

export async function renderDashboard() {
  const app = document.getElementById('app');
  app.innerHTML = `
    <div class="d-flex justify-content-between align-items-center mb-3 flex-wrap gap-2">
      <h1 class="h3 mb-0">Мои задачи</h1>
      <button class="btn btn-primary" id="btn-new-job"><i class="bi bi-plus-lg"></i> Запустить задачу</button>
    </div>
    <div id="settings-banner"></div>
    <div id="jobs-area">${skeletonCards(6)}</div>
    <div id="jobs-pagination"></div>`;

  app.querySelector('#btn-new-job').addEventListener('click', onNewJobClick);

  await reloadJobs(1);
  await loadSettingsBanner();
}

async function loadSettingsBanner() {
  const banner = document.getElementById('settings-banner');
  if (!banner) return;
  if (!state.settings) {
    state.settings = await safeApi(() => api.getSettings());
  }
  const s = state.settings;
  if (s && !s.hh_login) {
    banner.innerHTML = `
      <div class="alert alert-warning d-flex align-items-center justify-content-between flex-wrap gap-2 job-card" id="banner-settings" role="alert">
        <span><i class="bi bi-exclamation-triangle me-2"></i>Заполните настройки hh.ru — без учётных данных задачи не запускаются.</span>
        <a href="#/settings" class="btn btn-sm btn-outline-dark">Перейти в настройки</a>
      </div>`;
    banner.querySelector('#banner-settings').addEventListener('click', (e) => {
      if (e.target.closest('a')) return; // ссылку обрабатывает роутер
      router.go('#/settings');
    });
  } else {
    banner.innerHTML = '';
  }
}

async function reloadJobs(page = state.jobsPage || 1) {
  const resp = await safeApi(() => api.getJobs(page, PAGE_SIZE));
  if (!resp) return;
  state.jobs = resp.jobs || [];
  state.jobsTotal = resp.total || 0;
  state.jobsPage = resp.page || page;
  renderJobs();
  startJobsPollingIfNeeded();
}

function filtersSummary(job) {
  if (job.mode === 'manual') {
    const urls = job.filters?.vacancy_urls || [];
    return urls.length ? `URL вакансий: ${urls.length}` : 'Вручную (без URL)';
  }
  if (job.mode === 'recommendations') {
    return job.filters?.resume_id ? `Резюме: ${shortId(job.filters.resume_id)}` : 'Рекомендации';
  }
  const f = job.filters || {};
  const parts = [];
  if (f.text) parts.push(truncate(f.text, 30));
  if (f.area_name || f.area) parts.push(`регион ${f.area_name || f.area}`);
  if (f.salary) parts.push(`от ${f.salary} ₽`);
  if (f.experience) parts.push(truncate(f.experience, 20));
  return parts.length ? parts.join(', ') : 'auto';
}

function jobCard(job) {
  return `
    <div class="col-12 col-sm-6 col-lg-4">
      <div class="card job-card h-100 shadow-sm" data-id="${escapeHtml(job.id)}"
           style="background:#1e1e1e;border:1px solid #333;transition:transform .15s, box-shadow .15s;">
        <div class="card-body d-flex flex-column">
          <div class="d-flex justify-content-between align-items-start mb-2">
            ${modeBadge(job.mode)} ${statusBadge(job.status)}
          </div>
          <div class="small text-secondary mb-1"><i class="bi bi-calendar3"></i> ${fmtDate(job.created_at)}</div>
          <div class="small text-secondary mb-2"><i class="bi bi-hash"></i> ${escapeHtml(shortId(job.id))}</div>
          <div class="flex-grow-1 small">${escapeHtml(filtersSummary(job))}</div>
          <div class="d-flex gap-2 mt-3">
            <a href="#/jobs/${escapeHtml(job.id)}" class="btn btn-sm btn-outline-primary btn-details">Детали</a>
            ${job.status === 'pending'
              ? `<button class="btn btn-sm btn-outline-danger btn-cancel" data-id="${escapeHtml(job.id)}">Отменить</button>`
              : ''}
          </div>
        </div>
      </div>
    </div>`;
}

function renderJobs() {
  const area = document.getElementById('jobs-area');
  if (!area) return;
  if (!state.jobs.length) {
    area.innerHTML = emptyState('bi-inbox', 'Нет задач',
      'Запустите первую задачу, чтобы начать автоматически откликаться на вакансии.',
      '<button class="btn btn-primary mt-2" id="empty-new-job"><i class="bi bi-plus-lg"></i> Запустить</button>');
    area.querySelector('#empty-new-job')?.addEventListener('click', onNewJobClick);
  } else {
    area.innerHTML = `<div class="row g-3">${state.jobs.map(jobCard).join('')}</div>`;
    area.querySelectorAll('.job-card').forEach((card) => {
      card.addEventListener('click', (e) => {
        if (e.target.closest('a') || e.target.closest('button')) return;
        router.go('#/jobs/' + card.dataset.id);
      });
      card.addEventListener('mouseenter', () => { card.style.transform = 'translateY(-2px)'; card.classList.add('shadow'); });
      card.addEventListener('mouseleave', () => { card.style.transform = ''; card.classList.remove('shadow'); });
    });
    area.querySelectorAll('.btn-cancel').forEach((btn) => {
      btn.addEventListener('click', (e) => { e.stopPropagation(); onCancelJob(btn.dataset.id); });
    });
  }
  const pag = document.getElementById('jobs-pagination');
  if (pag) renderPagination(pag, state.jobsTotal, PAGE_SIZE, state.jobsPage, reloadJobs);
}

function startJobsPollingIfNeeded() {
  const hasRunning = state.jobs.some((j) => j.status === 'running');
  if (hasRunning && !state.pollingTimers.jobs) {
    state.pollingTimers.jobs = setInterval(async () => {
      const resp = await safeApi(() => api.getJobs(state.jobsPage, PAGE_SIZE));
      if (!resp) return;
      state.jobs = resp.jobs || [];
      state.jobsTotal = resp.total || 0;
      renderJobs();
      if (!state.jobs.some((j) => j.status === 'running')) {
        clearInterval(state.pollingTimers.jobs);
        delete state.pollingTimers.jobs;
      }
    }, 5000);
  }
}

async function onCancelJob(id) {
  const ok = await window.HHAutoApply.showConfirmationModal(
    'Отменить задачу?', 'Действие необратимо.', 'Отменить', 'Назад');
  if (!ok) return;
  try {
    await api.cancelJob(id);
    window.HHAutoApply.showNotification('Задача отменена', 'success');
    await reloadJobs();
  } catch (e) {
    window.HHAutoApply.showNotification(e.detail || 'Ошибка отмены', 'danger');
  }
}

function onNewJobClick() {
  if (!state.settings || !state.settings.hh_login) {
    window.HHAutoApply.showNotification('Сначала заполните настройки hh.ru', 'warning');
    router.go('#/settings');
    return;
  }
  openNewJobModal();
}

/* ---------- Модалка «Новая задача» ---------- */

let modalInstance = null;

function ensureModalShell() {
  if (document.getElementById('new-job-modal')) return;
  const div = document.createElement('div');
  div.innerHTML = `
    <div class="modal fade" id="new-job-modal" tabindex="-1" aria-hidden="true">
      <div class="modal-dialog modal-dialog-centered">
        <div class="modal-content" style="background:#1e1e1e;border:1px solid #444;border-radius:8px;">
          <div class="modal-header border-secondary">
            <h5 class="modal-title">Новая задача</h5>
            <button type="button" class="btn-close btn-close-white" data-bs-dismiss="modal" aria-label="Закрыть"></button>
          </div>
          <div class="modal-body" id="njm-body"></div>
          <div class="modal-footer border-secondary">
            <button type="button" class="btn btn-secondary" data-bs-dismiss="modal">Отмена</button>
            <button type="button" class="btn btn-primary" id="njm-submit">Запустить</button>
          </div>
        </div>
      </div>
    </div>`;
  document.body.appendChild(div.firstElementChild);
}

const MODE_CARDS = [
  { mode: 'auto', icon: 'bi-search', title: 'Автоматический', desc: 'Поиск вакансий по фильтрам и автоотклик' },
  { mode: 'manual', icon: 'bi-link-45deg', title: 'Вручную', desc: 'Отклик по списку URL вакансий' },
  { mode: 'recommendations', icon: 'bi-stars', title: 'Рекомендации', desc: 'Отклик по рекомендациям HH по резюме' },
];

function openNewJobModal() {
  ensureModalShell();
  const body = document.getElementById('njm-body');
  let selected = 'auto';

  body.innerHTML = `
    <div class="row g-2 mb-3" id="njm-modes">
      ${MODE_CARDS.map((m) => `
        <div class="col-12">
          <div class="mode-card card p-3 ${m.mode === selected ? 'selected' : ''}" data-mode="${m.mode}">
            <input class="form-check-input me-2 float-start" type="radio" name="njm-mode" value="${m.mode}"
                   id="mode-${m.mode}" ${m.mode === selected ? 'checked' : ''}>
            <label class="mb-0" for="mode-${m.mode}">
              <i class="bi ${m.icon} text-primary me-1"></i><strong>${m.title}</strong>
              <div class="small text-secondary">${m.desc}</div>
            </label>
          </div>
        </div>`).join('')}
    </div>
    <div id="njm-fields"></div>`;

  const renderFields = () => {
    const fields = document.getElementById('njm-fields');
    if (selected === 'auto') {
      fields.innerHTML = `
        <div class="mb-2">
          <label class="form-label">Ключевые слова</label>
          <input class="form-control" id="nj-text" placeholder="например: python developer">
        </div>
        <div class="row g-2">
          <div class="col-6">
            <label class="form-label">Регион</label>
            <select class="form-select" id="nj-area">
              <option value="">— не выбран —</option>
              <option value="1">Москва</option>
              <option value="2">Санкт-Петербург</option>
              <option value="3">Москва и область</option>
              <option value="113">Вся Россия</option>
            </select>
          </div>
          <div class="col-6">
            <label class="form-label">Зарплата от, ₽</label>
            <input type="number" class="form-control" id="nj-salary" min="0" step="1000">
          </div>
        </div>
        <div class="mt-2">
          <label class="form-label">Опыт</label>
          <select class="form-select" id="nj-exp">
            <option value="">— не выбран —</option>
            <option value="noExperience">Без опыта</option>
            <option value="between1And3">1–3 года</option>
            <option value="between3And6">3–6 лет</option>
            <option value="moreThan6">Более 6 лет</option>
          </select>
        </div>`;
    } else if (selected === 'manual') {
      fields.innerHTML = `
        <label class="form-label">URL вакансий</label>
        <textarea class="form-control" id="nj-urls" rows="6"
          placeholder="https://hh.ru/vacancy/123456782&#10;по одному на строку"></textarea>`;
    } else {
      fields.innerHTML = `
        <label class="form-label">ID резюме</label>
        <input class="form-control" id="nj-resume" value="${escapeHtml(state.settings?.resume_id || '')}"
               placeholder="d511...">
        <div class="form-text">Из URL hh.ru/resume/{id}. Пусто — основное резюме.</div>`;
    }
  };
  renderFields();

  body.querySelectorAll('.mode-card').forEach((card) => {
    card.addEventListener('click', () => {
      selected = card.dataset.mode;
      body.querySelectorAll('.mode-card').forEach((c) => c.classList.toggle('selected', c === card));
      card.querySelector('input').checked = true;
      renderFields();
    });
  });

  const modalEl = document.getElementById('new-job-modal');
  modalInstance = bootstrap.Modal.getOrCreateInstance(modalEl);
  modalInstance.show();

  const submitBtn = document.getElementById('njm-submit');
  const newSubmit = submitBtn.cloneNode(true);
  submitBtn.replaceWith(newSubmit);
  newSubmit.addEventListener('click', async () => {
    const payload = { mode: selected };
    if (selected === 'auto') {
      const filters = {};
      const text = document.getElementById('nj-text').value.trim();
      const area = document.getElementById('nj-area').value;
      const salary = document.getElementById('nj-salary').value;
      const exp = document.getElementById('nj-exp').value;
      if (text) filters.text = text;
      if (area) filters.area = area;
      if (salary) filters.salary = Number(salary);
      if (exp) filters.experience = exp;
      payload.filters = filters;
    } else if (selected === 'manual') {
      const urls = document.getElementById('nj-urls').value
        .split('\n').map((s) => s.trim()).filter(Boolean);
      if (!urls.length) {
        window.HHAutoApply.showNotification('Укажите хотя бы один URL вакансии', 'warning');
        return;
      }
      payload.vacancy_urls = urls;
    } else {
      const rid = document.getElementById('nj-resume').value.trim();
      if (rid) payload.resume_id = rid;
    }

    newSubmit.disabled = true;
    newSubmit.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Запуск...';
    try {
      await api.createJob(payload);
      modalInstance.hide();
      window.HHAutoApply.showNotification('Задача создана', 'success');
      await reloadJobs(1);
    } catch (e) {
      window.HHAutoApply.showNotification(e.detail || 'Ошибка создания задачи', 'danger');
      newSubmit.disabled = false;
      newSubmit.textContent = 'Запустить';
    }
  });
}
