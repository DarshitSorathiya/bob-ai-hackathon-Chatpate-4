'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { BellOff, Bell, AlertTriangle, ShieldAlert, CheckCircle2 } from 'lucide-react';
import { isAuthenticated, listAlerts, acknowledgeAlert } from '../../lib/api';
import NavBar from '../../components/NavBar';

const SEVERITY_STYLES = {
  critical: { border: 'border-l-red-500',    badge: 'bg-red-500/15 border-red-500/30 text-red-400' },
  warning:  { border: 'border-l-amber-500',  badge: 'bg-amber-500/15 border-amber-500/30 text-amber-400' },
  info:     { border: 'border-l-[#1e4d35]',  badge: 'bg-[#e1eadf] border-[#1e4d35]/30 text-[#1e4d35] dark:bg-[#1e4d35]/30 dark:text-emerald-300' },
};

export default function AlertsPage() {
  const router = useRouter();
  const [alerts, setAlerts] = useState([]);
  const [loading, setLoading] = useState(true);
  const [statusFilter, setStatusFilter] = useState('ACTIVE');
  const [acknowledging, setAcknowledging] = useState(null);

  useEffect(() => {
    if (!isAuthenticated()) { router.replace('/login'); return; }
  }, [router]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listAlerts({ status_filter: statusFilter || undefined, limit: 100 });
      setAlerts(data || []);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [statusFilter]);

  useEffect(() => { load(); }, [load]);

  const handleAcknowledge = async (alertId) => {
    setAcknowledging(alertId);
    try {
      await acknowledgeAlert(alertId);
      await load();
    } catch { /* ignore */ }
    finally { setAcknowledging(null); }
  };

  const displayAlerts = alerts;
  const criticalCount = alerts.filter((alert) => alert.severity === 'critical').length;
  const warningCount = alerts.filter((alert) => alert.severity === 'warning').length;
  const infoCount = alerts.filter((alert) => alert.severity === 'info').length;

  return (
    <NavBar title="Active Alerts" onBack={() => router.push('/dashboard')}>
      <div className="space-y-6">
        {/* Title Header */}
        <div className="flex items-center justify-between flex-wrap gap-4 pt-1">
          <div className="space-y-1">
            <span className="inline-block px-3 py-0.5 rounded-md text-[10px] font-mono font-bold uppercase tracking-widest bg-[#e1eadf] text-[#1e4d35] dark:bg-[#1e4d35]/30 dark:text-emerald-300 border border-[#1e4d35]/30">
              TELEMETRY ALERTS
            </span>
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-[#122018] dark:text-slate-100 font-sans">
              Operational Alerts
            </h1>
            <p className="text-xs sm:text-sm text-[#566b5c] dark:text-slate-400">
              Real-time telemetry threshold triggers, critical system warnings, and status logs.
            </p>
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-4 py-2.5 text-xs font-mono dashboard-card-shape rounded-xl text-[#122018] dark:text-slate-200 focus:outline-none focus:border-[#1e4d35] shadow-md transition-colors"
          >
            <option value="">All Statuses</option>
            <option value="ACTIVE">ACTIVE</option>
            <option value="ACKNOWLEDGED">ACKNOWLEDGED</option>
            <option value="RESOLVED">RESOLVED</option>
          </select>
        </div>

        {/* Metric Cards Banner */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="dashboard-card-shape rounded-2xl p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-mono text-[#566b5c] dark:text-slate-400">Critical Alerts</p>
              <p className="text-2xl font-extrabold font-mono text-red-500 dark:text-red-400 mt-1">{criticalCount}</p>
            </div>
            <div className="w-10 h-10 rounded-full bg-red-500/10 border border-red-500/30 flex items-center justify-center text-red-500">
              <ShieldAlert className="w-5 h-5" />
            </div>
          </div>
          <div className="dashboard-card-shape rounded-2xl p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-mono text-[#566b5c] dark:text-slate-400">Warnings</p>
              <p className="text-2xl font-extrabold font-mono text-amber-500 dark:text-amber-400 mt-1">{warningCount}</p>
            </div>
            <div className="w-10 h-10 rounded-full bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-500">
              <AlertTriangle className="w-5 h-5" />
            </div>
          </div>
          <div className="dashboard-card-shape rounded-2xl p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-mono text-[#566b5c] dark:text-slate-400">Info Notices</p>
              <p className="text-2xl font-extrabold font-mono text-[#1e4d35] dark:text-emerald-400 mt-1">{infoCount}</p>
            </div>
            <div className="w-10 h-10 rounded-full bg-[#e1eadf] dark:bg-[#1e4d35]/30 border border-[#1e4d35]/30 flex items-center justify-center text-[#1e4d35] dark:text-emerald-400">
              <Bell className="w-5 h-5" />
            </div>
          </div>
        </div>

        {loading ? (
          <div className="space-y-4">{[...Array(3)].map((_, i) => <div key={i} className="h-24 dashboard-card-shape rounded-2xl animate-pulse" />)}</div>
        ) : (
          <div className="space-y-4">
            {displayAlerts.length === 0 ? (
              <p className="py-12 text-center text-xs font-mono text-slate-500">No alerts found.</p>
            ) : displayAlerts.map((alert) => {
              const sev = SEVERITY_STYLES[alert.severity] || SEVERITY_STYLES.info;
              return (
                <div
                  key={alert.id}
                  className={`dashboard-card-shape border-l-4 ${sev.border} rounded-2xl p-6 transition-all`}
                >
                  <div className="flex items-start justify-between gap-4 flex-wrap">
                    <div className="flex-1 min-w-0 space-y-2">
                      <div className="flex items-center gap-2.5 flex-wrap">
                        <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-mono font-bold border ${sev.badge}`}>
                          {alert.severity?.toUpperCase()}
                        </span>
                        <span className="text-xs font-mono text-[#566b5c] dark:text-slate-400 uppercase bg-[#e1eadf]/60 dark:bg-slate-950/60 px-2.5 py-1 rounded-lg border border-[#1e4d35]/20">{alert.alert_type}</span>
                        <span className={`text-xs font-mono font-bold uppercase ${alert.status === 'ACTIVE' ? 'text-amber-500' : alert.status === 'ACKNOWLEDGED' ? 'text-[#1e4d35] dark:text-emerald-400' : 'text-slate-500'}`}>
                          {alert.status}
                        </span>
                      </div>
                      <p className="text-base font-bold text-[#122018] dark:text-slate-100">{alert.title}</p>
                      <p className="text-sm text-[#566b5c] dark:text-slate-300 leading-relaxed">{alert.message}</p>
                      <p className="text-xs text-slate-400 font-mono pt-1">{new Date(alert.created_at).toLocaleString()}</p>
                    </div>
                    {alert.status === 'ACTIVE' && (
                      <button
                        onClick={() => handleAcknowledge(alert.id)}
                        disabled={acknowledging === alert.id}
                        className="flex items-center gap-2 text-xs font-mono font-bold text-[#1e4d35] dark:text-emerald-400 hover:bg-[#e1eadf] px-4 py-2.5 rounded-xl border border-[#1e4d35]/30 bg-[#e1eadf]/50 dark:bg-[#1e4d35]/20 disabled:opacity-50 transition-all shrink-0"
                      >
                        <BellOff className="w-4 h-4" />
                        {acknowledging === alert.id ? 'Acknowledging…' : 'Acknowledge'}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </NavBar>
  );
}
