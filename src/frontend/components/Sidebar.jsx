'use client';

import React from 'react';
import Link from 'next/link';
import { usePathname } from 'next/navigation';
import {
  LayoutDashboard, Shield, Compass, Wrench, AlertTriangle,
  Activity, Sparkles, Cpu
} from 'lucide-react';

const SIDEBAR_NAV = [
  { href: '/dashboard',    label: 'Dashboard',    icon: LayoutDashboard },
  { href: '/assets',       label: 'Assets',       icon: Shield },
  { href: '/missions',     label: 'Missions',     icon: Compass },
  { href: '/maintenance',  label: 'Maintenance',  icon: Wrench },
  { href: '/alerts',       label: 'Alerts',       icon: AlertTriangle, hasBadge: true },
  { href: '/data-quality', label: 'Data Quality', icon: Activity },
  { href: '/copilot',      label: 'Copilot',      icon: Sparkles },
  { href: '/models',       label: 'Models',       icon: Cpu },
];

export default function Sidebar({ alertCount = 0 }) {
  const pathname = usePathname();

  return (
    <aside className="w-56 shrink-0 bg-[#f4f6ee] dark:bg-[#060913]/85 border-r border-[#1e4d35]/20 dark:border-slate-800/80 min-h-screen flex flex-col justify-between p-4 backdrop-blur-xl relative z-30 select-none shadow-xl">
      <div className="space-y-6">
        {/* Brand Header matching Reference */}
        <div className="flex items-center gap-3 px-2 py-1">
          <div className="w-8 h-8 rounded-lg bg-[#e1eadf] dark:bg-[#1e4d35]/30 border border-[#1e4d35]/30 flex items-center justify-center text-[#1e4d35] dark:text-emerald-400 shadow-sm">
            <svg className="w-4.5 h-4.5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
              <path d="m9 12 2 2 4-4" />
            </svg>
          </div>
          <div className="flex flex-col">
            <span className="text-sm font-bold font-mono uppercase tracking-wider text-[#122018] dark:text-slate-100 leading-tight">
              MISSION<span className="text-[#1e4d35] dark:text-emerald-400">READY</span>
            </span>
            <span className="text-[9px] font-mono text-[#566b5c] dark:text-slate-500 uppercase tracking-widest">
              MISSION CONTROL
            </span>
          </div>
        </div>

        {/* Vertical Navigation Links */}
        <nav className="space-y-1 text-xs font-mono">
          {SIDEBAR_NAV.map(({ href, label, icon: Icon, hasBadge }) => {
            const active = pathname === href || (href !== '/dashboard' && pathname?.startsWith(href));
            return (
              <Link
                key={href}
                href={href}
                className={`flex items-center justify-between px-3 py-2.5 rounded-xl border transition-all duration-150 ${
                  active
                    ? 'bg-[#1e4d35] text-white font-bold border-[#1e4d35] shadow-md'
                    : 'border-transparent text-[#122018] dark:text-slate-400 hover:text-[#1e4d35] hover:bg-[#e1eadf]/60 dark:hover:bg-slate-900/60'
                }`}
              >
                <div className="flex items-center gap-3 min-w-0">
                  <Icon className={`w-4 h-4 shrink-0 ${active ? 'text-white' : 'text-[#566b5c] dark:text-slate-500'}`} />
                  <span className="truncate">{label}</span>
                </div>

                {hasBadge && alertCount > 0 && (
                  <span className="px-1.5 py-0.5 rounded-full text-[9px] font-bold bg-red-500/20 text-red-600 dark:text-red-400 border border-red-500/40 animate-pulse">
                    {alertCount}
                  </span>
                )}
              </Link>
            );
          })}
        </nav>
      </div>

      {/* Footer Branding Slogan matching Reference */}
      <div className="pt-4 border-t border-[#1e4d35]/20 dark:border-slate-800/80 space-y-3">
        <div className="border-l-2 border-[#1e4d35] pl-2.5 py-0.5 font-mono text-[9px] tracking-widest leading-relaxed">
          <p className="text-[#122018] dark:text-slate-400 font-bold uppercase">SAFER MISSIONS</p>
          <p className="text-[#566b5c] dark:text-slate-500 uppercase">HIGHER SUCCESS</p>
        </div>
      </div>
    </aside>
  );
}
