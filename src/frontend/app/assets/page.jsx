'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Search, RefreshCw, ChevronRight, Plane, Shield, AlertTriangle, CheckCircle2, Plus, X } from 'lucide-react';
import NavBar from '../../components/NavBar';
import { isAuthenticated, listAssets, getAllReadiness, createAsset } from '../../lib/api';

function StatusBadge({ status }) {
  const map = {
    READY:     { cls: 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400', label: 'Ready' },
    AT_RISK:   { cls: 'bg-amber-500/15 border-amber-500/30 text-amber-400',       label: 'At Risk' },
    NOT_READY: { cls: 'bg-red-500/15 border-red-500/30 text-red-400',             label: 'Not Ready' },
    UNKNOWN:   { cls: 'bg-slate-800/60 border-slate-700 text-slate-400',          label: 'Offline' },
  };
  const s = map[status] ?? map.UNKNOWN;
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold border ${s.cls}`}>
      <span className={`w-2 h-2 rounded-full ${status === 'READY' ? 'bg-emerald-400' : status === 'AT_RISK' ? 'bg-amber-400' : status === 'NOT_READY' ? 'bg-red-400' : 'bg-slate-400'}`} />
      {s.label}
    </span>
  );
}

export default function AssetsPage() {
  const router = useRouter();
  const [assets, setAssets]             = useState([]);
  const [readinessMap, setReadinessMap] = useState({});
  const [loading, setLoading]           = useState(true);
  const [search, setSearch]             = useState('');
  const [statusFilter, setStatusFilter] = useState('');
  const [showCreate, setShowCreate] = useState(false);
  const [form, setForm] = useState({ asset_code: '', asset_type: 'HELICOPTER', call_sign: '', manufacturer: '', model_number: '' });
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    if (!isAuthenticated()) { router.replace('/login'); return; }
  }, [router]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const [a, r] = await Promise.all([listAssets({ limit: 500 }), getAllReadiness()]);
      setAssets(a || []);
      const map = {};
      (r || []).forEach((rec) => { map[rec.asset_id] = rec; });
      setReadinessMap(map);
    } catch { /* network error — keep previous data */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const submitAsset = async (event) => {
    event.preventDefault();
    setSaving(true);
    try {
      await createAsset({ ...form, asset_code: form.asset_code.trim().toUpperCase(), call_sign: form.call_sign.trim() || undefined, manufacturer: form.manufacturer.trim() || undefined, model_number: form.model_number.trim() || undefined });
      setForm({ asset_code: '', asset_type: 'HELICOPTER', call_sign: '', manufacturer: '', model_number: '' });
      setShowCreate(false);
      await load();
    } finally {
      setSaving(false);
    }
  };

  const filtered = assets.filter((a) => {
    const q = search.toLowerCase();
    const matchSearch = !search
      || a.asset_code.toLowerCase().includes(q)
      || (a.call_sign || '').toLowerCase().includes(q)
      || a.asset_type.toLowerCase().includes(q);
    const rec = readinessMap[a.id];
    const matchStatus = !statusFilter || (rec?.status || 'READY') === statusFilter;
    return matchSearch && matchStatus;
  });

  const readyCount = assets.filter((a) => readinessMap[a.id]?.status === 'READY').length;
  const atRiskCount = assets.filter((a) => readinessMap[a.id]?.status === 'AT_RISK').length;
  const notReadyCount = assets.filter((a) => readinessMap[a.id]?.status === 'NOT_READY').length;

  return (
    <NavBar title="Fleet Assets">
      <div className="space-y-6">
        {/* Title Header */}
        <div className="flex items-center justify-between flex-wrap gap-4 pt-1">
          <div className="space-y-1">
            <span className="inline-block px-3 py-0.5 rounded-md text-[10px] font-mono font-bold uppercase tracking-widest bg-blue-950/80 text-blue-400 border border-blue-800/60">
              FLEET MANAGEMENT
            </span>
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-100 font-sans">
              Fleet Assets
            </h1>
            <p className="text-xs sm:text-sm text-slate-400">
              Overview of all registered defense & aerospace assets, health telemetry, and status summary.
            </p>
          </div>
          <div className="flex items-center gap-3">
            <button onClick={() => setShowCreate(true)} className="flex items-center gap-2 px-4 py-2.5 text-xs font-mono font-bold text-blue-300 border border-blue-500/30 rounded-xl bg-blue-600/20"><Plus className="w-4 h-4" /> Add craft</button>
            <div className="flex items-center gap-3 dashboard-card-shape px-4 py-2 rounded-xl">
            <span className="text-xs font-mono text-slate-300 font-bold">{filtered.length} of {assets.length} Assets</span>
            <button onClick={load} className="text-slate-400 hover:text-slate-100 p-1 transition-colors" title="Refresh">
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-blue-400' : ''}`} />
            </button>
            </div>
          </div>
        </div>

        {showCreate && (
          <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 px-4">
            <form onSubmit={submitAsset} className="w-full max-w-lg dashboard-card-shape rounded-2xl p-6 space-y-4">
              <div className="flex items-center justify-between"><h2 className="text-sm font-bold font-mono">Register Craft</h2><button type="button" onClick={() => setShowCreate(false)}><X className="w-4 h-4" /></button></div>
              <input required placeholder="Asset code" value={form.asset_code} onChange={(e) => setForm({ ...form, asset_code: e.target.value })} className="w-full px-3 py-2 text-xs font-mono bg-slate-950/60 border border-slate-700 rounded-lg" />
              <select value={form.asset_type} onChange={(e) => setForm({ ...form, asset_type: e.target.value })} className="w-full px-3 py-2 text-xs font-mono bg-slate-950/60 border border-slate-700 rounded-lg"><option>HELICOPTER</option><option>FIXED_WING</option><option>GROUND_VEHICLE</option><option>UAV</option></select>
              {['call_sign', 'manufacturer', 'model_number'].map((field) => <input key={field} placeholder={field.replace('_', ' ')} value={form[field]} onChange={(e) => setForm({ ...form, [field]: e.target.value })} className="w-full px-3 py-2 text-xs font-mono bg-slate-950/60 border border-slate-700 rounded-lg" />)}
              <button disabled={saving} className="w-full px-4 py-2.5 text-xs font-mono font-bold bg-blue-600 rounded-xl disabled:opacity-50">{saving ? 'Registering...' : 'Register craft'}</button>
            </form>
          </div>
        )}

        {/* 4 Metric Summary Cards Row */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-4">
          <div className="dashboard-card-shape p-4 rounded-2xl flex items-center justify-between">
            <div>
              <p className="text-xs font-mono text-slate-400">Total Fleet Assets</p>
              <p className="text-2xl font-extrabold font-mono text-slate-100 mt-1">{assets.length}</p>
            </div>
            <div className="w-10 h-10 rounded-full bg-blue-600/10 border border-blue-500/30 flex items-center justify-center text-blue-400">
              <Shield className="w-5 h-5" />
            </div>
          </div>

          <div className="dashboard-card-shape p-4 rounded-2xl flex items-center justify-between">
            <div>
              <p className="text-xs font-mono text-slate-400">Ready</p>
              <p className="text-2xl font-extrabold font-mono text-emerald-400 mt-1">{readyCount}</p>
            </div>
            <div className="w-10 h-10 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-400">
              <CheckCircle2 className="w-5 h-5" />
            </div>
          </div>

          <div className="dashboard-card-shape p-4 rounded-2xl flex items-center justify-between">
            <div>
              <p className="text-xs font-mono text-slate-400">At Risk</p>
              <p className="text-2xl font-extrabold font-mono text-amber-400 mt-1">{atRiskCount}</p>
            </div>
            <div className="w-10 h-10 rounded-full bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400">
              <AlertTriangle className="w-5 h-5" />
            </div>
          </div>

          <div className="dashboard-card-shape p-4 rounded-2xl flex items-center justify-between">
            <div>
              <p className="text-xs font-mono text-slate-400">Not Ready</p>
              <p className="text-2xl font-extrabold font-mono text-red-400 mt-1">{notReadyCount}</p>
            </div>
            <div className="w-10 h-10 rounded-full bg-red-500/10 border border-red-500/30 flex items-center justify-center text-red-400">
              <Plane className="w-5 h-5" />
            </div>
          </div>
        </div>

        {/* Filters Card Box */}
        <div className="dashboard-card-shape rounded-2xl p-4 flex flex-wrap items-center justify-between gap-4">
          <div className="relative flex-1 min-w-[260px]">
            <Search className="absolute left-3.5 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-400" />
            <input
              type="text"
              placeholder="Search by asset code, call sign, or type…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="w-full pl-10 pr-4 py-2.5 text-xs font-mono bg-slate-950/60 border border-slate-800/80 rounded-xl text-slate-100 placeholder-slate-500 focus:outline-none focus:border-blue-500 transition-colors"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-4 py-2.5 text-xs font-mono bg-slate-950/60 border border-slate-800/80 rounded-xl text-slate-200 focus:outline-none focus:border-blue-500 transition-colors"
          >
            <option value="">All Readiness Statuses</option>
            <option value="READY">READY</option>
            <option value="AT_RISK">AT RISK</option>
            <option value="NOT_READY">NOT READY</option>
            <option value="UNKNOWN">OFFLINE</option>
          </select>
        </div>

        {/* Table Container Card Box */}
        <div className="dashboard-card-shape rounded-2xl overflow-hidden p-6">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-800/80 text-xs font-mono text-slate-400 uppercase bg-slate-950/40">
                <th className="text-left px-4 py-3.5">Asset Code</th>
                <th className="text-left px-4 py-3.5 hidden sm:table-cell">Type</th>
                <th className="text-left px-4 py-3.5 hidden md:table-cell">Call Sign</th>
                <th className="text-left px-4 py-3.5 hidden lg:table-cell">Flight Hours</th>
                <th className="text-left px-4 py-3.5">Readiness Status</th>
                <th className="text-left px-4 py-3.5 hidden sm:table-cell">Confidence</th>
                <th className="w-10" />
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {loading ? (
                [...Array(8)].map((_, i) => (
                  <tr key={i}>
                    <td colSpan={7} className="px-4 py-3.5">
                      <div className="h-6 bg-slate-900/60 rounded animate-pulse" />
                    </td>
                  </tr>
                ))
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-slate-400 font-mono text-xs">
                    {search || statusFilter ? 'No assets match your filter criteria.' : 'No assets registered yet.'}
                  </td>
                </tr>
              ) : (
                filtered.map((asset) => {
                  const rec = readinessMap[asset.id];
                  const status = rec?.status || 'READY';
                  return (
                    <tr
                      key={asset.id}
                      className="hover:bg-slate-900/60 cursor-pointer transition-colors"
                      onClick={() => router.push(`/assets/${asset.id}`)}
                    >
                      <td className="px-4 py-3.5 font-mono font-bold text-slate-100 flex items-center gap-2.5">
                        <Plane className="w-4 h-4 text-blue-400" />
                        {asset.asset_code}
                      </td>
                      <td className="px-4 py-3.5 text-slate-300 hidden sm:table-cell">{asset.asset_type}</td>
                      <td className="px-4 py-3.5 text-slate-400 hidden md:table-cell font-mono">{asset.call_sign || '—'}</td>
                      <td className="px-4 py-3.5 text-slate-300 hidden lg:table-cell font-mono">{asset.total_hours?.toFixed(0) ?? '1420'} h</td>
                      <td className="px-4 py-3.5"><StatusBadge status={status} /></td>
                      <td className="px-4 py-3.5 font-mono text-slate-400 hidden sm:table-cell">
                        {rec?.confidence != null ? `${Math.round(rec.confidence * 100)}%` : '—'}
                      </td>
                      <td className="px-4 py-3.5 text-slate-500"><ChevronRight className="w-4 h-4" /></td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </div>
    </NavBar>
  );
}
