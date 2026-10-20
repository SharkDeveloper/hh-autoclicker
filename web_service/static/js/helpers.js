/*
 * helpers.js — мелкие утилиты SPA (escapeHtml, truncate, shortId, словари бейджей).
 */

export function escapeHtml(str) {
  return String(str ?? '').replace(/[&<>"']/g, (c) => ({
    '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;',
  }[c]));
}

export function truncate(str, n = 50) {
  return str && str.length > n ? str.slice(0, n) + '…' : str || '';
}

export function shortId(uuid) {
  return uuid ? String(uuid).slice(0, 8) : '';
}

export const MODE_BADGE = {
  auto:            { cls: 'text-bg-info',      label: 'Авто' },
  manual:          { cls: 'text-bg-warning',   label: 'Вручную' },
  recommendations: { cls: 'text-bg-secondary', label: 'Рекомендации' },
};

export const STATUS_BADGE = {
  pending:   { cls: 'text-bg-secondary', label: 'Ожидает' },
  running:   { cls: 'text-bg-primary pulse-badge', label: 'Выполняется' },
  done:      { cls: 'text-bg-success',   label: 'Готово' },
  failed:    { cls: 'text-bg-danger',    label: 'Ошибка' },
  cancelled: { cls: 'text-bg-dark',      label: 'Отменена' },
};

export const APPLY_BADGE = {
  sent:    { cls: 'text-bg-success', label: 'Отправлен' },
  skipped: { cls: 'text-bg-secondary', label: 'Пропущен' },
  error:   { cls: 'text-bg-danger',  label: 'Ошибка' },
};

export function modeBadge(mode) {
  const m = MODE_BADGE[mode] || { cls: 'text-bg-secondary', label: mode };
  return `<span class="badge ${m.cls}">${escapeHtml(m.label)}</span>`;
}

export function statusBadge(status) {
  const s = STATUS_BADGE[status] || { cls: 'text-bg-secondary', label: status };
  return `<span class="badge ${s.cls}">${escapeHtml(s.label)}</span>`;
}

export function applyBadge(status) {
  const a = APPLY_BADGE[status] || { cls: 'text-bg-secondary', label: status };
  return `<span class="badge ${a.cls}">${escapeHtml(a.label)}</span>`;
}

export function fmtDate(iso) {
  if (!iso) return '—';
  try {
    return new Date(iso).toLocaleString('ru-RU', { dateStyle: 'DD.MM.YYYY', timeStyle: 'HH:mm' });
  } catch { return iso; }
}

export function skeletonCards(n = 6) {
  let html = '<div class="row g-3">';
  for (let i = 0; i < n; i++) html += '<div class="col-12 col-sm-6 col-lg-4"><div class="skeleton"></div></div>';
  return html + '</div>';
}

export function emptyState(icon, title, subtitle, ctaHtml = '') {
  return `
    <div class="text-center py-5">
      <div class="empty-state-icon"><i class="bi ${icon}"></i></div>
      <h2 class="h5 mt-3">${escapeHtml(title)}</h2>
      ${subtitle ? `<p class="text-secondary">${escapeHtml(subtitle)}</p>` : ''}
      ${ctaHtml}
    </div>`;
}

/* Пагинация: containerEl — элемент, куда рендерить; onPage(page) — колбэк. */
export function renderPagination(container, total, pageSize, page, onPage) {
  const pages = Math.max(1, Math.ceil(total / pageSize));
  if (pages <= 1) { container.innerHTML = ''; return; }
  const btn = (p, label, disabled, active) =>
    `<li class="page-item ${disabled ? 'disabled' : ''} ${active ? 'active' : ''}">
       <a class="page-link" href="#" data-page="${p}">${label}</a>
     </li>`;
  let items = btn(Math.max(1, page - 1), '«', page <= 1, false);
  const from = Math.max(1, page - 2), to = Math.min(pages, page + 2);
  for (let p = from; p <= to; p++) items += btn(p, String(p), false, p === page);
  items += btn(Math.min(pages, page + 1), '»', page >= pages, false);
  container.innerHTML = `
    <nav class="d-flex justify-content-center mt-4">
      <ul class="pagination pagination-sm mb-0">${items}</ul>
    </nav>`;
  container.querySelectorAll('a.page-link').forEach((a) => {
    a.addEventListener('click', (e) => {
      e.preventDefault();
      const li = a.closest('li');
      if (li.classList.contains('disabled') || li.classList.contains('active')) return;
      onPage(Number(a.dataset.page));
    });
  });
}
