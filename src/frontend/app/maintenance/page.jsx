'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Plus, X, Wrench, AlertTriangle, CheckCircle2, Clock } from 'lucide-react';
import { isAuthenticated, listWorkOrders, createWorkOrder, getMaintenanceQueue, updateWorkOrder, listAssets } from '../../lib/api';
import NavBar from '../../components/NavBar';

const URGENCY_COLORS = {
  IMMEDIATE: { badge: 'bg-red-500/15 border-red-500/30 text-red-400', bar: 'bg-red-500' },
  URGENT:    { badge: 'bg-amber-500/15 border-amber-500/30 text-amber-400', bar: 'bg-amber-500' },
  SCHEDULED: { badge: 'bg-[#e1eadf] border-[#1e4d35]/30 text-[#1e4d35] dark:bg-[#1e4d35]/30 dark:text-emerald-300', bar: 'bg-[#1e4d35]' },
  ROUTINE:   { badge: 'bg-slate-600/30 border-slate-600 text-slate-400', bar: 'bg-slate-500' },
  DEFERRED:  { badge: 'bg-slate-700/30 border-slate-700 text-slate-500', bar: 'bg-slate-600' },
};

function UrgencyBadge({ level }) {
  const c = URGENCY_COLORS[level] || URGENCY_COLORS.DEFERRED;
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold border ${c.badge}`}>
      {level}
    </span>
  );
}

function CreateWorkOrderModal({ onClose, onCreated }) {
  const [form, setForm] = useState({
    title: '',
    description: '',
    asset_id: '',
    component_id: '',
    urgency_level: 'SCHEDULED',
    is_blocking: false,
    estimated_hours: '',
  });
  const [assets, setAssets] = useState([]);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');

  useEffect(() => {
    listAssets({ limit: 100 }).then((data) => setAssets(data || [])).catch(() => {});
  }, []);

  const setField = (k, v) => setForm((f) => ({ ...f, [k]: v }));

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setSaving(true);
    try {
      const payload = {
        title: form.title.trim(),
        description: form.description.trim() || undefined,
        asset_id: form.asset_id || undefined,
        component_id: form.component_id.trim() || undefined,
        urgency_level: form.urgency_level,
        is_blocking: form.is_blocking,
        estimated_hours: parseFloat(form.estimated_hours) || undefined,
      };
      const wo = await createWorkOrder(payload);
      onCreated(wo);
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
          <div className="flex items-center gap-2">
            <Wrench className="w-5 h-5 text-amber-500" />
            <h2 className="text-sm font-bold font-mono text-[#122018] dark:text-slate-100">New Work Order</h2>
          </div>
          <button onClick={onClose} className="text-slate-400 hover:text-slate-600 transition-colors"><X className="w-4 h-4" /></button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4 max-h-[80vh] overflow-y-auto">
          {error && (
            <div className="bg-red-950/40 border border-red-700/40 text-red-400 text-xs font-mono px-4 py-2 rounded-lg">{error}</div>
          )}

          <div>
            <label className="block text-[11px] font-mono text-[#566b5c] dark:text-slate-400 mb-1">Title *</label>
            <input required value={form.title} onChange={(e) => setField('title', e.target.value)}
              className="w-full px-3 py-2 text-sm font-mono bg-white dark:bg-slate-950/60 border border-[#1e4d35]/20 rounded-lg text-[#122018] dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:border-[#1e4d35]"
              placeholder="e.g., Turbofan Hydraulic Line Replacement" />
          </div>

          <div>
            <label className="block text-[11px] font-mono text-[#566b5c] dark:text-slate-400 mb-1">Description</label>
            <textarea rows={2} value={form.description} onChange={(e) => setField('description', e.target.value)}
              className="w-full px-3 py-2 text-sm font-mono bg-white dark:bg-slate-950/60 border border-[#1e4d35]/20 rounded-lg text-[#122018] dark:text-slate-100 placeholder-slate-400 focus:outline-none focus:border-[#1e4d35] resize-none"
              placeholder="Optional maintenance instructions..." />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[11px] font-mono text-[#566b5c] dark:text-slate-400 mb-1">Asset</label>
              <select value={form.asset_id} onChange={(e) => setField('asset_id', e.target.value)}
                className="w-full px-3 py-2 text-sm font-mono bg-white dark:bg-slate-950/60 border border-[#1e4d35]/20 rounded-lg text-[#122018] dark:text-slate-200 focus:outline-none focus:border-[#1e4d35]">
                <option value="">Unassigned</option>
                {assets.map((a) => (
                  <option key={a.id} value={a.id}>{a.asset_code} ({a.asset_type})</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-[11px] font-mono text-[#566b5c] dark:text-slate-400 mb-1">Urgency</label>
              <select value={form.urgency_level} onChange={(e) => setField('urgency_level', e.target.value)}
                className="w-full px-3 py-2 text-sm font-mono bg-white dark:bg-slate-950/60 border border-[#1e4d35]/20 rounded-lg text-[#122018] dark:text-slate-200 focus:outline-none focus:border-[#1e4d35]">
                <option value="IMMEDIATE">IMMEDIATE</option>
                <option value="URGENT">URGENT</option>
                <option value="SCHEDULED">SCHEDULED</option>
                <option value="ROUTINE">ROUTINE</option>
                <option value="DEFERRED">DEFERRED</option>
              </select>
            </div>
          </div>

          <div className="flex items-center justify-between pt-2">
            <label className="flex items-center gap-2 cursor-pointer text-xs font-mono text-[#122018] dark:text-slate-300">
              <input type="checkbox" checked={form.is_blocking} onChange={(e) => setField('is_blocking', e.target.checked)} className="rounded border-[#1e4d35]/40 text-[#1e4d35] focus:ring-0" />
              Blocks Mission Readiness
            </label>
            <button type="submit" disabled={saving} className="px-5 py-2 bg-[#1e4d35] hover:bg-[#163a26] text-white font-mono font-bold text-xs rounded-xl disabled:opacity-50">
              {saving ? 'Creating…' : 'Create Work Order'}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

export default function MaintenancePage() {
  const router = useRouter();
  const [queue, setQueue]           = useState(null);
  const [workOrders, setWorkOrders] = useState([]);
  const [loading, setLoading]       = useState(true);
  const [tab, setTab]               = useState('queue');
  const [showCreate, setShowCreate] = useState(false);

  useEffect(() => {
    if (!isAuthenticated()) { router.replace('/login'); return; }
  }, [router]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [q, wo] = await Promise.allSettled([getMaintenanceQueue(), listWorkOrders({ limit: 100 })]);
      if (q.status === 'fulfilled')  setQueue(q.value);
      if (wo.status === 'fulfilled') setWorkOrders(wo.value || []);
    } finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleClose = async (woId) => {
    await updateWorkOrder(woId, { status: 'COMPLETED' });
    await load();
  };

  const handleCreated = () => {
    setShowCreate(false);
    load();
  };

  const items = queue?.items || [];

  return (
    <NavBar title="Fleet Maintenance" onBack={() => router.push('/dashboard')}>
      {showCreate && (
        <CreateWorkOrderModal onClose={() => setShowCreate(false)} onCreated={handleCreated} />
      )}

      <div className="space-y-6">
        {/* Title Header */}
        <div className="flex items-center justify-between flex-wrap gap-4 pt-1">
          <div className="space-y-1">
            <span className="inline-block px-3 py-0.5 rounded-md text-[10px] font-mono font-bold uppercase tracking-widest bg-[#e1eadf] text-[#1e4d35] dark:bg-[#1e4d35]/30 dark:text-emerald-300 border border-[#1e4d35]/30">
              MAINTENANCE QUEUE
            </span>
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-[#122018] dark:text-slate-100 font-sans">
              Maintenance Management
            </h1>
            <div className="flex gap-4 text-xs font-mono pt-1">
              <span className="text-red-500 font-bold">{queue?.total_immediate ?? 0} IMMEDIATE</span>
              <span className="text-amber-500 font-bold">{queue?.total_urgent ?? 0} URGENT</span>
              <span className="text-[#1e4d35] dark:text-emerald-400 font-bold">{queue?.total_scheduled ?? 0} SCHEDULED</span>
            </div>
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-4 py-2.5 text-xs font-mono font-bold bg-[#1e4d35] hover:bg-[#163a26] text-white rounded-xl transition-all shadow-md"
          >
            <Plus className="w-4 h-4" />
            New Work Order
          </button>
        </div>

        {/* Tab Switcher Box */}
        <div className="flex gap-3 dashboard-card-shape rounded-2xl p-2 w-fit">
          {[{ id: 'queue', label: 'Priority Queue' }, { id: 'work-orders', label: 'Work Orders' }].map(({ id, label }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`px-5 py-2.5 text-xs font-mono font-bold rounded-xl transition-all ${tab === id ? 'bg-[#1e4d35] border border-[#1e4d35] text-white shadow-md' : 'text-[#566b5c] hover:text-[#122018] dark:text-slate-400 dark:hover:text-slate-100'}`}
            >
              {label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="space-y-4">{[...Array(3)].map((_, i) => <div key={i} className="h-24 dashboard-card-shape rounded-2xl animate-pulse" />)}</div>
        ) : tab === 'queue' ? (
          <div className="space-y-4">
            {items.length === 0 ? (
              <p className="py-12 text-center text-xs font-mono text-slate-500">No maintenance queue items found.</p>
            ) : items.map((item) => (
              <div key={item.item_id} className="dashboard-card-shape rounded-2xl p-6">
                <div className="flex items-start justify-between gap-4 flex-wrap">
                  <div className="flex-1 min-w-0 space-y-2">
                    <div className="flex items-center gap-2.5 flex-wrap">
                      <UrgencyBadge level={item.urgency_level} />
                      <span className="font-mono font-bold text-base text-slate-100">{item.asset_code}</span>
                      <span className="text-slate-400 font-mono text-xs">/ {item.component_code}</span>
                      {item.blocks_mission && (
                        <span className="text-[10px] font-mono bg-red-500/10 border border-red-500/30 text-red-400 px-2.5 py-0.5 rounded font-bold">BLOCKS MISSION</span>
                      )}
                    </div>
                    <p className="text-sm text-slate-200">{item.description}</p>
                    <p className="text-xs text-slate-400 font-mono">{item.recommended_action}</p>
                  </div>
                  <div className="text-right shrink-0 bg-slate-950/60 p-3 rounded-xl border border-slate-800/80">
                    <p className="text-xs text-slate-400 font-mono">Priority Score</p>
                    <p className="text-2xl font-black font-mono tabular-nums mt-0.5" style={{color: item.priority_score > 0.7 ? '#f87171' : item.priority_score > 0.5 ? '#fbbf24' : '#94a3b8'}}>
                      {(item.priority_score * 100).toFixed(0)}
                    </p>
                  </div>
                </div>
              </div>
            ))}
          </div>
        ) : (
          <div className="dashboard-card-shape rounded-2xl overflow-hidden p-6">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-slate-800/80 text-xs font-mono text-slate-400 uppercase bg-slate-950/40">
                  <th className="text-left px-4 py-3.5">Title</th>
                  <th className="text-left px-4 py-3.5 hidden sm:table-cell">Status</th>
                  <th className="text-left px-4 py-3.5 hidden md:table-cell">Urgency</th>
                  <th className="text-left px-4 py-3.5 hidden lg:table-cell">Blocking</th>
                  <th className="px-4 py-3.5 text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-800/50">
                {workOrders.map((wo) => (
                  <tr key={wo.id} className="hover:bg-slate-900/60 transition-colors">
                    <td className="px-4 py-3.5">
                      <p className="font-bold text-slate-100 truncate max-w-xs">{wo.title}</p>
                      <p className="text-xs text-slate-400 font-mono">Asset: {wo.asset_id}</p>
                    </td>
                    <td className="px-4 py-3.5 hidden sm:table-cell">
                      <span className={`text-xs font-mono font-bold uppercase ${wo.status === 'OPEN' ? 'text-amber-400' : wo.status === 'COMPLETED' ? 'text-emerald-400' : 'text-slate-400'}`}>{wo.status}</span>
                    </td>
                    <td className="px-4 py-3.5 hidden md:table-cell"><UrgencyBadge level={wo.urgency_level} /></td>
                    <td className="px-4 py-3.5 hidden lg:table-cell">
                      {wo.is_blocking ? <span className="text-red-400 text-xs font-mono font-bold">YES</span> : <span className="text-slate-500 text-xs font-mono">No</span>}
                    </td>
                    <td className="px-4 py-3.5 text-right">
                      {wo.status === 'OPEN' && (
                        <button
                          onClick={() => handleClose(wo.id)}
                          className="text-xs font-mono font-bold text-emerald-400 hover:text-emerald-300 px-3 py-1.5 rounded-lg border border-emerald-500/30 bg-emerald-600/10 transition-colors"
                        >
                          Close
                        </button>
                      )}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </NavBar>
  );
}
