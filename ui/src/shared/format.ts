export function fmtPct(v: number | null | undefined, digits = 0): string {
  return v == null ? '—' : `${v.toFixed(digits)}%`;
}

export function fmtBytes(v: number | null | undefined): string {
  if (v == null) return '—';
  const u = ['B', 'KB', 'MB', 'GB', 'TB'];
  let n = v, i = 0;
  while (n >= 1024 && i < u.length - 1) { n /= 1024; i++; }
  return `${n.toFixed(n >= 100 || i === 0 ? 0 : 1)} ${u[i]}`;
}

export function fmtMbps(bytesPerSec: number | null | undefined): string {
  if (bytesPerSec == null) return '—';
  const mbps = (bytesPerSec * 8) / 1e6;
  if (mbps >= 1) return `${mbps.toFixed(1)} Mbps`;
  return `${(mbps * 1000).toFixed(0)} Kbps`;
}

export function fmtDuration(seconds: number | null | undefined): string {
  if (seconds == null) return '—';
  const s = Math.max(0, Math.floor(seconds));
  const d = Math.floor(s / 86400);
  const h = Math.floor((s % 86400) / 3600);
  const m = Math.floor((s % 3600) / 60);
  if (d > 0) return `${d}d ${h}h`;
  if (h > 0) return `${h}h ${m}m`;
  if (m > 0) return `${m}m ${s % 60}s`;
  return `${s}s`;
}

export function fmtTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso.slice(11, 19);
  return d.toLocaleTimeString('de-DE', { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso;
  return d.toLocaleString('de-DE', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}

// systemd ActiveEnterTimestamp like "Sat 2026-05-30 20:11:22 CEST" -> "30. Mai, 20:11"
export function fmtSystemdTime(raw: string | null | undefined): string {
  if (!raw) return '—';
  const m = raw.match(/(\d{4})-(\d{2})-(\d{2})\s+(\d{2}):(\d{2})/);
  if (!m) return raw;
  const d = new Date(`${m[1]}-${m[2]}-${m[3]}T${m[4]}:${m[5]}:00`);
  if (isNaN(d.getTime())) return raw;
  return d.toLocaleString('de-DE', { day: '2-digit', month: 'short', hour: '2-digit', minute: '2-digit' });
}

export function relTime(iso: string | null | undefined): string {
  if (!iso) return '—';
  const then = new Date(iso).getTime();
  if (isNaN(then)) return '—';
  const diff = (Date.now() - then) / 1000;
  if (diff < 60) return 'gerade eben';
  if (diff < 3600) return `vor ${Math.floor(diff / 60)} Min`;
  if (diff < 86400) return `vor ${Math.floor(diff / 3600)} Std`;
  return `vor ${Math.floor(diff / 86400)} Tg`;
}

export function dockerUptime(c: { started_at: string | null; uptime_text: string | null }): string {
  if (c.started_at) {
    const d = new Date(c.started_at);
    if (!isNaN(d.getTime())) return fmtDuration((Date.now() - d.getTime()) / 1000);
  }
  return c.uptime_text || '—';
}
