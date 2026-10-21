/*
 * api.js — обёртка над fetch для всех эндпоинтов HH AutoApply.
 * Все запросы идут с credentials: 'include' (JWT в httpOnly cookie).
 */

async function request(method, url, body, isForm = false) {
  const options = {
    method,
    credentials: 'include',
    headers: {},
  };

  if (body !== undefined && body !== null) {
    if (isForm) {
      options.headers['Content-Type'] = 'application/x-www-form-urlencoded';
      options.body = new URLSearchParams(body).toString();
    } else {
      options.headers['Content-Type'] = 'application/json';
      options.body = JSON.stringify(body);
    }
  }

  let response;
  try {
    response = await fetch(url, options);
  } catch (networkError) {
    throw { status: 0, detail: 'Нет связи с сервером' };
  }

  if (response.status === 401) {
    throw { status: 401, detail: 'Требуется авторизация' };
  }

  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const data = await response.json();
      if (data && data.detail !== undefined) {
        if (typeof data.detail === 'string') {
          detail = data.detail;
        } else if (Array.isArray(data.detail)) {
          // pydantic-валидация 422
          detail = data.detail.map((d) => (d.msg ? `${d.loc ? d.loc.join('.') + ': ' : ''}${d.msg}` : JSON.stringify(d))).join('; ');
        } else {
          detail = JSON.stringify(data.detail);
        }
      }
    } catch (e) {
      /* не-JSON ответ — оставляем HTTP status */
    }
    throw { status: response.status, detail };
  }

  if (response.status === 204) return null;
  const text = await response.text();
  if (!text) return null;
  try {
    return JSON.parse(text);
  } catch (e) {
    return null;
  }
}

const GET = (url) => request('GET', url);
const POST = (url, body) => request('POST', url, body);
const POST_FORM = (url, body) => request('POST', url, body, true);
const PUT = (url, body) => request('PUT', url, body);
const DELETE = (url) => request('DELETE', url);

export const api = {
  register: (email, password) => POST('/api/auth/register', { email, password }),
  login: (email, password) => POST_FORM('/api/auth/login', { username: email, password }),
  logout: () => POST('/api/auth/logout'),
  me: () => GET('/api/auth/me'),

  getSettings: () => GET('/api/settings'),
  putSettings: (data) => PUT('/api/settings', data),

  getJobs: (page = 1, pageSize = 20) => GET(`/api/jobs?page=${page}&page_size=${pageSize}`),
  getJob: (id) => GET(`/api/jobs/${id}`),
  createJob: (data) => POST('/api/jobs', data),
  cancelJob: (id) => DELETE(`/api/jobs/${id}`),          // удалить задачу
  stopJob: (id) => POST(`/api/jobs/${id}/stop`),        // отменить pending / остановить running

  getStats: () => GET('/api/stats'),
  getHistory: (params = {}) => GET('/api/stats/history?' + new URLSearchParams(params)),

  getTimeseries: (days = 30) => GET(`/api/stats/timeseries?days=${days}`),
  getByMode: () => GET('/api/stats/by-mode'),
  getTopCompanies: (limit = 10) => GET(`/api/stats/top-companies?limit=${limit}`),
  getHeatmap: (days = 90) => GET(`/api/stats/heatmap?days=${days}`),

  health: () => GET('/api/health'),
};
