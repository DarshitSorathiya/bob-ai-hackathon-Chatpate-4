'use client';

import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Navigation, ExternalLink, AlertCircle } from 'lucide-react';
import { listAssets, getAllReadiness } from '../lib/api';

// Realistic Indian Air Force & Defense Airbase Locations Mapping
const INDIAN_AIRBASE_LOCATIONS = {
  // Primary Enrolled Assets
  'TJS-014':    { name: 'HAL Tejas Mk1A',           base: 'HAL Airport Base, Bengaluru, Karnataka, India',          lat: 12.9716, lng: 77.5946 },
  'SU-30-01':   { name: 'Sukhoi Su-30MKI',          base: 'Lohegaon Air Force Base, Pune, Maharashtra, India',      lat: 18.5822, lng: 73.9197 },
  'RAF-01':    { name: 'Dassault Rafale DH',       base: 'Ambala Air Force Station, Punjab, India',                lat: 30.3683, lng: 76.8169 },
  'M2K-01':    { name: 'Mirage 2000-5',            base: 'Maharajpur Airbase, Gwalior, Madhya Pradesh, India',     lat: 26.2933, lng: 78.2278 },
  'MIG-29-02': { name: 'MiG-29UPG Fulcrum',       base: 'Adampur Air Force Base, Jalandhar, Punjab, India',       lat: 31.4333, lng: 75.7583 },
  'LCH-01':    { name: 'HAL Prachand LCH',         base: 'Jodhpur Air Force Base, Rajasthan, India',               lat: 26.2511, lng: 73.0489 },
  'MIG-29K-03':{ name: 'MiG-29K Naval Fighter',   base: 'INS Hansa Naval Air Station, Goa, India',               lat: 15.3808, lng: 73.8314 },
  'C17-01':    { name: 'C-17 Globemaster III',     base: 'Hindon Air Force Station, Ghaziabad, UP, India',        lat: 28.7072, lng: 77.3601 },

  // API Asset Code Mappings
  'AH-64-01':   { name: 'HAL Tejas Mk1A (TJS-014)', base: 'HAL Airport Base, Bengaluru, Karnataka, India',          lat: 12.9716, lng: 77.5946 },
  'F-16-01':    { name: 'Sukhoi Su-30MKI (SU-30)',  base: 'Lohegaon Air Force Base, Pune, Maharashtra, India',      lat: 18.5822, lng: 73.9197 },
  'HMMWV-01':   { name: 'Tata WhAP Recon Vehicle',  base: 'Jaisalmer Defense Outpost, Rajasthan, India',            lat: 26.9157, lng: 70.9083 },
  'C-130-02':   { name: 'C-130J Super Hercules',    base: 'Sulur Air Force Station, Coimbatore, Tamil Nadu, India', lat: 11.0132, lng: 77.1611 },
  'UH-60-03':   { name: 'MH-60R Seahawk Naval',     base: 'INS Garuda Naval Base, Kochi, Kerala, India',            lat: 9.9483,  lng: 76.2731 },
  'CH-47-04':   { name: 'CH-47F Chinook Heavy-Lift',base: 'Chandigarh Air Station, Punjab, India',                 lat: 30.6732, lng: 76.7885 },

  'ast_ah64_01': { name: 'HAL Tejas Mk1A (TJS-014)', base: 'HAL Airport Base, Bengaluru, Karnataka, India',          lat: 12.9716, lng: 77.5946 },
  'ast_f16_01':  { name: 'Sukhoi Su-30MKI (SU-30)',  base: 'Lohegaon Air Force Base, Pune, Maharashtra, India',      lat: 18.5822, lng: 73.9197 },
  'ast_hmmwv_01':{ name: 'Tata WhAP Recon Vehicle',  base: 'Jaisalmer Defense Outpost, Rajasthan, India',            lat: 26.9157, lng: 70.9083 },
  'ast_c130_02': { name: 'C-130J Super Hercules',    base: 'Sulur Air Force Station, Coimbatore, Tamil Nadu, India', lat: 11.0132, lng: 77.1611 },
  'ast_uh60_03': { name: 'MH-60R Seahawk Naval',     base: 'INS Garuda Naval Base, Kochi, Kerala, India',            lat: 9.9483,  lng: 76.2731 },
  'ast_ch47_04': { name: 'CH-47F Chinook Heavy-Lift',base: 'Chandigarh Air Station, Punjab, India',                 lat: 30.6732, lng: 76.7885 },
};

export default function FleetLeafletMap({ assets: initialAssets = [], readinessMap: initialReadinessMap = {} }) {
  const router = useRouter();
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);

  const [userLocation, setUserLocation] = useState(null);
  const [userLocStatus, setUserLocStatus] = useState('Detecting GPS...');
  const [locAvailable, setLocAvailable] = useState(true);
  const [activeFilter, setActiveFilter] = useState('ALL');

  // Backend telemetry state & periodic polling
  const [liveAssets, setLiveAssets] = useState(initialAssets);
  const [liveReadinessMap, setLiveReadinessMap] = useState(initialReadinessMap);

  useEffect(() => {
    if (initialAssets && initialAssets.length > 0) setLiveAssets(initialAssets);
    if (initialReadinessMap && Object.keys(initialReadinessMap).length > 0) setLiveReadinessMap(initialReadinessMap);
  }, [initialAssets, initialReadinessMap]);

  // Periodic 10s backend telemetry fetch
  const fetchTelemetryData = useCallback(async () => {
    try {
      const [assetsData, readinessData] = await Promise.allSettled([
        listAssets({ limit: 100 }),
        getAllReadiness(),
      ]);
      if (assetsData.status === 'fulfilled' && Array.isArray(assetsData.value)) {
        setLiveAssets(assetsData.value);
      }
      if (readinessData.status === 'fulfilled' && Array.isArray(readinessData.value)) {
        const map = {};
        readinessData.value.forEach((r) => { map[r.asset_id] = r; });
        setLiveReadinessMap(map);
      }
    } catch {
      // Keep existing data on transient network errors
    }
  }, []);

  useEffect(() => {
    fetchTelemetryData();
    const interval = setInterval(fetchTelemetryData, 10000);
    return () => clearInterval(interval);
  }, [fetchTelemetryData]);

  // Browser Geolocation API for User Position
  useEffect(() => {
    if (typeof window === 'undefined' || !navigator.geolocation) {
      setLocAvailable(false);
      setUserLocStatus('Location unavailable');
      return;
    }

    let watchId;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setUserLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setUserLocStatus('GPS Active');
        setLocAvailable(true);
      },
      () => {
        setLocAvailable(false);
        setUserLocStatus('Location permission denied');
      },
      { enableHighAccuracy: true, timeout: 8000 }
    );

    watchId = navigator.geolocation.watchPosition(
      (pos) => {
        setUserLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setUserLocStatus('GPS Active');
        setLocAvailable(true);
      },
      () => {},
      { enableHighAccuracy: true, timeout: 10000, maximumAge: 5000 }
    );

    return () => {
      if (watchId !== undefined && navigator.geolocation) {
        navigator.geolocation.clearWatch(watchId);
      }
    };
  }, []);

  // Format Indian fleet asset coordinates
  const fleetLocations = useMemo(() => {
    const list = liveAssets && liveAssets.length > 0 ? liveAssets : [
      { id: 'ast_ah64_01', asset_code: 'TJS-014', call_sign: 'HAL Tejas Mk1A', asset_type: 'FIXED_WING', status: 'READY' },
      { id: 'ast_f16_01', asset_code: 'SU-30-01', call_sign: 'Sukhoi Su-30MKI', asset_type: 'FIXED_WING', status: 'READY' },
      { id: 'ast_hmmwv_01', asset_code: 'LCH-01', call_sign: 'HAL Prachand LCH', asset_type: 'HELICOPTER', status: 'AT_RISK' },
      { id: 'ast_c130_02', asset_code: 'RAF-01', call_sign: 'Rafale DH', asset_type: 'FIXED_WING', status: 'READY' },
      { id: 'ast_uh60_03', asset_code: 'MIG-29-02', call_sign: 'MiG-29UPG', asset_type: 'FIXED_WING', status: 'NOT_READY' },
      { id: 'ast_ch47_04', asset_code: 'C17-01', call_sign: 'C-17 Globemaster', asset_type: 'FIXED_WING', status: 'READY' },
    ];

    return list.map((a, idx) => {
      const rec = liveReadinessMap[a.id] || {};
      const status = rec.status || a.status || 'READY';
      const locSpec = INDIAN_AIRBASE_LOCATIONS[a.asset_code] || INDIAN_AIRBASE_LOCATIONS[a.id] || {
        name: a.call_sign || a.description || a.asset_code || 'Fleet Aircraft',
        base: `Indian Sector Base ${idx + 1}`,
        lat: 20.0 + (idx * 3.2) % 12,
        lng: 73.0 + (idx * 4.1) % 15,
      };

      return {
        ...a,
        status,
        name: locSpec.name,
        baseName: locSpec.base,
        lat: locSpec.lat,
        lng: locSpec.lng,
      };
    });
  }, [liveAssets, liveReadinessMap]);

  const filteredLocations = useMemo(() => {
    if (activeFilter === 'ALL') return fleetLocations;
    return fleetLocations.filter((item) => item.status === activeFilter);
  }, [fleetLocations, activeFilter]);

  // Navigate to Request Component page with asset, location & aircraft params
  const handleRequestClick = useCallback((locItem) => {
    const assetId = locItem.asset_code || locItem.id;
    const locationStr = encodeURIComponent(locItem.baseName || '');
    const aircraftStr = encodeURIComponent(locItem.name || locItem.call_sign || assetId);
    router.push(`/request?asset_id=${encodeURIComponent(assetId)}&location=${locationStr}&aircraft=${aircraftStr}`);
  }, [router]);

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

      // Default center: India (20.5937° N, 78.9629° E)
      const defaultCenter = userLocation ? [userLocation.lat, userLocation.lng] : [21.7679, 78.8718];
      const map = L.map(mapContainerRef.current, {
        center: defaultCenter,
        zoom: 5,
        zoomControl: true,
        attributionControl: false,
      });

      // Free Public OpenStreetMap Standard Tiles (No API key, No billing, No watermark)
      L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        maxZoom: 19,
        subdomains: 'abc',
      }).addTo(map);

      // Render User Current Location Marker
      if (userLocation) {
        const userHtml = `
          <div style="position: relative; display: flex; align-items: center; justify-content: center;">
            <span class="animate-ping" style="position: absolute; width: 22px; height: 22px; border-radius: 9999px; background-color: #38bdf8; opacity: 0.6;"></span>
            <span style="position: relative; width: 12px; height: 12px; border-radius: 9999px; background-color: #38bdf8; border: 2px solid #ffffff; box-shadow: 0 0 10px #38bdf8;"></span>
          </div>
        `;
        const userIcon = L.divIcon({
          html: userHtml,
          className: 'leaflet-user-loc-icon',
          iconSize: [22, 22],
          iconAnchor: [11, 11],
        });

        L.marker([userLocation.lat, userLocation.lng], { icon: userIcon })
          .addTo(map)
          .bindTooltip('<b style="font-family: monospace; font-size: 11px; color: #38bdf8;">📍 Your Current Location</b>', {
            direction: 'top',
            className: 'military-leaflet-tooltip',
          });
      }

      // Render Indian Fleet Markers
      const bounds = L.latLngBounds([]);
      if (userLocation) bounds.extend([userLocation.lat, userLocation.lng]);

      filteredLocations.forEach((loc) => {
        bounds.extend([loc.lat, loc.lng]);

        const colorMap = {
          READY:     '#34d399',
          AT_RISK:   '#fbbf24',
          NOT_READY: '#f87171',
        };
        const dotColor = colorMap[loc.status] || '#34d399';

        const dotHtml = `
          <div style="position: relative; display: flex; align-items: center; justify-content: center; cursor: pointer;">
            <span style="width: 14px; height: 14px; border-radius: 9999px; background-color: ${dotColor}; border: 2px solid #0d1b13; box-shadow: 0 2px 6px ${dotColor}80; transition: transform 0.2s;" onmouseover="this.style.transform='scale(1.4)'" onmouseout="this.style.transform='scale(1)'"></span>
          </div>
        `;

        const markerIcon = L.divIcon({
          html: dotHtml,
          className: 'leaflet-fleet-dot-icon',
          iconSize: [16, 16],
          iconAnchor: [8, 8],
        });

        const tooltipContent = `
          <div style="font-family: ui-sans-serif, system-ui, sans-serif; padding: 4px 6px; min-width: 190px;">
            <div style="display: flex; align-items: center; justify-content: space-between; gap: 8px; margin-bottom: 4px;">
              <strong style="color: #34d399; font-family: monospace; font-size: 12px;">${loc.asset_code || loc.id}</strong>
              <span style="font-size: 9px; font-family: monospace; padding: 1px 6px; border-radius: 9999px; font-weight: bold; background: rgba(30,77,53,0.5); color: ${dotColor}; border: 1px solid ${dotColor}40;">
                ${loc.status}
              </span>
            </div>
            <div style="font-size: 11px; font-weight: 600; color: #f1f5f9;">${loc.name}</div>
            <div style="font-size: 10px; font-family: monospace; color: #78b394; margin-top: 2px;">📍 ${loc.baseName}</div>
            <div style="font-size: 9px; font-family: monospace; color: #94a3b8; margin-top: 6px; border-top: 1px solid rgba(78,159,118,0.25); padding-top: 4px; display: flex; align-items: center; justify-content: space-between;">
              <span>Click to request component</span>
              <span style="color: #34d399;">→</span>
            </div>
          </div>
        `;

        const marker = L.marker([loc.lat, loc.lng], { icon: markerIcon }).addTo(map);
        marker.bindTooltip(tooltipContent, {
          direction: 'top',
          className: 'military-leaflet-tooltip',
          opacity: 0.98,
        });

        marker.on('click', () => {
          handleRequestClick(loc);
        });
      });

      if (filteredLocations.length > 0 && bounds.isValid()) {
        map.fitBounds(bounds, { padding: [40, 40], maxZoom: 7 });
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
  }, [userLocation, filteredLocations, handleRequestClick]);

  return (
    <div className="dashboard-card-shape p-6 flex flex-col justify-between transition-all duration-200">
      
      {/* Header Bar matching Fleet Locations requirement */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4 pb-4 border-b border-[#1e4d35]/20 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <h2 className="text-lg font-bold font-sans text-[#122018] dark:text-slate-100">
              Fleet Locations (India Sector)
            </h2>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-[#e1eadf] text-[#1e4d35] dark:bg-[#1e4d35]/40 dark:text-emerald-300 border border-[#1e4d35]/30">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              Live
            </span>
          </div>
          <div className="flex items-center gap-2">
            <p className="text-xs font-mono text-[#566b5c] dark:text-slate-400">
              Free OpenStreetMap Telemetry • {userLocStatus}
            </p>
            {!locAvailable && (
              <span className="inline-flex items-center gap-1 text-[10px] font-mono text-amber-500/90 bg-amber-500/10 px-2 py-0.5 rounded border border-amber-500/20">
                <AlertCircle className="w-3 h-3" /> Location unavailable
              </span>
            )}
          </div>
        </div>

        {/* Status Filter Buttons */}
        <div className="flex items-center gap-2 font-mono text-xs flex-wrap">
          <button
            onClick={() => setActiveFilter('ALL')}
            className={`px-3 py-1 rounded-full border text-xs transition-colors ${
              activeFilter === 'ALL'
                ? 'bg-[#1e4d35] text-white border-[#1e4d35]'
                : 'bg-[#e1eadf]/60 dark:bg-[#122419] border-[#1e4d35]/20 text-[#122018] dark:text-slate-300 hover:bg-[#e1eadf]'
            }`}
          >
            All ({fleetLocations.length})
          </button>
          <button
            onClick={() => setActiveFilter('READY')}
            className={`px-3 py-1 rounded-full border text-xs transition-colors ${
              activeFilter === 'READY'
                ? 'bg-emerald-600 text-white border-emerald-600'
                : 'bg-[#e1eadf]/60 dark:bg-[#122419] border-[#1e4d35]/20 text-[#122018] dark:text-slate-300 hover:bg-[#e1eadf]'
            }`}
          >
            Ready ({fleetLocations.filter((f) => f.status === 'READY').length})
          </button>
          <button
            onClick={() => setActiveFilter('AT_RISK')}
            className={`px-3 py-1 rounded-full border text-xs transition-colors ${
              activeFilter === 'AT_RISK'
                ? 'bg-amber-600 text-white border-amber-600'
                : 'bg-[#e1eadf]/60 dark:bg-[#122419] border-[#1e4d35]/20 text-[#122018] dark:text-slate-300 hover:bg-[#e1eadf]'
            }`}
          >
            At Risk ({fleetLocations.filter((f) => f.status === 'AT_RISK').length})
          </button>
          <button
            onClick={() => setActiveFilter('NOT_READY')}
            className={`px-3 py-1 rounded-full border text-xs transition-colors ${
              activeFilter === 'NOT_READY'
                ? 'bg-red-600 text-white border-red-600'
                : 'bg-[#e1eadf]/60 dark:bg-[#122419] border-[#1e4d35]/20 text-[#122018] dark:text-slate-300 hover:bg-[#e1eadf]'
            }`}
          >
            Not Ready ({fleetLocations.filter((f) => f.status === 'NOT_READY').length})
          </button>
        </div>
      </div>

      {/* Leaflet OpenStreetMap Container */}
      <div className="relative w-full h-[390px] rounded-xl overflow-hidden border border-[#1e4d35]/25 dark:border-[#4e9f76]/30 bg-[#0d1b13] shadow-inner select-none z-0 dark-aerospace-map">
        <div ref={mapContainerRef} className="w-full h-full z-0" />
      </div>

      {/* Map Legend */}
      <div className="mt-3 flex items-center justify-between text-[10px] font-mono text-[#566b5c] dark:text-slate-400 bg-[#050811]/40 px-4 py-2 rounded-lg border border-[#1e4d35]/20">
        <span className="flex items-center gap-3">
          <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-cyan-400" /> Current Location</span>
          <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-[#34d399]" /> Ready</span>
          <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-amber-400" /> At Risk</span>
          <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-red-400" /> Not Ready</span>
        </span>
        <span className="text-[#4e9f76] font-semibold">Hover to view details • Click to request</span>
      </div>

    </div>
  );
}
