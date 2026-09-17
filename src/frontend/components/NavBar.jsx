'use client';

import React, { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import {
  Bell, Clock, RefreshCw, User, ChevronDown, ChevronLeft, Shield
} from 'lucide-react';
import Sidebar from './Sidebar';
import { getUser, clearSession } from '../lib/api';

/**
 * Universal Mission-Control Layout Shell Component for all secondary pages.
 */
export default function NavBar({ title, onBack, children }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState(null);
  const [lastRefresh, setLastRefresh] = useState(new Date());

  useEffect(() => {
    setUser(getUser());
  }, []);

  const handleLogout = () => {
    clearSession();
    router.push('/login');
  };

  const refreshPage = () => {
    setLastRefresh(new Date());
    router.refresh();
  };

  return (
    <div className="min-h-screen bg-[#050811] text-slate-100 font-sans flex overflow-x-hidden selection:bg-blue-600/30">
      {/* 1. Full-Screen Background Overlay Layer */}
      <div className="fixed inset-0 bg-[url('/images/landing-bg.png')] bg-cover bg-center opacity-30 pointer-events-none z-0" />
      <div className="fixed inset-0 bg-gradient-to-b from-[#050811]/90 via-[#050811]/80 to-[#050811]/95 pointer-events-none z-0" />

      {/* 2. Left Navigation Sidebar */}
      <Sidebar />

      {/* 3. Main Content Area */}
      <div className="flex-1 flex flex-col min-w-0 relative z-10">

        {/* Top Header Bar matching Dashboard */}
        <header className="w-full px-8 lg:px-10 py-4 border-b border-slate-800/80 bg-[#060913]/60 backdrop-blur-md flex items-center justify-between gap-4">
          <div className="flex items-center gap-3 font-mono text-xs">
            {onBack && (
              <button
                onClick={onBack}
                className="p-1.5 rounded-lg bg-blue-600/10 border border-blue-500/30 text-blue-400 hover:bg-blue-600/20 transition-colors mr-1 flex items-center gap-1 font-semibold"
                title="Go Back"
              >
                <ChevronLeft className="w-4 h-4" /> Back
              </button>
            )}

            {/* Active Navigation Pills */}
            <a
              href="/dashboard"
              className={`px-3.5 py-1 rounded-full transition-colors ${
                pathname === '/dashboard'
                  ? 'bg-blue-600/20 border border-blue-500/40 text-blue-300 font-bold'
                  : 'text-slate-400 hover:text-slate-100'
              }`}
            >
              Dashboard
            </a>
            <a
              href="/assets"
              className={`px-3.5 py-1 rounded-full transition-colors ${
                pathname?.startsWith('/assets')
                  ? 'bg-blue-600/20 border border-blue-500/40 text-blue-300 font-bold'
                  : 'text-slate-400 hover:text-slate-100'
              }`}
            >
              Fleet
            </a>
            <a
              href="/maintenance"
              className={`px-3.5 py-1 rounded-full transition-colors ${
                pathname?.startsWith('/maintenance')
                  ? 'bg-blue-600/20 border border-blue-500/40 text-blue-300 font-bold'
                  : 'text-slate-400 hover:text-slate-100'
              }`}
            >
              Maintenance
            </a>
            <a
              href="/alerts"
              className={`px-3.5 py-1 rounded-full transition-colors ${
                pathname?.startsWith('/alerts')
                  ? 'bg-blue-600/20 border border-blue-500/40 text-blue-300 font-bold'
                  : 'text-slate-400 hover:text-slate-100'
              }`}
            >
              Alerts
            </a>
            <a
              href="/missions"
              className={`px-3.5 py-1 rounded-full transition-colors ${
                pathname?.startsWith('/missions')
                  ? 'bg-blue-600/20 border border-blue-500/40 text-blue-300 font-bold'
                  : 'text-slate-400 hover:text-slate-100'
              }`}
            >
              Sessions
            </a>

            {title && (
              <span className="hidden sm:flex items-center gap-2 text-slate-400 border-l border-slate-800/80 pl-3">
                <span className="text-slate-100 font-bold">{title}</span>
              </span>
            )}
          </div>

          {/* Right Header Controls */}
          <div className="flex items-center gap-4">
            <a href="/alerts" className="relative p-1.5 text-slate-400 hover:text-slate-200 transition-colors">
              <Bell className="w-4 h-4" />
            </a>

            {user && (
              <div className="flex items-center gap-2 text-xs font-mono border-l border-slate-800/80 pl-4">
                <div className="w-7.5 h-7.5 rounded-full bg-blue-600/20 border border-blue-500/40 flex items-center justify-center text-blue-400">
                  <User className="w-4 h-4" />
                </div>
                <span className="text-slate-300 font-medium hidden sm:inline">
                  Welcome, <strong className="text-slate-100">{user.full_name?.split(' ')[0] || 'Operator'}</strong>
                </span>
                <button
                  onClick={handleLogout}
                  className="text-slate-500 hover:text-red-400 p-1 transition-colors"
                  title="Sign Out"
                >
                  <ChevronDown className="w-3.5 h-3.5" />
                </button>
              </div>
            )}
          </div>
        </header>

        {/* Render Children or Return Layout Shell */}
        {children ? (
          <main className="p-8 lg:p-12 space-y-8 max-w-[1400px] w-full mx-auto">
            {children}
          </main>
        ) : null}
      </div>
    </div>
  );
}
