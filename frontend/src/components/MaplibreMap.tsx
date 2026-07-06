import React, { useEffect, useRef, useCallback } from 'react';
import maplibregl from 'maplibre-gl';
import type { Sector } from './types';

interface MaplibreMapProps {
  sectors: Sector[];
  selectedSectorId: string | null;
  onSelectSector: (sector: Sector) => void;
}

const getRiskColor = (score: number): string => {
  if (score < 0.35) return '#3DD6A3';
  if (score < 0.70) return '#F0B429';
  return '#F0453A';
};

const getRiskLabel = (score: number): string => {
  if (score < 0.35) return 'LOW RISK';
  if (score < 0.70) return 'ELEVATED';
  return 'CRITICAL';
};

export const MaplibreMap: React.FC<MaplibreMapProps> = ({
  sectors,
  selectedSectorId,
  onSelectSector,
}) => {
  const containerRef  = useRef<HTMLDivElement>(null);
  const mapRef        = useRef<maplibregl.Map | null>(null);
  const markersRef    = useRef<{ [id: string]: maplibregl.Marker }>({});
  const popupsRef     = useRef<{ [id: string]: maplibregl.Popup }>({});
  const onSelectRef   = useRef(onSelectSector);
  onSelectRef.current = onSelectSector;

  // ── Initialize Map ──────────────────────────────────────────
  useEffect(() => {
    if (!containerRef.current || mapRef.current) return;

    const map = new maplibregl.Map({
      container: containerRef.current,
      style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center:  [103.8198, 1.3521],  // Singapore center
      zoom:    11,
      minZoom: 9,
      maxZoom: 16,
      attributionControl: false,
      pitchWithRotate: false,
    });

    map.addControl(
      new maplibregl.NavigationControl({ showCompass: false }),
      'bottom-right'
    );

    mapRef.current = map;

    return () => {
      // Clean up markers
      Object.values(markersRef.current).forEach(m => m.remove());
      markersRef.current = {};
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // ── Build popup HTML for a sector ──────────────────────────
  const buildPopupHtml = useCallback((sector: Sector): string => {
    const color = getRiskColor(sector.risk_score);
    const risk  = Math.round(sector.risk_score * 100);
    const label = getRiskLabel(sector.risk_score);

    return `
      <div style="font-family:'Inter',sans-serif; min-width:200px;">
        <div style="display:flex; align-items:center; justify-content:space-between; margin-bottom:10px; padding-bottom:8px; border-bottom:1px solid rgba(255,255,255,0.08);">
          <strong style="font-size:13px; color:#FFFFFF; font-family:'Outfit',sans-serif; font-weight:700;">${sector.name}</strong>
          <span style="font-size:9px; font-family:'JetBrains Mono',monospace; font-weight:700; padding:2px 7px; border-radius:4px;
            background:${color}22; color:${color}; border:1px solid ${color}44; white-space:nowrap; margin-left:8px;">${label}</span>
        </div>
        <div style="display:grid; grid-template-columns:1fr 1fr; gap:8px;">
          <div style="display:flex; flex-direction:column; gap:3px;">
            <span style="font-size:9px; font-family:'JetBrains Mono',monospace; text-transform:uppercase; letter-spacing:0.08em; color:#484F58;">Risk Index</span>
            <span style="font-size:22px; font-weight:800; font-family:'Outfit',sans-serif; color:${color}; line-height:1; letter-spacing:-0.02em;">${risk}<span style="font-size:12px; font-weight:600; opacity:0.7;">%</span></span>
            <div style="height:3px; background:rgba(255,255,255,0.07); border-radius:99px; overflow:hidden; margin-top:2px;">
              <div style="width:${risk}%; height:100%; background:${color}; box-shadow:0 0 6px ${color}; border-radius:99px;"></div>
            </div>
          </div>
          <div style="display:flex; flex-direction:column; gap:3px;">
            <span style="font-size:9px; font-family:'JetBrains Mono',monospace; text-transform:uppercase; letter-spacing:0.08em; color:#484F58;">Population</span>
            <span style="font-size:18px; font-weight:700; font-family:'Outfit',sans-serif; color:#FFFFFF; line-height:1; letter-spacing:-0.02em;">${sector.population?.toLocaleString() ?? 'N/A'}</span>
            <span style="font-size:9px; color:#484F58; font-family:'JetBrains Mono',monospace;">residents</span>
          </div>
        </div>
        <div style="margin-top:10px; padding-top:8px; border-top:1px solid rgba(255,255,255,0.06);">
          <span style="font-size:9.5px; color:#484F58; font-family:'JetBrains Mono',monospace;">${sector.sector_id.toUpperCase()} · ${sector.lat.toFixed(4)}°N ${sector.lng.toFixed(4)}°E</span>
        </div>
      </div>
    `;
  }, []);

  // ── Create / Update Markers ─────────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    const waitForLoad = () => {
      const sectorIds = new Set(sectors.map(s => s.sector_id));

      // Remove stale markers
      Object.keys(markersRef.current).forEach(id => {
        if (!sectorIds.has(id)) {
          markersRef.current[id].remove();
          delete markersRef.current[id];
          delete popupsRef.current[id];
        }
      });

      sectors.forEach(sector => {
        const color      = getRiskColor(sector.risk_score);
        const isSelected = selectedSectorId === sector.sector_id;
        const riskPct    = Math.round(sector.risk_score * 100);

        if (markersRef.current[sector.sector_id]) {
          // ── Update existing marker ──
          const wrapperEl = markersRef.current[sector.sector_id].getElement();
          wrapperEl.style.zIndex = isSelected ? '30' : '10';
          
          const el = wrapperEl.querySelector('.sector-marker') as HTMLElement;
          if (el) {
            el.className = `sector-marker${isSelected ? ' selected' : ''}`;
            el.style.borderColor  = isSelected ? '#00E5FF' : color;
            el.style.boxShadow    = isSelected
              ? '0 0 0 3px rgba(0,229,255,0.3), 0 0 24px rgba(0,229,255,0.6)'
              : `0 0 12px ${color}60`;
            el.style.borderWidth  = isSelected ? '3px' : '2px';
            
            // Update inner text
            const inner = el.querySelector('.marker-inner') as HTMLElement | null;
            if (inner) inner.textContent = riskPct.toString();
          }

          // Update popup content
          const popup = popupsRef.current[sector.sector_id];
          if (popup) popup.setHTML(buildPopupHtml(sector));

        } else {
          // ── Create new marker element ──
          const wrapperEl = document.createElement('div');
          wrapperEl.className = 'marker-wrapper';
          wrapperEl.style.cursor = 'pointer';
          wrapperEl.style.zIndex = isSelected ? '30' : '10';
          
          const el = document.createElement('div');
          el.className = `sector-marker${isSelected ? ' selected' : ''}`;
          el.style.color       = color;
          el.style.borderColor = isSelected ? '#00E5FF' : color;
          el.style.boxShadow   = isSelected
            ? '0 0 0 3px rgba(0,229,255,0.3), 0 0 24px rgba(0,229,255,0.6)'
            : `0 0 12px ${color}60`;

          // Inner label
          const inner = document.createElement('span');
          inner.className = 'marker-inner';
          inner.textContent = riskPct.toString();
          inner.style.cssText = 'font-size:9px; font-weight:700; font-family:\'Outfit\',sans-serif; letter-spacing:-0.01em; color:#fff; pointer-events:none;';
          el.appendChild(inner);
          
          wrapperEl.appendChild(el);

          // Click to select
          wrapperEl.addEventListener('click', (e) => {
            e.stopPropagation();
            onSelectRef.current(sector);
          });

          // Popup
          const popup = new maplibregl.Popup({
            closeButton: true,
            closeOnClick: false,
            offset: 18,
          }).setHTML(buildPopupHtml(sector));

          popupsRef.current[sector.sector_id] = popup;

          const marker = new maplibregl.Marker({ element: wrapperEl, anchor: 'center' })
            .setLngLat([sector.lng, sector.lat])
            .setPopup(popup)
            .addTo(map);

          markersRef.current[sector.sector_id] = marker;
        }
      });
    };

    if (map.isStyleLoaded()) {
      waitForLoad();
    } else {
      map.once('load', waitForLoad);
    }
  }, [sectors, selectedSectorId, buildPopupHtml]);

  // ── Fly to selected sector ──────────────────────────────────
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !selectedSectorId) return;

    const sector = sectors.find(s => s.sector_id === selectedSectorId);
    if (!sector) return;

    map.flyTo({
      center: [sector.lng, sector.lat],
      zoom:   12.8,
      speed:  1.4,
      curve:  1.2,
      essential: true,
    });

    // Open the popup
    const marker = markersRef.current[selectedSectorId];
    if (marker) {
      const popup = marker.getPopup();
      if (popup && !popup.isOpen()) marker.togglePopup();
    }
  }, [selectedSectorId, sectors]);

  return (
    <div className="map-container-wrapper" id="aegis-map-container">
      <div ref={containerRef} className="map-viewport" />

      {/* Legend overlay */}
      <div className="map-overlay-panel">
        <div className="map-overlay-card">
          <div style={{ fontSize: '9px', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.14em', color: 'var(--text-muted)', marginBottom: '10px', fontWeight: 700 }}>
            Risk Legend
          </div>
          {[
            { color: '#F0453A', label: 'Critical', range: '≥ 70%' },
            { color: '#F0B429', label: 'Elevated',  range: '35–69%' },
            { color: '#3DD6A3', label: 'Normal',    range: '< 35%' },
          ].map(({ color, label, range }) => (
            <div key={label} className="map-legend-row">
              <div
                className="map-legend-dot"
                style={{
                  background: color,
                  boxShadow: `0 0 6px ${color}80`,
                }}
              />
              <span style={{ flex: 1 }}>{label}</span>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: '10px', color: 'var(--text-muted)' }}>{range}</span>
            </div>
          ))}
          <div style={{ marginTop: '10px', paddingTop: '10px', borderTop: '1px solid var(--border-subtle)', fontSize: '10px', color: 'var(--text-muted)', fontFamily: 'var(--font-mono)' }}>
            {sectors.length} sector{sectors.length !== 1 ? 's' : ''} monitored
          </div>
        </div>
      </div>
    </div>
  );
};
