// === Bestehende API-Typen (SOFORT NUTZBAR) ===

export interface HealthResponse {
  status: string;
}

export interface RouteRequest {
  prompt: string;
  preferred_model?: string;
  stream?: boolean;
}

export interface RouteResponse {
  request_id: string;
  model: string;
  response: string;
  done: boolean;
  done_reason: string;
  duration_ms: number;
  fairness_review_attempted?: boolean;
  fairness_review_used?: boolean;
  fairness_risk?: string;
  fairness_review_override?: boolean;
  fairness_reasons?: string[];
  fairness_notes?: string[];
}

export interface RouteErrorResponse {
  request_id: string;
  model?: string;
  error: {
    code: string;
    message: string;
    retryable: boolean;
  };
}

export interface RouterSettings {
  router_host: string;
  router_port: number;
  ollama_host: string;
  ollama_port: number;
  timeout: number;
  default_model: string;
  logging_level: string;
  stream_default: boolean;
  require_api_key: boolean;
  escalation_threshold: string;
}

export interface SettingsUpdateResponse {
  settings: RouterSettings;
  restart_requested: boolean;
  restart_performed: boolean;
  restart_message?: string;
  validation_warnings: string[];
}

export interface RouteHistoryEntry {
  id: number;
  request_id: string;
  prompt_preview: string;
  model?: string;
  success: boolean;
  error_code?: string;
  client_name?: string;
  duration_ms?: number;
  fairness_review_attempted?: boolean;
  fairness_review_used?: boolean;
  fairness_risk?: string;
  fairness_review_override?: boolean;
  escalation_threshold?: string;
  fairness_reasons?: string[];
  fairness_notes?: string[];
  created_at: string;
}

export interface IntegrationGuide {
  router_base_url: string;
  auth_header_name: string;
  auth_header_example: string;
  allowed_routes: string[];
  security_controls: string[];
  example_create_client: Record<string, unknown>;
  example_curl: string;
}

export interface OllamaModel {
  name: string;
  size: string;
  modified_at: string;
  digest: string;
}

export interface ClientEntry {
  id: number;
  name: string;
  description: string;
  active: boolean;
  allowed_ip: string;
  allowed_routes: string[];
  api_key?: string;
  created_at?: string;
}

export interface LogEntry {
  timestamp: string;
  level: 'info' | 'warn' | 'error';
  source: string;
  message: string;
}

export interface ServiceStatus {
  service: string;
  active: boolean;
  uptime: string;
  pid: number;
  memory_usage: string;
  cpu_percent: number;
}

export interface AgentBehaviorSettings {
  analysis_mode: 'summary' | 'balanced' | 'deep';
  response_depth: 'concise' | 'balanced' | 'detailed';
  prioritization_style: 'risks_first' | 'ops_first' | 'systems_first';
  uncertainty_behavior: 'state_uncertainty' | 'ask_clarification' | 'be_conservative';
  risk_sensitivity: 'low' | 'medium' | 'high';
}

export interface AgentPersonalitySettings {
  style: 'analytical' | 'neutral' | 'supportive' | 'strict';
  tone: 'direct' | 'formal' | 'neutral';
  directness: 'low' | 'medium' | 'high';
  verbosity: 'short' | 'balanced' | 'detailed';
  technical_strictness: 'low' | 'medium' | 'high';
}

export interface AgentPolicySettings {
  allowed_tools: string[];
  allowed_skills: string[];
  allowed_actions: string[];
  read_only: boolean;
  can_propose_actions: boolean;
  can_use_logs: boolean;
  can_use_services: boolean;
  can_use_docker: boolean;
  max_steps: number;
  max_tool_calls?: number | null;
}

export interface AgentSettings {
  active: boolean;
  preferred_model?: string | null;
  max_steps: number;
  timeout_seconds?: number | null;
  read_only: boolean;
  policy: AgentPolicySettings;
  behavior: AgentBehaviorSettings;
  personality: AgentPersonalitySettings;
  custom_instruction?: string | null;
}

export interface AgentDefinition {
  name: string;
  description: string;
  agent_type: 'system' | 'custom' | 'actor';
  allowed_tools: string[];
  settings: AgentSettings;
  system_prompt: string;
}

export interface AgentCreateRequest {
  name: string;
  description: string;
  allowed_tools: string[];
  settings: AgentSettings;
  read_only: boolean;
}

export interface AgentUpdateRequest {
  description?: string;
  allowed_tools?: string[];
  settings?: AgentSettings;
  read_only?: boolean;
}

export interface AgentSettingsUpdate {
  active?: boolean;
  preferred_model?: string | null;
  max_steps?: number;
  timeout_seconds?: number | null;
  policy?: AgentPolicySettings | null;
  behavior?: AgentBehaviorSettings;
  personality?: AgentPersonalitySettings;
  custom_instruction?: string | null;
  read_only?: boolean;
}

export interface ToolCall {
  tool_name: string;
  arguments: Record<string, unknown>;
  reason: string;
}

export interface ToolResult {
  tool_name: string;
  success: boolean;
  output: unknown;
  error?: string | null;
}

export interface AgentStep {
  step_number: number;
  action:
    | 'model_response'
    | 'tool_call'
    | 'tool_result'
    | 'skill_call'
    | 'skill_result'
    | 'action_proposal'
    | 'final_answer'
    | 'parse_error'
    | 'abort';
  tool_call_or_response: ToolCall | ToolResult | string | Record<string, unknown>;
  observation?: string | null;
}

export interface AgentRunRequest {
  agent_name: string;
  input: string;
  preferred_model?: string;
  max_steps?: number;
}

export interface AgentRunResponse {
  run_id?: string | null;
  agent_name: string;
  success: boolean;
  final_answer: string;
  steps: AgentStep[];
  tool_calls: ToolCall[];
  proposed_action?: Record<string, unknown> | null;
  errors: string[];
  used_model?: string | null;
}

export interface SkillDefinition {
  name: string;
  description: string;
  allowed_tools: string[];
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  read_only: boolean;
  version: string;
  enabled: boolean;
}

export interface ActionDefinition {
  name: string;
  description: string;
  allowed_targets: string[];
  input_schema: Record<string, unknown>;
  output_schema: Record<string, unknown>;
  read_only: boolean;
  requires_approval: boolean;
  version: string;
  enabled: boolean;
}

export interface ActionProposal {
  action_name: string;
  arguments: Record<string, unknown>;
  reason: string;
  target?: string | null;
  requires_approval: boolean;
}

export interface ActionResult {
  action_name: string;
  success: boolean;
  output: unknown;
  error?: string | null;
}

export interface ActionProposalResponse {
  proposal_id?: string | null;
  agent_name: string;
  proposal: ActionProposal;
  action: ActionDefinition;
}

export interface ActionProposalRequest {
  agent_name: string;
  action_name: string;
  arguments: Record<string, unknown>;
  reason: string;
  target?: string | null;
}

export interface ActionExecuteRequest {
  agent_name: string;
  action_name: string;
  arguments: Record<string, unknown>;
  reason: string;
  target?: string | null;
  approved: boolean;
  proposal_id?: string | null;
}

// === UI-interne Typen ===

export interface MemoryRunSummary {
  run_id: string;
  agent_name: string;
  input: string;
  used_model?: string | null;
  success: boolean;
  final_answer: string;
  started_at: string;
  finished_at?: string | null;
}

export interface MemoryRunDetail extends MemoryRunSummary {
  steps: MemoryStepRead[];
  tool_calls: MemoryToolCallRead[];
  tool_results: MemoryToolResultRead[];
  skill_runs: MemorySkillRunRead[];
  action_proposals: MemoryActionProposalRead[];
  action_executions: MemoryActionExecutionRead[];
  approvals: MemoryApprovalRead[];
}

export interface MemoryStepRead {
  step_number: number;
  action_type: string;
  observation?: string | null;
  raw_payload: unknown;
  created_at: string;
}

export interface MemoryToolCallRead {
  step_number: number;
  tool_name: string;
  arguments: Record<string, unknown>;
  reason: string;
  created_at: string;
}

export interface MemoryToolResultRead {
  step_number: number;
  tool_name: string;
  success: boolean;
  output: unknown;
  error?: string | null;
  created_at: string;
}

export interface MemorySkillRunRead {
  step_number: number;
  skill_name: string;
  arguments: Record<string, unknown>;
  reason: string;
  success: boolean;
  output: unknown;
  error?: string | null;
  created_at: string;
}

export interface MemoryActionProposalRead {
  proposal_id: string;
  run_id?: string | null;
  agent_name: string;
  action_name: string;
  arguments: Record<string, unknown>;
  reason: string;
  target?: string | null;
  requires_approval: boolean;
  created_at: string;
}

export interface MemoryActionExecutionRead {
  proposal_id: string;
  run_id?: string | null;
  action_name: string;
  approved: boolean;
  success: boolean;
  output: unknown;
  error?: string | null;
  created_at: string;
}

export interface MemoryApprovalRead {
  proposal_id: string;
  approved_by?: string | null;
  approved_at: string;
  decision: string;
  comment?: string | null;
}

export interface MemoryIncidentFindingRead {
  source_type: string;
  source_ref: string;
  finding_type: string;
  content: string;
  confidence: number;
}

export interface MemoryIncidentRead {
  id: number;
  title: string;
  summary: string;
  severity: string;
  status: string;
  related_run_id?: string | null;
  created_at: string;
  updated_at: string;
  findings: MemoryIncidentFindingRead[];
}

export interface MemoryKnowledgeEntryRead {
  id: number;
  title: string;
  pattern: string;
  probable_cause: string;
  recommended_checks: string;
  recommended_actions: string;
  confidence: number;
  confirmed: boolean;
  source: string;
  created_at: string;
  updated_at: string;
}

export interface MemoryFeedbackEntryRead {
  id: number;
  related_run_id?: string | null;
  related_incident_id?: number | null;
  verdict: string;
  comment: string;
  created_by: string;
  created_at: string;
}

export interface MemoryIncidentCreate {
  title: string;
  summary?: string;
  severity?: string;
  status?: string;
  related_run_id?: string | null;
}

export interface MemoryIncidentFindingCreate {
  source_type: string;
  source_ref: string;
  finding_type?: string;
  content?: string;
  confidence?: number;
}

export interface MemoryKnowledgeCreate {
  title: string;
  pattern?: string;
  probable_cause?: string;
  recommended_checks?: string;
  recommended_actions?: string;
  confidence?: number;
  confirmed?: boolean;
  source?: string;
}

export interface MemoryFeedbackCreate {
  related_run_id?: string | null;
  related_incident_id?: number | null;
  verdict: string;
  comment?: string;
  created_by?: string;
}

export type Page = 'dashboard' | 'models' | 'agents' | 'skills' | 'clients' | 'settings' | 'diagnostics' | 'logs' | 'history' | 'memory';

export interface ApiError {
  message: string;
  status?: number;
  timestamp: string;
  code?: string;
  request_id?: string;
  retryable?: boolean;
}

export type ConnectionState = 'connected' | 'disconnected' | 'checking' | 'error';
