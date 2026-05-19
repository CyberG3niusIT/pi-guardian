import { useEffect, useMemo, useState } from 'react';
import type { ReactNode } from 'react';
import { Card } from '../components/Card';
import { Layout } from '../components/Layout';
import { Modal } from '../components/Modal';
import { SortableCardGrid } from '../components/SortableCardGrid';
import {
  ApiRequestError,
  addAgentMemory,
  confirmAgentMemory,
  createAgent,
  createSkill,
  deleteAgent,
  deleteAgentMemory,
  deleteSkill,
  disableAgent,
  disableSkill,
  enableSkill,
  enableAgent,
  extractAgentMemory,
  fetchActions,
  fetchAgentMemory,
  fetchAgents,
  fetchSkills,
  importAgents,
  importSkills,
  runAgent,
  updateAgent,
  updateAgentSettings,
  updateSkill,
} from '../api/client';
import type {
  ActionDefinition,
  AgentDefinition,
  AgentMemoryEntry,
  AgentMemoryType,
  AgentRunResponse,
  SkillDefinition,
} from '../types';

function formatDateTime(value?: string | null) {
  if (!value) return '–';
  try { return new Date(value).toLocaleString('de-DE'); } catch { return value; }
}

function parseJsonDraft(value: string, fallbackLabel: string): Record<string, unknown> {
  try {
    const parsed = JSON.parse(value);
    if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
      throw new Error(`${fallbackLabel} muss ein JSON-Objekt sein.`);
    }
    return parsed as Record<string, unknown>;
  } catch (error) {
    throw new Error(
      error instanceof Error && error.message
        ? error.message
        : `${fallbackLabel} ist kein gueltiges JSON-Objekt.`,
    );
  }
}

const MEMORY_TYPE_LABEL: Record<AgentMemoryType, string> = {
  finding: 'Beobachtung',
  failure: 'Fehlermuster',
  feedback: 'Feedback',
  instruction: 'Hinweis',
};

const MEMORY_TYPE_COLOR: Record<AgentMemoryType, string> = {
  finding: 'var(--green-500, #22c55e)',
  failure: 'var(--red-500, #ef4444)',
  feedback: 'var(--indigo-400, #818cf8)',
  instruction: 'var(--yellow-500, #eab308)',
};

interface EditDraft {
  description: string;
  preferred_model: string;
  custom_instruction: string;
  max_steps: string;
  active: boolean;
}

interface MemoryDraft {
  memory_type: AgentMemoryType;
  content: string;
  priority: number;
}

interface SkillDraft {
  name: string;
  description: string;
  prompt_template: string;
  input_schema: string;
  output_schema: string;
  preferred_model: string;
  source_url: string;
  version: string;
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

// ── Memory Panel ──────────────────────────────────────────────────────────────

function MemoryPanel({ agent, onClose }: { agent: AgentDefinition; onClose: () => void }) {
  const [memories, setMemories] = useState<AgentMemoryEntry[]>([]);
  const [loading, setLoading] = useState(true);
  const [extracting, setExtracting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [draft, setDraft] = useState<MemoryDraft>({ memory_type: 'instruction', content: '', priority: 3 });
  const [adding, setAdding] = useState(false);
  const [showForm, setShowForm] = useState(false);

  async function loadMemories() {
    setLoading(true);
    setError(null);
    try {
      setMemories(await fetchAgentMemory(agent.name));
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : 'Fehler beim Laden');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void loadMemories(); }, [agent.name]);

  async function handleExtract() {
    setExtracting(true);
    setError(null);
    try {
      const created = await extractAgentMemory(agent.name);
      if (created.length === 0) {
        setError('Kein neuer Eintrag extrahiert (bereits vorhanden oder kein erfolgreicher Run).');
      }
      await loadMemories();
    } catch (err) {
      setError(err instanceof ApiRequestError ? `${err.status}: ${err.body}` : 'Extraktion fehlgeschlagen');
    } finally {
      setExtracting(false);
    }
  }

  async function handleAdd() {
    if (!draft.content.trim()) return;
    setAdding(true);
    setError(null);
    try {
      await addAgentMemory(agent.name, {
        memory_type: draft.memory_type,
        content: draft.content.trim(),
        priority: draft.priority,
      });
      setDraft({ memory_type: 'instruction', content: '', priority: 3 });
      setShowForm(false);
      await loadMemories();
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : 'Hinzufügen fehlgeschlagen');
    } finally {
      setAdding(false);
    }
  }

  async function handleConfirm(m: AgentMemoryEntry) {
    try {
      await confirmAgentMemory(agent.name, m.id);
      await loadMemories();
    } catch { /* ignore */ }
  }

  async function handleDelete(m: AgentMemoryEntry) {
    try {
      await deleteAgentMemory(agent.name, m.id);
      await loadMemories();
    } catch { /* ignore */ }
  }

  const sorted = [...memories].sort((a, b) => b.priority - a.priority || b.times_confirmed - a.times_confirmed);

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
      <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
        <button
          className="btn btn--sm"
          style={{ background: 'var(--indigo-500)', color: '#fff' }}
          onClick={() => void handleExtract()}
          disabled={extracting}
        >
          {extracting ? 'Extrahiere…' : '⟳ Aus letztem Run extrahieren'}
        </button>
        <button
          className="btn btn--sm btn--ghost"
          onClick={() => setShowForm((v) => !v)}
        >
          {showForm ? 'Formular schließen' : '+ Manuell hinzufügen'}
        </button>
      </div>

      {showForm && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.6rem', padding: '0.75rem', background: 'var(--surface-2, #f8fafc)', borderRadius: '6px', border: '1px solid var(--border)' }}>
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <select
              className="form-input"
              style={{ flex: '0 0 auto' }}
              value={draft.memory_type}
              onChange={(e) => setDraft((d) => ({ ...d, memory_type: e.target.value as AgentMemoryType }))}
            >
              {(Object.keys(MEMORY_TYPE_LABEL) as AgentMemoryType[]).map((t) => (
                <option key={t} value={t}>{MEMORY_TYPE_LABEL[t]}</option>
              ))}
            </select>
            <select
              className="form-input"
              style={{ flex: '0 0 auto', width: '7rem' }}
              value={draft.priority}
              onChange={(e) => setDraft((d) => ({ ...d, priority: Number(e.target.value) }))}
            >
              <option value={5}>Prio 5 – Kritisch</option>
              <option value={4}>Prio 4 – Hoch</option>
              <option value={3}>Prio 3 – Normal</option>
              <option value={2}>Prio 2 – Niedrig</option>
              <option value={1}>Prio 1 – Info</option>
            </select>
          </div>
          <textarea
            className="form-input form-input--textarea"
            rows={3}
            placeholder="Inhalt des Gedächtniseintrags…"
            value={draft.content}
            onChange={(e) => setDraft((d) => ({ ...d, content: e.target.value }))}
            style={{ fontSize: '0.83rem' }}
          />
          <button
            className="btn btn--sm"
            style={{ background: 'var(--indigo-500)', color: '#fff', alignSelf: 'flex-end' }}
            onClick={() => void handleAdd()}
            disabled={adding || !draft.content.trim()}
          >
            {adding ? 'Speichere…' : 'Speichern'}
          </button>
        </div>
      )}

      {error && (
        <div className="alert alert--warn" style={{ fontSize: '0.82rem' }}>{error}</div>
      )}

      {loading ? (
        <p className="text--muted">Lade…</p>
      ) : sorted.length === 0 ? (
        <p className="text--muted" style={{ fontSize: '0.85rem' }}>
          Noch keine Gedächtniseinträge. Starte einen Run und extrahiere danach Erkenntnisse.
        </p>
      ) : (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
          {sorted.map((m) => (
            <div
              key={m.id}
              style={{
                display: 'flex',
                gap: '0.6rem',
                alignItems: 'flex-start',
                padding: '0.6rem 0.75rem',
                background: 'var(--surface-1, #fff)',
                border: '1px solid var(--border)',
                borderLeft: `3px solid ${MEMORY_TYPE_COLOR[m.memory_type as AgentMemoryType] ?? '#888'}`,
                borderRadius: '5px',
                fontSize: '0.82rem',
              }}
            >
              <div style={{ flex: 1 }}>
                <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center', marginBottom: '0.25rem', flexWrap: 'wrap' }}>
                  <span style={{
                    fontSize: '0.72rem', fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.04em',
                    color: MEMORY_TYPE_COLOR[m.memory_type as AgentMemoryType] ?? '#888',
                  }}>
                    {MEMORY_TYPE_LABEL[m.memory_type as AgentMemoryType] ?? m.memory_type}
                  </span>
                  <span className="text--muted" style={{ fontSize: '0.72rem' }}>Prio {m.priority}</span>
                  {m.times_confirmed > 0 && (
                    <span style={{ fontSize: '0.72rem', color: 'var(--green-600, #16a34a)', fontWeight: 500 }}>
                      ✓ {m.times_confirmed}×
                    </span>
                  )}
                  <span className="text--muted" style={{ fontSize: '0.7rem', marginLeft: 'auto' }}>
                    {formatDateTime(m.created_at)}
                  </span>
                </div>
                <p style={{ margin: 0, lineHeight: 1.45, whiteSpace: 'pre-wrap' }}>{m.content}</p>
              </div>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '0.3rem', flexShrink: 0 }}>
                <button
                  className="btn btn--sm btn--ghost"
                  style={{ fontSize: '0.72rem', padding: '0.15rem 0.45rem' }}
                  onClick={() => void handleConfirm(m)}
                  title="Bestätigen (Priorität erhöhen)"
                >
                  ✓
                </button>
                <button
                  className="btn btn--sm btn--ghost"
                  style={{ fontSize: '0.72rem', padding: '0.15rem 0.45rem', color: 'var(--red-500, #ef4444)' }}
                  onClick={() => void handleDelete(m)}
                  title="Löschen"
                >
                  ✕
                </button>
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ── Main Component ────────────────────────────────────────────────────────────

export function Agents() {
  const [agents, setAgents] = useState<AgentDefinition[]>([]);
  const [skills, setSkills] = useState<SkillDefinition[]>([]);
  const [actions, setActions] = useState<ActionDefinition[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [refreshedAt, setRefreshedAt] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(true);

  // ── Import Modal ────────────────────────────────────────────────────────────
  const [importOpen, setImportOpen] = useState(false);
  const [importType, setImportType] = useState<'agent' | 'skill'>('agent');
  const [importMethod, setImportMethod] = useState<'manual' | 'github'>('manual');
  const [githubUrl, setGithubUrl] = useState('');
  const [importName, setImportName] = useState('');
  const [importDesc, setImportDesc] = useState('');
  const [importAllowedTools, setImportAllowedTools] = useState('system_status');
  const [importPreferredModel, setImportPreferredModel] = useState('');
  const [importCustomInstruction, setImportCustomInstruction] = useState('');
  const [importMaxSteps, setImportMaxSteps] = useState('5');
  const [importPromptTemplate, setImportPromptTemplate] = useState('Beschreibe die Eingabe strukturiert: {input_json}');
  const [importInputSchema, setImportInputSchema] = useState('{\n  "type": "object"\n}');
  const [importOutputSchema, setImportOutputSchema] = useState('{\n  "type": "object"\n}');
  const [importSourceUrl, setImportSourceUrl] = useState('');
  const [importVersion, setImportVersion] = useState('1.0');

  // ── Edit Modal ──────────────────────────────────────────────────────────────
  const [editAgent, setEditAgent] = useState<AgentDefinition | null>(null);
  const [editDraft, setEditDraft] = useState<EditDraft>({
    description: '', preferred_model: '', custom_instruction: '', max_steps: '', active: true,
  });
  const [saving, setSaving] = useState(false);
  const [saveError, setSaveError] = useState<string | null>(null);

  const [editSkill, setEditSkill] = useState<SkillDefinition | null>(null);
  const [skillDraft, setSkillDraft] = useState<SkillDraft>({
    name: '',
    description: '',
    prompt_template: '',
    input_schema: '{\n  "type": "object"\n}',
    output_schema: '{\n  "type": "object"\n}',
    preferred_model: '',
    source_url: '',
    version: '1.0',
  });
  const [savingSkill, setSavingSkill] = useState(false);
  const [skillSaveError, setSkillSaveError] = useState<string | null>(null);

  // ── Memory Modal ────────────────────────────────────────────────────────────
  const [memoryAgent, setMemoryAgent] = useState<AgentDefinition | null>(null);

  // ── Delete ──────────────────────────────────────────────────────────────────
  const [deletingAgent, setDeletingAgent] = useState<string | null>(null);
  const [deletingSkill, setDeletingSkill] = useState<string | null>(null);

  // ── Run Modal ───────────────────────────────────────────────────────────────
  const [runAgentTarget, setRunAgentTarget] = useState<AgentDefinition | null>(null);
  const [runLoading, setRunLoading] = useState(false);
  const [runError, setRunError] = useState<string | null>(null);
  const [runResult, setRunResult] = useState<AgentRunResponse | null>(null);

  async function load() {
    setLoading(true);
    setError(null);
    try {
      const [nextAgents, nextSkills, nextActions] = await Promise.all([
        fetchAgents(), fetchSkills(), fetchActions(),
      ]);
      setAgents(nextAgents);
      setSkills(nextSkills);
      setActions(nextActions);
      setRefreshedAt(new Date().toLocaleTimeString('de-DE'));
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : 'Agentendaten konnten nicht geladen werden.');
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => { void load(); }, []);
  useEffect(() => {
    if (!autoRefresh) return undefined;
    const timer = window.setInterval(() => { void load(); }, 15000);
    return () => window.clearInterval(timer);
  }, [autoRefresh]);

  // ── Import ──────────────────────────────────────────────────────────────────
  function resetImportDraft() {
    setGithubUrl('');
    setImportName('');
    setImportDesc('');
    setImportAllowedTools('system_status');
    setImportPreferredModel('');
    setImportCustomInstruction('');
    setImportMaxSteps('5');
    setImportPromptTemplate('Beschreibe die Eingabe strukturiert: {input_json}');
    setImportInputSchema('{\n  "type": "object"\n}');
    setImportOutputSchema('{\n  "type": "object"\n}');
    setImportSourceUrl('');
    setImportVersion('1.0');
  }

  async function handleImport() {
    try {
      if (importType === 'agent') {
        if (importMethod === 'github') {
          await importAgents({ github_url: githubUrl });
        } else {
          const allowedTools = importAllowedTools
            .split(',')
            .map((value) => value.trim())
            .filter(Boolean);
          if (allowedTools.length === 0) {
            throw new Error('Mindestens ein erlaubtes Tool ist erforderlich.');
          }
          await createAgent({
            name: importName.trim(),
            description: importDesc.trim(),
            allowed_tools: allowedTools,
            settings: {
              active: true,
              preferred_model: importPreferredModel.trim() || undefined,
              max_steps: importMaxSteps ? parseInt(importMaxSteps, 10) : undefined,
              custom_instruction: importCustomInstruction.trim() || undefined,
            },
            read_only: true,
          });
        }
      } else {
        if (importMethod === 'github') {
          await importSkills({ github_url: githubUrl });
        } else {
          await createSkill({
            name: importName.trim(),
            description: importDesc.trim(),
            prompt_template: importPromptTemplate.trim(),
            input_schema: parseJsonDraft(importInputSchema, 'Input-Schema'),
            output_schema: parseJsonDraft(importOutputSchema, 'Output-Schema'),
            preferred_model: importPreferredModel.trim() || undefined,
            source_url: importSourceUrl.trim() || undefined,
            version: importVersion.trim() || undefined,
            read_only: true,
          });
        }
      }
      setImportOpen(false);
      resetImportDraft();
      void load();
    } catch (err: unknown) {
      const msg = err instanceof ApiRequestError
        ? `API Fehler: ${err.status} - ${err.body}`
        : err instanceof Error
          ? err.message
          : 'Unbekannter Netzwerkfehler';
      setError('Import fehlgeschlagen: ' + msg);
    }
  }

  // ── Edit ────────────────────────────────────────────────────────────────────
  function openEdit(agent: AgentDefinition) {
    setEditAgent(agent);
    setEditDraft({
      description: agent.description ?? '',
      preferred_model: agent.settings?.preferred_model ?? '',
      custom_instruction: agent.settings?.custom_instruction ?? '',
      max_steps: String(agent.settings?.max_steps ?? agent.max_steps ?? ''),
      active: agent.settings?.active !== false,
    });
    setSaveError(null);
  }

  async function handleSave() {
    if (!editAgent) return;
    setSaving(true);
    setSaveError(null);
    try {
      if (editDraft.description !== (editAgent.description ?? '')) {
        await updateAgent(editAgent.name, { description: editDraft.description });
      }
      await updateAgentSettings(editAgent.name, {
        active: editDraft.active,
        preferred_model: editDraft.preferred_model || undefined,
        custom_instruction: editDraft.custom_instruction || undefined,
        max_steps: editDraft.max_steps ? parseInt(editDraft.max_steps, 10) : undefined,
      });
      setEditAgent(null);
      void load();
    } catch (err) {
      setSaveError(err instanceof ApiRequestError ? `${err.status}: ${err.body}` : 'Speichern fehlgeschlagen');
    } finally {
      setSaving(false);
    }
  }

  async function handleToggleActive(agent: AgentDefinition) {
    try {
      const isActive = agent.settings?.active !== false;
      if (isActive) { await disableAgent(agent.name); } else { await enableAgent(agent.name); }
      void load();
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : 'Status-Änderung fehlgeschlagen');
    }
  }

  async function handleDelete(agent: AgentDefinition) {
    if (!window.confirm(`Agent "${agent.name}" wirklich löschen? Diese Aktion kann nicht rückgängig gemacht werden.`)) return;
    setDeletingAgent(agent.name);
    try {
      await deleteAgent(agent.name);
      void load();
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : 'Löschen fehlgeschlagen');
    } finally {
      setDeletingAgent(null);
    }
  }

  function openSkillEdit(skill: SkillDefinition) {
    setEditSkill(skill);
    setSkillDraft({
      name: skill.name,
      description: skill.description ?? '',
      prompt_template: skill.prompt_template ?? '',
      input_schema: JSON.stringify(skill.input_schema ?? { type: 'object' }, null, 2),
      output_schema: JSON.stringify(skill.output_schema ?? { type: 'object' }, null, 2),
      preferred_model: skill.preferred_model ?? '',
      source_url: skill.source_url ?? '',
      version: skill.version ?? '1.0',
    });
    setSkillSaveError(null);
  }

  async function handleSkillSave() {
    if (!editSkill) return;
    setSavingSkill(true);
    setSkillSaveError(null);
    try {
      await updateSkill(editSkill.name, {
        description: skillDraft.description.trim(),
        prompt_template: skillDraft.prompt_template.trim(),
        input_schema: parseJsonDraft(skillDraft.input_schema, 'Input-Schema'),
        output_schema: parseJsonDraft(skillDraft.output_schema, 'Output-Schema'),
        preferred_model: skillDraft.preferred_model.trim() || undefined,
        source_url: skillDraft.source_url.trim() || undefined,
        version: skillDraft.version.trim() || undefined,
      });
      setEditSkill(null);
      void load();
    } catch (err) {
      setSkillSaveError(
        err instanceof ApiRequestError
          ? `${err.status}: ${err.body}`
          : err instanceof Error
            ? err.message
            : 'Skill konnte nicht gespeichert werden',
      );
    } finally {
      setSavingSkill(false);
    }
  }

  async function handleSkillToggle(skill: SkillDefinition) {
    try {
      if (skill.enabled === false) {
        await enableSkill(skill.name);
      } else {
        await disableSkill(skill.name);
      }
      void load();
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : 'Skill-Status konnte nicht geändert werden.');
    }
  }

  async function handleSkillDelete(skill: SkillDefinition) {
    if (!window.confirm(`Skill "${skill.name}" wirklich löschen?`)) return;
    setDeletingSkill(skill.name);
    try {
      await deleteSkill(skill.name);
      void load();
    } catch (err) {
      setError(err instanceof ApiRequestError ? err.message : 'Skill konnte nicht gelöscht werden.');
    } finally {
      setDeletingSkill(null);
    }
  }

  function buildDefaultRunPrompt(agent: AgentDefinition) {
    const description = agent.description?.trim();
    if (description) {
      return `Führe deine hinterlegte Aufgabe aus: ${description}`;
    }
    return 'Führe deine hinterlegte Aufgabe anhand deiner gespeicherten Konfiguration aus.';
  }

  function openRunModal(agent: AgentDefinition) {
    setRunAgentTarget(agent);
    setRunResult(null);
    setRunError(null);
    void handleRunAgent(agent);
  }

  async function handleRunAgent(agent = runAgentTarget) {
    if (!agent) return;
    setRunLoading(true);
    setRunError(null);
    setRunResult(null);
    try {
      const result = await runAgent(agent.name, buildDefaultRunPrompt(agent));
      setRunResult(result);
      void load();
    } catch (err) {
      setRunError(err instanceof ApiRequestError ? `${err.status}: ${err.body}` : 'Agent-Run fehlgeschlagen.');
    } finally {
      setRunLoading(false);
    }
  }

  const supervisor = agents.find((a) => a.name === 'guardian_supervisor') ?? agents[0] ?? null;
  const agentsWithActivity = useMemo(() => agents.filter((a) => a.activity?.last_run_at), [agents]);
  const lastActiveAgent = useMemo(() =>
    [...agentsWithActivity].sort((a, b) => {
      const at = a.activity?.last_run_at ? new Date(a.activity.last_run_at).getTime() : 0;
      const bt = b.activity?.last_run_at ? new Date(b.activity.last_run_at).getTime() : 0;
      return bt - at;
    })[0] ?? null, [agentsWithActivity]);

  return (
    <Layout title="Agenten">

      {/* ── Import Modal ── */}
      <Modal isOpen={importOpen} onClose={() => setImportOpen(false)} title="Agent / Skill importieren">
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div className="kv">
            <span className="kv__label">Typ</span>
            <select className="form-input" value={importType} onChange={(e) => setImportType(e.target.value as 'agent' | 'skill')}>
              <option value="agent">Agent</option>
              <option value="skill">Skill</option>
            </select>
          </div>
          <div className="kv">
            <span className="kv__label">Methode</span>
            <select className="form-input" value={importMethod} onChange={(e) => setImportMethod(e.target.value as 'manual' | 'github')}>
              <option value="manual">Manuell</option>
              <option value="github">GitHub URL</option>
            </select>
          </div>
          {importMethod === 'github' ? (
            <input className="form-input" placeholder="GitHub URL" value={githubUrl} onChange={(e) => setGithubUrl(e.target.value)} />
          ) : (
            <>
              <input className="form-input" placeholder="Name" value={importName} onChange={(e) => setImportName(e.target.value)} />
              <input className="form-input" placeholder="Beschreibung" value={importDesc} onChange={(e) => setImportDesc(e.target.value)} />
              {importType === 'agent' ? (
                <>
                  <input
                    className="form-input"
                    placeholder="Erlaubte Tools, komma-getrennt"
                    value={importAllowedTools}
                    onChange={(e) => setImportAllowedTools(e.target.value)}
                  />
                  <input
                    className="form-input"
                    placeholder="Bevorzugtes Modell (optional)"
                    value={importPreferredModel}
                    onChange={(e) => setImportPreferredModel(e.target.value)}
                  />
                  <input
                    className="form-input"
                    type="number"
                    min={1}
                    max={20}
                    placeholder="Max. Schritte"
                    value={importMaxSteps}
                    onChange={(e) => setImportMaxSteps(e.target.value)}
                  />
                  <textarea
                    className="form-input form-input--textarea"
                    rows={5}
                    placeholder="Custom Instruction (optional)"
                    value={importCustomInstruction}
                    onChange={(e) => setImportCustomInstruction(e.target.value)}
                  />
                </>
              ) : (
                <>
                  <textarea
                    className="form-input form-input--textarea"
                    rows={5}
                    placeholder="Prompt-Template"
                    value={importPromptTemplate}
                    onChange={(e) => setImportPromptTemplate(e.target.value)}
                  />
                  <textarea
                    className="form-input form-input--textarea"
                    rows={5}
                    placeholder="Input-Schema als JSON-Objekt"
                    value={importInputSchema}
                    onChange={(e) => setImportInputSchema(e.target.value)}
                    style={{ fontFamily: 'var(--font-mono)', fontSize: '0.76rem' }}
                  />
                  <textarea
                    className="form-input form-input--textarea"
                    rows={5}
                    placeholder="Output-Schema als JSON-Objekt"
                    value={importOutputSchema}
                    onChange={(e) => setImportOutputSchema(e.target.value)}
                    style={{ fontFamily: 'var(--font-mono)', fontSize: '0.76rem' }}
                  />
                  <input
                    className="form-input"
                    placeholder="Bevorzugtes Modell (optional)"
                    value={importPreferredModel}
                    onChange={(e) => setImportPreferredModel(e.target.value)}
                  />
                  <input
                    className="form-input"
                    placeholder="Source URL (optional)"
                    value={importSourceUrl}
                    onChange={(e) => setImportSourceUrl(e.target.value)}
                  />
                  <input
                    className="form-input"
                    placeholder="Version"
                    value={importVersion}
                    onChange={(e) => setImportVersion(e.target.value)}
                  />
                </>
              )}
            </>
          )}
          <button className="btn" style={{ background: 'var(--indigo-500)', color: '#fff' }} onClick={() => void handleImport()}>
            {importMethod === 'github' ? 'Importieren' : 'Anlegen'}
          </button>
        </div>
      </Modal>

      {/* ── Edit Modal ── */}
      <Modal isOpen={editAgent !== null} onClose={() => setEditAgent(null)} title={`Agent bearbeiten: ${editAgent?.name ?? ''}`}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1.1rem' }}>
          <div className="form-group">
            <label className="form-label">Beschreibung</label>
            <input className="form-input" value={editDraft.description}
              onChange={(e) => setEditDraft((d) => ({ ...d, description: e.target.value }))}
              placeholder="Kurzbeschreibung des Agenten" />
          </div>
          <div className="form-group">
            <label className="form-label">Hauptprompt (Custom Instruction)</label>
            <textarea className="form-input form-input--textarea" rows={8}
              style={{ fontFamily: 'var(--font-mono)', fontSize: '0.78rem' }}
              value={editDraft.custom_instruction}
              onChange={(e) => setEditDraft((d) => ({ ...d, custom_instruction: e.target.value }))}
              placeholder="Eigene Anweisungen, die in den System-Prompt eingefügt werden…" />
          </div>
          <div className="form-group">
            <label className="form-label">Bevorzugtes Modell</label>
            <input className="form-input" value={editDraft.preferred_model}
              onChange={(e) => setEditDraft((d) => ({ ...d, preferred_model: e.target.value }))}
              placeholder="z. B. qwen2.5-coder:3b (leer = Router-Standard)" />
          </div>
          <div className="form-group">
            <label className="form-label">Max. Schritte</label>
            <input className="form-input" type="number" min={1} max={20}
              value={editDraft.max_steps}
              onChange={(e) => setEditDraft((d) => ({ ...d, max_steps: e.target.value }))}
              placeholder="1–20" />
          </div>
          <div className="form-group">
            <label className="form-label">Status</label>
            <div className="toggle-row">
              <button className={`btn btn--sm ${editDraft.active ? 'btn--active' : 'btn--ghost'}`}
                onClick={() => setEditDraft((d) => ({ ...d, active: true }))}>Aktiv</button>
              <button className={`btn btn--sm ${!editDraft.active ? 'btn--active' : 'btn--ghost'}`}
                onClick={() => setEditDraft((d) => ({ ...d, active: false }))}>Inaktiv</button>
            </div>
          </div>
          {saveError && <div className="alert alert--error">{saveError}</div>}
          <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
            <button className="btn btn--ghost btn--sm" onClick={() => setEditAgent(null)}>Abbrechen</button>
            <button className="btn btn--sm" style={{ background: 'var(--indigo-500)', color: '#fff' }}
              onClick={() => void handleSave()} disabled={saving}>
              {saving ? 'Speichere…' : 'Speichern'}
            </button>
          </div>
        </div>
      </Modal>

      <Modal isOpen={editSkill !== null} onClose={() => setEditSkill(null)} title={`Skill bearbeiten: ${editSkill?.name ?? ''}`}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <input
            className="form-input"
            value={skillDraft.description}
            onChange={(e) => setSkillDraft((draft) => ({ ...draft, description: e.target.value }))}
            placeholder="Beschreibung"
          />
          <textarea
            className="form-input form-input--textarea"
            rows={6}
            value={skillDraft.prompt_template}
            onChange={(e) => setSkillDraft((draft) => ({ ...draft, prompt_template: e.target.value }))}
            placeholder="Prompt-Template"
          />
          <textarea
            className="form-input form-input--textarea"
            rows={5}
            value={skillDraft.input_schema}
            onChange={(e) => setSkillDraft((draft) => ({ ...draft, input_schema: e.target.value }))}
            placeholder="Input-Schema als JSON-Objekt"
            style={{ fontFamily: 'var(--font-mono)', fontSize: '0.76rem' }}
          />
          <textarea
            className="form-input form-input--textarea"
            rows={5}
            value={skillDraft.output_schema}
            onChange={(e) => setSkillDraft((draft) => ({ ...draft, output_schema: e.target.value }))}
            placeholder="Output-Schema als JSON-Objekt"
            style={{ fontFamily: 'var(--font-mono)', fontSize: '0.76rem' }}
          />
          <input
            className="form-input"
            value={skillDraft.preferred_model}
            onChange={(e) => setSkillDraft((draft) => ({ ...draft, preferred_model: e.target.value }))}
            placeholder="Bevorzugtes Modell (optional)"
          />
          <input
            className="form-input"
            value={skillDraft.source_url}
            onChange={(e) => setSkillDraft((draft) => ({ ...draft, source_url: e.target.value }))}
            placeholder="Source URL (optional)"
          />
          <input
            className="form-input"
            value={skillDraft.version}
            onChange={(e) => setSkillDraft((draft) => ({ ...draft, version: e.target.value }))}
            placeholder="Version"
          />
          {skillSaveError && <div className="alert alert--error">{skillSaveError}</div>}
          <div style={{ display: 'flex', gap: '0.5rem', justifyContent: 'flex-end' }}>
            <button className="btn btn--ghost btn--sm" onClick={() => setEditSkill(null)}>Abbrechen</button>
            <button
              className="btn btn--sm"
              style={{ background: 'var(--indigo-500)', color: '#fff' }}
              onClick={() => void handleSkillSave()}
              disabled={savingSkill}
            >
              {savingSkill ? 'Speichere…' : 'Speichern'}
            </button>
          </div>
        </div>
      </Modal>

      <Modal isOpen={runAgentTarget !== null} onClose={() => setRunAgentTarget(null)} title={`Agent ausführen: ${runAgentTarget?.name ?? ''}`}>
        <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
          <div className="alert alert--info">
            Der Agent wird direkt mit seiner hinterlegten Aufgabe und Konfiguration ausgeführt. Ein zusätzlicher manueller Prompt ist nicht mehr erforderlich.
          </div>
          {runAgentTarget?.description && (
            <div>
              <strong>Hinterlegte Aufgabe</strong>
              <pre className="code-block" style={{ whiteSpace: 'pre-wrap' }}>{runAgentTarget.description}</pre>
            </div>
          )}
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <button
              className="btn btn--sm"
              style={{ background: 'var(--indigo-500)', color: '#fff' }}
              onClick={() => void handleRunAgent()}
              disabled={runLoading}
            >
              {runLoading ? 'Läuft…' : 'Erneut starten'}
            </button>
          </div>
          {runError && <div className="alert alert--error">{runError}</div>}
          {runResult && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '0.8rem' }}>
              <div className={`alert ${runResult.success ? 'alert--success' : 'alert--warn'}`}>
                <strong>{runResult.success ? 'Erfolgreich' : 'Fehlgeschlagen'}</strong>
                <div>Modell: {runResult.used_model ?? '–'}</div>
                <div>Run-ID: {runResult.run_id ?? '–'}</div>
              </div>
              <div>
                <strong>Antwort</strong>
                <pre className="code-block" style={{ whiteSpace: 'pre-wrap' }}>{runResult.final_answer || '–'}</pre>
              </div>
              {runResult.errors.length > 0 && (
                <div>
                  <strong>Fehler</strong>
                  <pre className="code-block" style={{ whiteSpace: 'pre-wrap' }}>{runResult.errors.join('\n')}</pre>
                </div>
              )}
              <div>
                <strong>Schritte</strong>
                <pre className="code-block" style={{ whiteSpace: 'pre-wrap', maxHeight: '18rem', overflow: 'auto' }}>
                  {JSON.stringify(runResult.steps, null, 2)}
                </pre>
              </div>
            </div>
          )}
        </div>
      </Modal>

      {/* ── Memory Modal ── */}
      <Modal
        isOpen={memoryAgent !== null}
        onClose={() => setMemoryAgent(null)}
        title={`Gedächtnis: ${memoryAgent?.name ?? ''}`}
      >
        {memoryAgent && <MemoryPanel agent={memoryAgent} onClose={() => setMemoryAgent(null)} />}
      </Modal>

      {/* ── Summary Cards ── */}
      <div className="grid grid--dense">
        <Card title="Registry" tag="LIVE">
          <button className="btn btn--sm" style={{ marginBottom: '1rem' }} onClick={() => setImportOpen(true)}>
            Hinzufügen
          </button>
          <div className="kv"><span className="kv__label">Agenten</span><span className="kv__value">{agents.length}</span></div>
          <div className="kv"><span className="kv__label">Skills</span><span className="kv__value">{skills.length}</span></div>
          <div className="kv"><span className="kv__label">Actions</span><span className="kv__value">{actions.length}</span></div>
          <div className="kv"><span className="kv__label">Mit Aktivität</span><span className="kv__value">{agentsWithActivity.length}</span></div>
          <div className="kv"><span className="kv__label">Letztes Update</span><span className="kv__value">{refreshedAt ?? '–'}</span></div>
          <button className="btn btn--sm" onClick={() => void load()} disabled={loading} style={{ marginTop: '0.5rem' }}>
            {loading ? 'Lade…' : 'Neu laden'}
          </button>
        </Card>

        <Card title="guardian_supervisor" tag={supervisor?.read_only ? 'READ ONLY' : 'CUSTOM'}>
          {supervisor ? (
            <>
              <div className="kv"><span className="kv__label">Typ</span><span className="kv__value">{supervisor.agent_type ?? '–'}</span></div>
              <div className="kv"><span className="kv__label">Modell</span><code className="kv__value">{supervisor.settings?.preferred_model ?? '–'}</code></div>
              <div className="kv"><span className="kv__label">Max Steps</span><span className="kv__value">{supervisor.settings?.max_steps ?? supervisor.max_steps ?? '–'}</span></div>
              <div className="kv"><span className="kv__label">Letzter Lauf</span><span className="kv__value">{formatDateTime(supervisor.activity?.last_run_at)}</span></div>
              {supervisor.settings?.custom_instruction && (
                <div className="kv" style={{ alignItems: 'flex-start', marginTop: '0.5rem' }}>
                  <span className="kv__label">Anweisung</span>
                  <pre className="code-block" style={{ whiteSpace: 'pre-wrap', fontSize: '0.72rem', maxHeight: '6rem', overflow: 'auto' }}>
                    {supervisor.settings.custom_instruction}
                  </pre>
                </div>
              )}
              <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.75rem' }}>
                <button className="btn btn--sm" style={{ background: 'var(--indigo-500)', color: '#fff' }}
                  onClick={() => openEdit(supervisor)}>Bearbeiten</button>
                <button className="btn btn--sm btn--ghost"
                  onClick={() => openRunModal(supervisor)}>Run</button>
                <button className="btn btn--sm btn--ghost"
                  onClick={() => setMemoryAgent(supervisor)}>Gedächtnis</button>
              </div>
            </>
          ) : (
            <p className="text--muted">Kein Agent gefunden.</p>
          )}
        </Card>

        <Card title="Zugriff" tag="STATUS">
          <div className="kv" style={{ marginTop: '0.25rem' }}>
            <span className="kv__label">Auto-Refresh</span>
            <div className="toggle-row">
              <button className={`btn btn--sm ${autoRefresh ? 'btn--active' : 'btn--ghost'}`} onClick={() => setAutoRefresh(true)}>Aktiv</button>
              <button className={`btn btn--sm ${!autoRefresh ? 'btn--active' : 'btn--ghost'}`} onClick={() => setAutoRefresh(false)}>Aus</button>
            </div>
          </div>
          <div className="kv"><span className="kv__label">Zuletzt aktiv</span><span className="kv__value">{lastActiveAgent?.name ?? '–'}</span></div>
        </Card>
      </div>

      {error && (
        <div className="alert alert--error" style={{ marginTop: '1.5rem' }}>
          <strong>Fehler:</strong> {error}
          <button className="btn btn--sm btn--ghost" style={{ marginLeft: '1rem' }} onClick={() => setError(null)}>✕</button>
        </div>
      )}

      <div className="section">
        <SortableCardGrid
          items={agents}
          getItemId={(agent) => agent.name}
          storageKey="piGuardian.agentCardOrder"
          emptyState={!loading ? (
            <EmptyCollectionState
              title="Keine Agenten geladen"
              description="Sobald die API Agenten meldet, erscheinen sie hier als verschiebbare Cards."
            />
          ) : null}
          renderItem={(agent, dragState) => {
            const isActive = agent.settings?.active !== false;
            const lastRunLabel = agent.activity?.last_status === 'success'
              ? 'Erfolgreich'
              : agent.activity?.last_status === 'failed'
                ? 'Fehlgeschlagen'
                : 'Keine Runs';

            return (
              <Card
                title={agent.name}
                tag={agent.agent_type ?? 'agent'}
                className={`entity-card${dragState.isDragging ? ' entity-card--dragging' : ''}${dragState.isDropTarget ? ' entity-card--drop-target' : ''}`}
                headerActions={(
                  <>
                    <span className={`badge ${isActive ? 'badge--ok' : 'badge--warn'}`}>
                      <span className="badge__dot" />
                      {isActive ? 'Aktiv' : 'Inaktiv'}
                    </span>
                    {agent.read_only ? (
                      <span className="badge badge--warn">
                        <span className="badge__dot" />
                        Read only
                      </span>
                    ) : (
                      <span className="badge badge--ok">
                        <span className="badge__dot" />
                        Editierbar
                      </span>
                    )}
                    <button {...dragState.dragHandleProps} />
                  </>
                )}
              >
                <p className="entity-card__lead">{agent.description || 'Keine Beschreibung vorhanden.'}</p>

                <div className="entity-card__meta-grid">
                  <MetaItem label="Modell" value={agent.activity?.last_model ?? agent.settings?.preferred_model ?? '–'} />
                  <MetaItem label="Max Steps" value={agent.settings?.max_steps ?? agent.max_steps ?? '–'} />
                  <MetaItem label="Letzter Lauf" value={formatDateTime(agent.activity?.last_run_at)} />
                  <MetaItem label="Run-Status" value={lastRunLabel} plain />
                </div>

                <div className="entity-card__section">
                  <span className="entity-card__section-title">Erlaubte Tools</span>
                  {agent.allowed_tools.length > 0 ? (
                    <div className="entity-card__pill-list">
                      {agent.allowed_tools.map((tool) => (
                        <span key={tool} className="agent-tool-pill">{tool}</span>
                      ))}
                    </div>
                  ) : (
                    <div className="entity-card__empty">Keine Tools hinterlegt.</div>
                  )}
                </div>

                <div className="entity-card__footer">
                  <span className="text--muted text--xs">
                    {agent.activity?.total_runs ?? 0} Runs, {agent.activity?.failed_runs ?? 0} Fehler
                  </span>
                  <div className="entity-card__actions">
                    <button
                      className="btn btn--sm btn--ghost"
                      onClick={() => openRunModal(agent)}
                      title="Agent manuell ausführen"
                    >
                      Run
                    </button>
                    <button
                      className="btn btn--sm"
                      style={{ background: 'var(--indigo-500)', color: '#fff' }}
                      onClick={() => openEdit(agent)}
                    >
                      Bearbeiten
                    </button>
                    <button
                      className="btn btn--sm btn--ghost"
                      onClick={() => setMemoryAgent(agent)}
                      title="Gedächtnis anzeigen"
                    >
                      Gedächtnis
                    </button>
                    <button
                      className="btn btn--sm btn--ghost"
                      onClick={() => void handleToggleActive(agent)}
                      title={isActive ? 'Deaktivieren' : 'Aktivieren'}
                    >
                      {isActive ? 'Deakt.' : 'Akt.'}
                    </button>
                    {!agent.read_only && (
                      <button
                        className="btn btn--sm btn--danger"
                        onClick={() => void handleDelete(agent)}
                        disabled={deletingAgent === agent.name}
                        title={`Agent "${agent.name}" löschen`}
                      >
                        {deletingAgent === agent.name ? '…' : 'Löschen'}
                      </button>
                    )}
                  </div>
                </div>
              </Card>
            );
          }}
        />
      </div>

      <div className="section">
        <Card title="Skills" tag="API">
          <SortableCardGrid
            items={skills}
            getItemId={(skill) => skill.name}
            storageKey="piGuardian.skillCardOrder"
            emptyState={!loading ? (
              <EmptyCollectionState
                title="Keine Skills geladen"
                description="Skill-Definitionen erscheinen hier als responsive Cards."
              />
            ) : null}
            renderItem={(skill, dragState) => {
              const isEnabled = skill.enabled !== false;
              const isProtected = skill.skill_type === 'system';

              return (
                <Card
                  title={skill.name}
                  tag={skill.skill_type ?? 'custom'}
                  className={`entity-card${dragState.isDragging ? ' entity-card--dragging' : ''}${dragState.isDropTarget ? ' entity-card--drop-target' : ''}`}
                  headerActions={(
                    <>
                      <span className={`badge ${isEnabled ? 'badge--ok' : 'badge--warn'}`}>
                        <span className="badge__dot" />
                        {isEnabled ? 'Aktiv' : 'Inaktiv'}
                      </span>
                      <span className={`badge ${skill.read_only ? 'badge--warn' : 'badge--ok'}`}>
                        <span className="badge__dot" />
                        {skill.read_only ? 'Read only' : 'Editierbar'}
                      </span>
                      <button {...dragState.dragHandleProps} />
                    </>
                  )}
                >
                  <p className="entity-card__lead">{skill.description || 'Keine Beschreibung vorhanden.'}</p>

                  <div className="entity-card__meta-grid">
                    <MetaItem label="Version" value={skill.version ?? '–'} />
                    <MetaItem label="Modell" value={skill.preferred_model ?? '–'} />
                    <MetaItem label="Schutz" value={isProtected ? 'System-Skill' : 'Custom-Skill'} plain />
                  </div>

                  <div className="entity-card__section">
                    <span className="entity-card__section-title">Source</span>
                    {skill.source_url ? (
                      <div className="entity-card__meta-value">{skill.source_url}</div>
                    ) : (
                      <div className="entity-card__empty">Keine Source-URL hinterlegt.</div>
                    )}
                  </div>

                  <div className="entity-card__footer">
                    <span className="text--muted text--xs">
                      {skill.allowed_tools.length} erlaubte Tools
                    </span>
                    <div className="entity-card__actions">
                      <button
                        className="btn btn--sm"
                        style={{ background: 'var(--indigo-500)', color: '#fff' }}
                        onClick={() => openSkillEdit(skill)}
                        disabled={isProtected}
                        title={isProtected ? 'System-Skills können nicht bearbeitet werden.' : 'Skill bearbeiten'}
                      >
                        Bearbeiten
                      </button>
                      <button
                        className="btn btn--sm btn--ghost"
                        onClick={() => void handleSkillToggle(skill)}
                        title={isEnabled ? 'Skill deaktivieren' : 'Skill aktivieren'}
                      >
                        {isEnabled ? 'Deakt.' : 'Akt.'}
                      </button>
                      <button
                        className="btn btn--sm btn--danger"
                        onClick={() => void handleSkillDelete(skill)}
                        disabled={deletingSkill === skill.name || isProtected}
                        title={isProtected ? 'Geschützte Skills können nicht gelöscht werden.' : `Skill "${skill.name}" löschen`}
                      >
                        {deletingSkill === skill.name ? '…' : 'Löschen'}
                      </button>
                    </div>
                  </div>
                </Card>
              );
            }}
          />
        </Card>
      </div>

      <div className="section">
        <Card title="Actions" tag="API">
          <SortableCardGrid
            items={actions}
            getItemId={(action) => action.name}
            storageKey="piGuardian.actionCardOrder"
            emptyState={!loading ? (
              <EmptyCollectionState
                title="Keine Actions geladen"
                description="Sobald Actions vorhanden sind, lassen sie sich hier lokal umsortieren."
              />
            ) : null}
            renderItem={(action, dragState) => {
              const isEnabled = action.enabled !== false;

              return (
                <Card
                  title={action.name}
                  tag="action"
                  className={`entity-card${dragState.isDragging ? ' entity-card--dragging' : ''}${dragState.isDropTarget ? ' entity-card--drop-target' : ''}`}
                  headerActions={(
                    <>
                      <span className={`badge ${action.requires_approval ? 'badge--warn' : 'badge--ok'}`}>
                        <span className="badge__dot" />
                        {action.requires_approval ? 'Approval' : 'Direkt'}
                      </span>
                      <span className={`badge ${isEnabled ? 'badge--ok' : 'badge--warn'}`}>
                        <span className="badge__dot" />
                        {isEnabled ? 'Aktiv' : 'Inaktiv'}
                      </span>
                      <button {...dragState.dragHandleProps} />
                    </>
                  )}
                >
                  <p className="entity-card__lead">{action.description || 'Keine Beschreibung vorhanden.'}</p>

                  <div className="entity-card__section">
                    <span className="entity-card__section-title">Allowed Targets</span>
                    {action.allowed_targets.length > 0 ? (
                      <div className="entity-card__pill-list">
                        {action.allowed_targets.map((target) => (
                          <span key={target} className="agent-tool-pill">{target}</span>
                        ))}
                      </div>
                    ) : (
                      <div className="entity-card__empty">Keine Targets hinterlegt.</div>
                    )}
                  </div>
                </Card>
              );
            }}
          />
        </Card>
      </div>
    </Layout>
  );
}
