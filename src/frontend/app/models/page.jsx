'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { ChevronDown, ChevronUp, CheckCircle, XCircle, AlertTriangle, Cpu } from 'lucide-react';
import { isAuthenticated, listModels, getModel } from '../../lib/api';
import NavBar from '../../components/NavBar';

const TASK_COLORS = {
  rul:     'bg-blue-500/20 border-blue-500/40 text-blue-400',
  failure: 'bg-red-500/20 border-red-500/40 text-red-400',
  anomaly: 'bg-amber-500/20 border-amber-500/40 text-amber-400',
};

function TaskBadge({ task }) {
  const cls = TASK_COLORS[task] || 'bg-slate-700/50 border-slate-700 text-slate-400';
  return (
    <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-mono font-bold border ${cls}`}>
      {task?.toUpperCase() || 'UNKNOWN'}
    </span>
  );
}

function LeakageBadge({ status }) {
  if (status === 'PASS') return (
    <span className="inline-flex items-center gap-1.5 text-xs font-mono font-bold text-emerald-400">
      <CheckCircle className="w-3.5 h-3.5" /> PASS
    </span>
  );
  if (status === 'FAIL') return (
    <span className="inline-flex items-center gap-1.5 text-xs font-mono font-bold text-red-400">
      <XCircle className="w-3.5 h-3.5" /> FAIL
    </span>
  );
  return <span className="text-xs font-mono text-slate-500">UNKNOWN</span>;
}

function MetricRow({ label, value, unit = '' }) {
  if (value == null) return null;
  const num = typeof value === 'number' ? value.toFixed(4) : value;
  return (
    <div className="flex items-center justify-between py-1.5 border-b border-slate-800/50 text-xs font-mono">
      <span className="text-slate-400">{label}</span>
      <span className="text-slate-200 font-bold tabular-nums">{num}{unit && ` ${unit}`}</span>
    </div>
  );
}

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
      <div className="w-full max-w-2xl bg-[#090d16] border-[3px] border-white rounded-2xl shadow-2xl overflow-hidden max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 shrink-0">
          <div className="flex items-center gap-3">
            <Cpu className="w-5 h-5 text-blue-400" />
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
              <div className="grid grid-cols-2 gap-3 text-xs font-mono">
                <div className="bg-slate-950/60 rounded-xl p-3 border border-slate-800">
                  <p className="text-slate-400 mb-1 font-bold">Algorithm</p>
                  <p className="text-slate-100 font-bold">{data.algorithm || '—'}</p>
                </div>
                <div className="bg-slate-950/60 rounded-xl p-3 border border-slate-800">
                  <p className="text-slate-400 mb-1 font-bold">Features</p>
                  <p className="text-slate-100 font-bold">{data.feature_count}</p>
                </div>
                <div className="bg-slate-950/60 rounded-xl p-3 border border-slate-800">
                  <p className="text-slate-400 mb-1 font-bold">Feature Hash</p>
                  <p className="text-slate-200 font-mono text-[10px]">{data.feature_version || '—'}</p>
                </div>
                <div className="bg-slate-950/60 rounded-xl p-3 border border-slate-800">
                  <p className="text-slate-400 mb-1 font-bold">Leakage Check</p>
                  <LeakageBadge status={data.leakage_status} />
                </div>
              </div>

              {data.evaluation && Object.keys(data.evaluation).length > 0 && (
                <div>
                  <p className="text-xs font-mono text-slate-400 font-bold uppercase mb-2">Evaluation Metrics</p>
                  <div className="bg-slate-950/60 rounded-xl px-4 py-2 border border-slate-800">
                    {Object.entries(data.evaluation).map(([k, v]) => (
                      <MetricRow key={k} label={k} value={v} />
                    ))}
                  </div>
                </div>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}

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
    <NavBar title="ML Models" onBack={() => router.push('/dashboard')}>
      {selected && <ModelDetail tag={selected} onClose={() => setSelected(null)} />}

      <div className="space-y-6">
        {/* Title Header */}
        <div className="flex items-center justify-between flex-wrap gap-4 pt-2">
          <div className="space-y-1">
            <span className="inline-block px-3 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-widest bg-blue-950/80 text-blue-400 border border-blue-800/60 mb-1">
              MODEL REGISTRY
            </span>
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-100 font-sans flex items-center gap-3">
              <Cpu className="w-8 h-8 text-blue-400" />
              Machine Learning Models
            </h1>
            <p className="text-xs text-slate-400 font-mono pt-0.5">Registered model versions & evaluation benchmarks</p>
          </div>
          {!loading && !error && (
            <span className="text-xs font-mono font-bold text-slate-300 bg-[#0a0f1d]/80 border-[3px] border-white px-4 py-2 rounded-xl backdrop-blur-xl">
              {models.length} Registered Models
            </span>
          )}
        </div>

        {error && (
          <div className="bg-[#0a0f1d]/80 border-[3px] border-white rounded-2xl p-6 flex items-center gap-4 backdrop-blur-xl shadow-xl">
            <AlertTriangle className="w-6 h-6 text-red-400 shrink-0" />
            <div>
              <p className="text-sm font-bold text-red-300">{error}</p>
              <p className="text-xs text-slate-400 font-mono mt-1">Model metrics are available to MAINTAINER and ADMIN roles only.</p>
            </div>
          </div>
        )}

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[...Array(3)].map((_, i) => <div key={i} className="h-44 bg-slate-900/60 rounded-2xl border-[3px] border-white animate-pulse" />)}
          </div>
        ) : !error && models.length === 0 ? (
          <div className="bg-[#0a0f1d]/80 border-[3px] border-white rounded-2xl p-12 text-center backdrop-blur-xl shadow-xl">
            <Cpu className="w-10 h-10 text-slate-500 mx-auto mb-3" />
            <p className="text-slate-400 font-mono text-sm">No models registered yet.</p>
          </div>
        ) : !error ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {models.map((model) => (
              <div
                key={model.tag}
                onClick={() => setSelected(model.tag)}
                className="bg-[#0a0f1d]/80 border-[3px] border-white hover:border-blue-400/50 rounded-2xl p-6 backdrop-blur-xl shadow-xl cursor-pointer transition-all group flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-start justify-between gap-3 mb-4">
                    <div className="min-w-0">
                      <p className="font-mono font-bold text-lg text-slate-100 truncate">{model.tag}</p>
                      <p className="text-xs text-slate-400 font-mono mt-0.5">{model.algorithm || 'Unknown algorithm'}</p>
                    </div>
                    <TaskBadge task={model.task} />
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-xs font-mono bg-slate-950/40 p-3.5 rounded-xl border border-slate-800/80 mb-3">
                    <div>
                      <p className="text-slate-400 font-bold">Features</p>
                      <p className="text-slate-100 font-bold">{model.feature_count}</p>
                    </div>
                    <div>
                      <p className="text-slate-400 font-bold">Leakage</p>
                      <LeakageBadge status={model.leakage_status} />
                    </div>
                    {model.evaluation?.mae != null && (
                      <div>
                        <p className="text-slate-400 font-bold">MAE</p>
                        <p className="text-slate-100 font-bold tabular-nums">{model.evaluation.mae.toFixed(4)}</p>
                      </div>
                    )}
                    {model.evaluation?.pr_auc != null && (
                      <div>
                        <p className="text-slate-400 font-bold">PR-AUC</p>
                        <p className="text-slate-100 font-bold tabular-nums">{model.evaluation.pr_auc.toFixed(4)}</p>
                      </div>
                    )}
                  </div>
                </div>

                <p className="text-xs text-blue-400 font-mono font-bold group-hover:text-blue-300 transition-colors">View Model Details →</p>
              </div>
            ))}
          </div>
        ) : null}
      </div>
    </NavBar>
  );
}
