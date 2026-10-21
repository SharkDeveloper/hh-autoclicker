/*
 * pages/login.js — вход и регистрация (#/login).
 */

import { api } from '../api.js';
import { state } from '../state.js';
import { router } from '../router.js';
import { escapeHtml } from '../helpers.js';

const EMAIL_RE = /^[^@\s]+@[^@\s]+\.[^@\s]+$/;

export async function renderLogin() {
  const app = document.getElementById('app');

  // если уже авторизован — редирект сразу
  try {
    const me = await api.me();
    if (me) { state.user = me; router.go('#/dashboard'); return; }
  } catch (e) {
    if (!e || e.status !== 401) {
      app.innerHTML = `<div class="alert alert-danger mt-4">${escapeHtml(e.detail || 'Сервер недоступен')}</div>`;
      return;
    }
  }

  app.innerHTML = `
    <div class="row justify-content-center">
      <div class="col-12 col-sm-10 col-md-8 col-lg-6 col-xl-4">
        <div class="card shadow" style="background:#1e1e1e;border:1px solid #333;">
          <div class="card-body p-4">
            <div class="text-center mb-3">
              <h1 class="h4 mb-1"><i class="bi bi-briefcase text-primary"></i> HH AutoApply</h1>
              <p class="text-secondary small mb-0">Автоматические отклики на вакансии</p>
            </div>
            <ul class="nav nav-tabs justify-content-center mb-3" role="tablist">
              <li class="nav-item" style="flex:1">
                <button class="nav-link w-100 active" id="tab-login" data-bs-toggle="tab" data-bs-target="#pane-login" type="button">Вход</button>
              </li>
              <li class="nav-item" style="flex:1">
                <button class="nav-link w-100" id="tab-register" data-bs-toggle="tab" data-bs-target="#pane-register" type="button">Регистрация</button>
              </li>
            </ul>
            <div class="tab-content">
              <div class="tab-pane fade show active" id="pane-login">
                <form id="form-login" novalidate>
                  <div class="mb-3">
                    <label class="form-label" for="li-email">Email</label>
                    <input type="email" class="form-control" id="li-email" autocomplete="username" required>
                    <div class="invalid-feedback" id="li-email-err">Введите корректный email</div>
                  </div>
                  <div class="mb-3">
                    <label class="form-label" for="li-pass">Пароль</label>
                    <div class="input-group">
                      <input type="password" class="form-control" id="li-pass" autocomplete="current-password" required>
                      <button class="btn btn-outline-secondary toggle-pass" type="button" data-target="li-pass" aria-label="Показать пароль"><i class="bi bi-eye"></i></button>
                    </div>
                    <div class="invalid-feedback" id="li-pass-err">Минимум 6 символов</div>
                  </div>
                  <button class="btn btn-primary w-100 py-2" type="submit" id="li-submit">Войти</button>
                  <p class="text-center text-secondary small mt-3 mb-0">Нет аккаунта?
                    <a href="#" id="goto-register" class="link-primary">Зарегистрироваться</a>
                  </p>
                </form>
              </div>
              <div class="tab-pane fade" id="pane-register">
                <form id="form-register" novalidate>
                  <div class="mb-3">
                    <label class="form-label" for="rg-email">Email</label>
                    <input type="email" class="form-control" id="rg-email" autocomplete="username" required>
                    <div class="invalid-feedback" id="rg-email-err">Введите корректный email</div>
                  </div>
                  <div class="mb-3">
                    <label class="form-label" for="rg-pass">Пароль</label>
                    <div class="input-group">
                      <input type="password" class="form-control" id="rg-pass" autocomplete="new-password" required>
                      <button class="btn btn-outline-secondary toggle-pass" type="button" data-target="rg-pass" aria-label="Показать пароль"><i class="bi bi-eye"></i></button>
                    </div>
                    <div class="form-text">Минимум 6 символов</div>
                    <div class="invalid-feedback" id="rg-pass-err">Минимум 6 символов</div>
                  </div>
                  <div class="mb-3">
                    <label class="form-label" for="rg-pass2">Повторите пароль</label>
                    <input type="password" class="form-control" id="rg-pass2" autocomplete="new-password" required>
                    <div class="invalid-feedback" id="rg-pass2-err">Пароли не совпадают</div>
                  </div>
                  <button class="btn btn-primary w-100 py-2" type="submit" id="rg-submit">Зарегистрироваться</button>
                  <p class="text-center text-secondary small mt-3 mb-0">Уже есть аккаунт?
                    <a href="#" id="goto-login" class="link-primary">Войти</a>
                  </p>
                </form>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>`;

  bindPasswordToggles(app);
  bindTabSwitch();

  app.querySelector('#form-login').addEventListener('submit', onLogin);
  app.querySelector('#form-register').addEventListener('submit', onRegister);
}

function bindTabSwitch() {
  const go = (id) => {
    const tab = document.getElementById(id);
    if (tab) bootstrap.Tab.getOrCreateInstance(tab).show();
  };
  document.getElementById('goto-register')?.addEventListener('click', (e) => { e.preventDefault(); go('tab-register'); });
  document.getElementById('goto-login')?.addEventListener('click', (e) => { e.preventDefault(); go('tab-login'); });
}

function bindPasswordToggles(root) {
  root.querySelectorAll('.toggle-pass').forEach((btn) => {
    btn.addEventListener('click', () => {
      const input = document.getElementById(btn.dataset.target);
      input.type = input.type === 'password' ? 'text' : 'password';
      btn.querySelector('i').className = input.type === 'password' ? 'bi bi-eye' : 'bi bi-eye-slash';
    });
  });
}

function setFieldError(inputId, message) {
  const input = document.getElementById(inputId);
  const err = document.getElementById(inputId + '-err');
  input.classList.add('is-invalid');
  if (err && message) err.textContent = message;
}

function clearErrors(form) {
  form.querySelectorAll('.is-invalid').forEach((el) => el.classList.remove('is-invalid'));
}

function busy(btnId, on) {
  const btn = document.getElementById(btnId);
  if (on) {
    btn.disabled = true;
    btn.dataset.orig = btn.innerHTML;
    btn.innerHTML = '<span class="spinner-border spinner-border-sm me-2"></span>Подождите...';
  } else {
    btn.disabled = false;
    btn.innerHTML = btn.dataset.orig || btn.innerHTML;
  }
}

async function onLogin(e) {
  e.preventDefault();
  const form = e.target;
  clearErrors(form);
  const email = document.getElementById('li-email').value.trim();
  const password = document.getElementById('li-pass').value;

  let ok = true;
  if (!EMAIL_RE.test(email)) { setFieldError('li-email', 'Введите корректный email'); ok = false; }
  if (password.length < 6) { setFieldError('li-pass', 'Минимум 6 символов'); ok = false; }
  if (!ok) return;

  busy('li-submit', true);
  try {
    await api.login(email, password);
    state.user = await api.me();
    window.HHAutoApply?.showNotification('Вход выполнен', 'success');
    router.go('#/dashboard');
  } catch (err) {
    window.HHAutoApply?.showNotification(err.detail || 'Ошибка входа', 'warning');
    busy('li-submit', false);
  }
}

async function onRegister(e) {
  e.preventDefault();
  const form = e.target;
  clearErrors(form);
  const email = document.getElementById('rg-email').value.trim();
  const password = document.getElementById('rg-pass').value;
  const password2 = document.getElementById('rg-pass2').value;

  let ok = true;
  if (!EMAIL_RE.test(email)) { setFieldError('rg-email', 'Введите корректный email'); ok = false; }
  if (password.length < 6) { setFieldError('rg-pass', 'Минимум 6 символов'); ok = false; }
  if (password !== password2) { setFieldError('rg-pass2', 'Пароли не совпадают'); ok = false; }
  if (!ok) return;

  busy('rg-submit', true);
  try {
    await api.register(email, password);
    await api.login(email, password);
    state.user = await api.me();
    window.HHAutoApply?.showNotification('Аккаунт создан. Добро пожаловать!', 'success');
    router.go('#/dashboard');
  } catch (err) {
    window.HHAutoApply?.showNotification(err.detail || 'Ошибка регистрации', 'warning');
    busy('rg-submit', false);
  }
}
