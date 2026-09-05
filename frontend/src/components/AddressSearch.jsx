import { useEffect, useRef, useState } from 'react';
import { searchAddress } from '../geocoding';

// Debounced address autocomplete backed by Nominatim (see ../geocoding.js).
// Generic on purpose: used for the "search nearest miklat by address" flow
// today, and reusable as-is for a future "route from address A to address B"
// picker (two instances of this component, one per endpoint).

const DEBOUNCE_MS = 500;
const MIN_QUERY_LENGTH = 3;

export default function AddressSearch({ placeholder = 'Search by address…', onSelect }) {
  const [query, setQuery] = useState('');
  const [results, setResults] = useState([]);
  const [open, setOpen] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selected, setSelected] = useState(false);
  const containerRef = useRef(null);

  useEffect(() => {
    if (selected || query.trim().length < MIN_QUERY_LENGTH) {
      setResults([]);
      setOpen(false);
      return;
    }

    setLoading(true);
    const timer = setTimeout(() => {
      searchAddress(query)
        .then((items) => {
          setResults(items);
          setOpen(true);
        })
        .catch(() => setResults([]))
        .finally(() => setLoading(false));
    }, DEBOUNCE_MS);

    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [query]);

  useEffect(() => {
    function handleClickOutside(e) {
      if (containerRef.current && !containerRef.current.contains(e.target)) {
        setOpen(false);
      }
    }
    document.addEventListener('mousedown', handleClickOutside);
    return () => document.removeEventListener('mousedown', handleClickOutside);
  }, []);

  const handleChange = (e) => {
    setSelected(false);
    setQuery(e.target.value);
  };

  const handlePick = (result) => {
    setQuery(result.label);
    setSelected(true);
    setOpen(false);
    setResults([]);
    onSelect({ lon: result.lon, lat: result.lat, label: result.label });
  };

  const handleClear = () => {
    setQuery('');
    setSelected(false);
    setResults([]);
    setOpen(false);
    onSelect(null);
  };

  return (
    <div className="address-search" ref={containerRef}>
      <input
        type="text"
        placeholder={placeholder}
        value={query}
        onChange={handleChange}
        onFocus={() => results.length > 0 && setOpen(true)}
      />
      {selected && (
        <button type="button" className="address-search-clear" onClick={handleClear} aria-label="Clear">
          ×
        </button>
      )}
      {loading && <span className="address-search-spinner">…</span>}
      {open && (
        <ul className="address-search-results">
          {results.length > 0
            ? results.map((r) => (
                <li key={r.id} className="address-search-result" onClick={() => handlePick(r)}>
                  {r.label}
                </li>
              ))
            : !loading && <li className="address-search-empty">No results</li>}
        </ul>
      )}
    </div>
  );
}
