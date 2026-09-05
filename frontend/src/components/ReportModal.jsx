import { useState, useEffect } from 'react';

// Ported from shelter-route-planner/frontend/src/components/ReportModal.jsx.
// Necessary adaptations:
//   - Photo upload dropped (same reasoning as AddShelterModal — no
//     moderation path in our backend for a photo attached to a report).
//   - Issue-type list is our real one — verified against
//     db/seed/reports_seed.json: closed, wrong_address, other. The
//     original's "blocked_entrance" option doesn't exist in our data/schema,
//     so it's dropped rather than sent as a value the backend never expects.
// Everything else — layout, validation (min 5 chars), fields — is unchanged.

const ReportModal = ({ isOpen, onClose, onSubmit, shelterName }) => {
  const [formData, setFormData] = useState({
    issueType: 'closed',
    comment: '',
    contact: '',
  });

  useEffect(() => {
    if (isOpen) {
      setFormData({ issueType: 'closed', comment: '', contact: '' });
    }
  }, [isOpen]);

  const handleSubmit = (e) => {
    e.preventDefault();

    if (!formData.comment.trim() || formData.comment.length < 5) {
      alert('Please provide at least 5 characters in the details field');
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

  if (!isOpen) return null;

  return (
    <>
      {/* Full screen blocker - blocks ALL map events */}
      <div
        className="report-modal-blocker"
        onClick={(e) => e.stopPropagation()}
        onTouchStart={(e) => e.stopPropagation()}
        onTouchMove={(e) => e.stopPropagation()}
        onTouchEnd={(e) => e.stopPropagation()}
      />

      <div className="report-modal-backdrop" onClick={onClose} />

      <div className="report-modal">
        <div className="report-modal__header">
          <h2>🚫 Report Issue</h2>
          <button className="close-btn" onClick={onClose}>
            ✕
          </button>
        </div>

        <div className="report-modal__shelter-name">
          <strong>Shelter:</strong> {shelterName}
        </div>

        <form onSubmit={handleSubmit} className="report-modal__form">
          {/* Issue Type */}
          <div className="form-group">
            <label>Issue Type *</label>
            <select name="issueType" value={formData.issueType} onChange={handleChange} required>
              <option value="closed">❌ Shelter closed / doesn't exist</option>
              <option value="wrong_address">📍 Wrong address / coordinates</option>
              <option value="other">ℹ️ Other</option>
            </select>
          </div>

          {/* Details */}
          <div className="form-group">
            <label>Details *</label>
            <textarea
              name="comment"
              value={formData.comment}
              onChange={handleChange}
              placeholder="Please describe the issue..."
              rows={4}
              required
              minLength={5}
            />
            <small className="help-text">Minimum 5 characters</small>
          </div>

          {/* Contact */}
          <div className="form-group">
            <label>Contact (optional)</label>
            <input
              type="text"
              name="contact"
              value={formData.contact}
              onChange={handleChange}
              placeholder="Email or phone (if you want a response)"
            />
          </div>

          {/* Actions */}
          <div className="form-actions">
            <button type="button" className="btn btn--outline" onClick={onClose}>
              Cancel
            </button>
            <button type="submit" className="btn btn--primary">
              Submit Report
            </button>
          </div>
        </form>
      </div>
    </>
  );
};

export default ReportModal;
