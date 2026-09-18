'use client';

import React, { useState, useEffect } from 'react';
import Link from 'next/link';
import { usePathname, useRouter } from 'next/navigation';
import { User, ChevronDown, LogOut, Sun, Moon } from 'lucide-react';
import { getUser, clearSession } from '../lib/api';
import { useTheme } from './ThemeProvider';

/**
 * Top Navbar with Theme Toggle (Light / Dark Mode):
 * Left: Shield Icon + MISSIONREADY
 * Center: Spaced Navigation Tabs (Dashboard, Fleet, Maintenance, Alerts, Sessions, Copilot)
 * Right: Sun/Moon Theme Toggle + User Avatar Dropdown
 */
export default function TopNavbar() {
  const router = useRouter();
  const pathname = usePathname();
  const { theme, toggleTheme } = useTheme();
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
    { href: '/copilot', label: 'Copilot' },
  ];

  const firstName = user?.full_name?.split(' ')[0] || 'Tulsi';

  return (
    <header className="w-full bg-[#040814]/90 dark:bg-[#040814]/90 light:bg-white/90 border-b border-blue-900/30 dark:border-blue-900/30 light:border-slate-200 backdrop-blur-xl sticky top-0 z-50 px-6 lg:px-12 py-3 flex items-center justify-between gap-6 select-none shadow-lg dark:shadow-black/40 light:shadow-slate-200/50 transition-colors duration-200">
      {/* Left Brand Logo */}
      <Link href="/dashboard" className="flex items-center gap-3 group shrink-0">
        <div className="w-9 h-9 rounded-xl bg-blue-600/20 dark:bg-blue-600/20 light:bg-blue-100 border border-blue-500/40 dark:border-blue-500/40 light:border-blue-300 flex items-center justify-center text-blue-400 light:text-blue-600 shadow-md shadow-blue-500/10 group-hover:border-blue-400 transition-colors">
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            <path d="M12 8v8" />
            <path d="M8 12h8" />
          </svg>
        </div>
        <span className="text-base font-extrabold font-mono tracking-wider text-slate-100 dark:text-slate-100 light:text-slate-900 uppercase">
          MISSION<span className="text-blue-400 light:text-blue-600">READY</span>
        </span>
      </Link>

      {/* Center Navigation Tabs with Spacing */}
      <nav className="flex items-center gap-1.5 md:gap-3 bg-[#070f22]/80 dark:bg-[#070f22]/80 light:bg-slate-100/90 px-3 py-1.5 rounded-full border border-blue-900/30 dark:border-blue-900/30 light:border-slate-200 shadow-inner">
        {navItems.map((item) => {
          const isActive = pathname === item.href || (item.href !== '/dashboard' && pathname?.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`px-3.5 py-1.5 rounded-full text-xs font-mono transition-all duration-200 tracking-wide ${
                isActive
                  ? 'bg-[#122448] dark:bg-[#122448] light:bg-blue-600 text-blue-300 dark:text-blue-300 light:text-white font-bold border border-blue-500/40 light:border-blue-600 shadow-md shadow-blue-500/20'
                  : 'text-slate-400 dark:text-slate-400 light:text-slate-600 hover:text-slate-100 light:hover:text-slate-900 hover:bg-slate-800/40 light:hover:bg-slate-200/60'
              }`}
            >
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Right Controls: Theme Toggle + User Menu */}
      <div className="flex items-center gap-3 shrink-0">
        {/* Sun / Moon Theme Toggle Button */}
        <button
          onClick={toggleTheme}
          title={`Switch to ${theme === 'dark' ? 'Light' : 'Dark'} Mode`}
          className="p-2 rounded-full bg-[#070f22]/80 dark:bg-[#070f22]/80 light:bg-slate-100 border border-blue-900/40 dark:border-blue-900/40 light:border-slate-300 hover:border-blue-500/40 text-amber-400 dark:text-amber-400 light:text-blue-600 transition-all duration-200 shadow-sm"
        >
          {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>

        {/* User Profile Controls */}
        <div className="relative">
          <button
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            className="flex items-center gap-2.5 px-3.5 py-1.5 rounded-full bg-[#070f22]/80 dark:bg-[#070f22]/80 light:bg-slate-100 border border-blue-900/40 dark:border-blue-900/40 light:border-slate-300 hover:border-blue-500/40 text-xs font-mono text-slate-200 dark:text-slate-200 light:text-slate-800 transition-colors"
          >
            <div className="w-6 h-6 rounded-full bg-blue-600/20 light:bg-blue-100 border border-blue-500/40 light:border-blue-300 flex items-center justify-center text-blue-400 light:text-blue-600">
              <User className="w-3.5 h-3.5" />
            </div>
            <span className="font-medium text-slate-300 dark:text-slate-300 light:text-slate-700 hidden sm:inline">
              Welcome, <strong className="text-slate-100 dark:text-slate-100 light:text-slate-900">{firstName}</strong>
            </span>
            <ChevronDown className="w-3.5 h-3.5 text-slate-400 light:text-slate-500" />
          </button>

          {userMenuOpen && (
            <div className="absolute right-0 mt-2 w-48 rounded-xl bg-[#081024] dark:bg-[#081024] light:bg-white border border-blue-900/60 dark:border-blue-900/60 light:border-slate-200 shadow-2xl p-2 z-50 text-xs font-mono">
              <div className="px-3 py-2 border-b border-slate-800 dark:border-slate-800 light:border-slate-100 text-slate-400 light:text-slate-500">
                Signed in as <br />
                <strong className="text-slate-200 dark:text-slate-200 light:text-slate-900">{user?.email || 'tulsi@missionready.ai'}</strong>
              </div>
              <button
                onClick={handleLogout}
                className="w-full text-left flex items-center gap-2 px-3 py-2 mt-1 rounded-lg text-red-400 light:text-red-600 hover:bg-red-500/10 transition-colors"
              >
                <LogOut className="w-3.5 h-3.5" /> Sign Out
              </button>
            </div>
          )}
        </div>
      </div>
    </header>
  );
}
