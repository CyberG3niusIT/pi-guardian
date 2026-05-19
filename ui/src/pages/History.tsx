import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { Card } from '../components/Card';
import { Layout } from '../components/Layout';
import { ApiRequestError, fetchRouteHistory } from '../api/client';
import type { RouteHistoryEntry } from '../types';

function pickValue(entry: RouteHistoryEntry, keys: string[]) {
  for (const key of keys) {
    const value = entry[key];
    if (value !== undefined && value !== null && value !== '') return String(value);
  }
  return '–';
}

function formatDateTime(value?: string | null) {
  if (!value) return '–';
  try {
    return new Date(value).toLocaleString('de-DE');
  } catch {
    return value;
  }
}

function EmptyCollectionState({ title, description }: { title: string; description: string }) {
  return (
    <div className="empty-state">
      <div className="empty-state__icon">□</div>
      <div className="empty-state__title">{title}</div>
      <div className="empty-state__sub">{description}</div>
    </div>
  );
}

function MetaItem({
  label,
  value,
  plain = false,
}: {
  label: string;
  value: ReactNode;
  plain?: boolean;
}) {
  return (
    <div className="entity-card__meta-item">
      <span className="entity-card__meta-label">{label}</span>
      <div className={`entity-card__meta-value${plain ? ' entity-card__meta-value--plain' : ''}`}>{value}</div>
    </div>
  );
}

function classificationBadge(classification?: string | null) {
  switch (classification) {
    case 'blocked':
      return 'badge badge--fail';
    case 'tool_required':
    case 'internet_required':
      return 'badge badge--warn';
    case 'llm_only':
      return 'badge badge--ok';
    default:
      return 'badge badge--idle';
  }
}

function executionBadge(status?: string | null) {
  switch (status) {
    case 'succeeded':
      return 'badge badge--ok';
    case 'failed':
      return 'badge badge--fail';
    case 'not_executed':
      return 'badge badge--idle';
    default:
      return 'badge badge--idle';
  }
}

export function History() {
  const [entries, setEntries] = useState<RouteHistoryEntry[]>([]);
  const [limit, setLimit] = useState(25);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshedAt, setRefreshedAt] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const nextEntries = await fetchRouteHistory(limit);
      setEntries(nextEntries);
      setRefreshedAt(new Date().toLocaleTimeString('de-DE'));
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : 'Verlauf konnte nicht geladen werden.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void load();
  }, [limit]);

  const hasAuthorizationIssue = useMemo(() => {
    return Boolean(error && /401|403|Unauthorized|nicht nutzen/i.test(error));
  }, [error]);

  return (
    <Layout title="History">
      <div className="grid grid--dense">
        <Card title="Verlauf" tag="API">
          <div className="kv">
            <span className="kv__label">Einträge</span>
            <span className="kv__value">{entries.length}</span>
          </div>
          <div className="kv">
            <span className="kv__label">Letztes Update</span>
            <span className="kv__value">{refreshedAt ?? '–'}</span>
          </div>
          <button className="btn btn--sm" onClick={() => void load()} disabled={loading}>
            {loading ? 'Lade…' : 'Neu laden'}
          </button>
        </Card>

        <Card title="Anzeige" tag="FILTER">
          <div className="form-group">
            <label className="form-label">Limit</label>
            <input
              className="form-input"
              type="number"
              min={1}
              max={200}
              value={limit}
              onChange={(e) => setLimit(Number(e.target.value) || 25)}
            />
          </div>
          <p className="text--muted text--sm">
            Die Ansicht greift auf `/history` zu. Falls dein API-Key diese Route nicht darf,
            wird die Seite den Fehler klar anzeigen.
          </p>
        </Card>

        <Card title="Browser-Hinweis" tag="AUTH">
          <p className="text--sm">
            Die Seite nutzt denselben gespeicherten Router API-Key wie die restliche UI.
            Wenn der Zugriff auf `history` gesperrt ist, brauchst du einen Schlüssel mit
            entsprechender Freigabe.
          </p>
        </Card>
      </div>

      {error && (
        <div className={`alert ${hasAuthorizationIssue ? 'alert--warn' : 'alert--error'}`} style={{ marginTop: '1.5rem' }}>
          <strong>Fehler:</strong> {error}
        </div>
      )}

      <div className="section">
        <Card title="Execution History" tag="AUDIT">
          {loading ? (
            <div className="empty-state">
              <div className="empty-state__icon">…</div>
              <div className="empty-state__title">History wird geladen</div>
              <div className="empty-state__sub">Chronologische Auditdaten werden aus dem Router gelesen.</div>
            </div>
          ) : entries.length === 0 ? (
            <EmptyCollectionState
              title="Keine Verlaufsdaten vorhanden"
              description="Es wurden noch keine Einträge gefunden oder dein API-Key darf diese Auditroute nicht lesen."
            />
          ) : (
            <div className="entity-card-grid entity-card-grid--history">
              {entries.map((entry, index) => {
                const reasons = entry.decision_reasons ?? [];
                const fairnessNotes = entry.fairness_notes ?? [];
                const tools = entry.executed_tools ?? [];
                return (
                  <Card
                    key={`${pickValue(entry, ['request_id', 'id', 'timestamp'])}-${index}`}
                    className="entity-card"
                    title={formatDateTime(entry.created_at)}
                    tag={entry.decision_classification ?? 'AUDIT'}
                    headerActions={
                      <>
                        <span className={classificationBadge(entry.decision_classification)}>
                          <span className="badge__dot" />
                          {entry.decision_classification ?? 'unbekannt'}
                        </span>
                        <span className={executionBadge(entry.execution_status)}>
                          <span className="badge__dot" />
                          {entry.execution_status ?? 'offen'}
                        </span>
                      </>
                    }
                  >
                    <div className="entity-card__stack">
                      <p className="entity-card__lead">{pickValue(entry, ['prompt_preview'])}</p>

                      <div className="entity-card__meta-grid">
                        <MetaItem label="Request ID" value={pickValue(entry, ['request_id', 'id'])} />
                        <MetaItem label="Client" value={pickValue(entry, ['client_name'])} plain />
                        <MetaItem label="Lane" value={entry.execution_mode ?? 'llm'} plain />
                        <MetaItem label="Dauer" value={pickValue(entry, ['duration_ms'])} />
                        <MetaItem label="Modell" value={pickValue(entry, ['model'])} />
                        <MetaItem label="Fehlercode" value={pickValue(entry, ['error_code'])} />
                      </div>

                      <div className="entity-card__section">
                        <span className="entity-card__section-title">Ausgeführte Tools</span>
                        {tools.length > 0 ? (
                          <div className="entity-card__pill-list">
                            {tools.map((toolName) => (
                              <span key={`${entry.id}-${toolName}`} className="agent-tool-pill">
                                {toolName}
                              </span>
                            ))}
                          </div>
                        ) : (
                          <div className="entity-card__empty">Keine Tool-Ausführung protokolliert.</div>
                        )}
                      </div>

                      {(reasons.length > 0 || fairnessNotes.length > 0 || entry.fairness_risk || entry.execution_error) && (
                        <div className="entity-card__section">
                          <span className="entity-card__section-title">Evidenz</span>
                          <div className="entity-card__note-list">
                            {entry.fairness_risk && (
                              <div className="entity-card__note">
                                <strong>Fairness-Risiko:</strong> {entry.fairness_risk}
                              </div>
                            )}
                            {reasons.map((reason, reasonIndex) => (
                              <div key={`${entry.id}-reason-${reasonIndex}`} className="entity-card__note">
                                <strong>Entscheidung:</strong> {reason}
                              </div>
                            ))}
                            {fairnessNotes.map((note, noteIndex) => (
                              <div key={`${entry.id}-fairness-${noteIndex}`} className="entity-card__note">
                                <strong>Fairness:</strong> {note}
                              </div>
                            ))}
                            {entry.execution_error && (
                              <div className="entity-card__note entity-card__note--danger">
                                <strong>Execution Error:</strong> {entry.execution_error}
                              </div>
                            )}
                          </div>
                        </div>
                      )}
                    </div>
                  </Card>
                );
              })}
            </div>
          )}
        </Card>
      </div>
    </Layout>
  );
}
