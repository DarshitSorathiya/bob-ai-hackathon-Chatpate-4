'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Plus, X, Shield, ChevronDown } from 'lucide-react';
import { isAuthenticated, listMissions, createMission } from '../../lib/api';
import NavBar from '../../components/NavBar';

function StatusBadge({ status }) {
  const map = {
    GO:           { cls: 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400' },
    GO_WITH_RISK: { cls: 'bg-amber-500/20 border-amber-500/40 text-amber-400' },
    NO_GO:        { cls: 'bg-red-500/20 border-red-500/40 text-red-400' },
    UNKNOWN:      { cls: 'bg-slate-700/50 border-slate-700 text-slate-400' },
    PLANNED:      { cls: 'bg-blue-500/20 border-blue-500/40 text-blue-400' },
    ACTIVE:       { cls: 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400' },
    COMPLETED:    { cls: 'bg-slate-600/30 border-slate-600 text-slate-400' },
    CANCELLED:    { cls: 'bg-slate-700/30 border-slate-700 text-slate-500' },
  };
  const s = map[status] || map.UNKNOWN;
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold border ${s.cls}`}>
      {status}
    </span>
  );
}

const EMPTY_REQ = { capability: '', required_count: 1, is_critical: true, notes: '' };

function CreateMissionModal({ onClose, onCreated }) {
  const [form, setForm] = useState({
    mission_code: '',
    name: '',
    description: '',
    priority: 'MEDIUM',
    planned_start: '',
    planned_end: '',
    duration_hours: '',
    location: '',
  });
  const [requirements, setRequirements] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const setField = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const addReq = () => setRequirements((r) => [...r, { ...EMPTY_REQ }]);
  const removeReq = (i) => setRequirements((r) => r.filter((_, idx) => idx !== i));
  const setReq = (i, k, v) =>
    setRequirements((r) => r.map((req, idx) => (idx === i ? { ...req, [k]: v } : req)));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSaving(true);
    try {
      const payload = {
        mission_code: form.mission_code.trim().toUpperCase(),
        name: form.name.trim(),
        description: form.description.trim() || undefined,
        priority: form.priority,
        duration_hours: parseFloat(form.duration_hours) || 0,
        location: form.location.trim() || undefined,
        planned_start: form.planned_start || undefined,
        planned_end: form.planned_end || undefined,
        requirements: requirements
          .filter((r) => r.capability.trim())
          .map((r) => ({
            capability: r.capability.trim().toUpperCase(),
            required_count: parseInt(r.required_count, 10) || 1,
            is_critical: r.is_critical,
            notes: r.notes.trim() || undefined,
          })),
      };
      const mission = await createMission(payload);
      onCreated(mission);
    } catch (err) {
      setError(err.message);
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4">
      <div className="w-full max-w-2xl bg-[#0d1117] border border-slate-700 rounded-2xl shadow-2xl overflow-hidden">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Shield className="w-4 h-4 text-blue-400" />
            <h2 className="text-sm font-bold font-mono text-slate-100">New Mission</h2>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-200 transition-colors"><X className="w-4 h-4" /></button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4 max-h-[80vh] overflow-y-auto">
          {error && (
            <div className="bg-red-950/40 border border-red-700/40 text-red-400 text-xs font-mono px-4 py-2 rounded-lg">{error}</div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[11px] font-mono text-slate-400 mb-1">Mission Code *</label>
              <input required value={form.mission_code} onChange={(e) => setField('mission_code', e.target.value.toUpperCase())}
                className="w-full px-3 py-2 text-sm font-mono bg-slate-900/60 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500"
                placeholder="OPE-ALPHA-01" />
            </div>
            <div>
              <label className="block text-[11px] font-mono text-slate-400 mb-1">Priority</label>
              <select value={form.priority} onChange={(e) => setField('priority', e.target.value)}
                className="w-full px-3 py-2 text-sm font-mono bg-slate-900/60 border border-slate-700 rounded-lg text-slate-300 focus:outline-none focus:border-blue-500">
                {['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'].map((p) => <option key={p}>{p}</option>)}
              </select>
            </div>
          </div>

          <div>
            <label className="block text-[11px] font-mono text-slate-400 mb-1">Mission Name *</label>
            <input required value={form.name} onChange={(e) => setField('name', e.target.value)}
              className="w-full px-3 py-2 text-sm font-mono bg-slate-900/60 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500"
              placeholder="Operation Nighthawk" />
          </div>

          <div>
            <label className="block text-[11px] font-mono text-slate-400 mb-1">Description</label>
            <textarea rows={2} value={form.description} onChange={(e) => setField('description', e.target.value)}
              className="w-full px-3 py-2 text-sm font-mono bg-slate-900/60 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500 resize-none"
              placeholder="Optional mission description" />
          </div>

          <div className="grid grid-cols-3 gap-4">
            <div>
              <label className="block text-[11px] font-mono text-slate-400 mb-1">Duration (h)</label>
              <input type="number" min="0" step="0.5" value={form.duration_hours} onChange={(e) => setField('duration_hours', e.target.value)}
                className="w-full px-3 py-2 text-sm font-mono bg-slate-900/60 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500"
                placeholder="4.5" />
            </div>
            <div>
              <label className="block text-[11px] font-mono text-slate-400 mb-1">Planned Start</label>
              <input type="datetime-local" value={form.planned_start} onChange={(e) => setField('planned_start', e.target.value)}
                className="w-full px-3 py-2 text-sm font-mono bg-slate-900/60 border border-slate-700 rounded-lg text-slate-300 focus:outline-none focus:border-blue-500" />
            </div>
            <div>
              <label className="block text-[11px] font-mono text-slate-400 mb-1">Planned End</label>
              <input type="datetime-local" value={form.planned_end} onChange={(e) => setField('planned_end', e.target.value)}
                className="w-full px-3 py-2 text-sm font-mono bg-slate-900/60 border border-slate-700 rounded-lg text-slate-300 focus:outline-none focus:border-blue-500" />
            </div>
          </div>

          <div>
            <label className="block text-[11px] font-mono text-slate-400 mb-1">Location</label>
            <input value={form.location} onChange={(e) => setField('location', e.target.value)}
              className="w-full px-3 py-2 text-sm font-mono bg-slate-900/60 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500"
              placeholder="Grid sector / base name" />
          </div>

          {/* Capability requirements */}
          <div>
            <div className="flex items-center justify-between mb-2">
              <label className="text-[11px] font-mono text-slate-400">Capability Requirements</label>
              <button type="button" onClick={addReq}
                className="flex items-center gap-1 text-[11px] font-mono text-blue-400 hover:text-blue-300 px-2 py-1 rounded border border-blue-500/20 hover:border-blue-400/40 transition-colors">
                <Plus className="w-3 h-3" /> Add
              </button>
            </div>
            {requirements.length === 0 && (
              <p className="text-[11px] text-slate-600 font-mono py-2 text-center border border-dashed border-slate-800 rounded-lg">No requirements added yet.</p>
            )}
            {requirements.map((req, i) => (
              <div key={i} className="flex items-center gap-2 mb-2">
                <input value={req.capability} onChange={(e) => setReq(i, 'capability', e.target.value.toUpperCase())} placeholder="RECON"
                  className="flex-1 px-2 py-1.5 text-xs font-mono bg-slate-900/60 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500" />
                <input type="number" min="1" value={req.required_count} onChange={(e) => setReq(i, 'required_count', e.target.value)}
                  className="w-16 px-2 py-1.5 text-xs font-mono bg-slate-900/60 border border-slate-700 rounded-lg text-slate-100 focus:outline-none focus:border-blue-500 text-center" />
                <label className="flex items-center gap-1 text-[11px] font-mono text-slate-400 whitespace-nowrap">
                  <input type="checkbox" checked={req.is_critical} onChange={(e) => setReq(i, 'is_critical', e.target.checked)} className="rounded" />
                  Critical
                </label>
                <button type="button" onClick={() => removeReq(i)} className="text-slate-600 hover:text-red-400 transition-colors"><X className="w-3.5 h-3.5" /></button>
              </div>
            ))}
          </div>

          {/* Actions */}
          <div className="flex gap-3 pt-2 border-t border-slate-800">
            <button type="button" onClick={onClose}
              className="flex-1 px-4 py-2.5 text-sm font-mono text-slate-400 hover:text-slate-200 border border-slate-700 hover:border-slate-600 rounded-xl transition-colors">
              Cancel
            </button>
            <button type="submit" disabled={saving}
              className="flex-1 px-4 py-2.5 text-sm font-mono font-bold bg-blue-600 hover:bg-blue-500 text-white rounded-xl disabled:opacity-50 disabled:cursor-not-allowed transition-colors">
              {saving ? 'Creating…' : 'Create Mission'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function MissionsPage() {
  const router = useRouter();
  const [missions, setMissions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);

  useEffect(() => {
    if (!isAuthenticated()) { router.replace('/login'); return; }
  }, [router]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listMissions({ limit: 50 });
      setMissions(data || []);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleCreated = (mission) => {
    setShowCreate(false);
    router.push(`/missions/${mission.id}`);
  };

  return (
    <div className="min-h-screen bg-[#070a12] text-slate-100 font-sans">
      <NavBar title="Missions" onBack={() => router.push('/dashboard')} />

      {showCreate && (
        <CreateMissionModal onClose={() => setShowCreate(false)} onCreated={handleCreated} />
      )}

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-5">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold">Missions</h1>
            <p className="text-xs text-slate-500 font-mono mt-0.5">{missions.length} total</p>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-3 py-2 text-sm font-mono font-semibold bg-blue-600/20 hover:bg-blue-600/30 border border-blue-500/40 hover:border-blue-400/60 text-blue-400 rounded-xl transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Mission
          </button>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(6)].map((_, i) => <div key={i} className="h-36 bg-slate-800/60 rounded-xl animate-pulse" />)}
          </div>
        ) : missions.length === 0 ? (
          <div className="bg-slate-900/40 border border-dashed border-slate-700 rounded-xl p-12 text-center">
            <p className="text-slate-500 font-mono text-sm">No missions found.</p>
            <button onClick={() => setShowCreate(true)} className="mt-3 text-blue-400 hover:text-blue-300 text-xs font-mono underline">
              Create the first mission
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {missions.map((mission) => (
              <div
                key={mission.id}
                className="bg-slate-900/40 border border-slate-800 hover:border-slate-700 rounded-xl p-5 cursor-pointer transition-colors group"
                onClick={() => router.push(`/missions/${mission.id}`)}
              >
                <div className="flex items-start justify-between gap-2 mb-3">
                  <div className="min-w-0">
                    <p className="font-mono font-bold text-slate-100 truncate">{mission.mission_code}</p>
                    <p className="text-xs text-slate-400 mt-0.5 truncate">{mission.name}</p>
                  </div>
                  <StatusBadge status={mission.status} />
                </div>
                <div className="grid grid-cols-2 gap-2 text-[11px] font-mono">
                  <div>
                    <p className="text-slate-500">Duration</p>
                    <p className="text-slate-200">{mission.duration_hours} h</p>
                  </div>
                  <div>
                    <p className="text-slate-500">Priority</p>
                    <p className="text-slate-200">{mission.priority}</p>
                  </div>
                  {mission.planned_start && (
                    <div className="col-span-2">
                      <p className="text-slate-500">Planned Start</p>
                      <p className="text-slate-200">{new Date(mission.planned_start).toLocaleString()}</p>
                    </div>
                  )}
                </div>
                {mission.requirements?.length > 0 && (
                  <div className="mt-3 pt-3 border-t border-slate-800/60">
                    <p className="text-[10px] text-slate-500 font-mono mb-1">REQUIREMENTS</p>
                    <div className="flex flex-wrap gap-1">
                      {mission.requirements.map((r) => (
                        <span key={r.id} className="text-[10px] font-mono bg-blue-500/10 border border-blue-500/20 text-blue-300 px-2 py-0.5 rounded">
                          {r.capability} ×{r.required_count}{r.is_critical ? ' !' : ''}
                        </span>
                      ))}
                    </div>
                  </div>
                )}
                <p className="mt-3 text-[10px] text-slate-600 font-mono group-hover:text-slate-500 transition-colors">Click to view details →</p>
              </div>
            ))}
          </div>
        )}
      </main>
    </div>
  );
}
