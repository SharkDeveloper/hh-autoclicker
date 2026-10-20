/*
 * pages/settings.js — настройки (#/settings): аккаунт hh.ru, параметры откликов.
 */

import { api } from '../api.js';
import { state, safeApi } from '../state.js';
import { escapeHtml, fmtDate } from '../helpers.js';

export async function renderSettings() {
  const app = document.getElementById('app');
  app.innerHTML = `
    <h1 class="h3 mb-3">Настройки</h1>
    <div class="text-center py-5">
      <div class="spinner-border text-primary"></div>
      <p class="mt-2 text-secondary">Загрузка...</p>
    </div>`;

  const [user, settings] = await Promise.all([
    safeApi(() => api.me()),
    safeApi(() => api.getSettings()),
  ]);
  if (user) state.user = user;
  if (settings) state.settings = settings;
  paint();
}

function paint() {
  const app = document.getElementById('app');
  const s = state.settings || {};
  const u = state.user || {};
  app.innerHTML = `
    <div class="row justify-content-center"><div class="col-12 col-lg-9 col-xl-8">
      <h1 class="h3 mb-3">Настройки</h1>

      <form id="settings-form" novalidate>
        <div class="card mb-3" style="background:#1e1e1e;border:1px solid #333;">
          <div class="card-header border-secondary d-flex justify-content-between align-items-center">
            <div>
              <strong>Аккаунт hh.ru</strong>
              <div class="small text-secondary">Данные для входа. Хранятся в зашифрованном виде</div>
            </div>
          </div>
          <div class="card-body">
            <div class="mb-3">
              <label class="form-label" for="st-login">Email hh.ru</label>
              <div class="input-group">
                <span class="input-group-text"><i class="bi bi-envelope"></i></span>
                <input type="email" class="form-control" id="st-login" name="hh_login"
                       value="${escapeHtml(s.hh_login || '')}" placeholder="you@example.com">
              </div>
            </div>
            <div class="mb-3">
              <label class="form-label" for="st-pass">Пароль hh.ru</label>
              <div class="input-group">
                <input type="password" class="form-control" id="st-pass" name="hh_password"
                       autocomplete="new-password" placeholder="Оставьте пустым, чтобы не менять">
                <button class="btn btn-outline-secondary toggle-pass" type="button" data-target="st-pass"
                        aria-label="Показать пароль"><i class="bi bi-eye"></i></button>
              </div>
              <div class="form-text">Пароль шифруется и никогда не возвращается в браузер</div>
            </div>
            <div class="mb-0">
              <label class="form-label" for="st-resume">ID резюме</label>
              <input type="text" class="form-control" id="st-resume" name="resume_id"
                     value="${escapeHtml(s.resume_id || '')}" placeholder="d511...">
              <div class="form-text">Из URL hh.ru/resume/{id}</div>
            </div>
          </div>
        </div>

        <div class="card mb-3" style="background:#1e1e1e;border:1px solid #333;">
          <div class="card-header border-secondary">
            <strong>Параметры откликов</strong>
          </div>
          <div class="card-body">
            <div class="mb-3">
              <label class="form-label" for="st-letter">Сопроводительное письмо</label>
              <textarea class="form-control" id="st-letter" name="cover_letter" rows="6">${escapeHtml(s.cover_letter || '')}</textarea>
              <div class="form-text"><span id="letter-count">0</span> символов</div>
            </div>
            <div class="row g-3">
              <div class="col-6 col-md-4">
                <label class="form-label" for="st-rate">Лимит откликов</label>
                <input type="number" class="form-control" id="st-rate" name="rate_limit"
                       min="1" max="100" value="${s.rate_limit ?? 20}">
              </div>
              <div class="col-3 col-md-4">
                <label class="form-label" for="st-dmin">Задержка от, с</label>
                <input type="number" class="form-control" id="st-dmin" name="delay_min"
                       min="1" max="10" value="${s.delay_min ?? 1}">
              </div>
              <div class="col-3 col-md-4">
                <label class="form-label" for="st-dmax">до, с</label>
                <input type="number" class="form-control" id="st-dmax" name="delay_max"
                       min="1" max="30" value="${s.delay_max ?? 3}">
              </div>
            </div>
            <div class="form-check form-switch mt-3">
              <input class="form-check-input" type="checkbox" id="st-headless" name="headless"
                     ${s.headless ? 'checked' : ''}>
              <label class="form-check-label" for="st-headless">Headless-режим браузера worker</label>
            </div>
          </div>
        </div>

        <div class="card mb-3" style="background:#1e1e1e;border:1px solid #333;">
          <div class="card-header border-secondary"><strong>Информация</strong></div>
          <div class="card-body">
            <table class="table table-sm table-borderless mb-0">
              <tr><td class="text-secondary" style="width:180px">Email</td><td>${escapeHtml(u.email || '—')}</td></tr>
              <tr><td class="text-secondary">Дата регистрации</td><td>${fmtDate(u.created_at)}</td></tr>
            </table>
          </div>
        </div>

        <div class="d-grid d-md-flex justify-content-md-end">
          <button type="submit" class="btn btn-primary px-4" id="st-save">Сохранить настройки</button>
        </div>
      </form>
    </div></div>`;

  // счётчик символов
  const letter = document.getElementById('st-letter');
  const counter = document.getElementById('letter-count');
  const updateCount = () => { counter.textContent = String(letter.value.length); };
  letter.addEventListener('input', updateCount);
  updateCount();

  // toggle пароля
  document.querySelectorAll('.toggle-pass').forEach((btn) => {
    btn.addEventListener('click', () => {
      const input = document.getElementById(btn.dataset.target);
      input.type = input.type === 'password' ? 'text' : 'password';
      btn.querySelector('i').className = input.type === 'password' ? 'bi bi-eye' : 'bi bi-eye-slash';
    });
  });

  document.getElementById('settings-form').addEventListener('submit', onSubmit);
}

async function onSubmit(e) {
  e.preventDefault();
  const val = (id) => document.getElementById(id).value;

  const payload = {
    hh_login: val('st-login').trim(),
    resume_id: val('st-resume').trim(),
    cover_letter: val('st-letter'),
    delay_min: Number(val('st-dmin')),
    delay_max: Number(val('st-dmax')),
    rate_limit: Number(val('st-rate')),
    headless: document.getElementById('st-headless').checked,
  };
  const pass = val('st-pass');
  if (pass) payload.hh_password = pass;

  if (payload.delay_min > payload.delay_max) {
    window.HHAutoApply.showNotification('Задержка «от» не может быть больше «до»', 'warning');
    return;
  }
  if (payload.rate_limit < 1 || payload.rate_limit > 100) {
    window.HHAutoApply.showNotification('Лимит откликов: 1–100', 'warning');
    return;
  }

  const btn = document.getElementById('st-save');
  btn.disabled = true;
  btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Сохранение...';
  try {
    state.settings = await api.putSettings(payload);
    window.HHAutoApply.showNotification('Настройки сохранены', 'success');
    document.getElementById('st-pass').value = '';
  } catch (err) {
    window.HHAutoApply.showNotification(err.detail || 'Ошибка сохранения', 'danger');
  } finally {
    btn.disabled = false;
    btn.textContent = 'Сохранить настройки';
  }
}
