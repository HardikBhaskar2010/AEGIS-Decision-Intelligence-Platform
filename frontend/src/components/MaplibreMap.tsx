import React, { useEffect, useRef } from 'react';
import maplibregl from 'maplibre-gl';
import type { Sector } from './types';

interface MaplibreMapProps {
  sectors: Sector[];
  selectedSectorId: string | null;
  onSelectSector: (sector: Sector) => void;
}

export const MaplibreMap: React.FC<MaplibreMapProps> = ({
  sectors,
  selectedSectorId,
  onSelectSector,
}) => {
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<maplibregl.Map | null>(null);
  const markersRef = useRef<{ [key: string]: maplibregl.Marker }>({});

  // Initialize Map
  useEffect(() => {
    if (!mapContainerRef.current) return;

    // Use CARTO's Dark Matter GL Style which is free and matches cyberpunk aesthetic
    const map = new maplibregl.Map({
      container: mapContainerRef.current,
      style: 'https://basemaps.cartocdn.com/gl/dark-matter-gl-style/style.json',
      center: [77.5946, 12.9716], // Bangalore center [lng, lat]
      zoom: 11,
      minZoom: 10,
      maxZoom: 15,
      attributionControl: false,
    });

    map.addControl(new maplibregl.NavigationControl({ showCompass: false }), 'bottom-right');

    mapRef.current = map;

    return () => {
      map.remove();
      mapRef.current = null;
    };
  }, []);

  // Update Markers when sectors list or selected sector changes
  useEffect(() => {
    const map = mapRef.current;
    if (!map) return;

    // Helper to get color based on risk score
    const getRiskColor = (score: number) => {
      if (score < 0.35) return '#3DD6A3'; // Low Risk
      if (score < 0.70) return '#F0B429'; // Med Risk
      return '#F0453A'; // High Risk
    };

    // Remove old markers that are no longer present
    const sectorIds = new Set(sectors.map(s => s.sector_id));
    Object.keys(markersRef.current).forEach(id => {
      if (!sectorIds.has(id)) {
        markersRef.current[id].remove();
        delete markersRef.current[id];
      }
    });

    // Add or update markers
    sectors.forEach(sector => {
      const color = getRiskColor(sector.risk_score);
      const isSelected = selectedSectorId === sector.sector_id;

      // If marker already exists, update its element, otherwise create new
      let marker = markersRef.current[sector.sector_id];

      if (marker) {
        // Update element styling
        const el = marker.getElement();
        el.style.color = color;
        if (isSelected) {
          el.style.transform = 'scale(1.35)';
          el.style.borderWidth = '3px';
          el.style.borderColor = '#00E5FF';
          el.style.boxShadow = '0 0 20px #00E5FF';
        } else {
          el.style.transform = 'scale(1)';
          el.style.borderWidth = '2px';
          el.style.borderColor = '#FFFFFF';
          el.style.boxShadow = `0 0 15px ${color}`;
        }
      } else {
        // Create new DOM element for the marker
        const el = document.createElement('div');
        el.className = 'sector-marker';
        el.style.color = color;
        el.style.boxShadow = `0 0 15px ${color}`;
        
        // Show risk score as value in marker
        el.innerText = Math.round(sector.risk_score * 100).toString();

        if (isSelected) {
          el.style.transform = 'scale(1.35)';
          el.style.borderWidth = '3px';
          el.style.borderColor = '#00E5FF';
          el.style.boxShadow = '0 0 20px #00E5FF';
        }

        // Setup marker click handler
        el.addEventListener('click', (e) => {
          e.stopPropagation();
          onSelectSector(sector);
        });

        // Add Popup
        const popup = new maplibregl.Popup({
          closeButton: true,
          closeOnClick: false,
          offset: 15,
          className: 'maplibre-popup-content'
        }).setHTML(`
          <div style="font-family: var(--font-heading); margin-bottom: 4px;">
            <strong style="font-size: 14px; color: #FFFFFF;">${sector.name}</strong>
          </div>
          <div style="font-size: 12px; color: var(--text-secondary); display: flex; flex-direction: column; gap: 4px;">
            <div>Risk Index: <span style="font-weight: bold; color: ${color};">${Math.round(sector.risk_score * 100)}%</span></div>
            <div>Population: <span style="font-weight: bold; color: #FFFFFF;">${sector.population?.toLocaleString() || 'N/A'}</span></div>
          </div>
        `);

        // Create the maplibre marker
        const newMarker = new maplibregl.Marker({
          element: el,
          anchor: 'center',
        })
          .setLngLat([sector.lng, sector.lat])
          .setPopup(popup)
          .addTo(map);

        markersRef.current[sector.sector_id] = newMarker;
      }
    });
  }, [sectors, selectedSectorId, onSelectSector]);

  // Center or pan to selected sector
  useEffect(() => {
    const map = mapRef.current;
    if (!map || !selectedSectorId) return;

    const sector = sectors.find(s => s.sector_id === selectedSectorId);
    if (!sector) return;

    map.easeTo({
      center: [sector.lng, sector.lat],
      zoom: 12.5,
      duration: 1000,
    });

    // Open popup for selected sector
    const marker = markersRef.current[selectedSectorId];
    if (marker) {
      // Toggle popup active
      const popup = marker.getPopup();
      if (popup && !popup.isOpen()) {
        marker.togglePopup();
      }
    }
  }, [selectedSectorId, sectors]);

  return (
    <div className="map-container-wrapper" id="aegis-map-container">
      <div ref={mapContainerRef} className="map-viewport" />
      
      {/* Map Control / Info Overlay */}
      <div className="map-overlay-panel">
        <div className="map-overlay-card">
          <h3 style={{ fontSize: '15px', marginBottom: '8px', borderBottom: '1px solid var(--border-color)', paddingBottom: '6px' }}>
            OPERATIONAL SECTORS
          </h3>
          <div className="map-legend">
            <div className="legend-item">
              <div className="legend-color high" />
              <span>Critical Risk (&ge; 70%)</span>
            </div>
            <div className="legend-item">
              <div className="legend-color med" />
              <span>Elevated Risk (35% - 69%)</span>
            </div>
            <div className="legend-item">
              <div className="legend-color low" />
              <span>Low Risk (&lt; 35%)</span>
            </div>
          </div>
          <p style={{ fontSize: '12px', color: 'var(--text-secondary)', marginTop: '16px' }}>
            Click markers to inspect. Center: Bangalore, India.
          </p>
        </div>
      </div>
    </div>
  );
};
