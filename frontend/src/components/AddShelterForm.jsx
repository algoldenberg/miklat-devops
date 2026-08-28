import { useState } from 'react';
import { api } from '../api';

const TYPES = ['public_shelter', 'private_shelter', 'stairwell', 'parking_lot', 'reinforced_room', 'other'];

export default function AddShelterForm({ pickedLocation, onStartPicking, onClose, onSubmitted }) {
  const [form, setForm] = useState({ name: '', address: '', type: 'public_shelter', capacity: '', comment: '' });
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!pickedLocation) return;
    setSubmitting(true);
    try {
      await api.createSubmission({
        name: form.name.trim() || undefined,
        address: form.address.trim() || undefined,
        lon: pickedLocation.lon,
        lat: pickedLocation.lat,
        type: form.type,
        capacity: form.capacity ? Number(form.capacity) : undefined,
        comment: form.comment.trim() || undefined,
      });
      setResult({ type: 'success', text: 'Спасибо! Заявка отправлена на модерацию.' });
      onSubmitted?.();
    } catch {
      setResult({ type: 'error', text: 'Не удалось отправить заявку, попробуйте ещё раз.' });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Добавить укрытие</h3>
        {result ? (
          <>
            <p className={result.type === 'error' ? 'error' : 'success'}>{result.text}</p>
            <button onClick={onClose}>Закрыть</button>
          </>
        ) : (
          <form onSubmit={handleSubmit} className="stacked-form">
            <div className="pick-location-row">
              <button type="button" className="secondary" onClick={onStartPicking}>
                {pickedLocation ? 'Изменить точку на карте' : 'Указать точку на карте'}
              </button>
              {pickedLocation && (
                <span className="muted">
                  {pickedLocation.lat.toFixed(5)}, {pickedLocation.lon.toFixed(5)}
                </span>
              )}
            </div>
            <label>
              Название (необязательно)
              <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </label>
            <label>
              Адрес (необязательно)
              <input type="text" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
            </label>
            <label>
              Тип укрытия
              <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
                {TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Вместимость, человек (необязательно)
              <input
                type="number"
                min="0"
                value={form.capacity}
                onChange={(e) => setForm({ ...form, capacity: e.target.value })}
              />
            </label>
            <label>
              Комментарий (необязательно)
              <textarea value={form.comment} onChange={(e) => setForm({ ...form, comment: e.target.value })} />
            </label>
            <div className="modal-actions">
              <button type="button" onClick={onClose} className="secondary">
                Отмена
              </button>
              <button type="submit" disabled={submitting || !pickedLocation}>
                {submitting ? 'Отправка…' : 'Отправить заявку'}
              </button>
            </div>
            {!pickedLocation && <p className="muted">Сначала укажите точку на карте.</p>}
          </form>
        )}
      </div>
    </div>
  );
}
