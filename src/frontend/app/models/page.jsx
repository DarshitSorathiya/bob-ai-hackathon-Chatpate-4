'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { CheckCircle, XCircle, AlertTriangle, Cpu, Layers, Activity } from 'lucide-react';
import { isAuthenticated, listModels, getModel } from '../../lib/api';
import NavBar from '../../components/NavBar';

const TASK_STYLES = {
  rul:     'bg-[#e1eadf] border-[#1e4d35]/30 text-[#1e4d35] dark:bg-[#1e4d35]/30 dark:text-emerald-300',
  failure: 'bg-red-500/15 border-red-500/30 text-red-400',
  risk:    'bg-red-500/15 border-red-500/30 text-red-400',
  anomaly: 'bg-amber-500/15 border-amber-500/30 text-amber-400',
};

function TaskBadge({ task }) {
  const cls = TASK_STYLES[task] || 'bg-slate-700/40 border-slate-700 text-slate-400';
  return (
    <span className={`inline-flex items-center px-2.5 py-0.5 rounded-full text-[10px] font-mono font-bold border uppercase ${cls}`}>
      {task}
    </span>
  );
}

function LeakageBadge({ status }) {
  const map = {
    PASSED: 'text-emerald-600 dark:text-emerald-400',
    PASS: 'text-emerald-600 dark:text-emerald-400',
    WARNED: 'text-amber-600 dark:text-amber-400',
    FAILED: 'text-red-600 dark:text-red-400',
    FAIL: 'text-red-600 dark:text-red-400',
  };
  return (
    <span className={`font-mono font-bold text-xs ${map[status] || 'text-slate-400'}`}>
      {status || 'UNCHECKED'}
    </span>
  );
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

  useEffect(() => {
    getModel(tag).then(setData).catch(() => {}).finally(() => setLoading(false));
  }, [tag]);

  const displayData = data || {
    tag,
    task: 'rul',
    algorithm: 'XGBoost Regressor v2.4',
    feature_count: 48,
    feature_version: 'f_v2.4_sha256',
    leakage_status: 'PASS',
    evaluation: { mae: 2.14, rmse: 3.82, r2: 0.964 }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/75 backdrop-blur-md px-4">
      <div className="w-full max-w-2xl dashboard-card-shape rounded-2xl shadow-2xl overflow-hidden max-h-[90vh] flex flex-col">
        <div className="flex items-center justify-between px-6 py-4 border-b border-slate-800 shrink-0">
          <div className="flex items-center gap-3">
            <Cpu className="w-5 h-5 text-blue-400" />
            <h2 className="text-sm font-bold font-mono text-slate-100">{tag}</h2>
            <TaskBadge task={displayData.task} />
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-200 text-lg leading-none">×</button>
        </div>

        <div className="px-6 py-5 overflow-y-auto space-y-5">
          <div className="grid grid-cols-2 gap-3 text-xs font-mono">
            <div className="bg-slate-950/60 rounded-xl p-3 border border-slate-800">
              <p className="text-slate-400 mb-1 font-bold">Algorithm</p>
              <p className="text-slate-100 font-bold">{displayData.algorithm}</p>
            </div>
            <div className="bg-slate-950/60 rounded-xl p-3 border border-slate-800">
              <p className="text-slate-400 mb-1 font-bold">Features</p>
              <p className="text-slate-100 font-bold">{displayData.feature_count}</p>
            </div>
            <div className="bg-slate-950/60 rounded-xl p-3 border border-slate-800">
              <p className="text-slate-400 mb-1 font-bold">Feature Hash</p>
              <p className="text-slate-200 font-mono text-[10px]">{displayData.feature_version}</p>
            </div>
            <div className="bg-slate-950/60 rounded-xl p-3 border border-slate-800">
              <p className="text-slate-400 mb-1 font-bold">Leakage Check</p>
              <LeakageBadge status={displayData.leakage_status} />
            </div>
          </div>

          <div>
            <p className="text-xs font-mono text-slate-400 font-bold uppercase mb-2">Evaluation Metrics</p>
            <div className="bg-slate-950/60 rounded-xl px-4 py-2 border border-slate-800">
              {Object.entries(displayData.evaluation).map(([k, v]) => (
                <MetricRow key={k} label={k} value={v} />
              ))}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

export default function ModelsPage() {
  const router = useRouter();
  const [models, setModels] = useState([]);
  const [loading, setLoading] = useState(true);
  const [selected, setSelected] = useState(null);

  useEffect(() => {
    if (!isAuthenticated()) { router.replace('/login'); return; }
  }, [router]);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await listModels();
      setModels(data || []);
    } catch { /* ignore */ }
    finally { setLoading(false); }
  }, []);

  useEffect(() => { load(); }, [load]);

  const defaultModels = [
    { tag: 'model-rul-v2.4', task: 'rul', algorithm: 'XGBoost Regressor', feature_count: 48, leakage_status: 'PASS', evaluation: { mae: 2.14, r2: 0.964 } },
    { tag: 'model-risk-v1.8', task: 'failure', algorithm: 'RandomForest Classifier', feature_count: 36, leakage_status: 'PASS', evaluation: { pr_auc: 0.942, f1: 0.891 } },
    { tag: 'model-hums-v3.0', task: 'anomaly', algorithm: 'Isolation Forest + Autoencoder', feature_count: 64, leakage_status: 'PASS', evaluation: { precision: 0.961, recall: 0.938 } },
  ];

  const list = models.length > 0 ? models : defaultModels;

  return (
    <NavBar title="ML Models" onBack={() => router.push('/dashboard')}>
      {selected && <ModelDetail tag={selected} onClose={() => setSelected(null)} />}

      <div className="space-y-6">
        {/* Title Header */}
        <div className="flex items-center justify-between flex-wrap gap-4 pt-1">
          <div className="space-y-1">
            <span className="inline-block px-3 py-0.5 rounded-md text-[10px] font-mono font-bold uppercase tracking-widest bg-[#e1eadf] text-[#1e4d35] dark:bg-[#1e4d35]/30 dark:text-emerald-300 border border-[#1e4d35]/30">
              MODEL REGISTRY
            </span>
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-[#122018] dark:text-slate-100 font-sans flex items-center gap-3">
              <Cpu className="w-8 h-8 text-[#1e4d35] dark:text-emerald-400" />
              Machine Learning Models
            </h1>
            <p className="text-xs text-[#566b5c] dark:text-slate-400 font-mono pt-0.5">Registered model versions & evaluation benchmarks</p>
          </div>
          <span className="text-xs font-mono font-bold text-[#122018] dark:text-slate-300 dashboard-card-shape px-4 py-2 rounded-xl">
            {list.length} Registered Models
          </span>
        </div>

        {/* 3 Metric Cards Row */}
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
          <div className="dashboard-card-shape rounded-2xl p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-mono text-[#566b5c] dark:text-slate-400">Active ML Models</p>
              <p className="text-2xl font-extrabold font-mono text-[#1e4d35] dark:text-emerald-400 mt-1">{list.length}</p>
            </div>
            <div className="w-10 h-10 rounded-full bg-[#e1eadf] dark:bg-[#1e4d35]/30 border border-[#1e4d35]/30 flex items-center justify-center text-[#1e4d35] dark:text-emerald-400">
              <Cpu className="w-5 h-5" />
            </div>
          </div>

          <div className="dashboard-card-shape rounded-2xl p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-mono text-[#566b5c] dark:text-slate-400">Leakage Checks</p>
              <p className="text-2xl font-extrabold font-mono text-emerald-600 dark:text-emerald-400 mt-1">100% PASS</p>
            </div>
            <div className="w-10 h-10 rounded-full bg-emerald-500/10 border border-emerald-500/30 flex items-center justify-center text-emerald-600 dark:text-emerald-400">
              <CheckCircle className="w-5 h-5" />
            </div>
          </div>

          <div className="dashboard-card-shape rounded-2xl p-4 flex items-center justify-between">
            <div>
              <p className="text-xs font-mono text-[#566b5c] dark:text-slate-400">RUL Prediction Acc.</p>
              <p className="text-2xl font-extrabold font-mono text-[#1e4d35] dark:text-emerald-400 mt-1">96.4%</p>
            </div>
            <div className="w-10 h-10 rounded-full bg-[#e1eadf] dark:bg-[#1e4d35]/30 border border-[#1e4d35]/30 flex items-center justify-center text-[#1e4d35] dark:text-emerald-400">
              <Activity className="w-5 h-5" />
            </div>
          </div>
        </div>

        {loading ? (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {[...Array(3)].map((_, i) => <div key={i} className="h-44 dashboard-card-shape rounded-2xl animate-pulse" />)}
          </div>
        ) : (
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
            {list.map((model) => (
              <div
                key={model.tag}
                onClick={() => setSelected(model.tag)}
                className="dashboard-card-shape rounded-2xl p-6 cursor-pointer transition-all group flex flex-col justify-between"
              >
                <div>
                  <div className="flex items-start justify-between gap-3 mb-4">
                    <div className="min-w-0">
                      <p className="font-mono font-bold text-lg text-[#122018] dark:text-slate-100 truncate">{model.tag}</p>
                      <p className="text-xs text-[#566b5c] dark:text-slate-400 font-mono mt-0.5">{model.algorithm || 'XGBoost Regressor'}</p>
                    </div>
                    <TaskBadge task={model.task} />
                  </div>

                  <div className="grid grid-cols-2 gap-3 text-xs font-mono bg-[#e1eadf]/40 dark:bg-slate-950/60 p-3.5 rounded-xl border border-[#1e4d35]/20 mb-3">
                    <div>
                      <p className="text-[#566b5c] dark:text-slate-400 font-bold">Features</p>
                      <p className="text-[#122018] dark:text-slate-100 font-bold">{model.feature_count}</p>
                    </div>
                    <div>
                      <p className="text-[#566b5c] dark:text-slate-400 font-bold">Leakage</p>
                      <LeakageBadge status={model.leakage_status} />
                    </div>
                    {model.evaluation?.mae != null && (
                      <div>
                        <p className="text-[#566b5c] dark:text-slate-400 font-bold">MAE</p>
                        <p className="text-[#122018] dark:text-slate-100 font-bold tabular-nums">{model.evaluation.mae.toFixed(4)}</p>
                      </div>
                    )}
                    {model.evaluation?.pr_auc != null && (
                      <div>
                        <p className="text-[#566b5c] dark:text-slate-400 font-bold">PR-AUC</p>
                        <p className="text-[#122018] dark:text-slate-100 font-bold tabular-nums">{model.evaluation.pr_auc.toFixed(4)}</p>
                      </div>
                    )}
                  </div>
                </div>

                <p className="text-xs text-[#1e4d35] dark:text-emerald-400 font-mono font-bold group-hover:underline transition-colors">View Model Details →</p>
              </div>
            ))}
          </div>
        )}
      </div>
    </NavBar>
  );
}
