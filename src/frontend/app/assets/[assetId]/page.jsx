'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { ArrowLeft, RefreshCw, Loader2, AlertTriangle, CheckCircle2, HelpCircle } from 'lucide-react';
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
    <div className="min-h-screen bg-[#070a12] flex items-center justify-center">
      <Loader2 className="w-8 h-8 text-blue-400 animate-spin" />
    </div>
  );

  if (notFound || !asset) return (
    <div className="min-h-screen bg-[#070a12] flex flex-col items-center justify-center gap-4">
      <p className="text-slate-400 font-mono">Asset not found.</p>
      <button onClick={() => router.push('/assets')} className="text-blue-400 hover:text-blue-300 text-sm font-mono flex items-center gap-1">
        <ArrowLeft className="w-4 h-4" /> Back to Assets
      </button>
    </div>
  );

  const latestRUL     = predictions.find((p) => p.prediction_type === 'RUL');
  const latestRisk    = predictions.find((p) => p.prediction_type === 'FAILURE_RISK');
  const latestAnomaly = predictions.find((p) => p.prediction_type === 'ANOMALY');

  const predCards = [
    {
      label: 'RUL Estimate',
      value: latestRUL ? `${latestRUL.rul_estimate?.toFixed(0)} h` : '—',
      sub: latestRUL ? `CI [${latestRUL.rul_lower?.toFixed(0)}, ${latestRUL.rul_upper?.toFixed(0)}] h` : 'No prediction available',
      icon: CheckCircle2,
      color: latestRUL ? 'text-emerald-400' : 'text-slate-500',
    },
    {
      label: 'Failure Risk',
      value: latestRisk ? `${(latestRisk.failure_probability * 100).toFixed(1)}%` : '—',
      sub: latestRisk ? `Confidence ${Math.round(latestRisk.confidence * 100)}%` : 'No prediction available',
      icon: AlertTriangle,
      color: !latestRisk ? 'text-slate-500' : latestRisk.failure_probability > 0.45 ? 'text-red-400' : latestRisk.failure_probability > 0.15 ? 'text-amber-400' : 'text-emerald-400',
    },
    {
      label: 'Anomaly Score',
      value: latestAnomaly ? latestAnomaly.anomaly_score?.toFixed(3) : '—',
      sub: latestAnomaly ? new Date(latestAnomaly.predicted_at).toLocaleDateString() : 'No prediction available',
      icon: HelpCircle,
      color: !latestAnomaly ? 'text-slate-500' : latestAnomaly.anomaly_score > 0.7 ? 'text-amber-400' : 'text-slate-400',
    },
  ];

  return (
    <div className="min-h-screen bg-[#070a12] text-slate-100 font-sans">
      <NavBar
        title={asset.asset_code}
        onBack={() => router.push('/assets')}
      />

      <main className="max-w-7xl mx-auto px-4 sm:px-6 py-6 space-y-6">
        {/* Asset header card */}
        <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-6">
          <div className="flex items-start justify-between gap-4 flex-wrap">
            <div>
              <div className="flex items-center gap-3 mb-1 flex-wrap">
                <h1 className="text-2xl font-bold font-mono">{asset.asset_code}</h1>
                {readiness && <StatusBadge status={readiness.status} />}
              </div>
              <p className="text-slate-400 text-sm">
                {asset.asset_type}{asset.call_sign ? ` — ${asset.call_sign}` : ''}
                {asset.manufacturer ? ` · ${asset.manufacturer}` : ''}
              </p>
              {(asset.model_number || asset.serial_number) && (
                <p className="text-[11px] text-slate-600 font-mono mt-0.5">
                  {[asset.model_number, asset.serial_number].filter(Boolean).join(' / ')}
                </p>
              )}
            </div>
            <div className="flex items-center gap-6">
              <div className="text-right">
                <p className="text-[11px] text-slate-500 font-mono">Total Hours</p>
                <p className="text-2xl font-bold font-mono tabular-nums">{asset.total_hours?.toFixed(0) ?? '—'}</p>
              </div>
              {readiness?.confidence != null && (
                <div className="text-right">
                  <p className="text-[11px] text-slate-500 font-mono">Confidence</p>
                  <p className="text-2xl font-bold font-mono tabular-nums">{Math.round(readiness.confidence * 100)}%</p>
                </div>
              )}
              <button
                onClick={handleEvaluate}
                disabled={evaluating}
                className="flex items-center gap-1.5 text-[11px] font-mono text-blue-400 hover:text-blue-300 px-3 py-2 rounded-lg border border-blue-500/30 hover:border-blue-400/50 disabled:opacity-50 transition-colors"
              >
                <RefreshCw className={`w-3.5 h-3.5 ${evaluating ? 'animate-spin' : ''}`} />
                Re-evaluate
              </button>
            </div>
          </div>
        </div>

        <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Left column */}
          <div className="lg:col-span-2 space-y-6">
            {/* Predictions */}
            <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-5">
              <h2 className="text-sm font-bold font-mono uppercase text-slate-300 tracking-wider mb-4">ML Predictions</h2>
              <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
                {predCards.map(({ label, value, sub, icon: Icon, color }) => (
                  <div key={label} className="bg-slate-900/60 border border-slate-800 rounded-lg p-4">
                    <div className="flex items-center gap-2 mb-2">
                      <Icon className={`w-4 h-4 ${color}`} />
                      <p className="text-[11px] text-slate-400 font-mono uppercase">{label}</p>
                    </div>
                    <p className={`text-2xl font-bold font-mono tabular-nums ${color}`}>{value}</p>
                    <p className="text-[11px] text-slate-500 font-mono mt-1">{sub}</p>
                  </div>
                ))}
              </div>
              {predictions.length === 0 && (
                <p className="text-sm text-slate-500 font-mono text-center py-4 mt-2">
                  No predictions available. Trigger evaluation via the Re-evaluate button or the
                  <code className="text-blue-300 mx-1">POST /api/v1/readiness/evaluate/{'{assetId}'}</code> endpoint.
                </p>
              )}
            </div>

            {/* Readiness explanation */}
            {readiness?.contributing_factors?.length > 0 && (
              <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-5">
                <h2 className="text-sm font-bold font-mono uppercase text-slate-300 tracking-wider mb-1">
                  Readiness Explanation
                </h2>
                <p className="text-[11px] text-slate-500 font-mono mb-4">
                  Primary reason: <span className="text-slate-300">{readiness.primary_reason}</span>
                  {readiness.evaluated_at && (
                    <> · Evaluated {new Date(readiness.evaluated_at).toLocaleString()}</>
                  )}
                </p>
                <div className="space-y-3">
                  {readiness.contributing_factors.map((factor, i) => (
                    <div key={i} className="bg-slate-900/60 border border-slate-800/60 rounded-lg p-3">
                      <div className="flex items-center gap-2 mb-1">
                        <SeverityBadge severity={factor.severity} />
                        <span className="text-[11px] text-slate-400 font-mono">{factor.code}</span>
                      </div>
                      <p className="text-xs text-slate-300">{factor.message}</p>
                      {Object.keys(factor.evidence || {}).length > 0 && (
                        <details className="mt-1.5">
                          <summary className="text-[10px] text-slate-500 font-mono cursor-pointer hover:text-slate-400">Evidence</summary>
                          <pre className="text-[10px] text-slate-500 font-mono mt-1 overflow-x-auto">{JSON.stringify(factor.evidence, null, 2)}</pre>
                        </details>
                      )}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Alerts */}
            {alerts.length > 0 && (
              <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-5">
                <h2 className="text-sm font-bold font-mono uppercase text-slate-300 tracking-wider mb-4">Active Alerts</h2>
                <div className="space-y-2">
                  {alerts.map((alert) => (
                    <div key={alert.id} className={`border rounded-lg p-3 ${
                      alert.severity === 'critical' ? 'bg-red-950/20 border-red-900/50' :
                      alert.severity === 'warning'  ? 'bg-amber-950/20 border-amber-900/50' :
                      'bg-slate-900/60 border-slate-800/60'
                    }`}>
                      <div className="flex items-center justify-between gap-2 flex-wrap">
                        <SeverityBadge severity={alert.severity} />
                        <span className="text-[10px] text-slate-500 font-mono">
                          {new Date(alert.created_at).toLocaleString()}
                        </span>
                      </div>
                      <p className="text-sm font-semibold text-slate-200 mt-1">{alert.title}</p>
                      <p className="text-xs text-slate-400 mt-0.5">{alert.message}</p>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>

          {/* Right column */}
          <div className="space-y-4">
            {/* Components */}
            <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-4">
              <h2 className="text-sm font-bold font-mono uppercase text-slate-300 tracking-wider mb-3">
                Components <span className="text-slate-600 font-normal">({components.length})</span>
              </h2>
              {components.length === 0 ? (
                <p className="text-xs text-slate-500 font-mono">No components registered.</p>
              ) : (
                <div className="space-y-2">
                  {components.map((c) => (
                    <div key={c.id} className="bg-slate-900/60 border border-slate-800/60 rounded-lg p-3">
                      <p className="text-xs font-mono font-semibold text-slate-200">{c.component_code}</p>
                      <p className="text-[11px] text-slate-400">{c.name}</p>
                      <div className="flex items-center justify-between mt-0.5">
                        <span className="text-[10px] text-slate-600 font-mono">{c.component_type}</span>
                        <span className="text-[10px] text-slate-500 font-mono">{c.total_hours?.toFixed(0)} h</span>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Sensors */}
            <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-4">
              <h2 className="text-sm font-bold font-mono uppercase text-slate-300 tracking-wider mb-3">
                Sensors <span className="text-slate-600 font-normal">({sensors.length})</span>
              </h2>
              {sensors.length === 0 ? (
                <p className="text-xs text-slate-500 font-mono">No sensors registered.</p>
              ) : (
                <div className="divide-y divide-slate-800/50">
                  {sensors.map((s) => (
                    <div key={s.id} className="flex items-center justify-between py-2">
                      <div>
                        <p className="text-[11px] font-mono text-slate-200">{s.sensor_code}</p>
                        <p className="text-[10px] text-slate-500">{s.sensor_type}</p>
                      </div>
                      <div className="text-right">
                        <p className="text-[10px] text-slate-500 font-mono">{s.unit || '—'}</p>
                        {s.nominal_min != null && s.nominal_max != null && (
                          <p className="text-[9px] text-slate-600 font-mono">[{s.nominal_min}, {s.nominal_max}]</p>
                        )}
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>

            {/* Asset metadata */}
            <div className="bg-slate-900/40 border border-slate-800 rounded-xl p-4">
              <h2 className="text-sm font-bold font-mono uppercase text-slate-300 tracking-wider mb-3">Metadata</h2>
              <div className="divide-y divide-slate-800/50 text-[11px] font-mono">
                {[
                  ['Active', asset.is_active ? 'Yes' : 'No'],
                  ['Commission', asset.commission_date || '—'],
                  ['Manufacturer', asset.manufacturer || '—'],
                  ['Model', asset.model_number || '—'],
                  ['Serial', asset.serial_number || '—'],
                ].map(([l, v]) => (
                  <div key={l} className="flex justify-between py-1.5">
                    <span className="text-slate-500">{l}</span>
                    <span className="text-slate-300">{v}</span>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </main>
    </div>
  );
}
