import { useState, useEffect } from 'react';
import AddressSearch from './AddressSearch';

// Ported from shelter-route-planner/frontend/src/components/RouteBuilder.jsx
// ("Plan Route" tab content). Same adaptation as ShelterSearch.jsx: our
// AddressSearch.onSelect gives {lon, lat, label} instead of
// {latitude, longitude, address} — translated at the call site below.
// onCalculateRoute keeps the original's {start:{latitude,longitude},
// end:{latitude,longitude}} shape; App.jsx converts that into the
// {lon, lat} pairs our own api.routeBetweenPoints expects.

const RouteBuilder = ({ onCalculateRoute, loading, onClear, onSetMapClickMode, clickedPoints, onRoutePointSet }) => {
  const [startAddress, setStartAddress] = useState('');
  const [endAddress, setEndAddress] = useState('');
  const [startCoords, setStartCoords] = useState(null);
  const [endCoords, setEndCoords] = useState(null);
  const [editingStart, setEditingStart] = useState(false);
  const [editingEnd, setEditingEnd] = useState(false);
  const [loadingStartLocation, setLoadingStartLocation] = useState(false);
  const [loadingEndLocation, setLoadingEndLocation] = useState(false);

  const formatAddress = (fullAddress) => {
    if (!fullAddress) return '';
    if (fullAddress === 'Your location' || fullAddress === 'Selected from map') {
      return fullAddress;
    }

    const parts = fullAddress.split(',').map((p) => p.trim());
    if (parts.length >= 2) {
      return `${parts[0]}, ${parts[1]}`;
    }
    return parts[0] || fullAddress;
  };

  useEffect(() => {
    if (clickedPoints.start) {
      setStartCoords(clickedPoints.start);
      setStartAddress('Selected from map');
      setEditingStart(false);
    }
  }, [clickedPoints.start]);

  useEffect(() => {
    if (clickedPoints.end) {
      setEndCoords(clickedPoints.end);
      setEndAddress('Selected from map');
      setEditingEnd(false);
    }
  }, [clickedPoints.end]);

  const handleUseMyLocationStart = () => {
    if (navigator.geolocation) {
      setLoadingStartLocation(true);
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const coords = { latitude: position.coords.latitude, longitude: position.coords.longitude };
          setStartCoords(coords);
          setStartAddress('Your location');
          setEditingStart(false);
          setLoadingStartLocation(false);
          if (onRoutePointSet) onRoutePointSet('start', coords);
        },
        (error) => {
          console.error('Geolocation error:', error);
          alert('Could not get your location');
          setLoadingStartLocation(false);
        },
        { enableHighAccuracy: false, timeout: 2000, maximumAge: 60000 }
      );
    }
  };

  const handleUseMyLocationEnd = () => {
    if (navigator.geolocation) {
      setLoadingEndLocation(true);
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const coords = { latitude: position.coords.latitude, longitude: position.coords.longitude };
          setEndCoords(coords);
          setEndAddress('Your location');
          setEditingEnd(false);
          setLoadingEndLocation(false);
          if (onRoutePointSet) onRoutePointSet('end', coords);
        },
        (error) => {
          console.error('Geolocation error:', error);
          alert('Could not get your location');
          setLoadingEndLocation(false);
        },
        { enableHighAccuracy: false, timeout: 2000, maximumAge: 60000 }
      );
    }
  };

  const handleCalculate = () => {
    if (!startCoords || !endCoords) {
      alert('Please select both start and end points');
      return;
    }
    onCalculateRoute({ start: startCoords, end: endCoords });
  };

  const handleClear = () => {
    setStartAddress('');
    setEndAddress('');
    setStartCoords(null);
    setEndCoords(null);
    setEditingStart(false);
    setEditingEnd(false);
    if (onClear) onClear();
  };

  return (
    <div className="route-builder">
      <h2>🗺️ Plan Route</h2>

      {/* Start Point */}
      <div className="route-point">
        <div className="point-indicator start">●</div>
        <div className="point-content">
          {startAddress && !editingStart ? (
            <div className="address-display">
              <input
                type="text"
                value={formatAddress(startAddress)}
                readOnly
                className="location-input location-input--filled"
                title={startAddress}
              />
              <button
                onClick={() => {
                  setStartAddress('');
                  setStartCoords(null);
                  setEditingStart(true);
                }}
                className="btn-clear-input"
                title="Clear"
              >
                ✕
              </button>
            </div>
          ) : (
            <AddressSearch
              onSelect={(result) => {
                if (!result) return;
                const coords = { latitude: result.lat, longitude: result.lon };
                setStartAddress(result.label);
                setStartCoords(coords);
                setEditingStart(false);
                if (onRoutePointSet) onRoutePointSet('start', coords);
              }}
              placeholder="Start point"
            />
          )}
          <button onClick={handleUseMyLocationStart} className="btn-icon" title="Use my location" disabled={loadingStartLocation}>
            {loadingStartLocation ? '⏳' : '📍'}
          </button>
          <button onClick={() => onSetMapClickMode && onSetMapClickMode('start')} className="btn-icon" title="Select start on map">
            🗺️
          </button>
        </div>
      </div>

      {/* End Point */}
      <div className="route-point">
        <div className="point-indicator end">●</div>
        <div className="point-content">
          {endAddress && !editingEnd ? (
            <div className="address-display">
              <input
                type="text"
                value={formatAddress(endAddress)}
                readOnly
                className="location-input location-input--filled"
                title={endAddress}
              />
              <button
                onClick={() => {
                  setEndAddress('');
                  setEndCoords(null);
                  setEditingEnd(true);
                }}
                className="btn-clear-input"
                title="Clear"
              >
                ✕
              </button>
            </div>
          ) : (
            <AddressSearch
              onSelect={(result) => {
                if (!result) return;
                const coords = { latitude: result.lat, longitude: result.lon };
                setEndAddress(result.label);
                setEndCoords(coords);
                setEditingEnd(false);
                if (onRoutePointSet) onRoutePointSet('end', coords);
              }}
              placeholder="Choose destination"
            />
          )}
          <button
            onClick={handleUseMyLocationEnd}
            className="btn-icon"
            title="Use my location as destination"
            disabled={loadingEndLocation}
          >
            {loadingEndLocation ? '⏳' : '📍'}
          </button>
          <button onClick={() => onSetMapClickMode && onSetMapClickMode('end')} className="btn-icon" title="Select destination on map">
            🗺️
          </button>
        </div>
      </div>

      {/* Action Buttons */}
      <div className="route-actions">
        <button onClick={handleCalculate} disabled={!startCoords || !endCoords || loading} className="btn-calculate">
          {loading ? '⏳ Calculating...' : '🚀 Calculate Route'}
        </button>

        {(startCoords || endCoords) && (
          <button onClick={handleClear} className="btn-clear-simple">
            Clear All
          </button>
        )}
      </div>
    </div>
  );
};

export default RouteBuilder;
