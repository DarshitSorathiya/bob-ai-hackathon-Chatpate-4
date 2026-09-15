'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { ChevronDown, ChevronUp, CheckCircle, XCircle, AlertTriangle, Cpu } from 'lucide-react';
import { isAuthenticated, listModels, getModel } from '../../lib/api';
import NavBar from '../../components/NavBar';

// ─── Helpers ──────────────────────────────────────────────────────────────────

const TASK_COLORS = {
  rul:     'bg-blue-500/20 border-blue-500/40 text-blue-400',
  failure: 'bg-red-500/20 border-red-500/40 text-red-400',
  anomaly: 'bg-amber-500/20 border-amber-500/40 text-amber-400',
};

function TaskBadge({ task }) {
  const cls = TASK_COLORS[task] || 'bg-slate-700/50 border-slate-700 text-slate-400';
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold border ${cls}`}>
      {task?.toUpperCase() || 'UNKNOWN'}
    </span>
  );
}

function LeakageBadge({ status }) {
  if (status === 'PASS') return (
    <span className="inline-flex items-center gap-1 text-[10px] font-mono font-bold text-emerald-400">
      <CheckCircle className="w-3 h-3" /> PASS
    </span>
  );
  if (status === 'FAIL') return (
    <span className="inline-flex items-center gap-1 text-[10px] font-mono font-bold text-red-400">
      <XCircle className="w-3 h-3" /> FAIL
    </span>
  );
  return <span className="text-[10px] font-mono text-slate-500">UNKNOWN</span>;
}

function MetricRow({ label, value, unit = '' }) {
  if (value == null) return null;
  const num = typeof value === 'number' ? value.toFixed(4) : value;
  return (
    <div className="flex items-center justify-between py-1 border-b border-slate-800/50 text-xs font-mono">
      <span className="text-slate-400">{label}</span>
      <span className="text-slate-200 tabular-nums">{num}{unit && ` ${unit}`}</span>
    </div>
  );
}

// ─── Model detail panel ───────────────────────────────────────────────────────

function ModelDetail({ tag, onClose }) {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [showFeatures, setShowFeatures] = useState(false);
  const [showImportance, setShowImportance] = useState(true);

  useEffect(() => {
    getModel(tag).then(setData).catch(() => {}).finally(() => setLoading(false));
  }, [tag]);

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/70 backdrop-blur-sm px-4">
      <div className="w-full max-w-2xl bg-[#0d1117] border border-slate-700 rounded-2xl shadow-2xl overflow-hidden max-h-[90vh] flex flex-col">
        {/* Header */}
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 shrink-0">
          <div className="flex items-center gap-3">
            <Cpu className="w-4 h-4 text-blue-400" />
            <h2 className="text-sm font-bold font-mono text-slate-100">{tag}</h2>
            {data && <TaskBadge task={data.task} />}
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-200 text-lg leading-none">×</button>
        </div>

        <div className="px-6 py-5 overflow-y-auto space-y-5">
          {loading ? (
            <div className="space-y-3">{[...Array(4)].map((_, i) => <div key={i} className="h-8 bg-slate-800/60 rounded animate-pulse" />)}</div>
          ) : !data ? (
            <p className="text-slate-500 font-mono text-sm">Failed to load model details.</p>
          ) : (
            <>
              {/* Meta */}
              <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                <div className="bg-slate-900/40 rounded-lg p-3">
                  <p className="text-slate-500 mb-1">Algorithm</p>
                  <p className="text-slate-200 font-semibold">{data.algorithm || '—'}</p>
                </div>
                <div className="bg-slate-900/40 rounded-lg p-3">
                  <p className="text-slate-500 mb-1">Features</p>
                  <p className="text-slate-200 font-semibold">{data.feature_count}</p>
                </div>
                <div className="bg-slate-900/40 rounded-lg p-3">
                  <p className="text-slate-500 mb-1">Feature Hash</p>
                  <p className="text-slate-200 font-mono text-[10px]">{data.feature_version || '—'}</p>
                </div>
                <div className="bg-slate-900/40 rounded-lg p-3">
                  <p className="text-slate-500 mb-1">Leakage Check</p>
                  <LeakageBadge status={data.leakage_status} />
                </div>
              </div>

              {/* Evaluation metrics */}
              {data.evaluation && Object.keys(data.evaluation).length > 0 && (
                <div>
                  <p className="text-[10px] font-mono text-slate-500 uppercase mb-2">Evaluation Metrics</p>
                  <div className="bg-slate-900/40 rounded-lg px-4 py-2">
                    {Object.entries(data.evaluation).map(([k, v]) => (
                      <MetricRow key={k} label={k} value={v} />
                    ))}
                  </div>
                </div>
              )}

              {/* Training metadata */}
              {data.training_metadata && Object.keys(data.training_metadata).length > 0 && (
                <div>
                  <p className="text-[10px] font-mono text-slate-500 uppercase mb-2">Training Configuration</p>
                  <div className="bg-slate-900/40 rounded-lg px-4 py-2">
                    {Object.entries(data.training_metadata).map(([k, v]) => (
                      <MetricRow key={k} label={k} value={typeof v === 'object' ? JSON.stringify(v) : v} />
                    ))}
                  </div>
                </div>
              )}

              {/* Top feature importance */}
              {data.feature_importance && Object.keys(data.feature_importance).length > 0 && (
                <div>
                  <button
                    onClick={() => setShowImportance(!showImportance)}
                    className="flex items-center justify-between w-full text-[10px] font-mono text-slate-500 uppercase mb-2 hover:text-slate-300 transition-colors"
                  >
                    Top Feature Importances
                    {showImportance ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                  </button>
                  {showImportance && (
                    <div className="bg-slate-900/40 rounded-lg px-4 py-2 space-y-1.5">
                      {Object.entries(data.feature_importance)
                        .sort(([, a], [, b]) => b - a)
                        .slice(0, 20)
                        .map(([feat, imp]) => {
                          const pct = (imp * 100).toFixed(1);
                          return (
                            <div key={feat} className="flex items-center gap-2">
                              <span className="text-[10px] font-mono text-slate-400 w-40 shrink-0 truncate">{feat}</span>
                              <div className="flex-1 h-1.5 bg-slate-800 rounded-full overflow-hidden">
                                <div className="h-full bg-blue-500 rounded-full" style={{ width: `${Math.min(parseFloat(pct) * 5, 100)}%` }} />
                              </div>
                              <span className="text-[10px] font-mono text-slate-400 w-10 text-right tabular-nums">{pct}%</span>
                            </div>
                          );
                        })}
                    </div>
                  )}
                </div>
              )}

              {/* Feature names */}
              {data.feature_names?.length > 0 && (
                <div>
                  <button
                    onClick={() => setShowFeatures(!showFeatures)}
                    className="flex items-center justify-between w-full text-[10px] font-mono text-slate-500 uppercase mb-2 hover:text-slate-300 transition-colors"
                  >
                    Feature Names ({data.feature_names.length})
                    {showFeatures ? <ChevronUp className="w-3 h-3" /> : <ChevronDown className="w-3 h-3" />}
                  </button>
                  {showFeatures && (
                    <div className="bg-slate-900/40 rounded-lg p-3 flex flex-wrap gap-1.5 max-h-48 overflow-y-auto">
                      {data.feature_names.map((f) => (
                        <span key={f} className="text-[10px] font-mono text-slate-400 bg-slate-800/60 px-2 py-0.5 rounded">{f}</span>
                      ))}
                    </div>
                  )}
                </div>
              )}

              {data.created_at && (
                <p className="text-[10px] font-mono text-slate-600 text-right">
                  Registered: {new Date(data.created_at).toLocaleString()}
                </p>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

// ─── Main page ────────────────────────────────────────────────────────────────

export default function ModelsPage() {
  const router = useRouter();
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState('');
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    if (!isAuthenticated()) { router.replace('/login'); return; }
  }, [router]);

  const load = useCallback(async () => {
    setLoading(true);
    setError('');
    try {
      const data = await listModels();
      setModels(data || []);
    } catch (err) {
      // 403 = not enough role — show friendly message
      if (err.message?.includes('403') || err.message?.toLowerCase().includes('forbidden') || err.message?.toLowerCase().includes('not authorized')) {
        setError('Access restricted. This page requires MAINTAINER or ADMIN role.');
      } else {
        setError(err.message || 'Failed to load models.');
      }
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  return (
    <div className="min-h-screen bg-[#070a12] text-slate-100 font-sans">
      <NavBar title="Models" onBack={() => router.push('/dashboard')} />

      {selected && <ModelDetail tag={selected} onClose={() => setSelected(null)} />}

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-6">
        <div className="flex items-center justify-between flex-wrap gap-3">
          <div className="flex items-center gap-3">
            <Cpu className="w-5 h-5 text-blue-400" />
            <div>
              <h1 className="text-xl font-bold">ML Models</h1>
              <p className="text-xs text-slate-500 font-mono mt-0.5">Registered model versions and evaluation metrics — MAINTAINER / ADMIN only</p>
            </div>
          </div>
          {!loading && !error && (
            <span className="text-xs font-mono text-slate-500">{models.length} registered</span>
          )}
        </div>

        {error && (
          <div className="bg-red-950/30 border border-red-800/40 rounded-xl p-6 flex items-center gap-3">
            <AlertTriangle className="w-5 h-5 text-red-400 shrink-0" />
            <div>
              <p className="text-sm font-semibold text-red-300">{error}</p>
              <p className="text-xs text-slate-500 font-mono mt-1">Model metrics are available to MAINTAINER and ADMIN roles only.</p>
            </div>
          </div>
        )}

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {[...Array(3)].map((_, i) => <div key={i} className="h-40 bg-slate-800/60 rounded-xl animate-pulse" />)}
          </div>
        ) : !error && models.length === 0 ? (
          <div className="bg-slate-900/40 border border-dashed border-slate-700 rounded-xl p-12 text-center">
            <Cpu className="w-8 h-8 text-slate-600 mx-auto mb-3" />
            <p className="text-slate-500 font-mono text-sm">No models registered yet.</p>
            <p className="text-slate-600 font-mono text-xs mt-1">
              Train and register models using the ML pipeline scripts.
            </p>
          </div>
        ) : !error ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
            {models.map((model) => (
              <div
                key={model.tag}
                onClick={() => setSelected(model.tag)}
                className="bg-slate-900/40 border border-slate-800 hover:border-slate-600 rounded-xl p-5 cursor-pointer transition-colors group"
              >
                <div className="flex items-start justify-between gap-2 mb-3">
                  <div className="min-w-0">
                    <p className="font-mono font-bold text-slate-100 truncate">{model.tag}</p>
                    <p className="text-xs text-slate-500 font-mono mt-0.5">{model.algorithm || 'Unknown algorithm'}</p>
                  </div>
                  <TaskBadge task={model.task} />
                </div>

                <div className="grid grid-cols-2 gap-2 text-[11px] font-mono mb-3">
                  <div>
                    <p className="text-slate-500">Features</p>
                    <p className="text-slate-200">{model.feature_count}</p>
                  </div>
                  <div>
                    <p className="text-slate-500">Leakage</p>
                    <LeakageBadge status={model.leakage_status} />
                  </div>
                  {model.evaluation?.mae != null && (
                    <div>
                      <p className="text-slate-500">MAE</p>
                      <p className="text-slate-200 tabular-nums">{model.evaluation.mae.toFixed(4)}</p>
                    </div>
                  )}
                  {model.evaluation?.pr_auc != null && (
                    <div>
                      <p className="text-slate-500">PR-AUC</p>
                      <p className="text-slate-200 tabular-nums">{model.evaluation.pr_auc.toFixed(4)}</p>
                    </div>
                  )}
                  {model.evaluation?.roc_auc != null && (
                    <div>
                      <p className="text-slate-500">ROC-AUC</p>
                      <p className="text-slate-200 tabular-nums">{model.evaluation.roc_auc.toFixed(4)}</p>
                    </div>
                  )}
                </div>

                {model.created_at && (
                  <p className="text-[10px] text-slate-600 font-mono">{new Date(model.created_at).toLocaleString()}</p>
                )}
                <p className="mt-2 text-[10px] text-slate-700 font-mono group-hover:text-slate-500 transition-colors">Click to view details →</p>
              </div>
            ))}
          </div>
        ) : null}
      </main>
    </div>
  );
}
