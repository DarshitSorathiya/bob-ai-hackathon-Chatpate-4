'use client';

import React, { useState, useEffect, useRef, useMemo, useCallback } from 'react';
import { useRouter } from 'next/navigation';
import { Navigation, ExternalLink, ShieldAlert, CheckCircle2, Wrench, RefreshCw } from 'lucide-react';
import { listAssets, getAllReadiness } from '../lib/api';

const GOOGLE_MAPS_API_KEY = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY || '';

// Dark Graphite + Muted Military Green Aerospace Palette for Google Maps
const AEROSPACE_DARK_MAP_STYLES = [
  { elementType: 'geometry', stylers: [{ color: '#0d1b13' }] },
  { elementType: 'labels.text.stroke', stylers: [{ color: '#0d1b13' }] },
  { elementType: 'labels.text.fill', stylers: [{ color: '#4e9f76' }] },
  {
    featureType: 'administrative.locality',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#34d399' }],
  },
  {
    featureType: 'poi',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#4e9f76' }],
  },
  {
    featureType: 'poi.park',
    elementType: 'geometry',
    stylers: [{ color: '#122419' }],
  },
  {
    featureType: 'road',
    elementType: 'geometry',
    stylers: [{ color: '#122419' }],
  },
  {
    featureType: 'road',
    elementType: 'geometry.stroke',
    stylers: [{ color: '#1e4d35' }],
  },
  {
    featureType: 'road.highway',
    elementType: 'geometry',
    stylers: [{ color: '#1e4d35' }],
  },
  {
    featureType: 'water',
    elementType: 'geometry',
    stylers: [{ color: '#050811' }],
  },
  {
    featureType: 'water',
    elementType: 'labels.text.fill',
    stylers: [{ color: '#2d6a4f' }],
  },
];

// Base location coordinates mapping for enrolled fleet assets
const KNOWN_LOCATIONS = {
  'AH-64-01':    { base: 'Fort Campbell Airbase',      lat: 36.6575, lng: -87.4975, comp: 'Main Rotor: Ready • HUMS: Normal' },
  'F-16-01':     { base: 'Luke Air Force Base',        lat: 33.5350, lng: -112.3830, comp: 'Avionics Radar: Operational • Spares: Available' },
  'HMMWV-01':    { base: 'Fort Irwin Training Center',  lat: 35.2625, lng: -116.6858, comp: 'Coolant Pump: Degraded • Spares: Requested' },
  'C-130-02':    { base: 'Little Rock Air Force Base', lat: 34.9167, lng: -92.1497, comp: 'Turboprop Engine: Ready • Cargo Systems: Nominal' },
  'UH-60-03':    { base: 'Nellis Air Force Base',      lat: 36.2361, lng: -115.0342, comp: 'Rotor Assembly: Unserviceable • Work Order Open' },
  'CH-47-04':    { base: 'Joint Base Lewis-McChord',   lat: 47.1378, lng: -122.5814, comp: 'Tandem Rotor: Operational • Hydraulics: 100%' },
  'ast_ah64_01': { base: 'Fort Campbell Airbase',      lat: 36.6575, lng: -87.4975, comp: 'Main Rotor: Ready • HUMS: Normal' },
  'ast_f16_01':  { base: 'Luke Air Force Base',        lat: 33.5350, lng: -112.3830, comp: 'Avionics Radar: Operational • Spares: Available' },
  'ast_hmmwv_01':{ base: 'Fort Irwin Training Center', lat: 35.2625, lng: -116.6858, comp: 'Coolant Pump: Degraded • Spares: Requested' },
  'ast_c130_02': { base: 'Little Rock Air Force Base', lat: 34.9167, lng: -92.1497, comp: 'Turboprop Engine: Ready • Cargo Systems: Nominal' },
  'ast_uh60_03': { base: 'Nellis Air Force Base',      lat: 36.2361, lng: -115.0342, comp: 'Rotor Assembly: Unserviceable • Work Order Open' },
  'ast_ch47_04': { base: 'Joint Base Lewis-McChord',   lat: 47.1378, lng: -122.5814, comp: 'Tandem Rotor: Operational • Hydraulics: 100%' },
};

export default function FleetGoogleMap({ assets: initialAssets = [], readinessMap: initialReadinessMap = {} }) {
  const router = useRouter();
  const mapContainerRef = useRef(null);
  const mapInstanceRef = useRef(null);
  const markersRef = useRef([]);
  const userMarkerRef = useRef(null);

  const [userLocation, setUserLocation] = useState(null);
  const [userLocStatus, setUserLocStatus] = useState('Detecting GPS...');
  const [hoveredAsset, setHoveredAsset] = useState(null);
  const [mapLoaded, setMapLoaded] = useState(false);
  const [activeFilter, setActiveFilter] = useState('ALL');

  // Live polling state for backend telemetry
  const [liveAssets, setLiveAssets] = useState(initialAssets);
  const [liveReadinessMap, setLiveReadinessMap] = useState(initialReadinessMap);

  // Sync initial props
  useEffect(() => {
    if (initialAssets && initialAssets.length > 0) setLiveAssets(initialAssets);
    if (initialReadinessMap && Object.keys(initialReadinessMap).length > 0) setLiveReadinessMap(initialReadinessMap);
  }, [initialAssets, initialReadinessMap]);

  // Periodic 10s telemetry data fetch from backend
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
      // Keep existing state on transient network issues
    }
  }, []);

  useEffect(() => {
    fetchTelemetryData();
    const interval = setInterval(fetchTelemetryData, 10000);
    return () => clearInterval(interval);
  }, [fetchTelemetryData]);

  // Real-time user current location tracking via Geolocation API
  useEffect(() => {
    if (typeof window === 'undefined' || !navigator.geolocation) {
      setUserLocation({ lat: 37.0902, lng: -95.7129 });
      setUserLocStatus('Default Center (US)');
      return;
    }

    let watchId;
    navigator.geolocation.getCurrentPosition(
      (pos) => {
        setUserLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setUserLocStatus('GPS Active');
      },
      () => {
        setUserLocation({ lat: 37.0902, lng: -95.7129 });
        setUserLocStatus('Default Base (US)');
      },
      { enableHighAccuracy: true, timeout: 8000 }
    );

    watchId = navigator.geolocation.watchPosition(
      (pos) => {
        setUserLocation({ lat: pos.coords.latitude, lng: pos.coords.longitude });
        setUserLocStatus('GPS Active');
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

  // Compute normalized fleet location items
  const fleetLocations = useMemo(() => {
    const list = liveAssets && liveAssets.length > 0 ? liveAssets : [
      { id: 'ast_ah64_01', asset_code: 'AH-64-01', call_sign: 'Ghost 1', asset_type: 'HELICOPTER', status: 'READY' },
      { id: 'ast_f16_01', asset_code: 'F-16-01', call_sign: 'Viper Lead', asset_type: 'FIXED_WING', status: 'READY' },
      { id: 'ast_hmmwv_01', asset_code: 'HMMWV-01', call_sign: 'Bravo 1', asset_type: 'GROUND_VEHICLE', status: 'AT_RISK' },
      { id: 'ast_c130_02', asset_code: 'C-130-02', call_sign: 'Hercules 2', asset_type: 'FIXED_WING', status: 'READY' },
      { id: 'ast_uh60_03', asset_code: 'UH-60-03', call_sign: 'Blackhawk 3', asset_type: 'HELICOPTER', status: 'NOT_READY' },
      { id: 'ast_ch47_04', asset_code: 'CH-47-04', call_sign: 'Chinook 4', asset_type: 'HELICOPTER', status: 'READY' },
    ];

    return list.map((a, idx) => {
      const rec = liveReadinessMap[a.id] || {};
      const status = rec.status || a.status || 'READY';
      const locSpec = KNOWN_LOCATIONS[a.asset_code] || KNOWN_LOCATIONS[a.id] || {
        base: `Forward Base ${idx + 1}`,
        lat: 34.0 + (idx * 2.5) % 12,
        lng: -115.0 + (idx * 5.5) % 30,
        comp: 'Primary Systems: Operational • Spares: Ready',
      };

      return {
        ...a,
        status,
        baseName: locSpec.base,
        lat: locSpec.lat,
        lng: locSpec.lng,
        componentAvailability: locSpec.comp,
      };
    });
  }, [liveAssets, liveReadinessMap]);

  const filteredLocations = useMemo(() => {
    if (activeFilter === 'ALL') return fleetLocations;
    return fleetLocations.filter((item) => item.status === activeFilter);
  }, [fleetLocations, activeFilter]);

  // Handle click navigation to Request page with pre-selected asset & location
  const handleRequestClick = useCallback((locItem) => {
    const assetId = locItem.id || locItem.asset_code;
    const locationStr = encodeURIComponent(locItem.baseName || '');
    router.push(`/request?asset_id=${encodeURIComponent(assetId)}&location=${locationStr}`);
  }, [router]);

  // Load Google Maps JavaScript API script
  useEffect(() => {
    if (!GOOGLE_MAPS_API_KEY || typeof window === 'undefined') return;

    if (window.google?.maps) {
      setMapLoaded(true);
      return;
    }

    const scriptId = 'google-maps-js-api';
    if (!document.getElementById(scriptId)) {
      const script = document.createElement('script');
      script.id = scriptId;
      script.src = `https://maps.googleapis.com/maps/api/js?key=${GOOGLE_MAPS_API_KEY}&libraries=geometry&callback=initFleetMap`;
      script.async = true;
      script.defer = true;
      window.initFleetMap = () => setMapLoaded(true);
      document.head.appendChild(script);
    }
  }, []);

  // Initialize Native Google Maps instance
  useEffect(() => {
    if (!mapLoaded || !mapContainerRef.current || !window.google?.maps) return;

    if (!mapInstanceRef.current) {
      const defaultCenter = userLocation || { lat: 37.0902, lng: -95.7129 };
      const map = new window.google.maps.Map(mapContainerRef.current, {
        center: defaultCenter,
        zoom: 4,
        styles: AEROSPACE_DARK_MAP_STYLES,
        disableDefaultUI: true,
        zoomControl: true,
        mapTypeControl: false,
        streetViewControl: false,
      });
      mapInstanceRef.current = map;
    }

    const map = mapInstanceRef.current;

    // Clear previous markers
    markersRef.current.forEach((m) => m.setMap(null));
    markersRef.current = [];

    // Render User Current Location Marker
    if (userLocation) {
      if (userMarkerRef.current) userMarkerRef.current.setMap(null);
      userMarkerRef.current = new window.google.maps.Marker({
        position: userLocation,
        map,
        title: 'Current User Location',
        icon: {
          path: window.google.maps.SymbolPath.CIRCLE,
          scale: 7,
          fillColor: '#38bdf8',
          fillOpacity: 1,
          strokeColor: '#ffffff',
          strokeWeight: 2,
        },
      });
    }

    // Render Fleet Dots
    const colorMap = { READY: '#34d399', AT_RISK: '#fbbf24', NOT_READY: '#f87171' };
    const bounds = new window.google.maps.LatLngBounds();
    if (userLocation) bounds.extend(userLocation);

    filteredLocations.forEach((loc) => {
      const pos = { lat: loc.lat, lng: loc.lng };
      bounds.extend(pos);

      const marker = new window.google.maps.Marker({
        position: pos,
        map,
        title: `${loc.asset_code} — ${loc.baseName}`,
        icon: {
          path: window.google.maps.SymbolPath.CIRCLE,
          scale: 5,
          fillColor: colorMap[loc.status] || '#34d399',
          fillOpacity: 0.9,
          strokeColor: '#0d1b13',
          strokeWeight: 1.5,
        },
      });

      marker.addListener('mouseover', () => setHoveredAsset(loc));
      marker.addListener('click', () => handleRequestClick(loc));

      markersRef.current.push(marker);
    });

    if (filteredLocations.length > 1 && !mapInstanceRef.current.hasFitted) {
      map.fitBounds(bounds, 60);
      mapInstanceRef.current.hasFitted = true;
    }
  }, [mapLoaded, userLocation, filteredLocations, handleRequestClick]);

  return (
    <div className="dashboard-card-shape p-6 flex flex-col justify-between transition-all duration-200">
      
      {/* Header Bar with Fleet Locations title and Live status badge */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4 pb-4 border-b border-[#1e4d35]/20 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2.5 mb-1">
            <h2 className="text-lg font-bold font-sans text-[#122018] dark:text-slate-100">
              Fleet Locations
            </h2>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-[#e1eadf] text-[#1e4d35] dark:bg-[#1e4d35]/40 dark:text-emerald-300 border border-[#1e4d35]/30">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              Live
            </span>
          </div>
          <p className="text-xs font-mono text-[#566b5c] dark:text-slate-400">
            Geospatial positioning & status telemetry • {userLocStatus}
          </p>
        </div>

        {/* Status Filter Badges */}
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

      {/* Main Map Viewport */}
      <div className="relative w-full h-[390px] rounded-xl overflow-hidden border border-[#1e4d35]/25 dark:border-[#4e9f76]/30 bg-[#0d1b13] shadow-inner select-none">
        
        {/* Real Google Maps Container */}
        <div ref={mapContainerRef} className="w-full h-full" />

        {/* Interactive Aerospace Vector Map Fallback when Google API key is missing or script loading */}
        {(!GOOGLE_MAPS_API_KEY || !mapLoaded) && (
          <div className="absolute inset-0 bg-[#0d1b13] bg-[radial-gradient(#1e4d35_1px,transparent_1px)] [background-size:24px_24px] flex flex-col justify-between p-6">
            
            {/* Tactical Grid Background */}
            <div className="absolute inset-0 pointer-events-none opacity-20">
              <div className="absolute top-1/2 left-0 right-0 h-[1px] bg-[#4e9f76]" />
              <div className="absolute left-1/2 top-0 bottom-0 w-[1px] bg-[#4e9f76]" />
            </div>

            {/* Sector Header Tag */}
            <div className="relative z-10 flex items-center justify-between text-[11px] font-mono text-[#4e9f76] tracking-wider pointer-events-none">
              <span className="flex items-center gap-1.5 bg-[#050811]/80 px-3 py-1 rounded-md border border-[#1e4d35]/40 backdrop-blur-md">
                <Navigation className="w-3.5 h-3.5 text-cyan-400 animate-spin" />
                AEROSPACE GEOSPATIAL MAP
              </span>
              <span className="bg-[#050811]/80 px-3 py-1 rounded-md border border-[#1e4d35]/40 backdrop-blur-md">
                LAT {userLocation ? userLocation.lat.toFixed(4) : '37.0902'}° N / LON {userLocation ? Math.abs(userLocation.lng).toFixed(4) : '95.7129'}° W
              </span>
            </div>

            {/* Tactical Fleet Dots Overlay */}
            <div className="relative z-10 w-full h-full">
              
              {/* User Current Location Marker */}
              {userLocation && (
                <div
                  className="absolute transform -translate-x-1/2 -translate-y-1/2 flex flex-col items-center group cursor-pointer"
                  style={{ top: '54%', left: '40%' }}
                >
                  <div className="relative flex items-center justify-center">
                    <span className="animate-ping absolute inline-flex h-7 w-7 rounded-full bg-cyan-400 opacity-60" />
                    <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-cyan-400 border-2 border-white shadow-lg shadow-cyan-400/50" />
                  </div>
                  <span className="mt-1 px-2 py-0.5 rounded text-[9px] font-mono font-bold bg-[#050811]/90 text-cyan-300 border border-cyan-400/40 backdrop-blur-md shadow-md">
                    CURRENT LOCATION
                  </span>
                </div>
              )}

              {/* Fleet Minimal Dots */}
              {filteredLocations.map((loc, idx) => {
                const topPos = `${22 + ((idx * 15) % 55)}%`;
                const leftPos = `${18 + ((idx * 22) % 68)}%`;

                const dotColorMap = {
                  READY:     'bg-[#34d399] shadow-[#34d399]/60',
                  AT_RISK:   'bg-amber-400 shadow-amber-400/60',
                  NOT_READY: 'bg-red-400 shadow-red-400/60',
                };
                const dotColor = dotColorMap[loc.status] || dotColorMap.READY;

                return (
                  <div
                    key={loc.id || idx}
                    className="absolute transform -translate-x-1/2 -translate-y-1/2 group cursor-pointer"
                    style={{ top: topPos, left: leftPos }}
                    onMouseEnter={() => setHoveredAsset(loc)}
                    onMouseLeave={() => setHoveredAsset((prev) => (prev?.id === loc.id ? null : prev))}
                    onClick={() => handleRequestClick(loc)}
                  >
                    {/* Minimal Dot */}
                    <div className="relative flex items-center justify-center p-2">
                      <span className={`w-3 h-3 rounded-full ${dotColor} shadow-md transition-all duration-200 group-hover:scale-150 group-hover:ring-4 group-hover:ring-[#4e9f76]/40`} />
                    </div>

                    {/* Tooltip Card on Hover */}
                    <div className="absolute left-1/2 -translate-x-1/2 bottom-full mb-2 hidden group-hover:flex flex-col w-60 p-3.5 rounded-xl bg-[#0a150f]/95 border border-[#4e9f76]/60 text-slate-100 shadow-2xl backdrop-blur-md z-30 pointer-events-auto">
                      <div className="flex items-center justify-between gap-2 border-b border-[#1e4d35]/40 pb-1.5 mb-1.5">
                        <span className="font-mono font-bold text-xs text-emerald-400">
                          {loc.asset_code}
                        </span>
                        <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border font-bold ${
                          loc.status === 'READY' ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30' :
                          loc.status === 'AT_RISK' ? 'bg-amber-500/20 text-amber-300 border-amber-500/30' :
                          'bg-red-500/20 text-red-300 border-red-500/30'
                        }`}>
                          {loc.status}
                        </span>
                      </div>

                      <p className="text-[11px] font-sans font-semibold text-slate-200">{loc.call_sign || loc.asset_type}</p>
                      <p className="text-[10px] font-mono text-[#566b5c] dark:text-slate-400 mt-0.5">📍 {loc.baseName}</p>
                      <p className="text-[9px] font-mono text-emerald-300/90 mt-1">⚡ {loc.componentAvailability}</p>

                      <button
                        onClick={(e) => {
                          e.stopPropagation();
                          handleRequestClick(loc);
                        }}
                        className="mt-2.5 w-full py-1.5 rounded-lg bg-[#1e4d35] hover:bg-[#163a26] text-white font-mono text-[11px] font-bold transition-all flex items-center justify-center gap-1 shadow-sm"
                      >
                        Request Component <ExternalLink className="w-3 h-3" />
                      </button>
                    </div>
                  </div>
                );
              })}

            </div>

            {/* Bottom Legend Bar */}
            <div className="relative z-10 flex items-center justify-between text-[10px] font-mono text-[#566b5c] dark:text-slate-400 bg-[#050811]/80 px-4 py-2 rounded-lg border border-[#1e4d35]/30 backdrop-blur-md">
              <span className="flex items-center gap-3">
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-cyan-400" /> Current Location</span>
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-[#34d399]" /> Ready Location</span>
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-amber-400" /> At Risk</span>
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-red-400" /> Not Ready</span>
              </span>
              <span className="text-[#4e9f76] font-semibold">Hover to view details • Click to request</span>
            </div>

          </div>
        )}

        {/* Floating Active Hover Tooltip Card when Google Maps is active */}
        {GOOGLE_MAPS_API_KEY && mapLoaded && hoveredAsset && (
          <div className="absolute top-4 right-4 z-20 flex flex-col w-64 p-4 rounded-xl bg-[#0a150f]/95 border border-[#4e9f76]/60 text-slate-100 shadow-2xl backdrop-blur-md transition-all animate-in fade-in zoom-in-95">
            <div className="flex items-center justify-between gap-2 border-b border-[#1e4d35]/40 pb-2 mb-2">
              <span className="font-mono font-bold text-sm text-emerald-400">
                {hoveredAsset.asset_code}
              </span>
              <span className={`text-[10px] font-mono px-2 py-0.5 rounded-full border font-bold ${
                hoveredAsset.status === 'READY' ? 'bg-emerald-500/20 text-emerald-300 border-emerald-500/30' :
                hoveredAsset.status === 'AT_RISK' ? 'bg-amber-500/20 text-amber-300 border-amber-500/30' :
                'bg-red-500/20 text-red-300 border-red-500/30'
              }`}>
                {hoveredAsset.status}
              </span>
            </div>
            <p className="text-xs font-sans font-semibold text-slate-200">{hoveredAsset.call_sign || hoveredAsset.asset_type}</p>
            <p className="text-xs font-mono text-[#566b5c] dark:text-slate-400 mt-1">📍 {hoveredAsset.baseName}</p>
            <p className="text-[10px] font-mono text-emerald-400/90 mt-1 font-medium">⚡ {hoveredAsset.componentAvailability}</p>
            <button
              onClick={() => handleRequestClick(hoveredAsset)}
              className="mt-3 w-full py-2 rounded-lg bg-[#1e4d35] hover:bg-[#163a26] text-white font-mono text-xs font-bold transition-all flex items-center justify-center gap-1.5 shadow-md"
            >
              Request Component <ExternalLink className="w-3.5 h-3.5" />
            </button>
          </div>
        )}

      </div>
    </div>
  );
}
