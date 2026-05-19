import { useState, useEffect } from 'react';
import { Layout } from '../components/Layout';
import { fetchLogs } from '../api/client';
import { useApiCall } from '../hooks/useApi';
import type { LogEntry } from '../types';

type Level = LogEntry['level'] | 'debug' | 'critical';
type Filter = 'all' | Level;

const LEVEL_CLASS: Record<string, string> = {
  info:     'log__level--info',
  warn:     'log__level--warn',
  error:    'log__level--error',
  debug:    'log__level--debug',
  critical: 'log__level--critical',
};

export function Logs() {
  const [filter, setFilter] = useState<Filter>('all');
  const { data: logs, loading, error, execute } = useApiCall<LogEntry[]>();

  useEffect(() => {
    execute(() => fetchLogs(200)).catch(() => {});
  }, [execute]);

  const entries = logs ?? [];
  const filtered = filter === 'all' ? entries : entries.filter((l) => l.level === filter);

  const counts = {
    all:   entries.length,
    error: entries.filter((l) => l.level === 'error').length,
    warn:  entries.filter((l) => l.level === 'warn').length,
    info:  entries.filter((l) => l.level === 'info').length,
  };

  return (
    <Layout title="Logs">
      {/* ── Filter bar ── */}
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
                      background: level === 'error'
                        ? 'var(--rose-dim)'
                        : level === 'warn'
                        ? 'var(--amber-dim)'
                        : 'var(--indigo-dim)',
                      color: level === 'error'
                        ? 'var(--rose-500)'
                        : level === 'warn'
                        ? 'var(--amber-400)'
                        : 'var(--indigo-500)',
                    }}
                  >
                    {counts[level as keyof typeof counts]}
                  </span>
                )}
              </>
            )}
          </button>
        ))}
        <button
          className="btn btn--sm btn--ghost"
          style={{ marginLeft: 'auto' }}
          onClick={() => execute(() => fetchLogs(200)).catch(() => {})}
          disabled={loading}
        >
          {loading ? 'Lädt…' : '↺ Aktualisieren'}
        </button>
      </div>

      {error && <div className="alert alert--error" style={{ marginBottom: '1rem' }}>{error}</div>}

      {/* ── Terminal window ── */}
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
            <div style={{ color: 'rgba(99,102,241,0.5)', fontFamily: 'var(--font-mono)', fontSize: '0.78rem' }}>
              Lade Logs…
            </div>
          )}

          {!loading && !error && (
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
                <div style={{ color: 'rgba(99,102,241,0.35)', fontFamily: 'var(--font-mono)', fontSize: '0.78rem' }}>
                  — keine Einträge für diesen Filter —
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </Layout>
  );
}
