import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { Card } from '../components/Card';
import { Layout } from '../components/Layout';
import {
  ApiRequestError,
  createClient,
  deleteClient,
  fetchClients,
  updateClient,
} from '../api/client';
import type { ClientCreate, ClientRead } from '../types';

type ClientFormState = {
  name: string;
  description: string;
  active: boolean;
  allowed_ip: string;
  allowed_routes_text: string;
  can_use_llm: boolean;
  can_use_tools: boolean;
  can_use_internet: boolean;
};

type ClientTemplate = {
  label: string;
  description: string;
  form: ClientFormState;
};

const ROUTER_BASE_PATHS = [
  '/route',
  '/health',
  '/settings',
  '/models',
  '/models/select',
  '/models/registry',
  '/models/pull',
  '/models/delete',
  '/status/service',
  '/clients',
  '/history',
  '/logs',
  '/agents',
  '/skills',
  '/actions',
  '/memory',
  '/api/tags',
  '/api/generate',
  '/api/chat',
  '/v1/models',
  '/v1/chat/completions',
] as const;

const PUBLIC_ROUTE_PREFIX = '/api';

const EMPTY_FORM: ClientFormState = {
  name: '',
  description: '',
  active: true,
  allowed_ip: '',
  allowed_routes_text: '/route',
  can_use_llm: true,
  can_use_tools: false,
  can_use_internet: false,
};

const CLIENT_TEMPLATES: ClientTemplate[] = [
  {
    label: 'Mobile Light-Agent',
    description: 'Handy oder Tablet fuer lokale KI, Agenten, Skills, Verlauf und Diagnose.',
    form: {
      name: 'Mobile_Light_Agent',
      description: 'Mobiler LAN-Client fuer AirPI/Router Light-Agent-Aufgaben',
      active: true,
      allowed_ip: '192.168.50.0/24',
      allowed_routes_text: routesToText([
        '/route',
        '/health',
        '/status/service',
        '/agents',
        '/skills',
        '/actions',
        '/history',
        '/memory',
        '/api/tags',
        '/api/generate',
        '/api/chat',
        '/v1/models',
        '/v1/chat/completions',
      ]),
      can_use_llm: true,
      can_use_tools: true,
      can_use_internet: false,
    },
  },
  {
    label: 'Kids Controller',
    description: 'Serverseitiger Integrator mit kontrolliertem Router-Zugriff.',
    form: {
      name: 'Kids_Controller',
      description: 'Persistenter externer Client fuer den Kids Controller',
      active: true,
      allowed_ip: '192.168.50.0/24',
      allowed_routes_text: routesToText(['/route', '/health', '/status/service', '/history']),
      can_use_llm: true,
      can_use_tools: true,
      can_use_internet: false,
    },
  },
  {
    label: 'Mailtracker Bridge',
    description: 'Private forensische Bruecke, nur Analyseaufrufe und Health.',
    form: {
      name: 'AirPI_Mailtracker_Bridge',
      description: 'Lokale Mailtracker-Bruecke fuer deterministische Berichte und KI-Interpretation',
      active: true,
      allowed_ip: '192.168.50.10',
      allowed_routes_text: routesToText(['/route', '/health']),
      can_use_llm: true,
      can_use_tools: false,
      can_use_internet: false,
    },
  },
  {
    label: 'Admin UI',
    description: 'Vollzugriff fuer die lokale Router-Oberflaeche im Heimnetz.',
    form: {
      name: 'Router_Admin_UI_Persistent',
      description: 'Dedizierter persistenter Admin-Client fuer die Router-UI',
      active: true,
      allowed_ip: '192.168.50.0/24',
      allowed_routes_text: routesToText([...ROUTER_BASE_PATHS]),
      can_use_llm: true,
      can_use_tools: true,
      can_use_internet: true,
    },
  },
];

function routesToText(routes: string[]): string {
  return routes.join(', ');
}

function normalizeRoute(route: string): string {
  const trimmed = route.trim();
  if (!trimmed) return '';
  const withSlash = trimmed.startsWith('/') ? trimmed : `/${trimmed}`;
  if (ROUTER_BASE_PATHS.includes(withSlash as (typeof ROUTER_BASE_PATHS)[number])) {
    return withSlash;
  }
  if (withSlash.startsWith(`${PUBLIC_ROUTE_PREFIX}/api/`)) {
    return withSlash.slice(PUBLIC_ROUTE_PREFIX.length);
  }
  if (withSlash.startsWith(`${PUBLIC_ROUTE_PREFIX}/`)) {
    return withSlash.slice(PUBLIC_ROUTE_PREFIX.length);
  }
  return withSlash;
}

function parseRoutes(text: string): string[] {
  const routes = text
    .split(',')
    .map(normalizeRoute)
    .filter(Boolean);
  return [...new Set(routes)];
}

function toPublicPath(route: string): string {
  return `${PUBLIC_ROUTE_PREFIX}${route}`;
}

function clientToForm(client: ClientRead): ClientFormState {
  return {
    name: client.name,
    description: client.description ?? '',
    active: client.active,
    allowed_ip: client.allowed_ip,
    allowed_routes_text: routesToText(client.allowed_routes ?? []),
    can_use_llm: client.can_use_llm ?? true,
    can_use_tools: client.can_use_tools ?? false,
    can_use_internet: client.can_use_internet ?? false,
  };
}

function makePayload(form: ClientFormState): ClientCreate {
  return {
    name: form.name.trim(),
    description: form.description.trim(),
    active: form.active,
    allowed_ip: form.allowed_ip.trim(),
    allowed_routes: parseRoutes(form.allowed_routes_text),
    can_use_llm: form.can_use_llm,
    can_use_tools: form.can_use_tools,
    can_use_internet: form.can_use_internet,
    api_key: '',
  };
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

export function Clients() {
  const [clients, setClients] = useState<ClientRead[]>([]);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState('');
  const [form, setForm] = useState<ClientFormState>(EMPTY_FORM);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [notice, setNotice] = useState('');
  const [createdApiKey, setCreatedApiKey] = useState('');

  const sortedClients = useMemo(() => {
    return [...clients].sort((a, b) => {
      const aName = a.name.toLowerCase();
      const bName = b.name.toLowerCase();
      if (aName < bName) return -1;
      if (aName > bName) return 1;
      return String(a.id).localeCompare(String(b.id));
    });
  }, [clients]);

  async function loadClients() {
    setLoading(true);
    setError('');
    try {
      const data = await fetchClients();
      setClients(data);
    } catch (err) {
      setClients([]);
      setError(err instanceof ApiRequestError ? err.message : 'Clients konnten nicht geladen werden');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    void loadClients();
  }, []);

  function resetForm() {
    setForm(EMPTY_FORM);
    setEditingId(null);
  }

  function startCreate() {
    setNotice('');
    setCreatedApiKey('');
    resetForm();
  }

  function applyTemplate(template: ClientTemplate) {
    setNotice(`Vorlage "${template.label}" geladen.`);
    setCreatedApiKey('');
    setEditingId(null);
    setForm(template.form);
  }

  function startEdit(client: ClientRead) {
    setNotice('');
    setCreatedApiKey('');
    setEditingId(client.id);
    setForm(clientToForm(client));
  }

  function validateForm(): string | null {
    if (!form.name.trim()) return 'Name darf nicht leer sein.';
    if (!form.allowed_ip.trim()) return 'IP / Subnetz darf nicht leer sein.';
    if (parseRoutes(form.allowed_routes_text).length === 0) {
      return 'Mindestens eine Route muss angegeben werden.';
    }
    const unknownRoutes = parseRoutes(form.allowed_routes_text).filter(
      (route) => !ROUTER_BASE_PATHS.includes(route as (typeof ROUTER_BASE_PATHS)[number]),
    );
    if (unknownRoutes.length > 0) {
      return `Unbekannte Route: ${unknownRoutes.join(', ')}`;
    }
    return null;
  }

  async function handleSubmit() {
    const validationError = validateForm();
    if (validationError) {
      setError(validationError);
      return;
    }

    setSaving(true);
    setError('');
    try {
      const payload = makePayload(form);
      if (editingId !== null) {
        await updateClient(Number(editingId), payload);
        setNotice(`Client ${form.name.trim()} wurde aktualisiert.`);
        setCreatedApiKey('');
      } else {
        const created = await createClient(payload);
        setNotice(`Client ${created.name} wurde angelegt.`);
        setCreatedApiKey(created.api_key ?? '');
      }
      await loadClients();
      resetForm();
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : 'Client konnte nicht gespeichert werden');
    } finally {
      setSaving(false);
    }
  }

  async function handleDelete(client: ClientRead) {
    const confirmed = window.confirm(`Client "${client.name}" wirklich löschen?`);
    if (!confirmed) return;

    setSaving(true);
    setError('');
    try {
      await deleteClient(client.id);
      setNotice(`Client ${client.name} wurde gelöscht.`);
      setCreatedApiKey('');
      await loadClients();
      if (editingId === client.id) {
        resetForm();
      }
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : 'Client konnte nicht gelöscht werden');
    } finally {
      setSaving(false);
    }
  }

  async function handleToggleActive(client: ClientRead) {
    setSaving(true);
    setError('');
    try {
      await updateClient(client.id, { active: !client.active });
      setNotice(`Client ${client.name} ist jetzt ${client.active ? 'inaktiv' : 'aktiv'}.`);
      await loadClients();
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : 'Status konnte nicht geändert werden');
    } finally {
      setSaving(false);
    }
  }

  return (
    <Layout title="Client-Verwaltung">
      <div className="grid grid--dense">
        <Card title="Registrierte Clients" tag={`${clients.length} EINTRÄGE`}>
          <div className="kv">
            <span className="kv__label">Quelle</span>
            <span className="kv__value kv__value--highlight">UI liest /api/clients</span>
          </div>
          <div className="kv">
            <span className="kv__label">Persistenz</span>
            <span className="kv__value">SQLite `router/data/pi_guardian.db`</span>
          </div>
          <div className="kv">
            <span className="kv__label">Speicherformat</span>
            <span className="kv__value">Router-intern ohne /api-Prefix</span>
          </div>
          <div className="kv">
            <span className="kv__label">Kids Controller sichtbar</span>
            <span className="kv__value">
              {sortedClients.some((client) => client.name === 'Kids_Controller') ? 'Ja' : 'Nein'}
            </span>
          </div>
        </Card>

        <Card title="Hinweise" tag="ECHTE DATEN">
          <div className="kv">
            <span className="kv__label">Lesen</span>
            <span className="kv__value">GET /api/clients</span>
          </div>
          <div className="kv">
            <span className="kv__label">Anlegen</span>
            <span className="kv__value">POST /api/clients</span>
          </div>
          <div className="kv">
            <span className="kv__label">Aktualisieren</span>
            <span className="kv__value">PUT /api/clients/{'{id}'}</span>
          </div>
          <div className="kv">
            <span className="kv__label">Löschen</span>
            <span className="kv__value">DELETE /api/clients/{'{id}'}</span>
          </div>
          <div className="kv">
            <span className="kv__label">Client-Erlaubnis</span>
            <span className="kv__value">z.B. /route statt /api/route</span>
          </div>
        </Card>
      </div>

      {error && (
        <div className="alert alert--error" style={{ marginBottom: '1rem' }}>
          {error}
        </div>
      )}

      {notice && (
        <div className="alert alert--ok" style={{ marginBottom: '1rem' }}>
          {notice}
        </div>
      )}

      {createdApiKey && (
        <div className="alert alert--warn" style={{ marginBottom: '1rem' }}>
          Neuer API-Key wurde erzeugt und nur jetzt angezeigt:
          <div className="code-block" style={{ marginTop: '0.5rem' }}>
            {createdApiKey}
          </div>
        </div>
      )}

      <Card
        title="Persistente Clients"
        tag={loading ? 'Lädt…' : 'LIVE'}
        headerActions={(
          <button className="btn btn--sm btn--ghost" onClick={() => void loadClients()} disabled={loading || saving}>
            Neu laden
          </button>
        )}
      >
        {loading ? (
          <div className="empty-state">
            <div className="empty-state__icon">…</div>
            <div className="empty-state__title">Clients werden geladen</div>
            <div className="empty-state__sub">Die Verwaltungsansicht liest die aktuellen Einträge aus dem Router.</div>
          </div>
        ) : sortedClients.length === 0 ? (
          <EmptyCollectionState
            title="Keine Clients registriert"
            description="Neue Clients erscheinen hier als Verwaltungskarten ohne lokale Drag-and-Drop-Sortierung."
          />
        ) : (
          <div className="entity-card-grid entity-card-grid--clients">
            {sortedClients.map((client) => (
              <Card
                key={client.id}
                className="entity-card"
                title={client.name}
                tag={`ID ${client.id}`}
                headerActions={
                  <span className={`badge ${client.active ? 'badge--ok' : 'badge--fail'}`}>
                    <span className="badge__dot" />
                    {client.active ? 'Aktiv' : 'Inaktiv'}
                  </span>
                }
              >
                <div className="entity-card__stack">
                  <p className="entity-card__lead">
                    {client.description || 'Keine Beschreibung hinterlegt.'}
                  </p>
                  {client.name === 'Kids_Controller' && (
                    <div className="entity-card__note">
                      Persistenter externer Client für den Kids-Controller.
                    </div>
                  )}

                  <div className="entity-card__meta-grid">
                    <MetaItem label="IP / Host" value={client.allowed_ip} />
                    <MetaItem label="Routen intern" value={routesToText(client.allowed_routes ?? []) || '–'} />
                    <MetaItem
                      label="HTTP über UI"
                      value={routesToText((client.allowed_routes ?? []).map(toPublicPath)) || '–'}
                    />
                    <MetaItem label="LLM" value={client.can_use_llm ? 'Ja' : 'Nein'} plain />
                    <MetaItem label="Tools" value={client.can_use_tools ? 'Ja' : 'Nein'} plain />
                    <MetaItem label="Internet" value={client.can_use_internet ? 'Ja' : 'Nein'} plain />
                  </div>

                  <div className="entity-card__section">
                    <span className="entity-card__section-title">Fähigkeiten</span>
                    <div className="entity-card__pill-list">
                      <span className={`badge ${client.can_use_llm ? 'badge--ok' : 'badge--fail'}`}>
                        <span className="badge__dot" />
                        LLM
                      </span>
                      <span className={`badge ${client.can_use_tools ? 'badge--ok' : 'badge--fail'}`}>
                        <span className="badge__dot" />
                        Tools
                      </span>
                      <span className={`badge ${client.can_use_internet ? 'badge--ok' : 'badge--fail'}`}>
                        <span className="badge__dot" />
                        Internet
                      </span>
                    </div>
                  </div>

                  <div className="entity-card__footer">
                    <div className="text--muted text--sm">Alphabetische Ansicht, keine lokale Persistenz.</div>
                    <div className="entity-card__actions">
                      <button
                        className="btn btn--sm btn--ghost"
                        onClick={() => startEdit(client)}
                        disabled={saving}
                      >
                        Bearbeiten
                      </button>
                      <button
                        className="btn btn--sm btn--ghost"
                        onClick={() => handleToggleActive(client)}
                        disabled={saving}
                      >
                        {client.active ? 'Deaktivieren' : 'Aktivieren'}
                      </button>
                      <button
                        className="btn btn--sm btn--danger"
                        onClick={() => handleDelete(client)}
                        disabled={saving}
                      >
                        Löschen
                      </button>
                    </div>
                  </div>
                </div>
              </Card>
            ))}
          </div>
        )}
      </Card>

      <Card
        title={editingId === null ? 'Client anlegen' : `Client bearbeiten: ${form.name || editingId}`}
        tag={editingId === null ? 'NEU' : 'EDIT'}
      >
        {editingId === null && (
          <div className="entity-card__note-list" style={{ marginBottom: '1rem' }}>
            <div className="entity-card__note">
              Vorlagen setzen passende Routen, Rechte und IP-Bereiche. Gespeichert werden Router-interne Pfade ohne
              /api-Prefix, auch wenn du versehentlich /api/... einträgst.
            </div>
            <div className="entity-card__pill-list">
              {CLIENT_TEMPLATES.map((template) => (
                <button
                  key={template.label}
                  className="btn btn--sm btn--ghost"
                  onClick={() => applyTemplate(template)}
                  title={template.description}
                  type="button"
                  disabled={saving}
                >
                  {template.label}
                </button>
              ))}
            </div>
          </div>
        )}

        <div className="grid grid--2">
          <div className="form-group">
            <label className="form-label">Name</label>
            <input
              className="form-input"
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="z.B. Werkstatt-Terminal"
            />
          </div>
          <div className="form-group">
            <label className="form-label">Erlaubte IP / Subnetz</label>
            <input
              className="form-input"
              value={form.allowed_ip}
              onChange={(e) => setForm({ ...form, allowed_ip: e.target.value })}
              placeholder="z.B. 192.168.50.0/24"
            />
          </div>
        </div>

        <div className="form-group">
          <label className="form-label">Beschreibung</label>
          <textarea
            className="form-input form-input--textarea"
            value={form.description}
            onChange={(e) => setForm({ ...form, description: e.target.value })}
            placeholder="Wofür wird dieser Client genutzt?"
          />
        </div>

        <div className="form-group">
          <label className="form-label">Erlaubte Router-Routen (kommasepariert)</label>
          <textarea
            className="form-input form-input--textarea"
            value={form.allowed_routes_text}
            onChange={(e) => setForm({ ...form, allowed_routes_text: e.target.value })}
            placeholder="/route, /health, /clients"
          />
          <div className="entity-card__note" style={{ marginTop: '0.5rem' }}>
            Browser nutzt z.B. /api/route. Client-Rechte speichern den Router-Pfad /route, weil Nginx /api/ beim Proxy
            entfernt. Gueltige Routen: {routesToText([...ROUTER_BASE_PATHS])}
          </div>
        </div>

        <div className="toggle-row" style={{ marginBottom: '1rem' }}>
          <button
            className={`btn btn--sm ${form.active ? 'btn--active' : 'btn--ghost'}`}
            onClick={() => setForm({ ...form, active: true })}
            type="button"
          >
            Aktiv
          </button>
          <button
            className={`btn btn--sm ${!form.active ? 'btn--active' : 'btn--ghost'}`}
            onClick={() => setForm({ ...form, active: false })}
            type="button"
          >
            Inaktiv
          </button>
        </div>

        <div className="grid grid--3" style={{ marginBottom: '1rem' }}>
          <label className="toggle-card">
            <input
              type="checkbox"
              checked={form.can_use_llm}
              onChange={(e) => setForm({ ...form, can_use_llm: e.target.checked })}
            />
            <span>
              <strong>LLM</strong>
              <small>Client darf reine Modellanfragen stellen</small>
            </span>
          </label>
          <label className="toggle-card">
            <input
              type="checkbox"
              checked={form.can_use_tools}
              onChange={(e) => setForm({ ...form, can_use_tools: e.target.checked })}
            />
            <span>
              <strong>Tools</strong>
              <small>Client darf toolbasierte Requests anfordern</small>
            </span>
          </label>
          <label className="toggle-card">
            <input
              type="checkbox"
              checked={form.can_use_internet}
              onChange={(e) => setForm({ ...form, can_use_internet: e.target.checked })}
            />
            <span>
              <strong>Internet</strong>
              <small>Client darf internetbasierte Requests anfordern</small>
            </span>
          </label>
        </div>

        <div className="btn-group">
          <button className="btn" onClick={handleSubmit} disabled={saving}>
            {editingId === null ? 'Client speichern' : 'Änderungen speichern'}
          </button>
          <button className="btn btn--ghost" onClick={startCreate} disabled={saving}>
            Neuer Client
          </button>
          {editingId !== null && (
            <button className="btn btn--ghost" onClick={resetForm} disabled={saving}>
              Bearbeitung abbrechen
            </button>
          )}
        </div>
      </Card>
    </Layout>
  );
}
