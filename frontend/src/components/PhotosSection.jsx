import { useEffect, useRef, useState } from 'react';
import { api } from '../api';

export default function PhotosSection({ miklatId }) {
  const [photos, setPhotos] = useState([]);
  const [loading, setLoading] = useState(true);
  const [uploading, setUploading] = useState(false);
  const [message, setMessage] = useState(null);
  const fileInputRef = useRef(null);

  const load = () => {
    setLoading(true);
    api
      .listPhotos(miklatId)
      .then(setPhotos)
      .catch(() => setMessage({ type: 'error', text: 'Could not load photos' }))
      .finally(() => setLoading(false));
  };

  useEffect(load, [miklatId]);

  const handleFileChange = async (e) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setUploading(true);
    setMessage(null);
    try {
      await api.uploadPhoto(miklatId, file);
      setMessage({
        type: 'success',
        text: 'Photo sent for moderation — it will appear here once approved by an admin.',
      });
    } catch (err) {
      setMessage({ type: 'error', text: err.detail?.detail || 'Could not upload the photo' });
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  return (
    <section className="panel-section">
      <h3>Photos</h3>

      {loading && <p className="muted">Loading…</p>}
      {!loading && photos.length === 0 && <p className="muted">No approved photos yet.</p>}

      <div className="photo-grid">
        {photos.map((p) => (
          <a key={p.id} href={p.url} target="_blank" rel="noreferrer">
            <img src={p.url} alt="Shelter photo" className="photo-thumb" />
          </a>
        ))}
      </div>

      <label className="upload-label">
        {uploading ? 'Uploading…' : 'Add a photo (jpeg/png/webp, up to 8 MB)'}
        <input
          ref={fileInputRef}
          type="file"
          accept="image/jpeg,image/png,image/webp"
          onChange={handleFileChange}
          disabled={uploading}
          hidden
        />
      </label>
      {message && <p className={message.type === 'error' ? 'error' : 'success'}>{message.text}</p>}
    </section>
  );
}
