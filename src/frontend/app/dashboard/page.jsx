'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import Link from 'next/link';
import {
  AlertTriangle, Wrench, ChevronRight, Loader2,
  Calendar, Plane, Activity
} from 'lucide-react';
import TopNavbar from '../../components/TopNavbar';
import FleetRadarScope from '../../components/FleetRadarScope';
import {
  getUser, isAuthenticated,
  getFleetReadinessSummary, listAssets, getAllReadiness,
  listAlerts, getMaintenanceQueue
} from '../../lib/api';

/**
 * Metric Card matching Image 1:
 * Fixed height h-[165px], rounded-2xl corners, dark glass bg with glowing blue border.
 */
function SummaryCard({ icon: Icon, title, subtitle, href, children }) {
  return (
    <div className="h-[165px] dashboard-card-shape p-5 flex flex-col justify-between group transition-all duration-200">
      {/* Top Header Row */}
      <div className="flex items-center justify-between gap-3">
        <div className="w-11 h-11 rounded-full border border-[#1e4d35]/30 dark:border-[#4e9f76]/40 bg-[#e1eadf] dark:bg-[#1e4d35]/30 flex items-center justify-center text-[#1e4d35] dark:text-[#4e9f76] shrink-0 shadow-sm group-hover:border-[#1e4d35] transition-colors">
          <Icon className="w-5 h-5" />
        </div>
        {href && (
          <Link
            href={href}
            className="w-8 h-8 rounded-full border border-[#1e4d35]/30 dark:border-[#4e9f76]/40 flex items-center justify-center text-[#1e4d35] dark:text-[#4e9f76] hover:bg-[#1e4d35] hover:text-white transition-colors shrink-0"
            title="View details"
          >
            <ChevronRight className="w-4 h-4" />
          </Link>
        )}
      </div>

      {/* Middle Titles */}
      <div>
        <h3 className="text-base font-bold font-sans text-[#122018] dark:text-slate-100 tracking-tight leading-tight">{title}</h3>
        <p className="text-xs text-[#566b5c] dark:text-slate-400 font-normal mt-0.5">{subtitle}</p>
      </div>

      {/* Bottom Status Metrics */}
      <div className="pt-2 border-t border-[#1e4d35]/15 dark:border-slate-800/60">
        {children}
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

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace('/login');
      return;
    }
    setUser(getUser());
  }, [router]);

  const fetchAll = useCallback(async () => {
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
      setLoadingData(false);
    }
  }, []);

  useEffect(() => {
    fetchAll();
    const id = setInterval(fetchAll, 60_000);
    return () => clearInterval(id);
  }, [fetchAll]);

  if (!user) {
    return (
      <div className="min-h-screen bg-[#f4f6ee] dark:bg-[#0d1b13] flex flex-col items-center justify-center gap-3">
        <Loader2 className="w-8 h-8 text-[#1e4d35] dark:text-[#4e9f76] animate-spin" />
        <p className="text-xs font-mono text-[#566b5c] dark:text-slate-400 uppercase tracking-wider">Loading Mission Control...</p>
      </div>
    );
  }

  // Counts matching Picture 1 defaults
  const counts = {
    READY: fleetSummary?.counts?.READY ?? 0,
    AT_RISK: fleetSummary?.counts?.AT_RISK ?? 0,
    NOT_READY: fleetSummary?.counts?.NOT_READY ?? 0,
  };

  const firstName = user.full_name?.split(' ')[0] || 'Tulsi';

  const activityItems = recentAlerts.slice(0, 5).map((alert) => ({
    id: alert.id,
    icon: alert.severity === 'critical' ? AlertTriangle : Wrench,
    colorCls: alert.severity === 'critical'
      ? 'bg-red-500/15 border-red-500/30 text-red-600 dark:text-red-400'
      : 'bg-amber-500/15 border-amber-500/30 text-amber-600 dark:text-amber-400',
    title: alert.title,
    subtitle: alert.message,
    time: alert.created_at ? new Date(alert.created_at).toLocaleString() : 'Recently',
  }));

  return (
    <div className="min-h-screen bg-[#f4f6ee] dark:bg-[#0d1b13] text-[#122018] dark:text-slate-100 font-sans flex flex-col selection:bg-[#1e4d35]/30 transition-colors duration-200">
      {/* 1. Background Overlay */}
      <div className="fixed inset-0 bg-[url('/images/landing-pg.png')] bg-cover bg-center opacity-15 dark:opacity-20 pointer-events-none z-0" />
      <div className="fixed inset-0 bg-gradient-to-b from-[#f4f6ee]/85 via-[#f4f6ee]/75 to-[#f4f6ee]/90 dark:from-[#0d1b13]/85 dark:via-[#0d1b13]/75 dark:to-[#0d1b13]/90 pointer-events-none z-0" />

      {/* Top Navbar Header matching Picture 1 */}
      <TopNavbar />

      {/* Main Dashboard Content */}
      <main className="flex-1 relative z-10 p-4 sm:p-6 lg:p-8 max-w-[1240px] w-full mx-auto space-y-6">

        {/* 1. Hero Title Section with HUD Corner Tagline matching Picture 1 */}
        <div className="flex flex-col md:flex-row md:items-start justify-between gap-4 pt-1">
          <div className="space-y-1.5">
            <span className="inline-block px-3 py-0.5 rounded-md text-[10px] font-mono font-bold uppercase tracking-widest bg-[#e1eadf] dark:bg-[#1e4d35]/40 text-[#1e4d35] dark:text-[#4e9f76] border border-[#1e4d35]/30">
              MISSION CONTROL
            </span>
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-[#122018] dark:text-slate-100 font-sans">
              Welcome back, <span className="text-[#1e4d35] dark:text-[#4e9f76]">{firstName}</span>
            </h1>
            <p className="text-xs sm:text-sm text-[#566b5c] dark:text-slate-400 max-w-2xl font-normal leading-relaxed">
              Here&apos;s your mission overview. Keep the fleet ready, minimize risks and stay ahead.
            </p>
          </div>

          {/* HUD Corner Bracket Tagline matching Picture 1 */}
          <div className="relative px-5 py-2 text-xs font-mono tracking-wider text-[#1e4d35] dark:text-[#4e9f76] font-semibold select-none shrink-0 self-start md:self-auto">
            <span className="absolute top-0 left-0 w-2.5 h-2.5 border-t-2 border-l-2 border-[#1e4d35] dark:border-[#4e9f76]" />
            <span className="absolute top-0 right-0 w-2.5 h-2.5 border-t-2 border-r-2 border-[#1e4d35] dark:border-[#4e9f76]" />
            <span className="absolute bottom-0 left-0 w-2.5 h-2.5 border-b-2 border-l-2 border-[#1e4d35] dark:border-[#4e9f76]" />
            <span className="absolute bottom-0 right-0 w-2.5 h-2.5 border-b-2 border-r-2 border-[#1e4d35] dark:border-[#4e9f76]" />

            <span className="text-[#1e4d35] dark:text-[#4e9f76]">READY FLEET</span>
            <span className="text-[#1e4d35]/40 mx-3">/</span>
            <span className="text-[#1e4d35] dark:text-[#4e9f76]">SAFER MISSIONS</span>
            <span className="text-[#1e4d35]/40 mx-3">/</span>
            <span className="text-[#1e4d35] dark:text-[#4e9f76]">HIGHER SUCCESS</span>
          </div>
        </div>

        {/* 2. Top Summary Cards Row matching Picture 1 (4 Cards in 1 Horizontal Row) */}
        <div className="dashboard-cards-grid">

          {/* Card 1: Fleet Readiness */}
          <SummaryCard
            icon={Plane}
            title="Fleet Readiness"
            subtitle="Total aircraft status overview"
            href="/assets"
          >
            <div className="flex items-center gap-4 text-xs font-mono">
              <span className="flex items-center gap-1.5 text-[#122018] dark:text-slate-300 font-medium">
                <span className="w-2 h-2 rounded-full bg-[#2d9f6f]" /> Ready <strong className="text-[#1e4d35] dark:text-slate-100 ml-0.5">{counts.READY}</strong>
              </span>
              <span className="flex items-center gap-1.5 text-[#122018] dark:text-slate-300 font-medium">
                <span className="w-2 h-2 rounded-full bg-amber-500" /> At Risk <strong className="text-[#1e4d35] dark:text-slate-100 ml-0.5">{counts.AT_RISK}</strong>
              </span>
              <span className="flex items-center gap-1.5 text-[#122018] dark:text-slate-300 font-medium">
                <span className="w-2 h-2 rounded-full bg-red-500" /> Not Ready <strong className="text-[#1e4d35] dark:text-slate-100 ml-0.5">{counts.NOT_READY}</strong>
              </span>
            </div>
          </SummaryCard>

          {/* Card 2: Maintenance */}
          <SummaryCard
            icon={Wrench}
            title="Maintenance"
            subtitle="Upcoming & in progress"
            href="/maintenance"
          >
            <div className="flex items-center gap-4 text-xs font-mono">
              <span className="flex items-center gap-1.5 text-[#122018] dark:text-slate-300 font-medium">
                <span className="w-2 h-2 rounded-full bg-[#1e4d35] dark:bg-[#4e9f76]" /> Due Soon <strong className="text-[#1e4d35] dark:text-slate-100 ml-0.5">{maintenanceQueue?.total_scheduled ?? 0}</strong>
              </span>
              <span className="flex items-center gap-1.5 text-[#122018] dark:text-slate-300 font-medium">
                <span className="w-2 h-2 rounded-full bg-purple-500" /> In Progress <strong className="text-[#1e4d35] dark:text-slate-100 ml-0.5">{maintenanceQueue?.items?.filter((item) => item.maintenance_state === 'IN_PROGRESS').length ?? 0}</strong>
              </span>
            </div>
          </SummaryCard>

          {/* Card 3: Alerts */}
          <SummaryCard
            icon={AlertTriangle}
            title="Alerts"
            subtitle="Latest system alerts"
            href="/alerts"
          >
            <div className="flex items-center gap-4 text-xs font-mono">
              <span className="flex items-center gap-1.5 text-[#122018] dark:text-slate-300 font-medium">
                <span className="w-2 h-2 rounded-full bg-red-500" /> Critical <strong className="text-[#1e4d35] dark:text-slate-100 ml-0.5">{recentAlerts.filter((alert) => alert.severity === 'critical').length}</strong>
              </span>
              <span className="flex items-center gap-1.5 text-[#122018] dark:text-slate-300 font-medium">
                <span className="w-2 h-2 rounded-full bg-amber-500" /> Warning <strong className="text-[#1e4d35] dark:text-slate-100 ml-0.5">{recentAlerts.filter((alert) => alert.severity === 'warning').length}</strong>
              </span>
              <span className="flex items-center gap-1.5 text-[#122018] dark:text-slate-300 font-medium">
                <span className="w-2 h-2 rounded-full bg-[#4e9f76]" /> Info <strong className="text-[#1e4d35] dark:text-slate-100 ml-0.5">{recentAlerts.filter((alert) => alert.severity === 'info').length}</strong>
              </span>
            </div>
          </SummaryCard>

          {/* Card 4: Sessions */}
          <SummaryCard
            icon={Calendar}
            title="Sessions"
            subtitle="Active & upcoming sessions"
            href="/missions"
          >
            <div className="flex items-center gap-4 text-xs font-mono">
              <span className="flex items-center gap-1.5 text-[#122018] dark:text-slate-300 font-medium">
                <span className="w-2 h-2 rounded-full bg-[#2d9f6f]" /> Active <strong className="text-[#1e4d35] dark:text-slate-100 ml-0.5">{maintenanceQueue?.items?.filter((item) => item.maintenance_state === 'IN_PROGRESS').length ?? 0}</strong>
              </span>
              <span className="flex items-center gap-1.5 text-[#122018] dark:text-slate-300 font-medium">
                <span className="w-2 h-2 rounded-full bg-[#1e4d35] dark:bg-[#4e9f76]" /> Upcoming <strong className="text-[#1e4d35] dark:text-slate-100 ml-0.5">{maintenanceQueue?.items?.length ?? 0}</strong>
              </span>
            </div>
          </SummaryCard>

        </div>

        {/* 3. Main Bottom Section: 2 Columns matching Picture 1 */}
        <div className="dashboard-main-grid items-stretch">

          {/* LEFT COLUMN: Fleet Status Overview Panel */}
          <div className="dashboard-left-col min-w-0">
            <FleetRadarScope
              assets={assets}
              readinessMap={readinessMap}
              countsOverride={counts}
              loadingData={loadingData}
            />
          </div>

          {/* RIGHT COLUMN: RECENT ACTIVITY Panel */}
          <div className="dashboard-right-col min-w-0">
            <div className="dashboard-card-shape p-6 flex flex-col justify-between h-full transition-all duration-200">
              <div>
                {/* Header with Pulse Wave Icon matching Picture 1 */}
                <div className="flex items-center gap-2.5 pb-4 mb-2 border-b border-[#1e4d35]/15 dark:border-slate-800">
                  <Activity className="w-4.5 h-4.5 text-[#1e4d35] dark:text-[#4e9f76] shrink-0" />
                  <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-[#1e4d35] dark:text-[#4e9f76]">
                    RECENT ACTIVITY
                  </h2>
                </div>

                {/* Activity List */}
                <div className="divide-y divide-[#1e4d35]/10 dark:divide-slate-800">
                  {activityItems.length === 0 ? (
                    <p className="py-6 text-xs font-mono text-[#566b5c] dark:text-slate-500">No recent activity.</p>
                  ) : activityItems.map((item) => {
                    const ItemIcon = item.icon;
                    return (
                      <div key={item.id} className="py-3 flex items-center justify-between gap-3">
                        <div className="flex items-center gap-3.5 min-w-0">
                          <div className={`w-9 h-9 rounded-full border flex items-center justify-center shrink-0 ${item.colorCls}`}>
                            <ItemIcon className="w-4.5 h-4.5" />
                          </div>
                          <div className="min-w-0">
                            <p className="text-sm font-semibold text-[#122018] dark:text-slate-100 font-sans truncate">{item.title}</p>
                            <p className="text-xs text-[#566b5c] dark:text-slate-400 font-normal truncate mt-0.5">{item.subtitle}</p>
                          </div>
                        </div>
                        <span className="text-xs font-mono text-[#566b5c] dark:text-slate-400 shrink-0 ml-2">
                          {item.time}
                        </span>
                      </div>
                    );
                  })}
                </div>
              </div>
            </div>
          </div>

        </div>

      </main>
    </div>
  );
}