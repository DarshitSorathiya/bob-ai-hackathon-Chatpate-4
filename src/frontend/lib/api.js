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

// ─── Enrolled Demo Dataset Fallbacks for Offline / Standalone Mode ───────────────────────────

const DEMO_ENROLLED_ASSETS = [
  {
    id: 'ast_ah64_01',
    asset_code: 'TJS-014',
    asset_type: 'FIXED_WING',
    call_sign: 'Tejas Lead',
    description: 'HAL Tejas Mk1A — Light Combat Aircraft (HAL Airport Base, Bengaluru, Karnataka)',
    manufacturer: 'HAL',
    model_number: 'Tejas Mk1A',
    serial_number: 'SN-TJS-014',
    total_hours: 847.5,
    status: 'READY',
  },
  {
    id: 'ast_f16_01',
    asset_code: 'SU-30-01',
    asset_type: 'FIXED_WING',
    call_sign: 'Flanker Alpha',
    description: 'Sukhoi Su-30MKI — Twinjet Air Superiority Fighter (Lohegaon AFB, Pune, Maharashtra)',
    manufacturer: 'HAL / Sukhoi',
    model_number: 'Su-30MKI',
    serial_number: 'SN-SU30-001',
    total_hours: 2821.0,
    status: 'READY',
  },
  {
    id: 'ast_hmmwv_01',
    asset_code: 'LCH-01',
    asset_type: 'HELICOPTER',
    call_sign: 'Prachand 1',
    description: 'HAL Prachand LCH — Light Combat Helicopter (Jodhpur Airbase, Rajasthan)',
    manufacturer: 'HAL',
    model_number: 'Prachand LCH',
    serial_number: 'SN-LCH-001',
    total_hours: 450.0,
    status: 'AT_RISK',
  },
  {
    id: 'ast_c130_02',
    asset_code: 'RAF-01',
    asset_type: 'FIXED_WING',
    call_sign: 'Golden Arrows 1',
    description: 'Dassault Rafale DH — Omni-role Air Superiority Fighter (Ambala AFS, Punjab)',
    manufacturer: 'Dassault Aviation',
    model_number: 'Rafale DH',
    serial_number: 'SN-RAF-001',
    total_hours: 1120.0,
    status: 'READY',
  },
  {
    id: 'ast_uh60_03',
    asset_code: 'MIG-29-02',
    asset_type: 'FIXED_WING',
    call_sign: 'Black Archers 2',
    description: 'MiG-29UPG Fulcrum — Multi-role Fighter (Adampur Air Force Base, Jalandhar, Punjab)',
    manufacturer: 'Mikoyan',
    model_number: 'MiG-29UPG',
    serial_number: 'SN-MIG29-002',
    total_hours: 1980.5,
    status: 'NOT_READY',
  },
  {
    id: 'ast_ch47_04',
    asset_code: 'C17-01',
    asset_type: 'FIXED_WING',
    call_sign: 'Skyforce Heavy',
    description: 'C-17 Globemaster III — Strategic Military Transport (Hindon AFS, Ghaziabad, UP)',
    manufacturer: 'Boeing',
    model_number: 'C-17A',
    serial_number: 'SN-C17-001',
    total_hours: 3310.0,
    status: 'READY',
  },
];

const DEMO_ENROLLED_READINESS = [
  { asset_id: 'ast_ah64_01', status: 'READY', readiness_score: 95.5, readiness_level: 'MISSION_READY' },
  { asset_id: 'ast_f16_01', status: 'READY', readiness_score: 91.2, readiness_level: 'MISSION_READY' },
  { asset_id: 'ast_hmmwv_01', status: 'AT_RISK', readiness_score: 68.0, readiness_level: 'DEGRADED' },
  { asset_id: 'ast_c130_02', status: 'READY', readiness_score: 88.4, readiness_level: 'MISSION_READY' },
  { asset_id: 'ast_uh60_03', status: 'NOT_READY', readiness_score: 42.0, readiness_level: 'UNSERVICEABLE' },
  { asset_id: 'ast_ch47_04', status: 'READY', readiness_score: 94.0, readiness_level: 'MISSION_READY' },
];

const DEMO_ENROLLED_SUMMARY = {
  total_assets: 6,
  counts: {
    READY: 4,
    AT_RISK: 1,
    NOT_READY: 1,
  },
};

const DEMO_ENROLLED_ALERTS = [
  { id: 'alt_01', severity: 'critical', title: 'UH-60-03 Main Rotor Vibration Spike', message: 'Rotor vibration sensor exceeded critical threshold (26.5 mm/s).', status: 'ACTIVE', created_at: new Date().toISOString() },
  { id: 'alt_02', severity: 'warning', title: 'HMMWV-01 Coolant Temp High', message: 'Engine coolant temp elevated above 105°C during high load.', status: 'ACTIVE', created_at: new Date().toISOString() },
  { id: 'alt_03', severity: 'info', title: 'AH-64-01 Telemetry Sync', message: 'HUMS sensor telemetry package ingested successfully.', status: 'ACTIVE', created_at: new Date().toISOString() },
];

const DEMO_ENROLLED_QUEUE = {
  total_scheduled: 2,
  items: [
    { id: 'wo_01', maintenance_state: 'IN_PROGRESS', title: 'UH-60-03 Rotor Assembly Inspection', priority: 'HIGH' },
    { id: 'wo_02', maintenance_state: 'SCHEDULED', title: 'HMMWV-01 Radiator & Coolant Flush', priority: 'MEDIUM' },
  ],
};

const DEMO_ENROLLED_MISSIONS = [
  { id: 'msn_01', mission_code: 'OPE-NIGHTHAWK-01', name: 'Operation Nighthawk', status: 'IN_PROGRESS', priority: 'HIGH' },
  { id: 'msn_02', mission_code: 'OPE-SILVERWING-02', name: 'Operation Silverwing', status: 'PLANNED', priority: 'MEDIUM' },
  { id: 'msn_03', mission_code: 'OPE-IRONFORGE-03', name: 'Operation Ironforge', status: 'SCHEDULED', priority: 'HIGH' },
];

function getEnrolledFallback(path) {
  if (path.startsWith('/assets')) return DEMO_ENROLLED_ASSETS;
  if (path.startsWith('/readiness/all')) return DEMO_ENROLLED_READINESS;
  if (path.startsWith('/readiness')) return DEMO_ENROLLED_SUMMARY;
  if (path.startsWith('/alerts')) return DEMO_ENROLLED_ALERTS;
  if (path.startsWith('/maintenance')) return DEMO_ENROLLED_QUEUE;
  if (path.startsWith('/missions')) return DEMO_ENROLLED_MISSIONS;
  return null;
}

// ─── Core request helper ──────────────────────────────────────────────────────

async function request(path, options = {}) {
  const token = getToken();
  const headers = {
    'Content-Type': 'application/json',
    ...(token ? { Authorization: `Bearer ${token}` } : {}),
    ...(options.headers || {}),
  };

  let response;
  try {
    response = await fetch(`${API_BASE_URL}${path}`, {
      ...options,
      headers,
    });
  } catch (err) {
    const fallback = getEnrolledFallback(path);
    if (fallback !== null) return fallback;
    throw err;
  }

  let payload;
  try {
    payload = await response.json();
  } catch {
    payload = {};
  }

  if (!response.ok) {
    const fallback = getEnrolledFallback(path);
    if (fallback !== null) return fallback;

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

export const copilotQuery = queryCopilot;

// ─── Models API ───────────────────────────────────────────────────────────────

export function listModels() {
  return request('/models');
}

export function getModel(tag) {
  return request(`/models/${encodeURIComponent(tag)}`);
}
