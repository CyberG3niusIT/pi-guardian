import { useEffect } from 'react';
import { Card } from '../components/Card';
import { StatusBadge } from '../components/StatusBadge';
import { Layout } from '../components/Layout';
import { CONFIG } from '../config';
import { fetchServiceStatus, fetchSettings, fetchAgents, fetchMemoryRuns } from '../api/client';
import { useApiCall } from '../hooks/useApi';
import type {
  ConnectionState,
  RouterSettings,
  ServiceStatus,
  AgentDefinition,
  MemoryRunSummary,
} from '../types';

interface Props {
  connectionState: ConnectionState;
  lastCheck: string | null;
  healthError: string | null;
  onRefresh: () => void;
}

export function Dashboard({ connectionState, lastCheck, healthError, onRefresh }: Props) {
  const { data: serviceStatus, loading: statusLoading, error: statusError, execute } =
    useApiCall<ServiceStatus>();
  const { data: routerSettings, loading: settingsLoading, error: settingsError, execute: loadSettings } =
    useApiCall<RouterSettings>();
  const { data: agents, execute: loadAgents } =
    useApiCall<AgentDefinition[]>();
  const { data: memoryRuns, execute: loadMemoryRuns } =
    useApiCall<MemoryRunSummary[]>();

  useEffect(() => {
    execute(fetchServiceStatus).catch(() => {});
    loadSettings(fetchSettings).catch(() => {});
    loadAgents(fetchAgents).catch(() => {});
    loadMemoryRuns(fetchMemoryRuns).catch(() => {});
  }, [execute, loadSettings, loadAgents, loadMemoryRuns]);

  const activeAgents = agents?.filter((a) => a.settings?.active !== false).length ?? 0;
  const totalAgents  = agents?.length ?? 0;
  const memoryCount  = memoryRuns?.length ?? 0;
  const uptime       = serviceStatus?.uptime ?? '–';

  return (
    <Layout title="Dashboard">
      {/* ── Hero stat cards ── */}
      <div className="grid grid--4" style={{ marginBottom: '1.5rem' }}>
        <div className="stat-card">
          <span className="stat-card__icon">◉</span>
          <div className="stat-card__label">Aktive Agenten</div>
          <div className={`stat-card__value${activeAgents > 0 ? ' stat-card__value--indigo' : ''}`}>
            {activeAgents}
          </div>
          <div className="stat-card__sub">von {totalAgents} gesamt</div>
        </div>

        <div className="stat-card">
          <span className="stat-card__icon">◫</span>
          <div className="stat-card__label">Memory-Runs</div>
          <div className={`stat-card__value${memoryCount > 0 ? ' stat-card__value--violet' : ''}`}>
            {memoryCount}
          </div>
          <div className="stat-card__sub">gespeicherte Läufe</div>
        </div>

        <div className="stat-card">
          <span className="stat-card__icon">⬡</span>
          <div className="stat-card__label">Standardmodell</div>
          <div className="stat-card__value stat-card__value--emerald" style={{ fontSize: '1.05rem', letterSpacing: '-0.01em' }}>
            {settingsLoading ? '…' : (routerSettings?.default_model || CONFIG.defaultModel)}
          </div>
          <div className="stat-card__sub">Ollama (lokal)</div>
        </div>

        <div className="stat-card">
          <span className="stat-card__icon">↑</span>
          <div className="stat-card__label">Uptime</div>
          <div className="stat-card__value" style={{ fontSize: statusLoading ? '1.9rem' : '1.1rem', letterSpacing: '-0.01em' }}>
            {statusLoading ? '…' : uptime}
          </div>
          <div className="stat-card__sub">
            {serviceStatus?.active ? 'systemd aktiv' : 'systemd unbekannt'}
          </div>
        </div>
      </div>

      {/* ── Recent Activity + System Health ── */}
      <div className="grid grid--2">
        {/* Recent Activity */}
        <Card title="Recent Activity" tag="LIVE">
          {/* Status overview */}
          <div className="kv">
            <span className="kv__label">Backend</span>
            <StatusBadge state={connectionState} />
          </div>
          <div className="kv">
            <span className="kv__label">Router</span>
            <code className="kv__value">{CONFIG.routerHost}:{CONFIG.routerPort}</code>
          </div>
          <div className="kv">
            <span className="kv__label">Letzter Check</span>
            <span className="kv__value">{lastCheck ?? '–'}</span>
          </div>
          {healthError && (
            <div className="alert alert--error" style={{ marginTop: '0.75rem' }}>{healthError}</div>
          )}
          {settingsError && (
            <div className="alert alert--error" style={{ marginTop: '0.75rem' }}>{settingsError}</div>
          )}

          {/* API endpoints quick-ref */}
          <div style={{ marginTop: '1.1rem', paddingTop: '0.85rem', borderTop: '1px solid var(--card-border)' }}>
            <div className="text--xs text--muted" style={{ fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '0.6rem' }}>
              Verfügbare Endpunkte
            </div>
            <ul className="gap-list">
              <li><code>GET /health</code>, <code>GET /status/service</code></li>
              <li><code>GET /models</code>, <code>POST /route</code></li>
              <li><code>GET /logs</code>, <code>GET /history</code></li>
              <li><code>PUT /settings</code>, <code>/clients</code> CRUD</li>
            </ul>
          </div>

          <div style={{ marginTop: '1rem' }}>
            <button className="btn btn--sm btn--ghost" onClick={onRefresh}>
              Health prüfen
            </button>
          </div>
        </Card>

        {/* System Health */}
        <Card title="System Health" tag="LIVE">
          {statusLoading && (
            <div className="text--muted text--sm">Lade Dienststatus…</div>
          )}
          {statusError && !statusLoading && (
            <div className="alert alert--error">{statusError}</div>
          )}
          {serviceStatus && !statusLoading && (
            <>
              <div className="kv">
                <span className="kv__label">systemd</span>
                <StatusBadge
                  state={serviceStatus.active ? 'connected' : 'disconnected'}
                  label={serviceStatus.active ? 'Aktiv' : 'Inaktiv'}
                />
              </div>
              <div className="kv">
                <span className="kv__label">Uptime</span>
                <span className="kv__value">{serviceStatus.uptime ?? '–'}</span>
              </div>
              <div className="kv">
                <span className="kv__label">PID</span>
                <code className="kv__value">{serviceStatus.pid ?? '–'}</code>
              </div>
              <div className="kv">
                <span className="kv__label">CPU</span>
                <span className="kv__value">
                  {serviceStatus.cpu_percent != null ? `${serviceStatus.cpu_percent} %` : '–'}
                </span>
              </div>
              <div className="kv">
                <span className="kv__label">Memory</span>
                <span className="kv__value">{serviceStatus.memory_usage ?? '–'}</span>
              </div>
            </>
          )}
          {!serviceStatus && !statusLoading && !statusError && (
            <div className="empty-state">
              <div className="empty-state__icon">◌</div>
              <div className="empty-state__title">Kein Dienststatus</div>
              <div className="empty-state__sub">GET /status/service nicht erreichbar</div>
            </div>
          )}

          {/* Model config quick-view */}
          {!settingsLoading && routerSettings && (
            <div style={{ marginTop: '1.1rem', paddingTop: '0.85rem', borderTop: '1px solid var(--card-border)' }}>
              <div className="text--xs text--muted" style={{ fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '0.6rem' }}>
                Modell-Konfiguration
              </div>
              <div className="kv">
                <span className="kv__label">Default</span>
                <code className="kv__value kv__value--highlight">{routerSettings.default_model}</code>
              </div>
              <div className="kv">
                <span className="kv__label">Timeout</span>
                <span className="kv__value">{routerSettings.timeout}s</span>
              </div>
              <div className="kv">
                <span className="kv__label">API-Key</span>
                <span className="kv__value">{routerSettings.require_api_key ? 'erforderlich' : 'offen'}</span>
              </div>
            </div>
          )}
        </Card>
      </div>
    </Layout>
  );
}
