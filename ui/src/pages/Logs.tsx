import { useEffect, useState } from 'react';
import { Layout } from '../components/Layout';
import { fetchLogs, ApiRequestError } from '../api/client';
import type { LogEntry } from '../types';

const LEVEL_CLASS: Record<string, string> = {
  info:     'log__level--info',
  warn:     'log__level--warn',
  error:    'log__level--error',
  debug:    'log__level--debug',
  critical: 'log__level--critical',
};

export function Logs() {
  const [logs, setLogs] = useState<LogEntry[]>([]);
  const [filter, setFilter] = useState<'all' | LogEntry['level']>('all');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [limit, setLimit] = useState(100);

  async function load() {
    setLoading(true); setError(null);
    try {
      setLogs(await fetchLogs(limit));
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : 'Logs konnten nicht geladen werden.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, [limit]);

  const filtered = filter === 'all' ? logs : logs.filter((l) => l.level === filter);

  const counts = {
    all:   logs.length,
    error: logs.filter((l) => l.level === 'error').length,
    warn:  logs.filter((l) => l.level === 'warn').length,
    info:  logs.filter((l) => l.level === 'info').length,
  };

  return (
    <Layout title="Logs">
      {/* ── Toolbar ── */}
      <div
        style={{
          display: 'flex',
          alignItems: 'center',
          gap: '0.5rem',
          marginBottom: '1rem',
          flexWrap: 'wrap',
        }}
      >
        {(['all', 'error', 'warn', 'info'] as const).map((level) => (
          <button
            key={level}
            className={`btn btn--sm ${filter === level ? 'btn--active' : 'btn--ghost'}`}
            onClick={() => setFilter(level)}
          >
            {level === 'all' ? `Alle (${counts.all})` : (
              <>
                {level.toUpperCase()}
                {counts[level as keyof typeof counts] > 0 && (
                  <span
                    style={{
                      marginLeft: '0.35rem',
                      padding: '0 0.4rem',
                      borderRadius: '99px',
                      fontSize: '0.65rem',
                      background: level === 'error' ? 'var(--rose-dim)' : level === 'warn' ? 'var(--amber-dim)' : 'var(--indigo-dim)',
                      color:      level === 'error' ? 'var(--rose-500)' : level === 'warn' ? 'var(--amber-400)' : 'var(--indigo-500)',
                    }}
                  >
                    {counts[level as keyof typeof counts]}
                  </span>
                )}
              </>
            )}
          </button>
        ))}

        <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginLeft: 'auto' }}>
          <input
            className="form-input"
            type="number"
            min={10}
            max={500}
            value={limit}
            onChange={(e) => setLimit(Number(e.target.value) || 100)}
            style={{ width: '5rem', padding: '0.28rem 0.5rem', fontSize: '0.78rem' }}
            title="Max. Einträge"
          />
          <button className="btn btn--sm btn--ghost" onClick={() => void load()} disabled={loading}>
            {loading ? 'Lädt…' : '↺ Aktualisieren'}
          </button>
        </div>
      </div>

      {error && <div className="alert alert--error" style={{ marginBottom: '1rem' }}>{error}</div>}

      {/* ── Terminal ── */}
      <div className="terminal">
        <div className="terminal__bar">
          <div className="terminal__dot terminal__dot--red" />
          <div className="terminal__dot terminal__dot--amber" />
          <div className="terminal__dot terminal__dot--green" />
          <span className="terminal__title">
            router.log — {filtered.length} Einträge
            {filter !== 'all' && ` · gefiltert: ${filter.toUpperCase()}`}
          </span>
        </div>

        <div className="terminal__body">
          {loading && (
            <div style={{ color: 'rgba(99,102,241,0.5)', fontFamily: 'var(--mono)', fontSize: '0.78rem' }}>
              Lade Logs…
            </div>
          )}
          {!loading && (
            <div className="log-list">
              {filtered.map((entry, i) => (
                <div key={i} className="log-entry">
                  <span className="log__time">
                    {new Date(entry.timestamp).toLocaleTimeString('de-DE')}
                  </span>
                  <span className={`log__level ${LEVEL_CLASS[entry.level] ?? 'log__level--info'}`}>
                    {entry.level.toUpperCase()}
                  </span>
                  <span className="log__source" title={entry.source}>
                    {entry.source.length > 12 ? entry.source.slice(0, 12) + '…' : entry.source}
                  </span>
                  <span className="log__msg">{entry.message}</span>
                </div>
              ))}
              {filtered.length === 0 && (
                <div style={{ color: 'rgba(99,102,241,0.35)', fontFamily: 'var(--mono)', fontSize: '0.78rem' }}>
                  — keine Einträge{filter !== 'all' ? ` für Level "${filter}"` : ''} —
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
