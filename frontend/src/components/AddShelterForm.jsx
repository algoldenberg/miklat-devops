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
      setResult({ type: 'success', text: 'Thanks! Your submission was sent for moderation.' });
      onSubmitted?.();
    } catch {
      setResult({ type: 'error', text: 'Could not submit, please try again.' });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Add a shelter</h3>
        {result ? (
          <>
            <p className={result.type === 'error' ? 'error' : 'success'}>{result.text}</p>
            <button onClick={onClose}>Close</button>
          </>
        ) : (
          <form onSubmit={handleSubmit} className="stacked-form">
            <div className="pick-location-row">
              <button type="button" className="secondary" onClick={onStartPicking}>
                {pickedLocation ? 'Change point on the map' : 'Pick a point on the map'}
              </button>
              {pickedLocation && (
                <span className="muted">
                  {pickedLocation.lat.toFixed(5)}, {pickedLocation.lon.toFixed(5)}
                </span>
              )}
            </div>
            <label>
              Name (optional)
              <input type="text" value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} />
            </label>
            <label>
              Address (optional)
              <input type="text" value={form.address} onChange={(e) => setForm({ ...form, address: e.target.value })} />
            </label>
            <label>
              Shelter type
              <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
                {TYPES.map((t) => (
                  <option key={t} value={t}>
                    {t}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Capacity, people (optional)
              <input
                type="number"
                min="0"
                value={form.capacity}
                onChange={(e) => setForm({ ...form, capacity: e.target.value })}
              />
            </label>
            <label>
              Comment (optional)
              <textarea value={form.comment} onChange={(e) => setForm({ ...form, comment: e.target.value })} />
            </label>
            <div className="modal-actions">
              <button type="button" onClick={onClose} className="secondary">
                Cancel
              </button>
              <button type="submit" disabled={submitting || !pickedLocation}>
                {submitting ? 'Submitting…' : 'Submit'}
              </button>
            </div>
            {!pickedLocation && <p className="muted">Pick a point on the map first.</p>}
          </form>
        )}
      </div>
    </div>
  );
}
