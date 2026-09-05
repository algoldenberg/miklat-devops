export default function RoutePanel({ route, loading, error, onClear }) {
  if (loading) return <p className="muted">Building route…</p>;
  if (error) return <p className="error">{error}</p>;
  if (!route) return null;

  const minutes = Math.round(route.duration_s / 60);

  return (
    <div className="route-panel">
      <div>
        On foot: <strong>{(route.distance_m / 1000).toFixed(2)} km</strong> · ~{minutes} min
      </div>
      <button className="secondary" onClick={onClear}>
        Hide route
      </button>
    </div>
  );
}
