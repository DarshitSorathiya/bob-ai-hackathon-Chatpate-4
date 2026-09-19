'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Database, AlertTriangle, CheckCircle, XCircle, HelpCircle } from 'lucide-react';
import { getDataQualityEvents, getDataQualitySummary } from '../../lib/api';
import NavBar from '../../components/NavBar';
import RoleGuard from '../../components/RoleGuard';

const ISSUE_SEVERITY = {
  critical: { border: 'border-l-red-500',   badge: 'bg-red-500/15 border-red-500/30 text-red-400',     icon: XCircle },
  warning:  { border: 'border-l-amber-500', badge: 'bg-amber-500/15 border-amber-500/30 text-amber-400', icon: AlertTriangle },
  info:     { border: 'border-l-[#1e4d35]',  badge: 'bg-[#e1eadf] border-[#1e4d35]/30 text-[#1e4d35] dark:bg-[#1e4d35]/30 dark:text-emerald-300',   icon: HelpCircle },
  ok:       { border: 'border-l-emerald-500', badge: 'bg-emerald-500/15 border-emerald-500/30 text-emerald-400', icon: CheckCircle },
};

function SeverityBadge({ severity }) {
  const s = ISSUE_SEVERITY[severity] || ISSUE_SEVERITY.info;
  return (
    <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-mono font-bold border ${s.badge}`}>
      {severity?.toUpperCase()}
    </span>
  );
}

function SummaryCard({ label, value, color = 'text-slate-200' }) {
  return (
    <div className="dashboard-card-shape rounded-2xl p-5 text-center">
      <p className={`text-2xl font-black font-mono tabular-nums ${color}`}>{value ?? '—'}</p>
      <p className="text-xs font-mono text-slate-400 mt-1 font-bold">{label}</p>
    </div>
  );
}

const ISSUE_TYPES = [
  'missing_values',
  'sensor_fault',
  'stale_data',
  'out_of_range',
  'calibration_drift',
  'sampling_rate_anomaly',
  'checksum_error',
  'data_gap',
];

export default function DataQualityPage() {
  const router = useRouter();
  const [events, setEvents] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [severityFilter, setSeverityFilter] = useState('');
  const [issueTypeFilter, setIssueTypeFilter] = useState('');
  const [page, setPage] = useState(0);
  const PAGE_SIZE = 50;

  // Auth enforcement handled by RoleGuard wrapper below.

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const params = {
        limit: PAGE_SIZE,
        skip: page * PAGE_SIZE,
      };
      if (severityFilter) params.severity = severityFilter;
      if (issueTypeFilter) params.issue_type = issueTypeFilter;

      const [evts, sum] = await Promise.all([
        getDataQualityEvents(params),
        getDataQualitySummary(),
      ]);
      setEvents(evts || []);
      setSummary(sum);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, [severityFilter, issueTypeFilter, page]);

  useEffect(() => { load(); }, [load]);

  const applyFilter = (setter, value) => { setPage(0); setter(value); };

  const displayEvents = events;
  const displaySummary = summary || { total: 0, critical: 0, warning: 0, info: 0, sensor_faults: 0, stale_data: 0 };

  return (
    <RoleGuard minRole="operator">
    <NavBar title="Data Quality" onBack={() => router.push('/dashboard')}>
      <div className="space-y-6">
        {/* Title Header */}
        <div className="flex items-center justify-between flex-wrap gap-4 pt-1">
          <div className="space-y-1">
            <span className="inline-block px-3 py-0.5 rounded-md text-[10px] font-mono font-bold uppercase tracking-widest bg-[#e1eadf] text-[#1e4d35] dark:bg-[#1e4d35]/30 dark:text-emerald-300 border border-[#1e4d35]/30">
              TELEMETRY INTEGRITY
            </span>
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-[#122018] dark:text-slate-100 font-sans">
              Data Quality & Sensor Faults
            </h1>
            <p className="text-xs sm:text-sm text-[#566b5c] dark:text-slate-400">
              Diagnostic verification of sensor sampling, packet drops, and calibration drift telemetry.
            </p>
          </div>
        </div>

        {/* Summary Counters Banner */}
        <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
          <SummaryCard label="Total Events"   value={displaySummary.total}    color="text-[#122018] dark:text-slate-100" />
          <SummaryCard label="Critical"       value={displaySummary.critical} color="text-red-500 dark:text-red-400" />
          <SummaryCard label="Warnings"       value={displaySummary.warning}  color="text-amber-500 dark:text-amber-400" />
          <SummaryCard label="Info"           value={displaySummary.info}     color="text-[#1e4d35] dark:text-emerald-400" />
          <SummaryCard label="Sensor Faults"  value={displaySummary.sensor_faults}  color="text-[#566b5c] dark:text-slate-200" />
          <SummaryCard label="Stale Data"     value={displaySummary.stale_data}     color="text-[#566b5c] dark:text-slate-200" />
        </div>

        {/* Filters Card Box */}
        <div className="dashboard-card-shape rounded-2xl p-4 flex gap-4 flex-wrap items-center">
          <select
            value={severityFilter}
            onChange={(e) => applyFilter(setSeverityFilter, e.target.value)}
            className="px-4 py-2.5 text-xs font-mono bg-white dark:bg-slate-950/60 border border-[#1e4d35]/20 rounded-xl text-[#122018] dark:text-slate-200 focus:outline-none focus:border-[#1e4d35] transition-colors"
          >
            <option value="">All Severities</option>
            <option value="critical">Critical</option>
            <option value="warning">Warning</option>
            <option value="info">Info</option>
          </select>

          <select
            value={issueTypeFilter}
            onChange={(e) => applyFilter(setIssueTypeFilter, e.target.value)}
            className="px-4 py-2.5 text-xs font-mono bg-white dark:bg-slate-950/60 border border-[#1e4d35]/20 rounded-xl text-[#122018] dark:text-slate-200 focus:outline-none focus:border-[#1e4d35] transition-colors"
          >
            <option value="">All Issue Types</option>
            {ISSUE_TYPES.map((t) => (
              <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>
            ))}
          </select>

          {(severityFilter || issueTypeFilter) && (
            <button
              onClick={() => { setPage(0); setSeverityFilter(''); setIssueTypeFilter(''); }}
              className="px-4 py-2.5 text-xs font-mono font-bold text-[#122018] dark:text-slate-300 border border-[#1e4d35]/30 bg-[#e1eadf]/50 dark:bg-slate-950/40 rounded-xl transition-colors"
            >
              Clear filters
            </button>
          )}
        </div>

        {/* Events List */}
        {loading ? (
          <div className="space-y-4">
            {[...Array(3)].map((_, i) => <div key={i} className="h-24 dashboard-card-shape rounded-2xl animate-pulse" />)}
          </div>
        ) : (
          <div className="space-y-4">
            {displayEvents.length === 0 ? (
              <p className="py-12 text-center text-xs font-mono text-slate-500">No data quality events found.</p>
            ) : displayEvents.map((evt) => {
              const sev = ISSUE_SEVERITY[evt.severity] || ISSUE_SEVERITY.info;
              return (
                <div
                  key={evt.id}
                  className={`dashboard-card-shape border-l-4 ${sev.border} rounded-2xl p-6 transition-all`}
                >
                  <div className="flex items-start justify-between gap-4 flex-wrap">
                    <div className="flex-1 min-w-0 space-y-2">
                      <div className="flex items-center gap-2.5 flex-wrap">
                        <SeverityBadge severity={evt.severity} />
                        <span className="text-xs font-mono text-[#566b5c] dark:text-slate-400 uppercase bg-[#e1eadf]/50 dark:bg-slate-950/60 px-2.5 py-1 rounded-lg border border-[#1e4d35]/20">
                          {evt.issue_type?.replace(/_/g, ' ')}
                        </span>
                        {evt.asset_code && (
                          <span className="text-xs font-mono font-bold text-[#1e4d35] dark:text-emerald-400">{evt.asset_code}</span>
                        )}
                        {evt.sensor_code && (
                          <span className="text-xs font-mono text-slate-400">/ {evt.sensor_code}</span>
                        )}
                      </div>
                      <p className="text-sm font-semibold text-slate-100">{evt.description}</p>
                    </div>
                    <div className="text-right shrink-0">
                      <p className="text-xs text-slate-400 font-mono">
                        {evt.created_at ? new Date(evt.created_at).toLocaleString() : '—'}
                      </p>
                    </div>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </NavBar>
    </RoleGuard>
  );
}
