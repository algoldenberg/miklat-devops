import { useState } from 'react';
import { api } from '../api';

const ISSUE_TYPES = [
  { value: 'closed', label: 'Shelter is closed/inaccessible' },
  { value: 'wrong_address', label: 'Wrong address/coordinates' },
  { value: 'other', label: 'Other' },
];

export default function ReportForm({ miklatId, onClose }) {
  const [form, setForm] = useState({ issue_type: 'closed', comment: '', contact: '' });
  const [submitting, setSubmitting] = useState(false);
  const [result, setResult] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSubmitting(true);
    try {
      await api.createReport(miklatId, {
        issue_type: form.issue_type,
        comment: form.comment.trim() || undefined,
        contact: form.contact.trim() || undefined,
      });
      setResult({ type: 'success', text: 'Thank you! The report was sent, an admin will check the shelter.' });
    } catch {
      setResult({ type: 'error', text: 'Could not submit the report, please try again.' });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Report a shelter</h3>
        {result ? (
          <>
            <p className={result.type === 'error' ? 'error' : 'success'}>{result.text}</p>
            <button onClick={onClose}>Close</button>
          </>
        ) : (
          <form onSubmit={handleSubmit} className="stacked-form">
            <label>
              Issue type
              <select value={form.issue_type} onChange={(e) => setForm({ ...form, issue_type: e.target.value })}>
                {ISSUE_TYPES.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Comment (optional)
              <textarea value={form.comment} onChange={(e) => setForm({ ...form, comment: e.target.value })} />
            </label>
            <label>
              Contact (optional)
              <input
                type="text"
                value={form.contact}
                onChange={(e) => setForm({ ...form, contact: e.target.value })}
                placeholder="email or phone"
              />
            </label>
            <div className="modal-actions">
              <button type="button" onClick={onClose} className="secondary">
                Cancel
              </button>
              <button type="submit" disabled={submitting}>
                {submitting ? 'Submitting…' : 'Submit report'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
