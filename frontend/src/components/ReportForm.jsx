import { useState } from 'react';
import { api } from '../api';

const ISSUE_TYPES = [
  { value: 'closed', label: 'Укрытие закрыто/недоступно' },
  { value: 'wrong_address', label: 'Неверный адрес/координаты' },
  { value: 'other', label: 'Другое' },
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
      setResult({ type: 'success', text: 'Спасибо! Жалоба отправлена, администратор проверит укрытие.' });
    } catch {
      setResult({ type: 'error', text: 'Не удалось отправить жалобу, попробуйте ещё раз.' });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-backdrop" onClick={onClose}>
      <div className="modal" onClick={(e) => e.stopPropagation()}>
        <h3>Пожаловаться на укрытие</h3>
        {result ? (
          <>
            <p className={result.type === 'error' ? 'error' : 'success'}>{result.text}</p>
            <button onClick={onClose}>Закрыть</button>
          </>
        ) : (
          <form onSubmit={handleSubmit} className="stacked-form">
            <label>
              Тип проблемы
              <select value={form.issue_type} onChange={(e) => setForm({ ...form, issue_type: e.target.value })}>
                {ISSUE_TYPES.map((opt) => (
                  <option key={opt.value} value={opt.value}>
                    {opt.label}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Комментарий (необязательно)
              <textarea value={form.comment} onChange={(e) => setForm({ ...form, comment: e.target.value })} />
            </label>
            <label>
              Контакт для связи (необязательно)
              <input
                type="text"
                value={form.contact}
                onChange={(e) => setForm({ ...form, contact: e.target.value })}
                placeholder="email или телефон"
              />
            </label>
            <div className="modal-actions">
              <button type="button" onClick={onClose} className="secondary">
                Отмена
              </button>
              <button type="submit" disabled={submitting}>
                {submitting ? 'Отправка…' : 'Отправить жалобу'}
              </button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
