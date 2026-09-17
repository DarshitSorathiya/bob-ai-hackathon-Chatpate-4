'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft, RefreshCw, Loader2, AlertTriangle, CheckCircle2, HelpCircle, Activity, Wrench, Shield, Plane } from 'lucide-react';
import NavBar from '../../../components/NavBar';
import {
  isAuthenticated, getAsset, getAssetReadiness, getAssetComponents,
  getAssetSensors, getAssetPredictions, getAssetAlerts, evaluateAssetReadiness,
} from '../../../lib/api';

function StatusBadge({ status }) {
  const map = {
    READY:     { cls: 'bg-emerald-500/20 border-emerald-500/40 text-emerald-400' },
    AT_RISK:   { cls: 'bg-amber-500/20 border-amber-500/40 text-amber-400' },
    NOT_READY: { cls: 'bg-red-500/20 border-red-500/40 text-red-400' },
    UNKNOWN:   { cls: 'bg-slate-700/50 border-slate-700 text-slate-400' },
  };
  const s = map[status] ?? map.UNKNOWN;
  return (
    <span className={`inline-flex items-center px-3 py-1 rounded-full text-xs font-mono font-bold border ${s.cls}`}>
      {status}
    </span>
  );
}

function SeverityBadge({ severity }) {
  const m = {
    critical: 'text-red-400 bg-red-500/10 border-red-500/30',
    warning:  'text-amber-400 bg-amber-500/10 border-amber-500/30',
    info:     'text-blue-400 bg-blue-500/10 border-blue-500/30',
  };
  return (
    <span className={`inline-flex items-center px-2 py-0.5 rounded text-[10px] font-mono font-bold border uppercase ${m[severity] || m.info}`}>
      {severity}
    </span>
  );
}

export default function AssetDetailPage({ params }) {
  const router = useRouter();
  const assetId = params?.assetId;

  const [asset, setAsset]           = useState(null);
  const [readiness, setReadiness]   = useState(null);
  const [components, setComponents] = useState([]);
  const [sensors, setSensors]       = useState([]);
  const [predictions, setPredictions] = useState([]);
  const [alerts, setAlerts]         = useState([]);
  const [loading, setLoading]       = useState(true);
  const [evaluating, setEvaluating] = useState(false);
  const [notFound, setNotFound]     = useState(false);

  useEffect(() => {
    if (!isAuthenticated()) { router.replace('/login'); return; }
  }, [router]);

  const load = useCallback(async () => {
    if (!assetId) return;
    setLoading(true);
    try {
      const [a, r, c, s, p, al] = await Promise.allSettled([
        getAsset(assetId),
        getAssetReadiness(assetId),
        getAssetComponents(assetId),
        getAssetSensors(assetId),
        getAssetPredictions(assetId, 20),
        getAssetAlerts(assetId),
      ]);
      if (a.status === 'fulfilled')  setAsset(a.value);
      else if (a.reason?.message?.includes('not found')) setNotFound(true);
      if (r.status === 'fulfilled')  setReadiness(r.value);
      if (c.status === 'fulfilled')  setComponents(c.value || []);
      if (s.status === 'fulfilled')  setSensors(s.value || []);
      if (p.status === 'fulfilled')  setPredictions(p.value || []);
      if (al.status === 'fulfilled') setAlerts(al.value || []);
    } finally { setLoading(false); }
  }, [assetId]);

  useEffect(() => { load(); }, [load]);

  const handleEvaluate = async () => {
    setEvaluating(true);
    try { await evaluateAssetReadiness(assetId); await load(); }
    finally { setEvaluating(false); }
  };

  if (loading) return (
    <div className="min-h-screen bg-[#050811] flex items-center justify-center">
      <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
    </div>
  );

  if (notFound || !asset) return (
    <div className="min-h-screen bg-[#050811] flex flex-col items-center justify-center gap-4">
      <p className="text-slate-400 font-mono">Asset not found.</p>
      <button onClick={() => router.push('/assets')} className="text-blue-400 hover:text-blue-300 text-sm font-mono flex items-center gap-1">
        <ArrowLeft className="w-4 h-4" /> Back to Assets
      </button>
    </div>
  );

  const rulPred = predictions.find((p) => p.task === 'rul');
  const failPred = predictions.find((p) => p.task === 'failure');

  const predCards = [
    {
      label: 'Remaining Useful Life',
      value: rulPred?.prediction_value != null ? `${rulPred.prediction_value.toFixed(1)} h` : '—',
      sub: rulPred?.model_tag ? `Model: ${rulPred.model_tag}` : 'No RUL model run',
      icon: Activity,
      color: 'text-blue-400',
    },
    {
      label: 'Failure Risk (24h)',
      value: failPred?.probability != null ? `${Math.round(failPred.probability * 100)}%` : '—',
      sub: failPred?.risk_level ? `Level: ${failPred.risk_level.toUpperCase()}` : 'No risk model run',
      icon: AlertTriangle,
      color: failPred?.probability > 0.3 ? 'text-red-400' : 'text-amber-400',
    },
    {
      label: 'Readiness Engine',
      value: readiness?.status || 'UNKNOWN',
      sub: readiness?.confidence != null ? `${Math.round(readiness.confidence * 100)}% confidence` : '',
      icon: Shield,
      color: readiness?.status === 'READY' ? 'text-emerald-400' : 'text-amber-400',
    },
  ];

  return (
    <NavBar title={`Fleet / ${asset.asset_code}`} onBack={() => router.push('/assets')}>
      <div className="space-y-6">
        {/* Asset Header Card */}
        <div className="bg-[#0a0f1d]/80 border-[3px] border-white rounded-2xl p-6 lg:p-7 backdrop-blur-xl shadow-xl">
          <div className="flex items-start justify-between gap-6 flex-wrap">
            <div className="space-y-1.5">
              <div className="flex items-center gap-3 flex-wrap">
                <Plane className="w-6 h-6 text-blue-400" />
                <h1 className="text-3xl font-extrabold font-mono text-slate-100">{asset.asset_code}</h1>
                {readiness && <StatusBadge status={readiness.status} />}
              </div>
              <p className="text-slate-300 text-sm font-medium">
                {asset.asset_type}{asset.call_sign ? ` — ${asset.call_sign}` : ''}
                {asset.manufacturer ? ` · ${asset.manufacturer}` : ''}
              </p>
              {(asset.model_number || asset.serial_number) && (
                <p className="text-xs text-slate-400 font-mono">
                  {[asset.model_number, asset.serial_number].filter(Boolean).join(' / ')}
                </p>
              )}
            </div>

            <div className="flex items-center gap-6">
              <div className="text-right bg-slate-950/40 px-4 py-2 rounded-xl border border-slate-800">
                <p className="text-xs text-slate-400 font-mono">Total Hours</p>
                <p className="text-2xl font-bold font-mono text-slate-100 tabular-nums">{asset.total_hours?.toFixed(0) ?? '—'}</p>
              </div>
              {readiness?.confidence != null && (
                <div className="text-right bg-slate-950/40 px-4 py-2 rounded-xl border border-slate-800">
                  <p className="text-xs text-slate-400 font-mono">Confidence</p>
                  <p className="text-2xl font-bold font-mono text-slate-100 tabular-nums">{Math.round(readiness.confidence * 100)}%</p>
                </div>
              )}
              <button
                onClick={handleEvaluate}
                disabled={evaluating}
                className="flex items-center gap-2 text-xs font-mono font-bold text-blue-300 hover:text-blue-200 px-4 py-3 rounded-xl border border-blue-500/30 hover:border-blue-400/50 bg-blue-600/20 disabled:opacity-50 transition-all shadow-md"
              >
                <RefreshCw className={`w-4 h-4 ${evaluating ? 'animate-spin' : ''}`} />
                Re-evaluate
              </button>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left Column */}
          <div className="lg:col-span-2 space-y-6">
            {/* Predictions Card Box */}
            <div className="bg-[#0a0f1d]/80 border-[3px] border-white rounded-2xl p-6 backdrop-blur-xl shadow-xl">
              <h2 className="text-base font-bold font-mono uppercase text-slate-100 tracking-wider mb-4">ML Telemetry Predictions</h2>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {predCards.map(({ label, value, sub, icon: Icon, color }) => (
                  <div key={label} className="bg-slate-950/60 border border-slate-800/80 rounded-xl p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <Icon className={`w-4 h-4 ${color}`} />
                      <p className="text-xs text-slate-400 font-mono uppercase font-semibold">{label}</p>
                    </div>
                    <p className={`text-2xl font-bold font-mono tabular-nums ${color}`}>{value}</p>
                    <p className="text-xs text-slate-400 font-mono mt-1">{sub}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* Readiness Explanation Card Box */}
            {readiness?.contributing_factors?.length > 0 && (
              <div className="bg-[#0a0f1d]/80 border-[3px] border-white rounded-2xl p-6 backdrop-blur-xl shadow-xl">
                <h2 className="text-base font-bold font-mono uppercase text-slate-100 tracking-wider mb-1">
                  Readiness Diagnosis
                </h2>
                <p className="text-xs text-slate-400 font-mono mb-4">
                  Primary reason: <span className="text-slate-200 font-bold">{readiness.primary_reason}</span>
                </p>
                <div className="space-y-3">
                  {readiness.contributing_factors.map((factor, i) => (
                    <div key={i} className="bg-slate-950/60 border border-slate-800/80 rounded-xl p-4">
                      <div className="flex items-center gap-2 mb-1.5">
                        <SeverityBadge severity={factor.severity} />
                        <span className="text-xs text-slate-300 font-mono font-bold">{factor.code}</span>
                      </div>
                      <p className="text-xs text-slate-200">{factor.message}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Right Column */}
          <div className="space-y-6">
            {/* Components Card Box */}
            <div className="bg-[#0a0f1d]/80 border-[3px] border-white rounded-2xl p-5 backdrop-blur-xl shadow-xl">
              <h2 className="text-sm font-bold font-mono uppercase text-slate-100 tracking-wider mb-3">
                Sub-Components ({components.length})
              </h2>
              {components.length === 0 ? (
                <p className="text-xs text-slate-400 font-mono">No components registered.</p>
              ) : (
                <div className="space-y-2.5">
                  {components.map((c) => (
                    <div key={c.id} className="bg-slate-950/60 border border-slate-800/80 rounded-xl p-3">
                      <p className="text-xs font-mono font-bold text-slate-100">{c.component_code}</p>
                      <p className="text-xs text-slate-400">{c.name}</p>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Metadata Card Box */}
            <div className="bg-[#0a0f1d]/80 border-[3px] border-white rounded-2xl p-5 backdrop-blur-xl shadow-xl">
              <h2 className="text-sm font-bold font-mono uppercase text-slate-100 tracking-wider mb-3">Metadata</h2>
              <div className="divide-y divide-slate-800/50 text-xs font-mono">
                {[
                  ['Active', asset.is_active ? 'Yes' : 'No'],
                  ['Commission', asset.commission_date || '—'],
                  ['Manufacturer', asset.manufacturer || '—'],
                  ['Model', asset.model_number || '—'],
                  ['Serial', asset.serial_number || '—'],
                ].map(([l, v]) => (
                  <div key={l} className="flex justify-between py-2">
                    <span className="text-slate-400">{l}</span>
                    <span className="text-slate-200 font-bold">{v}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </div>
    </NavBar>
  );
}
