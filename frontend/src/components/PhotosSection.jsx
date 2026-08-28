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
      .catch(() => setMessage({ type: 'error', text: 'Не удалось загрузить фото' }))
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
        text: 'Фото отправлено на модерацию — появится здесь после проверки администратором.',
      });
    } catch (err) {
      setMessage({ type: 'error', text: err.detail?.detail || 'Не удалось загрузить фото' });
    } finally {
      setUploading(false);
      if (fileInputRef.current) fileInputRef.current.value = '';
    }
  };

  return (
    <section className="panel-section">
      <h3>Фото</h3>

      {loading && <p className="muted">Загрузка…</p>}
      {!loading && photos.length === 0 && <p className="muted">Пока нет одобренных фото.</p>}

      <div className="photo-grid">
        {photos.map((p) => (
          <a key={p.id} href={p.url} target="_blank" rel="noreferrer">
            <img src={p.url} alt="Фото укрытия" className="photo-thumb" />
          </a>
        ))}
      </div>

      <label className="upload-label">
        {uploading ? 'Загрузка…' : 'Добавить фото (jpeg/png/webp, до 8 МБ)'}
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
