import React, { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import 'maplibre-gl/dist/maplibre-gl.css';
import { MapPin, MapPinOff } from 'lucide-react';

const OSM_STYLE = {
  version: 8,
  sources: {
    osm: {
      type: 'raster',
      tiles: ['https://tile.openstreetmap.org/{z}/{x}/{y}.png'],
      tileSize: 256,
      attribution:
        '&copy; <a href="https://www.openstreetmap.org/copyright" target="_blank" rel="noopener noreferrer">OpenStreetMap</a> contributors',
    },
  },
  layers: [{ id: 'osm-tiles', type: 'raster', source: 'osm', minzoom: 0, maxzoom: 19 }],
};

const GESTURE_LOCALE = {
  'CooperativeGesturesHandler.WindowsHelpText': 'Usa Ctrl + scroll para acercar el mapa',
  'CooperativeGesturesHandler.MacHelpText': 'Usa ⌘ + scroll para acercar el mapa',
  'CooperativeGesturesHandler.MobileHelpText': 'Usa dos dedos para mover el mapa',
};

/**
 * Mapa de ubicación del establecimiento, con vuelo de cámara y marcador
 * animado. Si no hay coordenadas cargadas, muestra un placeholder del
 * mismo tamaño en su lugar.
 */
export default function EstablishmentMap({ lat, lng, name, address }) {
  const containerRef = useRef(null);
  const mapRef = useRef(null);
  const hasCoords = typeof lat === 'number' && typeof lng === 'number';

  useEffect(() => {
    if (!hasCoords || !containerRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: OSM_STYLE,
      center: [lng, lat],
      zoom: 4,
      attributionControl: { compact: true },
      cooperativeGestures: true,
      locale: GESTURE_LOCALE,
    });
    mapRef.current = map;

    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'top-right');

    map.once('load', () => {
      map.resize();

      const markerEl = document.createElement('div');
      markerEl.className = 'map-marker';
      markerEl.innerHTML = `
        <span class="map-marker-pulse"></span>
        <span class="map-marker-pin">
          <svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
            <path d="M20 10c0 6-8 12-8 12s-8-6-8-12a8 8 0 0 1 16 0Z"/>
            <circle cx="12" cy="10" r="3"/>
          </svg>
        </span>
      `;

      const popup = new maplibregl.Popup({ offset: 22, closeButton: true }).setHTML(
        `<div style="font-family: Inter, sans-serif; max-width: 220px;">
           <p style="margin:0 0 2px; font-weight: 700; font-size: 13px; color: #0f172a;">${escapeHtml(name || '')}</p>
           <p style="margin:0; font-size: 12px; color: #64748b;">${escapeHtml(address || 'Dirección sin especificar')}</p>
         </div>`
      );

      new maplibregl.Marker({ element: markerEl, anchor: 'bottom' })
        .setLngLat([lng, lat])
        .setPopup(popup)
        .addTo(map);

      map.flyTo({ center: [lng, lat], zoom: 15, duration: 1600, curve: 1.4, essential: true });
    });

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, [hasCoords, lat, lng, name, address]);

  if (!hasCoords) {
    return (
      <div className="bg-white p-5 rounded-2xl border border-slate-100 shadow-sm space-y-4">
        <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
          <MapPin size={15} className="text-sky-500" />
          Ubicación
        </h3>
        <div className="h-72 rounded-xl border border-dashed border-slate-200 bg-slate-50 flex flex-col items-center justify-center gap-2 text-center px-6">
          <MapPinOff size={26} className="text-slate-300" />
          <p className="text-sm font-semibold text-slate-500">Ubicación no disponible</p>
          <p className="text-xs text-slate-400">Puedes cargar la latitud y longitud desde "Editar Ficha".</p>
        </div>
      </div>
    );
  }

  return (
    <div className="bg-white p-5 rounded-2xl border border-slate-100 shadow-sm space-y-4">
      <h3 className="text-sm font-bold text-slate-400 uppercase tracking-wider flex items-center gap-2">
        <MapPin size={15} className="text-sky-500" />
        Ubicación
      </h3>
      <div ref={containerRef} className="w-full h-72 rounded-xl overflow-hidden border border-slate-100" />
    </div>
  );
}

function escapeHtml(str) {
  return String(str)
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}
