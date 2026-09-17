'use client';

import React, { useMemo } from 'react';
import Image from 'next/image';
import { Shield } from 'lucide-react';

/**
 * Tactical SVG Radar Scope HUD matching Reference "Fleet Status" panel.
 * Uses translucent dark glass container with background blur.
 */
export default function FleetRadarScope({ assets = [], readinessMap = {}, loadingData = false }) {
  const targets = useMemo(() => {
    if (!assets || assets.length === 0) return [];

    return assets.map((asset, index) => {
      const rec = readinessMap[asset.id] || {};
      const status = rec.status || 'UNKNOWN';

      const angleStep = (2 * Math.PI) / Math.max(assets.length, 1);
      const angle = index * angleStep - Math.PI / 2;
      const distPercent = 0.35 + ((index * 0.17) % 0.5);

      const cx = 140 + Math.cos(angle) * (110 * distPercent);
      const cy = 140 + Math.sin(angle) * (110 * distPercent);

      const colorMap = {
        READY:     { dot: '#34d399', glow: 'rgba(52, 211, 153, 0.35)' },
        AT_RISK:   { dot: '#f87171', glow: 'rgba(248, 113, 113, 0.4)' },
        NOT_READY: { dot: '#fbbf24', glow: 'rgba(251, 191, 36, 0.4)' },
        UNKNOWN:   { dot: '#94a3b8', glow: 'rgba(148, 163, 184, 0.25)' },
      };

      return {
        ...asset,
        status,
        cx,
        cy,
        colors: colorMap[status] || colorMap.UNKNOWN,
      };
    });
  }, [assets, readinessMap]);

  const counts = useMemo(() => {
    const c = { READY: 0, AT_RISK: 0, NOT_READY: 0, UNKNOWN: 0 };
    targets.forEach((t) => {
      c[t.status] = (c[t.status] || 0) + 1;
    });
    return c;
  }, [targets]);

  return (
    <div className="bg-[#0a0f1d]/75 border-[3px] border-white rounded-2xl p-5 backdrop-blur-xl shadow-xl flex flex-col justify-between h-full transition-all duration-200">
      {/* Header matching Reference */}
      <div className="flex items-center gap-3.5 mb-2">
        <div className="w-8 h-8 rounded-full bg-blue-600/15 border border-blue-500/30 flex items-center justify-center text-blue-400 shrink-0 shadow-sm shadow-blue-500/10">
          <Shield className="w-4 h-4" />
        </div>
        <h2 className="text-xs font-mono font-bold uppercase tracking-wider text-slate-200">
          Fleet Status
        </h2>
      </div>

      {/* Center Radar Scope + Side Legend Layout */}
      <div className="flex flex-col sm:flex-row items-center justify-between gap-4 my-2">
        {/* Radar Scope */}
        <div className="relative w-52 h-52 shrink-0 flex items-center justify-center">
          <svg viewBox="0 0 280 280" className="w-full h-full text-blue-500/20">
            <defs>
              <radialGradient id="sweepGrad" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.18" />
                <stop offset="80%" stopColor="#38bdf8" stopOpacity="0.03" />
                <stop offset="100%" stopColor="#38bdf8" stopOpacity="0" />
              </radialGradient>
            </defs>

            {/* Concentric Rings */}
            <circle cx="140" cy="140" r="120" fill="none" stroke="currentColor" strokeWidth="1" strokeDasharray="3 3" />
            <circle cx="140" cy="140" r="85"  fill="none" stroke="currentColor" strokeWidth="1" opacity="0.6" />
            <circle cx="140" cy="140" r="50"  fill="none" stroke="currentColor" strokeWidth="1" strokeDasharray="4 4" opacity="0.4" />
            <circle cx="140" cy="140" r="20"  fill="none" stroke="currentColor" strokeWidth="1" opacity="0.3" />

            {/* Crosshairs */}
            <line x1="140" y1="10" x2="140" y2="270" stroke="currentColor" strokeWidth="0.8" opacity="0.4" />
            <line x1="10" y1="140" x2="270" y2="140" stroke="currentColor" strokeWidth="0.8" opacity="0.4" />

            {/* Rotating Beam */}
            <g className="origin-center animate-[spin_10s_linear_infinite]">
              <path d="M 140 140 L 140 20 A 120 120 0 0 1 225 55 Z" fill="url(#sweepGrad)" />
              <line x1="140" y1="140" x2="140" y2="20" stroke="#38bdf8" strokeWidth="1.2" opacity="0.7" />
            </g>

            {/* Target Blips */}
            {!loadingData && targets.map((t) => (
              <g key={t.id}>
                <circle
                  cx={t.cx}
                  cy={t.cy}
                  r="6"
                  fill={t.colors.glow}
                  className={t.status === 'AT_RISK' || t.status === 'NOT_READY' ? 'animate-ping' : ''}
                  style={{ animationDuration: '3s' }}
                />
                <circle cx={t.cx} cy={t.cy} r="3" fill={t.colors.dot} stroke="#070a12" strokeWidth="0.8" />
              </g>
            ))}
          </svg>

          {/* Center Aircraft Graphic Silhouette */}
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="relative w-10 h-10 opacity-75 filter drop-shadow-[0_0_6px_rgba(56,189,248,0.5)]">
              <Image
                src="/images/aircraft.png"
                alt="Center Fleet Command"
                fill
                className="object-contain"
              />
            </div>
          </div>
        </div>

        {/* Status Key Legend matching Reference */}
        <div className="w-full sm:w-auto flex-1 space-y-2.5 font-mono text-xs text-slate-300">
          <div className="flex items-center justify-between gap-4 p-2 rounded-lg bg-slate-950/40 border border-slate-800/60">
            <span className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-emerald-400" /> Ready
            </span>
            <span className="font-bold text-slate-100">{loadingData ? '…' : counts.READY}</span>
          </div>

          <div className="flex items-center justify-between gap-4 p-2 rounded-lg bg-slate-950/40 border border-slate-800/60">
            <span className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-red-400" /> At Risk
            </span>
            <span className="font-bold text-slate-100">{loadingData ? '…' : counts.AT_RISK}</span>
          </div>

          <div className="flex items-center justify-between gap-4 p-2 rounded-lg bg-slate-950/40 border border-slate-800/60">
            <span className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-amber-400" /> Not Ready
            </span>
            <span className="font-bold text-slate-100">{loadingData ? '…' : counts.NOT_READY}</span>
          </div>

          <div className="flex items-center justify-between gap-4 p-2 rounded-lg bg-slate-950/40 border border-slate-800/60">
            <span className="flex items-center gap-2">
              <span className="w-2 h-2 rounded-full bg-slate-500" /> Offline
            </span>
            <span className="font-bold text-slate-100">{loadingData ? '…' : counts.UNKNOWN}</span>
          </div>
        </div>
      </div>
    </div>
  );
}
