import { useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, GeoJSON, useMapEvents } from 'react-leaflet';
import L from 'leaflet';

import markerIconUrl from 'leaflet/dist/images/marker-icon.png';
import markerIcon2xUrl from 'leaflet/dist/images/marker-icon-2x.png';
import markerShadowUrl from 'leaflet/dist/images/marker-shadow.png';

// react-leaflet/webpack-less bundlers (vite included) don't pick up
// Leaflet's default icons automatically — the path breaks after the build.
// Standard workaround: re-point the icons explicitly via import.
const defaultIcon = L.icon({
  iconUrl: markerIconUrl,
  iconRetinaUrl: markerIcon2xUrl,
  shadowUrl: markerShadowUrl,
  iconSize: [25, 41],
  iconAnchor: [12, 41],
  popupAnchor: [1, -34],
  shadowSize: [41, 41],
});

const selectedIcon = L.icon({
  iconUrl: markerIconUrl,
  iconRetinaUrl: markerIcon2xUrl,
  shadowUrl: markerShadowUrl,
  iconSize: [32, 52],
  iconAnchor: [16, 52],
  popupAnchor: [1, -44],
  shadowSize: [52, 52],
  className: 'miklat-marker-selected',
});

const userIcon = L.divIcon({
  className: 'user-location-marker',
  html: '<div class="user-location-dot"></div>',
  iconSize: [18, 18],
  iconAnchor: [9, 9],
});

// Start/end markers for an address-to-address route (see
// RouteBetweenAddresses.jsx) — kept visually distinct from userIcon and
// from the default shelter pins.
const routeStartIcon = L.divIcon({
  className: 'route-endpoint-marker',
  html: '<div class="route-endpoint-dot route-endpoint-dot-start"></div>',
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

const routeEndIcon = L.divIcon({
  className: 'route-endpoint-marker',
  html: '<div class="route-endpoint-dot route-endpoint-dot-end"></div>',
  iconSize: [16, 16],
  iconAnchor: [8, 8],
});

// Shelters found along an address-to-address route (addressRoute.miklats) —
// a small distinct dot so they read as "on this route", separate from both
// the default shelter pins and the route start/end markers above.
const alongRouteIcon = L.divIcon({
  className: 'along-route-marker',
  html: '<div class="along-route-dot"></div>',
  iconSize: [14, 14],
  iconAnchor: [7, 7],
});

const TEL_AVIV_CENTER = [32.0853, 34.7818];

function ClickCapture({ enabled, onPick }) {
  useMapEvents({
    click(e) {
      if (enabled) onPick({ lon: e.latlng.lng, lat: e.latlng.lat });
    },
  });
  return null;
}

export default function MapView({
  miklats,
  selectedId,
  onSelect,
  userLocation,
  referenceLabel = 'You are here',
  routeGeometry,
  addressRoute,
  pickMode,
  onPickLocation,
}) {
  const routeLayer = useMemo(() => {
    if (!routeGeometry) return null;
    return { type: 'Feature', geometry: routeGeometry, properties: {} };
  }, [routeGeometry]);

  const addressRouteLayer = useMemo(() => {
    if (!addressRoute?.geometry) return null;
    return { type: 'Feature', geometry: addressRoute.geometry, properties: {} };
  }, [addressRoute]);

  return (
    <MapContainer
      center={userLocation ? [userLocation.lat, userLocation.lon] : TEL_AVIV_CENTER}
      zoom={14}
      className="map-container"
    >
      <TileLayer
        attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a>'
        url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
      />

      <ClickCapture enabled={pickMode} onPick={onPickLocation} />

      {userLocation && (
        <Marker position={[userLocation.lat, userLocation.lon]} icon={userIcon}>
          <Popup>{referenceLabel}</Popup>
        </Marker>
      )}

      {miklats.map((m) => (
        <Marker
          key={m.id}
          position={[m.lat, m.lon]}
          icon={m.id === selectedId ? selectedIcon : defaultIcon}
          eventHandlers={{ click: () => onSelect(m.id) }}
        >
          <Popup>
            <strong>{m.name || 'Unnamed shelter'}</strong>
            <br />
            {m.address || m.city || ''}
          </Popup>
        </Marker>
      ))}

      {routeLayer && <GeoJSON key={JSON.stringify(routeLayer)} data={routeLayer} pathOptions={{ color: '#2563eb', weight: 5 }} />}

      {addressRoute?.from && (
        <Marker position={[addressRoute.from.lat, addressRoute.from.lon]} icon={routeStartIcon}>
          <Popup>Route start</Popup>
        </Marker>
      )}
      {addressRoute?.to && (
        <Marker position={[addressRoute.to.lat, addressRoute.to.lon]} icon={routeEndIcon}>
          <Popup>Route destination</Popup>
        </Marker>
      )}
      {addressRouteLayer && (
        <GeoJSON
          key={JSON.stringify(addressRouteLayer)}
          data={addressRouteLayer}
          pathOptions={{ color: '#16a34a', weight: 5, dashArray: '6 4' }}
        />
      )}

      {(addressRoute?.miklats || []).map((m) => (
        <Marker key={`route-miklat-${m.id}`} position={[m.lat, m.lon]} icon={alongRouteIcon}>
          <Popup>
            <strong>{m.name || 'Unnamed shelter'}</strong>
            <br />
            {m.address || m.city || ''}
            <br />
            {Math.round(m.distance_to_route_m)} m from route
          </Popup>
        </Marker>
      ))}
    </MapContainer>
  );
}
