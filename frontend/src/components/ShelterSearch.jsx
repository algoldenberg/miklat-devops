import { useState, useEffect } from 'react';
import AddressSearch from './AddressSearch';

// Ported from shelter-route-planner/frontend/src/components/ShelterSearch.jsx
// ("Find Shelters" tab content). Necessary adaptations:
//   - Uses our own AddressSearch component, whose onSelect gives
//     {lon, lat, label} (or null on clear) instead of the original's
//     {latitude, longitude, address} — the callback below translates that
//     into the {latitude, longitude, radius} shape the rest of this
//     component (and App.jsx's onSearch) already uses, so no other logic
//     needed to change.
// Radius is still a fixed 1000m constant, exactly like the original (it
// really is hardcoded there — not user-adjustable).

const ShelterSearch = ({
  onSearch,
  loading,
  currentLocation,
  showSearchHere,
  onSearchHere,
  onSetMapClickMode,
  clickedSearchPoint,
  onClearSearchMarker,
  onSearchLocationSet,
}) => {
  const [searchAddress, setSearchAddress] = useState('');
  const [searchCoords, setSearchCoords] = useState(null);
  const [editingLocation, setEditingLocation] = useState(false);

  const formatAddress = (fullAddress) => {
    if (!fullAddress) return '';
    if (fullAddress === 'Your location' || fullAddress === 'Current location' || fullAddress === 'Selected from map') {
      return fullAddress;
    }

    const parts = fullAddress.split(',').map((p) => p.trim());
    if (parts.length >= 2) {
      return `${parts[0]}, ${parts[1]}`;
    }
    return parts[0] || fullAddress;
  };

  // Update from clicked search point
  useEffect(() => {
    if (clickedSearchPoint) {
      setSearchCoords(clickedSearchPoint);
      setSearchAddress('Selected from map');
      setEditingLocation(false);
    }
  }, [clickedSearchPoint]);

  const handleSearch = () => {
    if (!searchCoords) {
      alert('Please select a location');
      return;
    }

    onSearch({
      latitude: searchCoords.latitude,
      longitude: searchCoords.longitude,
      radius: 1000, // Fixed radius
    });

    if (onSearchLocationSet) {
      onSearchLocationSet(searchCoords);
    }
  };

  const handleUseMyLocation = () => {
    if (navigator.geolocation) {
      navigator.geolocation.getCurrentPosition(
        (position) => {
          const coords = {
            latitude: position.coords.latitude,
            longitude: position.coords.longitude,
          };
          setSearchCoords(coords);
          setSearchAddress('Your location');
          setEditingLocation(false);

          onSearch({ latitude: coords.latitude, longitude: coords.longitude, radius: 1000 });
        },
        (error) => {
          console.error('Geolocation error:', error);
          alert('Could not get your location');
        },
        { enableHighAccuracy: false, timeout: 2000, maximumAge: 60000 }
      );
    }
  };

  const handleClear = () => {
    setSearchAddress('');
    setSearchCoords(null);
    setEditingLocation(true);

    if (onClearSearchMarker) onClearSearchMarker();
  };

  // Set initial location from currentLocation prop
  useEffect(() => {
    if (currentLocation && !searchCoords) {
      setSearchCoords({ latitude: currentLocation[0], longitude: currentLocation[1] });
      setSearchAddress('Current location');
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [currentLocation]);

  return (
    <div className="shelter-search">
      <h2>🔍 Find Nearby Shelters</h2>

      <div className="search-location">
        <label>Location:</label>
        <div className="location-input-group">
          {searchAddress && !editingLocation ? (
            <div className="address-display">
              <input
                type="text"
                value={formatAddress(searchAddress)}
                readOnly
                className="location-input location-input--filled"
                onClick={() => setEditingLocation(true)}
                title={searchAddress}
                style={{ cursor: 'pointer' }}
              />
              <button onClick={handleClear} className="btn-clear-text" title="Clear">
                Clear
              </button>
            </div>
          ) : (
            <AddressSearch
              onSelect={(result) => {
                if (!result) return;
                const coords = { latitude: result.lat, longitude: result.lon };
                setSearchAddress(result.label);
                setSearchCoords(coords);
                setEditingLocation(false);

                if (onSearchLocationSet) onSearchLocationSet(coords);
              }}
              placeholder="Enter address or place"
            />
          )}
          <button onClick={handleUseMyLocation} className="btn-icon" title="Use my location">
            📍
          </button>
          <button
            onClick={() => onSetMapClickMode && onSetMapClickMode('search')}
            className="btn-icon"
            title="Select search location on map"
          >
            🗺️
          </button>
        </div>
      </div>

      <div className="search-actions">
        <button onClick={handleSearch} disabled={!searchCoords || loading} className="btn-search">
          {loading ? '⏳ Searching...' : '🔍 Search Shelters'}
        </button>

        {showSearchHere && (
          <button onClick={onSearchHere} className="btn-search-here">
            📍 Search Here
          </button>
        )}
      </div>
    </div>
  );
};

export default ShelterSearch;
