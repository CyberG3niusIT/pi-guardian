// Tiny typed fetch layer for the two backends.
// Guardian watchdog -> /guardian (nginx/dev-proxy -> :8072)
// Router            -> /api      (nginx/dev-proxy -> :8071)

export type Severity = 'ok' | 'info' | 'warn' | 'critical' | 'unknown';

async function getJSON<T>(path: string): Promise<T> {
  const res = await fetch(path, { headers: { Accept: 'application/json' } });
  if (!res.ok) throw new Error(`${path} → HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

async function postJSON<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`${path} → HTTP ${res.status}`);
  return res.json() as Promise<T>;
}

export const guardian = {
  overview: () => getJSON<OverviewData>('/guardian/overview'),
  metrics: () => getJSON<MetricsData>('/guardian/metrics'),
  metricsHistory: (limit = 120) => getJSON<MetricsHistory>(`/guardian/metrics/history?limit=${limit}`),
  services: () => getJSON<ServicesData>('/guardian/services'),
  containers: () => getJSON<ContainersData>('/guardian/containers'),
  events: (limit = 20) => getJSON<{ events: EventItem[]; count: number }>(`/guardian/events?limit=${limit}`),
  incidents: (limit = 20) => getJSON<{ incidents: Incident[]; count: number }>(`/guardian/incidents?limit=${limit}`),
  policies: () => getJSON<{ policies: Policy[] }>('/guardian/policies'),
  actions: (limit = 20) => getJSON<ActionsData>(`/guardian/actions?limit=${limit}`),
  status: () => getJSON<Snapshot>('/guardian/status'),
  health: () => getJSON<HealthResponse>('/guardian/health'),
  systemInfo: () => getJSON<HostInfo>('/guardian/system/info'),
  config: () => getJSON<GuardianConfig>('/guardian/config'),
  executeAction: (action_id: string) => postJSON<ActionDecision>('/guardian/actions/execute', { action_id }),
};

export interface GuardianConfig {
  actions: {
    enabled: boolean; dry_run: boolean; cooldown_seconds: number;
    max_attempts_per_window: number; window_seconds: number; command_timeout_seconds: number;
    allow: ActionRule[];
  };
  watch: { systemd: string[]; docker: string[] };
  discovery: { enabled: boolean; alert: boolean };
}

export interface HostInfo {
  hostname: string; ip: string | null; model: string | null; os: string | null;
  kernel: string | null; arch: string | null; cpu_count: number | null;
  uptime_seconds: number | null; load_avg_1m: number | null; load_avg_5m: number | null;
  load_avg_15m: number | null; cpu_temperature_c: number | null;
}

// ---- types (only the fields the UI uses) ----
export interface OverviewData {
  guardian_core: { status: Severity; label: string };
  alert_manager: { operational: boolean; detail: string };
  event_store: { online: boolean; path: string };
  policy_layer: { active_policies: number; total_policies: number };
  docker_monitoring: { healthy: number; total: number };
  systemd_monitoring: { healthy: number; total: number };
}

export interface SystemState {
  hostname: string; running_as_root: boolean;
  cpu_usage_percent: number | null; memory_usage_percent: number | null;
  swap_usage_percent: number | null; disk_usage_percent: number | null;
  disk_used_bytes: number | null; disk_total_bytes: number | null;
  memory_used_bytes: number | null; memory_total_bytes: number | null;
  temperature_c: number | null; load_avg_1m: number | null; load_avg_5m: number | null; load_avg_15m: number | null;
  network_interface: string | null; network_rx_bytes_per_s: number | null; network_tx_bytes_per_s: number | null;
  process_uptime_seconds: number | null; cpu_count: number | null;
}
export interface MetricsData { status: Severity; summary: string; system: SystemState; }

export interface MetricPoint {
  t: string; cpu: number | null; memory: number | null; disk: number | null;
  temperature: number | null; load: number | null; net_rx_bps: number | null; net_tx_bps: number | null;
}
export interface MetricsHistory { points: MetricPoint[]; count: number; temperature_min: number | null; temperature_max: number | null; }

export interface Unit {
  name: string; whitelisted: boolean; active_state: string; sub_state: string;
  description: string; active_since: string | null; restart_count: number | null;
}
export interface ServicesData { status: Severity; summary: string; evaluation: { systemd: { units: Unit[] } }; }

export interface Container {
  name: string; whitelisted: boolean; state: string; health: string; image: string;
  restart_count: number | null; cpu_percent: number | null; memory_usage: string | null;
  memory_percent: number | null; uptime_text: string | null; started_at: string | null;
}
export interface ContainersData { status: Severity; summary: string; evaluation: { docker: { containers: Container[] } }; }

export interface EventItem { time: string; type: string; severity: Severity; title: string; detail: string; source: string; }
export interface Incident { title: string; severity: Severity; started: string; ended: string | null; status: string; duration_seconds: number | null; }
export interface Policy { id: string; name: string; description: string; active: boolean; }

export interface ActionRule { id: string; kind: string; target: string; description: string; }
export interface ActionRecord {
  created_at: string; action_id: string; kind: string; target: string; outcome: string;
  dry_run: boolean; trigger: string; source: string; command: string; error: string | null;
}
export interface ActionsData { enabled: boolean; dry_run: boolean; whitelist: ActionRule[]; history: ActionRecord[]; }
export interface ActionDecision { action_id: string; outcome: string; dry_run: boolean; error: string | null; }

export interface Snapshot {
  checked_at: string; guardian_status: Severity; router_status: Severity; system_status: Severity;
  systemd_status: Severity | null; docker_status: Severity | null;
}
export interface HealthResponse {
  status: Severity; checked_at: string;
  system: SystemState;
}
