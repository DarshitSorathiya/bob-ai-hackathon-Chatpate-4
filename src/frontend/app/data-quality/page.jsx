'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Database, AlertTriangle, CheckCircle, XCircle, HelpCircle } from 'lucide-react';
import { isAuthenticated, getDataQualityEvents, getDataQualitySummary } from '../../lib/api';
import NavBar from '../../components/NavBar';

// ─── Severity styling ─────────────────────────────────────────────────────────

const ISSUE_SEVERITY = {
  critical: { border: 'border-l-red-500',   badge: 'bg-red-500/20 border-red-500/40 text-red-400',     icon: XCircle },
  warning:  { border: 'border-l-amber-500', badge: 'bg-amber-500/20 border-amber-500/40 text-amber-400', icon: AlertTriangle },
  info:     { border: 'border-l-blue-500',  badge: 'bg-blue-500/20 border-blue-500/40 text-blue-400',   icon: HelpCircle },
  ok:       { border: 'border-l-emerald-500', badge: 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400', icon: CheckCircle },
};

function SeverityBadge({ severity }) {
  const s = ISSUE_SEVERITY[severity] || ISSUE_SEVERITY.info;
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold border ${s.badge}`}>
      {severity?.toUpperCase()}
    </span>
  );
}

// ─── Summary card ─────────────────────────────────────────────────────────────

function SummaryCard({ label, value, color = 'text-slate-200' }) {
  return (
    <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-4 text-center">
      <p className={`text-2xl font-bold font-mono tabular-nums ${color}`}>{value ?? '—'}</p>
      <p className="text-[11px] font-mono text-slate-500 mt-1">{label}</p>
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

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

  // Reset to page 0 on filter change
  const applyFilter = (setter, value) => { setPage(0); setter(value); };

  return (
    <div className="min-h-screen bg-[#070a12] text-slate-100 font-sans">
      <NavBar title="Data Quality" onBack={() => router.push('/dashboard')} />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Page heading */}
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-2">
            <Database className="w-5 h-5 text-blue-400" />
            <h1 className="text-xl font-bold">Data Quality</h1>
          </div>
          <p className="text-xs text-slate-500 font-mono">
            Telemetry integrity monitoring — sensor faults, staleness, validation failures
          </p>
        </div>

        {/* Summary counters */}
        {summary && (
          <div className="grid grid-cols-2 sm:grid-cols-4 lg:grid-cols-6 gap-3">
            <SummaryCard label="Total Events"   value={summary.total}    color="text-slate-200" />
            <SummaryCard label="Critical"       value={summary.critical} color="text-red-400" />
            <SummaryCard label="Warnings"       value={summary.warning}  color="text-amber-400" />
            <SummaryCard label="Info"           value={summary.info}     color="text-blue-400" />
            <SummaryCard label="Sensor Faults"  value={summary.sensor_faults}  color="text-slate-300" />
            <SummaryCard label="Stale Data"     value={summary.stale_data}     color="text-slate-300" />
          </div>
        )}

        {/* Filters */}
        <div className="flex gap-3 flex-wrap">
          <select
            value={severityFilter}
            onChange={(e) => applyFilter(setSeverityFilter, e.target.value)}
            className="px-3 py-2 text-sm font-mono bg-slate-900/60 border border-slate-700 rounded-lg text-slate-300 focus:outline-none focus:border-blue-500"
          >
            <option value="">All Severities</option>
            <option value="critical">Critical</option>
            <option value="warning">Warning</option>
            <option value="info">Info</option>
          </select>

          <select
            value={issueTypeFilter}
            onChange={(e) => applyFilter(setIssueTypeFilter, e.target.value)}
            className="px-3 py-2 text-sm font-mono bg-slate-900/60 border border-slate-700 rounded-lg text-slate-300 focus:outline-none focus:border-blue-500"
          >
            <option value="">All Issue Types</option>
            {ISSUE_TYPES.map((t) => (
              <option key={t} value={t}>{t.replace(/_/g, ' ')}</option>
            ))}
          </select>

          {(severityFilter || issueTypeFilter) && (
            <button
              onClick={() => { setPage(0); setSeverityFilter(''); setIssueTypeFilter(''); }}
              className="px-3 py-2 text-xs font-mono text-slate-400 hover:text-slate-200 border border-slate-700 rounded-lg transition-colors"
            >
              Clear filters
            </button>
          )}
        </div>

        {/* Events list */}
        {loading ? (
          <div className="space-y-3">
            {[...Array(8)].map((_, i) => <div key={i} className="h-20 bg-slate-800/60 rounded-xl animate-pulse" />)}
          </div>
        ) : events.length === 0 ? (
          <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-12 text-center">
            <CheckCircle className="w-8 h-8 text-emerald-500 mx-auto mb-3" />
            <p className="text-slate-400 font-mono text-sm">No data quality events match the current filters.</p>
            <p className="text-slate-600 font-mono text-xs mt-1">
              {(severityFilter || issueTypeFilter) ? 'Try clearing the filters.' : 'All telemetry streams are clean.'}
            </p>
          </div>
        ) : (
          <>
            <div className="space-y-2">
              {events.map((evt) => {
                const sev = ISSUE_SEVERITY[evt.severity] || ISSUE_SEVERITY.info;
                const Icon = sev.icon;
                return (
                  <div
                    key={evt.id}
                    className={`bg-slate-900/40 border border-slate-800 border-l-2 ${sev.border} rounded-xl px-4 py-3`}
                  >
                    <div className="flex items-start justify-between gap-3 flex-wrap">
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2 mb-1 flex-wrap">
                          <SeverityBadge severity={evt.severity} />
                          <span className="text-[10px] font-mono text-slate-500 bg-slate-800/60 px-2 py-0.5 rounded uppercase">
                            {evt.issue_type?.replace(/_/g, ' ')}
                          </span>
                          {evt.asset_code && (
                            <span className="text-[10px] font-mono text-blue-400">{evt.asset_code}</span>
                          )}
                          {evt.sensor_code && (
                            <span className="text-[10px] font-mono text-slate-400">/ {evt.sensor_code}</span>
                          )}
                        </div>
                        <p className="text-sm text-slate-200">{evt.description}</p>
                        {evt.details && (
                          <p className="text-[11px] text-slate-500 font-mono mt-0.5">{
                            typeof evt.details === 'object'
                              ? Object.entries(evt.details).map(([k, v]) => `${k}: ${v}`).join(' · ')
                              : evt.details
                          }</p>
                        )}
                      </div>
                      <div className="text-right shrink-0">
                        <p className="text-[10px] text-slate-500 font-mono">
                          {evt.created_at ? new Date(evt.created_at).toLocaleString() : '—'}
                        </p>
                        {evt.is_resolved && (
                          <span className="text-[10px] font-mono text-emerald-400">✓ Resolved</span>
                        )}
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>

            {/* Pagination */}
            <div className="flex items-center justify-between pt-2">
              <button
                onClick={() => setPage((p) => Math.max(0, p - 1))}
                disabled={page === 0}
                className="px-3 py-1.5 text-xs font-mono text-slate-400 hover:text-slate-200 border border-slate-700 rounded-lg disabled:opacity-30 transition-colors"
              >
                ← Prev
              </button>
              <span className="text-xs font-mono text-slate-500">
                Page {page + 1} · {events.length} results
              </span>
              <button
                onClick={() => setPage((p) => p + 1)}
                disabled={events.length < PAGE_SIZE}
                className="px-3 py-1.5 text-xs font-mono text-slate-400 hover:text-slate-200 border border-slate-700 rounded-lg disabled:opacity-30 transition-colors"
              >
                Next →
              </button>
            </div>
          </>
        )}
      </main>
    </div>
  );
}
