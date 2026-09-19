'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Plus, X, Calendar, Compass, Clock, ShieldCheck } from 'lucide-react';
import { isAuthenticated, listMissions, createMission, hasMinRole } from '../../lib/api';
import NavBar from '../../components/NavBar';

const STATUS_MAP = {
  PLANNED:     { badge: 'bg-[#e1eadf] border-[#1e4d35]/30 text-[#1e4d35] dark:bg-[#1e4d35]/30 dark:text-emerald-300' },
  ACTIVE:      { badge: 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400' },
  PLANNING:    { badge: 'bg-[#e1eadf] border-[#1e4d35]/30 text-[#1e4d35] dark:bg-[#1e4d35]/30 dark:text-emerald-300' },
  BRIEFING:    { badge: 'bg-amber-500/15 border-amber-500/30 text-amber-400' },
  IN_PROGRESS: { badge: 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400' },
  COMPLETED:   { badge: 'bg-slate-700/50 border-slate-700 text-slate-400' },
  CANCELLED:   { badge: 'bg-red-500/15 border-red-500/30 text-red-400' },
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
    priority: 'MEDIUM',
    planned_start: '',
    location: '',
    requirements: [{ capability: '', required_count: '1', is_critical: true }],
  });
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  const setField = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const setRequirement = (index, key, value) => setForm((f) => ({
    ...f,
    requirements: f.requirements.map((item, i) => i === index ? { ...item, [key]: value } : item),
  }));

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
        priority: form.priority || 'MEDIUM',
        planned_start: form.planned_start ? new Date(form.planned_start).toISOString() : undefined,
        location: form.location.trim() || undefined,
        requirements: form.requirements
          .filter((requirement) => requirement.capability.trim())
          .map((requirement) => ({
            capability: requirement.capability.trim().toUpperCase(),
            required_count: parseInt(requirement.required_count, 10) || 1,
            is_critical: requirement.is_critical,
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-md px-4">
      <div className="w-full max-w-xl dashboard-card-shape rounded-2xl shadow-2xl overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-[#1e4d35]/20 dark:border-slate-800">
          <h2 className="text-sm font-bold font-mono text-[#122018] dark:text-slate-100">Create New Mission Session</h2>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 transition-colors"><X className="w-4 h-4" /></button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4 max-h-[80vh] overflow-y-auto">
          {error && (
            <div className="bg-red-950/40 border border-red-700/40 text-red-400 text-xs font-mono px-4 py-2 rounded-lg">{error}</div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[11px] font-mono text-[#566b5c] dark:text-slate-400 mb-1">Mission Code *</label>
              <input required value={form.mission_code} onChange={(e) => setField('mission_code', e.target.value.toUpperCase())}
                className="w-full px-3 py-2 text-sm font-mono bg-white dark:bg-slate-950/60 border border-[#1e4d35]/20 rounded-lg text-[#122018] dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:border-[#1e4d35] uppercase"
                placeholder="MIS-001" />
            </div>
            <div>
              <label className="block text-[11px] font-mono text-[#566b5c] dark:text-slate-400 mb-1">Mission Name *</label>
              <input required value={form.name} onChange={(e) => setField('name', e.target.value)}
                className="w-full px-3 py-2 text-sm font-mono bg-white dark:bg-slate-950/60 border border-[#1e4d35]/20 rounded-lg text-[#122018] dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:border-[#1e4d35]"
                placeholder="Operation Recon Alpha" />
            </div>
          </div>

          <div>
            <label className="block text-[11px] font-mono text-[#566b5c] dark:text-slate-400 mb-1">Description</label>
            <textarea rows={2} value={form.description} onChange={(e) => setField('description', e.target.value)}
              className="w-full px-3 py-2 text-sm font-mono bg-white dark:bg-slate-950/60 border border-[#1e4d35]/20 rounded-lg text-[#122018] dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:border-[#1e4d35] resize-none"
              placeholder="Optional mission briefing notes..." />
          </div>

          <div className="grid grid-cols-3 gap-3">

                      <div className="space-y-2 border-t border-[#1e4d35]/20 pt-4 col-span-3">
                        <div className="flex items-center justify-between">
                          <label className="text-[11px] font-mono text-[#566b5c] dark:text-slate-400">Mission Requirements</label>
                          <button type="button" onClick={() => setForm((f) => ({ ...f, requirements: [...f.requirements, { capability: '', required_count: '1', is_critical: true }] }))} className="text-[11px] font-mono text-[#1e4d35] dark:text-emerald-400 font-bold">Add requirement</button>
                        </div>
                        {form.requirements.map((requirement, index) => (
                          <div key={index} className="grid grid-cols-[1fr_80px_auto] gap-2">
                            <input value={requirement.capability} onChange={(e) => setRequirement(index, 'capability', e.target.value)} placeholder="HELICOPTER" className="px-3 py-2 text-xs font-mono bg-white dark:bg-slate-950/60 border border-[#1e4d35]/20 rounded-lg text-[#122018] dark:text-slate-100" />
                            <input type="number" min="1" value={requirement.required_count} onChange={(e) => setRequirement(index, 'required_count', e.target.value)} className="px-3 py-2 text-xs font-mono bg-white dark:bg-slate-950/60 border border-[#1e4d35]/20 rounded-lg text-[#122018] dark:text-slate-100" />
                            <label className="flex items-center gap-1 text-[10px] font-mono text-[#566b5c] dark:text-slate-400"><input type="checkbox" checked={requirement.is_critical} onChange={(e) => setRequirement(index, 'is_critical', e.target.checked)} /> critical</label>
                          </div>
                        ))}
                      </div>
            <div>
              <label className="block text-[11px] font-mono text-[#566b5c] dark:text-slate-400 mb-1">Duration (h)</label>
              <input type="number" step="0.5" value={form.duration_hours} onChange={(e) => setField('duration_hours', e.target.value)}
                className="w-full px-3 py-2 text-sm font-mono bg-white dark:bg-slate-950/60 border border-[#1e4d35]/20 rounded-lg text-[#122018] dark:text-slate-100 focus:outline-none focus:border-[#1e4d35]" />
            </div>
            <div>
              <label className="block text-[11px] font-mono text-[#566b5c] dark:text-slate-400 mb-1">Priority</label>
              <select value={form.priority} onChange={(e) => setField('priority', e.target.value)}
                className="w-full px-3 py-2 text-sm font-mono bg-white dark:bg-slate-950/60 border border-[#1e4d35]/20 rounded-lg text-[#122018] dark:text-slate-200 focus:outline-none focus:border-[#1e4d35]">
                <option value="LOW">LOW</option>
                <option value="MEDIUM">MEDIUM</option>
                <option value="HIGH">HIGH</option>
                <option value="CRITICAL">CRITICAL</option>
              </select>
            </div>
            <div>
              <label className="block text-[11px] font-mono text-[#566b5c] dark:text-slate-400 mb-1">Planned Start</label>
              <input type="datetime-local" value={form.planned_start} onChange={(e) => setField('planned_start', e.target.value)}
                className="w-full px-3 py-2 text-xs font-mono bg-white dark:bg-slate-950/60 border border-[#1e4d35]/20 rounded-lg text-[#122018] dark:text-slate-200 focus:outline-none focus:border-[#1e4d35]" />
            </div>
          </div>

          <div className="flex gap-3 pt-2 border-t border-[#1e4d35]/20">
            <button type="button" onClick={onClose}
              className="flex-1 px-4 py-2.5 text-xs font-mono text-[#566b5c] hover:text-[#122018] dark:text-slate-400 dark:hover:text-slate-200 border border-[#1e4d35]/20 rounded-xl transition-colors">
              Cancel
            </button>
            <button type="submit" disabled={saving}
              className="flex-1 px-4 py-2.5 text-xs font-mono font-bold bg-[#1e4d35] hover:bg-[#163a26] text-white rounded-xl disabled:opacity-50 transition-colors">
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

  const list = missions;
  const activeCount = missions.filter((mission) => ['ACTIVE', 'IN_PROGRESS'].includes(mission.status)).length;
  const upcomingCount = missions.filter((mission) => ['PLANNED', 'PLANNING', 'BRIEFING'].includes(mission.status)).length;
  const completedCount = missions.filter((mission) => mission.status === 'COMPLETED').length;

  return (
    <NavBar title="Mission Sessions" onBack={() => router.push('/dashboard')}>
      {showCreate && hasMinRole('maintainer') && (
        <CreateMissionModal onClose={() => setShowCreate(false)} onCreated={handleCreated} />
      )}

      <div className="space-y-6">
        {/* Title Header */}
        <div className="flex items-center justify-between flex-wrap gap-4 pt-1">
          <div className="space-y-1">
            <span className="inline-block px-3 py-0.5 rounded-md text-[10px] font-mono font-bold uppercase tracking-widest bg-[#e1eadf] text-[#1e4d35] dark:bg-[#1e4d35]/30 dark:text-emerald-300 border border-[#1e4d35]/30">
              MISSION PLANNING
            </span>
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-[#122018] dark:text-slate-100 font-sans">
              Operational Sessions
            </h1>
            <p className="text-xs text-[#566b5c] dark:text-slate-400 font-mono pt-1">{list.length} active sessions</p>
          </div>
          {hasMinRole('maintainer') && (
            <button
              onClick={() => setShowCreate(true)}
              className="flex items-center gap-2 px-4 py-2.5 text-xs font-mono font-bold bg-[#1e4d35] hover:bg-[#163a26] text-white rounded-xl transition-all shadow-md"
            >
              <Plus className="w-4 h-4" />
              New Mission
            </button>
          )}
        </div>

        {/* 3 Metric Cards Row */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="dashboard-card-shape rounded-2xl p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-mono text-[#566b5c] dark:text-slate-400">Active Sessions</p>
              <p className="text-2xl font-extrabold font-mono text-emerald-600 dark:text-emerald-400 mt-1">{activeCount}</p>
            </div>
            <div className="w-10 h-10 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-600 dark:text-emerald-400">
              <Compass className="w-5 h-5" />
            </div>
          </div>
          <div className="dashboard-card-shape rounded-2xl p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-mono text-[#566b5c] dark:text-slate-400">Upcoming Missions</p>
              <p className="text-2xl font-extrabold font-mono text-[#1e4d35] dark:text-emerald-400 mt-1">{upcomingCount}</p>
            </div>
            <div className="w-10 h-10 rounded-full bg-[#e1eadf] dark:bg-[#1e4d35]/30 border border-[#1e4d35]/30 flex items-center justify-center text-[#1e4d35] dark:text-emerald-400">
              <Calendar className="w-5 h-5" />
            </div>
          </div>
          <div className="dashboard-card-shape rounded-2xl p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-mono text-[#566b5c] dark:text-slate-400">Completed Sessions</p>
              <p className="text-2xl font-extrabold font-mono text-[#566b5c] dark:text-slate-400 mt-1">{completedCount}</p>
            </div>
            <div className="w-10 h-10 rounded-full bg-slate-500/10 border border-slate-500/30 flex items-center justify-center text-[#566b5c] dark:text-slate-400">
              <ShieldCheck className="w-5 h-5" />
            </div>
          </div>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[...Array(3)].map((_, i) => <div key={i} className="h-44 dashboard-card-shape rounded-2xl animate-pulse" />)}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {list.length === 0 ? (
              <p className="col-span-full py-12 text-center text-xs font-mono text-slate-500">No missions found.</p>
            ) : list.map((mission) => (
              <div
                key={mission.id}
                className="dashboard-card-shape rounded-2xl p-6 cursor-pointer transition-all flex flex-col justify-between group"
                onClick={() => router.push(`/missions/${mission.id}`)}
              >
                <div>
                  <div className="flex items-start justify-between gap-3 mb-4">
                    <div className="min-w-0">
                      <p className="font-mono font-bold text-lg text-[#122018] dark:text-slate-100 truncate">{mission.mission_code}</p>
                      <p className="text-xs text-[#566b5c] dark:text-slate-300 mt-0.5 truncate font-semibold">{mission.name}</p>
                    </div>
                    <StatusBadge status={mission.status} />
                  </div>
                  <div className="grid grid-cols-2 gap-3 text-xs font-mono bg-[#e1eadf]/40 dark:bg-slate-950/60 p-3 rounded-xl border border-[#1e4d35]/20">
                    <div>
                      <p className="text-[#566b5c] dark:text-slate-400 font-bold">Duration</p>
                      <p className="text-[#122018] dark:text-slate-100 font-bold">{mission.duration_hours} h</p>
                    </div>
                    <div>
                      <p className="text-[#566b5c] dark:text-slate-400 font-bold">Priority</p>
                      <p className="text-[#122018] dark:text-slate-100 font-bold">{mission.priority}</p>
                    </div>
                  </div>
                </div>
                <p className="mt-4 text-xs text-[#1e4d35] dark:text-emerald-400 font-mono font-bold group-hover:underline transition-colors">View Mission Details →</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </NavBar>
  );
}
