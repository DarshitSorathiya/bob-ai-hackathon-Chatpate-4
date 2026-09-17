'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Plus, X } from 'lucide-react';
import { isAuthenticated, listMissions, createMission, listAssets } from '../../lib/api';
import NavBar from '../../components/NavBar';

const STATUS_MAP = {
  PLANNING:    { badge: 'bg-blue-500/20 border-blue-500/40 text-blue-400' },
  BRIEFING:    { badge: 'bg-amber-500/20 border-amber-500/40 text-amber-400' },
  IN_PROGRESS: { badge: 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400' },
  COMPLETED:   { badge: 'bg-slate-700/50 border-slate-700 text-slate-400' },
  CANCELLED:   { badge: 'bg-red-500/20 border-red-500/40 text-red-400' },
};

function StatusBadge({ status }) {
  const s = STATUS_MAP[status] ?? { badge: 'bg-slate-700/50 border-slate-700 text-slate-400' };
  return (
    <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-mono font-bold border ${s.badge}`}>
      {status?.replace('_', ' ')}
    </span>
  );
}

function CreateMissionModal({ onClose, onCreated }) {
  const [form, setForm] = useState({
    name: '',
    mission_code: '',
    description: '',
    duration_hours: '2.0',
    priority: '3',
    planned_start: '',
    location: '',
  });
  const [requirements, setRequirements] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const setField = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const addReq = () => {
    setRequirements((r) => [...r, { capability: '', required_count: 1, is_critical: false }]);
  };
  const removeReq = (i) => setRequirements((r) => r.filter((_, idx) => idx !== i));
  const setReq = (i, k, v) => setRequirements((r) => r.map((req, idx) => idx === i ? { ...req, [k]: v } : req));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSaving(true);
    try {
      const payload = {
        name: form.name.trim(),
        mission_code: form.mission_code.trim().toUpperCase(),
        description: form.description.trim() || undefined,
        duration_hours: parseFloat(form.duration_hours) || 2.0,
        priority: parseInt(form.priority, 10) || 3,
        planned_start: form.planned_start ? new Date(form.planned_start).toISOString() : undefined,
        location: form.location.trim() || undefined,
        requirements: requirements
          .filter((req) => req.capability.trim())
          .map((req) => ({
            capability: req.capability.trim().toUpperCase(),
            required_count: parseInt(req.required_count, 10) || 1,
            is_critical: Boolean(req.is_critical),
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
      <div className="w-full max-w-xl bg-[#090d16] border-[3px] border-white rounded-2xl shadow-2xl overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800">
          <h2 className="text-sm font-bold font-mono text-slate-100">Create New Mission</h2>
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
                className="w-full px-3 py-2 text-sm font-mono bg-slate-900/60 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500 uppercase"
                placeholder="MIS-001" />
            </div>
            <div>
              <label className="block text-[11px] font-mono text-slate-400 mb-1">Mission Name *</label>
              <input required value={form.name} onChange={(e) => setField('name', e.target.value)}
                className="w-full px-3 py-2 text-sm font-mono bg-slate-900/60 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500"
                placeholder="Operation Recon Alpha" />
            </div>
          </div>

          <div>
            <label className="block text-[11px] font-mono text-slate-400 mb-1">Description</label>
            <textarea rows={2} value={form.description} onChange={(e) => setField('description', e.target.value)}
              className="w-full px-3 py-2 text-sm font-mono bg-slate-900/60 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500 resize-none"
              placeholder="Optional mission details" />
          </div>

          <div className="grid grid-cols-3 gap-3">
            <div>
              <label className="block text-[11px] font-mono text-slate-400 mb-1">Duration (hours)</label>
              <input type="number" step="0.5" value={form.duration_hours} onChange={(e) => setField('duration_hours', e.target.value)}
                className="w-full px-3 py-2 text-sm font-mono bg-slate-900/60 border border-slate-700 rounded-lg text-slate-100 focus:outline-none focus:border-blue-500" />
            </div>
            <div>
              <label className="block text-[11px] font-mono text-slate-400 mb-1">Priority (1–5)</label>
              <input type="number" min="1" max="5" value={form.priority} onChange={(e) => setField('priority', e.target.value)}
                className="w-full px-3 py-2 text-sm font-mono bg-slate-900/60 border border-slate-700 rounded-lg text-slate-100 focus:outline-none focus:border-blue-500" />
            </div>
            <div>
              <label className="block text-[11px] font-mono text-slate-400 mb-1">Planned Start</label>
              <input type="datetime-local" value={form.planned_start} onChange={(e) => setField('planned_start', e.target.value)}
                className="w-full px-3 py-2 text-xs font-mono bg-slate-900/60 border border-slate-700 rounded-lg text-slate-200 focus:outline-none focus:border-blue-500" />
            </div>
          </div>

          <div className="flex gap-3 pt-2 border-t border-slate-800">
            <button type="button" onClick={onClose}
              className="flex-1 px-4 py-2.5 text-xs font-mono text-slate-400 hover:text-slate-200 border border-slate-700 rounded-xl transition-colors">
              Cancel
            </button>
            <button type="submit" disabled={saving}
              className="flex-1 px-4 py-2.5 text-xs font-mono font-bold bg-blue-600 hover:bg-blue-500 text-white rounded-xl disabled:opacity-50 transition-colors">
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
    <NavBar title="Mission Sessions" onBack={() => router.push('/dashboard')}>
      {showCreate && (
        <CreateMissionModal onClose={() => setShowCreate(false)} onCreated={handleCreated} />
      )}

      <div className="space-y-6">
        {/* Title Header */}
        <div className="flex items-center justify-between flex-wrap gap-4 pt-2">
          <div className="space-y-1">
            <span className="inline-block px-3 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-widest bg-blue-950/80 text-blue-400 border border-blue-800/60 mb-1">
              MISSION PLANNING
            </span>
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-100 font-sans">
              Operational Sessions
            </h1>
            <p className="text-xs text-slate-400 font-mono pt-1">{missions.length} active sessions</p>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2.5 text-xs font-mono font-bold bg-blue-600/20 hover:bg-blue-600/30 border-[3px] border-white text-blue-300 rounded-2xl transition-all shadow-xl backdrop-blur-xl"
          >
            <Plus className="w-4 h-4" />
            New Mission
          </button>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[...Array(6)].map((_, i) => <div key={i} className="h-44 bg-slate-900/60 rounded-2xl border-[3px] border-white animate-pulse" />)}
          </div>
        ) : missions.length === 0 ? (
          <div className="bg-[#0a0f1d]/80 border-[3px] border-white rounded-2xl p-12 text-center backdrop-blur-xl shadow-xl">
            <p className="text-slate-400 font-mono text-sm">No operational missions found.</p>
            <button onClick={() => setShowCreate(true)} className="mt-3 text-blue-400 hover:text-blue-300 text-xs font-mono font-bold underline">
              Create the first mission
            </button>
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {missions.map((mission) => (
              <div
                key={mission.id}
                className="bg-[#0a0f1d]/80 border-[3px] border-white hover:border-blue-400/50 rounded-2xl p-6 backdrop-blur-xl shadow-xl cursor-pointer transition-all flex flex-col justify-between group"
                onClick={() => router.push(`/missions/${mission.id}`)}
              >
                <div>
                  <div className="flex items-start justify-between gap-3 mb-4">
                    <div className="min-w-0">
                      <p className="font-mono font-bold text-lg text-slate-100 truncate">{mission.mission_code}</p>
                      <p className="text-xs text-slate-300 mt-0.5 truncate font-semibold">{mission.name}</p>
                    </div>
                    <StatusBadge status={mission.status} />
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-xs font-mono bg-slate-950/40 p-3 rounded-xl border border-slate-800/80">
                    <div>
                      <p className="text-slate-400 font-bold">Duration</p>
                      <p className="text-slate-100 font-bold">{mission.duration_hours} h</p>
                    </div>
                    <div>
                      <p className="text-slate-400 font-bold">Priority</p>
                      <p className="text-slate-100 font-bold">{mission.priority}</p>
                    </div>
                  </div>
                </div>
                <p className="mt-4 text-xs text-blue-400 font-mono font-bold group-hover:text-blue-300 transition-colors">View Mission Details →</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </NavBar>
  );
}
