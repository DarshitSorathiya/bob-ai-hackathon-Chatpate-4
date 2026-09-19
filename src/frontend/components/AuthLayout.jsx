'use client';

import React from 'react';
import Link from 'next/link';
import HumsSensorCanvas from './HumsSensorCanvas';

export default function AuthLayout({ children, title, subtitle }) {
  return (
    <div className="min-h-screen w-full bg-[#f4f6ee] dark:bg-[#0d1b13] text-[#122018] dark:text-slate-100 flex flex-col justify-between relative overflow-hidden font-sans transition-colors duration-200">
      {/* 1. Background Atmospheric Image with Very Low White Transparency */}
      <div className="fixed inset-0 bg-[url('/images/landing-pg.png')] bg-cover bg-center opacity-15 dark:opacity-20 pointer-events-none z-0" />
      <div className="fixed inset-0 bg-gradient-to-b from-[#f4f6ee]/85 via-[#f4f6ee]/75 to-[#f4f6ee]/90 dark:from-[#0d1b13]/85 dark:via-[#0d1b13]/75 dark:to-[#0d1b13]/90 pointer-events-none z-0" />

      {/* 2. Full-Viewport Interactive HUMS Sensor Radar Layer */}
      <HumsSensorCanvas />

      {/* 3. Top Header Overlay (Seamless, zero top bar cutoff) */}
      <header className="relative z-10 w-full px-6 py-5 flex justify-between items-center bg-transparent border-none">
        <Link href="/" className="flex items-center gap-3 group">
          <div className="w-8 h-8 rounded-lg bg-[#e1eadf]/80 border border-[#1e4d35]/30 flex items-center justify-center text-[#1e4d35] group-hover:bg-[#1e4d35] group-hover:text-white transition-colors backdrop-blur-sm shadow-sm">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="w-4 h-4"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              <path d="M12 7.5v7M9.5 11.5h5M10.5 14.5h3" />
            </svg>
          </div>
          <div>
            <span className="text-base font-bold tracking-tight text-[#122018] dark:text-slate-100 uppercase font-mono">
              Mission<span className="text-[#1e4d35] dark:text-[#4e9f76]">Ready</span>
            </span>
            <span className="text-[10px] block text-[#566b5c] dark:text-slate-400 tracking-wider uppercase font-mono">
              Predict the failure. Protect the mission.
            </span>
          </div>
        </Link>

        {/* Process Flow Badge */}
        <div className="hidden sm:flex items-center gap-2 text-[11px] font-mono text-[#122018] dark:text-slate-300 bg-[#e1eadf]/70 dark:bg-[#122419]/80 border border-[#1e4d35]/25 px-3.5 py-1.5 rounded-full backdrop-blur-md shadow-sm">
          <span>HUMS Sensors</span>
          <span className="text-[#1e4d35] dark:text-[#4e9f76]">→</span>
          <span>Telemetry</span>
          <span className="text-[#1e4d35] dark:text-[#4e9f76]">→</span>
          <span className="text-[#2d9f6f] font-medium">Health</span>
          <span className="text-[#1e4d35] dark:text-[#4e9f76]">→</span>
          <span className="text-amber-500 font-medium">Prediction</span>
          <span className="text-[#1e4d35] dark:text-[#4e9f76]">→</span>
          <span className="text-[#1e4d35] dark:text-[#4e9f76] font-semibold">Mission Readiness</span>
        </div>
      </header>

      {/* 4. Center Auth Card Container */}
      <main className="relative z-10 w-full flex-1 flex items-center justify-center px-4 py-8 max-w-7xl mx-auto">
        <div className="w-full max-w-md">
          {/* Auth Card container */}
          <div className="bg-[#f4f6ee]/95 dark:bg-[#122419]/95 border border-[#1e4d35]/25 dark:border-[#4e9f76]/30 backdrop-blur-xl p-8 shadow-2xl rounded-2xl relative">
            {/* Header Content inside Card */}
            <div className="text-center mb-6">
              <div className="inline-block px-3 py-0.5 rounded text-[10px] font-mono font-bold uppercase tracking-widest bg-[#e1eadf] dark:bg-[#1e4d35]/40 text-[#1e4d35] dark:text-[#4e9f76] border border-[#1e4d35]/30 mb-2">
                DEFENSE & AEROSPACE OPERATIONS
              </div>
              <h1 className="text-2xl font-bold text-[#122018] dark:text-slate-100 tracking-tight font-sans">{title}</h1>
              {subtitle && <p className="text-xs text-[#566b5c] dark:text-slate-400 pt-1 leading-relaxed">{subtitle}</p>}
            </div>

            {children}
          </div>
        </div>
      </main>

      {/* 5. Bottom Footer Overlay (Seamless, zero bottom bar cutoff) */}
      <footer className="relative z-10 w-full px-6 py-4 bg-transparent border-none flex flex-col sm:flex-row justify-between items-center text-[11px] font-mono text-[#566b5c] dark:text-slate-400 gap-2">
        <p>MissionReady Copilot &copy; {new Date().getFullYear()} Team Chatpate-4</p>
        <div className="flex gap-4">
          <span className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-[#2d9f6f]" />
            Sensor Network: ACTIVE
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-[#1e4d35] dark:bg-[#4e9f76]" />
            Scanner Parallax: ACTIVE
          </span>
        </div>
      </footer>
    </div>
  );
}
