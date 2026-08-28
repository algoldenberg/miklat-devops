export default function RoutePanel({ route, loading, error, onClear }) {
  if (loading) return <p className="muted">Строим маршрут…</p>;
  if (error) return <p className="error">{error}</p>;
  if (!route) return null;

  const minutes = Math.round(route.duration_s / 60);

  return (
    <div className="route-panel">
      <div>
        Пешком: <strong>{(route.distance_m / 1000).toFixed(2)} км</strong> · ~{minutes} мин
      </div>
      <button className="secondary" onClick={onClear}>
        Скрыть маршрут
      </button>
    </div>
  );
}
