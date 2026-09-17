'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { BellOff, Bell, AlertTriangle } from 'lucide-react';
import { isAuthenticated, listAlerts, acknowledgeAlert } from '../../lib/api';
import NavBar from '../../components/NavBar';

const SEVERITY_STYLES = {
  critical: { border: 'border-l-red-500',    badge: 'bg-red-500/20 border-red-500/40 text-red-400' },
  warning:  { border: 'border-l-amber-500',  badge: 'bg-amber-500/20 border-amber-500/40 text-amber-400' },
  info:     { border: 'border-l-blue-500',   badge: 'bg-blue-500/20 border-blue-500/40 text-blue-400' },
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

  return (
    <NavBar title="Active Alerts" onBack={() => router.push('/dashboard')}>
      <div className="space-y-6">
        {/* Title Header */}
        <div className="flex items-center justify-between flex-wrap gap-4 pt-2">
          <div className="space-y-1">
            <span className="inline-block px-3 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-widest bg-blue-950/80 text-blue-400 border border-blue-800/60 mb-1">
              TELEMETRY ALERTS
            </span>
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-100 font-sans">
              Operational Alerts
            </h1>
          </div>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-4 py-2.5 text-xs font-mono bg-[#0a0f1d]/80 border-[3px] border-white rounded-2xl text-slate-200 focus:outline-none focus:border-blue-500 shadow-xl backdrop-blur-xl transition-colors"
          >
            <option value="">All Statuses</option>
            <option value="ACTIVE">ACTIVE</option>
            <option value="ACKNOWLEDGED">ACKNOWLEDGED</option>
            <option value="RESOLVED">RESOLVED</option>
          </select>
        </div>

        {loading ? (
          <div className="space-y-4">{[...Array(5)].map((_, i) => <div key={i} className="h-24 bg-slate-900/60 rounded-2xl border-[3px] border-white animate-pulse" />)}</div>
        ) : alerts.length === 0 ? (
          <div className="bg-[#0a0f1d]/80 border-[3px] border-white rounded-2xl p-12 text-center backdrop-blur-xl shadow-xl">
            <BellOff className="w-10 h-10 text-slate-500 mx-auto mb-3" />
            <p className="text-slate-400 font-mono text-sm">No alerts match the current status filter.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {alerts.map((alert) => {
              const sev = SEVERITY_STYLES[alert.severity] || SEVERITY_STYLES.info;
              return (
                <div
                  key={alert.id}
                  className={`bg-[#0a0f1d]/80 border-[3px] border-white border-l-4 ${sev.border} rounded-2xl p-6 backdrop-blur-xl shadow-xl transition-all hover:border-blue-500/40`}
                >
                  <div className="flex items-start justify-between gap-4 flex-wrap">
                    <div className="flex-1 min-w-0 space-y-2">
                      <div className="flex items-center gap-2.5 flex-wrap">
                        <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-mono font-bold border ${sev.badge}`}>
                          {alert.severity?.toUpperCase()}
                        </span>
                        <span className="text-xs font-mono text-slate-400 uppercase bg-slate-950/60 px-2.5 py-1 rounded-lg border border-slate-800/80">{alert.alert_type}</span>
                        <span className={`text-xs font-mono font-bold uppercase ${alert.status === 'ACTIVE' ? 'text-amber-400' : alert.status === 'ACKNOWLEDGED' ? 'text-blue-400' : 'text-slate-500'}`}>
                          {alert.status}
                        </span>
                      </div>
                      <p className="text-base font-bold text-slate-100">{alert.title}</p>
                      <p className="text-sm text-slate-300 leading-relaxed">{alert.message}</p>
                      <p className="text-xs text-slate-500 font-mono pt-1">{new Date(alert.created_at).toLocaleString()}</p>
                    </div>
                    {alert.status === 'ACTIVE' && (
                      <button
                        onClick={() => handleAcknowledge(alert.id)}
                        disabled={acknowledging === alert.id}
                        className="flex items-center gap-2 text-xs font-mono font-bold text-blue-400 hover:text-blue-300 px-4 py-2.5 rounded-xl border border-blue-500/30 hover:border-blue-400/50 bg-blue-600/10 disabled:opacity-50 transition-all shrink-0"
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
