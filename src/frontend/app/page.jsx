'use client';

import React, { useState } from 'react';
import Image from 'next/image';
import LandingRadarCanvas from '../components/LandingRadarCanvas';

export default function HomePage() {
  const [isTransitioning, setIsTransitioning] = useState(false);

  const handleAction = (route) => {
    if (isTransitioning) return;
    setIsTransitioning(true);

    // Smooth flight transition duration (1.35 seconds) then navigate reliably
    setTimeout(() => {
      window.location.href = route;
    }, 1350);
  };

  return (
    <main className="relative min-h-screen w-full bg-[#050811] text-slate-100 overflow-hidden font-sans select-none">
      {/* 1. Full-Screen Atmospheric Background Image */}
      <div
        className={`absolute inset-0 bg-[url('/images/landing-bg.png')] bg-cover bg-center transition-opacity duration-1000 ${
          isTransitioning ? 'opacity-0 scale-105' : 'opacity-85 scale-100'
        }`}
      />

      {/* Subtle Atmospheric Gradient Overlay for Contrast */}
      <div
        className={`absolute inset-0 bg-gradient-to-b from-[#050811]/70 via-transparent to-[#050811]/90 transition-opacity duration-1000 ${
          isTransitioning ? 'opacity-0' : 'opacity-100'
        }`}
      />

      {/* 2. Interactive Radar / Telemetry Overlay Layer */}
      <div className={`transition-opacity duration-700 ${isTransitioning ? 'opacity-0' : 'opacity-100'}`}>
        <LandingRadarCanvas />
      </div>

      {/* Top Header Branding Bar */}
      <header
        className={`relative z-20 w-full px-6 py-6 flex justify-between items-center max-w-7xl mx-auto transition-all duration-700 ${
          isTransitioning ? 'opacity-0 -translate-y-4' : 'opacity-100 translate-y-0'
        }`}
      >
        <div className="flex items-center gap-3">
          <div className="w-8 h-8 rounded-lg bg-blue-500/20 border border-blue-400/40 flex items-center justify-center text-blue-400">
            <svg className="w-4.5 h-4.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              <path d="m9 12 2 2 4-4" />
            </svg>
          </div>
          <span className="text-base font-bold tracking-wider text-slate-100 uppercase font-mono">
            MISSION<span className="text-blue-400">READY</span>
          </span>
        </div>

        <div className="flex items-center gap-2 text-[11px] font-mono text-slate-400 bg-slate-900/60 border border-slate-800/80 px-3 py-1.5 rounded-full backdrop-blur-sm">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          AEROSPACE HUMS MONITORING
        </div>
      </header>

      {/* 3. Main Cinematic Landing Content (Upper-Center) */}
      <div
        className={`relative z-20 max-w-3xl mx-auto text-center px-4 pt-10 sm:pt-16 pb-32 flex flex-col items-center space-y-6 transition-all duration-700 ${
          isTransitioning ? 'opacity-0 scale-95 -translate-y-8' : 'opacity-100 scale-100 translate-y-0'
        }`}
      >
        <div className="inline-flex items-center gap-2 px-3 py-1 rounded-full bg-blue-950/70 border border-blue-800/60 text-blue-300 text-xs font-mono font-semibold tracking-wide backdrop-blur-sm">
          DEFENSE & AEROSPACE TELEMETRY COPILOT
        </div>

        <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight text-slate-100 font-sans leading-tight">
          Know what&apos;s ready.<br />
          <span className="text-transparent bg-clip-text bg-gradient-to-r from-blue-300 via-sky-400 to-blue-500">
            Before the mission begins.
          </span>
        </h1>

        <p className="text-slate-300 text-sm sm:text-base leading-relaxed max-w-xl font-normal">
          Ingesting real-time aircraft HUMS sensor telemetry and historical service records to forecast component failure risks and prioritize fleet mission readiness.
        </p>

        {/* Action Buttons */}
        <div className="flex flex-col sm:flex-row gap-4 pt-4 w-full sm:w-auto justify-center">
          <button
            onClick={() => handleAction('/login')}
            className="px-8 py-3.5 rounded-xl bg-blue-600 hover:bg-blue-500 text-white font-mono font-semibold text-sm transition-all shadow-lg shadow-blue-600/30 hover:shadow-blue-500/50 hover:scale-105 active:scale-95"
          >
            Login
          </button>
          <button
            onClick={() => handleAction('/signup')}
            className="px-8 py-3.5 rounded-xl bg-slate-900/80 border border-slate-700/80 hover:bg-slate-800 text-slate-100 font-mono font-semibold text-sm transition-all backdrop-blur-sm hover:scale-105 active:scale-95"
          >
            Sign Up
          </button>
        </div>
      </div>

      {/* 4. Bottom Aircraft Image & Flight Transition Layer */}
      <div
        className={`fixed left-1/2 -translate-x-1/2 pointer-events-none z-30 transition-all duration-[1400ms] ease-in-out ${
          isTransitioning
            ? 'bottom-[120vh] scale-125 opacity-0 brightness-150 blur-[1px]'
            : 'bottom-[-65px] sm:bottom-[-55px] scale-100 opacity-95 brightness-110'
        }`}
        style={{
          transitionTimingFunction: isTransitioning
            ? 'cubic-bezier(0.4, 0, 0.2, 1)'
            : 'ease-out',
        }}
      >
        {/* Blue Engine Thruster Glow */}
        <div
          className={`absolute bottom-2 left-1/2 -translate-x-1/2 w-28 h-28 bg-blue-500/20 rounded-full blur-2xl transition-opacity duration-500 ${
            isTransitioning ? 'opacity-100 scale-150 bg-sky-400/40' : 'opacity-50'
          }`}
        />

        {/* Compact Transparent Aircraft Cutout */}
        <div className="relative w-[180px] sm:w-[240px] md:w-[280px] h-[180px] sm:h-[240px] md:h-[280px]">
          <Image
            src="/images/aircraft.png"
            alt="Aircraft Telemetry Target"
            fill
            className="object-contain filter drop-shadow-[0_0_18px_rgba(56,189,248,0.35)]"
            priority
          />
        </div>
      </div>
    </main>
  );
}
