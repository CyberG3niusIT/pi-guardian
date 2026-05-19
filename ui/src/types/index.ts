// ── UI-intern ─────────────────────────────────────────────────────────────────

export type ConnectionState = 'connected' | 'disconnected' | 'checking' | 'error';

export type Page =
  | 'dashboard'
  | 'diagnostics'
  | 'models'
  | 'clients'
  | 'settings'
  | 'logs'
  | 'agents'
  | 'history'
  | 'memory';

// ── Router-Backend (response_models.py) ───────────────────────────────────────

export interface HealthResponse {
  status: string;
}

export interface ServiceStatus {
  service: string;
  active: boolean;
  uptime: string | null;
  pid: number | null;
  memory_usage: string | null;
  cpu_percent: number | null;
}

export interface RoutePolicyTrace {
  can_use_llm: boolean;
  can_use_tools: boolean;
  can_use_internet: boolean;
  decision_classification: 'llm_only' | 'tool_required' | 'internet_required' | 'blocked';
  tool_execution_allowed: boolean;
  internet_execution_allowed: boolean;
}

export interface RouteToolExecution {
  tool_name: string;
  arguments: Record<string, unknown>;
  reason: string;
  success: boolean;
  duration_ms: number;
  output: unknown;
  error: string | null;
}

export interface RouteResponse {
  request_id: string;
  model: string;
  response: string;
  done: boolean;
  done_reason: string | null;
  duration_ms: number;
  decision_classification: 'llm_only' | 'tool_required' | 'internet_required' | 'blocked';
  decision_reasons: string[];
  decision_tool_hints: string[];
  decision_internet_hints: string[];
  fairness_review_attempted: boolean;
  fairness_review_used: boolean;
  fairness_risk: string;
  fairness_review_override: boolean;
  fairness_reasons: string[];
  fairness_notes: string[];
  execution_mode: 'llm' | 'tool' | 'internet_pending';
  policy_trace: RoutePolicyTrace | null;
  tool_executions: RouteToolExecution[];
  execution_error: string | null;
}

export interface RouterSettings {
  router_host: string;
  router_port: number;
  ollama_host: string;
  ollama_port: number;
  timeout: number;
  default_model: string;
  large_model: string;
  logging_level: string;
  stream_default: boolean;
  require_api_key: boolean;
  escalation_threshold: string;
}

export interface SettingsUpdateResponse {
  settings: RouterSettings;
  restart_requested: boolean;
  restart_performed: boolean;
  restart_message: string | null;
  validation_warnings: string[];
}

export interface OllamaModel {
  name: string;
  size: string;
  modified_at: string;
  digest: string;
}

export interface LogEntry {
  timestamp: string;
  level: 'info' | 'warn' | 'error';
  source: string;
  message: string;
}

export interface RouteHistoryEntry {
  id: number;
  request_id: string;
  prompt_preview: string;
  model: string | null;
  success: boolean;
  error_code: string | null;
  client_name: string | null;
  duration_ms: number | null;
  decision_classification: 'llm_only' | 'tool_required' | 'internet_required' | 'blocked';
  decision_reasons: string[];
  decision_tool_hints: string[];
  decision_internet_hints: string[];
  fairness_review_attempted: boolean;
  fairness_review_used: boolean;
  fairness_risk: string;
  fairness_review_override: boolean;
  escalation_threshold: string | null;
  fairness_reasons: string[];
  fairness_notes: string[];
  policy_trace: Record<string, unknown>;
  execution_mode: 'llm' | 'tool' | 'internet_pending';
  execution_status: 'not_executed' | 'succeeded' | 'failed';
  executed_tools: string[];
  tool_execution_records: Record<string, unknown>[];
  execution_error: string | null;
  created_at: string;
  [key: string]: unknown;
}

// ── Clients (models/client.py) ────────────────────────────────────────────────

export interface ClientRead {
  id: number;
  name: string;
  description: string;
  active: boolean;
  allowed_ip: string;
  allowed_routes: string[];
  api_key?: string;
  can_use_llm: boolean;
  can_use_tools: boolean;
  can_use_internet: boolean;
  created_at: string;
}

export interface ClientCreate {
  name: string;
  description: string;
  active?: boolean;
  allowed_ip: string;
  allowed_routes: string[];
  api_key?: string;
  can_use_llm?: boolean;
  can_use_tools?: boolean;
  can_use_internet?: boolean;
}

export interface ClientUpdate {
  name?: string;
  description?: string;
  active?: boolean;
  allowed_ip?: string;
  allowed_routes?: string[];
  can_use_llm?: boolean;
  can_use_tools?: boolean;
  can_use_internet?: boolean;
}

// ── Modell-Registry ───────────────────────────────────────────────────────────

export interface ModelRegistryEntry {
  id: number;
  name: string;
  description: string;
  role: string;
  enabled: boolean;
  created_at: string;
  updated_at: string;
}

export interface ModelRegistryEntryCreate {
  name: string;
  description?: string;
  role?: string;
  enabled?: boolean;
}

export interface ModelPullJob {
  id: number;
  model_name: string;
  status: 'queued' | 'running' | 'succeeded' | 'failed';
  progress_percent: number | null;
  progress_message: string;
  requested_by: string | null;
  created_at: string;
  updated_at: string;
}

// ── Agents (routes_agents.py) ─────────────────────────────────────────────────

export interface AgentSettings {
  active: boolean;
  preferred_model: string | null;
  max_steps: number;
  timeout_seconds: number;
  read_only: boolean;
  policy: {
    read_only?: boolean;
    allowed_tools?: string[];
    max_steps?: number;
    [key: string]: unknown;
  };
  behavior?: {
    analysis_mode?: string;
    response_depth?: string;
    risk_sensitivity?: string;
    [key: string]: unknown;
  };
  personality?: {
    style?: string;
    tone?: string;
    verbosity?: string;
    [key: string]: unknown;
  };
  custom_instruction?: string | null;
}

export interface AgentActivity {
  last_run_at: string | null;
  last_run_success: boolean | null;
  total_runs: number;
  failed_runs: number;
  last_status?: 'success' | 'failed' | string | null;
  last_model?: string | null;
  last_activity?: string | null;
  last_run_id?: string | null;
  last_result_preview?: string | null;
}

export interface AgentDefinition {
  name: string;
  description: string;
  agent_type: string;
  allowed_tools: string[];
  settings: AgentSettings;
  activity?: AgentActivity;
  enabled?: boolean;
  read_only?: boolean;
  max_steps?: number;
  system_prompt?: string | null;
}

export interface AgentRunResponse {
  run_id?: string | null;
  agent_name: string;
  success: boolean;
  final_answer: string;
  steps: Array<{
    step_number: number;
    action: string;
    tool_call_or_response: unknown;
    observation?: string | null;
  }>;
  tool_calls: Array<{
    tool_name: string;
    arguments: Record<string, unknown>;
    reason: string;
  }>;
  proposed_action?: Record<string, unknown> | null;
  errors: string[];
  used_model?: string | null;
}

// ── Skills (routes_skills.py) ─────────────────────────────────────────────────

export interface SkillDefinition {
  name: string;
  description: string;
  skill_type?: string;
  allowed_tools: string[];
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  prompt_template?: string | null;
  preferred_model?: string | null;
  source_url?: string | null;
  read_only?: boolean;
  version?: string;
  enabled?: boolean;
}

// ── Actions (routes_actions.py) ───────────────────────────────────────────────

export interface ActionDefinition {
  name: string;
  description: string;
  allowed_targets: string[];
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  requires_approval?: boolean;
  enabled?: boolean;
}

// ── Memory (routes_memory.py) ─────────────────────────────────────────────────

export interface MemoryRunSummary {
  run_id: string;
  agent_name: string;
  input: string;
  used_model: string;
  success: boolean;
  final_answer: string | null;
  started_at: string;
  finished_at: string;
}

export interface MemoryRunDetail extends MemoryRunSummary {
  steps: Record<string, unknown>[];
  tool_calls: Record<string, unknown>[];
  error: string | null;
}

export interface IncidentFinding {
  id: number;
  incident_id: number;
  content: string;
  created_at: string;
}

export interface MemoryIncidentRead {
  id: number;
  title: string;
  severity: string;
  description: string;
  summary?: string | null;
  status: string;
  created_at: string;
  updated_at: string;
  findings: IncidentFinding[];
}

export interface MemoryIncidentCreate {
  title: string;
  severity?: string;
  description?: string;
  status?: string;
}

export interface MemoryKnowledgeEntryRead {
  id: number;
  category: string;
  title: string;
  content: string;
  probable_cause?: string | null;
  confidence?: string | number | null;
  confirmed?: boolean | null;
  created_at: string;
}

export interface MemoryKnowledgeEntryCreate {
  category: string;
  title: string;
  content: string;
}

export interface MemoryFeedbackEntryRead {
  id: number;
  run_id: string;
  related_run_id?: string | null;
  rating: number;
  verdict?: string | null;
  comment: string | null;
  created_by?: string | null;
  created_at: string;
}

// ── Agent Memory (routes_agent_memory.py) ─────────────────────────────────────

export type AgentMemoryType = 'finding' | 'failure' | 'feedback' | 'instruction';

export interface AgentMemoryEntry {
  id: number;
  agent_name: string;
  memory_type: AgentMemoryType;
  content: string;
  active: boolean;
  priority: number;
  source_run_id: string | null;
  times_confirmed: number;
  created_at: string;
  updated_at: string;
}

export interface AgentMemoryEntryCreate {
  memory_type: AgentMemoryType;
  content: string;
  priority?: number;
}
