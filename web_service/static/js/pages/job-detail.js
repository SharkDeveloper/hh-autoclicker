/*
 * pages/job-detail.js — детали задачи (#/jobs/{id}): инфо, фильтры, отклики,
 * polling, отмена.
 */

import { api } from '../api.js';
import { state, safeApi } from '../state.js';
import { router } from '../router.js';
import { escapeHtml, shortId, fmtDate, modeBadge, statusBadge, applyBadge, renderPagination } from '../helpers.js';

const PAGE_SIZE = 20;
let jobId = null;
let appliesPage = 1;

export async function renderJobDetail(params) {
  jobId = params.id;
  appliesPage = 1;
  const app = document.getElementById('app');
  app.innerHTML = `
    <a href="#/dashboard" class="btn btn-link px-0 mb-2"><i class="bi bi-arrow-left"></i> К задачам</a>
    <div id="jd-content">
      <div class="text-center py-5">
        <div class="spinner-border text-primary"></div>
        <p class="mt-2 text-secondary">Загрузка...</p>
      </div>
    </div>`;
  await loadAndRender();
}

async function loadApplies() {
  return safeApi(() => api.getHistory({ job_id: jobId, limit: PAGE_SIZE, offset: (appliesPage - 1) * PAGE_SIZE }));
}

async function loadAndRender() {
  const [job, history] = await Promise.all([
    safeApi(() => api.getJob(jobId)),
    loadApplies(),
  ]);
  if (!job) {
    document.getElementById('jd-content').innerHTML =
      '<div class="alert alert-danger">Задача не найдена.</div>';
    return;
  }
  state.currentJob = job;
  state.applies = history?.applies || [];
  state.appliesTotal = history?.total || 0;
  paint();
  startPollingIfNeeded(job);
}

function progressPercent(job) {
  const done = state.appliesTotal;
  const total = (state.settings?.rate_limit) || job.filters?.rate_limit || 20;
  return Math.min(100, Math.round((done / total) * 100));
}

function filtersRows(filters) {
  const labels = {
    text: 'Ключевые слова', area: 'Регион', area_name: 'Регион',
    salary: 'Зарплата от', experience: 'Опыт', vacancy_urls: 'URL вакансий',
    resume_id: 'ID резюме',
  };
  return Object.entries(filters || {})
    .map(([k, v]) => `
      <tr>
        <td class="text-secondary">${escapeHtml(labels[k] || k)}</td>
        <td>${Array.isArray(v) ? v.map((u) => `<div><a href="${escapeHtml(u)}" target="_blank" rel="noopener">${escapeHtml(u)}</a></div>`).join('') : escapeHtml(String(v))}</td>
      </tr>`).join('');
}

function applyRow(a) {
  return `
    <tr>
      <td><a href="${escapeHtml(a.vacancy_url)}" target="_blank" rel="noopener">${escapeHtml(a.vacancy_title || a.vacancy_id)}</a></td>
      <td>${escapeHtml(a.company || '—')}</td>
      <td>${applyBadge(a.status)}</td>
      <td class="small text-danger">${escapeHtml(a.error_msg || '')}</td>
      <td class="small text-secondary">${fmtDate(a.applied_at)}</td>
    </tr>`;
}

function paint() {
  const job = state.currentJob;
  const content = document.getElementById('jd-content');
  if (!job || !content) return;

  const isRunning = job.status === 'running';
  content.innerHTML = `
    <div class="card mb-3" style="background:#1e1e1e;border:1px solid #333;">
      <div class="card-body">
        <div class="row g-3">
          <div class="col-12 col-md-6">
            <h2 class="h5 mb-2">Задача ${escapeHtml(shortId(job.id))}</h2>
            <div class="mb-2">${modeBadge(job.mode)} ${statusBadge(job.status)}</div>
            <table class="table table-sm table-borderless mb-0 small">
              <tr><td class="text-secondary">Создана</td><td>${fmtDate(job.created_at)}</td></tr>
              <tr><td class="text-secondary">Начата</td><td>${fmtDate(job.started_at)}</td></tr>
              <tr><td class="text-secondary">Завершена</td><td>${fmtDate(job.finished_at)}</td></tr>
              <tr><td class="text-secondary">ID</td><td><code>${escapeHtml(job.id)}</code></td></tr>
            </table>
            ${job.status === 'pending'
              ? `<button class="btn btn-danger btn-sm mt-2" id="jd-cancel">Отменить задачу</button>` : ''}
          </div>
          <div class="col-12 col-md-6">
            ${isRunning ? `
              <div class="mb-2 text-secondary small">Прогресс</div>
              <div class="progress" style="height:12px;">
                <div class="progress-bar progress-bar-animated bg-primary" style="width:${progressPercent(job)}%"></div>
              </div>
              <div class="small text-secondary mt-1">Откликов: ${state.appliesTotal}</div>` : `
              <div class="display-6 fw-bold text-center my-4">${state.appliesTotal}</div>
              <div class="text-center text-secondary">откликов</div>`}
          </div>
        </div>
      </div>
    </div>

    ${job.mode === 'auto' || (job.filters && Object.keys(job.filters).length) ? `
      <div class="card mb-3" style="background:#1e1e1e;border:1px solid #333;">
        <div class="card-header border-secondary">Фильтры</div>
        <div class="card-body p-0">
          <table class="table table-sm mb-0"><tbody>${filtersRows(job.filters)}</tbody></table>
        </div>
      </div>` : ''}

    <div class="card" style="background:#1e1e1e;border:1px solid #333;">
      <div class="card-header border-secondary">Отклики</div>
      <div class="card-body">
        <div id="jd-applies"></div>
        <div id="jd-pagination"></div>
      </div>
    </div>`;

  content.querySelector('#jd-cancel')?.addEventListener('click', onCancel);
  paintApplies();
}

function paintApplies() {
  const el = document.getElementById('jd-applies');
  if (!el) return;
  const job = state.currentJob;
  if (!state.applies.length) {
    if (job && job.status === 'running') {
      el.innerHTML = `
        <div class="text-center py-4">
          <div class="spinner-border text-primary"></div>
          <p class="mt-2 text-secondary">Задача выполняется, отклики появятся по мере отправки...</p>
        </div>`;
    } else {
      el.innerHTML = '<p class="text-secondary text-center py-4 mb-0">Откликов пока нет</p>';
    }
  } else {
    el.innerHTML = `
      <div class="table-responsive table-scroll-x">
        <table class="table table-dark table-hover align-middle mb-0">
          <thead><tr>
            <th>Вакансия</th><th>Компания</th><th>Статус</th><th>Ошибка</th><th>Время</th>
          </tr></thead>
          <tbody>${state.applies.map(applyRow).join('')}</tbody>
        </table>
      </div>`;
  }
  const pag = document.getElementById('jd-pagination');
  if (pag) renderPagination(pag, state.appliesTotal, PAGE_SIZE, appliesPage, async (p) => {
    appliesPage = p;
    const history = await loadApplies();
    if (history) {
      state.applies = history.applies || [];
      state.appliesTotal = history.total || 0;
      paintApplies();
    }
  });
}

function startPollingIfNeeded(job) {
  if (job.status !== 'running' || state.pollingTimers.job) return;
  state.pollingTimers.job = setInterval(async () => {
    const [freshJob, history] = await Promise.all([
      safeApi(() => api.getJob(jobId)),
      loadApplies(),
    ]);
    if (!freshJob) return;
    state.currentJob = freshJob;
    if (history) {
      state.applies = history.applies || [];
      state.appliesTotal = history.total || 0;
    }
    paint();
    if (freshJob.status !== 'running') {
      clearInterval(state.pollingTimers.job);
      delete state.pollingTimers.job;
      window.HHAutoApply.showNotification(
        `Задача ${freshJob.status === 'done' ? 'выполнена' : freshJob.status === 'failed' ? 'завершилась с ошибкой' : 'остановлена'}`,
        freshJob.status === 'done' ? 'success' : 'warning');
    }
  }, 3000);
}

async function onCancel() {
  const ok = await window.HHAutoApply.showConfirmationModal(
    'Отменить задачу?', 'Действие необратимо.', 'Отменить', 'Назад');
  if (!ok) return;
  try {
    await api.cancelJob(jobId);
    window.HHAutoApply.showNotification('Задача отменена', 'success');
    await loadAndRender();
  } catch (e) {
    window.HHAutoApply.showNotification(e.detail || 'Ошибка отмены', 'danger');
  }
}
