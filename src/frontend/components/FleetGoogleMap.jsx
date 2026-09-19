'use client';

import React, { useState, useEffect, useRef, useMemo } from 'react';
import { useRouter } from 'next/navigation';
import { MapPin, Navigation, Compass, Layers, ExternalLink, ShieldAlert, CheckCircle2 } from 'lucide-react';

const GOOGLE_MAPS_API_KEY = process.env.NEXT_PUBLIC_GOOGLE_MAPS_API_KEY || '';

// Dark Graphite + Muted Military Green Aerospace Palette Google Map Styles
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

// Tactical Airbase Locations mapping for enrolled fleet assets
const KNOWN_LOCATIONS = {
  'AH-64-01':   { base: 'Fort Campbell Airbase',      lat: 36.6575, lng: -87.4975 },
  'F-16-01':    { base: 'Luke Air Force Base',        lat: 33.5350, lng: -112.3830 },
  'HMMWV-01':   { base: 'Fort Irwin Training Center',  lat: 35.2625, lng: -116.6858 },
  'C-130-02':   { base: 'Little Rock Air Force Base', lat: 34.9167, lng: -92.1497 },
  'UH-60-03':   { base: 'Nellis Air Force Base',      lat: 36.2361, lng: -115.0342 },
  'CH-47-04':   { base: 'Joint Base Lewis-McChord',   lat: 47.1378, lng: -122.5814 },
  'ast_ah64_01':{ base: 'Fort Campbell Airbase',      lat: 36.6575, lng: -87.4975 },
  'ast_f16_01': { base: 'Luke Air Force Base',        lat: 33.5350, lng: -112.3830 },
  'ast_hmmwv_01':{ base: 'Fort Irwin Training Center', lat: 35.2625, lng: -116.6858 },
  'ast_c130_02':{ base: 'Little Rock Air Force Base', lat: 34.9167, lng: -92.1497 },
  'ast_uh60_03':{ base: 'Nellis Air Force Base',      lat: 36.2361, lng: -115.0342 },
  'ast_ch47_04':{ base: 'Joint Base Lewis-McChord',   lat: 47.1378, lng: -122.5814 },
};

export default function FleetGoogleMap({ assets = [], readinessMap = {} }) {
  const router = useRouter();
  const mapContainerRef = useRef(null);
  const [userLocation, setUserLocation] = useState(null);
  const [userLocStatus, setUserLocStatus] = useState('Detecting GPS...');
  const [hoveredAsset, setHoveredAsset] = useState(null);
  const [mapLoaded, setMapLoaded] = useState(false);
  const [activeFilter, setActiveFilter] = useState('ALL');

  // Detect user current location via Geolocation API
  useEffect(() => {
    if (typeof window !== 'undefined' && navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (pos) => {
          setUserLocation({
            lat: pos.coords.latitude,
            lng: pos.coords.longitude,
          });
          setUserLocStatus('GPS Active');
        },
        () => {
          // Fallback location: Los Angeles Air Command Base
          setUserLocation({ lat: 34.0522, lng: -118.2437 });
          setUserLocStatus('Base Location Set');
        },
        { timeout: 8000 }
      );
    } else {
      setUserLocation({ lat: 34.0522, lng: -118.2437 });
      setUserLocStatus('Default Base Set');
    }
  }, []);

  // Format fleet asset locations data
  const fleetLocations = useMemo(() => {
    const list = assets && assets.length > 0 ? assets : [
      { id: 'ast_ah64_01', asset_code: 'AH-64-01', call_sign: 'Ghost 1', asset_type: 'HELICOPTER', status: 'READY' },
      { id: 'ast_f16_01', asset_code: 'F-16-01', call_sign: 'Viper Lead', asset_type: 'FIXED_WING', status: 'READY' },
      { id: 'ast_hmmwv_01', asset_code: 'HMMWV-01', call_sign: 'Bravo 1', asset_type: 'GROUND_VEHICLE', status: 'AT_RISK' },
      { id: 'ast_c130_02', asset_code: 'C-130-02', call_sign: 'Hercules 2', asset_type: 'FIXED_WING', status: 'READY' },
      { id: 'ast_uh60_03', asset_code: 'UH-60-03', call_sign: 'Blackhawk 3', asset_type: 'HELICOPTER', status: 'NOT_READY' },
      { id: 'ast_ch47_04', asset_code: 'CH-47-04', call_sign: 'Chinook 4', asset_type: 'HELICOPTER', status: 'READY' },
    ];

    return list.map((a, idx) => {
      const rec = readinessMap[a.id] || {};
      const status = rec.status || a.status || 'READY';
      const locSpec = KNOWN_LOCATIONS[a.asset_code] || KNOWN_LOCATIONS[a.id] || {
        base: `Sector Base ${idx + 1}`,
        lat: 34.0 + (idx * 2.2) % 12,
        lng: -115.0 + (idx * 5.1) % 30,
      };

      return {
        ...a,
        status,
        baseName: locSpec.base,
        lat: locSpec.lat,
        lng: locSpec.lng,
      };
    });
  }, [assets, readinessMap]);

  const filteredLocations = useMemo(() => {
    if (activeFilter === 'ALL') return fleetLocations;
    return fleetLocations.filter((item) => item.status === activeFilter);
  }, [fleetLocations, activeFilter]);

  // Load Google Maps JS API script if API key is provided
  useEffect(() => {
    if (!GOOGLE_MAPS_API_KEY || typeof window === 'undefined') return;

    if (window.google?.maps) {
      setMapLoaded(true);
      return;
    }

    const scriptId = 'google-maps-api-script';
    if (!document.getElementById(scriptId)) {
      const script = document.createElement('script');
      script.id = scriptId;
      script.src = `https://maps.googleapis.com/maps/api/js?key=${GOOGLE_MAPS_API_KEY}&callback=initGoogleMap`;
      script.async = true;
      script.defer = true;
      window.initGoogleMap = () => setMapLoaded(true);
      document.head.appendChild(script);
    }
  }, []);

  // Initialize Native Google Map when Google Script is available
  useEffect(() => {
    if (!mapLoaded || !mapContainerRef.current || !window.google?.maps) return;

    const center = userLocation || { lat: 37.0902, lng: -95.7129 };
    const map = new window.google.maps.Map(mapContainerRef.current, {
      center,
      zoom: 4,
      styles: AEROSPACE_DARK_MAP_STYLES,
      disableDefaultUI: true,
      zoomControl: true,
    });

    // User Location Marker
    if (userLocation) {
      new window.google.maps.Marker({
        position: userLocation,
        map,
        title: 'Your Location',
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

    // Fleet Dots
    filteredLocations.forEach((loc) => {
      const colorMap = { READY: '#34d399', AT_RISK: '#fbbf24', NOT_READY: '#f87171' };
      const marker = new window.google.maps.Marker({
        position: { lat: loc.lat, lng: loc.lng },
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
      marker.addListener('click', () => {
        router.push(`/maintenance?asset_id=${loc.id || loc.asset_code}&request=true`);
      });
    });
  }, [mapLoaded, userLocation, filteredLocations, router]);

  const handleRequestClick = (assetItem) => {
    router.push(`/maintenance?asset_id=${assetItem.id || assetItem.asset_code}&request=true`);
  };

  return (
    <div className="dashboard-card-shape p-6 flex flex-col justify-between transition-all duration-200">
      {/* Header Bar matching Picture 1 */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4 mb-4 pb-4 border-b border-[#1e4d35]/20 dark:border-slate-800">
        <div>
          <div className="flex items-center gap-2 mb-1">
            <span className="text-[10px] font-mono font-bold uppercase tracking-widest text-[#1e4d35] dark:text-[#4e9f76]">
              FLEET GEOSPATIAL TELEMETRY
            </span>
            <span className="inline-flex items-center gap-1.5 px-2.5 py-0.5 rounded-full text-[10px] font-mono font-semibold bg-[#e1eadf] text-[#1e4d35] dark:bg-[#1e4d35]/40 dark:text-emerald-300 border border-[#1e4d35]/30">
              <span className="w-1.5 h-1.5 rounded-full bg-emerald-400 animate-pulse" />
              {userLocStatus}
            </span>
          </div>
          <h2 className="text-lg font-bold font-sans text-[#122018] dark:text-slate-100">
            Global Fleet Operations Map
          </h2>
        </div>

        {/* Status Filter Badges matching aerospace design */}
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
      <div className="relative w-full h-[380px] rounded-xl overflow-hidden border border-[#1e4d35]/25 dark:border-[#4e9f76]/30 bg-[#0d1b13] shadow-inner select-none">
        
        {/* Google Map Container Element */}
        <div ref={mapContainerRef} className="w-full h-full" />

        {/* Custom Dark Vector Map Rendering Fallback when API Key is not set or when loading */}
        {(!GOOGLE_MAPS_API_KEY || !mapLoaded) && (
          <div className="absolute inset-0 bg-[#0d1b13] bg-[radial-gradient(#1e4d35_1px,transparent_1px)] [background-size:24px_24px] flex flex-col justify-between p-6">
            
            {/* Tactical Grid Coordinates Lines */}
            <div className="absolute inset-0 pointer-events-none opacity-20">
              <div className="absolute top-1/2 left-0 right-0 h-[1px] bg-[#4e9f76]" />
              <div className="absolute left-1/2 top-0 bottom-0 w-[1px] bg-[#4e9f76]" />
            </div>

            {/* Map Header Status Indicator Overlay */}
            <div className="relative z-10 flex items-center justify-between text-[11px] font-mono text-[#4e9f76] tracking-wider pointer-events-none">
              <span className="flex items-center gap-1.5 bg-[#050811]/80 px-3 py-1 rounded-md border border-[#1e4d35]/40 backdrop-blur-md">
                <Navigation className="w-3.5 h-3.5 text-cyan-400 animate-spin" />
                SECTOR GEOSPATIAL VECTOR MATRIX
              </span>
              <span className="bg-[#050811]/80 px-3 py-1 rounded-md border border-[#1e4d35]/40 backdrop-blur-md">
                LAT 34.0522° N / LON 118.2437° W
              </span>
            </div>

            {/* Tactical Minimal Dot Markers for Fleet Locations */}
            <div className="relative z-10 w-full h-full">
              
              {/* User Primary Location Marker */}
              {userLocation && (
                <div
                  className="absolute transform -translate-x-1/2 -translate-y-1/2 flex flex-col items-center group cursor-pointer"
                  style={{ top: '55%', left: '42%' }}
                >
                  <div className="relative flex items-center justify-center">
                    <span className="animate-ping absolute inline-flex h-8 w-8 rounded-full bg-cyan-400 opacity-60" />
                    <span className="relative inline-flex rounded-full h-3.5 w-3.5 bg-cyan-400 border-2 border-white shadow-lg shadow-cyan-400/50" />
                  </div>
                  <span className="mt-1 px-2 py-0.5 rounded text-[9px] font-mono font-bold bg-[#050811]/90 text-cyan-300 border border-cyan-400/40 backdrop-blur-md shadow-md">
                    YOUR LOCATION
                  </span>
                </div>
              )}

              {/* Fleet Aircraft Location Minimal Dots */}
              {filteredLocations.map((loc, idx) => {
                const topPos = `${25 + ((idx * 16) % 55)}%`;
                const leftPos = `${18 + ((idx * 21) % 68)}%`;

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
                    onClick={() => handleRequestClick(loc)}
                  >
                    {/* Small Minimal Dot Marker */}
                    <div className="relative flex items-center justify-center p-2">
                      <span className={`w-3 h-3 rounded-full ${dotColor} shadow-md transition-all duration-200 group-hover:scale-150 group-hover:ring-4 group-hover:ring-[#4e9f76]/40`} />
                    </div>

                    {/* Interactive Tooltip Card on Hover */}
                    <div className="absolute left-1/2 -translate-x-1/2 bottom-full mb-2 hidden group-hover:flex flex-col w-56 p-3 rounded-xl bg-[#0a150f]/95 border border-[#4e9f76]/50 text-slate-100 shadow-2xl backdrop-blur-md z-30 pointer-events-auto">
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
                      <p className="text-[10px] font-mono text-[#566b5c] dark:text-slate-400 mt-0.5">{loc.baseName}</p>
                      <p className="text-[9px] font-mono text-emerald-400/80 mt-0.5">{loc.lat.toFixed(4)}° N, {Math.abs(loc.lng).toFixed(4)}° W</p>

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

            {/* Bottom Map Legend */}
            <div className="relative z-10 flex items-center justify-between text-[10px] font-mono text-[#566b5c] dark:text-slate-400 bg-[#050811]/80 px-4 py-2 rounded-lg border border-[#1e4d35]/30 backdrop-blur-md">
              <span className="flex items-center gap-3">
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-cyan-400" /> Current Location</span>
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-[#34d399]" /> Ready Location</span>
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-amber-400" /> At Risk Location</span>
                <span className="flex items-center gap-1.5"><span className="w-2 h-2 rounded-full bg-red-400" /> Not Ready Location</span>
              </span>
              <span className="text-[#4e9f76] font-semibold">Hover to view details • Click to request</span>
            </div>

          </div>
        )}

      </div>
    </div>
  );
}
