import { MapContainer, TileLayer, Marker, Popup, Polyline, useMap, useMapEvents, Circle } from 'react-leaflet';
import { useEffect, useState } from 'react';
import 'leaflet/dist/leaflet.css';
import L from 'leaflet';
import ShelterPopup from './ShelterPopup';
import BottomSheet from './BottomSheet';
import LocationInfo from './LocationInfo';
import AddShelterButton from './AddShelterButton';
import AddShelterModal from './AddShelterModal';
import ReportModal from './ReportModal';
import { api } from '../api';
import { routeStartIcon, routeEndIcon, searchCenterIcon } from '../utils/mapIcons';

// Ported from shelter-route-planner/frontend/src/components/Map.jsx. Field
// names adapted throughout to our own data shape (m.lon/m.lat/m.id instead
// of shelter.longitude/latitude/_id, addressRoute.{geometry,miklats,from,to}
// instead of routeData.{geometry,shelters,start,end}) — see the note at the
// top of App.jsx for the full list of places this port had to adapt to our
// backend instead of being a byte-for-byte copy.

delete L.Icon.Default.prototype._getIconUrl;
L.Icon.Default.mergeOptions({
  iconRetinaUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon-2x.png',
  iconUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-icon.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
});

// Shelter type marker icons with colors (same leaflet-color-markers set as
// the original; extended to cover our actual `type` values, which differ
// from the original's — verified against the real seed data
// (db/seed/miklats_seed.json): public_shelter (12419), school_shelter (101),
// parking_storage (94), parking_shelter (16), migunit (9),
// private_building (1). Everything else falls back to `default`/grey.
const shelterIcons = {
  public_shelter: new L.Icon({
    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
    iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34], shadowSize: [41, 41],
  }),
  school_shelter: new L.Icon({
    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
    iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34], shadowSize: [41, 41],
  }),
  parking_storage: new L.Icon({
    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-orange.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
    iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34], shadowSize: [41, 41],
  }),
  parking_shelter: new L.Icon({
    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-yellow.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
    iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34], shadowSize: [41, 41],
  }),
  migunit: new L.Icon({
    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-violet.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
    iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34], shadowSize: [41, 41],
  }),
  private_building: new L.Icon({
    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-black.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
    iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34], shadowSize: [41, 41],
  }),
  default: new L.Icon({
    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-grey.png',
    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
    iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34], shadowSize: [41, 41],
  }),
};

const getShelterIcon = (type) => shelterIcons[type] || shelterIcons.default;

const startIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-green.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
  iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34], shadowSize: [41, 41],
});

const endIcon = new L.Icon({
  iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png',
  shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/1.7.1/images/marker-shadow.png',
  iconSize: [25, 41], iconAnchor: [12, 41], popupAnchor: [1, -34], shadowSize: [41, 41],
});

function MapClickHandler({ onMapClick, mapClickMode }) {
  useMapEvents({
    click: (e) => {
      if (mapClickMode && onMapClick) {
        onMapClick(e.latlng.lat, e.latlng.lng, mapClickMode);
      }
    },
  });
  return null;
}

function MapMoveHandler({ onMapMove }) {
  const map = useMap();

  useEffect(() => {
    const handleMoveEnd = () => {
      const newCenter = map.getCenter();
      if (onMapMove) onMapMove([newCenter.lat, newCenter.lng]);
    };
    map.on('moveend', handleMoveEnd);
    return () => map.off('moveend', handleMoveEnd);
  }, [map, onMapMove]);

  return null;
}

function ChangeView({ center, zoom, routeGeometry }) {
  const map = useMap();

  useEffect(() => {
    if (routeGeometry && routeGeometry.length > 0) {
      const bounds = L.latLngBounds(routeGeometry.map((coord) => [coord[1], coord[0]]));
      map.fitBounds(bounds, { padding: [100, 100] });
    } else if (center) {
      map.setView(center, zoom);
    }
  }, [routeGeometry, map, center, zoom]);

  return null;
}

function SaveMapInstance({ onMapReady }) {
  const map = useMap();
  useEffect(() => {
    onMapReady(map);
  }, [map, onMapReady]);
  return null;
}

// Live GPS location tracker with manual map movement detection ("follow
// mode"). Ported as-is — pure browser geolocation + Leaflet, no dependency
// on our backend's data shape.
function LocationTracker({ followMode, onLocationUpdate, onFollowModeChange }) {
  const [position, setPosition] = useState(null);
  const [heading, setHeading] = useState(null);
  const [accuracy, setAccuracy] = useState(null);
  const [isUserDragging, setIsUserDragging] = useState(false);
  const map = useMap();

  useEffect(() => {
    if (!followMode) return;

    const handleDragStart = () => {
      setIsUserDragging(true);
      onFollowModeChange(false);
    };
    const handleDragEnd = () => setIsUserDragging(false);

    map.on('dragstart', handleDragStart);
    map.on('dragend', handleDragEnd);
    return () => {
      map.off('dragstart', handleDragStart);
      map.off('dragend', handleDragEnd);
    };
  }, [followMode, map, onFollowModeChange]);

  useEffect(() => {
    if (!navigator.geolocation) {
      console.warn('Geolocation is not supported');
      return;
    }

    navigator.geolocation.getCurrentPosition(
      (pos) => {
        const newPos = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        setPosition(newPos);
        setAccuracy(pos.coords.accuracy);
        onLocationUpdate?.(newPos);
      },
      null,
      { enableHighAccuracy: false, timeout: 1000, maximumAge: 60000 }
    );

    const watchId = navigator.geolocation.watchPosition(
      (pos) => {
        const newPos = { lat: pos.coords.latitude, lng: pos.coords.longitude };
        setPosition(newPos);
        setAccuracy(pos.coords.accuracy);

        if (pos.coords.heading !== null && pos.coords.heading >= 0) {
          setHeading(pos.coords.heading);
        }

        if (followMode && !isUserDragging) {
          map.setView([newPos.lat, newPos.lng], map.getZoom(), { animate: true, duration: 0.5 });
        }

        onLocationUpdate?.(newPos);
      },
      (error) => console.error('Geolocation error:', error),
      { enableHighAccuracy: true, maximumAge: 0, timeout: 10000 }
    );

    return () => navigator.geolocation.clearWatch(watchId);
  }, [followMode, map, onLocationUpdate, isUserDragging]);

  if (!position) return null;

  const locationIcon = L.divIcon({
    html:
      heading !== null && heading >= 0
        ? `<div style="width:20px;height:20px;background:#4285F4;border:3px solid white;border-radius:50%;box-shadow:0 2px 8px rgba(0,0,0,0.3);position:relative;">
            <div style="position:absolute;top:-15px;left:50%;transform:translateX(-50%) rotate(${heading}deg);width:0;height:0;border-left:6px solid transparent;border-right:6px solid transparent;border-bottom:12px solid #4285F4;"></div>
          </div>`
        : `<div style="width:20px;height:20px;background:#4285F4;border:3px solid white;border-radius:50%;box-shadow:0 2px 8px rgba(0,0,0,0.3);"></div>`,
    className: '',
    iconSize: [20, 20],
    iconAnchor: [10, 10],
  });

  return (
    <>
      {accuracy && (
        <Circle
          center={position}
          radius={accuracy}
          pathOptions={{ color: '#4285F4', fillColor: '#4285F4', fillOpacity: 0.1, weight: 1 }}
        />
      )}
      <Marker position={position} icon={locationIcon} zIndexOffset={1000} />
    </>
  );
}

const Map = ({
  center = [32.0853, 34.7818],
  zoom = 13,
  shelters = [],
  onMarkerClick,
  routeData = null,
  onMapClick = null,
  mapClickMode = null,
  onBuildRouteToShelter = null,
  onMapMove = null,
  onFollowModeEnabled = null,
  activeTab = 'shelters',
  clearSearchTrigger = 0,
  clickedSearchPoint = null,
  clickedPoints = { start: null, end: null },
  onShelterAdded = null,
}) => {
  const [selectedShelter, setSelectedShelter] = useState(null);
  const [isMobile, setIsMobile] = useState(window.innerWidth <= 768);
  const [followMode, setFollowMode] = useState(false);
  const [currentPosition, setCurrentPosition] = useState(null);
  const [mapInstance, setMapInstance] = useState(null);
  const [showAddShelterModal, setShowAddShelterModal] = useState(false);
  const [isPickingLocation, setIsPickingLocation] = useState(false);
  const [pickedLocation, setPickedLocation] = useState(null);
  const [showReportModal, setShowReportModal] = useState(false);
  const [reportingShelter, setReportingShelter] = useState(null);
  const [buildingRouteFromPopup, setBuildingRouteFromPopup] = useState(false);

  const [routeStartMarker, setRouteStartMarker] = useState(null);
  const [routeEndMarker, setRouteEndMarker] = useState(null);

  const [searchCenterMarker, setSearchCenterMarker] = useState(null);
  const searchRadius = 1000; // fixed, same as the original (no radius slider there either)

  useEffect(() => {
    if (!routeData) {
      setRouteStartMarker(null);
      setRouteEndMarker(null);
    }
  }, [routeData]);

  useEffect(() => {
    if (!clickedPoints.start && !clickedPoints.end) {
      setRouteStartMarker(null);
      setRouteEndMarker(null);
    }
  }, [clickedPoints.start, clickedPoints.end]);

  useEffect(() => {
    if (activeTab === 'route') setSearchCenterMarker(null);
  }, [activeTab]);

  useEffect(() => {
    if (clearSearchTrigger > 0) setSearchCenterMarker(null);
  }, [clearSearchTrigger]);

  useEffect(() => {
    if (clickedSearchPoint) setSearchCenterMarker(clickedSearchPoint);
  }, [clickedSearchPoint]);

  useEffect(() => {
    if (clickedPoints.start) setRouteStartMarker(clickedPoints.start);
  }, [clickedPoints.start]);

  useEffect(() => {
    if (clickedPoints.end) setRouteEndMarker(clickedPoints.end);
  }, [clickedPoints.end]);

  useEffect(() => {
    const handleResize = () => setIsMobile(window.innerWidth <= 768);
    window.addEventListener('resize', handleResize);
    return () => window.removeEventListener('resize', handleResize);
  }, []);

  // Our geometry is a GeoJSON LineString ({type, coordinates: [[lon,lat],...]}),
  // not a plain coordinate array like the original's routeData.geometry.
  const routeCoordinates = routeData?.geometry?.coordinates
    ? routeData.geometry.coordinates.map((coord) => [coord[1], coord[0]])
    : null;

  const handleFollowModeToggle = () => {
    const newMode = !followMode;
    setFollowMode(newMode);

    if (newMode && currentPosition && mapInstance) {
      mapInstance.setView([currentPosition.lat, currentPosition.lng], mapInstance.getZoom(), {
        animate: true,
        duration: 0.5,
      });

      if (onFollowModeEnabled && currentPosition) {
        onFollowModeEnabled({ latitude: currentPosition.lat, longitude: currentPosition.lng });
      }
    }
  };

  const handleMapClickInternal = (lat, lng, mode) => {
    if (isPickingLocation) {
      setPickedLocation({ latitude: lat, longitude: lng });
      setIsPickingLocation(false);
      setShowAddShelterModal(true);
      return;
    }

    if (mapClickMode === 'start') {
      setRouteStartMarker({ latitude: lat, longitude: lng });
      onMapClick?.(lat, lng, 'start');
      return;
    }

    if (mapClickMode === 'end') {
      setRouteEndMarker({ latitude: lat, longitude: lng });
      onMapClick?.(lat, lng, 'end');
      return;
    }

    if (mapClickMode === 'search') {
      setSearchCenterMarker({ latitude: lat, longitude: lng });
      onMapClick?.(lat, lng, 'search');
      return;
    }

    onMapClick?.(lat, lng, mode);
  };

  const handleAddShelterSubmit = async (formData) => {
    try {
      await api.createSubmission({
        name: formData.name || undefined,
        address: formData.address || undefined,
        lon: parseFloat(formData.longitude),
        lat: parseFloat(formData.latitude),
        type: formData.type,
        capacity: formData.capacity ? parseInt(formData.capacity, 10) : undefined,
        comment: formData.comment || undefined,
      });

      setShowAddShelterModal(false);
      setPickedLocation(null);
      alert('✅ Thank you! Your shelter suggestion has been submitted for review.');
      onShelterAdded?.();
    } catch (error) {
      console.error('Failed to submit shelter:', error);
      alert('❌ Failed to submit shelter. Please try again.');
    }
  };

  const handlePickOnMap = (enabled) => {
    setIsPickingLocation(enabled);
    setShowAddShelterModal(false);
  };

  const handleReportClick = (shelter) => {
    if (isMobile && selectedShelter) setSelectedShelter(null);
    setReportingShelter(shelter);
    setShowReportModal(true);
  };

  const handleReportSubmit = async (reportData) => {
    try {
      await api.createReport(reportingShelter.id, {
        issue_type: reportData.issueType,
        comment: reportData.comment,
        contact: reportData.contact || undefined,
      });
      setShowReportModal(false);
      setReportingShelter(null);
      alert('✅ Thank you for reporting this issue! We will review it soon.');
    } catch (error) {
      console.error('Failed to submit report:', error);
      alert('❌ Failed to submit report. Please try again.');
    }
  };

  return (
    <>
      <MapContainer
        center={center}
        zoom={zoom}
        style={{
          height: '100%',
          width: '100%',
          cursor: isPickingLocation ? 'crosshair' : mapClickMode ? 'crosshair' : 'grab',
        }}
        scrollWheelZoom={true}
      >
        <ChangeView center={center} zoom={zoom} routeGeometry={routeData?.geometry?.coordinates} />
        <SaveMapInstance onMapReady={setMapInstance} />
        <MapClickHandler
          onMapClick={handleMapClickInternal}
          mapClickMode={mapClickMode || (isPickingLocation ? 'pick' : null)}
        />
        <MapMoveHandler onMapMove={onMapMove} />

        <TileLayer
          attribution='&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
          url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png"
        />

        {(mapClickMode || isPickingLocation) && (
          <div
            style={{
              position: 'absolute',
              top: '10px',
              left: '50%',
              transform: 'translateX(-50%)',
              zIndex: 1000,
              background: isPickingLocation
                ? '#667eea'
                : mapClickMode === 'start'
                ? '#4CAF50'
                : mapClickMode === 'end'
                ? '#f44336'
                : '#10b981',
              color: 'white',
              padding: '10px 20px',
              borderRadius: '8px',
              fontWeight: 'bold',
              boxShadow: '0 2px 8px rgba(0,0,0,0.3)',
              pointerEvents: 'none',
            }}
          >
            {isPickingLocation
              ? '📍 Click on map to select shelter location'
              : mapClickMode === 'start'
              ? '📍 Click map to set START point'
              : mapClickMode === 'end'
              ? '🎯 Click map to set END point'
              : '🔍 Click map to set SEARCH center'}
          </div>
        )}

        {!routeData && routeStartMarker && (
          <Marker position={[routeStartMarker.latitude, routeStartMarker.longitude]} icon={routeStartIcon} zIndexOffset={500}>
            <Popup>
              <div>
                <strong>🟢 Start Point</strong>
                <p>Lat: {routeStartMarker.latitude.toFixed(6)}</p>
                <p>Lon: {routeStartMarker.longitude.toFixed(6)}</p>
              </div>
            </Popup>
          </Marker>
        )}

        {!routeData && routeEndMarker && (
          <Marker position={[routeEndMarker.latitude, routeEndMarker.longitude]} icon={routeEndIcon} zIndexOffset={500}>
            <Popup>
              <div>
                <strong>🔴 End Point</strong>
                <p>Lat: {routeEndMarker.latitude.toFixed(6)}</p>
                <p>Lon: {routeEndMarker.longitude.toFixed(6)}</p>
              </div>
            </Popup>
          </Marker>
        )}

        {!routeData && searchCenterMarker && (
          <>
            <Circle
              center={[searchCenterMarker.latitude, searchCenterMarker.longitude]}
              radius={searchRadius}
              pathOptions={{ color: '#10b981', fillColor: '#10b981', fillOpacity: 0.08, weight: 2, dashArray: '8, 4' }}
            />
            <Marker position={[searchCenterMarker.latitude, searchCenterMarker.longitude]} icon={searchCenterIcon} zIndexOffset={500}>
              <Popup>
                <div>
                  <strong>🔍 Search Center</strong>
                  <p>Lat: {searchCenterMarker.latitude.toFixed(6)}</p>
                  <p>Lon: {searchCenterMarker.longitude.toFixed(6)}</p>
                  <p>Radius: {searchRadius}m</p>
                </div>
              </Popup>
            </Marker>
          </>
        )}

        {!routeData &&
          shelters.map((shelter) => {
            if (shelter.lat == null || shelter.lon == null) return null;
            const markerIcon = getShelterIcon(shelter.type || 'default');

            return (
              <Marker
                key={shelter.id}
                position={[shelter.lat, shelter.lon]}
                icon={markerIcon}
                eventHandlers={{
                  click: () => {
                    if (isMobile) setSelectedShelter(shelter);
                  },
                }}
              >
                {!isMobile && !buildingRouteFromPopup && (
                  <Popup maxWidth={350} minWidth={280}>
                    <ShelterPopup
                      shelter={shelter}
                      onBuildRoute={(lat, lng) => {
                        setBuildingRouteFromPopup(true);
                        onBuildRouteToShelter(lat, lng);
                        setTimeout(() => setBuildingRouteFromPopup(false), 500);
                      }}
                      currentLocation={center}
                      onReportClick={() => handleReportClick(shelter)}
                    />
                  </Popup>
                )}
              </Marker>
            );
          })}

        {routeData && (
          <>
            {routeCoordinates && <Polyline positions={routeCoordinates} color="#2196F3" weight={5} opacity={0.7} />}

            {routeData.from && (
              <Marker position={[routeData.from.lat, routeData.from.lon]} icon={startIcon}>
                <Popup>
                  <div>
                    <strong>🟢 Start Point</strong>
                    <p>Lat: {routeData.from.lat.toFixed(6)}</p>
                    <p>Lon: {routeData.from.lon.toFixed(6)}</p>
                  </div>
                </Popup>
              </Marker>
            )}

            {routeData.to && (
              <Marker position={[routeData.to.lat, routeData.to.lon]} icon={endIcon}>
                <Popup>
                  <div>
                    <strong>🔴 End Point</strong>
                    <p>Lat: {routeData.to.lat.toFixed(6)}</p>
                    <p>Lon: {routeData.to.lon.toFixed(6)}</p>
                  </div>
                </Popup>
              </Marker>
            )}

            {routeData.miklats &&
              routeData.miklats.map((shelter) => {
                const markerIcon = getShelterIcon(shelter.type || 'default');
                return (
                  <Marker
                    key={shelter.id}
                    position={[shelter.lat, shelter.lon]}
                    icon={markerIcon}
                    eventHandlers={{
                      click: () => {
                        if (isMobile) setSelectedShelter(shelter);
                        else onMarkerClick?.(shelter);
                      },
                    }}
                  >
                    {!isMobile && (
                      <Popup maxWidth={350} minWidth={280}>
                        <ShelterPopup
                          shelter={shelter}
                          onBuildRoute={onBuildRouteToShelter}
                          currentLocation={center}
                          onReportClick={() => handleReportClick(shelter)}
                        />
                      </Popup>
                    )}
                  </Marker>
                );
              })}
          </>
        )}

        <LocationTracker followMode={followMode} onLocationUpdate={setCurrentPosition} onFollowModeChange={setFollowMode} />
      </MapContainer>

      <button
        onClick={handleFollowModeToggle}
        className={`follow-mode-btn ${followMode ? 'follow-mode-btn--active' : ''}`}
        title={followMode ? 'Disable follow mode' : 'Enable follow mode'}
      >
        {followMode ? '📍' : '🧭'}
      </button>

      <AddShelterButton onClick={() => setShowAddShelterModal(true)} />

      {(currentPosition || center) && (
        <LocationInfo
          currentPosition={currentPosition}
          shelters={shelters}
          destination={routeData?.to}
          searchCenter={!routeData ? center : null}
          showDestination={activeTab === 'route' && !!routeData}
          onShelterClick={(shelter) => {
            if (isMobile) {
              setSelectedShelter(shelter);
            } else if (mapInstance) {
              mapInstance.setView([shelter.lat, shelter.lon], mapInstance.getZoom(), { animate: true, duration: 0.5 });
              setTimeout(() => {
                mapInstance.eachLayer((layer) => {
                  if (layer instanceof L.Marker) {
                    const pos = layer.getLatLng();
                    if (Math.abs(pos.lat - shelter.lat) < 0.00001 && Math.abs(pos.lng - shelter.lon) < 0.00001) {
                      layer.openPopup();
                    }
                  }
                });
              }, 600);
            }
          }}
        />
      )}

      {isMobile && selectedShelter && (
        <BottomSheet
          shelter={selectedShelter}
          onClose={() => setSelectedShelter(null)}
          onBuildRoute={onBuildRouteToShelter}
          currentLocation={center}
          onReportClick={() => handleReportClick(selectedShelter)}
        />
      )}

      <AddShelterModal
        isOpen={showAddShelterModal}
        onClose={() => {
          setShowAddShelterModal(false);
          setIsPickingLocation(false);
          setPickedLocation(null);
        }}
        onSubmit={handleAddShelterSubmit}
        onPickOnMap={handlePickOnMap}
        isPickingLocation={isPickingLocation}
        pickedLocation={pickedLocation}
      />

      <ReportModal
        isOpen={showReportModal}
        onClose={() => {
          setShowReportModal(false);
          setReportingShelter(null);
        }}
        onSubmit={handleReportSubmit}
        shelterName={reportingShelter?.name || 'Unnamed Shelter'}
      />
    </>
  );
};

export default Map;
