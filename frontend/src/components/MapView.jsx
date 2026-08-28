import { useMemo } from 'react';
import { MapContainer, TileLayer, Marker, Popup, GeoJSON, useMapEvents } from 'react-leaflet';
import L from 'leaflet';

import markerIconUrl from 'leaflet/dist/images/marker-icon.png';
import markerIcon2xUrl from 'leaflet/dist/images/marker-icon-2x.png';
import markerShadowUrl from 'leaflet/dist/images/marker-shadow.png';

// react-leaflet/webpack-less bundlers (vite included) не подхватывают
// дефолтные иконки Leaflet автоматически — путь к картинкам ломается после
// сборки. Стандартный обход: явно переопределить иконки через import.
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
  routeGeometry,
  pickMode,
  onPickLocation,
}) {
  const routeLayer = useMemo(() => {
    if (!routeGeometry) return null;
    return { type: 'Feature', geometry: routeGeometry, properties: {} };
  }, [routeGeometry]);

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
          <Popup>Вы здесь</Popup>
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
            <strong>{m.name || 'Укрытие без названия'}</strong>
            <br />
            {m.address || m.city || ''}
          </Popup>
        </Marker>
      ))}

      {routeLayer && <GeoJSON key={JSON.stringify(routeLayer)} data={routeLayer} pathOptions={{ color: '#2563eb', weight: 5 }} />}
    </MapContainer>
  );
}
