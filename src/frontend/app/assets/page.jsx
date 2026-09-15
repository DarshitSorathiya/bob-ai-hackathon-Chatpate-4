'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Search, RefreshCw, ChevronRight } from 'lucide-react';
import NavBar from '../../components/NavBar';
import { isAuthenticated, listAssets, getAllReadiness } from '../../lib/api';

function StatusBadge({ status }) {
  const map = {
    READY:     { cls: 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400', label: 'READY' },
    AT_RISK:   { cls: 'bg-amber-500/20 border-amber-500/40 text-amber-400',       label: 'AT RISK' },
    NOT_READY: { cls: 'bg-red-500/20 border-red-500/40 text-red-400',             label: 'NOT READY' },
    UNKNOWN:   { cls: 'bg-slate-700/50 border-slate-700 text-slate-400',          label: 'UNKNOWN' },
  };
  const s = map[status] ?? map.UNKNOWN;
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold border ${s.cls}`}>
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
    <div className="min-h-screen bg-[#070a12] text-slate-100 font-sans">
      <NavBar title="Assets" />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-5">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <h1 className="text-xl font-bold">Fleet Assets</h1>
          <div className="flex items-center gap-2">
            <span className="text-xs font-mono text-slate-500">{filtered.length} of {assets.length}</span>
            <button onClick={load} className="text-slate-400 hover:text-slate-200 p-1" title="Refresh">
              <RefreshCw className={`w-4 h-4 ${loading ? 'animate-spin' : ''}`} />
            </button>
          </div>
        </div>

        {/* Filters */}
        <div className="flex flex-wrap gap-3">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-slate-500" />
            <input
              type="text"
              placeholder="Search by code, call sign, or type…"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              className="pl-9 pr-4 py-2 text-sm font-mono bg-slate-900/60 border border-slate-700 rounded-lg text-slate-100 placeholder-slate-600 focus:outline-none focus:border-blue-500 w-72"
            />
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 text-sm font-mono bg-slate-900/60 border border-slate-700 rounded-lg text-slate-300 focus:outline-none focus:border-blue-500"
          >
            <option value="">All Statuses</option>
            <option value="READY">READY</option>
            <option value="AT_RISK">AT RISK</option>
            <option value="NOT_READY">NOT READY</option>
            <option value="UNKNOWN">UNKNOWN</option>
          </select>
        </div>

        {/* Table */}
        <div className="bg-slate-900/40 border border-slate-800 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-slate-800 text-[11px] font-mono text-slate-500 uppercase bg-slate-900/60">
                <th className="text-left px-4 py-3">Asset Code</th>
                <th className="text-left px-4 py-3 hidden sm:table-cell">Type</th>
                <th className="text-left px-4 py-3 hidden md:table-cell">Call Sign</th>
                <th className="text-left px-4 py-3 hidden lg:table-cell">Hours</th>
                <th className="text-left px-4 py-3">Status</th>
                <th className="text-left px-4 py-3 hidden sm:table-cell">Confidence</th>
                <th className="w-10" />
              </tr>
            </thead>
            <tbody>
              {loading ? (
                [...Array(8)].map((_, i) => (
                  <tr key={i} className="border-b border-slate-800/50">
                    <td colSpan={7} className="px-4 py-3">
                      <div className="h-5 bg-slate-800/60 rounded animate-pulse" />
                    </td>
                  </tr>
                ))
              ) : filtered.length === 0 ? (
                <tr>
                  <td colSpan={7} className="px-4 py-12 text-center text-slate-500 font-mono text-sm">
                    {search || statusFilter ? 'No assets match your filters.' : 'No assets registered yet.'}
                  </td>
                </tr>
              ) : (
                filtered.map((asset) => {
                  const rec = readinessMap[asset.id];
                  const status = rec?.status || 'UNKNOWN';
                  return (
                    <tr
                      key={asset.id}
                      className="border-b border-slate-800/50 hover:bg-slate-800/30 cursor-pointer transition-colors"
                      onClick={() => router.push(`/assets/${asset.id}`)}
                    >
                      <td className="px-4 py-3 font-mono font-semibold text-slate-100">{asset.asset_code}</td>
                      <td className="px-4 py-3 text-slate-400 hidden sm:table-cell">{asset.asset_type}</td>
                      <td className="px-4 py-3 text-slate-400 hidden md:table-cell">{asset.call_sign || '—'}</td>
                      <td className="px-4 py-3 text-slate-400 hidden lg:table-cell font-mono">{asset.total_hours?.toFixed(0) ?? '—'} h</td>
                      <td className="px-4 py-3"><StatusBadge status={status} /></td>
                      <td className="px-4 py-3 font-mono text-slate-400 hidden sm:table-cell">
                        {rec?.confidence != null ? `${Math.round(rec.confidence * 100)}%` : '—'}
                      </td>
                      <td className="px-4 py-3 text-slate-600"><ChevronRight className="w-4 h-4" /></td>
                    </tr>
                  );
                })
              )}
            </tbody>
          </table>
        </div>
      </main>
    </div>
  );
}
