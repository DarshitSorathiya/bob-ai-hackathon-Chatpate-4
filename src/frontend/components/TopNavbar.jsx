'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { User, ChevronDown, LogOut } from 'lucide-react';
import { getUser, clearSession } from '../lib/api';

/**
 * Top Navbar matching Image 1:
 * Left: Shield Icon + MISSIONREADY
 * Center: Spaced Navigation Tabs (Dashboard, Fleet, Maintenance, Alerts, Sessions)
 * Right: User Avatar + Welcome, Tulsi + Dropdown Chevron
 */
export default function TopNavbar() {
  const router = useRouter();
  const pathname = usePathname();
  const [user, setUser] = useState(null);
  const [userMenuOpen, setUserMenuOpen] = useState(false);

  useEffect(() => {
    setUser(getUser());
  }, []);

  const handleLogout = () => {
    clearSession();
    router.push('/login');
  };

  const navItems = [
    { href: '/dashboard', label: 'Dashboard' },
    { href: '/assets', label: 'Fleet' },
    { href: '/maintenance', label: 'Maintenance' },
    { href: '/alerts', label: 'Alerts' },
    { href: '/missions', label: 'Sessions' },
  ];

  const firstName = user?.full_name?.split(' ')[0] || 'Tulsi';

  return (
    <header className="w-full bg-[#040814]/90 border-b border-blue-900/40 backdrop-blur-xl sticky top-0 z-50 px-6 lg:px-12 py-3 flex items-center justify-between gap-6 select-none shadow-lg shadow-black/40">
      {/* Left Brand Logo */}
      <Link href="/dashboard" className="flex items-center gap-3 group shrink-0">
        <div className="w-9 h-9 rounded-xl bg-blue-600/20 border border-blue-500/40 flex items-center justify-center text-blue-400 shadow-md shadow-blue-500/10 group-hover:border-blue-400 transition-colors">
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            <path d="M12 8v8" />
            <path d="M8 12h8" />
          </svg>
        </div>
        <span className="text-base font-extrabold font-mono tracking-wider text-slate-100 uppercase">
          MISSION<span className="text-blue-400">READY</span>
        </span>
      </Link>

      {/* Center Navigation Tabs with Generous Spacing matching Picture 1 */}
      <nav className="flex items-center gap-3 md:gap-5 bg-[#070f22]/80 px-3 py-1.5 rounded-full border border-blue-900/40 shadow-inner">
        {navItems.map((item) => {
          const isActive = pathname === item.href || (item.href !== '/dashboard' && pathname?.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`px-5 py-2 rounded-full text-xs font-mono transition-all duration-200 tracking-wide ${
                isActive
                  ? 'bg-[#122448] text-blue-300 font-bold border border-blue-500/50 shadow-md shadow-blue-500/20'
                  : 'text-slate-400 hover:text-slate-100 hover:bg-slate-800/50'
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Right User Controls */}
      <div className="relative shrink-0">
        <button
          onClick={() => setUserMenuOpen(!userMenuOpen)}
          className="flex items-center gap-2.5 px-4 py-2 rounded-full bg-[#070f22]/80 border border-blue-900/40 hover:border-blue-500/40 text-xs font-mono text-slate-200 transition-colors"
        >
          <div className="w-6.5 h-6.5 rounded-full bg-blue-600/20 border border-blue-500/40 flex items-center justify-center text-blue-400">
            <User className="w-3.5 h-3.5" />
          </div>
          <span className="font-medium text-slate-300 hidden sm:inline">
            Welcome, <strong className="text-slate-100">{firstName}</strong>
          </span>
          <ChevronDown className="w-3.5 h-3.5 text-slate-400" />
        </button>

        {userMenuOpen && (
          <div className="absolute right-0 mt-2 w-48 rounded-xl bg-[#081024] border border-blue-900/60 shadow-2xl p-2 z-50 text-xs font-mono">
            <div className="px-3 py-2 border-b border-slate-800 text-slate-400">
              Signed in as <br />
              <strong className="text-slate-200">{user?.email || 'tulsi@missionready.ai'}</strong>
            </div>
            <button
              onClick={handleLogout}
              className="w-full text-left flex items-center gap-2 px-3 py-2 mt-1 rounded-lg text-red-400 hover:bg-red-500/10 transition-colors"
            >
              <LogOut className="w-3.5 h-3.5" /> Sign Out
            </button>
          </div>
        )}
      </div>
    </header>
  );
}
