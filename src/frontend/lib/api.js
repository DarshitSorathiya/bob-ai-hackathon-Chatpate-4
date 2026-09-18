'use client';

/**
 * MissionReady AI — central API client for the Next.js frontend.
 *
 * Auth routes (/auth/register, /auth/login, /auth/me, /auth/google) return
 * raw AuthResponse / UserResponse shapes (NOT wrapped in the envelope).
 *
 * All other routes return the standard envelope:
 *   { success, data, meta, error }
 *
 * Session keys:
 *   missionready_access_token  — JWT bearer token
 *   missionready_user          — JSON-serialised UserResponse
 */

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_URL || 'http://localhost:8000/api/v1';

// ─── Session helpers ──────────────────────────────────────────────────────────

const TOKEN_KEY = 'missionready_access_token';
const USER_KEY  = 'missionready_user';

export function getToken() {
  if (typeof window === 'undefined') return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function getUser() {
  if (typeof window === 'undefined') return null;
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function saveSession(authResponse) {
  localStorage.setItem(TOKEN_KEY, authResponse.access_token);
  localStorage.setItem(USER_KEY, JSON.stringify(authResponse.user));
}

export function clearSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
}

export function isAuthenticated() {
  return Boolean(getToken());
}

// ─── Core request helper ──────────────────────────────────────────────────────

async function request(path, options = {}) {
  const token = getToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };

  const response = await fetch(`${API_BASE_URL}${path}`, {
    ...options,
    headers,
  });

  let payload;
  try {
    payload = await response.json();
  } catch {
    payload = {};
  }

  if (!response.ok) {
    // FastAPI validation error: { detail: [{msg, loc, type}] }
    if (Array.isArray(payload.detail)) {
      throw new Error(payload.detail.map((d) => d.msg).join(', '));
    }
    // API envelope error: { success: false, error: { message } }
    if (payload.error?.message) {
      throw new Error(payload.error.message);
    }
    // Plain FastAPI HTTPException: { detail: "string" }
    if (payload.detail) {
      throw new Error(payload.detail);
    }
    throw new Error(`Request failed with status ${response.status}`);
  }

  // If this is an envelope response, unwrap it
  if (payload && typeof payload.success === 'boolean') {
    if (!payload.success) {
      throw new Error(payload.error?.message || 'Request failed');
    }
    return payload.data;
  }

  // Direct response (auth routes, etc.)
  return payload;
}

// ─── Auth API ─────────────────────────────────────────────────────────────────

/**
 * Register a new user. Returns AuthResponse { access_token, token_type, user }.
 */
export function registerUser(data) {
  return request('/auth/register', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * Log in with email + password. Returns AuthResponse.
 */
export function loginUser(data) {
  return request('/auth/login', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

/**
 * Log in with a Google ID token. Returns AuthResponse.
 */
export function loginWithGoogle(idToken) {
  return request('/auth/google', {
    method: 'POST',
    body: JSON.stringify({ id_token: idToken }),
  });
}

/**
 * Validate the stored token and return the current UserResponse.
 * Throws if token is invalid / expired.
 */
export function getMe() {
  return request('/auth/me');
}

/**
 * Request a password reset email (no-op on backend for now).
 */
export function requestPasswordReset(email) {
  return request('/auth/forgot-password', {
    method: 'POST',
    body: JSON.stringify({ email }),
  });
}

// ─── System API ───────────────────────────────────────────────────────────────

export function getHealth() {
  return request('/health');
}

export function ingestTelemetry(readings, refresh_predictions = true) {
  return request('/telemetry/batch', {
    method: 'POST',
    body: JSON.stringify({ readings, refresh_predictions }),
  });
}

// ─── Assets API ───────────────────────────────────────────────────────────────

export function listAssets(params = {}) {
  const qs = new URLSearchParams(params).toString();
  return request(`/assets${qs ? '?' + qs : ''}`);
}

export function getAsset(assetId) {
  return request(`/assets/${assetId}`);
}

export function createAsset(data) {
  return request('/assets', { method: 'POST', body: JSON.stringify(data) });
}

export function getAssetComponents(assetId) {
  return request(`/assets/${assetId}/components`);
}

export function getAssetSensors(assetId) {
  return request(`/assets/${assetId}/sensors`);
}

export function getAssetPredictions(assetId, limit = 20) {
  return request(`/assets/${assetId}/predictions?limit=${limit}`);
}

export function getAssetReadiness(assetId) {
  return request(`/assets/${assetId}/readiness`);
}

export function getAssetAlerts(assetId) {
  return request(`/assets/${assetId}/alerts`);
}

// ─── Readiness API ────────────────────────────────────────────────────────────

export function getFleetReadinessSummary() {
  return request('/readiness');
}

export function getAllReadiness(statusFilter) {
  const qs = statusFilter ? `?status_filter=${statusFilter}` : '';
  return request(`/readiness/all${qs}`);
}

export function evaluateAssetReadiness(assetId, params = {}) {
  const qs = new URLSearchParams(params).toString();
  return request(`/readiness/evaluate/${assetId}${qs ? '?' + qs : ''}`, { method: 'POST' });
}

// ─── Missions API ─────────────────────────────────────────────────────────────

export function listMissions(params = {}) {
  const qs = new URLSearchParams(params).toString();
  return request(`/missions${qs ? '?' + qs : ''}`);
}

export function getMission(missionId) {
  return request(`/missions/${missionId}`);
}

export function createMission(data) {
  return request('/missions', { method: 'POST', body: JSON.stringify(data) });
}

export function updateMission(missionId, data) {
  return request(`/missions/${missionId}`, { method: 'PATCH', body: JSON.stringify(data) });
}

export function getMissionReadiness(missionId) {
  return request(`/missions/${missionId}/readiness`);
}

export function assignAssetToMission(missionId, data) {
  return request(`/missions/${missionId}/assignments`, { method: 'POST', body: JSON.stringify(data) });
}

// ─── Maintenance API ──────────────────────────────────────────────────────────

export function listWorkOrders(params = {}) {
  const qs = new URLSearchParams(params).toString();
  return request(`/maintenance/work-orders${qs ? '?' + qs : ''}`);
}

export function getWorkOrder(woId) {
  return request(`/maintenance/work-orders/${woId}`);
}

export function createWorkOrder(data) {
  return request('/maintenance/work-orders', { method: 'POST', body: JSON.stringify(data) });
}

export function updateWorkOrder(woId, data) {
  return request(`/maintenance/work-orders/${woId}`, { method: 'PATCH', body: JSON.stringify(data) });
}

export function getMaintenanceQueue() {
  return request('/maintenance/queue');
}

// ─── Alerts API ───────────────────────────────────────────────────────────────

export function listAlerts(params = {}) {
  const qs = new URLSearchParams(params).toString();
  return request(`/alerts${qs ? '?' + qs : ''}`);
}

export function acknowledgeAlert(alertId) {
  return request(`/alerts/${alertId}/acknowledge`, { method: 'POST' });
}

// ─── Data quality API ─────────────────────────────────────────────────────────

export function getDataQualityEvents(params = {}) {
  const qs = new URLSearchParams(params).toString();
  return request(`/data-quality${qs ? '?' + qs : ''}`);
}

export function getDataQualitySummary() {
  return request('/data-quality/summary');
}

// ─── Copilot API ──────────────────────────────────────────────────────────────

export function queryCopilot(question, assetCode = null) {
  return request('/copilot/query', {
    method: 'POST',
    body: JSON.stringify({ question, asset_code: assetCode }),
  });
}

// ─── Models API ───────────────────────────────────────────────────────────────

export function listModels() {
  return request('/models');
}

export function getModel(tag) {
  return request(`/models/${encodeURIComponent(tag)}`);
}
