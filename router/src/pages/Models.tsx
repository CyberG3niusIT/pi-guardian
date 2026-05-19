import { useState, useEffect } from 'react';
import { Card } from '../components/Card';
import { Layout } from '../components/Layout';
import { sendRoute, fetchModels, fetchSettings, selectModel, ApiRequestError } from '../api/client';
import { useApiCall } from '../hooks/useApi';
import { CONFIG } from '../config';
import type { OllamaModel, RouteResponse, RouterSettings } from '../types';

/** Infer provider from model name heuristics */
function getProvider(name: string): 'ollama' | 'anthropic' | 'openai' {
  const n = name.toLowerCase();
  if (n.includes('claude')) return 'anthropic';
  if (n.includes('gpt') || n.includes('openai')) return 'openai';
  return 'ollama';
}

function ProviderBadge({ name }: { name: string }) {
  const provider = getProvider(name);
  const labels: Record<string, string> = {
    anthropic: 'Anthropic',
    openai: 'OpenAI',
    ollama: 'Ollama',
  };
  return (
    <span className={`provider-badge provider-badge--${provider}`}>
      {labels[provider]}
    </span>
  );
}

export function Models() {
  const [testPrompt, setTestPrompt] = useState('Antworte kurz: Was ist 2+2?');
  const [testResult, setTestResult] = useState<RouteResponse | null>(null);
  const [testError, setTestError] = useState<string | null>(null);
  const [testing, setTesting] = useState(false);
  const [activeModel, setActiveModel] = useState(CONFIG.defaultModel);
  const [selectionError, setSelectionError] = useState<string | null>(null);
  const [selectingModel, setSelectingModel] = useState<string | null>(null);

  const { data: models, loading: modelsLoading, error: modelsError, execute } =
    useApiCall<OllamaModel[]>();
  const { execute: loadSettings } = useApiCall<RouterSettings>();

  useEffect(() => {
    execute(fetchModels).catch(() => {});
    loadSettings(fetchSettings)
      .then((settings) => { if (settings) setActiveModel(settings.default_model); })
      .catch(() => {});
  }, [execute, loadSettings]);

  async function handleTest() {
    setTesting(true); setTestError(null); setTestResult(null);
    try {
      setTestResult(await sendRoute({ prompt: testPrompt }));
    } catch (err) {
      setTestError(err instanceof ApiRequestError ? err.message : 'Fehler beim Testen');
    } finally { setTesting(false); }
  }

  async function handleSelectModel(modelName: string) {
    setSelectionError(null); setSelectingModel(modelName);
    try {
      const result = await selectModel(modelName);
      setActiveModel(result.model);
    } catch (err) {
      setSelectionError(err instanceof ApiRequestError ? err.message : 'Fehler beim Modellwechsel');
    } finally { setSelectingModel(null); }
  }

  return (
    <Layout title="Modelle">
      {/* ── Active model highlight ── */}
      <div className="agent-banner" style={{ marginBottom: '1.5rem' }}>
        <div>
          <div className="agent-banner__eyebrow">Intelligence</div>
          <div className="agent-banner__title">Modellverwaltung</div>
          <div className="agent-banner__text">
            Lokale Ollama-Modelle — wähle das Standardmodell für alle Route-Requests.
          </div>
        </div>
        <div className="agent-banner__stats">
          <div className="agent-stat">
            <span>Aktiv</span>
            <strong style={{ fontSize: '0.9rem', fontFamily: 'var(--font-mono)' }}>
              {activeModel.split(':')[0]}
            </strong>
          </div>
          <div className="agent-stat">
            <span>Provider</span>
            <strong>Ollama</strong>
          </div>
        </div>
      </div>

      {/* ── Model cards grid ── */}
      {modelsLoading && (
        <div className="text--muted text--sm" style={{ marginBottom: '1rem' }}>Lade Modelle…</div>
      )}
      {modelsError && (
        <div className="alert alert--error" style={{ marginBottom: '1rem' }}>{modelsError}</div>
      )}
      {selectionError && (
        <div className="alert alert--error" style={{ marginBottom: '1rem' }}>{selectionError}</div>
      )}

      {!modelsLoading && !modelsError && (
        <div className="grid grid--3" style={{ marginBottom: '1.5rem' }}>
          {(models ?? []).map((m) => (
            <div key={m.name} className="model-card">
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: '0.5rem' }}>
                <div className="model-card__name">{m.name}</div>
                {m.name === activeModel && (
                  <span className="badge badge--ok">
                    <span className="badge__dot" />Aktiv
                  </span>
                )}
              </div>
              <div className="model-card__meta">
                <ProviderBadge name={m.name} />
                <span>{m.size}</span>
                {m.modified_at && (
                  <span style={{ marginLeft: 'auto', fontSize: '0.7rem' }}>
                    {new Date(m.modified_at).toLocaleDateString('de-DE')}
                  </span>
                )}
              </div>
              {m.name !== activeModel && (
                <button
                  className="btn btn--sm btn--ghost"
                  style={{ marginTop: '0.4rem', alignSelf: 'flex-start' }}
                  onClick={() => handleSelectModel(m.name)}
                  disabled={selectingModel === m.name}
                >
                  {selectingModel === m.name ? 'Aktiviere…' : 'Als Standard setzen'}
                </button>
              )}
            </div>
          ))}
          {(models ?? []).length === 0 && (
            <div className="empty-state" style={{ gridColumn: '1 / -1' }}>
              <div className="empty-state__icon">⬡</div>
              <div className="empty-state__title">Keine Modelle gefunden</div>
              <div className="empty-state__sub">Ollama läuft möglicherweise nicht</div>
            </div>
          )}
        </div>
      )}

      {/* ── Model test ── */}
      <Card title="Modelltest" tag="LIVE">
        <div className="form-group">
          <label className="form-label">Prompt</label>
          <textarea
            className="form-input form-input--textarea"
            rows={3}
            value={testPrompt}
            onChange={(e) => setTestPrompt(e.target.value)}
            placeholder="Prompt eingeben…"
          />
        </div>
        <button
          className="btn"
          onClick={handleTest}
          disabled={testing || !testPrompt.trim()}
        >
          {testing ? 'Sende…' : 'An Modell senden'}
        </button>

        {testResult && (
          <div className="result-box" style={{ marginTop: '1rem' }}>
            <div className="kv">
              <span className="kv__label">Modell</span>
              <code className="kv__value">{testResult.model}</code>
            </div>
            <div className="kv">
              <span className="kv__label">Status</span>
              <span className="kv__value">{testResult.done ? 'Fertig' : 'Läuft…'}</span>
            </div>
            <div className="kv">
              <span className="kv__label">Grund</span>
              <span className="kv__value">{testResult.done_reason}</span>
            </div>
            <div className="kv">
              <span className="kv__label">Fairness-Check</span>
              <span className="kv__value">
                {testResult.fairness_review_attempted ? 'KI eingebunden' : 'nicht ausgeführt'}
              </span>
            </div>
            {testResult.fairness_review_attempted && (
              <>
                <div className="kv">
                  <span className="kv__label">Fairness-Risiko</span>
                  <span className="kv__value">{testResult.fairness_risk || 'unknown'}</span>
                </div>
                <div className="kv">
                  <span className="kv__label">Route angehoben</span>
                  <span className="kv__value">
                    {testResult.fairness_review_override ? 'Ja' : 'Nein'}
                  </span>
                </div>
              </>
            )}
            <div style={{ marginTop: '0.85rem' }}>
              <label className="form-label">Antwort</label>
              <pre className="code-block code-block--request">{testResult.response}</pre>
            </div>
          </div>
        )}

        {testError && (
          <div className="alert alert--error" style={{ marginTop: '1rem' }}>{testError}</div>
        )}
      </Card>
    </Layout>
  );
}
