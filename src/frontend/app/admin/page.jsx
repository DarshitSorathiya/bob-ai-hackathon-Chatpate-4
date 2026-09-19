'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Users, ShieldCheck, RefreshCw, CheckCircle, AlertTriangle } from 'lucide-react';
import { adminListUsers, adminUpdateUserRole, ROLE_LABELS, ROLES } from '../../lib/api';
import NavBar from '../../components/NavBar';
import RoleGuard from '../../components/RoleGuard';

const ROLE_OPTIONS = [ROLES.OPERATOR, ROLES.MAINTAINER, ROLES.ADMIN];

const ROLE_BADGE = {
  admin:      'bg-purple-500/15 border-purple-500/40 text-purple-600 dark:text-purple-400',
  maintainer: 'bg-amber-500/15 border-amber-500/40 text-amber-700 dark:text-amber-400',
  operator:   'bg-[#e1eadf] border-[#1e4d35]/30 text-[#1e4d35] dark:bg-[#1e4d35]/20 dark:text-emerald-400',
};

function RoleBadge({ role }) {
  return (
    <span className={`px-2 py-0.5 rounded-full text-[9px] font-mono font-bold uppercase tracking-widest border ${ROLE_BADGE[role] ?? 'bg-slate-700/40 border-slate-600 text-slate-300'}`}>
      {ROLE_LABELS[role] ?? role}
    </span>
  );
}

export default function AdminPage() {
  const router = useRouter();
  const [users, setUsers] = useState([]);
  const [loading, setLoading] = useState(true);
  const [updating, setUpdating] = useState(null); // userId being updated
  const [toast, setToast] = useState(null);        // { type: 'ok'|'err', msg }

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await adminListUsers();
      setUsers(Array.isArray(data) ? data : []);
    } catch (err) {
      setToast({ type: 'err', msg: err.message || 'Failed to load users' });
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { load(); }, [load]);

  const handleRoleChange = async (userId, newRole) => {
    setUpdating(userId);
    setToast(null);
    try {
      const updated = await adminUpdateUserRole(userId, newRole);
      setUsers((prev) => prev.map((u) => (u.id === userId ? { ...u, role: updated.role } : u)));
      setToast({ type: 'ok', msg: `Role updated to ${ROLE_LABELS[newRole] ?? newRole}` });
    } catch (err) {
      setToast({ type: 'err', msg: err.message || 'Failed to update role' });
    } finally {
      setUpdating(null);
      setTimeout(() => setToast(null), 3000);
    }
  };

  return (
    <RoleGuard minRole="admin">
      <NavBar title="Admin" onBack={() => router.push('/dashboard')}>
        <div className="space-y-6">
          {/* Header */}
          <div className="flex items-center justify-between flex-wrap gap-4 pt-1">
            <div className="space-y-1">
              <span className="inline-block px-3 py-0.5 rounded-md text-[10px] font-mono font-bold uppercase tracking-widest bg-purple-500/15 text-purple-600 dark:text-purple-400 border border-purple-500/30">
                ADMIN PANEL
              </span>
              <h1 className="text-xl font-bold font-sans text-[#122018] dark:text-slate-100 flex items-center gap-2">
                <Users className="w-5 h-5 text-[#1e4d35] dark:text-emerald-400" />
                User Management
              </h1>
              <p className="text-xs text-[#566b5c] dark:text-slate-400">
                Assign roles to registered users. Role changes take effect on their next request.
              </p>
            </div>
            <button
              onClick={load}
              disabled={loading}
              className="flex items-center gap-2 px-4 py-2 rounded-xl bg-[#1e4d35] text-white text-xs font-mono font-bold hover:bg-[#163a26] disabled:opacity-50 transition-colors"
            >
              <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
              Refresh
            </button>
          </div>

          {/* Toast */}
          {toast && (
            <div className={`flex items-center gap-2 p-3 rounded-xl border text-xs font-mono ${
              toast.type === 'ok'
                ? 'bg-emerald-500/10 border-emerald-500/30 text-emerald-600 dark:text-emerald-400'
                : 'bg-red-500/10 border-red-500/30 text-red-600 dark:text-red-400'
            }`}>
              {toast.type === 'ok'
                ? <CheckCircle className="w-4 h-4 shrink-0" />
                : <AlertTriangle className="w-4 h-4 shrink-0" />}
              {toast.msg}
            </div>
          )}

          {/* Users table */}
          {loading ? (
            <div className="text-center py-16 text-xs font-mono text-[#566b5c] dark:text-slate-400 animate-pulse">
              Loading users…
            </div>
          ) : users.length === 0 ? (
            <div className="text-center py-16 text-xs font-mono text-[#566b5c] dark:text-slate-400">
              No users found.
            </div>
          ) : (
            <div className="overflow-x-auto rounded-2xl border border-[#1e4d35]/20 dark:border-slate-800">
              <table className="w-full text-xs font-mono">
                <thead>
                  <tr className="border-b border-[#1e4d35]/20 dark:border-slate-800 bg-[#e1eadf]/50 dark:bg-[#0d1b13]/50">
                    <th className="text-left px-4 py-3 text-[#566b5c] dark:text-slate-400 font-bold uppercase tracking-widest text-[10px]">ID</th>
                    <th className="text-left px-4 py-3 text-[#566b5c] dark:text-slate-400 font-bold uppercase tracking-widest text-[10px]">Name</th>
                    <th className="text-left px-4 py-3 text-[#566b5c] dark:text-slate-400 font-bold uppercase tracking-widest text-[10px]">Email</th>
                    <th className="text-left px-4 py-3 text-[#566b5c] dark:text-slate-400 font-bold uppercase tracking-widest text-[10px]">Current Role</th>
                    <th className="text-left px-4 py-3 text-[#566b5c] dark:text-slate-400 font-bold uppercase tracking-widest text-[10px]">Status</th>
                    <th className="text-left px-4 py-3 text-[#566b5c] dark:text-slate-400 font-bold uppercase tracking-widest text-[10px]">Change Role</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((user) => (
                    <tr
                      key={user.id}
                      className="border-b border-[#1e4d35]/10 dark:border-slate-800/60 hover:bg-[#e1eadf]/30 dark:hover:bg-slate-900/40 transition-colors"
                    >
                      <td className="px-4 py-3 text-[#566b5c] dark:text-slate-500">{user.id}</td>
                      <td className="px-4 py-3 font-semibold text-[#122018] dark:text-slate-100">{user.full_name}</td>
                      <td className="px-4 py-3 text-[#566b5c] dark:text-slate-400">{user.email}</td>
                      <td className="px-4 py-3">
                        <RoleBadge role={user.role} />
                      </td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 rounded-full text-[9px] font-bold uppercase border ${
                          user.is_active
                            ? 'bg-emerald-500/15 border-emerald-500/30 text-emerald-600 dark:text-emerald-400'
                            : 'bg-red-500/15 border-red-500/30 text-red-500'
                        }`}>
                          {user.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <select
                          value={user.role}
                          disabled={updating === user.id}
                          onChange={(e) => handleRoleChange(user.id, e.target.value)}
                          className="bg-[#e1eadf] dark:bg-slate-900 border border-[#1e4d35]/30 dark:border-slate-700 rounded-lg px-2 py-1 text-xs font-mono text-[#122018] dark:text-slate-200 focus:outline-none focus:border-[#1e4d35] disabled:opacity-50 cursor-pointer"
                        >
                          {ROLE_OPTIONS.map((r) => (
                            <option key={r} value={r}>{ROLE_LABELS[r]}</option>
                          ))}
                        </select>
                        {updating === user.id && (
                          <span className="ml-2 text-[#1e4d35] dark:text-emerald-400 animate-pulse">saving…</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          {/* RBAC reference */}
          <div className="rounded-2xl border border-[#1e4d35]/20 dark:border-slate-800 p-5 bg-[#e1eadf]/30 dark:bg-[#0d1b13]/50 space-y-3">
            <h2 className="text-xs font-mono font-bold uppercase tracking-widest text-[#122018] dark:text-slate-300 flex items-center gap-2">
              <ShieldCheck className="w-4 h-4 text-[#1e4d35] dark:text-emerald-400" />
              Role Permissions Reference
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-3 text-[11px]">
              {[
                {
                  role: 'operator',
                  perms: [
                    'View dashboard, assets, missions',
                    'View alerts, maintenance queue',
                    'View data quality events',
                    'Use copilot',
                  ],
                },
                {
                  role: 'maintainer',
                  perms: [
                    'All Operator permissions',
                    'Create & update assets',
                    'Create & update work orders',
                    'View ML model registry',
                  ],
                },
                {
                  role: 'admin',
                  perms: [
                    'All Maintainer permissions',
                    'Access Admin panel',
                    'Change user roles',
                    'Full system access',
                  ],
                },
              ].map(({ role, perms }) => (
                <div key={role} className="space-y-2">
                  <RoleBadge role={role} />
                  <ul className="space-y-1 pl-1">
                    {perms.map((p) => (
                      <li key={p} className="text-[#566b5c] dark:text-slate-400 flex items-start gap-1.5">
                        <span className="text-[#1e4d35] dark:text-emerald-500 mt-0.5">›</span>
                        {p}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
          </div>
        </div>
      </NavBar>
    </RoleGuard>
  );
}
