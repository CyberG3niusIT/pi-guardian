import { useEffect, useState } from 'react';
import type { ReactNode } from 'react';
import { Card } from '../components/Card';
import { Layout } from '../components/Layout';
import {
  ApiRequestError,
  fetchActions,
  fetchAgents,
  fetchMemoryFeedback,
  fetchMemoryIncidents,
  fetchMemoryKnowledge,
  fetchMemoryRuns,
  fetchSkills,
} from '../api/client';
import type {
  ActionDefinition,
  AgentDefinition,
  MemoryFeedbackEntryRead,
  MemoryIncidentRead,
  MemoryKnowledgeEntryRead,
  MemoryRunSummary,
  SkillDefinition,
} from '../types';

interface MemoryNote {
  id: string;
  title: string;
  content: string;
  created_at: string;
}

const MEMORY_STORAGE_KEY = 'pi-guardian.memory.notes';

function readNotes(): MemoryNote[] {
  if (typeof window === 'undefined') return [];
  try {
    const raw = window.localStorage.getItem(MEMORY_STORAGE_KEY);
    return raw ? (JSON.parse(raw) as MemoryNote[]) : [];
  } catch {
    return [];
  }
}

function writeNotes(notes: MemoryNote[]) {
  if (typeof window === 'undefined') return;
  window.localStorage.setItem(MEMORY_STORAGE_KEY, JSON.stringify(notes));
}

function formatDateTime(value?: string | null): string {
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

export function Memory() {
  const [agents, setAgents] = useState<AgentDefinition[]>([]);
  const [skills, setSkills] = useState<SkillDefinition[]>([]);
  const [actions, setActions] = useState<ActionDefinition[]>([]);
  const [runs, setRuns] = useState<MemoryRunSummary[]>([]);
  const [incidents, setIncidents] = useState<MemoryIncidentRead[]>([]);
  const [knowledge, setKnowledge] = useState<MemoryKnowledgeEntryRead[]>([]);
  const [feedback, setFeedback] = useState<MemoryFeedbackEntryRead[]>([]);
  const [notes, setNotes] = useState<MemoryNote[]>(() => readNotes());
  const [title, setTitle] = useState('');
  const [content, setContent] = useState('');
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshedAt, setRefreshedAt] = useState<string | null>(null);

  async function load() {
    setLoading(true);
    setError(null);

    const results = await Promise.allSettled([
      fetchAgents(),
      fetchSkills(),
      fetchActions(),
      fetchMemoryRuns(),
      fetchMemoryIncidents(),
      fetchMemoryKnowledge(),
      fetchMemoryFeedback(),
    ]);

    const [agentsRes, skillsRes, actionsRes, runsRes, incidentsRes, knowledgeRes, feedbackRes] = results;

    if (agentsRes.status === 'fulfilled') setAgents(agentsRes.value);
    if (skillsRes.status === 'fulfilled') setSkills(skillsRes.value);
    if (actionsRes.status === 'fulfilled') setActions(actionsRes.value);
    if (runsRes.status === 'fulfilled') setRuns(runsRes.value);
    if (incidentsRes.status === 'fulfilled') setIncidents(incidentsRes.value);
    if (knowledgeRes.status === 'fulfilled') setKnowledge(knowledgeRes.value);
    if (feedbackRes.status === 'fulfilled') setFeedback(feedbackRes.value);

    const rejected = results.find((item) => item.status === 'rejected');
    if (rejected && rejected.status === 'rejected') {
      const reason = rejected.reason;
      setError(reason instanceof ApiRequestError ? reason.message : 'Memory-Daten konnten nicht vollständig geladen werden.');
    }

    setRefreshedAt(new Date().toLocaleTimeString('de-DE'));
    setLoading(false);
  }

  useEffect(() => {
    void load();
  }, []);

  function addNote() {
    if (!title.trim() || !content.trim()) return;
    const nextNotes = [
      {
        id: `note-${Date.now()}`,
        title: title.trim(),
        content: content.trim(),
        created_at: new Date().toISOString(),
      },
      ...notes,
    ];
    setNotes(nextNotes);
    writeNotes(nextNotes);
    setTitle('');
    setContent('');
  }

  function removeNote(id: string) {
    const nextNotes = notes.filter((note) => note.id !== id);
    setNotes(nextNotes);
    writeNotes(nextNotes);
  }

  return (
    <Layout title="Memory">
      <div className="grid grid--dense">
        <Card title="Memory Snapshot" tag="LIVE">
          <div className="kv">
            <span className="kv__label">Runs</span>
            <span className="kv__value">{runs.length}</span>
          </div>
          <div className="kv">
            <span className="kv__label">Incidents</span>
            <span className="kv__value">{incidents.length}</span>
          </div>
          <div className="kv">
            <span className="kv__label">Knowledge</span>
            <span className="kv__value">{knowledge.length}</span>
          </div>
          <div className="kv">
            <span className="kv__label">Feedback</span>
            <span className="kv__value">{feedback.length}</span>
          </div>
          <div className="kv">
            <span className="kv__label">Letztes Update</span>
            <span className="kv__value">{refreshedAt ?? '–'}</span>
          </div>
          <button className="btn btn--sm" onClick={() => void load()} disabled={loading}>
            {loading ? 'Lade…' : 'Neu laden'}
          </button>
        </Card>

        <Card title="Registry-Snapshot" tag="LIVE">
          <div className="kv">
            <span className="kv__label">Agenten</span>
            <span className="kv__value">{agents.length}</span>
          </div>
          <div className="kv">
            <span className="kv__label">Skills</span>
            <span className="kv__value">{skills.length}</span>
          </div>
          <div className="kv">
            <span className="kv__label">Actions</span>
            <span className="kv__value">{actions.length}</span>
          </div>
          <p className="text--sm" style={{ marginTop: '0.75rem' }}>
            Die Registry kommt aus dem Router-Backend. Sie ist unabhängig von den
            Memory-Runs und zeigt den aktuellen Freigabestand.
          </p>
        </Card>

        <Card title="Browser-Notizen" tag="LOCAL">
          <div className="kv">
            <span className="kv__label">Notizen</span>
            <span className="kv__value">{notes.length}</span>
          </div>
          <p className="text--muted text--sm" style={{ marginTop: '0.75rem' }}>
            Diese Notizen bleiben lokal im Browser erhalten und helfen beim operativen Arbeiten.
          </p>
        </Card>
      </div>

      {error && (
        <div className="alert alert--warn" style={{ marginTop: '1.5rem' }}>
          <strong>Teilfehler:</strong> {error}
        </div>
      )}

      <div className="grid grid--2 section">
        <Card title="Aktuelle Runs" tag="API">
          {loading ? (
            <div className="empty-state">
              <div className="empty-state__icon">…</div>
              <div className="empty-state__title">Runs werden geladen</div>
              <div className="empty-state__sub">Chronologische Ausführungen werden aus dem Router gelesen.</div>
            </div>
          ) : runs.length === 0 ? (
            <EmptyCollectionState
              title="Keine Memory-Runs vorhanden"
              description="Sobald Agent-Läufe in der Memory-API ankommen, erscheinen sie hier als Karten."
            />
          ) : (
            <div className="entity-card-grid entity-card-grid--compact">
              {runs.map((run) => (
                <Card
                  key={run.run_id}
                  className="entity-card"
                  title={run.agent_name}
                  tag={run.success ? 'SUCCESS' : 'FAILED'}
                  headerActions={
                    <span className={`badge ${run.success ? 'badge--ok' : 'badge--fail'}`}>
                      <span className="badge__dot" />
                      {run.success ? 'Erfolgreich' : 'Fehlgeschlagen'}
                    </span>
                  }
                >
                  <div className="entity-card__stack">
                    <p className="entity-card__lead">{run.input || 'Kein Input gespeichert.'}</p>
                    <div className="entity-card__meta-grid">
                      <MetaItem label="Gestartet" value={formatDateTime(run.started_at)} plain />
                      <MetaItem label="Beendet" value={formatDateTime(run.finished_at)} plain />
                      <MetaItem label="Modell" value={run.used_model ?? '–'} />
                      <MetaItem label="Run ID" value={run.run_id} />
                    </div>
                    {run.final_answer && (
                      <div className="entity-card__section">
                        <span className="entity-card__section-title">Final Answer</span>
                        <div className="entity-card__note">{run.final_answer}</div>
                      </div>
                    )}
                  </div>
                </Card>
              ))}
            </div>
          )}
        </Card>

        <Card title="Incidents" tag="API">
          {loading ? (
            <div className="empty-state">
              <div className="empty-state__icon">…</div>
              <div className="empty-state__title">Incidents werden geladen</div>
              <div className="empty-state__sub">Bestehende Vorfälle bleiben chronologisch unverändert.</div>
            </div>
          ) : incidents.length === 0 ? (
            <EmptyCollectionState
              title="Keine Incidents gespeichert"
              description="Es gibt aktuell keine Incident-Einträge in der Memory-API."
            />
          ) : (
            <div className="entity-card-grid entity-card-grid--compact">
              {incidents.map((incident) => (
                <Card
                  key={incident.id}
                  className="entity-card"
                  title={incident.title}
                  tag={incident.severity}
                  headerActions={
                    <span className={`badge ${incident.status === 'closed' ? 'badge--ok' : 'badge--warn'}`}>
                      <span className="badge__dot" />
                      {incident.status}
                    </span>
                  }
                >
                  <div className="entity-card__stack">
                    <p className="entity-card__lead">{incident.summary || incident.description || 'Keine Zusammenfassung vorhanden.'}</p>
                    <div className="entity-card__meta-grid">
                      <MetaItem label="Erstellt" value={formatDateTime(incident.created_at)} plain />
                      <MetaItem label="Aktualisiert" value={formatDateTime(incident.updated_at)} plain />
                      <MetaItem label="Findings" value={incident.findings.length} plain />
                      <MetaItem label="Severity" value={incident.severity} plain />
                    </div>
                    {incident.findings.length > 0 && (
                      <div className="entity-card__section">
                        <span className="entity-card__section-title">Findings</span>
                        <div className="entity-card__note-list">
                          {incident.findings.slice(0, 3).map((finding) => (
                            <div key={finding.id} className="entity-card__note">
                              {finding.content}
                            </div>
                          ))}
                        </div>
                      </div>
                    )}
                  </div>
                </Card>
              ))}
            </div>
          )}
        </Card>
      </div>

      <div className="grid grid--2 section">
        <Card title="Knowledge" tag="API">
          {loading ? (
            <div className="empty-state">
              <div className="empty-state__icon">…</div>
              <div className="empty-state__title">Knowledge wird geladen</div>
              <div className="empty-state__sub">Bestätigte und unbestätigte Wissenseinträge erscheinen als Karten.</div>
            </div>
          ) : knowledge.length === 0 ? (
            <EmptyCollectionState
              title="Keine Knowledge-Einträge gespeichert"
              description="Es liegen noch keine Wissenseinträge aus dem Router vor."
            />
          ) : (
            <div className="entity-card-grid entity-card-grid--compact">
              {knowledge.map((entry) => (
                <Card
                  key={entry.id}
                  className="entity-card"
                  title={entry.title}
                  tag={entry.category}
                  headerActions={
                    <span className={`badge ${entry.confirmed ? 'badge--ok' : 'badge--idle'}`}>
                      <span className="badge__dot" />
                      {entry.confirmed ? 'Bestätigt' : 'Unbestätigt'}
                    </span>
                  }
                >
                  <div className="entity-card__stack">
                    <p className="entity-card__lead">{entry.probable_cause || entry.content}</p>
                    <div className="entity-card__meta-grid">
                      <MetaItem label="Confidence" value={entry.confidence ?? '–'} plain />
                      <MetaItem label="Erstellt" value={formatDateTime(entry.created_at)} plain />
                    </div>
                    <div className="entity-card__section">
                      <span className="entity-card__section-title">Inhalt</span>
                      <div className="entity-card__note">{entry.content}</div>
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </Card>

        <Card title="Feedback" tag="API">
          {loading ? (
            <div className="empty-state">
              <div className="empty-state__icon">…</div>
              <div className="empty-state__title">Feedback wird geladen</div>
              <div className="empty-state__sub">Verknüpfte Run-Rückmeldungen bleiben in API-Reihenfolge erhalten.</div>
            </div>
          ) : feedback.length === 0 ? (
            <EmptyCollectionState
              title="Kein Feedback gespeichert"
              description="Der Router hat aktuell keine Feedback-Einträge zurückgeliefert."
            />
          ) : (
            <div className="entity-card-grid entity-card-grid--compact">
              {feedback.map((entry) => (
                <Card
                  key={entry.id}
                  className="entity-card"
                  title={entry.verdict ?? 'Feedback'}
                  tag={`Rating ${entry.rating}`}
                  headerActions={
                    <span className={`badge ${entry.rating >= 4 ? 'badge--ok' : entry.rating >= 2 ? 'badge--warn' : 'badge--fail'}`}>
                      <span className="badge__dot" />
                      {entry.created_by || 'Unbekannt'}
                    </span>
                  }
                >
                  <div className="entity-card__stack">
                    <p className="entity-card__lead">{entry.comment || 'Kein Kommentar hinterlegt.'}</p>
                    <div className="entity-card__meta-grid">
                      <MetaItem label="Run ID" value={entry.run_id} />
                      <MetaItem label="Related Run" value={entry.related_run_id ?? '–'} />
                      <MetaItem label="Erstellt" value={formatDateTime(entry.created_at)} plain />
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </Card>
      </div>

      <div className="grid grid--2 section">
        <Card title="Persistierte Notizen" tag="LOCAL">
          <div className="form-group">
            <label className="form-label">Titel</label>
            <input
              className="form-input"
              value={title}
              onChange={(e) => setTitle(e.target.value)}
              placeholder="Beobachtung oder Erkenntnis"
            />
          </div>
          <div className="form-group">
            <label className="form-label">Inhalt</label>
            <textarea
              className="form-input form-input--textarea"
              rows={4}
              value={content}
              onChange={(e) => setContent(e.target.value)}
              placeholder="Kurze operative Notiz"
            />
          </div>
          <button className="btn" onClick={addNote}>
            Notiz speichern
          </button>

          <div style={{ marginTop: '1rem' }}>
            {notes.length === 0 ? (
              <EmptyCollectionState
                title="Noch keine lokalen Notizen gespeichert"
                description="Neue Browser-Notizen erscheinen direkt darunter als lokale Karten."
              />
            ) : (
              <div className="entity-card-grid entity-card-grid--compact">
                {notes.map((note) => (
                  <Card
                    key={note.id}
                    className="entity-card"
                    title={note.title}
                    tag="LOCAL"
                    headerActions={<span className="text--muted text--sm">{formatDateTime(note.created_at)}</span>}
                  >
                    <div className="entity-card__stack">
                      <p className="entity-card__lead">{note.content}</p>
                      <div className="entity-card__footer">
                        <div className="text--muted text--sm">Nur im aktuellen Browser gespeichert</div>
                        <div className="entity-card__actions">
                          <button className="btn btn--sm btn--ghost" onClick={() => removeNote(note.id)}>
                            Löschen
                          </button>
                        </div>
                      </div>
                    </div>
                  </Card>
                ))}
              </div>
            )}
          </div>
        </Card>

        <Card title="Registry-Details" tag="API">
          {loading ? (
            <div className="empty-state">
              <div className="empty-state__icon">…</div>
              <div className="empty-state__title">Registry wird geladen</div>
              <div className="empty-state__sub">Agenten, Skills und Actions werden für die Freigabesicht gesammelt.</div>
            </div>
          ) : agents.length === 0 && skills.length === 0 && actions.length === 0 ? (
            <EmptyCollectionState
              title="Keine Registry-Daten verfügbar"
              description="Weder Agenten noch Skills oder Actions konnten geladen werden."
            />
          ) : (
            <div className="entity-card-grid entity-card-grid--compact">
              {agents.map((agent) => (
                <Card
                  key={`agent-${agent.name}`}
                  className="entity-card"
                  title={agent.name}
                  tag="AGENT"
                  headerActions={
                    <span className={`badge ${agent.enabled === false ? 'badge--fail' : 'badge--ok'}`}>
                      <span className="badge__dot" />
                      {agent.enabled === false ? 'Inaktiv' : 'Aktiv'}
                    </span>
                  }
                >
                  <div className="entity-card__stack">
                    <p className="entity-card__lead">{agent.description || 'Keine Beschreibung vorhanden.'}</p>
                    <div className="entity-card__meta-grid">
                      <MetaItem label="Read only" value={agent.read_only ? 'Ja' : 'Nein'} plain />
                      <MetaItem label="Tools" value={agent.allowed_tools.length} plain />
                    </div>
                  </div>
                </Card>
              ))}

              {skills.map((skill) => (
                <Card
                  key={`skill-${skill.name}`}
                  className="entity-card"
                  title={skill.name}
                  tag="SKILL"
                  headerActions={
                    <span className={`badge ${skill.enabled === false ? 'badge--fail' : 'badge--ok'}`}>
                      <span className="badge__dot" />
                      {skill.enabled === false ? 'Inaktiv' : 'Aktiv'}
                    </span>
                  }
                >
                  <div className="entity-card__stack">
                    <p className="entity-card__lead">{skill.description || 'Keine Beschreibung vorhanden.'}</p>
                    <div className="entity-card__meta-grid">
                      <MetaItem label="Read only" value={skill.read_only ? 'Ja' : 'Nein'} plain />
                      <MetaItem label="Tools" value={skill.allowed_tools.length} plain />
                    </div>
                  </div>
                </Card>
              ))}

              {actions.map((action) => (
                <Card key={`action-${action.name}`} className="entity-card" title={action.name} tag="ACTION">
                  <div className="entity-card__stack">
                    <p className="entity-card__lead">{action.description || 'Keine Beschreibung vorhanden.'}</p>
                    <div className="entity-card__meta-grid">
                      <MetaItem label="Targets" value={action.allowed_targets.length} plain />
                      <MetaItem label="Approval" value={action.requires_approval ? 'Ja' : 'Nein'} plain />
                    </div>
                  </div>
                </Card>
              ))}
            </div>
          )}
        </Card>
      </div>
    </Layout>
  );
}
