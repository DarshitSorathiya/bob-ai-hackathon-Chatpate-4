'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import {
  AlertTriangle, CheckCircle2, XCircle, HelpCircle,
  RefreshCw, Zap, Wrench, TrendingUp, ChevronRight, Loader2,
} from 'lucide-react';
import NavBar from '../../components/NavBar';
import {
  getUser, isAuthenticated,
  getFleetReadinessSummary, listAssets, getAllReadiness,
  listAlerts, getMaintenanceQueue, getHealth,
} from '../../lib/api';

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

function MetricCard({ icon: Icon, label, value, sub, color = 'blue', loading = false }) {
  const colors = {
    blue:  'text-blue-400 bg-blue-500/10',
    green: 'text-emerald-400 bg-emerald-500/10',
    amber: 'text-amber-400 bg-amber-500/10',
    red:   'text-red-400 bg-red-500/10',
    slate: 'text-slate-400 bg-slate-500/10',
  };
  return (
    <div className="bg-slate-900/60 border border-slate-800 rounded-xl p-5 flex items-start gap-4">
      <div className={`w-10 h-10 rounded-lg ${colors[color]} flex items-center justify-center shrink-0`}>
        <Icon className="w-5 h-5" />
      </div>
      <div className="min-w-0">
        <p className="text-[11px] text-slate-400 font-mono uppercase tracking-wider">{label}</p>
        {loading
          ? <div className="h-7 w-16 bg-slate-800 rounded animate-pulse mt-1" />
          : <p className="text-2xl font-bold text-slate-100 tabular-nums">{value}</p>
        }
        {sub && <p className="text-[11px] text-slate-500 font-mono mt-0.5">{sub}</p>}
      </div>
    </div>
  );
}

function AssetRow({ asset, readinessMap, onClick }) {
  const rec = readinessMap[asset.id] || {};
  const status = rec.status || 'UNKNOWN';
  const borderColor = {
    READY: 'border-l-emerald-500', AT_RISK: 'border-l-amber-500',
    NOT_READY: 'border-l-red-500', UNKNOWN: 'border-l-slate-600',
  }[status] || 'border-l-slate-600';
  return (
    <div
      onClick={onClick}
      className={`flex items-center justify-between px-4 py-3 rounded-lg bg-slate-900/40 border border-slate-800 border-l-2 ${borderColor} hover:bg-slate-900/70 cursor-pointer transition-colors`}
    >
      <div className="min-w-0">
        <p className="text-sm font-mono font-semibold text-slate-100">{asset.asset_code}</p>
        <p className="text-[11px] text-slate-500 truncate">{asset.asset_type}{asset.call_sign ? ` — ${asset.call_sign}` : ''}</p>
      </div>
      <div className="flex items-center gap-3 shrink-0">
        {rec.confidence != null && (
          <div className="text-right hidden sm:block">
            <p className="text-[10px] text-slate-500 font-mono">CONF</p>
            <p className="text-sm font-bold text-slate-200">{Math.round(rec.confidence * 100)}%</p>
          </div>
        )}
        <StatusBadge status={status} />
        <ChevronRight className="w-4 h-4 text-slate-600" />
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser]                     = useState(null);
  const [fleetSummary, setFleetSummary]     = useState(null);
  const [assets, setAssets]                 = useState([]);
  const [readinessMap, setReadinessMap]     = useState({});
  const [recentAlerts, setRecentAlerts]     = useState([]);
  const [maintenanceQueue, setMaintenanceQueue] = useState(null);
  const [loadingData, setLoadingData]       = useState(true);
  const [refreshing, setRefreshing]         = useState(false);
  const [lastRefresh, setLastRefresh]       = useState(new Date());

  useEffect(() => {
    if (!isAuthenticated()) { router.replace('/login'); return; }
    setUser(getUser());
  }, [router]);

  const fetchAll = useCallback(async () => {
    setRefreshing(true);
    setLoadingData(true);
    try {
      const [summary, assetsList, readinessList, alertsList, queue] = await Promise.allSettled([
        getFleetReadinessSummary(),
        listAssets({ limit: 20 }),
        getAllReadiness(),
        listAlerts({ limit: 5 }),
        getMaintenanceQueue(),
      ]);
      if (summary.status === 'fulfilled')       setFleetSummary(summary.value);
      if (assetsList.status === 'fulfilled')    setAssets(assetsList.value || []);
      if (readinessList.status === 'fulfilled') {
        const map = {};
        (readinessList.value || []).forEach((r) => { map[r.asset_id] = r; });
        setReadinessMap(map);
      }
      if (alertsList.status === 'fulfilled')    setRecentAlerts(alertsList.value || []);
      if (queue.status === 'fulfilled')         setMaintenanceQueue(queue.value);
    } finally {
      setRefreshing(false);
      setLoadingData(false);
      setLastRefresh(new Date());
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, 60_000);
    return () => clearInterval(id);
  }, [fetchAll]);

  if (!user) return (
    <div className="min-h-screen bg-[#070a12] flex items-center justify-center">
      <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
    </div>
  );

  const counts = fleetSummary?.counts || { READY: 0, AT_RISK: 0, NOT_READY: 0, UNKNOWN: 0 };
  const total = fleetSummary?.total || 0;
  const readinessPct = total > 0 ? Math.round((counts.READY / total) * 100) : 0;

  return (
    <div className="min-h-screen bg-[#070a12] text-slate-100 font-sans">
      <NavBar title="Dashboard" />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Header row */}
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-xl font-bold">Fleet Operations Dashboard</h1>
            <p className="text-xs text-slate-400 font-mono mt-0.5">
              Last updated: {lastRefresh.toLocaleTimeString()}
            </p>
          </div>
          <button
            onClick={fetchAll}
            disabled={refreshing}
            className="flex items-center gap-1.5 text-xs font-mono text-slate-400 hover:text-slate-200 px-3 py-1.5 rounded-lg border border-slate-800 hover:border-slate-700 disabled:opacity-50 transition-colors"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${refreshing ? 'animate-spin' : ''}`} />
            Refresh
          </button>
        </div>

        {/* Readiness banner */}
        <div className={`rounded-xl border p-4 flex items-center justify-between gap-4 ${
          readinessPct >= 80 ? 'bg-emerald-950/30 border-emerald-800/50'
          : readinessPct >= 60 ? 'bg-amber-950/30 border-amber-800/50'
          : 'bg-red-950/30 border-red-800/50'
        }`}>
          <div className="flex items-center gap-3">
            <div className={`w-10 h-10 rounded-lg flex items-center justify-center ${
              readinessPct >= 80 ? 'bg-emerald-500/20 text-emerald-400'
              : readinessPct >= 60 ? 'bg-amber-500/20 text-amber-400'
              : 'bg-red-500/20 text-red-400'
            }`}>
              <Zap className="w-5 h-5" />
            </div>
            <div>
              <p className="text-sm font-bold">
                Fleet Readiness:{' '}
                <span className={readinessPct >= 80 ? 'text-emerald-400' : readinessPct >= 60 ? 'text-amber-400' : 'text-red-400'}>
                  {loadingData ? '…' : `${readinessPct}%`}
                </span>
              </p>
              <p className="text-[11px] text-slate-400 font-mono">
                {counts.READY} READY · {counts.AT_RISK} AT RISK · {counts.NOT_READY} NOT READY · {counts.UNKNOWN} UNKNOWN · {total} total
              </p>
            </div>
          </div>
          <a href="/missions" className="text-right shrink-0 hover:opacity-80 transition-opacity">
            <p className="text-[10px] text-slate-500 font-mono uppercase">Missions</p>
            <p className="text-sm font-mono font-bold text-blue-400">View All →</p>
          </a>
        </div>

        {/* KPI cards */}
        <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
          <MetricCard icon={CheckCircle2} label="Ready"     value={loadingData ? '…' : counts.READY}     sub="Fit for mission"      color="green" loading={loadingData} />
          <MetricCard icon={AlertTriangle} label="At Risk"  value={loadingData ? '…' : counts.AT_RISK}   sub="Monitor closely"       color="amber" loading={loadingData} />
          <MetricCard icon={XCircle}      label="Not Ready" value={loadingData ? '…' : counts.NOT_READY} sub="Maintenance required"  color="red"   loading={loadingData} />
          <MetricCard icon={HelpCircle}   label="Unknown"   value={loadingData ? '…' : counts.UNKNOWN}   sub="Insufficient data"    color="slate" loading={loadingData} />
        </div>

        {/* Two-column body */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Asset list */}
          <div className="lg:col-span-2 bg-slate-900/40 border border-slate-800 rounded-xl p-4">
            <div className="flex items-center justify-between mb-4">
              <h2 className="text-sm font-bold font-mono uppercase text-slate-300 tracking-wider">Fleet Assets</h2>
              <a href="/assets" className="text-[10px] font-mono text-blue-400 hover:text-blue-300">View all →</a>
            </div>
            {loadingData ? (
              <div className="space-y-2">{[...Array(5)].map((_, i) => <div key={i} className="h-14 bg-slate-800/60 rounded-lg animate-pulse" />)}</div>
            ) : assets.length === 0 ? (
              <p className="text-sm text-slate-500 font-mono text-center py-8">
                No assets found. <a href="/assets" className="text-blue-400 hover:underline">Add assets</a> to get started.
              </p>
            ) : (
              <div className="space-y-2">
                {assets.slice(0, 10).map((a) => (
                  <AssetRow key={a.id} asset={a} readinessMap={readinessMap} onClick={() => router.push(`/assets/${a.id}`)} />
                ))}
              </div>
            )}
          </div>

          {/* Sidebar */}
          <div className="space-y-4">
            {/* Maintenance queue */}
            <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-4">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-bold font-mono uppercase text-slate-300 tracking-wider">Maintenance</h2>
                <a href="/maintenance" className="text-[10px] font-mono text-blue-400 hover:text-blue-300">View all →</a>
              </div>
              {loadingData
                ? <div className="space-y-2">{[...Array(3)].map((_, i) => <div key={i} className="h-10 bg-slate-800/60 rounded animate-pulse" />)}</div>
                : maintenanceQueue ? (
                  <div className="space-y-2">
                    {[
                      { label: 'IMMEDIATE', count: maintenanceQueue.total_immediate, cls: 'text-red-400 bg-red-500/10' },
                      { label: 'URGENT',    count: maintenanceQueue.total_urgent,    cls: 'text-amber-400 bg-amber-500/10' },
                      { label: 'SCHEDULED', count: maintenanceQueue.total_scheduled, cls: 'text-blue-400 bg-blue-500/10' },
                    ].map(({ label, count, cls }) => (
                      <div key={label} className="flex items-center justify-between p-2.5 rounded-lg bg-slate-900/60 border border-slate-800/60">
                        <div className="flex items-center gap-2">
                          <Wrench className={`w-3.5 h-3.5 ${cls.split(' ')[0]}`} />
                          <span className="text-xs font-mono text-slate-300">{label}</span>
                        </div>
                        <span className={`text-xs font-bold font-mono px-2 py-0.5 rounded ${cls}`}>{count}</span>
                      </div>
                    ))}
                  </div>
                ) : <p className="text-xs text-slate-500 font-mono">No open work orders.</p>
              }
            </div>

            {/* Recent alerts */}
            <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-4">
              <div className="flex items-center justify-between mb-3">
                <h2 className="text-sm font-bold font-mono uppercase text-slate-300 tracking-wider">Alerts</h2>
                <a href="/alerts" className="text-[10px] font-mono text-blue-400 hover:text-blue-300">View all →</a>
              </div>
              {loadingData
                ? <div className="space-y-2">{[...Array(3)].map((_, i) => <div key={i} className="h-10 bg-slate-800/60 rounded animate-pulse" />)}</div>
                : recentAlerts.length === 0
                  ? <p className="text-xs text-slate-500 font-mono">No active alerts.</p>
                  : <div className="space-y-2">
                      {recentAlerts.map((a) => (
                        <div key={a.id} className="p-2.5 rounded-lg bg-slate-900/60 border border-slate-800/60">
                          <div className="flex items-center gap-2">
                            <span className={`text-[10px] font-mono font-bold uppercase ${a.severity === 'critical' ? 'text-red-400' : a.severity === 'warning' ? 'text-amber-400' : 'text-blue-400'}`}>{a.severity}</span>
                            <span className="text-[11px] text-slate-300 truncate">{a.title}</span>
                          </div>
                        </div>
                      ))}
                    </div>
              }
            </div>

            {/* Session */}
            <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-4">
              <h2 className="text-sm font-bold font-mono uppercase text-slate-300 tracking-wider mb-3">Session</h2>
              <div className="space-y-1.5">
                {[['Operator', user.full_name], ['Role', user.role?.toUpperCase()]].map(([l, v]) => (
                  <div key={l} className="flex justify-between">
                    <span className="text-[11px] text-slate-500 font-mono">{l}</span>
                    <span className="text-[11px] font-mono text-slate-200">{v}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>

        <div className="bg-slate-900/30 border border-slate-800/60 rounded-xl p-4 flex items-start gap-3">
          <TrendingUp className="w-4 h-4 text-blue-400 shrink-0 mt-0.5" />
          <p className="text-xs text-slate-400 font-mono">
            <span className="text-slate-200 font-semibold">Live data:</span>{' '}
            All metrics are fetched from the FastAPI backend in real-time. Readiness is computed by the deterministic ReadinessEngine — no LLM in the decision path.
          </p>
        </div>
      </main>
    </div>
  );
}
