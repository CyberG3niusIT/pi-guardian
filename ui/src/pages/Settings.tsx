import { useEffect, useState } from 'react';
import { Card } from '../components/Card';
import { Layout } from '../components/Layout';
import { CONFIG } from '../config';
import { fetchSettings, updateSettings, ApiRequestError } from '../api/client';
import type { RouterSettings } from '../types';

/**
 * Router-Einstellungen
 *
 * BACKEND ERFORDERLICH:
 *   - GET /settings – Konfiguration laden
 *   - PUT /settings – Konfiguration speichern
 *
 * Die UI zeigt die erwartete Konfigurationsstruktur.
 * Werte sind Defaults/Annahmen bis GET /settings implementiert ist.
 */

const DEFAULT_SETTINGS: RouterSettings = {
  router_host: '0.0.0.0',
  router_port: CONFIG.routerPort,
  ollama_host: '127.0.0.1',
  ollama_port: 11434,
  timeout: 30,
  default_model: CONFIG.defaultModel,
  large_model: 'qwen2.5-coder:3b',
  logging_level: 'INFO',
  stream_default: false,
  require_api_key: true,
  escalation_threshold: 'medium',
};

export function Settings() {
  const [settings, setSettings] = useState<RouterSettings>({ ...DEFAULT_SETTINGS });
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);
  const [loadError, setLoadError] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    async function load() {
      setLoading(true);
      setLoadError(null);
      try {
        const current = await fetchSettings();
        setSettings({
          ...DEFAULT_SETTINGS,
          ...current,
          require_api_key: current.require_api_key ?? DEFAULT_SETTINGS.require_api_key,
          escalation_threshold: current.escalation_threshold ?? DEFAULT_SETTINGS.escalation_threshold,
        });
      } catch (err) {
        setLoadError(err instanceof ApiRequestError ? err.message : 'Einstellungen konnten nicht geladen werden.');
      } finally {
        setLoading(false);
      }
    }

    void load();
  }, []);

  function handleChange(key: keyof RouterSettings, value: string | number | boolean) {
    setSettings((prev) => ({ ...prev, [key]: value }));
    setSaved(false);
  }

  async function handleSave() {
    setSaving(true);
    setLoadError(null);
    try {
      const response = await updateSettings(settings);
      setSettings({
        ...DEFAULT_SETTINGS,
        ...response.settings,
      });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      setLoadError(err instanceof ApiRequestError ? err.message : 'Einstellungen konnten nicht gespeichert werden.');
    } finally {
      setSaving(false);
    }
  }

  function handleReset() {
    setSettings({ ...DEFAULT_SETTINGS });
    setSaved(false);
  }

  return (
    <Layout title="Router-Einstellungen">
      {loading && <p className="text--muted">Lade Einstellungen…</p>}

      <div className="grid grid--2">
        <Card title="Router" tag="LIVE">
          <div className="form-group">
            <label className="form-label">Host</label>
            <input
              className="form-input"
              value={settings.router_host}
              onChange={(e) => handleChange('router_host', e.target.value)}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Port</label>
            <input
              className="form-input"
              type="number"
              value={settings.router_port}
              onChange={(e) => handleChange('router_port', parseInt(e.target.value) || 0)}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Logging-Level</label>
            <select
              className="form-input"
              value={settings.logging_level}
              onChange={(e) => handleChange('logging_level', e.target.value)}
            >
              <option value="DEBUG">DEBUG</option>
              <option value="INFO">INFO</option>
              <option value="WARNING">WARNING</option>
              <option value="ERROR">ERROR</option>
            </select>
          </div>
        </Card>

        <Card title="Ollama" tag="LIVE">
          <div className="form-group">
            <label className="form-label">Host</label>
            <input
              className="form-input"
              value={settings.ollama_host}
              onChange={(e) => handleChange('ollama_host', e.target.value)}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Port</label>
            <input
              className="form-input"
              type="number"
              value={settings.ollama_port}
              onChange={(e) => handleChange('ollama_port', parseInt(e.target.value) || 0)}
            />
          </div>
          <div className="form-group">
            <label className="form-label">Timeout (Sekunden)</label>
            <input
              className="form-input"
              type="number"
              value={settings.timeout}
              onChange={(e) => handleChange('timeout', parseInt(e.target.value) || 0)}
            />
          </div>
        </Card>
      </div>

      <div style={{ marginTop: '1.5rem' }}>
        <Card title="Modell & Verhalten" tag="LIVE">
          <div className="grid grid--2">
            <div className="form-group">
              <label className="form-label">Standardmodell</label>
              <input
                className="form-input"
                value={settings.default_model}
                onChange={(e) => handleChange('default_model', e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Deep Model</label>
              <input
                className="form-input"
                value={settings.large_model}
                onChange={(e) => handleChange('large_model', e.target.value)}
              />
            </div>
            <div className="form-group">
              <label className="form-label">Stream standardmäßig</label>
              <div className="toggle-row">
                <button
                  className={`btn btn--sm ${settings.stream_default ? 'btn--active' : 'btn--ghost'}`}
                  onClick={() => handleChange('stream_default', true)}
                >
                  Ja
                </button>
                <button
                  className={`btn btn--sm ${!settings.stream_default ? 'btn--active' : 'btn--ghost'}`}
                  onClick={() => handleChange('stream_default', false)}
                >
                  Nein
                </button>
              </div>
            </div>
          </div>
          <div className="grid grid--2" style={{ marginTop: '1rem' }}>
            <div className="form-group">
              <label className="form-label">API-Key erforderlich</label>
              <div className="toggle-row">
                <button
                  className={`btn btn--sm ${settings.require_api_key ? 'btn--active' : 'btn--ghost'}`}
                  onClick={() => handleChange('require_api_key', true)}
                >
                  Ja
                </button>
                <button
                  className={`btn btn--sm ${!settings.require_api_key ? 'btn--active' : 'btn--ghost'}`}
                  onClick={() => handleChange('require_api_key', false)}
                >
                  Nein
                </button>
              </div>
            </div>
            <div className="form-group">
              <label className="form-label">Eskalationsschwelle</label>
              <select
                className="form-input"
                value={settings.escalation_threshold ?? 'medium'}
                onChange={(e) => handleChange('escalation_threshold', e.target.value)}
              >
                <option value="low">low</option>
                <option value="medium">medium</option>
                <option value="high">high</option>
              </select>
            </div>
          </div>
        </Card>
      </div>

      <div className="btn-group" style={{ marginTop: '1.5rem' }}>
        <button className="btn" onClick={() => void handleSave()} disabled={saving || loading}>
          {saving ? 'Speichere…' : 'Speichern'}
        </button>
        <button className="btn btn--ghost" onClick={handleReset}>
          Zurücksetzen
        </button>
        {saved && <span className="text--ok text--sm" style={{ marginLeft: '1rem' }}>Gespeichert.</span>}
      </div>

      {loadError && (
        <div className="alert alert--warn" style={{ marginTop: '1rem' }}>
          <strong>Hinweis:</strong> {loadError}
        </div>
      )}

      <div style={{ marginTop: '1.5rem' }}>
        <Card title="Auth-Session" tag="AUTH">
          <p className="text--sm">
            Die Session wird beim Start der App automatisch per <code>POST /auth/bootstrap</code> gesetzt.
            Der Auth-Cookie ist httpOnly und läuft nach einem Jahr ab – kein manueller API-Key nötig.
          </p>
          <button
            className="btn btn--sm btn--ghost"
            style={{ marginTop: '0.75rem' }}
            onClick={() => window.location.reload()}
          >
            Session erneuern (Seite neu laden)
          </button>
        </Card>
      </div>
    </Layout>
  );
}
