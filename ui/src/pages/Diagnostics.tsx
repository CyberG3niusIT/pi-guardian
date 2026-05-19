import { useEffect, useState } from 'react';
import { Card } from '../components/Card';
import { Layout } from '../components/Layout';
import { fetchHealth, fetchSettings, sendRoute, ApiRequestError } from '../api/client';
import { routerAddress, CONFIG } from '../config';
import type { HealthResponse, RouteResponse, ConnectionState, RouterSettings } from '../types';

interface Props {
  connectionState: ConnectionState;
  onRefresh: () => void;
}

/**
 * Diagnose-Seite
 *
 * SOFORT NUTZBAR:
 *   - Health-Check (GET /health)
 *   - Route-Test mit Prompt (POST /route)
 *   - Request/Response-Anzeige
 *   - Fehleranzeige
 */
export function Diagnostics({ connectionState, onRefresh }: Props) {
  // Health-Check State
  const [healthResult, setHealthResult] = useState<HealthResponse | null>(null);
  const [healthError, setHealthError] = useState<string | null>(null);
  const [healthLoading, setHealthLoading] = useState(false);
  const [healthTime, setHealthTime] = useState<number | null>(null);

  // Route-Test State
  const [prompt, setPrompt] = useState('');
  const [modelRole, setModelRole] = useState<'auto' | 'fast_model' | 'deep_model'>('auto');
  const [routeResult, setRouteResult] = useState<RouteResponse | null>(null);
  const [routeError, setRouteError] = useState<string | null>(null);
  const [routeLoading, setRouteLoading] = useState(false);
  const [routeTime, setRouteTime] = useState<number | null>(null);
  const [lastRequest, setLastRequest] = useState<string | null>(null);
  const [routerSettings, setRouterSettings] = useState<RouterSettings | null>(null);

  async function handleHealthCheck() {
    setHealthLoading(true);
    setHealthError(null);
    setHealthResult(null);
    const start = performance.now();
    try {
      const res = await fetchHealth();
      setHealthTime(Math.round(performance.now() - start));
      setHealthResult(res);
      onRefresh();
    } catch (err) {
      setHealthTime(Math.round(performance.now() - start));
      setHealthError(err instanceof ApiRequestError ? err.message : 'Unbekannter Fehler');
    } finally {
      setHealthLoading(false);
    }
  }

  async function loadRouterSettings() {
    try {
      const current = await fetchSettings();
      setRouterSettings(current);
    } catch {
      setRouterSettings(null);
    }
  }

  useEffect(() => {
    void loadRouterSettings();
  }, []);

  async function handleRouteTest() {
    if (!prompt.trim()) return;
    setRouteLoading(true);
    setRouteError(null);
    setRouteResult(null);

    const preferredModel =
      modelRole === 'deep_model'
        ? (routerSettings?.large_model ?? undefined)
        : modelRole === 'fast_model'
          ? (routerSettings?.default_model ?? CONFIG.defaultModel)
          : undefined;
    const requestBody = { prompt: prompt.trim(), preferred_model: preferredModel ?? null, stream: false };
    setLastRequest(JSON.stringify(requestBody, null, 2));

    const start = performance.now();
    try {
      const res = await sendRoute(prompt.trim(), preferredModel);
      setRouteTime(Math.round(performance.now() - start));
      setRouteResult(res);
    } catch (err) {
      setRouteTime(Math.round(performance.now() - start));
      setRouteError(err instanceof ApiRequestError ? err.message : 'Unbekannter Fehler');
    } finally {
      setRouteLoading(false);
    }
  }

  return (
    <Layout title="Test & Diagnose">
      <div className="grid grid--2">
        <Card title="Health Probe" tag="CONTROL">
          <p className="text--sm">Prüft GET /health auf dem Router.</p>
          <button
            className="btn"
            onClick={handleHealthCheck}
            disabled={healthLoading}
            style={{ marginTop: '0.5rem' }}
          >
            {healthLoading ? 'Prüfe…' : 'Health-Check ausführen'}
          </button>

          {healthResult && (
            <div className="result-box" style={{ marginTop: '1rem' }}>
              <div className="kv">
                <span className="kv__label">Status</span>
                <code className="kv__value kv__value--highlight">{healthResult.status}</code>
              </div>
              <div className="kv">
                <span className="kv__label">Antwortzeit</span>
                <span className="kv__value">{healthTime} ms</span>
              </div>
            </div>
          )}
          {healthError && (
            <div className="alert alert--error" style={{ marginTop: '1rem' }}>
              <strong>Fehler:</strong> {healthError}
              {healthTime !== null && <span className="text--sm"> ({healthTime} ms)</span>}
            </div>
          )}
        </Card>

        <Card title="Route Channel" tag="ROUTING">
          <div className="kv">
            <span className="kv__label">Ziel</span>
            <code className="kv__value">{routerAddress()}</code>
          </div>
          <div className="kv">
            <span className="kv__label">Proxy</span>
            <code className="kv__value">/api → Backend</code>
          </div>
          <div className="kv">
            <span className="kv__label">Zustand</span>
            <span className={`kv__value ${connectionState === 'connected' ? 'text--ok' : 'text--fail'}`}>
              {connectionState === 'connected' ? 'Erreichbar' : connectionState === 'checking' ? 'Prüfe…' : 'Nicht erreichbar'}
            </span>
          </div>
        </Card>
      </div>

      <div style={{ marginTop: '1.5rem' }}>
        <Card title="Route Console" tag="EXEC">
          <div className="grid grid--2">
            <div className="form-group">
              <label className="form-label">Prompt</label>
              <textarea
                className="form-input form-input--textarea"
                rows={4}
                value={prompt}
                onChange={(e) => setPrompt(e.target.value)}
                placeholder="z.B. Sage Hallo in einem Satz."
              />
            </div>
            <div>
              <div className="form-group">
                <label className="form-label">Modellrolle (optional)</label>
                <select
                  className="form-input"
                  value={modelRole}
                  onChange={(e) => setModelRole(e.target.value as 'auto' | 'fast_model' | 'deep_model')}
                >
                  <option value="auto">Automatisch</option>
                  <option value="fast_model">Fast Model</option>
                  <option value="deep_model">Deep Model</option>
                </select>
              </div>
              <button
                className="btn"
                onClick={handleRouteTest}
                disabled={routeLoading || !prompt.trim()}
                style={{ marginTop: '0.5rem' }}
              >
                {routeLoading ? 'Sende…' : 'POST /route senden'}
              </button>
            </div>
          </div>

          {/* Request anzeigen */}
          {lastRequest && (
            <div style={{ marginTop: '1rem' }}>
              <label className="form-label">Request Body</label>
              <pre className="code-block code-block--request">{lastRequest}</pre>
            </div>
          )}

          {/* Response anzeigen */}
          {routeResult && (
            <div className="result-box" style={{ marginTop: '1rem' }}>
              <div className="result-grid">
                <div className="kv">
                  <span className="kv__label">Request</span>
                  <code className="kv__value">{routeResult.request_id}</code>
                </div>
                <div className="kv">
                  <span className="kv__label">Execution Mode</span>
                  <code className="kv__value">{routeResult.execution_mode ?? 'llm'}</code>
                </div>
                <div className="kv">
                  <span className="kv__label">Modell</span>
                  <code className="kv__value">{routeResult.model}</code>
                </div>
                <div className="kv">
                  <span className="kv__label">Klassifikation</span>
                  <code className="kv__value">{routeResult.decision_classification ?? '–'}</code>
                </div>
                <div className="kv">
                  <span className="kv__label">Fertig</span>
                  <span className="kv__value">{routeResult.done ? 'Ja' : 'Nein'}</span>
                </div>
                <div className="kv">
                  <span className="kv__label">Antwortzeit</span>
                  <span className="kv__value">{routeResult.duration_ms || routeTime} ms</span>
                </div>
              </div>
              <div style={{ marginTop: '0.75rem' }}>
                <label className="form-label">Response</label>
                <pre className="code-block" style={{ whiteSpace: 'pre-wrap' }}>
                  {routeResult.response}
                </pre>
              </div>
              {routeResult.policy_trace && (
                <div style={{ marginTop: '1rem' }}>
                  <label className="form-label">Policy Trace</label>
                  <div className="trace-list">
                    <div className="trace-list__row">
                      <span className="trace-list__label">LLM</span>
                      <span className="trace-list__value">{routeResult.policy_trace.can_use_llm ? 'erlaubt' : 'gesperrt'}</span>
                    </div>
                    <div className="trace-list__row">
                      <span className="trace-list__label">Tools</span>
                      <span className="trace-list__value">
                        {routeResult.policy_trace.can_use_tools ? 'erlaubt' : 'gesperrt'}
                        {routeResult.policy_trace.tool_execution_allowed ? ' · aktiv im Pfad' : ''}
                      </span>
                    </div>
                    <div className="trace-list__row">
                      <span className="trace-list__label">Internet</span>
                      <span className="trace-list__value">
                        {routeResult.policy_trace.can_use_internet ? 'erlaubt' : 'gesperrt'}
                        {routeResult.policy_trace.internet_execution_allowed ? ' · vorbereiteter Pfad' : ''}
                      </span>
                    </div>
                  </div>
                </div>
              )}
              {routeResult.tool_executions && routeResult.tool_executions.length > 0 && (
                <div style={{ marginTop: '1rem' }}>
                  <label className="form-label">Tool Execution</label>
                  <div className="table-wrap">
                    <table className="table">
                      <thead>
                        <tr>
                          <th>Tool</th>
                          <th>Status</th>
                          <th>Dauer</th>
                          <th>Grund</th>
                        </tr>
                      </thead>
                      <tbody>
                        {routeResult.tool_executions.map((execution) => (
                          <tr key={`${execution.tool_name}-${execution.duration_ms}`}>
                            <td>
                              <strong>{execution.tool_name}</strong>
                              <div className="text--muted text--sm">
                                {JSON.stringify(execution.arguments)}
                              </div>
                            </td>
                            <td>{execution.success ? 'OK' : 'Fehler'}</td>
                            <td>{execution.duration_ms} ms</td>
                            <td>{execution.reason}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
              {routeResult.done_reason && (
                <div className="kv">
                  <span className="kv__label">Done reason</span>
                  <span className="kv__value">{routeResult.done_reason}</span>
                </div>
              )}
              {(routeResult.fairness_risk || routeResult.fairness_review_attempted) && (
                <div className="kv">
                  <span className="kv__label">Fairness</span>
                  <span className="kv__value">
                    {routeResult.fairness_risk ?? 'unknown'}
                  </span>
                </div>
              )}
              {routeResult.execution_error && (
                <div className="alert alert--warn" style={{ marginTop: '0.75rem' }}>
                  {routeResult.execution_error}
                </div>
              )}
            </div>
          )}

          {routeError && (
            <div className="alert alert--error" style={{ marginTop: '1rem' }}>
              <strong>Fehler:</strong> {routeError}
              {routeTime !== null && <span className="text--sm"> ({routeTime} ms)</span>}
            </div>
          )}
        </Card>
      </div>
    </Layout>
  );
}
