import React from 'react';
import { guardian } from '../shared/api';
import type { Severity } from '../shared/api';
import { usePoll } from '../shared/hooks';
import { Badge, Donut, Panel, Ring, Sparkline, Spinner, StatusTile, sevColor } from '../shared/ui';
import { Icon } from '../shared/icons';
import { fmtBytes, fmtDuration, fmtMbps, fmtPct, fmtSystemdTime, fmtTime, dockerUptime, fmtDateTime } from '../shared/format';

function tileColor(s: Severity | string): string { return sevColor(s); }

// ---------------- Top status tiles ----------------
function TopTiles() {
  const { data } = usePoll(guardian.overview, 15000);
  if (!data) return <div className="pg-tilegrid">{Array.from({ length: 6 }).map((_, i) => <div className="pg-tile" key={i} style={{ height: 70 }} />)}</div>;
  const ok = (b: boolean) => (b ? 'var(--green)' : 'var(--amber)');
  return (
    <div className="pg-tilegrid">
      <StatusTile icon={Icon.shield()} iconColor={tileColor(data.guardian_core.status)} label="Guardian Core"
        value={<span style={{ color: tileColor(data.guardian_core.status) }}>{data.guardian_core.label}</span>}
        sub="Watchdog aktiv" />
      <StatusTile icon={Icon.bell()} iconColor={ok(data.alert_manager.operational)} label="Alert Manager"
        value={data.alert_manager.operational ? 'Operational' : 'Inaktiv'} sub={data.alert_manager.detail} />
      <StatusTile icon={Icon.logs()} iconColor={ok(data.event_store.online)} label="Event Store"
        value={data.event_store.online ? 'Online' : 'Offline'} sub={data.event_store.path} />
      <StatusTile icon={Icon.policy()} iconColor="var(--green)" label="Policy Layer"
        value="Enforced" sub={`${data.policy_layer.active_policies} Policies aktiv`} />
      <StatusTile icon={Icon.box()} iconColor="var(--blue)" label="Docker Monitoring"
        value={`${data.docker_monitoring.healthy}/${data.docker_monitoring.total}`} sub="Container healthy"
        ring={<Ring value={data.docker_monitoring.total ? (data.docker_monitoring.healthy / data.docker_monitoring.total) * 100 : 0} size={44} />} />
      <StatusTile icon={Icon.server()} iconColor="var(--accent)" label="systemd Monitoring"
        value={`${data.systemd_monitoring.healthy}/${data.systemd_monitoring.total}`} sub="Units healthy"
        ring={<Ring value={data.systemd_monitoring.total ? (data.systemd_monitoring.healthy / data.systemd_monitoring.total) * 100 : 0} size={44} />} />
    </div>
  );
}

// ---------------- System Health Overview ----------------
function HealthOverview() {
  const { data: m } = usePoll(guardian.metrics, 10000);
  const { data: hist } = usePoll(() => guardian.metricsHistory(60), 15000);
  const sys = m?.system;
  const points = hist?.points ?? [];
  const overall = m?.status ?? 'unknown';
  const overallCol = sevColor(overall);

  return (
    <Panel title={<>System Health Overview</>}>
      <div className="pg-row" style={{ justifyContent: 'space-between', marginBottom: 12 }}>
        <span className="pg-updated">Aktualisiert: {fmtTime(new Date().toISOString())}</span>
      </div>
      <div className="pg-health">
        <div className="pg-health-cell">
          <div className="pg-health-label">Overall Status</div>
          <div style={{ display: 'grid', placeItems: 'center', margin: '4px 0' }}>
            <Ring value={overall === 'ok' ? 100 : overall === 'warn' ? 55 : 20} size={56}
              color={overallCol} label={overall === 'ok' ? '✓' : overall === 'critical' ? '!' : '~'} />
          </div>
          <div className="pg-health-foot" style={{ color: overallCol, fontWeight: 600 }}>
            {overall === 'ok' ? 'Healthy' : overall === 'warn' ? 'Needs attention' : overall === 'critical' ? 'Critical' : '—'}
          </div>
        </div>

        <div className="pg-health-cell">
          <div className="pg-health-label">Load Average</div>
          <div className="pg-health-big">{sys?.load_avg_1m != null ? sys.load_avg_1m.toFixed(2) : '—'}</div>
          <div className="pg-health-unit">1m</div>
          <div style={{ marginTop: 6 }}><Sparkline values={points.map((p) => p.load)} color="var(--accent)" height={30} /></div>
        </div>

        <div className="pg-health-cell">
          <div className="pg-health-label">CPU Temperature</div>
          <div className="pg-health-big">{sys?.temperature_c != null ? `${sys.temperature_c.toFixed(1)}` : '—'}<span className="pg-health-unit"> °C</span></div>
          <div style={{ marginTop: 6 }}><Sparkline values={points.map((p) => p.temperature)} color="var(--orange)" height={30} /></div>
          <div className="pg-health-foot">Min {hist?.temperature_min?.toFixed(1) ?? '—'}° · Max {hist?.temperature_max?.toFixed(1) ?? '—'}°</div>
        </div>

        <div className="pg-health-cell">
          <div className="pg-health-label">Storage ( / )</div>
          <Donut value={sys?.disk_usage_percent ?? null} size={78} caption="genutzt" />
          <div className="pg-health-foot">{fmtBytes(sys?.disk_used_bytes)} / {fmtBytes(sys?.disk_total_bytes)}</div>
        </div>

        <div className="pg-health-cell">
          <div className="pg-health-label">Memory</div>
          <Donut value={sys?.memory_usage_percent ?? null} size={78} caption="genutzt" />
          <div className="pg-health-foot">{fmtBytes(sys?.memory_used_bytes)} / {fmtBytes(sys?.memory_total_bytes)}</div>
        </div>

        <div className="pg-health-cell">
          <div className="pg-health-label">Network ({sys?.network_interface ?? 'net'})</div>
          <div style={{ fontSize: 14, fontWeight: 700, margin: '4px 0', lineHeight: 1.4 }}>
            <div style={{ color: 'var(--green)' }}>↓ {fmtMbps(sys?.network_rx_bytes_per_s)}</div>
            <div style={{ color: 'var(--blue)' }}>↑ {fmtMbps(sys?.network_tx_bytes_per_s)}</div>
          </div>
          <Sparkline values={points.map((p) => p.net_rx_bps)} color="var(--green)" height={26} />
        </div>
      </div>
    </Panel>
  );
}

// ---------------- Recent Alerts ----------------
function RecentAlerts() {
  const { data } = usePoll(() => guardian.events(25), 15000);
  const alerts = (data?.events ?? []).filter((e) => e.severity !== 'ok').slice(0, 5);
  return (
    <Panel title="Recent Alerts" count={alerts.length ? String(alerts.length) : undefined} action="View all events">
      {alerts.length === 0 && <div className="pg-empty">Keine aktuellen Alerts.</div>}
      <div className="pg-list">
        {alerts.map((a, i) => (
          <div className="pg-listrow" key={i}>
            <div className={`li-ico ic-${a.severity}`}>{a.type === 'action' ? Icon.bolt({ size: 13 }) : Icon.bell({ size: 13 })}</div>
            <div className="li-main">
              <div className="li-title">{a.title}</div>
              <div className="li-sub">{a.source}{a.detail ? ` · ${a.detail}` : ''}</div>
            </div>
            <div className="li-time">{fmtTime(a.time)}</div>
          </div>
        ))}
      </div>
    </Panel>
  );
}

// ---------------- systemd Units ----------------
function unitSev(s: string): Severity { return s === 'active' ? 'ok' : s === 'failed' ? 'critical' : 'warn'; }
function MonitoredUnits() {
  const { data } = usePoll(guardian.services, 15000);
  const units = (data?.evaluation?.systemd?.units ?? []).filter((u) => u.whitelisted);
  return (
    <Panel title="Monitored systemd Units" count={`${units.filter((u) => u.active_state === 'active').length} Healthy`} action="View all">
      <table className="pg-table">
        <thead><tr><th>Unit</th><th>Status</th><th>Active Since</th><th>Restarts</th></tr></thead>
        <tbody>
          {units.map((u) => (
            <tr key={u.name}>
              <td><div className="li-title" style={{ fontSize: 12.5 }}>{u.name}</div><div className="pg-muted" style={{ fontSize: 11 }}>{u.description}</div></td>
              <td><Badge sev={unitSev(u.active_state)}>{u.active_state}</Badge></td>
              <td className="mono">{fmtSystemdTime(u.active_since)}</td>
              <td className="mono">{u.restart_count ?? '—'}</td>
            </tr>
          ))}
          {units.length === 0 && <tr><td colSpan={4} className="pg-empty">—</td></tr>}
        </tbody>
      </table>
    </Panel>
  );
}

// ---------------- Docker Containers ----------------
function contSev(c: { state: string; health: string }): Severity {
  if (c.state !== 'running') return 'critical';
  if (c.health === 'unhealthy') return 'critical';
  if (c.health === 'starting') return 'warn';
  return 'ok';
}
function Containers() {
  const { data } = usePoll(guardian.containers, 15000);
  const cs = (data?.evaluation?.docker?.containers ?? []).filter((c) => c.whitelisted);
  const hasMem = cs.some((c) => c.memory_usage); // cgroup memory accounting available?
  const colCount = hasMem ? 5 : 4;
  return (
    <Panel title="Docker Containers" count={`${cs.filter((c) => c.state === 'running').length} Healthy`} action="View all">
      <table className="pg-table">
        <thead><tr><th>Container</th><th>Status</th><th>Uptime</th><th>CPU</th>{hasMem && <th>RAM</th>}</tr></thead>
        <tbody>
          {cs.map((c) => (
            <tr key={c.name}>
              <td><div className="li-title" style={{ fontSize: 12 }}>{c.name}</div><div className="pg-muted" style={{ fontSize: 10.5, maxWidth: 130, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{c.image}</div></td>
              <td><Badge sev={contSev(c)}>{c.state}{c.health !== 'none' && c.health !== 'unknown' ? ` · ${c.health}` : ''}</Badge></td>
              <td className="mono">{dockerUptime(c)}</td>
              <td className="mono">{c.cpu_percent != null ? `${c.cpu_percent.toFixed(1)}%` : '—'}</td>
              {hasMem && <td className="mono">{c.memory_usage ?? '—'}</td>}
            </tr>
          ))}
          {cs.length === 0 && <tr><td colSpan={colCount} className="pg-empty">—</td></tr>}
        </tbody>
      </table>
    </Panel>
  );
}

// ---------------- Event Timeline ----------------
function EventTimeline() {
  const { data } = usePoll(() => guardian.events(8), 15000);
  const events = data?.events ?? [];
  return (
    <Panel title="Event Timeline" action="View all events">
      <div className="pg-timeline">
        {events.map((e, i) => (
          <div className="pg-tl-row" key={i}>
            <span className="pg-tl-dot" style={{ background: sevColor(e.severity) }} />
            <div className="pg-tl-main">
              <div className="pg-tl-time">{fmtTime(e.time)}</div>
              <div className="pg-tl-title">{e.title}</div>
              {e.detail && <div className="pg-tl-sub">{e.detail}</div>}
            </div>
          </div>
        ))}
        {events.length === 0 && <div className="pg-empty">Keine Ereignisse.</div>}
      </div>
    </Panel>
  );
}

// ---------------- Recent Incidents ----------------
function Incidents() {
  const { data } = usePoll(() => guardian.incidents(8), 20000);
  const incidents = data?.incidents ?? [];
  return (
    <Panel title="Recent Incidents" action="View all">
      <table className="pg-table">
        <thead><tr><th>Incident</th><th>Severity</th><th>Status</th><th>Started</th><th>Duration</th></tr></thead>
        <tbody>
          {incidents.map((inc, i) => (
            <tr key={i}>
              <td>{inc.title}</td>
              <td><Badge sev={inc.severity}>{inc.severity}</Badge></td>
              <td><Badge sev={inc.status === 'active' ? 'critical' : 'ok'}>{inc.status === 'active' ? 'Active' : 'Resolved'}</Badge></td>
              <td className="mono">{fmtDateTime(inc.started)}</td>
              <td className="mono">{fmtDuration(inc.duration_seconds)}</td>
            </tr>
          ))}
          {incidents.length === 0 && <tr><td colSpan={5} className="pg-empty">Keine Incidents – alles ruhig.</td></tr>}
        </tbody>
      </table>
    </Panel>
  );
}

// ---------------- Policy Summary ----------------
function PolicySummary() {
  const { data } = usePoll(guardian.policies, 30000);
  const policies = data?.policies ?? [];
  return (
    <Panel title="Policy Summary" action="Manage policies">
      <div className="pg-policygrid">
        {policies.map((p) => (
          <div className="pg-policy" key={p.id}>
            <div className="p-ico">{Icon.policy({ size: 16 })}</div>
            <div className="p-main"><div className="p-title">{p.name}</div><div className="p-sub">{p.description}</div></div>
            <Badge sev={p.active ? 'ok' : 'muted'}>{p.active ? 'Active' : 'Off'}</Badge>
          </div>
        ))}
      </div>
    </Panel>
  );
}

export default function GuardianOverview({ onJump }: { onJump?: (s: string) => void }) {
  const { loading } = usePoll(guardian.overview, 60000);
  void onJump;
  if (loading) return <Spinner />;
  return (
    <>
      <TopTiles />
      <div className="pg-grid pg-row-health" style={{ marginBottom: 16 }}>
        <HealthOverview />
        <RecentAlerts />
      </div>
      <div className="pg-grid pg-row-mid" style={{ marginBottom: 16 }}>
        <MonitoredUnits />
        <Containers />
        <EventTimeline />
      </div>
      <div className="pg-grid pg-row-bottom" style={{ marginBottom: 8 }}>
        <Incidents />
        <PolicySummary />
      </div>
    </>
  );
}
