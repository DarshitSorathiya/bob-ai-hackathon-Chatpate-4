'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Search, RefreshCw, ChevronRight, Plane } from 'lucide-react';
import NavBar from '../../components/NavBar';
import { isAuthenticated, listAssets, getAllReadiness } from '../../lib/api';

function StatusBadge({ status }) {
  const map = {
    READY:     { cls: 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400', label: 'Ready' },
    AT_RISK:   { cls: 'bg-red-500/20 border-red-500/40 text-red-400',             label: 'At Risk' },
    NOT_READY: { cls: 'bg-amber-500/20 border-amber-500/40 text-amber-400',       label: 'Not Ready' },
    UNKNOWN:   { cls: 'bg-slate-800/60 border-slate-700 text-slate-400',          label: 'Offline' },
  };
  const s = map[status] ?? map.UNKNOWN;
  return (
    <span className={`inline-flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-mono font-bold border ${s.cls}`}>
      <span className={`w-2 h-2 rounded-full ${status === 'READY' ? 'bg-emerald-400' : status === 'AT_RISK' ? 'bg-red-400' : status === 'NOT_READY' ? 'bg-amber-400' : 'bg-slate-400'}`} />
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

  const filtered = assets.filter((a) => {
    const q = search.toLowerCase();
    const matchSearch = !search
      || a.asset_code.toLowerCase().includes(q)
      || (a.call_sign || '').toLowerCase().includes(q)
      || a.asset_type.toLowerCase().includes(q);
    const rec = readinessMap[a.id];
    const matchStatus = !statusFilter || (rec?.status || 'UNKNOWN') === statusFilter;
    return matchSearch && matchStatus;
  });

  return (
    <NavBar title="Fleet Assets">
      <div className="space-y-6">
        {/* Title Header */}
        <div className="flex items-center justify-between flex-wrap gap-4 pt-2">
          <div className="space-y-1">
            <span className="inline-block px-3 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-widest bg-blue-950/80 text-blue-400 border border-blue-800/60 mb-1">
              FLEET MANAGEMENT
            </span>
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-100 font-sans">
              Fleet Assets
            </h1>
          </div>
          <div className="flex items-center gap-3 bg-[#0a0f1d]/80 border-[3px] border-white px-4 py-2 rounded-xl backdrop-blur-xl">
            <span className="text-xs font-mono text-slate-300 font-bold">{filtered.length} of {assets.length} Assets</span>
            <button onClick={load} className="text-slate-400 hover:text-slate-100 p-1" title="Refresh">
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin text-blue-400' : ''}`} />
            </button>
          </div>
        </div>

        {/* Filters Card Box */}
        <div className="bg-[#0a0f1d]/80 border-[3px] border-white rounded-2xl p-5 backdrop-blur-xl shadow-xl flex flex-wrap items-center justify-between gap-4">
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
        <div className="bg-[#0a0f1d]/80 border-[3px] border-white rounded-2xl backdrop-blur-xl shadow-xl overflow-hidden p-6">
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
                  const status = rec?.status || 'UNKNOWN';
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
                      <td className="px-4 py-3.5 text-slate-300 hidden lg:table-cell font-mono">{asset.total_hours?.toFixed(0) ?? '—'} h</td>
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
