import { useState, useEffect } from 'react';
import AddressSearch from './AddressSearch';

// Ported from shelter-route-planner/frontend/src/components/AddShelterModal.jsx.
// Necessary adaptations (see App.jsx header note for the full list):
//   - hCaptcha dropped entirely — we have no site key or backend validation
//     for it, so there is nothing to port it against.
//   - Photo upload dropped from this form — a submission's photos would have
//     no moderation path in our backend; photos are only ever attached to an
//     already-approved shelter, via PhotosSection.
//   - The address-input mode reuses our own already-tested AddressSearch
//     component (Nominatim-backed) instead of duplicating a raw fetch call.
//   - The shelter type list is our real one (public_shelter, school_shelter,
//     parking_storage, parking_shelter, migunit, private_building — verified
//     against db/seed/miklats_seed.json) instead of the original's
//     mismatched 4-option list.
// Everything else — the dual address/map location mode, the field layout,
// the map-picking flow — is unchanged.

const SHELTER_TYPES = [
  { value: 'public_shelter', label: 'Public Shelter' },
  { value: 'school_shelter', label: 'School Shelter' },
  { value: 'parking_storage', label: 'Parking Storage' },
  { value: 'parking_shelter', label: 'Parking Shelter' },
  { value: 'migunit', label: 'Migunit' },
  { value: 'private_building', label: 'Private Building' },
];

const AddShelterModal = ({ isOpen, onClose, onSubmit, onPickOnMap, isPickingLocation, pickedLocation }) => {
  const [formData, setFormData] = useState({
    name: '',
    address: '',
    latitude: '',
    longitude: '',
    type: 'public_shelter',
    capacity: '',
    comment: '',
  });

  const [inputMethod, setInputMethod] = useState('address');

  // Reset form when modal opens
  useEffect(() => {
    if (isOpen) {
      setFormData({
        name: '',
        address: '',
        latitude: '',
        longitude: '',
        type: 'public_shelter',
        capacity: '',
        comment: '',
      });
    }
  }, [isOpen]);

  // Update coordinates when location picked from map
  useEffect(() => {
    if (pickedLocation) {
      setFormData((prev) => ({
        ...prev,
        latitude: pickedLocation.latitude.toString(),
        longitude: pickedLocation.longitude.toString(),
      }));
    }
  }, [pickedLocation]);

  const handleSubmit = (e) => {
    e.preventDefault();

    if (inputMethod === 'map' && (!formData.latitude || !formData.longitude)) {
      alert('Please pick a location on the map first');
      return;
    }

    if (inputMethod === 'address' && (!formData.latitude || !formData.longitude)) {
      alert('Please select an address from the suggestions to get coordinates');
      return;
    }

    onSubmit({ ...formData });
  };

  const handleChange = (e) => {
    setFormData({
      ...formData,
      [e.target.name]: e.target.value,
    });
  };

  const handleAddressSelect = (result) => {
    if (!result) {
      setFormData((prev) => ({ ...prev, address: '', latitude: '', longitude: '' }));
      return;
    }
    setFormData((prev) => ({
      ...prev,
      address: result.label,
      latitude: result.lat.toString(),
      longitude: result.lon.toString(),
    }));
  };

  const handlePickOnMap = () => {
    onPickOnMap(true);
  };

  if (!isOpen) return null;

  return (
    <>
      <div className="add-shelter-modal-backdrop" onClick={onClose} />

      <div className="add-shelter-modal">
        <div className="add-shelter-modal__header">
          <h2>🛡️ Suggest New Shelter</h2>
          <button className="close-btn" onClick={onClose}>
            ✕
          </button>
        </div>

        <form onSubmit={handleSubmit} className="add-shelter-modal__form">
          {/* Location Method */}
          <div className="form-group">
            <label>How to specify location:</label>
            <div className="radio-group">
              <label className="radio-label">
                <input
                  type="radio"
                  value="address"
                  checked={inputMethod === 'address'}
                  onChange={(e) => setInputMethod(e.target.value)}
                  disabled={isPickingLocation}
                />
                🔍 Enter Address
              </label>
              <label className="radio-label">
                <input
                  type="radio"
                  value="map"
                  checked={inputMethod === 'map'}
                  onChange={(e) => setInputMethod(e.target.value)}
                  disabled={isPickingLocation}
                />
                📍 Click on Map
              </label>
            </div>
          </div>

          {/* Shelter Name */}
          <div className="form-group">
            <label>Shelter Name *</label>
            <input
              type="text"
              name="name"
              value={formData.name}
              onChange={handleChange}
              placeholder="e.g., Building 5 Shelter"
              required
              minLength={3}
              disabled={isPickingLocation}
            />
          </div>

          {/* Address with autocomplete (our AddressSearch component) */}
          {inputMethod === 'address' && (
            <div className="form-group">
              <label>Address *</label>
              <AddressSearch placeholder="Start typing street name, city…" onSelect={handleAddressSelect} />
              {formData.latitude && formData.longitude && (
                <small className="help-text success-text">
                  ✓ Coordinates: {parseFloat(formData.latitude).toFixed(6)}, {parseFloat(formData.longitude).toFixed(6)}
                </small>
              )}
            </div>
          )}

          {/* Coordinates (locked when map mode) */}
          {inputMethod === 'map' && (
            <div className="form-group">
              <label>Coordinates</label>
              <div className="coords-inputs">
                <input
                  type="text"
                  value={formData.latitude || 'Auto-filled after picking'}
                  placeholder="Latitude"
                  disabled
                  className="coords-locked"
                />
                <input
                  type="text"
                  value={formData.longitude || 'Auto-filled after picking'}
                  placeholder="Longitude"
                  disabled
                  className="coords-locked"
                />
              </div>
              {!formData.latitude && (
                <small className="help-text">
                  Click "Pick on Map" button below, then click on the map to select location
                </small>
              )}
              {formData.latitude && (
                <small className="help-text success-text">
                  ✓ Location selected: {parseFloat(formData.latitude).toFixed(6)}, {parseFloat(formData.longitude).toFixed(6)}
                </small>
              )}
            </div>
          )}

          {/* Type */}
          <div className="form-group">
            <label>Shelter Type *</label>
            <select name="type" value={formData.type} onChange={handleChange} required disabled={isPickingLocation}>
              {SHELTER_TYPES.map((t) => (
                <option key={t.value} value={t.value}>
                  {t.label}
                </option>
              ))}
            </select>
          </div>

          {/* Capacity */}
          <div className="form-group">
            <label>Capacity (optional)</label>
            <input
              type="number"
              name="capacity"
              value={formData.capacity}
              onChange={handleChange}
              placeholder="Approximate number of people"
              min="1"
              disabled={isPickingLocation}
            />
          </div>

          {/* Comment/Instructions */}
          <div className="form-group">
            <label>Instructions / Comment (optional)</label>
            <textarea
              name="comment"
              value={formData.comment}
              onChange={handleChange}
              placeholder="Where is the entrance? Any access details?"
              rows={3}
              disabled={isPickingLocation}
            />
          </div>

          {/* Actions */}
          <div className="form-actions">
            {inputMethod === 'map' && !formData.latitude && (
              <button type="button" className="btn btn--secondary" onClick={handlePickOnMap}>
                📍 Pick on Map
              </button>
            )}
            <button type="button" className="btn btn--outline" onClick={onClose} disabled={isPickingLocation}>
              Cancel
            </button>
            <button type="submit" className="btn btn--primary" disabled={isPickingLocation}>
              Submit Shelter
            </button>
          </div>
        </form>
      </div>
    </>
  );
};

export default AddShelterModal;
