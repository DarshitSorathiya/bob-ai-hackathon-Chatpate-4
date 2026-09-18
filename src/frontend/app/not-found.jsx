'use client';

import React from 'react';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { AlertTriangle, ArrowLeft, Home, Compass, ShieldAlert } from 'lucide-react';
import TopNavbar from '../components/TopNavbar';

export default function NotFound() {
  const router = useRouter();

  return (
    <div className="min-h-screen bg-[#030712] text-slate-100 font-sans flex flex-col selection:bg-blue-600/30 relative overflow-hidden">
      {/* 1. Full-Screen Background Atmospheric Overlay Layer */}
      <div className="fixed inset-0 bg-[url('/images/landing-bg.png')] bg-cover bg-center opacity-20 pointer-events-none z-0" />
      <div className="fixed inset-0 bg-gradient-to-b from-[#030712]/90 via-[#030712]/80 to-[#030712]/95 pointer-events-none z-0" />

      {/* 2. Top Header Navigation Shell */}
      <TopNavbar />

      {/* 3. Central 404 Mission Control Error HUD */}
      <main className="flex-1 flex items-center justify-center p-6 lg:p-12 relative z-10 w-full max-w-[1400px] mx-auto">
        <div className="w-full max-w-xl bg-[#0a0f1d]/85 border-[3px] border-white rounded-2xl p-8 lg:p-12 backdrop-blur-xl shadow-2xl text-center flex flex-col items-center space-y-6 transition-all">
          
          {/* Glowing Radar Error Icon Badge */}
          <div className="relative flex items-center justify-center">
            <div className="w-20 h-20 rounded-full bg-amber-500/10 border-2 border-amber-500/30 flex items-center justify-center text-amber-400 shadow-lg shadow-amber-500/20 animate-pulse">
              <ShieldAlert className="w-10 h-10" />
            </div>
            <div className="absolute -top-1 -right-1 w-6 h-6 rounded-full bg-red-600 border-2 border-[#0a0f1d] flex items-center justify-center text-[10px] font-mono font-bold text-white">
              !
            </div>
          </div>

          {/* Status Tag Badge */}
          <span className="inline-flex items-center gap-2 px-3.5 py-1 rounded-full text-xs font-mono font-bold uppercase tracking-widest bg-red-950/80 text-red-400 border border-red-800/60 shadow-sm">
            <span className="w-2 h-2 rounded-full bg-red-500 animate-ping" />
            ERROR 404 — POSITION UNKNOWN
          </span>

          {/* 404 Heading & Description */}
          <div className="space-y-3 max-w-md">
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-slate-100 font-sans">
              Signal Lost: Out of Range
            </h1>
            <p className="text-xs sm:text-sm text-slate-400 font-normal leading-relaxed">
              The telemetry coordinate or URL path you requested does not exist or has been relocated outside mission control boundaries.
            </p>
          </div>

          {/* Tactical Diagnostic Key/Value Grid */}
          <div className="w-full grid grid-cols-2 gap-3 p-4 rounded-xl bg-slate-950/60 border border-slate-800/80 font-mono text-xs text-left">
            <div>
              <span className="text-slate-500 block text-[10px] uppercase">Telemetry Error:</span>
              <span className="text-amber-400 font-bold">404 NOT_FOUND</span>
            </div>
            <div>
              <span className="text-slate-500 block text-[10px] uppercase">Navigation Vector:</span>
              <span className="text-slate-300 font-bold">INVALID_ROUTE</span>
            </div>
          </div>

          {/* Action Navigation Buttons */}
          <div className="flex flex-col sm:flex-row items-center gap-4 w-full pt-2">
            <Link
              href="/dashboard"
              className="w-full sm:flex-1 py-3 px-5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-mono text-xs font-bold border border-blue-400/40 shadow-lg shadow-blue-600/20 flex items-center justify-center gap-2 transition-all"
            >
              <Home className="w-4 h-4" />
              Return to Mission Control
            </Link>

            <button
              onClick={() => router.back()}
              className="w-full sm:flex-1 py-3 px-5 rounded-xl bg-slate-900/80 hover:bg-slate-800 text-slate-300 hover:text-slate-100 font-mono text-xs font-bold border border-slate-700/60 flex items-center justify-center gap-2 transition-all"
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
