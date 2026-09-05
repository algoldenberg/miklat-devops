// Summary + shelter list for an address-to-address route (see
// RouteBetweenAddresses.jsx). Separate from RoutePanel.jsx on purpose —
// that one is the single "route to this shelter" panel, this one carries
// an extra list of shelters found along the way.

export default function AddressRoutePanel({ route, onClear }) {
  if (!route) return null;

  const minutes = Math.round(route.duration_s / 60);
  const miklats = route.miklats || [];

  return (
    <div className="address-route-summary">
      <div className="route-panel">
        <div>
          <div>
            Walking route: <strong>{(route.distance_m / 1000).toFixed(2)} km</strong> · ~{minutes} min
          </div>
          <div className="muted small">
            {miklats.length} shelter{miklats.length === 1 ? '' : 's'} along the route
          </div>
        </div>
        <button className="secondary" onClick={onClear}>
          Clear route
        </button>
      </div>

      {miklats.length > 0 && (
        <ul className="shelter-list">
          {miklats.map((m) => (
            <li key={m.id} className="shelter-list-item">
              <div className="shelter-list-item-title">{m.name || 'Unnamed shelter'}</div>
              <div className="shelter-list-item-sub">
                {m.address || m.city || '—'} · {Math.round(m.distance_to_route_m)} m from route
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
