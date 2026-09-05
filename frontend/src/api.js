// Единая точка обращения к бэкенду. Все запросы идут на "/api/*" — во
// время `npm run dev` это проксируется на miklat-gateway через vite.config.js
// (server.proxy), а в docker-compose/проде — nginx-контейнером фронтенда
// (см. nginx.conf), который отрезает префикс "/api" и форвардит на
// miklat-gateway. Сам фронтенд никогда не обращается к сервисам напрямую —
// только через шлюз, ровно как задумано в Фазе 1 шаге 7.

const API_BASE = '/api';

class ApiError extends Error {
  constructor(status, detail) {
    super(typeof detail === 'string' ? detail : detail?.detail || `HTTP ${status}`);
    this.status = status;
    this.detail = detail;
  }
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    headers: { 'Content-Type': 'application/json', ...(options.headers || {}) },
    ...options,
  });

  if (!response.ok) {
    let detail;
    try {
      detail = await response.json();
    } catch {
      detail = await response.text();
    }
    throw new ApiError(response.status, detail);
  }

  if (response.status === 204) return null;
  return response.json();
}

export const api = {
  // ---------- miklats ----------
  listMiklats: (params = {}) => {
    const qs = new URLSearchParams(
      Object.fromEntries(Object.entries(params).filter(([, v]) => v !== undefined && v !== null && v !== ''))
    ).toString();
    return request(`/miklats${qs ? `?${qs}` : ''}`);
  },
  getMiklat: (id) => request(`/miklats/${id}`),
  nearestMiklats: (lon, lat, limit = 10) =>
    request(`/miklats/nearest?lon=${lon}&lat=${lat}&limit=${limit}`),
  // "Find Shelters" tab (ShelterSearch.jsx) — production calls this
  // GET /shelters/nearby/?latitude&longitude&radius&limit; our equivalent is
  // the same /miklats/nearest endpoint used above, with max_distance_m as
  // the radius filter (see miklat-service/app/routers/miklats.py).
  nearbyMiklats: (lon, lat, radius = 1000, limit = 50) =>
    request(`/miklats/nearest?lon=${lon}&lat=${lat}&max_distance_m=${radius}&limit=${limit}`),

  // ---------- comments / rating ----------
  listComments: (miklatId) => request(`/miklats/${miklatId}/comments`),
  ratingSummary: (miklatId) => request(`/miklats/${miklatId}/rating-summary`),
  createComment: (miklatId, { username, comment, rating }) =>
    request(`/miklats/${miklatId}/comments`, {
      method: 'POST',
      body: JSON.stringify({ username, comment, rating }),
    }),

  // ---------- photos ----------
  listPhotos: (miklatId) => request(`/miklats/${miklatId}/photos`),
  uploadPhoto: async (miklatId, file) => {
    const formData = new FormData();
    formData.append('file', file);
    const response = await fetch(`${API_BASE}/miklats/${miklatId}/photos`, {
      method: 'POST',
      body: formData,
    });
    if (!response.ok) {
      let detail;
      try {
        detail = await response.json();
      } catch {
        detail = await response.text();
      }
      throw new ApiError(response.status, detail);
    }
    return response.json();
  },

  // ---------- reports (жалоба на существующее укрытие) ----------
  createReport: (miklatId, { issue_type, comment, contact }) =>
    request(`/miklats/${miklatId}/reports`, {
      method: 'POST',
      body: JSON.stringify({ issue_type, comment, contact }),
    }),

  // ---------- submissions (заявка на новое укрытие) ----------
  createSubmission: (data) =>
    request('/submissions', {
      method: 'POST',
      body: JSON.stringify(data),
    }),

  // ---------- маршруты (пешие, miklat-walking-routes) ----------
  routeToMiklat: (miklatId, fromLon, fromLat) =>
    request(`/route-to-miklat/${miklatId}?from_lon=${fromLon}&from_lat=${fromLat}`),
  // Route between two arbitrary points, with shelters found along the way
  // (POST /route, buffer_m param — see miklat-walking-routes/app/crud.py).
  routeBetweenPoints: (from, to, bufferM = 300) =>
    request('/route', {
      method: 'POST',
      body: JSON.stringify({ from: { lon: from.lon, lat: from.lat }, to: { lon: to.lon, lat: to.lat }, buffer_m: bufferM }),
    }),

  // ---------- meta ----------
  ready: () => request('/ready'),
};

export { ApiError };
