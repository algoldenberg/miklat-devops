// Client-side geocoding via the public OpenStreetMap Nominatim API.
// Called directly from the browser — same approach the production
// shelter-route-planner uses (frontend/src/services/geocoding.js), no
// backend involved, no gateway route needed.
//
// Nominatim accepts a query in any language/script (Hebrew, Russian,
// English, ...) and geocodes it — we don't need to do anything special
// for that. `countrycodes=il` just narrows results to Israel, matching
// this app's scope.
//
// Usage policy (https://operations.osmfoundation.org/policies/nominatim/):
// max ~1 request/second per client. The debounce in AddressSearch.jsx
// already keeps a single typing user well under that.

const NOMINATIM_URL = 'https://nominatim.openstreetmap.org/search';
const COUNTRY_CODE = 'il';
const RESULT_LIMIT = 5;

export async function searchAddress(query) {
  const params = new URLSearchParams({
    q: query,
    format: 'jsonv2',
    countrycodes: COUNTRY_CODE,
    limit: String(RESULT_LIMIT),
  });

  const response = await fetch(`${NOMINATIM_URL}?${params.toString()}`);
  if (!response.ok) {
    throw new Error(`Nominatim request failed: HTTP ${response.status}`);
  }

  const data = await response.json();
  return data.map((item) => ({
    id: item.place_id,
    label: item.display_name,
    lon: parseFloat(item.lon),
    lat: parseFloat(item.lat),
  }));
}
