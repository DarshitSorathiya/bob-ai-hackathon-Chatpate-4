'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Database, AlertTriangle, CheckCircle, XCircle, HelpCircle } from 'lucide-react';
import { isAuthenticated, getDataQualityEvents, getDataQualitySummary } from '../../lib/api';
import NavBar from '../../components/NavBar';

const ISSUE_SEVERITY = {
  critical: { border: 'border-l-red-500',   badge: 'bg-red-500/20 border-red-500/40 text-red-400',     icon: XCircle },
  warning:  { border: 'border-l-amber-500', badge: 'bg-amber-500/20 border-amber-500/40 text-amber-400', icon: AlertTriangle },
  info:     { border: 'border-l-blue-500',  badge: 'bg-blue-500/20 border-blue-500/40 text-blue-400',   icon: HelpCircle },
  ok:       { border: 'border-l-emerald-500', badge: 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400', icon: CheckCircle },
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
    <div className="bg-[#0a0f1d]/80 border-[3px] border-white rounded-2xl p-5 text-center backdrop-blur-xl shadow-xl">
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

  useEffect(() => {
    if (!isAuthenticated()) { router.replace('/login'); return; }
  }, [router]);

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

  return (
    <NavBar title="Data Quality" onBack={() => router.push('/dashboard')}>
      <div className="space-y-6">
        {/* Title Header */}
        <div className="flex items-center justify-between flex-wrap gap-4 pt-2">
          <div className="space-y-1">
            <span className="inline-block px-3 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-widest bg-blue-950/80 text-blue-400 border border-blue-800/60 mb-1">
              TELEMETRY INTEGRITY
            </span>
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-100 font-sans">
              Data Quality & Sensor Faults
            </h1>
          </div>
        </div>

        {/* Summary counters */}
        {summary && (
          <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-4">
            <SummaryCard label="Total Events"   value={summary.total}    color="text-slate-100" />
            <SummaryCard label="Critical"       value={summary.critical} color="text-red-400" />
            <SummaryCard label="Warnings"       value={summary.warning}  color="text-amber-400" />
            <SummaryCard label="Info"           value={summary.info}     color="text-blue-400" />
            <SummaryCard label="Sensor Faults"  value={summary.sensor_faults}  color="text-slate-200" />
            <SummaryCard label="Stale Data"     value={summary.stale_data}     color="text-slate-200" />
          </div>
        )}

        {/* Filters Card Box */}
        <div className="bg-[#0a0f1d]/80 border-[3px] border-white rounded-2xl p-5 backdrop-blur-xl shadow-xl flex gap-4 flex-wrap items-center">
          <select
            value={severityFilter}
            onChange={(e) => applyFilter(setSeverityFilter, e.target.value)}
            className="px-4 py-2.5 text-xs font-mono bg-slate-950/60 border border-slate-800/80 rounded-xl text-slate-200 focus:outline-none focus:border-blue-500 transition-colors"
          >
            <option value="">All Severities</option>
            <option value="critical">Critical</option>
            <option value="warning">Warning</option>
            <option value="info">Info</option>
          </select>

          <select
            value={issueTypeFilter}
            onChange={(e) => applyFilter(setIssueTypeFilter, e.target.value)}
            className="px-4 py-2.5 text-xs font-mono bg-slate-950/60 border border-slate-800/80 rounded-xl text-slate-200 focus:outline-none focus:border-blue-500 transition-colors"
          >
            <option value="">All Issue Types</option>
            {ISSUE_TYPES.map((t) => (
              <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>
            ))}
          </select>

          {(severityFilter || issueTypeFilter) && (
            <button
              onClick={() => { setPage(0); setSeverityFilter(''); setIssueTypeFilter(''); }}
              className="px-4 py-2.5 text-xs font-mono font-bold text-slate-300 hover:text-slate-100 border border-slate-800 bg-slate-950/40 rounded-xl transition-colors"
            >
              Clear filters
            </button>
          )}
        </div>

        {/* Events list */}
        {loading ? (
          <div className="space-y-4">
            {[...Array(6)].map((_, i) => <div key={i} className="h-24 bg-slate-900/60 rounded-2xl border-[3px] border-white animate-pulse" />)}
          </div>
        ) : events.length === 0 ? (
          <div className="bg-[#0a0f1d]/80 border-[3px] border-white rounded-2xl p-12 text-center backdrop-blur-xl shadow-xl">
            <CheckCircle className="w-10 h-10 text-emerald-400 mx-auto mb-3" />
            <p className="text-slate-400 font-mono text-sm">No data quality events match the current filters.</p>
          </div>
        ) : (
          <div className="space-y-4">
            {events.map((evt) => {
              const sev = ISSUE_SEVERITY[evt.severity] || ISSUE_SEVERITY.info;
              return (
                <div
                  key={evt.id}
                  className={`bg-[#0a0f1d]/80 border-[3px] border-white border-l-4 ${sev.border} rounded-2xl p-6 backdrop-blur-xl shadow-xl hover:border-blue-500/40 transition-all`}
                >
                  <div className="flex items-start justify-between gap-4 flex-wrap">
                    <div className="flex-1 min-w-0 space-y-2">
                      <div className="flex items-center gap-2.5 flex-wrap">
                        <SeverityBadge severity={evt.severity} />
                        <span className="text-xs font-mono text-slate-400 uppercase bg-slate-950/60 px-2.5 py-1 rounded-lg border border-slate-800">
                          {evt.issue_type?.replace(/_/g, ' ')}
                        </span>
                        {evt.asset_code && (
                          <span className="text-xs font-mono font-bold text-blue-400">{evt.asset_code}</span>
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
  );
}
