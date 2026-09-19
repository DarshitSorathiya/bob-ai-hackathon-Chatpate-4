'use client';

import React, { useState } from 'react';
import Image from 'next/image';
import LandingRadarCanvas from '../components/LandingRadarCanvas';

export default function HomePage() {
  const [isTransitioning, setIsTransitioning] = useState(false);

  const handleAction = (route) => {
    if (isTransitioning) return;
    setIsTransitioning(true);

    // Reduced flight takeoff transition duration (450ms) then navigate
    setTimeout(() => {
      window.location.href = route;
    }, 450);
  };

  return (
    <main className="relative min-h-screen w-full bg-[#050811] text-slate-100 overflow-hidden font-sans select-none">
      {/* 1. Full-Screen Atmospheric Background Image */}
      <div
        className={`absolute inset-0 bg-[url('/images/landing-pg.png')] bg-cover bg-center transition-opacity duration-900 ${
          isTransitioning ? 'opacity-0 scale-105' : 'opacity-85 scale-100'
        }`}
      />

      {/* Subtle Atmospheric Gradient Overlay for Contrast */}
      <div
        className={`absolute inset-0 bg-gradient-to-b from-[#050811]/70 via-transparent to-[#050811]/90 transition-opacity duration-900 ${
          isTransitioning ? 'opacity-0' : 'opacity-100'
        }`}
      />

      {/* 2. Left Radar Canvas Overlay Layer */}
      <div className={`transition-opacity duration-900 ${isTransitioning ? 'opacity-0' : 'opacity-100'}`}>
        <LandingRadarCanvas />
      </div>

      {/* 3. Left Tactical HUD Overlay (Image 2) */}
      <div
        className={`hidden lg:flex fixed left-8 top-[42%] -translate-y-1/2 flex-col space-y-1 font-mono text-[11px] text-[#4e9f76]/80 tracking-widest z-20 pointer-events-none select-none transition-opacity duration-900 ${
          isTransitioning ? 'opacity-0' : 'opacity-100'
        }`}
      >
        <div className="flex items-center gap-2">
          <span className="w-2.5 h-[1px] bg-[#4e9f76]" />
          <span className="font-semibold text-emerald-400">HUMS</span>
        </div>
        <div className="pl-4 text-emerald-300/70">TELEMETRY</div>
        <div className="pl-4 text-emerald-300/70">ANALYSIS</div>
      </div>

      {/* 4. Right Tactical HUD Overlay (Image 2) */}
      <div
        className={`hidden lg:flex fixed right-10 top-[22%] flex-col items-end space-y-3 font-mono text-[11px] text-[#4e9f76]/80 tracking-widest z-20 pointer-events-none select-none transition-opacity duration-900 ${
          isTransitioning ? 'opacity-0' : 'opacity-100'
        }`}
      >
        <div className="text-right space-y-0.5 text-emerald-300/70">
          <div>LAT 22.3072° N</div>
          <div>LON 70.6800° E</div>
        </div>
        <div className="pt-2 pr-1">
          <svg className="w-5 h-5 text-[#4e9f76]/60" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1">
            <line x1="12" y1="2" x2="12" y2="22" />
            <line x1="2" y1="12" x2="22" y2="12" />
            <circle cx="12" cy="12" r="5" strokeDasharray="2 2" />
          </svg>
        </div>
      </div>

      {/* 5. Top Header Branding Bar matching Image 2 */}
      <header
        className={`relative z-20 w-full px-6 py-6 flex justify-between items-center max-w-7xl mx-auto transition-all duration-900 ${
          isTransitioning ? 'opacity-0 -translate-y-4' : 'opacity-100 translate-y-0'
        }`}
      >
        <div className="flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-[#0d1b13] border border-[#1e4d35]/50 flex items-center justify-center text-emerald-400 shadow-sm">
            <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              <path d="M12 7.5v7M9.5 11.5h5M10.5 14.5h3" strokeLinecap="round" />
            </svg>
          </div>
          <span className="text-base font-bold tracking-wider text-slate-100 uppercase font-mono">
            MISSION<span className="text-emerald-400">READY</span>
          </span>
        </div>

        <div className="flex items-center gap-2 text-[11px] font-mono text-emerald-300 bg-[#0d1b13]/80 border border-[#1e4d35]/50 px-3.5 py-1.5 rounded-full backdrop-blur-md shadow-sm">
          <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse" />
          AEROSPACE HUMS MONITORING
        </div>
      </header>

      {/* 6. Main Landing Content matching Image 2 */}
      <div
        className={`relative z-20 max-w-3xl mx-auto text-center px-4 pt-8 sm:pt-14 pb-32 flex flex-col items-center space-y-6 transition-all duration-900 ${
          isTransitioning ? 'opacity-0 scale-95 -translate-y-8' : 'opacity-100 scale-100 translate-y-0'
        }`}
      >
        {/* Center Pill with Horizontal Tactical Accent Lines */}
        <div className="flex items-center justify-center gap-3">
          <span className="w-10 sm:w-16 h-[1px] bg-gradient-to-r from-transparent to-[#4e9f76]/60" />
          <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-[#0d1b13]/80 text-emerald-300 border border-[#4e9f76]/40 text-xs font-mono font-semibold tracking-wider backdrop-blur-md shadow-sm">
            DEFENSE & AEROSPACE TELEMETRY COPILOT
          </div>
          <span className="w-10 sm:w-16 h-[1px] bg-gradient-to-l from-transparent to-[#4e9f76]/60" />
        </div>

        {/* Headline Typography matching Image 2 Colors & Formatting */}
        <h1 className="text-4xl sm:text-6xl font-extrabold tracking-tight font-sans leading-[1.15]">
          <span className="block text-[#489a6f]">
            Know what&apos;s ready.
          </span>
          <span className="block text-slate-100 mt-1">
            Before the mission
          </span>
          <span className="block text-slate-100">
            begins.
          </span>
        </h1>

        <p className="text-slate-300 text-sm sm:text-base leading-relaxed max-w-xl font-normal">
          Ingesting real-time aircraft HUMS sensor telemetry and historical service records<br className="hidden sm:inline" /> to forecast component failure risks and prioritize fleet mission readiness.
        </p>

        {/* Action Buttons matching Image 2 */}
        <div className="flex flex-col sm:flex-row gap-4 pt-3 w-full sm:w-auto justify-center">
          <button
            onClick={() => handleAction('/login')}
            className="px-9 py-3 rounded-2xl bg-[#185235] hover:bg-[#123e28] text-white font-mono font-bold text-sm transition-all shadow-lg hover:scale-105 active:scale-95 border border-[#4e9f76]/30"
          >
            Login
          </button>
          <button
            onClick={() => handleAction('/signup')}
            className="px-9 py-3 rounded-2xl bg-[#e1eadf] hover:bg-[#f4f6ee] text-[#122018] font-mono font-bold text-sm transition-all shadow-lg hover:scale-105 active:scale-95 border border-[#1e4d35]/20"
          >
            Sign Up
          </button>
        </div>
      </div>

      {/* 7. Bottom Runway Tactical Line & Aircraft Cutout */}
      <div className={`fixed bottom-9 left-0 right-0 h-[1px] bg-gradient-to-r from-transparent via-[#4e9f76]/40 to-transparent z-20 pointer-events-none transition-opacity duration-450 ${isTransitioning ? 'opacity-0' : 'opacity-100'}`} />

      <div
        className={`fixed left-[48.5%] -translate-x-1/2 pointer-events-none z-30 transition-all duration-450 ease-in-out ${
          isTransitioning
            ? 'bottom-[120vh] scale-125 opacity-0 brightness-150 blur-[1px]'
            : 'bottom-[-20px] sm:bottom-[-10px] scale-100 opacity-95 brightness-110 animate-smooth-float'
        }`}
        style={{
          transitionTimingFunction: isTransitioning
            ? 'cubic-bezier(0.4, 0, 0.2, 1)'
            : 'ease-out',
        }}
      >
        {/* Military Sage Engine Thruster Glow */}
        <div
          className={`absolute bottom-1 left-1/2 -translate-x-1/2 w-14 h-14 bg-[#1e4d35]/30 rounded-full blur-xl transition-opacity duration-450 ${
            isTransitioning ? 'opacity-100 scale-150 bg-emerald-400/40' : 'opacity-50'
          }`}
        />

        {/* Compact Aircraft Cutout */}
        <div className="relative w-[65px] sm:w-[85px] md:w-[105px] h-[65px] sm:h-[85px] md:h-[105px]">
          <Image
            src="/images/aircraft.png"
            alt="Aircraft Telemetry Target"
            fill
            className="object-contain filter drop-shadow-[0_0_12px_rgba(78,159,118,0.7)]"
            priority
          />
        </div>
      </div>
    </main>
  );
}
