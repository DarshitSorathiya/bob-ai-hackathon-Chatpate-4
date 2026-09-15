'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Plus, X, Wrench } from 'lucide-react';
import { isAuthenticated, listWorkOrders, createWorkOrder, getMaintenanceQueue, updateWorkOrder, listAssets } from '../../lib/api';
import NavBar from '../../components/NavBar';

const URGENCY_COLORS = {
  IMMEDIATE: { badge: 'bg-red-500/20 border-red-500/40 text-red-400', bar: 'bg-red-500' },
  URGENT:    { badge: 'bg-amber-500/20 border-amber-500/40 text-amber-400', bar: 'bg-amber-500' },
  SCHEDULED: { badge: 'bg-blue-500/20 border-blue-500/40 text-blue-400', bar: 'bg-blue-500' },
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
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4">
      <div className="w-full max-w-xl bg-[#0d1117] border border-slate-700 rounded-2xl shadow-2xl overflow-hidden">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800">
          <div className="flex items-center gap-2">
            <Wrench className="w-4 h-4 text-amber-400" />
            <h2 className="text-sm font-bold font-mono text-slate-100">New Work Order</h2>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-200 transition-colors"><X className="w-4 h-4" /></button>
        </div>

        <form onSubmit={handleSubmit} className="px-6 py-5 space-y-4 max-h-[80vh] overflow-y-auto">
          {error && (
            <div className="bg-red-950/40 border border-red-700/40 text-red-400 text-xs font-mono px-4 py-2 rounded-lg">{error}</div>
          )}

          <div>
            <label className="block text-[11px] font-mono text-slate-400 mb-1">Title *</label>
            <input required value={form.title} onChange={(e) => setField('title', e.target.value)}
              className="w-full px-3 py-2 text-sm font-mono bg-slate-900/60 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500"
              placeholder="Replace engine filter" />
          </div>

          <div>
            <label className="block text-[11px] font-mono text-slate-400 mb-1">Description</label>
            <textarea rows={2} value={form.description} onChange={(e) => setField('description', e.target.value)}
              className="w-full px-3 py-2 text-sm font-mono bg-slate-900/60 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500 resize-none"
              placeholder="Optional details" />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[11px] font-mono text-slate-400 mb-1">Asset</label>
              <select value={form.asset_id} onChange={(e) => setField('asset_id', e.target.value)}
                className="w-full px-3 py-2 text-sm font-mono bg-slate-900/60 border border-slate-700 rounded-lg text-slate-300 focus:outline-none focus:border-blue-500">
                <option value="">— select asset —</option>
                {assets.map((a) => <option key={a.id} value={a.id}>{a.asset_code} — {a.name}</option>)}
              </select>
            </div>
            <div>
              <label className="block text-[11px] font-mono text-slate-400 mb-1">Urgency Level</label>
              <select value={form.urgency_level} onChange={(e) => setField('urgency_level', e.target.value)}
                className="w-full px-3 py-2 text-sm font-mono bg-slate-900/60 border border-slate-700 rounded-lg text-slate-300 focus:outline-none focus:border-blue-500">
                {['IMMEDIATE', 'URGENT', 'SCHEDULED', 'ROUTINE', 'DEFERRED'].map((u) => <option key={u}>{u}</option>)}
              </select>
            </div>
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-[11px] font-mono text-slate-400 mb-1">Est. Hours</label>
              <input type="number" min="0" step="0.5" value={form.estimated_hours} onChange={(e) => setField('estimated_hours', e.target.value)}
                className="w-full px-3 py-2 text-sm font-mono bg-slate-900/60 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500"
                placeholder="2.0" />
            </div>
            <div className="flex items-center gap-2 mt-5">
              <input type="checkbox" id="blocking" checked={form.is_blocking} onChange={(e) => setField('is_blocking', e.target.checked)}
                className="rounded border-slate-600 bg-slate-900" />
              <label htmlFor="blocking" className="text-xs font-mono text-slate-300">Blocks mission assignment</label>
            </div>
          </div>

          <div className="flex gap-3 pt-2 border-t border-slate-800">
            <button type="button" onClick={onClose}
              className="flex-1 px-4 py-2.5 text-sm font-mono text-slate-400 hover:text-slate-200 border border-slate-700 hover:border-slate-600 rounded-xl transition-colors">
              Cancel
            </button>
            <button type="submit" disabled={saving}
              className="flex-1 px-4 py-2.5 text-sm font-mono font-bold bg-amber-600/20 hover:bg-amber-600/30 border border-amber-500/40 text-amber-300 rounded-xl disabled:opacity-50 transition-colors">
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
  const [tab, setTab] = useState('queue');
  const [queue, setQueue] = useState(null);
  const [workOrders, setWorkOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreate, setShowCreate] = useState(false);

  useEffect(() => {
    if (!isAuthenticated()) { router.replace('/login'); return; }
  }, [router]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [q, w] = await Promise.all([
        getMaintenanceQueue(),
        listWorkOrders({ limit: 100 }),
      ]);
      setQueue(q);
      setWorkOrders(w || []);
    } catch { /* ignore */ }
    finally { setLoading(false); }
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

  return (
    <div className="min-h-screen bg-[#070a12] text-slate-100 font-sans">
      <NavBar title="Maintenance" onBack={() => router.push('/dashboard')} />

      {showCreate && (
        <CreateWorkOrderModal onClose={() => setShowCreate(false)} onCreated={handleCreated} />
      )}

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-5">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div>
            <h1 className="text-xl font-bold">Maintenance</h1>
            {queue && (
              <div className="flex gap-3 text-xs font-mono mt-0.5">
                <span className="text-red-400">{queue.total_immediate} IMMEDIATE</span>
                <span className="text-amber-400">{queue.total_urgent} URGENT</span>
                <span className="text-blue-400">{queue.total_scheduled} SCHEDULED</span>
              </div>
            )}
          </div>
          <button
            onClick={() => setShowCreate(true)}
            className="flex items-center gap-2 px-3 py-2 text-sm font-mono font-semibold bg-amber-500/10 hover:bg-amber-500/20 border border-amber-500/30 hover:border-amber-400/50 text-amber-400 rounded-xl transition-colors"
          >
            <Plus className="w-4 h-4" />
            New Work Order
          </button>
        </div>

        {/* Tab switcher */}
        <div className="flex gap-2 border-b border-slate-800">
          {[{ id: 'queue', label: 'Priority Queue' }, { id: 'work-orders', label: 'Work Orders' }].map(({ id, label }) => (
            <button
              key={id}
              onClick={() => setTab(id)}
              className={`px-4 py-2 text-sm font-mono border-b-2 transition-colors ${tab === id ? 'border-blue-400 text-blue-400' : 'border-transparent text-slate-400 hover:text-slate-200'}`}
            >
              {label}
            </button>
          ))}
        </div>

        {loading ? (
          <div className="space-y-3">{[...Array(5)].map((_, i) => <div key={i} className="h-20 bg-slate-800/60 rounded-xl animate-pulse" />)}</div>
        ) : tab === 'queue' ? (
          queue?.items?.length === 0 ? (
            <p className="text-slate-500 font-mono text-sm py-8 text-center">No open maintenance items.</p>
          ) : (
            <div className="space-y-3">
              {(queue?.items || []).map((item) => (
                <div key={item.item_id} className="bg-slate-900/40 border border-slate-800 rounded-xl p-4">
                  <div className="flex items-start justify-between gap-3 flex-wrap">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <UrgencyBadge level={item.urgency_level} />
                        <span className="font-mono font-semibold text-slate-100">{item.asset_code}</span>
                        <span className="text-slate-500 font-mono text-xs">/ {item.component_code}</span>
                        {item.blocks_mission && (
                          <span className="text-[10px] font-mono bg-red-500/10 border border-red-500/30 text-red-400 px-2 py-0.5 rounded">BLOCKS MISSION</span>
                        )}
                      </div>
                      <p className="text-sm text-slate-300">{item.description}</p>
                      <p className="text-xs text-slate-500 font-mono mt-1">{item.recommended_action}</p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="text-xs text-slate-500 font-mono">Priority Score</p>
                      <p className="text-xl font-bold font-mono tabular-nums" style={{color: item.priority_score > 0.7 ? '#f87171' : item.priority_score > 0.5 ? '#fbbf24' : '#94a3b8'}}>
                        {(item.priority_score * 100).toFixed(0)}
                      </p>
                    </div>
                  </div>
                  <div className="mt-3 pt-3 border-t border-slate-800/60 grid grid-cols-3 sm:grid-cols-7 gap-2 text-[10px] font-mono">
                    {Object.entries(item.score_breakdown || {}).filter(([k]) => k !== 'total').map(([key, val]) => (
                      <div key={key} className="text-center">
                        <p className="text-slate-600 truncate">{key.replace(/_score$/, '').replace(/_/g, ' ')}</p>
                        <p className="text-slate-300">{(val * 100).toFixed(0)}</p>
                      </div>
                    ))}
                  </div>
                </div>
              ))}
            </div>
          )
        ) : (
          workOrders.length === 0 ? (
            <div className="bg-slate-900/40 border border-dashed border-slate-700 rounded-xl p-12 text-center">
              <p className="text-slate-500 font-mono text-sm">No work orders found.</p>
              <button onClick={() => setShowCreate(true)} className="mt-3 text-amber-400 hover:text-amber-300 text-xs font-mono underline">
                Create the first work order
              </button>
            </div>
          ) : (
            <div className="bg-slate-900/40 border border-slate-800 rounded-xl overflow-hidden">
              <table className="w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-800 text-[11px] font-mono text-slate-500 uppercase">
                    <th className="text-left px-4 py-3">Title</th>
                    <th className="text-left px-4 py-3 hidden sm:table-cell">Status</th>
                    <th className="text-left px-4 py-3 hidden md:table-cell">Urgency</th>
                    <th className="text-left px-4 py-3 hidden lg:table-cell">Blocking</th>
                    <th className="px-4 py-3" />
                  </tr>
                </thead>
                <tbody>
                  {workOrders.map((wo) => (
                    <tr key={wo.id} className="border-b border-slate-800/50 hover:bg-slate-800/30 transition-colors">
                      <td className="px-4 py-3">
                        <p className="font-semibold text-slate-100 truncate max-w-xs">{wo.title}</p>
                        <p className="text-[11px] text-slate-500 font-mono">{wo.asset_id?.slice(0, 8)}…</p>
                      </td>
                      <td className="px-4 py-3 hidden sm:table-cell">
                        <span className={`text-[10px] font-mono font-bold uppercase ${wo.status === 'OPEN' ? 'text-amber-400' : wo.status === 'COMPLETED' ? 'text-emerald-400' : 'text-slate-400'}`}>{wo.status}</span>
                      </td>
                      <td className="px-4 py-3 hidden md:table-cell"><UrgencyBadge level={wo.urgency_level} /></td>
                      <td className="px-4 py-3 hidden lg:table-cell">
                        {wo.is_blocking ? <span className="text-red-400 text-xs font-mono">YES</span> : <span className="text-slate-600 text-xs font-mono">No</span>}
                      </td>
                      <td className="px-4 py-3">
                        {wo.status === 'OPEN' && (
                          <button
                            onClick={() => handleClose(wo.id)}
                            className="text-[11px] font-mono text-emerald-400 hover:text-emerald-300 px-2 py-1 rounded border border-emerald-500/20 hover:border-emerald-400/40 transition-colors"
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
          )
        )}
      </main>
    </div>
  );
}
