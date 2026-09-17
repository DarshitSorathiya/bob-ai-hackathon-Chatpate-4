'use client';

import React, { useState, useEffect, useCallback, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import {
  AlertTriangle, CheckCircle2, XCircle, HelpCircle,
  RefreshCw, Zap, Wrench, ChevronRight, Loader2,
  Clock, Shield, Bell, Calendar, User, ChevronDown, Plane
} from 'lucide-react';
import Sidebar from '../../components/Sidebar';
import FleetRadarScope from '../../components/FleetRadarScope';
import {
  getUser, isAuthenticated,
  getFleetReadinessSummary, listAssets, getAllReadiness,
  listAlerts, getMaintenanceQueue, clearSession
} from '../../lib/api';

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

/**
 * Compact Flex Summary Card Component with generous margins & padding.
 */
function SummaryCard({ icon: Icon, title, href, children, loading = false }) {
  return (
    <div className="flex-1 min-w-0 bg-[#080d1a]/85 border-[3px] border-white rounded-2xl p-6 lg:p-7 backdrop-blur-xl flex flex-col justify-between shadow-xl transition-all duration-200 h-full">
      {/* Top Header Row */}
      <div className="flex items-center justify-between gap-3 mb-4">
        <div className="flex items-center gap-4 min-w-0">
          <div className="w-10 h-10 rounded-full border border-blue-500/30 bg-blue-600/10 flex items-center justify-center text-blue-400 shrink-0 shadow-sm shadow-blue-500/10">
            <Icon className="w-5 h-5" />
          </div>
          <h3 className="text-xs sm:text-sm font-mono font-bold text-slate-200 tracking-wide truncate">{title}</h3>
        </div>
        {href && (
          <a href={href} className="text-slate-500 hover:text-blue-400 text-base font-mono transition-colors shrink-0 p-0.5" title="View details">
            ›
          </a>
        )}
      </div>

      {/* Bottom Metrics Row */}
      <div className="pt-3">
        {loading ? (
          <div className="h-7 w-20 bg-slate-800/60 rounded animate-pulse mx-auto" />
        ) : (
          children
        )}
      </div>
    </div>
  );
}

function AssetRow({ asset, readinessMap, onClick }) {
  const rec = readinessMap[asset.id] || {};
  const status = rec.status || 'UNKNOWN';

  return (
    <div
      onClick={onClick}
      className="flex items-center justify-between py-3.5 px-4 rounded-xl bg-slate-950/40 border border-slate-800/50 hover:bg-slate-900/60 cursor-pointer transition-colors"
    >
      <div className="flex items-center gap-3.5 min-w-0">
        <Plane className="w-4.5 h-4.5 text-blue-400 shrink-0" />
        <div className="min-w-0">
          <p className="text-sm font-mono font-bold text-slate-100">{asset.asset_code}</p>
          <p className="text-xs text-slate-400 truncate">{asset.asset_type}{asset.call_sign ? ` — ${asset.call_sign}` : ''}</p>
        </div>
      </div>

      <div className="flex items-center gap-4 shrink-0">
        <StatusBadge status={status} />
        <span className="text-xs font-mono text-slate-400 hidden sm:inline">
          {rec.confidence != null ? `${Math.round(rec.confidence * 100)}%` : '2h ago'}
        </span>
      </div>
    </div>
  );
}

export default function DashboardPage() {
  const router = useRouter();
  const [user, setUser]                         = useState(null);
  const [fleetSummary, setFleetSummary]         = useState(null);
  const [assets, setAssets]                     = useState([]);
  const [readinessMap, setReadinessMap]         = useState({});
  const [recentAlerts, setRecentAlerts]         = useState([]);
  const [maintenanceQueue, setMaintenanceQueue] = useState(null);
  const [loadingData, setLoadingData]           = useState(true);
  const [refreshing, setRefreshing]             = useState(false);
  const [lastRefresh, setLastRefresh]           = useState(new Date());

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

  const alertCounts = useMemo(() => {
    const c = { critical: 0, warning: 0, info: 0 };
    recentAlerts.forEach((a) => {
      const s = (a.severity || 'info').toLowerCase();
      if (c[s] !== undefined) c[s]++;
      else c.info++;
    });
    return c;
  }, [recentAlerts]);

  if (!user) return (
    <div className="min-h-screen bg-[#050811] flex flex-col items-center justify-center gap-3">
      <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
      <p className="text-xs font-mono text-slate-400 uppercase tracking-wider">Loading Mission Control...</p>
    </div>
  );

  const counts = fleetSummary?.counts || { READY: 0, AT_RISK: 0, NOT_READY: 0, UNKNOWN: 0 };
  const totalImmediate = maintenanceQueue?.total_immediate || 0;
  const totalUrgent = maintenanceQueue?.total_urgent || 0;
  const totalScheduled = maintenanceQueue?.total_scheduled || 0;

  return (
    <div className="min-h-screen bg-[#050811] text-slate-100 font-sans flex overflow-x-hidden selection:bg-blue-600/30">
      {/* Background Overlay Layer */}
      <div className="fixed inset-0 bg-[url('/images/landing-bg.png')] bg-cover bg-center opacity-30 pointer-events-none z-0" />
      <div className="fixed inset-0 bg-gradient-to-b from-[#050811]/90 via-[#050811]/80 to-[#050811]/95 pointer-events-none z-0" />

      {/* 1. LEFT SIDEBAR NAVIGATION matching Reference */}
      <Sidebar alertCount={recentAlerts.length} />

      {/* 2. MAIN DASHBOARD CONTENT AREA */}
      <div className="flex-1 flex flex-col min-w-0 relative z-10">

        {/* TOP BAR / NAVIGATION HEADER matching Reference */}
        <header className="w-full px-8 lg:px-10 py-4 border-b border-slate-800/80 bg-[#060913]/60 backdrop-blur-md flex items-center justify-between gap-4">
          {/* Active Navigation Pills */}
          <div className="flex items-center gap-3 font-mono text-xs">
            <span className="px-3.5 py-1 rounded-full bg-blue-600/20 border border-blue-500/40 text-blue-300 font-bold">
              Dashboard
            </span>
            <a href="/assets" className="px-3 py-1 text-slate-400 hover:text-slate-100 transition-colors">Fleet</a>
            <a href="/maintenance" className="px-3 py-1 text-slate-400 hover:text-slate-100 transition-colors">Maintenance</a>
            <a href="/alerts" className="px-3 py-1 text-slate-400 hover:text-slate-100 transition-colors">Alerts</a>
            <a href="/missions" className="px-3 py-1 text-slate-400 hover:text-slate-100 transition-colors">Sessions</a>
          </div>

          {/* Right Header Controls */}
          <div className="flex items-center gap-4">
            {/* Notification Bell */}
            <a href="/alerts" className="relative p-1.5 text-slate-400 hover:text-slate-200 transition-colors">
              <Bell className="w-4 h-4" />
              {recentAlerts.length > 0 && (
                <span className="absolute top-1 right-1 w-2 h-2 rounded-full bg-red-500 animate-pulse" />
              )}
            </a>

            {/* User Profile */}
            <div className="flex items-center gap-2 text-xs font-mono border-l border-slate-800/80 pl-4">
              <div className="w-7.5 h-7.5 rounded-full bg-blue-600/20 border border-blue-500/40 flex items-center justify-center text-blue-400">
                <User className="w-4 h-4" />
              </div>
              <span className="text-slate-300 font-medium hidden sm:inline">Welcome, <strong className="text-slate-100">{user.full_name?.split(' ')[0] || 'Operator'}</strong></span>
              <button
                onClick={() => { clearSession(); router.push('/login'); }}
                className="text-slate-500 hover:text-red-400 p-1 transition-colors"
                title="Sign Out"
              >
                <ChevronDown className="w-3.5 h-3.5" />
              </button>
            </div>
          </div>
        </header>

        {/* DASHBOARD BODY with generous breathing space & extra margins */}
        <main className="p-8 lg:p-12 space-y-10 lg:space-y-12 max-w-[1400px] w-full mx-auto">

          {/* 3. INTEGRATED HEADER (NO CONTAINER BOX!) matching Reference */}
          <div className="flex flex-col sm:flex-row sm:items-start justify-between gap-4 pt-2">
            <div className="space-y-2">
              <span className="inline-block px-3 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-widest bg-blue-950/80 text-blue-400 border border-blue-800/60 mb-1">
                MISSION CONTROL
              </span>
              <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-100 font-sans">
                Welcome back, <span className="text-blue-400">{user.full_name?.split(' ')[0] || 'Operator'}</span>
              </h1>
              <p className="text-xs sm:text-sm text-slate-400 max-w-2xl font-normal leading-relaxed">
                Here&apos;s your mission overview. Keep an eye on fleet readiness, maintenance status, active alerts and ongoing sessions.
              </p>
            </div>

            {/* Live Operational Time Display */}
            <div className="flex items-center gap-3 shrink-0">
              <div className="bg-[#0a0f1d]/80 border border-slate-800/80 px-4 py-2.5 rounded-xl backdrop-blur-xl flex items-center gap-2.5 text-xs font-mono text-slate-300">
                <Clock className="w-3.5 h-3.5 text-blue-400" />
                <span>{lastRefresh.toLocaleDateString([], { weekday: 'short', day: 'numeric', month: 'short', year: 'numeric' })}</span>
                <span className="text-slate-500">|</span>
                <span className="text-slate-100 font-bold">{lastRefresh.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
              </div>
              <button
                onClick={fetchAll}
                disabled={refreshing}
                className="p-2.5 rounded-xl bg-[#0a0f1d]/80 border border-slate-800/80 text-slate-400 hover:text-slate-100 backdrop-blur-xl disabled:opacity-50 transition-colors"
                title="Refresh Data"
              >
                <RefreshCw className={`w-4 h-4 ${refreshing ? 'animate-spin text-blue-400' : ''}`} />
              </button>
            </div>
          </div>

          {/* 4. ALL 4 SUMMARY BOXES IN ONE SINGLE HORIZONTAL ROW USING FLEX (EXPANDED GAPS: gap-6 sm:gap-8 lg:gap-10 xl:gap-12) */}
          <div className="flex flex-row flex-nowrap items-stretch gap-6 sm:gap-8 lg:gap-10 xl:gap-12 w-full overflow-x-auto pb-2">

            {/* Card 1: Fleet Readiness */}
            <SummaryCard icon={Plane} title="Fleet Readiness" href="/assets" loading={loadingData}>
              <div className="grid grid-cols-3 gap-3 sm:gap-4 text-left">
                <div>
                  <span className="text-xl sm:text-2xl font-extrabold font-mono text-red-400 block">{counts.AT_RISK}</span>
                  <span className="text-[10px] font-mono text-slate-400 flex items-center gap-1.5 mt-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-red-400" /> At Risk
                  </span>
                </div>
                <div>
                  <span className="text-xl sm:text-2xl font-extrabold font-mono text-amber-400 block">{counts.NOT_READY}</span>
                  <span className="text-[10px] font-mono text-slate-400 flex items-center gap-1.5 mt-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-400" /> Not Ready
                  </span>
                </div>
                <div>
                  <span className="text-xl sm:text-2xl font-extrabold font-mono text-emerald-400 block">{counts.READY}</span>
                  <span className="text-[10px] font-mono text-slate-400 flex items-center gap-1.5 mt-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> Ready
                  </span>
                </div>
              </div>
            </SummaryCard>

            {/* Card 2: Maintenance */}
            <SummaryCard icon={Wrench} title="Maintenance" href="/maintenance" loading={loadingData}>
              <div className="grid grid-cols-3 gap-3 sm:gap-4 text-left">
                <div>
                  <span className="text-xl sm:text-2xl font-extrabold font-mono text-red-400 block">{totalImmediate}</span>
                  <span className="text-[10px] font-mono text-slate-400 flex items-center gap-1.5 mt-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-red-400" /> Due Soon
                  </span>
                </div>
                <div>
                  <span className="text-xl sm:text-2xl font-extrabold font-mono text-blue-400 block">{totalUrgent}</span>
                  <span className="text-[10px] font-mono text-slate-400 flex items-center gap-1.5 mt-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-blue-400" /> In Progress
                  </span>
                </div>
                <div>
                  <span className="text-xl sm:text-2xl font-extrabold font-mono text-emerald-400 block">{totalScheduled}</span>
                  <span className="text-[10px] font-mono text-slate-400 flex items-center gap-1.5 mt-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> Completed
                  </span>
                </div>
              </div>
            </SummaryCard>

            {/* Card 3: Alerts */}
            <SummaryCard icon={AlertTriangle} title="Alerts" href="/alerts" loading={loadingData}>
              <div className="grid grid-cols-3 gap-3 sm:gap-4 text-left">
                <div>
                  <span className="text-xl sm:text-2xl font-extrabold font-mono text-red-400 block">{alertCounts.critical}</span>
                  <span className="text-[10px] font-mono text-slate-400 flex items-center gap-1.5 mt-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-red-400" /> Critical
                  </span>
                </div>
                <div>
                  <span className="text-xl sm:text-2xl font-extrabold font-mono text-amber-400 block">{alertCounts.warning}</span>
                  <span className="text-[10px] font-mono text-slate-400 flex items-center gap-1.5 mt-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-amber-400" /> Warning
                  </span>
                </div>
                <div>
                  <span className="text-xl sm:text-2xl font-extrabold font-mono text-blue-400 block">{alertCounts.info}</span>
                  <span className="text-[10px] font-mono text-slate-400 flex items-center gap-1.5 mt-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-blue-400" /> Info
                  </span>
                </div>
              </div>
            </SummaryCard>

            {/* Card 4: Sessions */}
            <SummaryCard icon={Calendar} title="Sessions" href="/missions" loading={loadingData}>
              <div className="grid grid-cols-3 gap-3 sm:gap-4 text-left">
                <div>
                  <span className="text-xl sm:text-2xl font-extrabold font-mono text-emerald-400 block">3</span>
                  <span className="text-[10px] font-mono text-slate-400 flex items-center gap-1.5 mt-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" /> Active
                  </span>
                </div>
                <div>
                  <span className="text-xl sm:text-2xl font-extrabold font-mono text-blue-400 block">5</span>
                  <span className="text-[10px] font-mono text-slate-400 flex items-center gap-1.5 mt-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-blue-400" /> Upcoming
                  </span>
                </div>
                <div>
                  <span className="text-xl sm:text-2xl font-extrabold font-mono text-slate-400 block">12</span>
                  <span className="text-[10px] font-mono text-slate-400 flex items-center gap-1.5 mt-1">
                    <span className="w-1.5 h-1.5 rounded-full bg-slate-400" /> Completed
                  </span>
                </div>
              </div>
            </SummaryCard>

          </div>

          {/* 5. THREE MAIN PANELS IN ONE SINGLE ROW USING FLEXBOX WITH EXPANDED GAPS (gap-8 lg:gap-10 xl:gap-12) */}
          <div className="flex flex-row flex-nowrap items-stretch gap-8 lg:gap-10 xl:gap-12 w-full overflow-x-auto pb-2">

            {/* LEFT PANEL: Fleet Readiness Overview (Table) */}
            <div className="flex-[5] min-w-0 bg-[#0a0f1d]/80 border-[3px] border-white rounded-2xl p-6 lg:p-7 backdrop-blur-xl shadow-xl flex flex-col justify-between transition-all duration-200">
              <div>
                <div className="flex items-center justify-between pb-4 mb-4 border-b border-slate-800/80">
                  <div className="flex items-center gap-3.5">
                    <div className="w-9 h-9 rounded-full bg-blue-600/15 border border-blue-500/30 flex items-center justify-center text-red-400 shrink-0 shadow-sm shadow-blue-500/10">
                      <AlertTriangle className="w-4.5 h-4.5" />
                    </div>
                    <h2 className="text-sm font-mono font-bold uppercase tracking-wider text-slate-100">
                      Fleet Readiness Overview
                    </h2>
                  </div>
                  <a href="/assets" className="text-xs font-mono text-blue-400 hover:text-blue-300">
                    View All →
                  </a>
                </div>

                {loadingData ? (
                  <div className="space-y-3">{[...Array(6)].map((_, i) => <div key={i} className="h-11 bg-slate-900/60 rounded-xl animate-pulse" />)}</div>
                ) : assets.length === 0 ? (
                  <p className="text-xs font-mono text-slate-500 py-6 text-center">No fleet assets registered.</p>
                ) : (
                  <div className="space-y-3">
                    {assets.slice(0, 6).map((asset) => (
                      <AssetRow
                        key={asset.id}
                        asset={asset}
                        readinessMap={readinessMap}
                        onClick={() => router.push(`/assets/${asset.id}`)}
                      />
                    ))}
                  </div>
                )}
              </div>
            </div>

            {/* MIDDLE PANEL: Fleet Status (Tactical Radar Scope) */}
            <div className="flex-[4] min-w-0 min-h-[380px]">
              <FleetRadarScope
                assets={assets}
                readinessMap={readinessMap}
                loadingData={loadingData}
              />
            </div>

            {/* RIGHT PANEL: Stacked Recent Alerts + Sessions Queue */}
            <div className="flex-[3] min-w-0 flex flex-col gap-6 lg:gap-8 justify-between">

              {/* Sub-Card 1: Recent Alerts */}
              <div className="bg-[#0a0f1d]/80 border-[3px] border-white rounded-2xl p-5 lg:p-6 backdrop-blur-xl shadow-xl flex-1 flex flex-col justify-between transition-all duration-200">
                <div>
                  <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-800/80">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-amber-500/15 border border-amber-500/30 flex items-center justify-center text-amber-400 shrink-0">
                        <Bell className="w-4 h-4" />
                      </div>
                      <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-100">
                        Recent Alerts
                      </h2>
                    </div>
                    <a href="/alerts" className="text-xs font-mono text-blue-400 hover:text-blue-300">
                      View All →
                    </a>
                  </div>

                  {loadingData ? (
                    <div className="space-y-2">{[...Array(3)].map((_, i) => <div key={i} className="h-9 bg-slate-900/60 rounded animate-pulse" />)}</div>
                  ) : recentAlerts.length === 0 ? (
                    <p className="text-xs text-slate-500 font-mono py-2">No active alerts.</p>
                  ) : (
                    <div className="space-y-2.5 text-xs">
                      {recentAlerts.slice(0, 3).map((a) => (
                        <div key={a.id} className="p-2.5 rounded-lg bg-slate-950/40 border border-slate-800/60 flex items-start gap-2.5">
                          <AlertTriangle className={`w-4 h-4 shrink-0 mt-0.5 ${a.severity === 'critical' ? 'text-red-400' : 'text-amber-400'}`} />
                          <div className="min-w-0 flex-1">
                            <p className="text-xs font-semibold text-slate-200 truncate">{a.title}</p>
                            <p className="text-[10px] font-mono text-slate-500">2h ago</p>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              </div>

              {/* Sub-Card 2: Ongoing Sessions / Queue */}
              <div className="bg-[#0a0f1d]/80 border-[3px] border-white rounded-2xl p-5 lg:p-6 backdrop-blur-xl shadow-xl flex-1 flex flex-col justify-between transition-all duration-200">
                <div>
                  <div className="flex items-center justify-between pb-3 mb-3 border-b border-slate-800/80">
                    <div className="flex items-center gap-3">
                      <div className="w-8 h-8 rounded-full bg-blue-500/15 border border-blue-500/30 flex items-center justify-center text-blue-400 shrink-0">
                        <Calendar className="w-4 h-4" />
                      </div>
                      <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-100">
                        Ongoing Sessions
                      </h2>
                    </div>
                    <a href="/missions" className="text-xs font-mono text-blue-400 hover:text-blue-300">
                      View All →
                    </a>
                  </div>

                  <div className="space-y-2.5 text-xs font-mono">
                    <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-950/40 border border-slate-800/60">
                      <span className="flex items-center gap-2 text-slate-300">
                        <span className="w-2 h-2 rounded-full bg-emerald-400" /> Mission Briefing
                      </span>
                      <span className="text-[10px] text-slate-500">2h ago</span>
                    </div>

                    <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-950/40 border border-slate-800/60">
                      <span className="flex items-center gap-2 text-slate-300">
                        <span className="w-2 h-2 rounded-full bg-blue-400" /> System Check
                      </span>
                      <span className="text-[10px] text-slate-500">4h ago</span>
                    </div>

                    <div className="flex items-center justify-between p-2.5 rounded-lg bg-slate-950/40 border border-slate-800/60">
                      <span className="flex items-center gap-2 text-slate-300">
                        <span className="w-2 h-2 rounded-full bg-blue-400" /> Training Session
                      </span>
                      <span className="text-[10px] text-slate-500">6h ago</span>
                    </div>
                  </div>
                </div>
              </div>

            </div>

          </div>

        </main>
      </div>
    </div>
  );
}
