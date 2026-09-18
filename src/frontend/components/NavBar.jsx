'use client';

import React from 'react';
import TopNavbar from './TopNavbar';

/**
 * Universal Mission-Control Layout Shell Component for secondary pages.
 */
export default function NavBar({ title, onBack, children }) {
  return (
    <div className="min-h-screen bg-[#030712] text-slate-100 font-sans flex flex-col selection:bg-blue-600/30">
      {/* 1. Full-Screen Background Overlay Layer */}
      <div className="fixed inset-0 bg-[url('/images/landing-bg.png')] bg-cover bg-center opacity-20 pointer-events-none z-0" />
      <div className="fixed inset-0 bg-gradient-to-b from-[#030712]/90 via-[#030712]/80 to-[#030712]/95 pointer-events-none z-0" />

      {/* 2. Top Header Navigation */}
      <TopNavbar />

      {/* 3. Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 relative z-10 p-6 lg:p-10 max-w-[1500px] w-full mx-auto space-y-6">
        {title && (
          <div className="flex items-center justify-between border-b border-blue-900/40 pb-4">
            <h1 className="text-2xl font-bold font-sans text-slate-100">{title}</h1>
            {onBack && (
              <button
                onClick={onBack}
                className="px-3 py-1.5 rounded-lg bg-blue-900/30 border border-blue-500/30 text-blue-400 hover:bg-blue-600/20 text-xs font-mono transition-colors"
              >
                ← Back
              </button>
            )}
          </div>
        )}
        {children}
      </div>
    </div>
  );
}
