import L from 'leaflet';

// Ported from shelter-route-planner/frontend/src/utils/mapIcons.js as-is —
// emoji-based divIcons, no external image assets needed.

// Route start marker (blue pin).
export const routeStartIcon = L.divIcon({
  className: 'custom-route-marker',
  html: `
    <div style="
      font-size: 36px;
      line-height: 1;
      text-align: center;
      filter: drop-shadow(0 2px 6px rgba(0,0,0,0.4));
      transform: translateY(-8px);
    ">
      📍
    </div>
  `,
  iconSize: [36, 36],
  iconAnchor: [18, 36],
  popupAnchor: [0, -36],
});

// Route end marker (checkered flag).
export const routeEndIcon = L.divIcon({
  className: 'custom-route-marker',
  html: `
    <div style="
      font-size: 36px;
      line-height: 1;
      text-align: center;
      filter: drop-shadow(0 2px 6px rgba(0,0,0,0.4));
      transform: translateY(-8px);
    ">
      🏁
    </div>
  `,
  iconSize: [36, 36],
  iconAnchor: [18, 36],
  popupAnchor: [0, -36],
});

// Search center marker (magnifying glass).
export const searchCenterIcon = L.divIcon({
  className: 'custom-search-marker',
  html: `
    <div style="
      font-size: 36px;
      line-height: 1;
      text-align: center;
      filter: drop-shadow(0 2px 6px rgba(0,0,0,0.4));
      transform: translateY(-8px);
    ">
      🔍
    </div>
  `,
  iconSize: [36, 36],
  iconAnchor: [18, 36],
  popupAnchor: [0, -36],
});
