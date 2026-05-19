import { useEffect, useState } from 'react';
import { Card } from '../components/Card';
import { StatusBadge } from '../components/StatusBadge';
import { Layout } from '../components/Layout';
import { ApiRequestError, fetchServiceStatus, fetchSettings, fetchAgents, fetchMemoryRuns } from '../api/client';
import { CONFIG } from '../config';
import type { RouterSettings, ServiceStatus, AgentDefinition, MemoryRunSummary, ConnectionState } from '../types';

interface Props {
  connectionState: ConnectionState;
  lastCheck: string | null;
  healthError: string | null;
  onRefresh: () => void;
}

export function Dashboard({ connectionState, lastCheck, healthError, onRefresh }: Props) {
  const [serviceStatus, setServiceStatus] = useState<ServiceStatus | null>(null);
  const [serviceError, setServiceError] = useState<string | null>(null);
  const [serviceLoading, setServiceLoading] = useState(false);
  const [routerSettings, setRouterSettings] = useState<RouterSettings | null>(null);
  const [agents, setAgents] = useState<AgentDefinition[] | null>(null);
  const [memoryRuns, setMemoryRuns] = useState<MemoryRunSummary[] | null>(null);

  async function loadAll() {
    setServiceLoading(true);
    setServiceError(null);
    try {
      const [status, settings, agentList, runs] = await Promise.allSettled([
        fetchServiceStatus(),
        fetchSettings(),
        fetchAgents(),
        fetchMemoryRuns(),
      ]);
      if (status.status === 'fulfilled') setServiceStatus(status.value);
      else setServiceError(status.reason instanceof ApiRequestError ? status.reason.message : 'Fehler beim Laden');
      if (settings.status === 'fulfilled') setRouterSettings(settings.value);
      if (agentList.status === 'fulfilled') setAgentList(agentList.value);
      if (runs.status === 'fulfilled') setMemoryRuns(runs.value);
    } finally {
      setServiceLoading(false);
    }
  }

  function setAgentList(list: AgentDefinition[]) { setAgents(list); }

  useEffect(() => { void loadAll(); }, []);

  const activeAgents = agents?.filter((a) => a.settings?.active !== false).length ?? 0;
  const totalAgents  = agents?.length ?? 0;
  const memoryCount  = memoryRuns?.length ?? 0;

  return (
    <Layout title="Dashboard">
      {/* ── Hero stat cards ── */}
      <div className="grid grid--4" style={{ marginBottom: '1.5rem' }}>
        <div className="stat-card">
          <svg className="stat-card__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><circle cx="9" cy="7" r="4"/><path d="M3 21v-2a4 4 0 0 1 4-4h4a4 4 0 0 1 4 4v2"/><path d="M16 3.13a4 4 0 0 1 0 7.75"/><path d="M21 21v-2a4 4 0 0 0-3-3.87"/></svg>
          <div className="stat-card__label">Aktive Agenten</div>
          <div className={`stat-card__value${activeAgents > 0 ? ' stat-card__value--indigo' : ''}`}>
            {activeAgents}
          </div>
          <div className="stat-card__sub">von {totalAgents} gesamt</div>
        </div>

        <div className="stat-card">
          <svg className="stat-card__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><ellipse cx="12" cy="5" rx="9" ry="3"/><path d="M3 5v14a9 3 0 0 0 18 0V5"/><path d="M3 12a9 3 0 0 0 18 0"/></svg>
          <div className="stat-card__label">Memory-Runs</div>
          <div className={`stat-card__value${memoryCount > 0 ? ' stat-card__value--violet' : ''}`}>
            {memoryCount}
          </div>
          <div className="stat-card__sub">gespeicherte Läufe</div>
        </div>

        <div className="stat-card">
          <svg className="stat-card__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><rect x="4" y="4" width="16" height="16" rx="2"/><rect x="9" y="9" width="6" height="6"/><path d="M9 2v2M15 2v2M9 20v2M15 20v2M2 9h2M2 15h2M20 9h2M20 15h2"/></svg>
          <div className="stat-card__label">Standardmodell</div>
          <div className="stat-card__value stat-card__value--emerald" style={{ fontSize: '1.05rem', letterSpacing: '-0.01em' }}>
            {routerSettings?.default_model ?? CONFIG.defaultModel}
          </div>
          <div className="stat-card__sub">Ollama (lokal)</div>
        </div>

        <div className="stat-card">
          <svg className="stat-card__icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"/></svg>
          <div className="stat-card__label">Uptime</div>
          <div className="stat-card__value" style={{ fontSize: '1.1rem', letterSpacing: '-0.01em' }}>
            {serviceLoading ? '…' : (serviceStatus?.uptime ?? '–')}
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

          <div style={{ marginTop: '1.1rem', paddingTop: '0.85rem', borderTop: '1px solid var(--card-border)' }}>
            <div className="text--xs text--muted" style={{ fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '0.6rem' }}>
              Routing-Lanes
            </div>
            <ul className="gap-list">
              <li><code>llm_only</code> — Direktpfad mit Fairness-Prüfung</li>
              <li><code>tool_required</code> — Read-Only Tools via /route</li>
              <li><code>internet_required</code> — erkannt, kontrollierter Stop</li>
            </ul>
          </div>

          <div style={{ marginTop: '1rem' }}>
            <button
              className="btn btn--sm btn--ghost"
              onClick={() => { onRefresh(); void loadAll(); }}
              disabled={serviceLoading}
            >
              {serviceLoading ? 'Lädt…' : 'Health prüfen'}
            </button>
          </div>
        </Card>

        {/* System Health */}
        <Card title="System Health" tag="LIVE">
          {serviceLoading && (
            <div className="text--muted text--sm">Lade Dienststatus…</div>
          )}
          {serviceError && !serviceLoading && (
            <div className="alert alert--warn">{serviceError}</div>
          )}
          {serviceStatus && !serviceLoading && (
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
                  {serviceStatus.cpu_percent != null ? `${serviceStatus.cpu_percent.toFixed(1)} %` : '–'}
                </span>
              </div>
              <div className="kv">
                <span className="kv__label">Memory</span>
                <span className="kv__value">{serviceStatus.memory_usage ?? '–'}</span>
              </div>
            </>
          )}

          {routerSettings && (
            <div style={{ marginTop: '1.1rem', paddingTop: '0.85rem', borderTop: '1px solid var(--card-border)' }}>
              <div className="text--xs text--muted" style={{ fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '0.6rem' }}>
                Modell-Konfiguration
              </div>
              <div className="kv">
                <span className="kv__label">Fast Model</span>
                <code className="kv__value kv__value--highlight">{routerSettings.default_model}</code>
              </div>
              <div className="kv">
                <span className="kv__label">Deep Model</span>
                <code className="kv__value kv__value--highlight">{routerSettings.large_model ?? '–'}</code>
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
