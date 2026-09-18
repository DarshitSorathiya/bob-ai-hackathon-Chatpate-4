'use client';

import React, { useMemo } from 'react';
import Image from 'next/image';
import Link from 'next/link';

/**
 * Tactical SVG Radar Scope + Fleet Status Progress Bars component matching Image 1.
 */
export default function FleetRadarScope({ assets = [], readinessMap = {}, loadingData = false, countsOverride }) {
  const targets = useMemo(() => {
    if (!assets || assets.length === 0) {
      // Default radar blips matching Picture 1 setup
      return [
        { id: 1, cx: 100, cy: 110, status: 'READY', colors: { dot: '#34d399', glow: 'rgba(52, 211, 153, 0.4)' } },
        { id: 2, cx: 180, cy: 90, status: 'READY', colors: { dot: '#34d399', glow: 'rgba(52, 211, 153, 0.4)' } },
        { id: 3, cx: 160, cy: 190, status: 'AT_RISK', colors: { dot: '#f87171', glow: 'rgba(248, 113, 113, 0.5)' } },
        { id: 4, cx: 85, cy: 175, status: 'NOT_READY', colors: { dot: '#fbbf24', glow: 'rgba(251, 191, 36, 0.5)' } },
        { id: 5, cx: 200, cy: 150, status: 'READY', colors: { dot: '#34d399', glow: 'rgba(52, 211, 153, 0.4)' } },
      ];
    }

    return assets.map((asset, index) => {
      const rec = readinessMap[asset.id] || {};
      const status = rec.status || 'READY';

      const angleStep = (2 * Math.PI) / Math.max(assets.length, 1);
      const angle = index * angleStep - Math.PI / 2;
      const distPercent = 0.3 + ((index * 0.17) % 0.5);

      const cx = 140 + Math.cos(angle) * (110 * distPercent);
      const cy = 140 + Math.sin(angle) * (110 * distPercent);

      const colorMap = {
        READY:     { dot: '#34d399', glow: 'rgba(52, 211, 153, 0.4)' },
        AT_RISK:   { dot: '#f87171', glow: 'rgba(248, 113, 113, 0.5)' },
        NOT_READY: { dot: '#fbbf24', glow: 'rgba(251, 191, 36, 0.5)' },
        UNKNOWN:   { dot: '#94a3b8', glow: 'rgba(148, 163, 184, 0.3)' },
      };

      return {
        ...asset,
        status,
        cx,
        cy,
        colors: colorMap[status] || colorMap.READY,
      };
    });
  }, [assets, readinessMap]);

  const counts = useMemo(() => {
    if (countsOverride) return countsOverride;
    return {
      READY: 18,
      AT_RISK: 4,
      NOT_READY: 3,
    };
  }, [countsOverride]);

  const total = (counts.READY || 0) + (counts.AT_RISK || 0) + (counts.NOT_READY || 0) || 25;
  const readyPercent = Math.round(((counts.READY || 18) / total) * 100);
  const atRiskPercent = Math.round(((counts.AT_RISK || 4) / total) * 100);
  const notReadyPercent = Math.round(((counts.NOT_READY || 3) / total) * 100);

  return (
    <div className="dashboard-card-shape p-6 flex flex-col justify-between h-full transition-all duration-200">
      {/* Header matching Picture 1 */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-blue-400 light:text-blue-700 block mb-1">
            FLEET READINESS
          </span>
          <h2 className="text-lg font-bold font-sans text-slate-100 dark:text-slate-100 light:text-slate-900">
            Fleet Status Overview
          </h2>
        </div>
        <Link
          href="/assets"
          className="px-4 py-1.5 rounded-full border border-blue-500/30 dark:border-blue-500/30 light:border-blue-300 bg-blue-950/40 dark:bg-blue-950/40 light:bg-blue-50 text-xs font-mono text-blue-400 light:text-blue-600 hover:bg-blue-600/20 light:hover:bg-blue-100 transition-colors flex items-center gap-1"
        >
          View All →
        </Link>
      </div>

      {/* Main Content Row: Left Radar Scope + Right Status Progress Bars */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-center my-auto py-2">
        {/* Radar Scope */}
        <div className="relative w-60 h-60 mx-auto shrink-0 flex items-center justify-center">
          <svg viewBox="0 0 280 280" className="w-full h-full text-blue-400/25 light:text-blue-600/30">
            <defs>
              <radialGradient id="sweepGrad" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="#38bdf8" stopOpacity="0.25" />
                <stop offset="80%" stopColor="#38bdf8" stopOpacity="0.05" />
                <stop offset="100%" stopColor="#38bdf8" stopOpacity="0" />
              </radialGradient>
            </defs>

            {/* Concentric Radar Rings */}
            <circle cx="140" cy="140" r="125" fill="none" stroke="currentColor" strokeWidth="1" strokeDasharray="4 4" />
            <circle cx="140" cy="140" r="95"  fill="none" stroke="currentColor" strokeWidth="1" opacity="0.6" />
            <circle cx="140" cy="140" r="60"  fill="none" stroke="currentColor" strokeWidth="1" strokeDasharray="4 4" opacity="0.4" />
            <circle cx="140" cy="140" r="25"  fill="none" stroke="currentColor" strokeWidth="1" opacity="0.3" />

            {/* Crosshairs */}
            <line x1="140" y1="10" x2="140" y2="270" stroke="currentColor" strokeWidth="0.8" opacity="0.4" />
            <line x1="10" y1="140" x2="270" y2="140" stroke="currentColor" strokeWidth="0.8" opacity="0.4" />

            {/* Rotating Beam */}
            <g className="origin-center animate-[spin_8s_linear_infinite]">
              <path d="M 140 140 L 140 15 A 125 125 0 0 1 228 52 Z" fill="url(#sweepGrad)" />
              <line x1="140" y1="140" x2="140" y2="15" stroke="#38bdf8" strokeWidth="1.5" opacity="0.8" />
            </g>

            {/* Target Blips */}
            {targets.map((t) => (
              <g key={t.id}>
                <circle
                  cx={t.cx}
                  cy={t.cy}
                  r="7"
                  fill={t.colors.glow}
                  className={t.status === 'AT_RISK' || t.status === 'NOT_READY' ? 'animate-ping' : ''}
                  style={{ animationDuration: '3s' }}
                />
                <circle cx={t.cx} cy={t.cy} r="3.5" fill={t.colors.dot} stroke="#040814" strokeWidth="1" />
              </g>
            ))}
          </svg>

          {/* Center Airplane Silhouette matching Picture 1 */}
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="relative w-12 h-12 filter drop-shadow-[0_0_12px_rgba(56,189,248,0.9)]">
              <Image
                src="/images/aircraft.png"
                alt="Fleet Radar Center"
                fill
                className="object-contain"
              />
            </div>
          </div>
        </div>

        {/* Status Progress Bars matching Picture 1 */}
        <div className="space-y-6 font-mono text-xs w-full pl-0 md:pl-2">
          {/* Row 1: Ready */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-slate-200 dark:text-slate-200 light:text-slate-800">
              <span className="flex items-center gap-2.5 font-semibold text-sm">
                <span className="w-2.5 h-2.5 rounded-full bg-emerald-400 shadow-sm shadow-emerald-400/50" />
                Ready
              </span>
              <span className="text-base font-extrabold text-slate-100 dark:text-slate-100 light:text-slate-900 font-mono">
                {loadingData ? '18' : (counts.READY ?? 18)}
              </span>
            </div>
            <div className="w-full bg-[#050b18] dark:bg-[#050b18] light:bg-slate-200 rounded-full h-2 overflow-hidden border border-blue-900/30 dark:border-blue-900/30 light:border-slate-300">
              <div
                className="bg-emerald-400 h-full rounded-full transition-all duration-500 shadow-sm shadow-emerald-400/50"
                style={{ width: `${readyPercent}%` }}
              />
            </div>
          </div>

          {/* Row 2: At Risk */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-slate-200 dark:text-slate-200 light:text-slate-800">
              <span className="flex items-center gap-2.5 font-semibold text-sm">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-400 shadow-sm shadow-amber-400/50" />
                At Risk
              </span>
              <span className="text-base font-extrabold text-slate-100 dark:text-slate-100 light:text-slate-900 font-mono">
                {loadingData ? '4' : (counts.AT_RISK ?? 4)}
              </span>
            </div>
            <div className="w-full bg-[#050b18] dark:bg-[#050b18] light:bg-slate-200 rounded-full h-2 overflow-hidden border border-blue-900/30 dark:border-blue-900/30 light:border-slate-300">
              <div
                className="bg-amber-400 h-full rounded-full transition-all duration-500 shadow-sm shadow-amber-400/50"
                style={{ width: `${atRiskPercent}%` }}
              />
            </div>
          </div>

          {/* Row 3: Not Ready */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-slate-200 dark:text-slate-200 light:text-slate-800">
              <span className="flex items-center gap-2.5 font-semibold text-sm">
                <span className="w-2.5 h-2.5 rounded-full bg-red-400 shadow-sm shadow-red-400/50" />
                Not Ready
              </span>
              <span className="text-base font-extrabold text-slate-100 dark:text-slate-100 light:text-slate-900 font-mono">
                {loadingData ? '3' : (counts.NOT_READY ?? 3)}
              </span>
            </div>
            <div className="w-full bg-[#050b18] dark:bg-[#050b18] light:bg-slate-200 rounded-full h-2 overflow-hidden border border-blue-900/30 dark:border-blue-900/30 light:border-slate-300">
              <div
                className="bg-red-400 h-full rounded-full transition-all duration-500 shadow-sm shadow-red-400/50"
                style={{ width: `${notReadyPercent}%` }}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
