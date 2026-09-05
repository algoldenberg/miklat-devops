import { useState, useEffect } from 'react';
import CommentsSection from './CommentsSection';
import PhotosSection from './PhotosSection';

// Ported from shelter-route-planner/frontend/src/components/ShelterPopup.jsx.
// Necessary adaptations (see App.jsx header note for the full list):
//   - shelter.id/lat/lon/address instead of shelter._id/latitude/longitude/street.
//   - shelter.distance_to_route_m (perpendicular distance from the route,
//     computed by miklat-walking-routes' PostGIS query) instead of the
//     original's distance_from_start (distance travelled along the route) —
//     these are genuinely different measurements, so the label says
//     "From route" rather than "From start".
//   - The combined comment+photo form and the comment-photo gallery are
//     replaced by our existing, separately-moderated CommentsSection +
//     PhotosSection components (our backend doesn't support attaching a
//     photo directly to a comment — photos go through their own moderation
//     queue). Everything else — header, info block, the three action
//     buttons — is unchanged.

const ShelterPopup = ({ shelter, onBuildRoute, currentLocation, onReportClick }) => {
  const [distance, setDistance] = useState(null);

  useEffect(() => {
    calculateDistance();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [shelter]);

  const calculateDistance = () => {
    if (currentLocation) {
      const R = 6371;
      const dLat = ((shelter.lat - currentLocation[0]) * Math.PI) / 180;
      const dLon = ((shelter.lon - currentLocation[1]) * Math.PI) / 180;
      const a =
        Math.sin(dLat / 2) * Math.sin(dLat / 2) +
        Math.cos((currentLocation[0] * Math.PI) / 180) *
          Math.cos((shelter.lat * Math.PI) / 180) *
          Math.sin(dLon / 2) *
          Math.sin(dLon / 2);
      const c = 2 * Math.atan2(Math.sqrt(a), Math.sqrt(1 - a));
      setDistance(R * c);
    }
  };

  const handleTouchButton = (callback) => (e) => {
    e.preventDefault();
    e.stopPropagation();
    callback();
  };

  return (
    <div className="shelter-popup">
      <div className="shelter-popup__header">
        <h3 className="shelter-popup__title">🛡️ {shelter.name || 'Unnamed Shelter'}</h3>
      </div>

      <div className="shelter-popup__info">
        {shelter.address && (
          <p className="info-item">
            <span className="icon">📍</span>
            {shelter.address}
            {shelter.city ? `, ${shelter.city}` : ''}
          </p>
        )}

        <p className="info-item">
          <span className="icon">🏷️</span>
          <strong>Type:</strong> {(shelter.type || 'public_shelter').replace('_', ' ')}
        </p>
        {distance !== null && (
          <p className="info-item">
            <span className="icon">📏</span>
            <strong>Distance:</strong> {distance < 1 ? `${(distance * 1000).toFixed(0)}m` : `${distance.toFixed(2)}km`}
          </p>
        )}

        {shelter.distance_to_route_m !== undefined && (
          <p className="info-item">
            <span className="icon">🚶</span>
            <strong>From route:</strong> {Math.round(shelter.distance_to_route_m)}m
          </p>
        )}

        <p className="info-item">
          <span className="icon">📐</span>
          <strong>Coordinates:</strong> {shelter.lat.toFixed(6)}, {shelter.lon.toFixed(6)}
        </p>
      </div>

      <div className="shelter-popup__actions">
        <button
          className="btn btn--primary"
          onClick={(e) => {
            e.stopPropagation();
            if (onBuildRoute) onBuildRoute(shelter.lat, shelter.lon);
          }}
          onTouchEnd={handleTouchButton(() => {
            if (onBuildRoute) onBuildRoute(shelter.lat, shelter.lon);
          })}
        >
          🗺️ Build Route Here
        </button>

        <button
          className="btn btn--secondary"
          onClick={(e) => {
            e.stopPropagation();
            const url = `https://www.google.com/maps/dir/?api=1&destination=${shelter.lat},${shelter.lon}`;
            window.open(url, '_blank');
          }}
          onTouchEnd={handleTouchButton(() => {
            const url = `https://www.google.com/maps/dir/?api=1&destination=${shelter.lat},${shelter.lon}`;
            window.open(url, '_blank');
          })}
        >
          📍 Open in Google Maps
        </button>

        <button
          className="btn btn--report"
          onClick={(e) => {
            e.stopPropagation();
            if (onReportClick) onReportClick();
          }}
          onTouchEnd={handleTouchButton(() => {
            if (onReportClick) onReportClick();
          })}
        >
          🚫 Report Issue
        </button>
      </div>

      <div className="shelter-popup__comments" onClick={(e) => e.stopPropagation()}>
        <CommentsSection miklatId={shelter.id} />
        <PhotosSection miklatId={shelter.id} />
      </div>
    </div>
  );
};

export default ShelterPopup;
