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
    <header className="w-full bg-[#f4f6ee]/90 dark:bg-[#0d1b13]/90 border-b border-[#1e4d35]/20 dark:border-[#78b394]/20 backdrop-blur-xl sticky top-0 z-50 px-6 lg:px-12 py-3 flex items-center justify-between gap-6 select-none shadow-md shadow-[#1e4d35]/5 dark:shadow-black/40 transition-colors duration-200">
      {/* Left Brand Logo */}
      <Link href="/dashboard" className="flex items-center gap-3 group shrink-0">
        <div className="w-9 h-9 rounded-xl bg-[#e1eadf] dark:bg-[#1e4d35]/30 border border-[#1e4d35]/30 dark:border-[#4e9f76]/40 flex items-center justify-center text-[#1e4d35] dark:text-[#4e9f76] shadow-sm group-hover:border-[#1e4d35] transition-colors">
          <svg className="w-5 h-5" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z" />
            <path d="M12 8v8" />
            <path d="M8 12h8" />
          </svg>
        </div>
        <span className="text-base font-extrabold font-mono tracking-wider text-[#122018] dark:text-slate-100 uppercase">
          MISSION<span className="text-[#1e4d35] dark:text-[#4e9f76]">READY</span>
        </span>
      </Link>

      {/* Center Navigation Tabs with Spacing */}
      <nav className="flex items-center gap-1.5 md:gap-3 bg-[#e1eadf]/60 dark:bg-[#122419]/80 px-3 py-1.5 rounded-full border border-[#1e4d35]/20 dark:border-[#4e9f76]/30 shadow-inner">
        {navItems.map((item) => {
          const isActive = pathname === item.href || (item.href !== '/dashboard' && pathname?.startsWith(item.href));
          return (
            <Link
              key={item.href}
              href={item.href}
              className={`px-3.5 py-1.5 rounded-full text-xs font-mono transition-all duration-200 tracking-wide ${
                isActive
                  ? 'bg-[#1e4d35] text-white font-bold border border-[#163a26] shadow-md shadow-[#1e4d35]/20'
                  : 'text-[#122018] dark:text-slate-300 hover:text-[#1e4d35] dark:hover:text-white hover:bg-[#e1eadf] dark:hover:bg-[#1e4d35]/40'
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
          className="p-2 rounded-full bg-[#e1eadf]/80 dark:bg-[#122419]/80 border border-[#1e4d35]/30 dark:border-[#4e9f76]/40 text-[#1e4d35] dark:text-amber-400 hover:border-[#1e4d35] transition-all duration-200 shadow-sm"
        >
          {theme === 'dark' ? <Sun className="w-4 h-4" /> : <Moon className="w-4 h-4" />}
        </button>

        {/* User Profile Controls */}
        <div className="relative">
          <button
            onClick={() => setUserMenuOpen(!userMenuOpen)}
            className="flex items-center gap-2.5 px-3.5 py-1.5 rounded-full bg-[#e1eadf]/80 dark:bg-[#122419]/80 border border-[#1e4d35]/30 dark:border-[#4e9f76]/40 hover:border-[#1e4d35] text-xs font-mono text-[#122018] dark:text-slate-200 transition-colors"
          >
            <div className="w-6 h-6 rounded-full bg-[#1e4d35]/20 dark:bg-[#4e9f76]/20 border border-[#1e4d35]/30 flex items-center justify-center text-[#1e4d35] dark:text-[#4e9f76]">
              <User className="w-3.5 h-3.5" />
            </div>
            <span className="font-medium text-[#122018] dark:text-slate-300 hidden sm:inline">
              Welcome, <strong className="text-[#1e4d35] dark:text-slate-100">{firstName}</strong>
            </span>
            <ChevronDown className="w-3.5 h-3.5 text-[#566b5c] dark:text-slate-400" />
          </button>

          {userMenuOpen && (
            <div className="absolute right-0 mt-2 w-48 rounded-xl bg-white dark:bg-[#122419] border border-[#1e4d35]/30 dark:border-[#4e9f76]/40 shadow-2xl p-2 z-50 text-xs font-mono">
              <div className="px-3 py-2 border-b border-slate-200 dark:border-slate-800 text-[#566b5c] dark:text-slate-400">
                Signed in as <br />
                <strong className="text-[#122018] dark:text-slate-200">{user?.email || 'tulsi@missionready.ai'}</strong>
              </div>
              <button
                onClick={handleLogout}
                className="w-full text-left flex items-center gap-2 px-3 py-2 mt-1 rounded-lg text-red-600 dark:text-red-400 hover:bg-red-500/10 transition-colors"
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
