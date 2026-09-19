'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Wrench, Plus, CheckCircle2, AlertTriangle, Clock, ArrowLeft, Plane, Shield, Layers, Send } from 'lucide-react';
import NavBar from '../../components/NavBar';
import { isAuthenticated, listAssets, createWorkOrder, listWorkOrders, getMaintenanceQueue } from '../../lib/api';

const URGENCY_BADGES = {
  IMMEDIATE: 'bg-red-500/15 border-red-500/30 text-red-400',
  URGENT:    'bg-amber-500/15 border-amber-500/30 text-amber-400',
  SCHEDULED: 'bg-[#e1eadf] border-[#1e4d35]/30 text-[#1e4d35] dark:bg-[#1e4d35]/30 dark:text-emerald-300',
  ROUTINE:   'bg-slate-700/30 border-slate-700 text-slate-400',
};

export default function RequestPage() {
  const router = useRouter();
  const [assets, setAssets] = useState([]);
  const [workOrders, setWorkOrders] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  const [form, setForm] = useState({
    title: '',
    description: '',
    asset_id: '',
    component_id: '',
    urgency_level: 'SCHEDULED',
    is_blocking: false,
    estimated_hours: '2',
  });

  // Handle URL query parameters for preselected asset
  useEffect(() => {
    if (!isAuthenticated()) { router.replace('/login'); return; }

    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const assetId = params.get('asset_id');
      if (assetId) {
        setForm((f) => ({
          ...f,
          asset_id: assetId,
          title: f.title || `Component Request — Asset #${assetId}`,
        }));
      }
    }
  }, [router]);

  const loadData = useCallback(async () => {
    setLoading(true);
    try {
      const [aList, woList] = await Promise.allSettled([
        listAssets({ limit: 100 }),
        listWorkOrders({ limit: 100 }),
      ]);
      if (aList.status === 'fulfilled') setAssets(aList.value || []);
      if (woList.status === 'fulfilled') setWorkOrders(woList.value || []);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const setField = (field, value) => {
    setForm((prev) => ({ ...prev, [field]: value }));
  };

  const handleAssetSelect = (asset) => {
    setForm((prev) => ({
      ...prev,
      asset_id: asset.id || asset.asset_code,
      title: `Component Request — ${asset.asset_code} (${asset.call_sign || asset.asset_type})`,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    setSuccessMsg('');
    setSaving(true);

    try {
      const payload = {
        title: form.title.trim() || `Component Request for Asset #${form.asset_id}`,
        description: form.description.trim() || undefined,
        asset_id: form.asset_id || undefined,
        component_id: form.component_id.trim() || undefined,
        urgency_level: form.urgency_level,
        is_blocking: form.is_blocking,
        estimated_hours: parseFloat(form.estimated_hours) || 2,
      };

      await createWorkOrder(payload);
      setSuccessMsg(`Component request successfully submitted for Asset #${form.asset_id || 'Fleet'}.`);
      setForm({
        title: '',
        description: '',
        asset_id: '',
        component_id: '',
        urgency_level: 'SCHEDULED',
        is_blocking: false,
        estimated_hours: '2',
      });
      await loadData();
    } catch (err) {
      setErrorMsg(err.message || 'Failed to submit request.');
    } finally {
      setSaving(false);
    }
  };

  return (
    <NavBar title="Component & Maintenance Requests" onBack={() => router.push('/dashboard')}>
      <div className="space-y-6">

        {/* Title Header Banner */}
        <div className="flex items-center justify-between flex-wrap gap-4 pt-1">
          <div className="space-y-1">
            <span className="inline-block px-3 py-0.5 rounded-md text-[10px] font-mono font-bold uppercase tracking-widest bg-[#e1eadf] text-[#1e4d35] dark:bg-[#1e4d35]/30 dark:text-emerald-300 border border-[#1e4d35]/30">
              SUPPLY & LOGISTICS REQUISITION
            </span>
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-[#122018] dark:text-slate-100 font-sans">
              Component Requests
            </h1>
            <p className="text-xs sm:text-sm text-[#566b5c] dark:text-slate-400 max-w-2xl">
              Request component replacements, specialized parts, and maintenance work orders for specific fleet assets across airbases.
            </p>
          </div>
        </div>

        {/* Main Grid: Form Left (7 Cols) + Asset Selection Cards Right (5 Cols) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          
          {/* Left Form Panel */}
          <div className="lg:col-span-7 dashboard-card-shape p-6 rounded-2xl space-y-5">
            <div className="flex items-center gap-2.5 pb-4 border-b border-[#1e4d35]/15 dark:border-slate-800">
              <Wrench className="w-5 h-5 text-[#1e4d35] dark:text-[#4e9f76]" />
              <h2 className="text-sm font-bold font-mono text-[#122018] dark:text-slate-100 uppercase tracking-wider">
                Submit New Component Request
              </h2>
            </div>

            {successMsg && (
              <div className="p-3.5 rounded-xl bg-emerald-500/15 border border-emerald-500/30 text-emerald-600 dark:text-emerald-400 text-xs font-mono flex items-center gap-2">
                <CheckCircle2 className="w-4 h-4 shrink-0" />
                <span>{successMsg}</span>
              </div>
            )}

            {errorMsg && (
              <div className="p-3.5 rounded-xl bg-red-500/15 border border-red-500/30 text-red-600 dark:text-red-400 text-xs font-mono flex items-center gap-2">
                <AlertTriangle className="w-4 h-4 shrink-0" />
                <span>{errorMsg}</span>
              </div>
            )}

            <form onSubmit={handleSubmit} className="space-y-4">
              
              {/* Select Target Asset */}
              <div>
                <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-[#122018] dark:text-slate-300 mb-1">
                  Target Fleet Asset / Location *
                </label>
                <select
                  required
                  value={form.asset_id}
                  onChange={(e) => setField('asset_id', e.target.value)}
                  className="w-full px-3.5 py-2.5 text-xs font-mono bg-[#f4f6ee] dark:bg-[#0d1b13] border border-[#1e4d35]/30 dark:border-[#4e9f76]/30 rounded-xl text-[#122018] dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-[#1e4d35]"
                >
                  <option value="">-- Select Enrolled Aircraft / Vehicle --</option>
                  {assets.map((a) => (
                    <option key={a.id || a.asset_code} value={a.id || a.asset_code}>
                      {a.asset_code} — {a.call_sign || a.asset_type} ({a.manufacturer || 'Fleet'})
                    </option>
                  ))}
                </select>
              </div>

              {/* Request Title */}
              <div>
                <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-[#122018] dark:text-slate-300 mb-1">
                  Request Title *
                </label>
                <input
                  required
                  type="text"
                  value={form.title}
                  onChange={(e) => setField('title', e.target.value)}
                  placeholder="e.g., Main Rotor Shaft Hydraulic Seal Replacement"
                  className="w-full px-3.5 py-2.5 text-xs font-mono bg-[#f4f6ee] dark:bg-[#0d1b13] border border-[#1e4d35]/30 dark:border-[#4e9f76]/30 rounded-xl text-[#122018] dark:text-slate-100 placeholder-[#566b5c]/60 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-[#1e4d35]"
                />
              </div>

              {/* Component Code & Estimated Hours */}
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-[#122018] dark:text-slate-300 mb-1">
                    Component / Part ID
                  </label>
                  <input
                    type="text"
                    value={form.component_id}
                    onChange={(e) => setField('component_id', e.target.value)}
                    placeholder="e.g., CMP-ROTOR-99"
                    className="w-full px-3.5 py-2.5 text-xs font-mono bg-[#f4f6ee] dark:bg-[#0d1b13] border border-[#1e4d35]/30 dark:border-[#4e9f76]/30 rounded-xl text-[#122018] dark:text-slate-100 placeholder-[#566b5c]/60 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-[#1e4d35]"
                  />
                </div>

                <div>
                  <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-[#122018] dark:text-slate-300 mb-1">
                    Urgency Priority
                  </label>
                  <select
                    value={form.urgency_level}
                    onChange={(e) => setField('urgency_level', e.target.value)}
                    className="w-full px-3.5 py-2.5 text-xs font-mono bg-[#f4f6ee] dark:bg-[#0d1b13] border border-[#1e4d35]/30 dark:border-[#4e9f76]/30 rounded-xl text-[#122018] dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-[#1e4d35]"
                  >
                    <option value="IMMEDIATE">IMMEDIATE (Critical Priority)</option>
                    <option value="URGENT">URGENT (High Priority)</option>
                    <option value="SCHEDULED">SCHEDULED (Normal Priority)</option>
                    <option value="ROUTINE">ROUTINE (Low Priority)</option>
                  </select>
                </div>
              </div>

              {/* Description */}
              <div>
                <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-[#122018] dark:text-slate-300 mb-1">
                  Technical Justification & Notes
                </label>
                <textarea
                  rows={3}
                  value={form.description}
                  onChange={(e) => setField('description', e.target.value)}
                  placeholder="Specify component part specifications, failure symptoms, or airbase delivery instructions..."
                  className="w-full px-3.5 py-2.5 text-xs font-mono bg-[#f4f6ee] dark:bg-[#0d1b13] border border-[#1e4d35]/30 dark:border-[#4e9f76]/30 rounded-xl text-[#122018] dark:text-slate-100 placeholder-[#566b5c]/60 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-[#1e4d35] resize-none"
                />
              </div>

              {/* Options & Action Row */}
              <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 pt-2 border-t border-[#1e4d35]/15 dark:border-slate-800">
                <label className="flex items-center gap-2 cursor-pointer text-xs font-mono text-[#122018] dark:text-slate-300">
                  <input
                    type="checkbox"
                    checked={form.is_blocking}
                    onChange={(e) => setField('is_blocking', e.target.checked)}
                    className="rounded border-[#1e4d35]/40 text-[#1e4d35] focus:ring-0"
                  />
                  Blocks Mission Readiness
                </label>

                <button
                  type="submit"
                  disabled={saving}
                  className="px-6 py-3 rounded-xl bg-[#1e4d35] hover:bg-[#163a26] text-white font-mono font-bold text-xs transition-all shadow-md flex items-center justify-center gap-2 disabled:opacity-50"
                >
                  <Send className="w-4 h-4" />
                  {saving ? 'Submitting Request…' : 'Submit Requisition'}
                </button>
              </div>

            </form>
          </div>

          {/* Right 1-Click Quick Select Enrolled Asset Cards */}
          <div className="lg:col-span-5 space-y-4">
            <div className="dashboard-card-shape p-5 rounded-2xl">
              <div className="flex items-center justify-between pb-3 mb-3 border-b border-[#1e4d35]/15 dark:border-slate-800">
                <span className="text-xs font-mono font-bold uppercase tracking-wider text-[#1e4d35] dark:text-[#4e9f76] flex items-center gap-2">
                  <Plane className="w-4 h-4" /> 1-Click Asset Requisition
                </span>
                <span className="text-[10px] font-mono text-[#566b5c] dark:text-slate-400">
                  Enrolled Fleet
                </span>
              </div>

              <div className="space-y-2.5 max-h-[420px] overflow-y-auto pr-1">
                {assets.map((asset) => {
                  const isSelected = form.asset_id === (asset.id || asset.asset_code);
                  return (
                    <div
                      key={asset.id || asset.asset_code}
                      onClick={() => handleAssetSelect(asset)}
                      className={`p-3.5 rounded-xl border transition-all cursor-pointer flex items-center justify-between gap-3 ${
                        isSelected
                          ? 'bg-[#1e4d35]/20 border-[#1e4d35] dark:bg-[#1e4d35]/40 dark:border-[#4e9f76]'
                          : 'bg-[#f4f6ee]/60 dark:bg-[#0d1b13]/60 border-[#1e4d35]/20 hover:border-[#1e4d35]/50'
                      }`}
                    >
                      <div>
                        <div className="flex items-center gap-2">
                          <strong className="text-xs font-mono text-[#122018] dark:text-slate-100">
                            {asset.asset_code}
                          </strong>
                          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-[#e1eadf] dark:bg-[#122419] text-[#1e4d35] dark:text-emerald-300 border border-[#1e4d35]/20">
                            {asset.call_sign || asset.asset_type}
                          </span>
                        </div>
                        <p className="text-[11px] font-sans text-[#566b5c] dark:text-slate-400 mt-0.5 truncate">
                          {asset.description || `${asset.manufacturer} ${asset.model_number || ''}`}
                        </p>
                      </div>

                      <button
                        type="button"
                        className={`px-3 py-1 rounded-lg font-mono text-[11px] font-semibold transition-colors shrink-0 ${
                          isSelected
                            ? 'bg-[#1e4d35] text-white'
                            : 'bg-[#e1eadf] text-[#1e4d35] dark:bg-slate-800 dark:text-slate-200 hover:bg-[#1e4d35] hover:text-white'
                        }`}
                      >
                        {isSelected ? 'Selected' : 'Select'}
                      </button>
                    </div>
                  );
                })}
              </div>
            </div>
          </div>

        </div>

        {/* Bottom Active Requests Table */}
        <div className="dashboard-card-shape p-6 rounded-2xl space-y-4">
          <div className="flex items-center justify-between border-b border-[#1e4d35]/15 dark:border-slate-800 pb-3">
            <h3 className="text-sm font-bold font-mono text-[#122018] dark:text-slate-100 uppercase tracking-wider">
              Submitted Component Requisitions ({workOrders.length})
            </h3>
          </div>

          <div className="divide-y divide-[#1e4d35]/10 dark:divide-slate-800">
            {workOrders.length === 0 ? (
              <p className="py-6 text-xs font-mono text-[#566b5c] dark:text-slate-500 text-center">
                No active component requests submitted.
              </p>
            ) : (
              workOrders.map((wo) => (
                <div key={wo.id} className="py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs font-mono">
                  <div>
                    <span className="font-bold text-[#122018] dark:text-slate-100">{wo.title}</span>
                    <span className="text-[#566b5c] dark:text-slate-400 ml-2">[{wo.asset_id || 'Fleet'}]</span>
                  </div>

                  <div className="flex items-center gap-3">
                    <span className={`px-2.5 py-0.5 rounded-full text-[10px] font-bold border ${URGENCY_BADGES[wo.urgency_level] || URGENCY_BADGES.SCHEDULED}`}>
                      {wo.urgency_level || 'SCHEDULED'}
                    </span>
                    <span className="text-[#566b5c] dark:text-slate-400">
                      {wo.status || wo.maintenance_state || 'SUBMITTED'}
                    </span>
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

      </div>
    </NavBar>
  );
}
