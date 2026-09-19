'use client';

import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { Send, X, CheckCircle2 } from 'lucide-react';
import { createResourceRequest } from '../lib/api';

// Simplified Indian Defense & Sector Stations Mapping
const STATIONS_DATA = [
  {
    id: 'stn_bengaluru',
    name: 'Bengaluru Station',
    location: 'HAL Airport Station, Bengaluru, Karnataka',
    isUserStation: true, // Current User's Station
    lat: 12.9716,
    lng: 77.5946,
  },
  {
    id: 'stn_pune',
    name: 'Pune Station',
    location: 'Lohegaon Station, Pune, Maharashtra',
    isUserStation: false,
    lat: 18.5822,
    lng: 73.9197,
  },
  {
    id: 'stn_ambala',
    name: 'Ambala Station',
    location: 'Ambala Station, Punjab',
    isUserStation: false,
    lat: 30.3683,
    lng: 76.8169,
  },
  {
    id: 'stn_gwalior',
    name: 'Gwalior Station',
    location: 'Maharajpur Station, Gwalior, Madhya Pradesh',
    isUserStation: false,
    lat: 26.2933,
    lng: 78.2278,
  },
  {
    id: 'stn_jodhpur',
    name: 'Jodhpur Station',
    location: 'Jodhpur Station, Rajasthan',
    isUserStation: false,
    lat: 26.2511,
    lng: 73.0489,
  },
  {
    id: 'stn_goa',
    name: 'Goa Station',
    location: 'INS Hansa Station, Goa',
    isUserStation: false,
    lat: 15.3808,
    lng: 73.8314,
  },
  {
    id: 'stn_hindon',
    name: 'Hindon Station',
    location: 'Hindon Station, Ghaziabad, Uttar Pradesh',
    isUserStation: false,
    lat: 28.7072,
    lng: 77.3601,
  },
  {
    id: 'stn_sulur',
    name: 'Sulur Station',
    location: 'Sulur Station, Coimbatore, Tamil Nadu',
    isUserStation: false,
    lat: 11.0132,
    lng: 77.1611,
  },
];

export default function FleetLeafletMap() {
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);

  // Selected Neighbouring Station for Modal Request
  const [selectedStation, setSelectedStation] = useState(null);
  const [modalOpen, setModalOpen] = useState(false);
  const [sending, setSaving] = useState(false);
  const [successMsg, setSuccessMsg] = useState('');

  // Resource Request Modal Form State
  const [requestForm, setRequestForm] = useState({
    resource_name: 'Hydraulic Fluid (MIL-PRF-83282)',
    quantity: '20 units',
    priority: 'High',
    reason: '',
  });

  const handleOpenRequestModal = useCallback((station) => {
    if (station.isUserStation) return;
    setSelectedStation(station);
    setRequestForm({
      resource_name: 'Hydraulic Fluid (MIL-PRF-83282)',
      quantity: '20 units',
      priority: 'High',
      reason: `Resource requirement for Bengaluru Station from ${station.name}`,
    });
    setSuccessMsg('');
    setModalOpen(true);
  }, []);

  const handleSendRequest = async (e) => {
    e.preventDefault();
    if (!selectedStation) return;
    setSaving(true);

    try {
      createResourceRequest({
        requester_id: 'usr_current_operator',
        requester_name: 'Bengaluru Station Operator',
        requester_location: 'HAL Airport Station, Bengaluru, Karnataka',
        provider_id: selectedStation.id,
        provider_facility: selectedStation.location,
        resource_name: requestForm.resource_name,
        quantity: requestForm.quantity,
        priority: requestForm.priority.toUpperCase(),
        reason: requestForm.reason || `Resource request to ${selectedStation.name}`,
      });

      setSuccessMsg(`Resource request sent to ${selectedStation.name}.`);
      setTimeout(() => {
        setModalOpen(false);
        setSaving(false);
        setSuccessMsg('');
      }, 1500);
    } catch {
      setSaving(false);
    }
  };

  // Initialize Leaflet Map Instance Client-side
  useEffect(() => {
    let isMounted = true;

    async function initMap() {
      if (typeof window === 'undefined' || !mapContainerRef.current) return;

      const L = (await import('leaflet')).default;
      if (!isMounted || !mapContainerRef.current) return;

      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }

      // Default center: India (21.7679° N, 78.8718° E)
      const map = L.map(mapContainerRef.current, {
        center: [21.7679, 78.8718],
        zoom: 5,
        zoomControl: true,
        attributionControl: false,
      });

      // Free Public OpenStreetMap Standard Tiles
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        subdomains: 'abc',
      }).addTo(map);

      const bounds = L.latLngBounds([]);

      STATIONS_DATA.forEach((station) => {
        bounds.extend([station.lat, station.lng]);

        // Station Markers: Blue for Current User's Station, Green for Neighbouring Stations
        const isUser = station.isUserStation;
        const color = isUser ? '#38bdf8' : '#34d399'; // Blue vs Green

        const markerHtml = isUser
          ? `
            <div style="position: relative; display: flex; align-items: center; justify-content: center; cursor: pointer;">
              <span class="animate-ping" style="position: absolute; width: 20px; height: 20px; border-radius: 9999px; background-color: #38bdf8; opacity: 0.6;"></span>
              <span style="position: relative; width: 14px; height: 14px; border-radius: 9999px; background-color: #38bdf8; border: 2px solid #ffffff; box-shadow: 0 0 10px #38bdf8;"></span>
            </div>
          `
          : `
            <div style="position: relative; display: flex; align-items: center; justify-content: center; cursor: pointer;">
              <span style="width: 14px; height: 14px; border-radius: 9999px; background-color: #34d399; border: 2px solid #0d1b13; box-shadow: 0 2px 6px rgba(52,211,153,0.5); transition: transform 0.2s;" onmouseover="this.style.transform='scale(1.35)'" onmouseout="this.style.transform='scale(1)'"></span>
            </div>
          `;

        const markerIcon = L.divIcon({
          html: markerHtml,
          className: isUser ? 'leaflet-user-loc-icon' : 'leaflet-fleet-dot-icon',
          iconSize: [18, 18],
          iconAnchor: [9, 9],
        });

        const tooltipContent = isUser
          ? `
            <div style="font-family: ui-sans-serif, system-ui, sans-serif; padding: 4px 6px;">
              <strong style="color: #38bdf8; font-family: monospace; font-size: 12px;">📍 Your Station</strong>
              <div style="font-size: 11px; color: #f1f5f9; font-weight: 600; margin-top: 2px;">${station.name}</div>
              <div style="font-size: 10px; font-family: monospace; color: #94a3b8;">${station.location}</div>
            </div>
          `
          : `
            <div style="font-family: ui-sans-serif, system-ui, sans-serif; padding: 4px 6px;">
              <strong style="color: #34d399; font-size: 12px;">${station.name}</strong>
              <div style="font-size: 10px; font-family: monospace; color: #78b394; margin-top: 2px;">${station.location}</div>
              <div style="font-size: 10px; font-family: monospace; color: #38bdf8; margin-top: 4px; font-weight: 600;">
                Click to Request Resources →
              </div>
            </div>
          `;

        const marker = L.marker([station.lat, station.lng], { icon: markerIcon }).addTo(map);
        marker.bindTooltip(tooltipContent, {
          direction: 'top',
          className: 'military-leaflet-tooltip',
          opacity: 0.98,
        });

        if (!isUser) {
          marker.on('click', () => handleOpenRequestModal(station));
        }
      });

      if (bounds.isValid()) {
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 6 });
      }

      mapInstanceRef.current = map;
    }

    initMap();

    return () => {
      isMounted = false;
      if (mapInstanceRef.current) {
        mapInstanceRef.current.remove();
        mapInstanceRef.current = null;
      }
    };
  }, [handleOpenRequestModal]);

  return (
    <div className="dashboard-card-shape p-6 flex flex-col justify-between transition-all duration-200 relative">
      
      {/* 1. Simple Clean Header */}
      <div className="flex items-center justify-between gap-4 mb-4 pb-4 border-b border-[#1e4d35]/20 dark:border-slate-800">
        <div>
          <h2 className="text-lg font-bold font-sans text-[#122018] dark:text-slate-100">
            Nearby Stations
          </h2>
          <p className="text-xs font-mono text-[#566b5c] dark:text-slate-400 mt-0.5">
            View neighbouring stations and request resources
          </p>
        </div>
      </div>

      {/* 2. Map Container */}
      <div className="relative w-full h-[390px] rounded-xl overflow-hidden border border-[#1e4d35]/25 dark:border-[#4e9f76]/30 bg-[#0d1b13] shadow-inner select-none z-0 dark-aerospace-map">
        <div ref={mapContainerRef} className="w-full h-full z-0" />
      </div>

      {/* 3. Simplified 2-Item Legend */}
      <div className="mt-3 flex items-center justify-between text-xs font-mono text-[#566b5c] dark:text-slate-300 bg-[#050811]/40 px-4 py-2 rounded-lg border border-[#1e4d35]/20">
        <div className="flex items-center gap-6">
          <span className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-[#38bdf8] border border-white shadow-sm" />
            <strong className="text-[#38bdf8]">Your Station</strong>
          </span>
          <span className="flex items-center gap-2">
            <span className="w-3 h-3 rounded-full bg-[#34d399] border border-[#0d1b13] shadow-sm" />
            <strong className="text-[#34d399]">Neighbouring Station</strong>
          </span>
        </div>
        <span className="text-[11px] text-[#4e9f76]">
          Click any neighbouring station to request resources
        </span>
      </div>

      {/* 4. Simple Resource Request Modal */}
      {modalOpen && selectedStation && (
        <div className="fixed inset-0 z-50 bg-black/70 backdrop-blur-sm flex items-center justify-center p-4 animate-in fade-in duration-200">
          <div className="bg-[#122419] border border-[#4e9f76]/40 rounded-2xl p-6 max-w-md w-full text-slate-100 shadow-2xl relative space-y-4">
            
            {/* Modal Header */}
            <div className="flex items-center justify-between border-b border-[#1e4d35]/40 pb-3">
              <div>
                <h3 className="text-base font-bold font-sans text-slate-100">
                  Request Resources
                </h3>
                <p className="text-xs font-mono text-emerald-400 mt-0.5">
                  To: {selectedStation.name} ({selectedStation.location.split(',')[0]})
                </p>
              </div>
              <button
                onClick={() => setModalOpen(false)}
                className="p-1 rounded-lg text-slate-400 hover:text-white hover:bg-[#1e4d35]/40 transition-colors"
              >
                <X className="w-5 h-5" />
              </button>
            </div>

            {successMsg ? (
              <div className="py-6 text-center space-y-2 font-mono">
                <CheckCircle2 className="w-10 h-10 text-emerald-400 mx-auto animate-bounce" />
                <p className="text-sm font-bold text-emerald-300">{successMsg}</p>
                <p className="text-xs text-slate-400">Request successfully dispatched to {selectedStation.name}.</p>
              </div>
            ) : (
              <form onSubmit={handleSendRequest} className="space-y-4 font-mono text-xs">
                
                {/* Resource Selection */}
                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-300 mb-1">
                    Resource
                  </label>
                  <select
                    required
                    value={requestForm.resource_name}
                    onChange={(e) => setRequestForm({ ...requestForm, resource_name: e.target.value })}
                    className="w-full px-3 py-2 bg-[#0d1b13] border border-[#4e9f76]/30 rounded-xl text-slate-100 focus:outline-none focus:ring-1 focus:ring-emerald-400"
                  >
                    <option value="Hydraulic Fluid (MIL-PRF-83282)">Hydraulic Fluid (MIL-PRF-83282)</option>
                    <option value="Avionics Radar Sensor Module">Avionics Radar Sensor Module</option>
                    <option value="Spare Turboprop Rotor Seals">Spare Turboprop Rotor Seals</option>
                    <option value="Aviation Jet Fuel (JP-8)">Aviation Jet Fuel (JP-8)</option>
                    <option value="Tactical Ground Support Equipment">Tactical Ground Support Equipment</option>
                  </select>
                </div>

                {/* Quantity */}
                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-300 mb-1">
                    Quantity
                  </label>
                  <input
                    required
                    type="text"
                    value={requestForm.quantity}
                    onChange={(e) => setRequestForm({ ...requestForm, quantity: e.target.value })}
                    placeholder="e.g., 20 units"
                    className="w-full px-3 py-2 bg-[#0d1b13] border border-[#4e9f76]/30 rounded-xl text-slate-100 focus:outline-none focus:ring-1 focus:ring-emerald-400"
                  />
                </div>

                {/* Priority */}
                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-300 mb-1">
                    Priority
                  </label>
                  <select
                    value={requestForm.priority}
                    onChange={(e) => setRequestForm({ ...requestForm, priority: e.target.value })}
                    className="w-full px-3 py-2 bg-[#0d1b13] border border-[#4e9f76]/30 rounded-xl text-slate-100 focus:outline-none focus:ring-1 focus:ring-emerald-400"
                  >
                    <option value="High">High Priority</option>
                    <option value="Medium">Medium Priority</option>
                    <option value="Low">Low Priority</option>
                  </select>
                </div>

                {/* Reason / Description */}
                <div>
                  <label className="block text-[11px] font-bold uppercase tracking-wider text-slate-300 mb-1">
                    Reason
                  </label>
                  <textarea
                    rows={2}
                    value={requestForm.reason}
                    onChange={(e) => setRequestForm({ ...requestForm, reason: e.target.value })}
                    placeholder="Optional description or operational notes..."
                    className="w-full px-3 py-2 bg-[#0d1b13] border border-[#4e9f76]/30 rounded-xl text-slate-100 focus:outline-none focus:ring-1 focus:ring-emerald-400 resize-none"
                  />
                </div>

                {/* Modal Buttons */}
                <div className="flex items-center justify-end gap-3 pt-2 border-t border-[#1e4d35]/40">
                  <button
                    type="button"
                    onClick={() => setModalOpen(false)}
                    className="px-4 py-2 rounded-xl bg-slate-800 hover:bg-slate-700 text-slate-300 font-bold transition-colors"
                  >
                    Cancel
                  </button>
                  <button
                    type="submit"
                    disabled={sending}
                    className="px-5 py-2 rounded-xl bg-[#1e4d35] hover:bg-[#163a26] text-white font-bold transition-colors flex items-center gap-1.5 shadow-md disabled:opacity-50"
                  >
                    <Send className="w-3.5 h-3.5" />
                    {sending ? 'Sending...' : 'Send Request'}
                  </button>
                </div>

              </form>
            )}

          </div>
        </div>
      )}

    </div>
  );
}
