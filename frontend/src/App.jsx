import { useEffect, useState } from 'react';
import MapView from './components/MapView';
import ShelterList from './components/ShelterList';
import ShelterDetail from './components/ShelterDetail';
import AddShelterForm from './components/AddShelterForm';
import { api } from './api';

function useGeolocation() {
  const [location, setLocation] = useState(null);

  useEffect(() => {
    if (!navigator.geolocation) return;
    navigator.geolocation.getCurrentPosition(
      (pos) => setLocation({ lon: pos.coords.longitude, lat: pos.coords.latitude }),
      () => setLocation(null),
      { enableHighAccuracy: true, timeout: 8000 }
    );
  }, []);

  return location;
}

export default function App() {
  const userLocation = useGeolocation();

  const [miklats, setMiklats] = useState([]);
  const [loadingList, setLoadingList] = useState(true);
  const [filters, setFilters] = useState({ city: '', type: '' });
  const [selectedId, setSelectedId] = useState(null);
  const [selectedMiklat, setSelectedMiklat] = useState(null);

  const [route, setRoute] = useState(null);
  const [routeLoading, setRouteLoading] = useState(false);
  const [routeError, setRouteError] = useState(null);

  const [showAddForm, setShowAddForm] = useState(false);
  const [pickMode, setPickMode] = useState(false);
  const [pickedLocation, setPickedLocation] = useState(null);

  const loadList = () => {
    setLoadingList(true);
    const query = { city: filters.city || undefined, type: filters.type || undefined, limit: 200 };
    const request = userLocation && !filters.city && !filters.type
      ? api.nearestMiklats(userLocation.lon, userLocation.lat, 100)
      : api.listMiklats(query);

    request
      .then(setMiklats)
      .catch(() => setMiklats([]))
      .finally(() => setLoadingList(false));
  };

  useEffect(loadList, [filters.city, filters.type, userLocation]);

  useEffect(() => {
    if (selectedId == null) {
      setSelectedMiklat(null);
      return;
    }
    api.getMiklat(selectedId).then(setSelectedMiklat).catch(() => setSelectedMiklat(null));
    setRoute(null);
    setRouteError(null);
  }, [selectedId]);

  const handleBuildRoute = async (miklatId) => {
    if (!userLocation) return;
    setRouteLoading(true);
    setRouteError(null);
    try {
      const data = await api.routeToMiklat(miklatId, userLocation.lon, userLocation.lat);
      setRoute(data);
    } catch {
      setRouteError('Не удалось построить маршрут.');
    } finally {
      setRouteLoading(false);
    }
  };

  const handlePickLocation = (coords) => {
    setPickedLocation(coords);
    setPickMode(false);
  };

  return (
    <div className="app-layout">
      <header className="app-header">
        <h1>ShelterNearYou · miklat-devops</h1>
        <div className="filters">
          <input
            type="text"
            placeholder="Город"
            value={filters.city}
            onChange={(e) => setFilters({ ...filters, city: e.target.value })}
          />
          <input
            type="text"
            placeholder="Тип"
            value={filters.type}
            onChange={(e) => setFilters({ ...filters, type: e.target.value })}
          />
          <button
            onClick={() => {
              setShowAddForm(true);
              setPickedLocation(null);
            }}
          >
            + Добавить укрытие
          </button>
        </div>
      </header>

      <div className="app-body">
        <aside className="sidebar">
          <ShelterList miklats={miklats} selectedId={selectedId} onSelect={setSelectedId} loading={loadingList} />
        </aside>

        <main className="map-pane">
          {pickMode && <div className="pick-mode-banner">Кликните на карту, чтобы указать точку укрытия</div>}
          <MapView
            miklats={miklats}
            selectedId={selectedId}
            onSelect={setSelectedId}
            userLocation={userLocation}
            routeGeometry={route?.geometry}
            pickMode={pickMode}
            onPickLocation={handlePickLocation}
          />
        </main>

        <aside className="detail-pane">
          <ShelterDetail
            miklat={selectedMiklat}
            userLocation={userLocation}
            onBuildRoute={handleBuildRoute}
            route={route}
            routeLoading={routeLoading}
            routeError={routeError}
            onClearRoute={() => setRoute(null)}
          />
        </aside>
      </div>

      {showAddForm && !pickMode && (
        <AddShelterForm
          pickedLocation={pickedLocation}
          onStartPicking={() => setPickMode(true)}
          onClose={() => {
            setShowAddForm(false);
            setPickMode(false);
          }}
          onSubmitted={loadList}
        />
      )}
    </div>
  );
}
