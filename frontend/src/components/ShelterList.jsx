export default function ShelterList({ miklats, selectedId, onSelect, loading }) {
  if (loading) return <p className="muted">Loading shelters…</p>;
  if (miklats.length === 0) return <p className="muted">No shelters match the current filters.</p>;

  return (
    <ul className="shelter-list">
      {miklats.map((m) => (
        <li
          key={m.id}
          className={m.id === selectedId ? 'shelter-list-item selected' : 'shelter-list-item'}
          onClick={() => onSelect(m.id)}
        >
          <div className="shelter-list-item-title">
            {m.name || 'Unnamed shelter'}
            {m.distance_m !== undefined && (
              <span className="badge">{Math.round(m.distance_m)} m</span>
            )}
          </div>
          <div className="shelter-list-item-sub">
            {m.address || m.city || '—'} · {m.type}
            {!m.accessible && ' · not wheelchair accessible'}
          </div>
        </li>
      ))}
    </ul>
  );
}
