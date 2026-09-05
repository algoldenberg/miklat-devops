import { useState } from 'react';
import AddressSearch from './AddressSearch';
import { api } from '../api';

// Address-to-address walking route with shelters found along the way
// (backend: POST /route on miklat-walking-routes, buffer_m param).
// Reuses AddressSearch as-is for both endpoints, exactly as anticipated
// when that component was first written (see its own top comment).

export default function RouteBetweenAddresses({ onClose, onBuilt }) {
  const [from, setFrom] = useState(null);
  const [to, setTo] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  const canBuild = Boolean(from && to);

  const handleBuild = async () => {
    if (!canBuild) return;
    setLoading(true);
    setError(null);
    try {
      const data = await api.routeBetweenPoints(from, to);
      onBuilt({ ...data, from, to });
      onClose();
    } catch {
      setError('Could not build a route between these addresses.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Route between two addresses</h3>
        <div className="stacked-form">
          <label>
            From
            <AddressSearch placeholder="Start address…" onSelect={setFrom} />
          </label>
          <label>
            To
            <AddressSearch placeholder="Destination address…" onSelect={setTo} />
          </label>
          {error && <p className="error">{error}</p>}
          <div className="modal-actions">
            <button type="button" onClick={onClose} className="secondary">
              Cancel
            </button>
            <button type="button" onClick={handleBuild} disabled={!canBuild || loading}>
              {loading ? 'Building…' : 'Build route'}
            </button>
          </div>
          {!canBuild && <p className="muted small">Pick both a start and a destination address.</p>}
        </div>
      </div>
    </div>
  );
}
