'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { BellOff } from 'lucide-react';
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
    <div className="min-h-screen bg-[#070a12] text-slate-100 font-sans">
      <NavBar title="Alerts" onBack={() => router.push('/dashboard')} />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-5">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <h1 className="text-xl font-bold">Alerts</h1>
          <select
            value={statusFilter}
            onChange={(e) => setStatusFilter(e.target.value)}
            className="px-3 py-2 text-sm font-mono bg-slate-900/60 border border-slate-700 rounded-lg text-slate-300 focus:outline-none focus:border-blue-500"
          >
            <option value="">All Statuses</option>
            <option value="ACTIVE">ACTIVE</option>
            <option value="ACKNOWLEDGED">ACKNOWLEDGED</option>
            <option value="RESOLVED">RESOLVED</option>
          </select>
        </div>

        {loading ? (
          <div className="space-y-3">{[...Array(5)].map((_, i) => <div key={i} className="h-24 bg-slate-800/60 rounded-xl animate-pulse" />)}</div>
        ) : alerts.length === 0 ? (
          <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-12 text-center">
            <BellOff className="w-8 h-8 text-slate-600 mx-auto mb-3" />
            <p className="text-slate-500 font-mono text-sm">No alerts match the current filter.</p>
          </div>
        ) : (
          <div className="space-y-3">
            {alerts.map((alert) => {
              const sev = SEVERITY_STYLES[alert.severity] || SEVERITY_STYLES.info;
              return (
                <div
                  key={alert.id}
                  className={`bg-slate-900/40 border border-slate-800 border-l-2 ${sev.border} rounded-xl p-4`}
                >
                  <div className="flex items-start justify-between gap-3 flex-wrap">
                    <div className="flex-1 min-w-0">
                      <div className="flex items-center gap-2 mb-1 flex-wrap">
                        <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold border ${sev.badge}`}>
                          {alert.severity?.toUpperCase()}
                        </span>
                        <span className="text-[10px] font-mono text-slate-500 uppercase bg-slate-800/60 px-2 py-0.5 rounded">{alert.alert_type}</span>
                        <span className={`text-[10px] font-mono font-bold uppercase ${alert.status === 'ACTIVE' ? 'text-amber-400' : alert.status === 'ACKNOWLEDGED' ? 'text-blue-400' : 'text-slate-500'}`}>
                          {alert.status}
                        </span>
                      </div>
                      <p className="font-semibold text-slate-100">{alert.title}</p>
                      <p className="text-sm text-slate-400 mt-0.5">{alert.message}</p>
                      <p className="text-[11px] text-slate-600 font-mono mt-1">{new Date(alert.created_at).toLocaleString()}</p>
                    </div>
                    {alert.status === 'ACTIVE' && (
                      <button
                        onClick={() => handleAcknowledge(alert.id)}
                        disabled={acknowledging === alert.id}
                        className="flex items-center gap-1.5 text-[11px] font-mono text-blue-400 hover:text-blue-300 px-3 py-1.5 rounded-lg border border-blue-500/30 hover:border-blue-400/50 disabled:opacity-50 transition-colors shrink-0"
                      >
                        <BellOff className="w-3 h-3" />
                        {acknowledging === alert.id ? 'Acknowledging…' : 'Acknowledge'}
                      </button>
                    )}
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </main>
    </div>
  );
}
