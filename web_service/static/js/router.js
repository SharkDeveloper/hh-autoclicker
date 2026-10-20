/*
 * router.js — собственный hash-роутер SPA.
 * Поддерживает паттерны '#/dashboard', '#/jobs/:id', auth-guard, очистку polling-таймеров.
 */

import { state, clearPollingTimers } from './state.js';
import { api } from './api.js';
import { renderNavbar } from './main.js';

const routes = [];   // { pattern, segments, handler }
let currentPattern = null;

function parseHash(hash) {
  const clean = (hash || '').replace(/^#/, '') || '/';
  return clean.split('/').filter(Boolean); // ['jobs','123']
}

export const router = {
  register(pattern, handler) {
    routes.push({
      pattern,
      segments: parseHash(pattern),
      handler,
    });
  },

  go(hash) {
    if (!hash.startsWith('#')) hash = '#' + hash;
    if (location.hash === hash) {
      // принудительный ре-рендер
      router.render();
    } else {
      location.hash = hash;
    }
  },

  current() {
    return currentPattern;
  },

  match(hash) {
    const parts = parseHash(hash);
    for (const r of routes) {
      if (r.segments.length !== parts.length) continue;
      const params = {};
      let ok = true;
      for (let i = 0; i < r.segments.length; i++) {
        const seg = r.segments[i];
        if (seg.startsWith(':')) {
          params[seg.slice(1)] = decodeURIComponent(parts[i]);
        } else if (seg !== parts[i]) {
          ok = false;
          break;
        }
      }
      if (ok) return { route: r, params };
    }
    return null;
  },

  async render() {
    const hash = location.hash || '#/dashboard';
    const matched = router.match(hash);
    const app = document.getElementById('app');

    // при смене route — убрать таймеры предыдущей страницы
    clearPollingTimers();

    if (!matched) {
      router.go('#/dashboard');
      return;
    }

    currentPattern = matched.route.pattern;

    // Auth guard: все роуты кроме #/login требуют авторизации
    const isLogin = matched.route.pattern === '#/login';
    if (!isLogin) {
      if (!state.user) {
        try {
          state.user = await api.me();
        } catch (err) {
          if (err && err.status === 401) {
            state.user = null;
            router.go('#/login');
            return;
          }
          throw err;
        }
      }
    }

    // skeleton/loading на время асинхронного рендера страницы
    if (app) {
      app.innerHTML = `
        <div class="text-center py-5">
          <div class="spinner-border text-primary" role="status">
            <span class="visually-hidden">Загрузка...</span>
          </div>
          <p class="mt-2 text-secondary">Загрузка...</p>
        </div>`;
    }

    try {
      await matched.route.handler(matched.params);
    } catch (err) {
      console.error('render error:', err);
      if (app) {
        app.innerHTML = `
          <div class="alert alert-danger mt-4">
            <i class="bi bi-x-circle"></i> Ошибка отображения страницы.
            <button class="btn btn-sm btn-outline-light ms-2" onclick="location.reload()">Перезагрузить</button>
          </div>`;
      }
    }

    // навбар обновляется после каждого рендера route
    renderNavbar();
  },

  start() {
    if (!location.hash) {
      // дефолт: dashboard, если нет хеша (guard сам редиректит на login)
      location.replace('#/dashboard');
    }
    window.addEventListener('hashchange', () => router.render());
    router.render();
  },
};
