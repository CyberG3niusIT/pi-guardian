import React, { useState } from 'react';
import { guardian } from '../shared/api';
import type { ActionDecision } from '../shared/api';
import { usePoll } from '../shared/hooks';
import { Badge, Panel, Spinner, StatusTile } from '../shared/ui';
import { Icon } from '../shared/icons';
import { fmtDateTime, fmtDuration } from '../shared/format';

function outcomeSev(o: string): 'ok' | 'warn' | 'critical' | 'info' {
  if (o === 'executed') return 'ok';
  if (o === 'failed') return 'critical';
  if (o === 'dry_run') return 'info';
  return 'warn'; // suppressed_*, disabled, not_whitelisted, no_candidate
}

function kindLabel(k: string): string {
  return k === 'systemd_restart' ? 'systemd · restart' : k === 'docker_restart' ? 'docker · restart' : k;
}

export default function GuardianActions() {
  const { data, loading, refresh } = usePoll(guardian.actions, 10000);
  const { data: cfg } = usePoll(guardian.config, 30000);
  const [busy, setBusy] = useState<string | null>(null);
  const [result, setResult] = useState<ActionDecision | null>(null);

  if (loading && !data) return <Spinner />;

  const enabled = data?.enabled ?? false;
  const dryRun = data?.dry_run ?? true;
  const whitelist = data?.whitelist ?? [];
  const history = data?.history ?? [];
  const ac = cfg?.actions;

  async function run(id: string) {
    if (!confirm(`Aktion "${id}" anstoßen?\nGuardian entscheidet final (Whitelist, Cooldown, dry-run).`)) return;
    setBusy(id);
    setResult(null);
    try {
      const decision = await guardian.executeAction(id);
      setResult(decision);
      refresh();
    } catch (e) {
      setResult({ action_id: id, outcome: 'error', dry_run: dryRun, error: e instanceof Error ? e.message : String(e) });
    } finally {
      setBusy(null);
    }
  }

  return (
    <>
      <div className="pg-tilegrid" style={{ gridTemplateColumns: 'repeat(4, minmax(0, 1fr))' }}>
        <StatusTile icon={Icon.bolt()} iconColor={enabled ? 'var(--green)' : 'var(--text-muted)'}
          label="Recovery Engine" value={enabled ? 'Enabled' : 'Disabled'} sub={enabled ? 'aktiv' : 'deaktiviert'} />
        <StatusTile icon={Icon.shield()} iconColor={dryRun ? 'var(--amber)' : 'var(--red)'}
          label="Ausführungsmodus" value={dryRun ? 'Dry-Run' : 'Scharf'}
          sub={dryRun ? 'nur simulieren/loggen' : 'echte Restarts'} />
        <StatusTile icon={Icon.policy()} iconColor="var(--blue)" label="Whitelist"
          value={String(whitelist.length)} sub="erlaubte Aktionen" />
        <StatusTile icon={Icon.events()} iconColor="var(--accent)" label="Cooldown / Limit"
          value={ac ? `${ac.cooldown_seconds}s` : '—'}
          sub={ac ? `max ${ac.max_attempts_per_window}/${ac.window_seconds}s` : ''} />
      </div>

      {result && (
        <div className="pg-panel" style={{ marginBottom: 16, borderColor: 'var(--border)' }}>
          <div className="pg-panel-body" style={{ paddingTop: 14 }}>
            <div className="pg-row" style={{ gap: 10 }}>
              <Badge sev={outcomeSev(result.outcome)}>{result.outcome}</Badge>
              <span style={{ fontWeight: 600 }}>{result.action_id}</span>
              <span className="pg-muted">{result.dry_run ? '· dry-run' : '· scharf'}</span>
              {result.error && <span style={{ color: 'var(--red)' }}>· {result.error}</span>}
            </div>
          </div>
        </div>
      )}

      <div className="pg-grid pg-row-bottom" style={{ marginBottom: 16 }}>
        <Panel title="Recovery-Aktionen (Whitelist)" count={dryRun ? 'dry-run' : 'scharf'} action="Refresh" onAction={refresh}>
          <table className="pg-table">
            <thead><tr><th>Aktion</th><th>Typ</th><th>Ziel</th><th></th></tr></thead>
            <tbody>
              {whitelist.map((r) => (
                <tr key={r.id}>
                  <td><div className="li-title" style={{ fontSize: 12 }}>{r.id}</div><div className="pg-muted" style={{ fontSize: 10.5 }}>{r.description}</div></td>
                  <td className="pg-muted">{kindLabel(r.kind)}</td>
                  <td className="mono">{r.target}</td>
                  <td style={{ textAlign: 'right' }}>
                    <button className="pg-btn" disabled={!enabled || busy === r.id} onClick={() => run(r.id)}>
                      {busy === r.id ? '…' : 'Ausführen'}
                    </button>
                  </td>
                </tr>
              ))}
              {whitelist.length === 0 && <tr><td colSpan={4} className="pg-empty">Keine erlaubten Aktionen.</td></tr>}
            </tbody>
          </table>
        </Panel>

        <Panel title="Sicherheitsgrenzen">
          <div className="pg-list">
            <SafetyRow label="Ausführung" value={dryRun ? 'Dry-Run (Simulation)' : 'Scharf (echte Restarts)'} sev={dryRun ? 'warn' : 'critical'} />
            <SafetyRow label="Cooldown pro Aktion" value={ac ? fmtDuration(ac.cooldown_seconds) : '—'} sev="ok" />
            <SafetyRow label="Rate-Limit" value={ac ? `${ac.max_attempts_per_window} / ${fmtDuration(ac.window_seconds)}` : '—'} sev="ok" />
            <SafetyRow label="Kommando-Timeout" value={ac ? `${ac.command_timeout_seconds}s` : '—'} sev="ok" />
            <SafetyRow label="Freie Shell" value="nicht erlaubt (nur Whitelist)" sev="ok" />
          </div>
        </Panel>
      </div>

      <Panel title="Aktions-Historie" action="Refresh" onAction={refresh}>
        <table className="pg-table">
          <thead><tr><th>Zeit</th><th>Aktion</th><th>Ziel</th><th>Auslöser</th><th>Quelle</th><th>Ergebnis</th></tr></thead>
          <tbody>
            {history.map((h, i) => (
              <tr key={i}>
                <td className="mono">{fmtDateTime(h.created_at)}</td>
                <td>{h.action_id}</td>
                <td className="mono">{h.target}</td>
                <td className="pg-muted">{h.trigger}</td>
                <td className="pg-muted">{h.source}</td>
                <td><Badge sev={outcomeSev(h.outcome)}>{h.outcome}</Badge>{h.dry_run ? <span className="pg-muted" style={{ fontSize: 11 }}> · dry-run</span> : null}</td>
              </tr>
            ))}
            {history.length === 0 && <tr><td colSpan={6} className="pg-empty">Noch keine Aktionen protokolliert.</td></tr>}
          </tbody>
        </table>
      </Panel>
    </>
  );
}

function SafetyRow({ label, value, sev }: { label: string; value: string; sev: 'ok' | 'warn' | 'critical' }) {
  return (
    <div className="pg-listrow">
      <div className={`li-ico ic-${sev}`}>{Icon.shield({ size: 13 })}</div>
      <div className="li-main"><div className="li-title">{label}</div></div>
      <div className="li-time" style={{ color: 'var(--text-dim)' }}>{value}</div>
    </div>
  );
}
