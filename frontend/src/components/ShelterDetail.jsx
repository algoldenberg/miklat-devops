import { useState } from 'react';
import CommentsSection from './CommentsSection';
import PhotosSection from './PhotosSection';
import ReportForm from './ReportForm';
import RoutePanel from './RoutePanel';

export default function ShelterDetail({ miklat, userLocation, onBuildRoute, route, routeLoading, routeError, onClearRoute }) {
  const [showReportForm, setShowReportForm] = useState(false);

  if (!miklat) {
    return (
      <div className="detail-panel empty">
        <p className="muted">Select a shelter on the map or in the list.</p>
      </div>
    );
  }

  return (
    <div className="detail-panel">
      <h2>{miklat.name || 'Unnamed shelter'}</h2>
      <p className="muted">
        {miklat.address || '—'}
        {miklat.city ? `, ${miklat.city}` : ''}
      </p>
      <div className="detail-facts">
        <span className="badge">{miklat.type}</span>
        {miklat.capacity != null && <span className="badge">up to {miklat.capacity} people</span>}
        <span className="badge">{miklat.accessible ? 'wheelchair accessible' : 'not wheelchair accessible'}</span>
        {miklat.is_verified && <span className="badge verified">verified</span>}
      </div>
      {miklat.description && <p>{miklat.description}</p>}

      <div className="detail-actions">
        <button onClick={() => onBuildRoute(miklat.id)} disabled={!userLocation}>
          Walking route from here
        </button>
        <button className="secondary" onClick={() => setShowReportForm(true)}>
          Report an issue
        </button>
      </div>
      {!userLocation && <p className="muted small">Allow location access or search an address to build a route.</p>}

      <RoutePanel route={route} loading={routeLoading} error={routeError} onClear={onClearRoute} />

      <CommentsSection miklatId={miklat.id} />
      <PhotosSection miklatId={miklat.id} />

      {showReportForm && <ReportForm miklatId={miklat.id} onClose={() => setShowReportForm(false)} />}
    </div>
  );
}
