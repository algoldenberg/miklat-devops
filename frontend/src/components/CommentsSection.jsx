import { useEffect, useState } from 'react';
import { api } from '../api';

export default function CommentsSection({ miklatId }) {
  const [comments, setComments] = useState([]);
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [form, setForm] = useState({ username: '', comment: '', rating: '' });
  const [submitting, setSubmitting] = useState(false);

  const load = () => {
    setLoading(true);
    setError(null);
    Promise.all([api.listComments(miklatId), api.ratingSummary(miklatId)])
      .then(([commentsData, summaryData]) => {
        setComments(commentsData);
        setSummary(summaryData);
      })
      .catch(() => setError('Could not load comments'))
      .finally(() => setLoading(false));
  };

  useEffect(load, [miklatId]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!form.comment.trim()) return;
    setSubmitting(true);
    setError(null);
    try {
      await api.createComment(miklatId, {
        username: form.username.trim() || undefined,
        comment: form.comment.trim(),
        rating: form.rating ? Number(form.rating) : undefined,
      });
      setForm({ username: '', comment: '', rating: '' });
      load();
    } catch {
      setError('Could not submit the comment');
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <section className="panel-section">
      <h3>
        Comments
        {summary && summary.ratings_count > 0 && (
          <span className="rating-summary">
            ★ {summary.average_rating?.toFixed(1)} ({summary.ratings_count})
          </span>
        )}
      </h3>

      {loading && <p className="muted">Loading…</p>}
      {!loading && comments.length === 0 && <p className="muted">No comments yet.</p>}

      <ul className="comment-list">
        {comments.map((c) => (
          <li key={c.id} className="comment-item">
            <div className="comment-header">
              <strong>{c.username}</strong>
              {c.rating && <span className="badge">★ {c.rating}</span>}
            </div>
            <div>{c.comment}</div>
          </li>
        ))}
      </ul>

      <form className="inline-form" onSubmit={handleSubmit}>
        <input
          type="text"
          placeholder="Your name (optional)"
          value={form.username}
          onChange={(e) => setForm({ ...form, username: e.target.value })}
        />
        <textarea
          placeholder="Your comment"
          value={form.comment}
          onChange={(e) => setForm({ ...form, comment: e.target.value })}
          required
        />
        <select value={form.rating} onChange={(e) => setForm({ ...form, rating: e.target.value })}>
          <option value="">No rating</option>
          {[1, 2, 3, 4, 5].map((n) => (
            <option key={n} value={n}>
              {n} ★
            </option>
          ))}
        </select>
        <button type="submit" disabled={submitting}>
          {submitting ? 'Sending…' : 'Send'}
        </button>
      </form>
      {error && <p className="error">{error}</p>}
    </section>
  );
}
