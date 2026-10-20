/*
 * pages/stats.js — статистика (#/stats): сводка, графики Chart.js, heatmap,
 * история откликов с фильтрами и пагинацией.
 */

import { api } from '../api.js';
import { state, safeApi } from '../state.js';
import { escapeHtml, fmtDate, applyBadge, renderPagination, emptyState } from '../helpers.js';

const PAGE_SIZE = 20;
let days = 30;
let historyPage = 1;
let statusFilter = '';
let charts = {};

if (window.Chart) {
  Chart.defaults.color = '#e0e0e0';
  Chart.defaults.borderColor = '#333';
  Chart.defaults.plugins.legend.position = 'bottom';
}

export async function renderStats() {
  const app = document.getElementById('app');
  app.innerHTML = `
    <div class="d-flex justify-content-between align-items-center mb-1 flex-wrap gap-2">
      <h1 class="h3 mb-0">Статистика</h1>
      <div class="btn-group" role="group" id="period-group">
        ${[7, 14, 30, 90].map((d) => `
          <button type="button" class="btn btn-sm ${d === days ? 'btn-primary' : 'btn-outline-secondary'}" data-days="${d}">${d}д</button>`).join('')}
      </div>
    </div>
    <p class="text-secondary small mb-3" id="period-label">Данные за последние ${days} дней</p>
    <div id="stats-body">
      <div class="row g-3 mb-4">${'<div class="col-6 col-md-4 col-xl-2"><div class="skeleton" style="min-height:100px"></div></div>'.repeat(6)}</div>
      <div class="text-center py-5"><div class="spinner-border text-primary"></div></div>
    </div>`;

  document.getElementById('period-group').addEventListener('click', (e) => {
    const btn = e.target.closest('[data-days]');
    if (!btn) return;
    days = Number(btn.dataset.days);
    document.querySelectorAll('#period-group .btn').forEach((b) => {
      b.classList.toggle('btn-primary', Number(b.dataset.days) === days);
      b.classList.toggle('btn-outline-secondary', Number(b.dataset.days) !== days);
    });
    document.getElementById('period-label').textContent = 'Данные за последние ' + days + ' дней';
    loadStats();
  });

  await loadStats();
}

async function loadStats() {
  destroyCharts();
  const [stats, history, timeseries, byMode, topCompanies, heatmap] = await Promise.all([
    safeApi(() => api.getStats()).catch(() => undefined),
    safeApi(() => api.getHistory({ limit: PAGE_SIZE, offset: 0 })).catch(() => undefined),
    safeApi(() => api.getTimeseries(days)).catch(() => undefined),
    safeApi(() => api.getByMode()).catch(() => undefined),
    safeApi(() => api.getTopCompanies(10)).catch(() => undefined),
    safeApi(() => api.getHeatmap(90)).catch(() => undefined),
  ]);
  if (stats) state.stats = stats;
  if (history) state.statsHistory = history;
  if (timeseries) state.timeseries = timeseries;
  if (byMode) state.byMode = byMode;
  if (topCompanies) state.topCompanies = topCompanies;
  if (heatmap) state.heatmap = heatmap;
  paint();
}

function destroyCharts() {
  Object.values(charts).forEach((c) => { try { c.destroy(); } catch (e) {} });
  charts = {};
}

function statCard(icon, value, label, pulse) {
  return `
    <div class="col-6 col-md-4 col-xl-2">
      <div class="card h-100 text-center" style="background:#1e1e1e;border:1px solid #333;">
        <div class="card-body py-3">
          <div class="mb-1"><i class="bi ${icon} fs-4 ${pulse ? 'pulse-badge text-danger' : 'text-primary'}"></i></div>
          <div class="stat-value">${value ?? 0}</div>
          <div class="stat-label">${label}</div>
        </div>
      </div>
    </div>`;
}

function chartCard(title, bodyId) {
  return `
    <div class="col-12 col-xl-6">
      <div class="card h-100" style="background:#1e1e1e;border:1px solid #333;">
        <div class="card-header border-secondary">${title}</div>
        <div class="card-body">
          <div class="chart-box" id="${bodyId}-box"><canvas id="${bodyId}"></canvas></div>
          <div id="${bodyId}-empty" class="text-center text-secondary py-5 d-none">
            <i class="bi bi-bar-chart fs-1 d-block mb-2"></i>Нет данных
          </div>
        </div>
      </div>
    </div>`;
}

function paint() {
  const el = document.getElementById('stats-body');
  if (!el) return;
  const s = state.stats || {};
  const noData = !s.total_applies;

  el.innerHTML = `
    ${noData ? `
      <div class="alert alert-info d-flex justify-content-between align-items-center flex-wrap gap-2">
        <span><i class="bi bi-info-circle me-2"></i>Статистики пока нет — выполните первую задачу.</span>
        <a href="#/dashboard" class="btn btn-sm btn-primary">Запустить</a>
      </div>` : ''}

    <div class="row g-3 mb-4">
      ${statCard('bi-send', s.total_applies, 'Всего откликов')}
      ${statCard('bi-calendar-check', s.today_applies, 'Сегодня')}
      ${statCard('bi-check-circle', s.sent_count, 'Отправлено')}
      ${statCard('bi-dash-circle', s.skipped_count, 'Пропущено')}
      ${statCard('bi-x-circle', s.error_count, 'Ошибок')}
      ${statCard('bi-activity', s.active_jobs, 'Активных задач', s.active_jobs > 0)}
    </div>

    <div class="row g-3 mb-4">
      ${chartCard('Отклики по дням', 'ch-timeseries')}
      ${chartCard('Распределение по статусам', 'ch-donut')}
    </div>
    <div class="row g-3 mb-4">
      ${chartCard('По режимам', 'ch-bymode')}
      ${chartCard('Топ компаний', 'ch-topcomp')}
    </div>

    <div class="card mb-4" style="background:#1e1e1e;border:1px solid #333;">
      <div class="card-header border-secondary">Активность по дням/часам (90 дней)</div>
      <div class="card-body table-scroll-x" id="heatmap-wrap"></div>
    </div>

    <div class="card" style="background:#1e1e1e;border:1px solid #333;">
      <div class="card-header border-secondary">История откликов</div>
      <div class="card-body">
        <form class="row g-2 mb-3" id="hist-filters">
          <div class="col-6 col-md-3"><input type="date" class="form-control form-control-sm" id="hf-from" title="От"></div>
          <div class="col-6 col-md-3"><input type="date" class="form-control form-control-sm" id="hf-to" title="До"></div>
          <div class="col-6 col-md-3">
            <select class="form-select form-select-sm" id="hf-status">
              <option value="">Все статусы</option>
              <option value="sent">Отправлен</option>
              <option value="skipped">Пропущен</option>
              <option value="error">Ошибка</option>
            </select>
          </div>
          <div class="col-6 col-md-3">
            <button class="btn btn-sm btn-outline-primary w-100" type="submit">Применить</button>
          </div>
        </form>
        <div id="hist-table"></div>
        <div id="hist-pagination"></div>
      </div>
    </div>`;

  document.getElementById('hist-filters').addEventListener('submit', (e) => {
    e.preventDefault();
    historyPage = 1;
    statusFilter = document.getElementById('hf-status').value;
    loadHistoryTable();
  });

  drawCharts();
  drawHeatmap();
  paintHistoryTable(state.statsHistory);
}

function showChartEmpty(id, isEmpty) {
  const box = document.getElementById(id + '-box');
  const empty = document.getElementById(id + '-empty');
  if (!box || !empty) return;
  box.classList.toggle('d-none', isEmpty);
  empty.classList.toggle('d-none', !isEmpty);
}

function drawCharts() {
  if (!window.Chart) return;

  // Line: отклики по дням
  const ts = state.timeseries || [];
  const hasTs = ts.some((d) => (d.sent + d.skipped + d.error) > 0);
  showChartEmpty('ch-timeseries', !hasTs);
  if (hasTs) {
    charts.ts = new Chart(document.getElementById('ch-timeseries'), {
      type: 'line',
      data: {
        labels: ts.map((d) => d.date.slice(5).split('-').reverse().join('.')),
        datasets: [
          { label: 'Отправлено', data: ts.map((d) => d.sent), borderColor: '#198754', backgroundColor: 'rgba(25,135,84,.15)', tension: 0.3 },
          { label: 'Пропущено', data: ts.map((d) => d.skipped), borderColor: '#888888', borderDash: [5, 5], tension: 0.3 },
          { label: 'Ошибки', data: ts.map((d) => d.error), borderColor: '#dc3545', tension: 0.3 },
        ],
      },
      options: { responsive: true, maintainAspectRatio: false, interaction: { mode: 'index', intersect: false } },
    });
  }

  // Doughnut: статусы (клик по сегменту фильтрует историю)
  const s = state.stats || {};
  const donutVals = [s.sent_count || 0, s.skipped_count || 0, s.error_count || 0];
  const donutTotal = donutVals.reduce((a, b) => a + b, 0);
  showChartEmpty('ch-donut', donutTotal === 0);
  if (donutTotal > 0) {
    const centerText = {
      id: 'centerText',
      afterDraw(chart) {
        const area = chart.chartArea;
        const ctx = chart.ctx;
        const x = (area.left + area.right) / 2, y = (area.top + area.bottom) / 2;
        ctx.save();
        ctx.textAlign = 'center';
        ctx.fillStyle = '#e0e0e0';
        ctx.font = '700 24px Segoe UI, sans-serif';
        ctx.fillText(String(donutTotal), x, y);
        ctx.font = '12px Segoe UI, sans-serif';
        ctx.fillStyle = '#888888';
        ctx.fillText('всего', x, y + 18);
        ctx.restore();
      },
    };
    charts.donut = new Chart(document.getElementById('ch-donut'), {
      type: 'doughnut',
      data: {
        labels: ['Отправлено', 'Пропущено', 'Ошибки'],
        datasets: [{ data: donutVals, backgroundColor: ['#198754', '#888888', '#dc3545'], borderColor: '#1e1e1e', borderWidth: 2 }],
      },
      options: {
        responsive: true, maintainAspectRatio: false, cutout: '65%',
        plugins: {
          legend: {
            position: 'bottom',
            labels: {
              generateLabels(chart) {
                const total = chart.data.datasets[0].data.reduce((a, b) => a + b, 0) || 1;
                return chart.data.labels.map((label, i) => {
                  const v = chart.data.datasets[0].data[i];
                  return {
                    text: label + ': ' + v + ' (' + Math.round(v / total * 100) + '%)',
                    fillStyle: chart.data.datasets[0].backgroundColor[i],
                    index: i, hidden: false,
                  };
                });
              },
            },
          },
        },
        onClick(evt, elements) {
          if (!elements.length) return;
          const names = ['sent', 'skipped', 'error'];
          statusFilter = names[elements[0].index];
          const sel = document.getElementById('hf-status');
          if (sel) sel.value = statusFilter;
          historyPage = 1;
          loadHistoryTable();
        },
      },
      plugins: [centerText],
    });
  }

  // Bar horizontal: по режимам
  const bm = state.byMode || [];
  const hasBm = bm.some((x) => x.count > 0);
  showChartEmpty('ch-bymode', !hasBm);
  if (hasBm) {
    const colors = { auto: '#0d6efd', manual: '#ffc107', recommendations: '#0dcaf0' };
    charts.bymode = new Chart(document.getElementById('ch-bymode'), {
      type: 'bar',
      data: {
        labels: bm.map((x) => x.mode),
        datasets: [{ data: bm.map((x) => x.count), backgroundColor: bm.map((x) => colors[x.mode] || '#888888') }],
      },
      options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } },
    });
  }

  // Bar horizontal: топ компаний
  const tc = state.topCompanies || [];
  const hasTc = tc.some((x) => x.count > 0);
  showChartEmpty('ch-topcomp', !hasTc);
  if (hasTc) {
    charts.tc = new Chart(document.getElementById('ch-topcomp'), {
      type: 'bar',
      data: {
        labels: tc.map((x) => x.company),
        datasets: [{ data: tc.map((x) => x.count), backgroundColor: tc.map((_, i) => {
          const t = i / Math.max(1, tc.length - 1);
          const mix = (a, b) => Math.round(a + (b - a) * t);
          return 'rgb(' + mix(13, 13) + ',' + mix(110, 202) + ',' + mix(253, 240) + ')';
        }) }],
      },
      options: { indexAxis: 'y', responsive: true, maintainAspectRatio: false, plugins: { legend: { display: false } } },
    });
  }
}

/* ---------- Heatmap: дни недели × часы ---------- */

const WEEKDAYS = ['Пн', 'Вт', 'Ср', 'Чт', 'Пт', 'Сб', 'Вс'];
const FULL_DAYS = ['Понедельник', 'Вторник', 'Среда', 'Четверг', 'Пятница', 'Суббота', 'Воскресенье'];

function heatColor(count, max) {
  if (!count) return '#2d2d2d';
  const t = Math.min(1, count / (max || 1));
  const mix = (a, b) => Math.round(a + (b - a) * t);
  return 'rgb(' + mix(13, 10) + ',' + mix(110, 88) + ',' + mix(253, 202) + ')';
}

function drawHeatmap() {
  const wrap = document.getElementById('heatmap-wrap');
  if (!wrap) return;
  const hm = state.heatmap || [];
  const max = Math.max.apply(null, hm.map((c) => c.count).concat([0]));
  if (!hm.some((c) => c.count > 0)) {
    wrap.innerHTML = '<p class="text-secondary text-center mb-0">Нет данных об активности</p>';
    return;
  }
  const grid = {};
  hm.forEach((c) => { grid[c.weekday + '-' + c.hour] = c.count; });
  let html = '<table class="mb-0" style="border-collapse:separate;"><tbody>';
  for (let wd = 0; wd < 7; wd++) {
    html += '<tr><td class="text-secondary small pe-2" style="white-space:nowrap">' + WEEKDAYS[wd] + '</td>';
    for (let h = 0; h < 24; h++) {
      const v = grid[wd + '-' + h] || 0;
      html += '<td><span class="heatmap-cell" title="' + FULL_DAYS[wd] + ', '
        + String(h).padStart(2, '0') + ':00 — ' + v + ' откликов" style="background:'
        + heatColor(v, max) + '"></span></td>';
    }
    html += '</tr>';
  }
  html += '<tr><td></td>';
  for (let h = 0; h < 24; h++) {
    html += '<td class="text-secondary text-center" style="font-size:10px">' + (h % 3 === 0 ? h : '') + '</td>';
  }
  html += '</tr></tbody></table>';
  html += '<div class="d-flex align-items-center gap-2 mt-2 small text-secondary">'
    + '<span>меньше</span>'
    + '<span class="heatmap-cell" style="background:#2d2d2d"></span>'
    + '<span class="heatmap-cell" style="background:' + heatColor(Math.ceil(max / 3), max) + '"></span>'
    + '<span class="heatmap-cell" style="background:' + heatColor(Math.ceil(max * 2 / 3), max) + '"></span>'
    + '<span class="heatmap-cell" style="background:' + heatColor(max, max) + '"></span>'
    + '<span>больше (' + max + ')</span></div>';
  wrap.innerHTML = html;
}

/* ---------- Таблица истории ---------- */

function buildHistoryParams() {
  const params = { limit: PAGE_SIZE, offset: (historyPage - 1) * PAGE_SIZE };
  const from = document.getElementById('hf-from');
  const to = document.getElementById('hf-to');
  if (from && from.value) params.start_date = from.value + 'T00:00:00';
  if (to && to.value) params.end_date = to.value + 'T23:59:59';
  if (statusFilter) params.status = statusFilter;
  return params;
}

async function loadHistoryTable() {
  const history = await safeApi(() => api.getHistory(buildHistoryParams()));
  if (history) {
    state.statsHistory = history;
    paintHistoryTable(history);
  }
}

function paintHistoryTable(history) {
  const el = document.getElementById('hist-table');
  if (!el) return;
  const applies = (history && history.applies) || [];
  const total = (history && history.total) || 0;
  if (!applies.length) {
    el.innerHTML = emptyState('bi-inbox', 'Откликов нет', 'Здесь появятся отклики после выполнения задач.');
  } else {
    el.innerHTML = `
      <div class="table-responsive table-scroll-x">
        <table class="table table-dark table-hover align-middle mb-0">
          <thead><tr><th>Вакансия</th><th>Компания</th><th>Статус</th><th>Ошибка</th><th>Время</th></tr></thead>
          <tbody>${applies.map((a) => `
            <tr>
              <td><a href="${escapeHtml(a.vacancy_url)}" target="_blank" rel="noopener">${escapeHtml(a.vacancy_title || a.vacancy_id)}</a></td>
              <td>${escapeHtml(a.company || '—')}</td>
              <td>${applyBadge(a.status)}</td>
              <td class="small text-danger">${escapeHtml(a.error_msg || '')}</td>
              <td class="small text-secondary">${fmtDate(a.applied_at)}</td>
            </tr>`).join('')}</tbody>
        </table>
      </div>`;
  }
  const pag = document.getElementById('hist-pagination');
  if (pag) renderPagination(pag, total, PAGE_SIZE, historyPage, (p) => { historyPage = p; loadHistoryTable(); });
}
