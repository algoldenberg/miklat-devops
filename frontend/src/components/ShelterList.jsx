export default function ShelterList({ miklats, selectedId, onSelect, loading }) {
  if (loading) return <p className="muted">Загрузка укрытий…</p>;
  if (miklats.length === 0) return <p className="muted">Ничего не найдено по текущим фильтрам.</p>;

  return (
    <ul className="shelter-list">
      {miklats.map((m) => (
        <li
          key={m.id}
          className={m.id === selectedId ? 'shelter-list-item selected' : 'shelter-list-item'}
          onClick={() => onSelect(m.id)}
        >
          <div className="shelter-list-item-title">
            {m.name || 'Укрытие без названия'}
            {m.distance_m !== undefined && (
              <span className="badge">{Math.round(m.distance_m)} м</span>
            )}
          </div>
          <div className="shelter-list-item-sub">
            {m.address || m.city || '—'} · {m.type}
            {!m.accessible && ' · без доступа для колясок'}
          </div>
        </li>
      ))}
    </ul>
  );
}
