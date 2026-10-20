/*
 * state.js — глобальное состояние SPA + safeApi (отдельно от main.js,
 * чтобы избежать циклических импортов страницы ↔ точка входа).
 */

export const state = {
  user: null,              // UserResponse | null
  settings: null,          // SettingsResponse | null
  jobs: [],                // JobResponse[]
  jobsPage: 1,
  jobsTotal: 0,
  stats: null,             // StatsSummary | null
  currentJob: null,        // JobResponse | null
  applies: [],             // ApplyResponse[]
  appliesTotal: 0,
  statsHistory: null,      // { applies, total }
  timeseries: null,
  byMode: null,
  topCompanies: null,
  heatmap: null,
  pollingTimers: {},       // name → intervalId
};

import { router } from './router.js';

export function clearPollingTimers() {
  Object.values(state.pollingTimers).forEach((id) => clearInterval(id));
  state.pollingTimers = {};
}

export async function safeApi(fn) {
  try {
    return await fn();
  } catch (err) {
    if (err && err.status === 401) {
      state.user = null;
      clearPollingTimers();
      router.go('#/login');
      return null;
    }
    throw err;
  }
}
