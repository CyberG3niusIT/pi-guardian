import { useState, useEffect, useCallback } from 'react';
import { Card } from '../components/Card';
import { Layout } from '../components/Layout';
import { useApiCall } from '../hooks/useApi';
import {
  fetchClients,
  fetchIntegrationGuide,
  createClient,
  updateClient,
  deleteClient,
  ApiRequestError,
} from '../api/client';
import type { ClientEntry, IntegrationGuide } from '../types';

type FormData = {
  name: string;
  description: string;
  active: boolean;
  allowed_ip: string;
  allowed_routes: string[];
};

const DEFAULT_ALLOWED_ROUTES = ['/route', '/health', '/api/tags', '/api/generate', '/api/chat'];

const EMPTY_FORM: FormData = {
  name: '',
  description: '',
  active: true,
  allowed_ip: '192.168.50.0/24',
  allowed_routes: [...DEFAULT_ALLOWED_ROUTES],
};

function clientToForm(client: ClientEntry): FormData {
  return {
    name: client.name,
    description: client.description,
    active: client.active,
    allowed_ip: client.allowed_ip,
    allowed_routes:
      client.allowed_routes.length > 0 ? [...client.allowed_routes] : [...DEFAULT_ALLOWED_ROUTES],
  };
}

/** Masked API key with <details> reveal */
function ApiKeyField({ apiKey }: { apiKey?: string }) {
  if (!apiKey) return <span className="text--faint">–</span>;
  const prefix = apiKey.slice(0, 4);
  const masked = prefix + '•'.repeat(24);
  return (
    <span className="api-key">
      <details>
        <summary>{masked}</summary>
        <span style={{ display: 'block', marginTop: '0.2rem', color: 'var(--text-body)', userSelect: 'all' }}>
          {apiKey}
        </span>
      </details>
    </span>
  );
}

/** IP allowlist as tag chips */
function IpTags({ ip }: { ip: string }) {
  if (!ip) return <span className="text--faint">–</span>;
  const parts = ip.split(',').map((s) => s.trim()).filter(Boolean);
  return (
    <div className="ip-tags">
      {parts.map((p) => (
        <span key={p} className="ip-tag">{p}</span>
      ))}
    </div>
  );
}

export function Clients() {
  const [clients, setClients] = useState<ClientEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showForm, setShowForm] = useState(false);
  const [editingClientId, setEditingClientId] = useState<number | null>(null);
  const [form, setForm] = useState<FormData>({ ...EMPTY_FORM });
  const [submitting, setSubmitting] = useState(false);
  const [actionId, setActionId] = useState<number | null>(null);
  const [newApiKey, setNewApiKey] = useState<string | null>(null);

  const {
    data: integrationGuide,
    loading: integrationLoading,
    error: integrationError,
    execute: loadIntegrationGuide,
  } = useApiCall<IntegrationGuide>();

  const isEditing = editingClientId !== null;

  const loadClients = useCallback(async () => {
    setLoading(true); setError(null);
    try {
      setClients(await fetchClients());
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : 'Fehler beim Laden der Clients');
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadClients();
  }, [loadClients]);

  useEffect(() => {
    loadIntegrationGuide(fetchIntegrationGuide).catch(() => {});
  }, [loadIntegrationGuide]);

  function openCreateForm() {
    setEditingClientId(null);
    setForm({ ...EMPTY_FORM });
    setShowForm(true);
    setNewApiKey(null);
    setError(null);
  }

  function openEditForm(client: ClientEntry) {
    setEditingClientId(client.id);
    setForm(clientToForm(client));
    setShowForm(true);
    setNewApiKey(null);
    setError(null);
  }

  function closeForm() {
    setShowForm(false);
    setEditingClientId(null);
    setForm({ ...EMPTY_FORM });
  }

  async function handleSubmit() {
    if (!form.name.trim()) return;
    setSubmitting(true); setError(null);
    try {
      const payload = {
        name: form.name,
        description: form.description,
        active: form.active,
        allowed_ip: form.allowed_ip,
        allowed_routes: form.allowed_routes,
      };
      if (isEditing && editingClientId !== null) {
        const updated = await updateClient(editingClientId, payload);
        setClients((prev) => prev.map((c) => (c.id === updated.id ? updated : c)));
      } else {
        const created = await createClient(payload);
        setClients((prev) => [created, ...prev]);
        if (created.api_key) setNewApiKey(created.api_key);
      }
      closeForm();
    } catch (err) {
      setError(
        err instanceof ApiRequestError
          ? err.message
          : isEditing ? 'Fehler beim Aktualisieren' : 'Fehler beim Erstellen'
      );
    } finally {
      setSubmitting(false);
    }
  }

  async function handleToggle(c: ClientEntry) {
    setActionId(c.id); setError(null);
    try {
      const updated = await updateClient(c.id, { active: !c.active });
      setClients((prev) => prev.map((x) => (x.id === updated.id ? updated : x)));
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : 'Fehler beim Aktualisieren');
    } finally { setActionId(null); }
  }

  async function handleDelete(c: ClientEntry) {
    if (!confirm(`Client "${c.name}" wirklich löschen?`)) return;
    setActionId(c.id); setError(null);
    try {
      await deleteClient(c.id);
      setClients((prev) => prev.filter((x) => x.id !== c.id));
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : 'Fehler beim Löschen');
    } finally { setActionId(null); }
  }

  return (
    <Layout title="Clients">
      {/* ── New API key reveal ── */}
      {newApiKey && (
        <div className="alert alert--ok" style={{ marginBottom: '1.25rem' }}>
          <strong>Neuer API-Key (einmalig sichtbar):</strong>
          <br />
          <code style={{ userSelect: 'all', fontSize: '0.88rem', display: 'block', marginTop: '0.35rem' }}>
            {newApiKey}
          </code>
          <button
            className="btn btn--sm btn--ghost"
            style={{ marginTop: '0.6rem' }}
            onClick={() => setNewApiKey(null)}
          >
            Verstanden
          </button>
        </div>
      )}

      {error && (
        <div className="alert alert--error" style={{ marginBottom: '1.25rem' }}>{error}</div>
      )}

      {/* ── Client table ── */}
      <Card title="Registrierte Clients" tag="LIVE">
        {loading ? (
          <div className="text--muted text--sm">Lade Clients…</div>
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Name</th>
                <th>API-Key</th>
                <th>IP-Allowlist</th>
                <th>Routen</th>
                <th>Status</th>
                <th>Aktionen</th>
              </tr>
            </thead>
            <tbody>
              {clients.map((c) => (
                <tr key={c.id}>
                  <td>
                    <strong style={{ fontSize: '0.85rem' }}>{c.name}</strong>
                    {c.description && (
                      <div className="text--faint text--xs" style={{ marginTop: '0.1rem' }}>
                        {c.description}
                      </div>
                    )}
                  </td>
                  <td>
                    <ApiKeyField apiKey={(c as ClientEntry & { api_key?: string }).api_key} />
                  </td>
                  <td>
                    <IpTags ip={c.allowed_ip} />
                  </td>
                  <td>
                    <div style={{ display: 'flex', gap: '0.25rem', flexWrap: 'wrap', maxWidth: '220px' }}>
                      {c.allowed_routes.map((r) => (
                        <span
                          key={r}
                          style={{
                            display: 'inline-block',
                            fontFamily: 'var(--font-mono)',
                            fontSize: '0.68rem',
                            color: 'var(--indigo-500)',
                            background: 'var(--indigo-dim)',
                            border: '1px solid rgba(99,102,241,0.14)',
                            borderRadius: 'var(--radius-sm)',
                            padding: '0.08rem 0.35rem',
                          }}
                        >
                          {r}
                        </span>
                      ))}
                    </div>
                  </td>
                  <td>
                    {c.active ? (
                      <span className="badge badge--ok"><span className="badge__dot" />Aktiv</span>
                    ) : (
                      <span className="badge badge--disabled"><span className="badge__dot" />Inaktiv</span>
                    )}
                  </td>
                  <td>
                    <div className="btn-group">
                      <button
                        className="btn btn--xs btn--ghost"
                        onClick={() => openEditForm(c)}
                        disabled={actionId === c.id}
                      >Bearbeiten</button>
                      <button
                        className="btn btn--xs btn--ghost"
                        onClick={() => handleToggle(c)}
                        disabled={actionId === c.id}
                      >
                        {actionId === c.id ? '…' : c.active ? 'Deaktiv.' : 'Aktivieren'}
                      </button>
                      <button
                        className="btn btn--xs btn--danger"
                        onClick={() => handleDelete(c)}
                        disabled={actionId === c.id}
                      >✕</button>
                    </div>
                  </td>
                </tr>
              ))}
              {clients.length === 0 && (
                <tr>
                  <td colSpan={6}>
                    <div className="empty-state">
                      <div className="empty-state__icon">⊞</div>
                      <div className="empty-state__title">Keine Clients registriert</div>
                      <div className="empty-state__sub">Füge den ersten Client hinzu</div>
                    </div>
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        )}

        <div className="btn-group" style={{ marginTop: '1rem' }}>
          <button
            className={`btn ${showForm ? 'btn--ghost' : ''}`}
            onClick={showForm ? closeForm : openCreateForm}
            disabled={loading}
          >
            {showForm ? '↩ Abbrechen' : '+ Client hinzufügen'}
          </button>
        </div>

        {/* ── Form ── */}
        {showForm && (
          <div className="form-section" style={{ marginTop: '1rem' }}>
            <div style={{ marginBottom: '0.85rem', display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
              <span style={{ fontWeight: 700, fontSize: '0.82rem', color: 'var(--text-heading)' }}>
                {isEditing ? 'Client bearbeiten' : 'Neuer Client'}
              </span>
              <label style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', fontSize: '0.82rem', cursor: 'pointer' }}>
                <span className="text--muted">Aktiv</span>
                <label className="toggle">
                  <input
                    type="checkbox"
                    checked={form.active}
                    onChange={(e) => setForm({ ...form, active: e.target.checked })}
                  />
                  <span className="toggle__track" />
                </label>
              </label>
            </div>

            <div className="grid grid--2">
              <div className="form-group">
                <label className="form-label">Name</label>
                <input
                  className="form-input"
                  value={form.name}
                  onChange={(e) => setForm({ ...form, name: e.target.value })}
                  placeholder="z.B. Werkstatt-Client"
                />
              </div>
              <div className="form-group">
                <label className="form-label">Erlaubte IP / Subnetz</label>
                <input
                  className="form-input"
                  value={form.allowed_ip}
                  onChange={(e) => setForm({ ...form, allowed_ip: e.target.value })}
                  placeholder="192.168.50.0/24"
                />
              </div>
            </div>

            <div className="form-group">
              <label className="form-label">Beschreibung</label>
              <input
                className="form-input"
                value={form.description}
                onChange={(e) => setForm({ ...form, description: e.target.value })}
                placeholder="Wofür wird dieser Client genutzt?"
              />
            </div>

            <div className="form-group">
              <label className="form-label">Erlaubte Routen (kommasepariert)</label>
              <input
                className="form-input"
                value={form.allowed_routes.join(', ')}
                onChange={(e) =>
                  setForm({
                    ...form,
                    allowed_routes: e.target.value.split(',').map((s) => s.trim()).filter(Boolean),
                  })
                }
                placeholder="/route, /health"
              />
            </div>

            <div className="btn-group">
              <button
                className="btn"
                onClick={handleSubmit}
                disabled={submitting || !form.name.trim()}
              >
                {submitting ? 'Speichert…' : isEditing ? 'Speichern' : 'Client anlegen'}
              </button>
              <button className="btn btn--ghost" onClick={closeForm} disabled={submitting}>
                Abbrechen
              </button>
            </div>
          </div>
        )}
      </Card>

      {/* ── Integration guide ── */}
      <div style={{ marginTop: '1.5rem' }}>
        <Card title="Integration" tag="SECURE">
          {integrationLoading ? (
            <div className="text--muted text--sm">Lädt…</div>
          ) : integrationError ? (
            <div className="alert alert--warn">Integrationshilfe nicht verfügbar: {integrationError}</div>
          ) : integrationGuide ? (
            <div className="grid grid--2">
              <div className="form-group">
                <label className="form-label">Router-URL</label>
                <code className="kv__value">{integrationGuide.router_base_url}</code>
              </div>
              <div className="form-group">
                <label className="form-label">{integrationGuide.auth_header_name}</label>
                <code className="kv__value">{integrationGuide.auth_header_example}</code>
              </div>
              <div className="form-group">
                <label className="form-label">Sicherheitskontrollen</label>
                <ul className="gap-list">
                  {integrationGuide.security_controls.map((item) => (
                    <li key={item}>{item}</li>
                  ))}
                </ul>
              </div>
              <div className="form-group">
                <label className="form-label">Erlaubte Routen</label>
                <div style={{ display: 'flex', gap: '0.25rem', flexWrap: 'wrap' }}>
                  {integrationGuide.allowed_routes.map((r) => (
                    <span key={r} className="ip-tag">{r}</span>
                  ))}
                </div>
              </div>
              <div className="form-group" style={{ gridColumn: '1 / -1' }}>
                <label className="form-label">cURL-Beispiel</label>
                <pre className="code-block code-block--request">{integrationGuide.example_curl}</pre>
              </div>
            </div>
          ) : (
            <span className="text--muted text--sm">Keine Integrationshilfe verfügbar.</span>
          )}
        </Card>
      </div>
    </Layout>
  );
}
