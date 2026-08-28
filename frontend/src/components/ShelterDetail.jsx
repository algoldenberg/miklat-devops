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
        <p className="muted">Выберите укрытие на карте или в списке слева.</p>
      </div>
    );
  }

  return (
    <div className="detail-panel">
      <h2>{miklat.name || 'Укрытие без названия'}</h2>
      <p className="muted">
        {miklat.address || '—'}
        {miklat.city ? `, ${miklat.city}` : ''}
      </p>
      <div className="detail-facts">
        <span className="badge">{miklat.type}</span>
        {miklat.capacity != null && <span className="badge">до {miklat.capacity} чел.</span>}
        <span className="badge">{miklat.accessible ? 'доступно для колясок' : 'без доступа для колясок'}</span>
        {miklat.is_verified && <span className="badge verified">проверено</span>}
      </div>
      {miklat.description && <p>{miklat.description}</p>}

      <div className="detail-actions">
        <button onClick={() => onBuildRoute(miklat.id)} disabled={!userLocation}>
          Маршрут пешком отсюда
        </button>
        <button className="secondary" onClick={() => setShowReportForm(true)}>
          Пожаловаться
        </button>
      </div>
      {!userLocation && <p className="muted small">Разрешите доступ к геолокации, чтобы построить маршрут.</p>}

      <RoutePanel route={route} loading={routeLoading} error={routeError} onClear={onClearRoute} />

      <CommentsSection miklatId={miklat.id} />
      <PhotosSection miklatId={miklat.id} />

      {showReportForm && <ReportForm miklatId={miklat.id} onClose={() => setShowReportForm(false)} />}
    </div>
  );
}
