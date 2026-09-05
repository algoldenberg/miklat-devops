import { useState, useEffect } from 'react';
import Map from './components/Map';
import ShelterSearch from './components/ShelterSearch';
import RouteBuilder from './components/RouteBuilder';
import Footer from './components/Footer';
import { api } from './api';

// Full 1:1 port of shelter-route-planner/frontend/src/App.jsx (tabbed
// "Find Shelters" / "Plan Route" sidebar, popup-based shelter details,
// click-on-map modes, "Search Here", live-location follow mode — see
// claude/miklat-work-plan.md, Phase 6 item 1, for the scope decision this
// implements). The UI text, layout and interaction logic below are kept
// exactly as the original. The following adaptations were unavoidable
// because our backend/data model differs from the original's (documented
// once here rather than repeated at every call site):
//   - Our shelter objects use id/lon/lat (not _id/longitude/latitude).
//   - "Find Shelters" calls api.nearbyMiklats (our /miklats/nearest with
//     max_distance_m) instead of GET /shelters/nearby/.
//   - "Plan Route" calls api.routeBetweenPoints (our POST /route, already
//     built in Phase 6 Step 2/3) instead of POST /route/calculate. Our
//     response is {distance_m, duration_s, geometry, miklats} with no
//     from/to or total_shelters fields, so those are attached here
//     (from/to) or derived (miklats.length) after the call.
//   - hCaptcha, hCaptcha-gated submission, hCaptcha-gated add-shelter photos,
//     hCaptcha-only Report/AddShelter fields, hCaptcha env var — all dropped
//     (no site key or backend validation exists for us). Photos are a
//     separate, already-moderated flow (PhotosSection) instead of being
//     attached to comments/submissions/reports.
//   - Shelter type list and issue-type list use our real values (see
//     AddShelterModal.jsx / ReportModal.jsx for the verified lists).
//   - Footer has no live shelter counter (no stats endpoint on our backend).
//   - PWA update notice, disclaimer modal, support/donate button, and the
//     info/privacy pages are excluded — agreed with the user on 05.09.2026,
//     before this UI port started (see miklat-work-plan.md).

const DEFAULT_CENTER = [32.0853, 34.7818]; // Tel Aviv — same fallback as the original

function App() {
  const [shelters, setShelters] = useState([]);
  const [center, setCenter] = useState(null);
  const [loading, setLoading] = useState(false);
  const [stats, setStats] = useState({ total: 0, radius: 0 });
  const [locationLoaded, setLocationLoaded] = useState(false);
  const [mapReady, setMapReady] = useState(false);

  // Route state
  const [routeData, setRouteData] = useState(null);
  const [routeLoading, setRouteLoading] = useState(false);
  const [activeTab, setActiveTab] = useState('shelters');

  // Map click mode state
  const [mapClickMode, setMapClickMode] = useState(null);
  const [clickedPoints, setClickedPoints] = useState({ start: null, end: null });

  // Search center state
  const [clickedSearchPoint, setClickedSearchPoint] = useState(null);

  // Search Here state
  const [showSearchHere, setShowSearchHere] = useState(false);
  const [mapCenter, setMapCenter] = useState(null);

  // Clear search marker trigger
  const [clearSearchTrigger, setClearSearchTrigger] = useState(0);

  const handleSearch = async ({ latitude, longitude, radius }) => {
    setLoading(true);
    try {
      const data = await api.nearbyMiklats(longitude, latitude, radius, 50);
      setShelters(data);
      setCenter([latitude, longitude]);
      setMapCenter([latitude, longitude]);
      setStats({ total: data.length, radius });
      setShowSearchHere(false);
    } catch (error) {
      console.error('Error fetching shelters:', error);
      alert('Service is updating. Please wait a moment and try again.');
    } finally {
      setLoading(false);
    }
  };

  // Auto-load user location on first mount
  useEffect(() => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const userLat = position.coords.latitude;
          const userLon = position.coords.longitude;
          setCenter([userLat, userLon]);
          setMapCenter([userLat, userLon]);
          setLocationLoaded(true);
          setMapReady(true);
          handleSearch({ latitude: userLat, longitude: userLon, radius: 1000 });
        },
        (error) => {
          console.warn('Geolocation error:', error.message);
          setCenter(DEFAULT_CENTER);
          setMapCenter(DEFAULT_CENTER);
          setLocationLoaded(false);
          setMapReady(true);
          handleSearch({ latitude: DEFAULT_CENTER[0], longitude: DEFAULT_CENTER[1], radius: 1000 });
        },
        { enableHighAccuracy: true, timeout: 10000, maximumAge: 0 }
      );
    } else {
      setCenter(DEFAULT_CENTER);
      setMapCenter(DEFAULT_CENTER);
      setLocationLoaded(false);
      setMapReady(true);
      handleSearch({ latitude: DEFAULT_CENTER[0], longitude: DEFAULT_CENTER[1], radius: 1000 });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const handleSearchHere = () => {
    if (mapCenter) {
      const coords = { latitude: mapCenter[0], longitude: mapCenter[1] };
      setClickedSearchPoint(coords);
      handleSearch({ latitude: coords.latitude, longitude: coords.longitude, radius: stats.radius || 1000 });
    }
  };

  const handleSearchLocationSet = (coords) => {
    setClickedSearchPoint(coords);
  };

  const handleMapMove = (newCenter) => {
    setMapCenter(newCenter);

    if (activeTab === 'shelters' && center && newCenter) {
      const distance = Math.sqrt(Math.pow(newCenter[0] - center[0], 2) + Math.pow(newCenter[1] - center[1], 2));
      const shouldShow = distance > 0.001; // ~100m threshold
      setShowSearchHere((prev) => (prev !== shouldShow ? shouldShow : prev));
    }
  };

  const handleCalculateRoute = async ({ start, end }) => {
    setRouteLoading(true);
    try {
      const data = await api.routeBetweenPoints(
        { lon: start.longitude, lat: start.latitude },
        { lon: end.longitude, lat: end.latitude }
      );

      setRouteData({
        ...data,
        from: { lat: start.latitude, lon: start.longitude },
        to: { lat: end.latitude, lon: end.longitude },
      });

      setShelters([]);
    } catch (error) {
      console.error('Error calculating route:', error);
      alert('Service is updating. Please wait a moment and try again.');
    } finally {
      setRouteLoading(false);
    }
  };

  const handleClearRoute = () => {
    setRouteData(null);
    setClickedPoints({ start: null, end: null });
    setMapClickMode(null);
    if (center) {
      handleSearch({ latitude: center[0], longitude: center[1], radius: stats.radius || 1000 });
    }
  };

  const handleBuildRouteToShelter = (shelterLat, shelterLon) => {
    setActiveTab('route');

    const startLat = center[0];
    const startLon = center[1];

    setClickedPoints({
      start: { latitude: startLat, longitude: startLon },
      end: { latitude: shelterLat, longitude: shelterLon },
    });

    handleCalculateRoute({
      start: { latitude: startLat, longitude: startLon },
      end: { latitude: shelterLat, longitude: shelterLon },
    });
  };

  const handleMapClick = async (lat, lng, mode) => {
    const newPoint = { latitude: lat, longitude: lng };

    if (mode === 'start') {
      setClickedPoints((prev) => ({ ...prev, start: newPoint }));
      setMapClickMode(null);
    } else if (mode === 'end') {
      setClickedPoints((prev) => ({ ...prev, end: newPoint }));
      setMapClickMode(null);
    } else if (mode === 'search') {
      setClickedSearchPoint(newPoint);
      setMapClickMode(null);
      await handleSearch({ latitude: newPoint.latitude, longitude: newPoint.longitude, radius: 1000 });
    }
  };

  const handleMarkerClick = (shelterRef) => {
    if (shelterRef && shelterRef.current) {
      shelterRef.current.openPopup();
    }
  };

  const handleFollowModeEnabled = (coords) => {
    if (activeTab === 'shelters') {
      handleSearch({ latitude: coords.latitude, longitude: coords.longitude, radius: 1000 });
      setCenter([coords.latitude, coords.longitude]);
    }
  };

  const handleSetMapClickMode = (mode) => {
    setMapClickMode(mode);
  };

  const handleClearSearchMarker = () => {
    setClickedSearchPoint(null);
    setClearSearchTrigger((prev) => prev + 1);
  };

  const handleRoutePointSet = (type, coords) => {
    if (type === 'start') {
      setClickedPoints((prev) => ({ ...prev, start: coords }));
    } else if (type === 'end') {
      setClickedPoints((prev) => ({ ...prev, end: coords }));
    }
  };

  const handleShelterAdded = () => {
    if (center) {
      handleSearch({ latitude: center[0], longitude: center[1], radius: stats.radius || 1000 });
    }
  };

  if (!mapReady || !center) {
    return (
      <div className="app">
        <header className="app-header">
          <h1>🛡️ Shelter Route Planner</h1>
          <p>Find safe routes through bomb shelters in Israel</p>
        </header>
        <div
          style={{
            flex: 1,
            display: 'flex',
            alignItems: 'center',
            justifyContent: 'center',
            fontSize: '1.2rem',
            color: '#666',
          }}
        >
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '3rem', marginBottom: '20px' }}>📍</div>
            <div>Getting your location...</div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="app-header">
        <h1>🛡️ Shelter Route Planner</h1>
        <p>Find safe routes through bomb shelters in Israel</p>
      </header>

      <div className="app-container">
        <aside className="sidebar">
          <div className="tabs">
            <button className={`tab ${activeTab === 'shelters' ? 'tab--active' : ''}`} onClick={() => setActiveTab('shelters')}>
              🔍 Find Shelters
            </button>
            <button className={`tab ${activeTab === 'route' ? 'tab--active' : ''}`} onClick={() => setActiveTab('route')}>
              🗺️ Plan Route
            </button>
          </div>

          {activeTab === 'shelters' && (
            <>
              <ShelterSearch
                onSearch={handleSearch}
                loading={loading}
                currentLocation={center}
                showSearchHere={showSearchHere}
                onSearchHere={handleSearchHere}
                onSetMapClickMode={handleSetMapClickMode}
                clickedSearchPoint={clickedSearchPoint}
                onClearSearchMarker={handleClearSearchMarker}
                onSearchLocationSet={handleSearchLocationSet}
              />

              <div className="stats">
                <h3>📊 Search Results</h3>
                <p>
                  <strong>{stats.total}</strong> shelters found
                </p>
                <p>
                  within <strong>{stats.radius}m</strong> radius
                </p>
                {locationLoaded && (
                  <p style={{ fontSize: '0.85rem', marginTop: '8px', color: '#4CAF50' }}>📍 Showing shelters near you</p>
                )}
              </div>
            </>
          )}

          {activeTab === 'route' && (
            <>
              <RouteBuilder
                onCalculateRoute={handleCalculateRoute}
                loading={routeLoading}
                onClear={handleClearRoute}
                onSetMapClickMode={handleSetMapClickMode}
                clickedPoints={clickedPoints}
                onRoutePointSet={handleRoutePointSet}
              />

              {routeData && (
                <>
                  <div className="route-info">
                    <h3>📍 Route Information</h3>
                    <p>
                      <strong>Distance:</strong> {(routeData.distance_m / 1000).toFixed(2)} km
                    </p>
                    <p>
                      <strong>Walking time:</strong> {Math.round(routeData.duration_s / 60)} minutes
                    </p>
                    <p>
                      <strong>Shelters along route:</strong> {routeData.miklats?.length || 0}
                    </p>
                  </div>

                  <button onClick={handleClearRoute} className="btn-clear-route">
                    ✕ Clear Route
                  </button>
                </>
              )}
            </>
          )}
        </aside>

        <main className="map-container">
          <Map
            center={center}
            zoom={15}
            shelters={shelters}
            onMarkerClick={handleMarkerClick}
            routeData={routeData}
            onMapClick={handleMapClick}
            mapClickMode={mapClickMode}
            onBuildRouteToShelter={handleBuildRouteToShelter}
            onMapMove={handleMapMove}
            onFollowModeEnabled={handleFollowModeEnabled}
            activeTab={activeTab}
            clearSearchTrigger={clearSearchTrigger}
            clickedSearchPoint={clickedSearchPoint}
            clickedPoints={clickedPoints}
            onShelterAdded={handleShelterAdded}
          />
        </main>
      </div>

      <Footer />
    </div>
  );
}

export default App;
