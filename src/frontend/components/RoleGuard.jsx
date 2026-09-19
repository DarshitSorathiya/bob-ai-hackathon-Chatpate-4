'use client';

import React, { useEffect, useState } from 'react';
import { useRouter } from 'next/navigation';
import { ShieldOff } from 'lucide-react';
import { isAuthenticated, hasMinRole, getUserRole, ROLE_LABELS } from '../lib/api';

/**
 * RoleGuard — wraps a page to enforce authentication and a minimum role level.
 *
 * Usage:
 *   <RoleGuard minRole="maintainer">
 *     <PageContent />
 *   </RoleGuard>
 *
 * Props:
 *   minRole  — minimum role required: 'operator' | 'maintainer' | 'admin'
 *              Defaults to 'operator' (any authenticated user).
 *   children — page content rendered when access is granted.
 */
export default function RoleGuard({ minRole = 'operator', children }) {
  const router = useRouter();
  const [status, setStatus] = useState('checking'); // 'checking' | 'allowed' | 'forbidden'

  useEffect(() => {
    if (!isAuthenticated()) {
      router.replace('/login');
      return;
    }
    if (!hasMinRole(minRole)) {
      setStatus('forbidden');
      return;
    }
    setStatus('allowed');
  }, [minRole, router]);

  if (status === 'checking') return null;

  if (status === 'forbidden') {
    const userRoleLabel = ROLE_LABELS[getUserRole()] ?? getUserRole();
    const requiredLabel = ROLE_LABELS[minRole] ?? minRole;
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#f4f6ee] dark:bg-[#0d1b13] p-6">
        <div className="max-w-sm w-full text-center space-y-4">
          <div className="mx-auto w-16 h-16 rounded-full bg-red-500/10 border border-red-500/30 flex items-center justify-center">
            <ShieldOff className="w-8 h-8 text-red-500" />
          </div>
          <h1 className="text-xl font-bold font-mono text-[#122018] dark:text-slate-100 uppercase tracking-wider">
            Access Denied
          </h1>
          <p className="text-sm text-[#566b5c] dark:text-slate-400">
            This page requires <span className="font-semibold text-[#1e4d35] dark:text-emerald-400">{requiredLabel}</span> or
            higher access.
          </p>
          <p className="text-xs text-[#566b5c] dark:text-slate-500 font-mono">
            Your current role: <span className="font-bold text-[#122018] dark:text-slate-300">{userRoleLabel}</span>
          </p>
          <button
            onClick={() => router.push('/dashboard')}
            className="mt-2 px-6 py-2 rounded-xl bg-[#1e4d35] text-white text-xs font-mono font-bold hover:bg-[#163a26] transition-colors"
          >
            Back to Dashboard
          </button>
        </div>
      </div>
    );
  }

  return <>{children}</>;
}
