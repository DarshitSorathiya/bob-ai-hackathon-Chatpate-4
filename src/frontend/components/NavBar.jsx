'use client';

import React from 'react';
import TopNavbar from './TopNavbar';

/**
 * Universal Mission-Control Layout Shell Component for secondary pages.
 */
export default function NavBar({ title, onBack, children }) {
  return (
    <div className="min-h-screen bg-[#030712] dark:bg-[#030712] light:bg-[#f8fafc] text-slate-100 dark:text-slate-100 light:text-slate-900 font-sans flex flex-col selection:bg-blue-600/30 transition-colors duration-200">
      {/* 1. Full-Screen Background Overlay Layer */}
      <div className="fixed inset-0 bg-[url('/images/landing-bg.png')] bg-cover bg-center opacity-20 dark:opacity-20 light:opacity-5 pointer-events-none z-0" />
      <div className="fixed inset-0 bg-gradient-to-b from-[#030712]/90 via-[#030712]/80 to-[#030712]/95 dark:from-[#030712]/90 dark:via-[#030712]/80 dark:to-[#030712]/95 light:from-slate-50/90 light:via-slate-100/80 light:to-slate-100/95 pointer-events-none z-0" />

      {/* 2. Top Header Navigation */}
      <TopNavbar />

      {/* 3. Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 relative z-10 p-4 sm:p-6 lg:p-8 max-w-[1240px] w-full mx-auto space-y-6">
        {title && (
          <div className="flex items-center justify-between border-b border-blue-900/30 dark:border-blue-900/30 light:border-slate-200 pb-4">
            <h1 className="text-2xl font-bold font-sans text-slate-100 dark:text-slate-100 light:text-slate-900">{title}</h1>
            {onBack && (
              <button
                onClick={onBack}
                className="px-3.5 py-1.5 rounded-lg bg-blue-900/30 dark:bg-blue-900/30 light:bg-blue-50 border border-blue-500/30 light:border-blue-300 text-blue-400 light:text-blue-600 hover:bg-blue-600/20 light:hover:bg-blue-100 text-xs font-mono transition-colors"
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
