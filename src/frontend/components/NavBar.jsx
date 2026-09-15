'use client';

import React, { useEffect, useState } from 'react';
import { useRouter, usePathname } from 'next/navigation';
import {
  Shield, LogOut, Loader2, WifiOff, Menu, X,
} from 'lucide-react';
import { getUser, clearSession, getHealth, isAuthenticated } from '../lib/api';

const NAV_LINKS = [
  { href: '/dashboard',    label: 'Dashboard' },
  { href: '/assets',       label: 'Assets' },
  { href: '/missions',     label: 'Missions' },
  { href: '/maintenance',  label: 'Maintenance' },
  { href: '/alerts',       label: 'Alerts' },
  { href: '/data-quality', label: 'Data Quality' },
  { href: '/copilot',      label: 'Copilot' },
  { href: '/models',       label: 'Models' },
];

/**
 * Shared top navigation bar for all authenticated pages.
 *
 * Props:
 *   title   — optional breadcrumb segment after the brand (e.g. "Assets / AH-64-01")
 *   onBack  — optional back-button handler; if omitted no back button is shown
 */
export default function NavBar({ title, onBack }) {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState(null);
  const [apiStatus, setApiStatus] = useState('checking');
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    setUser(getUser());
    getHealth()
      .then(() => setApiStatus('online'))
      .catch(() => setApiStatus('offline'));
  }, []);

  const handleLogout = () => {
    clearSession();
    router.push('/login');
  };

  return (
    <header className="sticky top-0 z-30 bg-[#070a12]/95 backdrop-blur-md border-b border-slate-800/70 px-4 sm:px-6 py-3">
      <div className="max-w-7xl mx-auto flex items-center justify-between gap-3">

        {/* Brand + optional back + breadcrumb */}
        <div className="flex items-center gap-3 min-w-0">
          {onBack && (
            <button
              onClick={onBack}
              className="text-slate-400 hover:text-slate-200 shrink-0"
              aria-label="Go back"
            >
              <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
              </svg>
            </button>
          )}
          <a href="/dashboard" className="flex items-center gap-2 shrink-0">
            <div className="w-7 h-7 rounded-lg bg-blue-600/20 border border-blue-500/40 flex items-center justify-center text-blue-400">
              <Shield className="w-3.5 h-3.5" />
            </div>
            <span className="text-sm font-bold font-mono uppercase tracking-wider text-slate-100">
              Mission<span className="text-blue-400">Ready</span>
            </span>
          </a>
          {title && (
            <span className="hidden sm:block text-slate-600 font-mono text-sm">
              / <span className="text-slate-300">{title}</span>
            </span>
          )}
        </div>

        {/* Desktop nav */}
        <nav className="hidden lg:flex items-center gap-0.5 text-[11px] font-mono">
          {NAV_LINKS.map(({ href, label }) => {
            const active = pathname === href || pathname?.startsWith(href + '/');
            return (
              <a
                key={href}
                href={href}
                className={`px-2.5 py-1.5 rounded-lg transition-colors ${
                  active
                    ? 'bg-blue-500/15 text-blue-400'
                    : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/60'
                }`}
              >
                {label}
              </a>
            );
          })}
        </nav>

        {/* Right cluster */}
        <div className="flex items-center gap-2 shrink-0">
          {/* API status pill */}
          <div
            className="hidden sm:flex items-center gap-1.5 px-2.5 py-1 rounded-full text-[10px] font-mono border"
            style={{
              background: apiStatus === 'online' ? 'rgba(6,78,59,.4)' : apiStatus === 'offline' ? 'rgba(69,10,10,.4)' : 'rgba(15,23,42,.4)',
              borderColor: apiStatus === 'online' ? 'rgba(6,95,70,.8)' : apiStatus === 'offline' ? 'rgba(127,29,29,.8)' : 'rgba(51,65,85,.8)',
              color: apiStatus === 'online' ? '#34d399' : apiStatus === 'offline' ? '#f87171' : '#94a3b8',
            }}
          >
            {apiStatus === 'online'
              ? <><span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" /><span>ONLINE</span></>
              : apiStatus === 'offline'
              ? <><WifiOff className="w-2.5 h-2.5" /><span>OFFLINE</span></>
              : <><Loader2 className="w-2.5 h-2.5 animate-spin" /><span>…</span></>
            }
          </div>

          {/* User + logout */}
          {user && (
            <>
              <div className="text-right hidden md:block">
                <p className="text-[10px] text-slate-500 font-mono uppercase">{user.role}</p>
                <p className="text-[11px] font-semibold text-slate-200 leading-tight">{user.full_name}</p>
              </div>
              <button
                onClick={handleLogout}
                className="flex items-center gap-1 text-[11px] font-mono text-slate-400 hover:text-red-400 px-2.5 py-1.5 rounded-lg border border-slate-800 hover:border-red-900/50 transition-colors"
                aria-label="Sign out"
              >
                <LogOut className="w-3.5 h-3.5" />
                <span className="hidden sm:inline">Out</span>
              </button>
            </>
          )}

          {/* Mobile hamburger */}
          <button
            onClick={() => setMobileOpen(!mobileOpen)}
            className="lg:hidden text-slate-400 hover:text-slate-200 p-1"
            aria-label="Toggle menu"
          >
            {mobileOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
          </button>
        </div>
      </div>

      {/* Mobile nav dropdown */}
      {mobileOpen && (
        <div className="lg:hidden border-t border-slate-800/60 mt-3 pt-3 pb-2 px-1 flex flex-col gap-1">
          {NAV_LINKS.map(({ href, label }) => {
            const active = pathname === href || pathname?.startsWith(href + '/');
            return (
              <a
                key={href}
                href={href}
                onClick={() => setMobileOpen(false)}
                className={`px-3 py-2 rounded-lg text-sm font-mono transition-colors ${
                  active
                    ? 'bg-blue-500/15 text-blue-400'
                    : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/60'
                }`}
              >
                {label}
              </a>
            );
          })}
        </div>
      )}
    </header>
  );
}
