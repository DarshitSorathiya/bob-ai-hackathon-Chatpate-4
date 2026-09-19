'use client';

import React, { useState, useEffect, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Wrench, CheckCircle2, AlertTriangle, Send, PackageCheck, Clock, ShieldCheck, UserCheck, ArrowRight } from 'lucide-react';
import NavBar from '../../components/NavBar';
import {
  isAuthenticated, getUser, listAssets, createWorkOrder, listWorkOrders,
  getResourceRequests, createResourceRequest, updateResourceRequestStatus
} from '../../lib/api';

const URGENCY_BADGES = {
  IMMEDIATE: 'bg-red-500/15 border-red-500/30 text-red-400',
  URGENT:    'bg-amber-500/15 border-amber-500/30 text-amber-400',
  SCHEDULED: 'bg-[#e1eadf] border-[#1e4d35]/30 text-[#1e4d35] dark:bg-[#1e4d35]/30 dark:text-emerald-300',
  ROUTINE:   'bg-slate-700/30 border-slate-700 text-slate-400',
};

const STATUS_BADGES = {
  PENDING:   'bg-amber-500/20 text-amber-300 border-amber-500/40',
  APPROVED:  'bg-emerald-500/20 text-emerald-300 border-emerald-500/40',
  FULFILLED: 'bg-cyan-500/20 text-cyan-300 border-cyan-500/40',
  REJECTED:  'bg-red-500/20 text-red-300 border-red-500/40',
};

export default function RequestPage() {
  const router = useRouter();
  const currentUser = getUser() || { id: 'usr_operator_bengaluru', full_name: 'Tulsi' };

  const [assets, setAssets] = useState([]);
  const [workOrders, setWorkOrders] = useState([]);
  const [resourceRequests, setResourceRequests] = useState([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');
  const [errorMsg, setErrorMsg] = useState('');

  const [selectedProvider, setSelectedProvider] = useState(null);
  const [selectedOrigin, setSelectedOrigin] = useState(null);

  // Form State
  const [form, setForm] = useState({
    title: '',
    resource_name: 'Hydraulic Fluid (MIL-PRF-83282)',
    quantity: '20 units',
    description: '',
    asset_id: 'TJS-014',
    component_id: 'CMP-HYD-88',
    urgency_level: 'URGENT',
    is_blocking: true,
    estimated_hours: '2',
  });

  // Handle URL query parameters
  useEffect(() => {
    if (!isAuthenticated()) { router.replace('/login'); return; }

    if (typeof window !== 'undefined') {
      const params = new URLSearchParams(window.location.search);
      const assetId = params.get('asset_id');
      const locName = params.get('location');
      const aircraftName = params.get('aircraft');
      const providerId = params.get('provider_id');
      const facilityName = params.get('facility');

      if (providerId || facilityName) {
        // Target is an External Resource Support Facility (User B / Provider)
        const provObj = {
          provider_id: providerId || 'usr_provider_pune',
          facility: facilityName || 'Lohegaon Resource Support Facility, Pune, Maharashtra, India',
          location: locName || 'Pune, Maharashtra, India',
        };
        setSelectedProvider(provObj);

        const defaultDesc = `Resource request from HAL Airport Base, Bengaluru to ${provObj.facility} for 20 units of Hydraulic Fluid (MIL-PRF-83282).`;
        setForm((f) => ({
          ...f,
          title: `Resource Request — ${provObj.facility}`,
          resource_name: 'Hydraulic Fluid (MIL-PRF-83282)',
          quantity: '20 units',
          description: defaultDesc,
        }));
      } else if (assetId || locName) {
        // Target is an Own Asset Requisition
        const originObj = {
          asset_id: assetId || 'TJS-014',
          location: locName || 'HAL Airport Base, Bengaluru, Karnataka, India',
          aircraft: aircraftName || 'HAL Tejas Mk1A',
        };
        setSelectedOrigin(originObj);

        setForm((f) => ({
          ...f,
          asset_id: assetId || f.asset_id,
          title: `Component Request — ${originObj.aircraft} (${originObj.asset_id})`,
          description: `Component requested for ${originObj.aircraft} (${originObj.asset_id}) stationed at ${originObj.location}.`,
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
      if (aList.status === 'fulfilled') {
        const assetsVal = aList.value;
        const assetsArr = Array.isArray(assetsVal) ? assetsVal : (assetsVal?.items || []);
        setAssets(assetsArr);
      }
      if (woList.status === 'fulfilled') {
        const woVal = woList.value;
        const woArr = Array.isArray(woVal)
          ? woVal
          : Array.isArray(woVal?.items)
          ? woVal.items
          : Array.isArray(woVal?.work_orders)
          ? woVal.work_orders
          : [];
        setWorkOrders(woArr);
      }
      setResourceRequests(getResourceRequests());
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
      description: `Component requested for ${asset.asset_code} (${asset.call_sign || asset.asset_type}) stationed at HAL Airport Base, Bengaluru, Karnataka, India.`,
    }));
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setErrorMsg('');
    setSuccessMsg('');
    setSaving(true);

    try {
      if (selectedProvider) {
        // Submit Resource Request to External Provider Facility
        const reqPayload = {
          requester_id: currentUser.id || 'usr_operator_bengaluru',
          requester_name: `${currentUser.full_name || 'Tulsi'} (HAL Bengaluru Base)`,
          requester_location: 'HAL Airport Base, Bengaluru, Karnataka, India',
          provider_id: selectedProvider.provider_id,
          provider_facility: selectedProvider.facility,
          resource_name: form.resource_name,
          quantity: form.quantity,
          priority: form.urgency_level,
          reason: form.description || `Request for ${form.quantity} of ${form.resource_name}`,
        };

        createResourceRequest(reqPayload);
        setSuccessMsg(`Resource request for ${form.quantity} of ${form.resource_name} successfully sent to ${selectedProvider.facility}. Request status: PENDING.`);
      } else {
        // Submit Internal Asset Work Order Requisition
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
        setSuccessMsg(`Component requisition successfully submitted for Asset #${form.asset_id || 'Fleet'}.`);
      }

      await loadData();
    } catch (err) {
      setErrorMsg(err.message || 'Failed to submit request.');
    } finally {
      setSaving(false);
    }
  };

  const handleStatusUpdate = (reqId, newStatus) => {
    updateResourceRequestStatus(reqId, newStatus);
    setResourceRequests(getResourceRequests());
  };

  return (
    <NavBar title="Resource Requisitions & Supply Requests" onBack={() => router.push('/dashboard')}>
      <div className="space-y-6">

        {/* Title Header Banner */}
        <div className="flex items-center justify-between flex-wrap gap-4 pt-1">
          <div className="space-y-1">
            <span className="inline-block px-3 py-0.5 rounded-md text-[10px] font-mono font-bold uppercase tracking-widest bg-[#e1eadf] text-[#1e4d35] dark:bg-[#1e4d35]/30 dark:text-emerald-300 border border-[#1e4d35]/30">
              SUPPLY & LOGISTICS REQUISITION
            </span>
            <h1 className="text-3xl sm:text-4xl font-extrabold tracking-tight text-[#122018] dark:text-slate-100 font-sans">
              Resource Requests
            </h1>
            <p className="text-xs sm:text-sm text-[#566b5c] dark:text-slate-400 max-w-2xl">
              Request supplies, specialized components, and logistics support from sector resource facilities with strict user-to-user privacy protection.
            </p>
          </div>
        </div>

        {/* Main Grid: Form Left (7 Cols) + Asset Selection / Resource Info Right (5 Cols) */}
        <div className="grid grid-cols-1 lg:grid-cols-12 gap-6 items-start">
          
          {/* Left Form Panel */}
          <div className="lg:col-span-7 dashboard-card-shape p-6 rounded-2xl space-y-5">
            <div className="flex items-center gap-2.5 pb-4 border-b border-[#1e4d35]/15 dark:border-slate-800">
              <Wrench className="w-5 h-5 text-[#1e4d35] dark:text-[#4e9f76]" />
              <h2 className="text-sm font-bold font-mono text-[#122018] dark:text-slate-100 uppercase tracking-wider">
                {selectedProvider ? 'Send Resource Request to Support Facility' : 'Submit Component Requisition'}
              </h2>
            </div>

            {/* Target Provider Banner */}
            {selectedProvider && (
              <div className="p-3.5 rounded-xl bg-teal-500/15 border border-teal-500/40 text-[#122018] dark:text-slate-100 flex items-start justify-between gap-3 shadow-sm">
                <div>
                  <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-teal-600 dark:text-teal-300">
                    TARGET RESOURCE SUPPORT PROVIDER
                  </span>
                  <p className="text-xs font-mono font-bold text-teal-700 dark:text-teal-200 mt-0.5">
                    🛡️ {selectedProvider.facility}
                  </p>
                  <p className="text-[11px] font-mono text-[#566b5c] dark:text-slate-300 mt-0.5">
                    📍 Destination Base: {selectedProvider.location}
                  </p>
                  <p className="text-[10px] font-mono text-emerald-600 dark:text-emerald-400 mt-1 font-semibold">
                    🔒 Provider private aircraft fleet status remains strictly hidden
                  </p>
                </div>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-teal-700 text-white font-semibold shrink-0">
                  PROVIDER TARGET
                </span>
              </div>
            )}

            {/* Target Own Asset Banner */}
            {!selectedProvider && selectedOrigin && (
              <div className="p-3.5 rounded-xl bg-[#e1eadf] dark:bg-[#1e4d35]/30 border border-[#1e4d35]/30 dark:border-[#4e9f76]/40 text-[#122018] dark:text-slate-100 flex items-start justify-between gap-3 shadow-sm">
                <div>
                  <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#1e4d35] dark:text-emerald-400">
                    MY FLEET ASSET LOCATION
                  </span>
                  <p className="text-xs font-mono font-bold text-[#1e4d35] dark:text-emerald-300 mt-0.5">
                    ✈️ {selectedOrigin.aircraft} ({selectedOrigin.asset_id})
                  </p>
                  <p className="text-xs font-mono text-[#566b5c] dark:text-slate-300 mt-0.5">
                    📍 {selectedOrigin.location}
                  </p>
                </div>
                <span className="px-2 py-0.5 rounded text-[10px] font-mono bg-[#1e4d35] text-white font-semibold shrink-0">
                  OWN FLEET
                </span>
              </div>
            )}

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
              
              {selectedProvider ? (
                /* Resource Request Form Controls */
                <>
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                    <div>
                      <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-[#122018] dark:text-slate-300 mb-1">
                        Resource / Supply Required *
                      </label>
                      <input
                        required
                        type="text"
                        value={form.resource_name}
                        onChange={(e) => setField('resource_name', e.target.value)}
                        placeholder="e.g., Hydraulic Fluid (MIL-PRF-83282)"
                        className="w-full px-3.5 py-2.5 text-xs font-mono bg-[#f4f6ee] dark:bg-[#0d1b13] border border-[#1e4d35]/30 dark:border-[#4e9f76]/30 rounded-xl text-[#122018] dark:text-slate-100 placeholder-[#566b5c]/60 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-[#1e4d35]"
                      />
                    </div>

                    <div>
                      <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-[#122018] dark:text-slate-300 mb-1">
                        Quantity Required *
                      </label>
                      <input
                        required
                        type="text"
                        value={form.quantity}
                        onChange={(e) => setField('quantity', e.target.value)}
                        placeholder="e.g., 20 units"
                        className="w-full px-3.5 py-2.5 text-xs font-mono bg-[#f4f6ee] dark:bg-[#0d1b13] border border-[#1e4d35]/30 dark:border-[#4e9f76]/30 rounded-xl text-[#122018] dark:text-slate-100 placeholder-[#566b5c]/60 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-[#1e4d35]"
                      />
                    </div>
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
                      <option value="IMMEDIATE">IMMEDIATE (Critical Operational Priority)</option>
                      <option value="URGENT">URGENT (High Priority)</option>
                      <option value="SCHEDULED">SCHEDULED (Normal Priority)</option>
                      <option value="ROUTINE">ROUTINE (Low Priority)</option>
                    </select>
                  </div>
                </>
              ) : (
                /* Internal Asset Requisition Controls */
                <>
                  <div>
                    <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-[#122018] dark:text-slate-300 mb-1">
                      Target Fleet Asset *
                    </label>
                    <select
                      required
                      value={form.asset_id}
                      onChange={(e) => setField('asset_id', e.target.value)}
                      className="w-full px-3.5 py-2.5 text-xs font-mono bg-[#f4f6ee] dark:bg-[#0d1b13] border border-[#1e4d35]/30 dark:border-[#4e9f76]/30 rounded-xl text-[#122018] dark:text-slate-100 focus:outline-none focus:ring-2 focus:ring-[#1e4d35]"
                    >
                      <option value="">-- Select Own Fleet Aircraft --</option>
                      {assets.map((a) => (
                        <option key={a.id || a.asset_code} value={a.id || a.asset_code}>
                          {a.asset_code} — {a.call_sign || a.asset_type} ({a.manufacturer || 'HAL'})
                        </option>
                      ))}
                    </select>
                  </div>

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
                </>
              )}

              {/* Description / Reason Field */}
              <div>
                <label className="block text-[11px] font-mono font-bold uppercase tracking-wider text-[#122018] dark:text-slate-300 mb-1">
                  Reason & Technical Justification (Auto-Filled)
                </label>
                <textarea
                  rows={3}
                  value={form.description}
                  onChange={(e) => setField('description', e.target.value)}
                  placeholder="Specify resource specifications, delivery instructions, or failure symptoms..."
                  className="w-full px-3.5 py-2.5 text-xs font-mono bg-[#f4f6ee] dark:bg-[#0d1b13] border border-[#1e4d35]/30 dark:border-[#4e9f76]/30 rounded-xl text-[#122018] dark:text-slate-100 placeholder-[#566b5c]/60 dark:placeholder-slate-500 focus:outline-none focus:ring-2 focus:ring-[#1e4d35] resize-none"
                />
              </div>

              {/* Action Button */}
              <div className="flex items-center justify-between gap-4 pt-3 border-t border-[#1e4d35]/15 dark:border-slate-800">
                <span className="text-[10px] font-mono text-[#566b5c] dark:text-slate-400">
                  {selectedProvider ? '🔒 Privacy Protected Request' : '⚡ Direct Asset Work Order'}
                </span>

                <button
                  type="submit"
                  disabled={saving}
                  className="px-6 py-3 rounded-xl bg-[#1e4d35] hover:bg-[#163a26] text-white font-mono font-bold text-xs transition-all shadow-md flex items-center justify-center gap-2 disabled:opacity-50"
                >
                  <Send className="w-4 h-4" />
                  {saving ? 'Sending...' : selectedProvider ? 'Send Resource Request' : 'Submit Requisition'}
                </button>
              </div>

            </form>
          </div>

          {/* Right Panel: Requisition Quick Selection & Resource Info */}
          <div className="lg:col-span-5 space-y-4">
            <div className="dashboard-card-shape p-5 rounded-2xl">
              <div className="flex items-center justify-between pb-3 mb-3 border-b border-[#1e4d35]/15 dark:border-slate-800">
                <span className="text-xs font-mono font-bold uppercase tracking-wider text-[#1e4d35] dark:text-[#4e9f76] flex items-center gap-2">
                  <PackageCheck className="w-4 h-4" /> Resource Request Guidance
                </span>
              </div>

              <div className="space-y-3 text-xs font-mono text-[#566b5c] dark:text-slate-300 leading-relaxed">
                <div className="p-3 rounded-xl bg-[#f4f6ee] dark:bg-[#0d1b13] border border-[#1e4d35]/20">
                  <strong className="text-[#1e4d35] dark:text-emerald-400 block mb-1">🔒 User-to-User Privacy Protection</strong>
                  <p className="text-[11px] text-[#566b5c] dark:text-slate-400">
                    Requesters cannot view provider internal fleet readiness, aircraft health, risk level, or available counts. Requests are processed purely as resource supply logistics.
                  </p>
                </div>

                <div className="p-3 rounded-xl bg-[#f4f6ee] dark:bg-[#0d1b13] border border-[#1e4d35]/20">
                  <strong className="text-[#1e4d35] dark:text-emerald-400 block mb-1">⚡ Request Lifecycle</strong>
                  <p className="text-[11px] text-[#566b5c] dark:text-slate-400">
                    Submitted requests enter <span className="text-amber-400 font-bold">PENDING</span> status. The provider receives the requisition and can Approve, Reject, or Fulfill it based on operational availability.
                  </p>
                </div>
              </div>
            </div>
          </div>

        </div>

        {/* Section 1: User-to-User Resource Requests Table */}
        <div className="dashboard-card-shape p-6 rounded-2xl space-y-4">
          <div className="flex items-center justify-between border-b border-[#1e4d35]/15 dark:border-slate-800 pb-3 flex-wrap gap-2">
            <div>
              <h3 className="text-sm font-bold font-mono text-[#122018] dark:text-slate-100 uppercase tracking-wider">
                User-to-User Resource Requests ({resourceRequests.length})
              </h3>
              <p className="text-[11px] font-mono text-[#566b5c] dark:text-slate-400 mt-0.5">
                Privacy-protected supply requisitions between requester and provider facilities
              </p>
            </div>
          </div>

          <div className="divide-y divide-[#1e4d35]/10 dark:divide-slate-800">
            {resourceRequests.length === 0 ? (
              <p className="py-6 text-xs font-mono text-[#566b5c] dark:text-slate-500 text-center">
                No active resource requests.
              </p>
            ) : (
              resourceRequests.map((req) => (
                <div key={req.id} className="py-3.5 flex flex-col md:flex-row md:items-center justify-between gap-4 text-xs font-mono">
                  <div className="space-y-1 max-w-xl">
                    <div className="flex items-center gap-2 flex-wrap">
                      <span className="font-bold text-[#122018] dark:text-slate-100 text-sm">{req.resource_name}</span>
                      <span className="px-2 py-0.5 rounded text-[10px] font-bold bg-[#1e4d35]/20 text-[#1e4d35] dark:bg-[#1e4d35]/50 dark:text-emerald-300">
                        {req.quantity}
                      </span>
                      <span className={`px-2 py-0.5 rounded text-[10px] font-bold border ${URGENCY_BADGES[req.priority] || URGENCY_BADGES.SCHEDULED}`}>
                        {req.priority}
                      </span>
                    </div>

                    <p className="text-[11px] text-[#566b5c] dark:text-slate-300">
                      <strong>From:</strong> {req.requester_name} &nbsp;→&nbsp; <strong>To:</strong> {req.provider_facility}
                    </p>

                    <p className="text-[10px] text-[#566b5c] dark:text-slate-400 italic">
                      &quot;{req.reason}&quot;
                    </p>
                  </div>

                  <div className="flex items-center gap-3 shrink-0 flex-wrap">
                    <span className={`px-3 py-1 rounded-full text-xs font-bold border ${STATUS_BADGES[req.status] || STATUS_BADGES.PENDING}`}>
                      {req.status}
                    </span>

                    {/* Provider Actions if User B views or tests provider role */}
                    {req.status === 'PENDING' && (
                      <div className="flex items-center gap-1.5">
                        <button
                          onClick={() => handleStatusUpdate(req.id, 'APPROVED')}
                          className="px-2.5 py-1 rounded bg-emerald-700 hover:bg-emerald-800 text-white text-[10px] font-bold transition-colors"
                        >
                          Approve
                        </button>
                        <button
                          onClick={() => handleStatusUpdate(req.id, 'FULFILLED')}
                          className="px-2.5 py-1 rounded bg-cyan-700 hover:bg-cyan-800 text-white text-[10px] font-bold transition-colors"
                        >
                          Fulfill
                        </button>
                        <button
                          onClick={() => handleStatusUpdate(req.id, 'REJECTED')}
                          className="px-2.5 py-1 rounded bg-red-700 hover:bg-red-800 text-white text-[10px] font-bold transition-colors"
                        >
                          Reject
                        </button>
                      </div>
                    )}
                  </div>
                </div>
              ))
            )}
          </div>
        </div>

        {/* Section 2: Submitted Work Order Requisitions Table */}
        {(() => {
          const safeWorkOrders = Array.isArray(workOrders) ? workOrders : [];
          return (
            <div className="dashboard-card-shape p-6 rounded-2xl space-y-4">
              <div className="flex items-center justify-between border-b border-[#1e4d35]/15 dark:border-slate-800 pb-3">
                <h3 className="text-sm font-bold font-mono text-[#122018] dark:text-slate-100 uppercase tracking-wider">
                  Work Order Requisitions ({safeWorkOrders.length})
                </h3>
              </div>

              <div className="divide-y divide-[#1e4d35]/10 dark:divide-slate-800">
                {safeWorkOrders.length === 0 ? (
                  <p className="py-6 text-xs font-mono text-[#566b5c] dark:text-slate-500 text-center">
                    No active work order requisitions.
                  </p>
                ) : (
                  safeWorkOrders.map((wo) => (
                    <div key={wo.id} className="py-3 flex flex-col sm:flex-row sm:items-center justify-between gap-3 text-xs font-mono">
                      <div>
                        <div className="flex items-center gap-2">
                          <span className="font-bold text-[#122018] dark:text-slate-100">{wo.title}</span>
                          <span className="text-[#566b5c] dark:text-slate-400">[{wo.asset_id || 'Fleet'}]</span>
                        </div>
                        {wo.description && (
                          <p className="text-[11px] font-mono text-[#566b5c] dark:text-slate-400 mt-1">
                            📍 {wo.description}
                          </p>
                        )}
                      </div>

                      <div className="flex items-center gap-3 shrink-0">
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
          );
        })()}

      </div>
    </NavBar>
  );
}
