'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter, useParams } from 'next/navigation';
import {
  CheckCircle, XCircle, AlertTriangle, HelpCircle,
  ChevronDown, ChevronUp, Plus, X, User,
} from 'lucide-react';
import {
  isAuthenticated, getMission, getMissionReadiness,
  updateMission, assignAssetToMission, listAssets,
} from '../../../lib/api';
import NavBar from '../../../components/NavBar';

// ─── Badges ──────────────────────────────────────────────────────────────────

function MissionStatusBadge({ status }) {
  const map = {
    PLANNED:   { cls: 'bg-blue-500/20 border-blue-500/40 text-blue-400' },
    ACTIVE:    { cls: 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400' },
    COMPLETED: { cls: 'bg-slate-600/30 border-slate-600 text-slate-400' },
    CANCELLED: { cls: 'bg-slate-700/30 border-slate-700 text-slate-500' },
  };
  const s = map[status] || map.PLANNED;
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold border ${s.cls}`}>
      {status}
    </span>
  );
}

function ReadinessBadge({ verdict }) {
  const map = {
    GO:           { cls: 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400', Icon: CheckCircle },
    GO_WITH_RISK: { cls: 'bg-amber-500/20 border-amber-500/40 text-amber-400',       Icon: AlertTriangle },
    NO_GO:        { cls: 'bg-red-500/20 border-red-500/40 text-red-400',             Icon: XCircle },
    UNKNOWN:      { cls: 'bg-slate-700/50 border-slate-700 text-slate-400',          Icon: HelpCircle },
  };
  const s = map[verdict] || map.UNKNOWN;
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold border ${s.cls}`}>
      <s.Icon className="w-3.5 h-3.5" />
      {verdict}
    </span>
  );
}

function AssetReadinessBadge({ status }) {
  const map = {
    READY:     { cls: 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400' },
    AT_RISK:   { cls: 'bg-amber-500/20 border-amber-500/40 text-amber-400' },
    NOT_READY: { cls: 'bg-red-500/20 border-red-500/40 text-red-400' },
    UNKNOWN:   { cls: 'bg-slate-700/50 border-slate-700 text-slate-400' },
  };
  const s = map[status] || map.UNKNOWN;
  return <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-bold border ${s.cls}`}>{status}</span>;
}

// ─── Assign Asset Modal ───────────────────────────────────────────────────────

function AssignAssetModal({ missionId, onClose, onAssigned }) {
  const [assets, setAssets] = useState([]);
  const [selectedId, setSelectedId] = useState('');
  const [notes, setNotes] = useState('');
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    listAssets({ limit: 100 }).then((d) => setAssets(d || [])).catch(() => {});
  }, []);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!selectedId) { setError('Select an asset.'); return; }
    setSaving(true);
    setError('');
    try {
      await assignAssetToMission(missionId, { asset_id: selectedId, notes: notes.trim() || undefined });
      onAssigned();
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4">
      <div className="w-full max-w-md bg-[#0d1117] border border-slate-700 rounded-2xl shadow-2xl overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <User className="w-4 h-4 text-blue-400" />
            <h2 className="text-sm font-bold font-mono text-slate-100">Assign Asset</h2>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-200 transition-colors"><X className="w-4 h-4" /></button>
        </div>
        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4">
          {error && <div className="bg-red-950/40 border border-red-700/40 text-red-400 text-xs font-mono px-4 py-2 rounded-lg">{error}</div>}
          <div>
            <label className="block text-[11px] font-mono text-slate-400 mb-1">Asset *</label>
            <select value={selectedId} onChange={(e) => setSelectedId(e.target.value)} required
              className="w-full px-3 py-2 text-sm font-mono bg-slate-900/60 border border-slate-700 rounded-lg text-slate-300 focus:outline-none focus:border-blue-500">
              <option value="">— select asset —</option>
              {assets.map((a) => <option key={a.id} value={a.id}>{a.asset_code} — {a.name}</option>)}
            </select>
          </div>
          <div>
            <label className="block text-[11px] font-mono text-slate-400 mb-1">Notes</label>
            <input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Optional"
              className="w-full px-3 py-2 text-sm font-mono bg-slate-900/60 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500" />
          </div>
          <div className="flex gap-3 pt-2 border-t border-slate-800">
            <button type="button" onClick={onClose}
              className="flex-1 px-4 py-2.5 text-sm font-mono text-slate-400 hover:text-slate-200 border border-slate-700 rounded-xl transition-colors">Cancel</button>
            <button type="submit" disabled={saving}
              className="flex-1 px-4 py-2.5 text-sm font-mono font-bold bg-blue-600 hover:bg-blue-500 text-white rounded-xl disabled:opacity-50 transition-colors">
              {saving ? 'Assigning…' : 'Assign'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

// ─── Readiness Panel ─────────────────────────────────────────────────────────

function ReadinessPanel({ readiness, onEvaluate, evaluating }) {
  const [open, setOpen] = useState(true);
  if (!readiness) return null;
  // API returns status (GO/NO_GO/GO_WITH_RISK/UNKNOWN) as "verdict"-equivalent
  const verdict = readiness.status || 'UNKNOWN';
  const risk_score = readiness.risk_score;
  const gaps = readiness.gaps || [];
  const conflicts = readiness.conflicts || [];
  const capReadiness = readiness.capability_readiness || [];

  return (
    <div className="bg-slate-900/40 border border-slate-800 rounded-xl overflow-hidden">
      <button
        onClick={() => setOpen(!open)}
        className="w-full flex items-center justify-between px-5 py-4 hover:bg-slate-800/30 transition-colors"
      >
        <div className="flex items-center gap-3">
          <span className="text-sm font-bold font-mono text-slate-100">Mission Readiness</span>
          <ReadinessBadge verdict={verdict} />
          {risk_score != null && (
            <span className="text-[11px] font-mono text-slate-400">
              Risk: <span style={{ color: risk_score > 0.7 ? '#f87171' : risk_score > 0.4 ? '#fbbf24' : '#34d399' }}>
                {(risk_score * 100).toFixed(0)}%
              </span>
            </span>
          )}
        </div>
        <div className="flex items-center gap-3">
          <button
            onClick={(e) => { e.stopPropagation(); onEvaluate(); }}
            disabled={evaluating}
            className="text-[11px] font-mono text-blue-400 hover:text-blue-300 px-2.5 py-1 rounded border border-blue-500/20 hover:border-blue-400/40 disabled:opacity-50 transition-colors"
          >
            {evaluating ? 'Evaluating…' : 'Re-evaluate'}
          </button>
          {open ? <ChevronUp className="w-4 h-4 text-slate-500" /> : <ChevronDown className="w-4 h-4 text-slate-500" />}
        </div>
      </button>

      {open && (
        <div className="px-5 pb-5 space-y-4">
          {/* Capability readiness summary */}
          {capReadiness.length > 0 && (
            <div>
              <p className="text-[10px] font-mono text-slate-500 uppercase mb-2">Capability Status</p>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2">
                {capReadiness.map((cr, i) => (
                  <div key={i} className="bg-slate-800/40 rounded-lg px-3 py-2 text-xs font-mono">
                    <div className="flex items-center justify-between gap-1 mb-1">
                      <span className="font-semibold text-slate-200">{cr.capability}</span>
                      <span className="text-slate-500">need {cr.required_count}</span>
                    </div>
                    <div className="flex gap-2 flex-wrap">
                      {cr.ready_assets > 0 && <span className="text-emerald-400">{cr.ready_assets} ready</span>}
                      {cr.at_risk_assets > 0 && <span className="text-amber-400">{cr.at_risk_assets} at-risk</span>}
                      {cr.not_ready_assets > 0 && <span className="text-red-400">{cr.not_ready_assets} not-ready</span>}
                      {cr.unknown_assets > 0 && <span className="text-slate-400">{cr.unknown_assets} unknown</span>}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Capability gaps */}
          {gaps.length > 0 && (
            <div>
              <p className="text-[10px] font-mono text-slate-500 uppercase mb-2">Capability Gaps</p>
              <div className="space-y-2">
                {gaps.map((g, i) => (
                  <div key={i} className="bg-red-950/20 border border-red-900/30 rounded-lg px-3 py-2 text-xs font-mono">
                    <div className="flex items-center justify-between gap-2 flex-wrap">
                      <span className="text-slate-200">{g.capability}</span>
                      <span className="text-red-400">Need {g.required_count} — Have {g.available_count} (short {g.shortage})</span>
                    </div>
                    {g.substitutions?.length > 0 && (
                      <div className="mt-1 flex flex-wrap gap-1">
                        {g.substitutions.map((sub, j) => (
                          <span key={j} className="text-[10px] bg-amber-900/20 border border-amber-800/30 text-amber-400 px-1.5 py-0.5 rounded">
                            {sub.asset_code} (suit {(sub.suitability_score * 100).toFixed(0)}%)
                          </span>
                        ))}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* Conflicts */}
          {conflicts.length > 0 && (
            <div>
              <p className="text-[10px] font-mono text-slate-500 uppercase mb-2">Conflicts</p>
              <div className="space-y-1">
                {conflicts.map((c, i) => (
                  <div key={i} className="bg-amber-950/20 border border-amber-800/30 rounded-lg px-3 py-1.5 text-xs font-mono text-amber-300">
                    {c.description}
                  </div>
                ))}
              </div>
            </div>
          )}

          {gaps.length === 0 && conflicts.length === 0 && capReadiness.length > 0 && (
            <p className="text-xs font-mono text-emerald-400 text-center py-2">✓ No gaps or conflicts detected</p>
          )}

          {capReadiness.length === 0 && (
            <p className="text-xs font-mono text-slate-500 text-center py-2">No assets assigned yet. Assign assets to evaluate mission readiness.</p>
          )}
        </div>
      )}
    </div>
  );
}

// ─── Main Page ────────────────────────────────────────────────────────────────

const STATUS_TRANSITIONS = {
  PLANNED:   ['ACTIVE', 'CANCELLED'],
  ACTIVE:    ['COMPLETED', 'CANCELLED'],
  COMPLETED: [],
  CANCELLED: [],
};

export default function MissionDetailPage() {
  const router = useRouter();
  const { missionId } = useParams();
  const [mission, setMission] = useState(null);
  const [readiness, setReadiness] = useState(null);
  const [loading, setLoading] = useState(true);
  const [evaluating, setEvaluating] = useState(false);
  const [showAssign, setShowAssign] = useState(false);
  const [statusChanging, setStatusChanging] = useState(false);

  const loadMission = useCallback(async () => {
    if (!missionId) return;
    setLoading(true);
    try {
      const [m, r] = await Promise.all([
        getMission(missionId),
        getMissionReadiness(missionId).catch(() => null),
      ]);
      setMission(m);
      setReadiness(r);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [missionId]);

  useEffect(() => {
    if (!isAuthenticated()) { router.replace('/login'); return; }
    loadMission();
  }, [router, loadMission]);

  const handleEvaluate = async () => {
    setEvaluating(true);
    try {
      const r = await getMissionReadiness(missionId);
      setReadiness(r);
    } catch { /* ignore */ }
    finally { setEvaluating(false); }
  };

  const handleStatusChange = async (newStatus) => {
    setStatusChanging(true);
    try {
      const updated = await updateMission(missionId, { status: newStatus });
      setMission(updated);
    } catch { /* ignore */ }
    finally { setStatusChanging(false); }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-[#070a12] text-slate-100 font-sans">
        <NavBar title="Mission" onBack={() => router.push('/missions')} />
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-8 space-y-4">
          {[...Array(4)].map((_, i) => <div key={i} className="h-24 bg-slate-800/60 rounded-xl animate-pulse" />)}
        </div>
      </div>
    );
  }

  if (!mission) {
    return (
      <div className="min-h-screen bg-[#070a12] text-slate-100 font-sans">
        <NavBar title="Mission Not Found" onBack={() => router.push('/missions')} />
        <div className="max-w-5xl mx-auto px-4 sm:px-6 py-16 text-center">
          <p className="text-slate-500 font-mono text-sm">Mission not found or you do not have access.</p>
        </div>
      </div>
    );
  }

  const transitions = STATUS_TRANSITIONS[mission.status] || [];

  return (
    <NavBar title={`Missions / ${mission.mission_code}`} onBack={() => router.push('/missions')}>
      {showAssign && (
        <AssignAssetModal
          missionId={missionId}
          onClose={() => setShowAssign(false)}
          onAssigned={() => { setShowAssign(false); loadMission(); handleEvaluate(); }}
        />
      )}

      <div className="space-y-6">
        {/* Header Box */}
        <div className="dashboard-card-shape rounded-2xl p-6 backdrop-blur-xl shadow-xl">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <div className="flex items-center gap-3 flex-wrap mb-1">
                <h1 className="text-2xl font-bold font-mono text-slate-100">{mission.mission_code}</h1>
                <MissionStatusBadge status={mission.status} />
                <span className={`text-xs font-mono font-bold uppercase px-3 py-1 rounded-full border ${
                  mission.priority === 'CRITICAL' ? 'bg-red-500/10 border-red-500/20 text-red-400' :
                  mission.priority === 'HIGH'     ? 'bg-amber-500/10 border-amber-500/20 text-amber-400' :
                  'bg-slate-700/30 border-slate-700 text-slate-400'
                }`}>{mission.priority}</span>
              </div>
              <p className="text-slate-200 text-base font-semibold">{mission.name}</p>
              {mission.description && <p className="text-slate-400 text-xs mt-1 font-mono">{mission.description}</p>}
            </div>
            {/* Status transition buttons */}
            {transitions.length > 0 && (
              <div className="flex gap-2 flex-wrap">
                {transitions.map((s) => (
                  <button
                    key={s}
                    onClick={() => handleStatusChange(s)}
                    disabled={statusChanging}
                    className={`px-4 py-2 text-xs font-mono font-bold rounded-xl border transition-colors disabled:opacity-50 ${
                      s === 'CANCELLED' ? 'border-red-700/40 bg-red-950/20 text-red-400 hover:bg-red-950/40' :
                      s === 'COMPLETED' ? 'border-emerald-700/40 bg-emerald-950/20 text-emerald-400 hover:bg-emerald-950/40' :
                      'border-blue-700/40 bg-blue-950/20 text-blue-400 hover:bg-blue-950/40'
                    }`}
                  >
                    → {s}
                  </button>
                ))}
              </div>
            )}
          </div>

          {/* Details grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-4 mt-5 pt-5 border-t border-slate-800/80 text-xs font-mono bg-slate-950/40 p-4 rounded-xl border border-slate-800/80">
            <div>
              <p className="text-slate-400 mb-0.5 font-bold">Duration</p>
              <p className="text-slate-100 font-bold">{mission.duration_hours} h</p>
            </div>
            {mission.planned_start && (
              <div>
                <p className="text-slate-400 mb-0.5 font-bold">Planned Start</p>
                <p className="text-slate-100 font-bold">{new Date(mission.planned_start).toLocaleString()}</p>
              </div>
            )}
            {mission.planned_end && (
              <div>
                <p className="text-slate-400 mb-0.5 font-bold">Planned End</p>
                <p className="text-slate-100 font-bold">{new Date(mission.planned_end).toLocaleString()}</p>
              </div>
            )}
            {mission.location && (
              <div>
                <p className="text-slate-400 mb-0.5 font-bold">Location</p>
                <p className="text-slate-100 font-bold">{mission.location}</p>
              </div>
            )}
          </div>
        </div>

        {/* Requirements Box */}
        {mission.requirements?.length > 0 && (
          <div className="dashboard-card-shape rounded-2xl p-6 backdrop-blur-xl shadow-xl">
            <p className="text-xs font-bold font-mono text-slate-300 uppercase mb-3">Capability Requirements</p>
            <div className="flex flex-wrap gap-2.5">
              {mission.requirements.map((r) => (
                <div key={r.id} className="flex items-center gap-2 bg-slate-950/60 border border-slate-800/80 rounded-xl px-3.5 py-2">
                  <span className="font-mono text-xs text-slate-100 font-bold">{r.capability}</span>
                  <span className="text-xs font-mono text-slate-400 font-bold">×{r.required_count}</span>
                  {r.is_critical && (
                    <span className="text-[10px] font-mono bg-red-500/10 border border-red-500/20 text-red-400 px-2 py-0.5 rounded font-bold">CRITICAL</span>
                  )}
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Readiness Panel Box */}
        <div>
          <div className="flex items-center justify-between mb-3">
            <p className="text-xs font-bold font-mono text-slate-300 uppercase">Readiness Evaluation</p>
            <button
              onClick={() => setShowAssign(true)}
              className="flex items-center gap-1.5 px-4 py-2 text-xs font-mono font-bold text-blue-300 hover:text-blue-200 border border-blue-500/30 rounded-xl bg-blue-600/20 shadow-md backdrop-blur-xl transition-all"
            >
              <Plus className="w-3.5 h-3.5" /> Assign Asset
            </button>
          </div>
          {readiness ? (
            <ReadinessPanel readiness={readiness} onEvaluate={handleEvaluate} evaluating={evaluating} />
          ) : (
            <div className="dashboard-card-shape rounded-2xl p-8 text-center backdrop-blur-xl shadow-xl">
              <p className="text-slate-400 font-mono text-sm">No readiness evaluation yet.</p>
              <button
                onClick={handleEvaluate}
                disabled={evaluating}
                className="mt-3 px-5 py-2.5 text-xs font-mono font-bold bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/30 text-blue-300 rounded-xl disabled:opacity-50 transition-colors"
              >
                {evaluating ? 'Evaluating…' : 'Run Evaluation'}
              </button>
            </div>
          )}
        </div>
      </div>
    </NavBar>
  );
}
