import { CONFIG } from '../config';
import type {
  ActionDefinition,
  AgentDefinition,
  AgentRunResponse,
  ClientCreate,
  ClientRead,
  ClientUpdate,
  HealthResponse,
  LogEntry,
  MemoryFeedbackEntryRead,
  MemoryIncidentCreate,
  MemoryIncidentRead,
  MemoryKnowledgeEntryCreate,
  MemoryKnowledgeEntryRead,
  MemoryRunDetail,
  MemoryRunSummary,
  ModelPullJob,
  ModelRegistryEntry,
  ModelRegistryEntryCreate,
  OllamaModel,
  RouteHistoryEntry,
  RouteResponse,
  RouterSettings,
  ServiceStatus,
  SettingsUpdateResponse,
  SkillDefinition,
} from '../types';

// ── Fehlerklasse ─────────────────────────────────────────────────────────────

export class ApiRequestError extends Error {
  constructor(
    message: string,
    public readonly status: number,
    public readonly body: string,
  ) {
    super(message);
    this.name = 'ApiRequestError';
  }
}

// ── Basis-Fetch ───────────────────────────────────────────────────────────────

interface FetchOptions extends RequestInit {
  timeout?: number;
}

async function apiFetch<T>(
  path: string,
  options: FetchOptions = {},
  timeout = CONFIG.defaultTimeout,
): Promise<T> {
  const { timeout: _ignored, ...init } = options;
  const controller = new AbortController();
  const timer = window.setTimeout(() => controller.abort(), timeout);

  try {
    const headers = new Headers(init.headers ?? {});
    headers.set('Accept', 'application/json');
    if (init.body) headers.set('Content-Type', 'application/json');

    const response = await fetch(`${CONFIG.apiBaseUrl}${path}`, {
      ...init,
      credentials: 'include',
      signal: controller.signal,
      headers,
    });

    if (!response.ok) {
      const body = await response.text().catch(() => '');
      throw new ApiRequestError(
        `HTTP ${response.status}: ${response.statusText}`,
        response.status,
        body,
      );
    }

    if (response.status === 204) return undefined as T;

    const ct = response.headers.get('content-type') ?? '';
    if (!ct.includes('application/json')) return undefined as T;

    return (await response.json()) as T;
  } catch (err) {
    if (err instanceof ApiRequestError) throw err;
    if (err instanceof DOMException && err.name === 'AbortError') {
      throw new ApiRequestError(`Timeout nach ${timeout}ms`, 0, '');
    }
    throw new ApiRequestError(
      err instanceof Error ? err.message : 'Unbekannter Fehler',
      0,
      '',
    );
  } finally {
    window.clearTimeout(timer);
  }
}

export function describeApiError(error: unknown, fallback = 'Unbekannter Fehler'): string {
  if (error instanceof ApiRequestError) {
    if (error.status > 0) return `HTTP ${error.status}: ${error.body || error.message}`;
    return error.message || fallback;
  }
  if (error instanceof Error) return error.message || fallback;
  return fallback;
}

// ── Health ────────────────────────────────────────────────────────────────────

export function fetchHealth(): Promise<HealthResponse> {
  return apiFetch<HealthResponse>('/health');
}

// ── Dienststatus ──────────────────────────────────────────────────────────────

export function fetchServiceStatus(): Promise<ServiceStatus> {
  return apiFetch<ServiceStatus>('/status/service');
}

// ── Route (LLM) ───────────────────────────────────────────────────────────────

export function sendRoute(
  prompt: string,
  preferredModel?: string,
): Promise<RouteResponse> {
  return apiFetch<RouteResponse>(
    '/route',
    {
      method: 'POST',
      body: JSON.stringify({
        prompt,
        preferred_model: preferredModel ?? null,
        stream: false,
      }),
    },
    CONFIG.modelTimeout,
  );
}

// ── Einstellungen ─────────────────────────────────────────────────────────────

export function fetchSettings(): Promise<RouterSettings> {
  return apiFetch<RouterSettings>('/settings');
}

export function updateSettings(data: Partial<RouterSettings>): Promise<SettingsUpdateResponse> {
  return apiFetch<SettingsUpdateResponse>('/settings', {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

// ── Modelle ───────────────────────────────────────────────────────────────────

export function fetchModels(): Promise<OllamaModel[]> {
  return apiFetch<OllamaModel[]>('/models');
}

export function selectModel(model: string): Promise<void> {
  return apiFetch<void>('/models/select', {
    method: 'POST',
    body: JSON.stringify({ model }),
  });
}

export function fetchModelRegistry(): Promise<ModelRegistryEntry[]> {
  return apiFetch<ModelRegistryEntry[]>('/models/registry');
}

export function createModelRegistryEntry(
  data: ModelRegistryEntryCreate,
): Promise<ModelRegistryEntry> {
  return apiFetch<ModelRegistryEntry>('/models/registry', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateModelRegistryEntry(
  id: number,
  data: Partial<ModelRegistryEntryCreate>,
): Promise<ModelRegistryEntry> {
  return apiFetch<ModelRegistryEntry>(`/models/registry/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export function deleteModelRegistryEntry(id: number): Promise<void> {
  return apiFetch<void>(`/models/registry/${id}`, { method: 'DELETE' });
}

export function deleteOllamaModel(name: string): Promise<void> {
  return apiFetch<void>(`/models/delete/${encodeURIComponent(name)}`, { method: 'DELETE' });
}

export function fetchModelPullJobs(limit = 10): Promise<ModelPullJob[]> {
  return apiFetch<ModelPullJob[]>(`/models/pull?limit=${limit}`);
}

export function createModelPullJob(modelName: string): Promise<ModelPullJob> {
  return apiFetch<ModelPullJob>('/models/pull', {
    method: 'POST',
    body: JSON.stringify({ model_name: modelName }),
  });
}

// ── Clients ───────────────────────────────────────────────────────────────────

export function fetchClients(): Promise<ClientRead[]> {
  return apiFetch<ClientRead[]>('/clients');
}

export function createClient(data: ClientCreate): Promise<ClientRead> {
  return apiFetch<ClientRead>('/clients', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateClient(id: number, data: ClientUpdate): Promise<ClientRead> {
  return apiFetch<ClientRead>(`/clients/${id}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export function deleteClient(id: number): Promise<void> {
  return apiFetch<void>(`/clients/${id}`, { method: 'DELETE' });
}

// ── Logs & History ─────────────────────────────────────────────────────────────

export function fetchLogs(limit = 50): Promise<LogEntry[]> {
  return apiFetch<LogEntry[]>(`/logs?limit=${limit}`);
}

export function fetchRouteHistory(limit = 25): Promise<RouteHistoryEntry[]> {
  return apiFetch<RouteHistoryEntry[]>(`/history?limit=${limit}`);
}

// ── Agents ────────────────────────────────────────────────────────────────────

export function fetchAgents(): Promise<AgentDefinition[]> {
  return apiFetch<AgentDefinition[]>('/agents');
}

export function createAgent(data: {
  name: string;
  description: string;
  allowed_tools: string[];
  settings?: Record<string, unknown>;
  read_only?: boolean;
}): Promise<AgentDefinition> {
  return apiFetch<AgentDefinition>('/agents', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function importAgents(data: { agents?: any[]; github_url?: string }): Promise<any> {
  return apiFetch<any>('/agents/import/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateAgent(name: string, data: { description?: string }): Promise<AgentDefinition> {
  return apiFetch<AgentDefinition>(`/agents/${encodeURIComponent(name)}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export function updateAgentSettings(
  name: string,
  data: { active?: boolean; preferred_model?: string; custom_instruction?: string; max_steps?: number },
): Promise<AgentDefinition> {
  return apiFetch<AgentDefinition>(`/agents/${encodeURIComponent(name)}/settings`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export function deleteAgent(name: string): Promise<void> {
  return apiFetch<void>(`/agents/${encodeURIComponent(name)}`, { method: 'DELETE' });
}

export function enableAgent(name: string): Promise<AgentDefinition> {
  return apiFetch<AgentDefinition>(`/agents/${encodeURIComponent(name)}/enable`, { method: 'POST' });
}

export function disableAgent(name: string): Promise<AgentDefinition> {
  return apiFetch<AgentDefinition>(`/agents/${encodeURIComponent(name)}/disable`, { method: 'POST' });
}

export function runAgent(agentName: string, input: string): Promise<AgentRunResponse> {
  return apiFetch<AgentRunResponse>(
    '/agents/run',
    { method: 'POST', body: JSON.stringify({ agent_name: agentName, input }) },
    CONFIG.modelTimeout,
  );
}

// ── Skills ────────────────────────────────────────────────────────────────────

export function fetchSkills(): Promise<SkillDefinition[]> {
  return apiFetch<SkillDefinition[]>('/skills');
}

export function createSkill(data: {
  name: string;
  description: string;
  prompt_template: string;
  input_schema?: Record<string, unknown>;
  output_schema?: Record<string, unknown>;
  preferred_model?: string;
  source_url?: string;
  version?: string;
  read_only?: boolean;
}): Promise<SkillDefinition> {
  return apiFetch<SkillDefinition>('/skills', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function updateSkill(
  name: string,
  data: {
    description?: string;
    prompt_template?: string;
    input_schema?: Record<string, unknown>;
    output_schema?: Record<string, unknown>;
    preferred_model?: string;
    source_url?: string;
    version?: string;
  },
): Promise<SkillDefinition> {
  return apiFetch<SkillDefinition>(`/skills/${encodeURIComponent(name)}`, {
    method: 'PUT',
    body: JSON.stringify(data),
  });
}

export function deleteSkill(name: string): Promise<void> {
  return apiFetch<void>(`/skills/${encodeURIComponent(name)}`, { method: 'DELETE' });
}

export function enableSkill(name: string): Promise<SkillDefinition> {
  return apiFetch<SkillDefinition>(`/skills/${encodeURIComponent(name)}/enable`, { method: 'POST' });
}

export function disableSkill(name: string): Promise<SkillDefinition> {
  return apiFetch<SkillDefinition>(`/skills/${encodeURIComponent(name)}/disable`, { method: 'POST' });
}

export function importSkills(data: { skills?: any[]; github_url?: string }): Promise<any> {
  return apiFetch<any>('/skills/import/', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

// ── Actions ───────────────────────────────────────────────────────────────────

export function fetchActions(): Promise<ActionDefinition[]> {
  return apiFetch<ActionDefinition[]>('/actions');
}

export function executeAction(name: string, input: Record<string, unknown> = {}): Promise<unknown> {
  return apiFetch<unknown>('/actions/execute', {
    method: 'POST',
    body: JSON.stringify({ name, input }),
  });
}

// ── Agent Memory ──────────────────────────────────────────────────────────────

export function fetchAgentMemory(agentName: string): Promise<import('../types').AgentMemoryEntry[]> {
  return apiFetch(`/agents/${encodeURIComponent(agentName)}/memory`);
}

export function addAgentMemory(
  agentName: string,
  data: import('../types').AgentMemoryEntryCreate,
): Promise<import('../types').AgentMemoryEntry> {
  return apiFetch(`/agents/${encodeURIComponent(agentName)}/memory`, {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function confirmAgentMemory(agentName: string, memoryId: number): Promise<import('../types').AgentMemoryEntry> {
  return apiFetch(`/agents/${encodeURIComponent(agentName)}/memory/${memoryId}/confirm`, { method: 'PUT' });
}

export function deleteAgentMemory(agentName: string, memoryId: number): Promise<void> {
  return apiFetch(`/agents/${encodeURIComponent(agentName)}/memory/${memoryId}`, { method: 'DELETE' });
}

export function extractAgentMemory(agentName: string): Promise<import('../types').AgentMemoryEntry[]> {
  return apiFetch(`/agents/${encodeURIComponent(agentName)}/memory/extract`, { method: 'POST' });
}

// ── Memory ────────────────────────────────────────────────────────────────────

export function fetchMemoryRuns(limit = 20): Promise<MemoryRunSummary[]> {
  return apiFetch<MemoryRunSummary[]>(`/memory/runs?limit=${limit}`);
}

export function fetchMemoryRunDetail(runId: string): Promise<MemoryRunDetail> {
  return apiFetch<MemoryRunDetail>(`/memory/runs/${runId}`);
}

export function fetchMemoryIncidents(): Promise<MemoryIncidentRead[]> {
  return apiFetch<MemoryIncidentRead[]>('/memory/incidents');
}

export function createMemoryIncident(data: MemoryIncidentCreate): Promise<MemoryIncidentRead> {
  return apiFetch<MemoryIncidentRead>('/memory/incidents', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function fetchMemoryKnowledge(): Promise<MemoryKnowledgeEntryRead[]> {
  return apiFetch<MemoryKnowledgeEntryRead[]>('/memory/knowledge');
}

export function createMemoryKnowledge(
  data: MemoryKnowledgeEntryCreate,
): Promise<MemoryKnowledgeEntryRead> {
  return apiFetch<MemoryKnowledgeEntryRead>('/memory/knowledge', {
    method: 'POST',
    body: JSON.stringify(data),
  });
}

export function fetchMemoryFeedback(): Promise<MemoryFeedbackEntryRead[]> {
  return apiFetch<MemoryFeedbackEntryRead[]>('/memory/feedback');
}
