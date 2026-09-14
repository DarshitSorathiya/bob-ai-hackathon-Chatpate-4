'use client';

import React from 'react';
import Link from 'next/link';
import HumsSensorCanvas from './HumsSensorCanvas';

export default function AuthLayout({ children, title, subtitle }) {
  return (
    <div className="min-h-screen w-full bg-[#060911] text-slate-100 flex flex-col justify-between relative overflow-hidden font-sans">
      {/* 1. Full-Viewport Interactive HUMS Sensor Background Layer */}
      <HumsSensorCanvas />

      {/* 2. Top Header Bar (Positioned to Top Leftmost Corner) */}
      <header className="relative z-10 w-full px-4 sm:px-6 py-3.5 flex justify-between items-center border-b border-slate-800/60 bg-[#060911]/60 backdrop-blur-md">
        <Link href="/" className="flex items-center gap-2.5 group">
          <div className="w-8 h-8 rounded-lg bg-blue-600/20 border border-blue-500/40 flex items-center justify-center text-blue-400 group-hover:bg-blue-600/30 transition-colors shrink-0">
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
              <path d="m9 12 2 2 4-4" />
            </svg>
          </div>
          <div>
            <span className="text-base font-bold tracking-tight text-slate-100 uppercase font-mono">
              Mission<span className="text-blue-400">Ready</span>
            </span>
            <span className="text-[10px] block text-slate-500 tracking-wider uppercase font-mono">
              Predict the failure. Protect the mission.
            </span>
          </div>
        </Link>

        {/* Process Flow Badge */}
        <div className="hidden sm:flex items-center gap-2 text-[11px] font-mono text-slate-400 bg-slate-900/80 border border-slate-800/80 px-3 py-1.5 rounded-full">
          <span>HUMS Sensors</span>
          <span className="text-blue-400">→</span>
          <span>Telemetry</span>
          <span className="text-blue-400">→</span>
          <span className="text-emerald-400 font-medium">Health</span>
          <span className="text-blue-400">→</span>
          <span className="text-amber-400 font-medium">Prediction</span>
          <span className="text-blue-400">→</span>
          <span className="text-blue-400 font-semibold">Mission Readiness</span>
        </div>
      </header>

      {/* 3. Dead-Center Solid High-Readability Authentication Layout */}
      <main className="relative z-10 w-full flex-1 flex items-center justify-center px-4 py-8 max-w-7xl mx-auto">
        <div className="w-full max-w-md">
          {/* Solid Translucent Auth Card */}
          <div className="bg-[#090d16]/96 border border-slate-700/80 backdrop-blur-xl p-8 shadow-2xl rounded-2xl relative">
            {/* Header Content inside Card */}
            <div className="text-center mb-6">
              <div className="inline-block px-2.5 py-0.5 rounded text-[10px] font-mono font-semibold uppercase tracking-wider bg-blue-950/80 text-blue-400 border border-blue-800/60 mb-2">
                Defense & Aerospace Operations
              </div>
              <h1 className="text-2xl font-bold text-slate-100 tracking-tight font-sans">{title}</h1>
              {subtitle && <p className="text-xs text-slate-400 pt-1 leading-relaxed">{subtitle}</p>}
            </div>

            {children}
          </div>
        </div>
      </main>

      {/* 4. Bottom Footer */}
      <footer className="relative z-10 w-full px-6 py-3 border-t border-slate-800/60 bg-[#060911]/60 backdrop-blur-md flex flex-col sm:flex-row justify-between items-center text-[11px] font-mono text-slate-500 gap-2">
        <p>MissionReady Copilot &copy; {new Date().getFullYear()} Team Chatpate-4</p>
        <div className="flex gap-4">
          <span className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-emerald-400" />
            Sensor Network: ACTIVE
          </span>
          <span className="flex items-center gap-1.5">
            <span className="w-1.5 h-1.5 rounded-full bg-blue-400" />
            Scanner Parallax: ACTIVE
          </span>
        </div>
      </footer>
    </div>
  );
}
