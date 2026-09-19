'use client';

import React from 'react';
import TopNavbar from './TopNavbar';

/**
 * Universal Mission-Control Layout Shell Component for secondary pages.
 */
export default function NavBar({ title, onBack, children }) {
  return (
    <div className="min-h-screen bg-[#f4f6ee] dark:bg-[#0d1b13] text-[#122018] dark:text-slate-100 font-sans flex flex-col selection:bg-[#1e4d35]/30 transition-colors duration-200">
      {/* 1. Full-Screen Background Overlay Layer */}
      <div className="fixed inset-0 bg-[url('/images/landing-pg.png')] bg-cover bg-center opacity-15 dark:opacity-20 pointer-events-none z-0" />
      <div className="fixed inset-0 bg-gradient-to-b from-[#f4f6ee]/85 via-[#f4f6ee]/75 to-[#f4f6ee]/90 dark:from-[#0d1b13]/85 dark:via-[#0d1b13]/75 dark:to-[#0d1b13]/90 pointer-events-none z-0" />

      {/* 2. Top Header Navigation */}
      <TopNavbar />

      {/* 3. Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 relative z-10 p-4 sm:p-6 lg:p-8 max-w-[1240px] w-full mx-auto space-y-6">
        {title && (
          <div className="flex items-center justify-between border-b border-[#1e4d35]/20 dark:border-[#4e9f76]/30 pb-4">
            <h1 className="text-2xl font-bold font-sans text-[#122018] dark:text-slate-100">{title}</h1>
            {onBack && (
              <button
                onClick={onBack}
                className="px-3.5 py-1.5 rounded-lg bg-[#e1eadf] dark:bg-[#1e4d35]/40 border border-[#1e4d35]/30 text-[#1e4d35] dark:text-[#4e9f76] hover:bg-[#1e4d35] hover:text-white text-xs font-mono transition-colors"
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
