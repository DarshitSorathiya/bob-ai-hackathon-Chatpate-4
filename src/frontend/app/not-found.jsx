'use client';

import React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { AlertTriangle, ArrowLeft, Home, Compass, ShieldAlert } from 'lucide-react';
import TopNavbar from '../components/TopNavbar';
import './globals.css';

export default function NotFound() {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-[#030712] dark:bg-[#030712] light:bg-[#f8fafc] text-slate-100 dark:text-slate-100 light:text-slate-900 font-sans flex flex-col selection:bg-blue-600/30 relative overflow-hidden transition-colors duration-200">
      {/* 1. Full-Screen Background Atmospheric Overlay Layer */}
      <div className="fixed inset-0 bg-[url('/images/landing-bg.png')] bg-cover bg-center opacity-20 dark:opacity-20 light:opacity-5 pointer-events-none z-0" />
      <div className="fixed inset-0 bg-gradient-to-b from-[#030712]/90 via-[#030712]/80 to-[#030712]/95 dark:from-[#030712]/90 dark:via-[#030712]/80 dark:to-[#030712]/95 light:from-slate-50/90 light:via-slate-100/80 light:to-slate-100/95 pointer-events-none z-0" />

      {/* 2. Top Header Navigation Shell */}
      <TopNavbar />

      {/* 3. Central 404 Mission Control Error HUD */}
      <main className="flex-1 flex items-center justify-center p-4 sm:p-6 lg:p-8 relative z-10 w-full max-w-[1140px] mx-auto">
        <div className="w-full max-w-lg bg-[#0a0f1d]/85 dark:bg-[#0a0f1d]/85 light:bg-white/95 border border-white/20 dark:border-white/20 light:border-slate-300 rounded-2xl p-6 sm:p-8 lg:p-10 backdrop-blur-xl shadow-2xl dark:shadow-black/60 light:shadow-slate-300/40 text-center flex flex-col items-center space-y-5 transition-all">
          
          {/* Glowing Radar Error Icon Badge */}
          <div className="relative flex items-center justify-center">
            <div className="w-16 h-16 rounded-full bg-amber-500/10 border border-amber-500/30 flex items-center justify-center text-amber-400 light:text-amber-600 shadow-lg shadow-amber-500/20 animate-pulse">
              <ShieldAlert className="w-8 h-8" />
            </div>
            <div className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-red-600 border border-[#0a0f1d] flex items-center justify-center text-[10px] font-mono font-bold text-white">
              !
            </div>
          </div>

          {/* Status Tag Badge */}
          <span className="inline-flex items-center gap-2 px-3 py-1 rounded-full text-[11px] font-mono font-bold uppercase tracking-widest bg-red-950/80 dark:bg-red-950/80 light:bg-red-100 text-red-400 light:text-red-700 border border-red-800/60 light:border-red-300 shadow-sm">
            <span className="w-2 h-2 rounded-full bg-red-500 animate-ping" />
            ERROR 404 — POSITION UNKNOWN
          </span>

          {/* 404 Heading & Description */}
          <div className="space-y-2 max-w-sm">
            <h1 className="text-2xl sm:text-3xl font-extrabold tracking-tight text-slate-100 dark:text-slate-100 light:text-slate-900 font-sans">
              Signal Lost: Out of Range
            </h1>
            <p className="text-xs sm:text-sm text-slate-400 dark:text-slate-400 light:text-slate-600 font-normal leading-relaxed">
              The telemetry coordinate or URL path you requested does not exist or has been relocated outside mission control boundaries.
            </p>
          </div>

          {/* Tactical Diagnostic Key/Value Grid */}
          <div className="w-full grid grid-cols-2 gap-3 p-3.5 rounded-xl bg-slate-950/60 dark:bg-slate-950/60 light:bg-slate-100 border border-slate-800/80 dark:border-slate-800/80 light:border-slate-300 font-mono text-xs text-left">
            <div>
              <span className="text-slate-500 light:text-slate-400 block text-[10px] uppercase">Telemetry Error:</span>
              <span className="text-amber-400 light:text-amber-600 font-bold">404 NOT_FOUND</span>
            </div>
            <div>
              <span className="text-slate-500 light:text-slate-400 block text-[10px] uppercase">Navigation Vector:</span>
              <span className="text-slate-300 light:text-slate-700 font-bold">INVALID_ROUTE</span>
            </div>
          </div>

          {/* Action Navigation Buttons */}
          <div className="flex flex-col sm:flex-row items-center gap-3 w-full pt-1">
            <Link
              href="/dashboard"
              className="w-full sm:flex-1 py-2.5 px-4 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-mono text-xs font-bold border border-blue-400/40 shadow-lg shadow-blue-600/20 flex items-center justify-center gap-2 transition-all"
            >
              <Home className="w-4 h-4" />
              Return to Mission Control
            </Link>

            <button
              onClick={() => router.back()}
              className="w-full sm:flex-1 py-2.5 px-4 rounded-xl bg-slate-900/80 dark:bg-slate-900/80 light:bg-slate-200 hover:bg-slate-800 light:hover:bg-slate-300 text-slate-300 dark:text-slate-300 light:text-slate-800 font-mono text-xs font-bold border border-slate-700/60 light:border-slate-300 flex items-center justify-center gap-2 transition-all"
            >
              <ArrowLeft className="w-4 h-4" />
              Go Back
            </button>
          </div>

        </div>
      </main>
    </div>
  );
}
