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
      return [];
    }

    return assets.map((asset, index) => {
      const rec = readinessMap[asset.id] || {};
      const status = rec.status || asset.status || 'READY';

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
    const c = { READY: 0, AT_RISK: 0, NOT_READY: 0 };
    if (assets && assets.length > 0) {
      assets.forEach((asset) => {
        const rec = readinessMap[asset.id] || {};
        const status = rec.status || asset.status || 'READY';
        if (c[status] !== undefined) c[status]++;
        else c.READY++;
      });
    }
    return c;
  }, [countsOverride, assets, readinessMap]);

  const total = (counts.READY || 0) + (counts.AT_RISK || 0) + (counts.NOT_READY || 0);
  const readyPercent = total > 0 ? Math.round(((counts.READY || 0) / total) * 100) : 0;
  const atRiskPercent = total > 0 ? Math.round(((counts.AT_RISK || 0) / total) * 100) : 0;
  const notReadyPercent = total > 0 ? Math.round(((counts.NOT_READY || 0) / total) * 100) : 0;

  return (
    <div className="dashboard-card-shape p-6 flex flex-col justify-between h-full transition-all duration-200">
      {/* Header matching Picture 1 */}
      <div className="flex items-center justify-between mb-4">
        <div>
          <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#1e4d35] dark:text-[#4e9f76] block mb-1">
            FLEET READINESS
          </span>
          <h2 className="text-lg font-bold font-sans text-[#122018] dark:text-slate-100">
            Fleet Status Overview
          </h2>
        </div>
        <Link
          href="/assets"
          className="px-4 py-1.5 rounded-full border border-[#1e4d35]/30 dark:border-[#4e9f76]/40 bg-[#e1eadf] dark:bg-[#1e4d35]/40 text-xs font-mono text-[#1e4d35] dark:text-[#4e9f76] hover:bg-[#1e4d35] hover:text-white transition-colors flex items-center gap-1"
        >
          View All →
        </Link>
      </div>

      {/* Main Content Row: Left Radar Scope + Right Status Progress Bars */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-6 items-center my-auto py-2">
        {/* Radar Scope */}
        <div className="relative w-60 h-60 mx-auto shrink-0 flex items-center justify-center">
          <svg viewBox="0 0 280 280" className="w-full h-full text-[#1e4d35]/30 dark:text-[#4e9f76]/40">
            <defs>
              <radialGradient id="sweepGrad" cx="50%" cy="50%" r="50%">
                <stop offset="0%" stopColor="#4e9f76" stopOpacity="0.3" />
                <stop offset="80%" stopColor="#4e9f76" stopOpacity="0.08" />
                <stop offset="100%" stopColor="#4e9f76" stopOpacity="0" />
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
            <g className="origin-center animate-[spin_14s_linear_infinite]">
              <path d="M 140 140 L 140 15 A 125 125 0 0 1 228 52 Z" fill="url(#sweepGrad)" />
              <line x1="140" y1="140" x2="140" y2="15" stroke="#4e9f76" strokeWidth="1.5" opacity="0.8" />
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
                <circle cx={t.cx} cy={t.cy} r="3.5" fill={t.colors.dot} stroke="#122018" strokeWidth="1" />
              </g>
            ))}
          </svg>

          {/* Center Airplane Silhouette matching Picture 1 */}
          <div className="absolute inset-0 flex items-center justify-center pointer-events-none">
            <div className="relative w-6 h-6 filter drop-shadow-[0_0_8px_rgba(78,159,118,0.8)]">
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
            <div className="flex items-center justify-between text-[#122018] dark:text-slate-200">
              <span className="flex items-center gap-2.5 font-semibold text-sm">
                <span className="w-2.5 h-2.5 rounded-full bg-[#2d9f6f] shadow-sm shadow-[#2d9f6f]/50" />
                Ready
              </span>
              <span className="text-base font-extrabold text-[#122018] dark:text-slate-100 font-mono">
                {loadingData ? '...' : (counts.READY ?? 0)}
              </span>
            </div>
            <div className="w-full bg-[#e1eadf] dark:bg-[#0d1b13] rounded-full h-2 overflow-hidden border border-[#1e4d35]/20 dark:border-[#4e9f76]/30">
              <div
                className="bg-[#2d9f6f] h-full rounded-full transition-all duration-500 shadow-sm shadow-[#2d9f6f]/50"
                style={{ width: `${readyPercent}%` }}
              />
            </div>
          </div>

          {/* Row 2: At Risk */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-[#122018] dark:text-slate-200">
              <span className="flex items-center gap-2.5 font-semibold text-sm">
                <span className="w-2.5 h-2.5 rounded-full bg-amber-500 shadow-sm shadow-amber-500/50" />
                At Risk
              </span>
              <span className="text-base font-extrabold text-[#122018] dark:text-slate-100 font-mono">
                {loadingData ? '...' : (counts.AT_RISK ?? 0)}
              </span>
            </div>
            <div className="w-full bg-[#e1eadf] dark:bg-[#0d1b13] rounded-full h-2 overflow-hidden border border-[#1e4d35]/20 dark:border-[#4e9f76]/30">
              <div
                className="bg-amber-500 h-full rounded-full transition-all duration-500 shadow-sm shadow-amber-500/50"
                style={{ width: `${atRiskPercent}%` }}
              />
            </div>
          </div>

          {/* Row 3: Not Ready */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between text-[#122018] dark:text-slate-200">
              <span className="flex items-center gap-2.5 font-semibold text-sm">
                <span className="w-2.5 h-2.5 rounded-full bg-red-500 shadow-sm shadow-red-500/50" />
                Not Ready
              </span>
              <span className="text-base font-extrabold text-[#122018] dark:text-slate-100 font-mono">
                {loadingData ? '...' : (counts.NOT_READY ?? 0)}
              </span>
            </div>
            <div className="w-full bg-[#e1eadf] dark:bg-[#0d1b13] rounded-full h-2 overflow-hidden border border-[#1e4d35]/20 dark:border-[#4e9f76]/30">
              <div
                className="bg-red-500 h-full rounded-full transition-all duration-500 shadow-sm shadow-red-500/50"
                style={{ width: `${notReadyPercent}%` }}
              />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
