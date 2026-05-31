import React from 'react';
import type { Severity } from './api';

const SEV_COLOR: Record<string, string> = {
  ok: 'var(--green)', info: 'var(--blue)', warn: 'var(--amber)',
  critical: 'var(--red)', unknown: 'var(--text-muted)',
};

export function sevColor(s: string | null | undefined): string {
  return SEV_COLOR[s || 'unknown'] || 'var(--text-muted)';
}

export function Badge({ sev, children }: { sev: Severity | string; children?: React.ReactNode }) {
  const cls = ['ok', 'info', 'warn', 'critical'].includes(sev as string) ? sev : 'muted';
  return <span className={`pg-badge ${cls}`}><span className="led" />{children ?? sev}</span>;
}

export function Dot({ sev }: { sev: string }) {
  const cls = ['ok', 'info', 'warn', 'critical'].includes(sev) ? sev : 'muted';
  return <span className={`pg-dot ${cls}`} />;
}

/** Circular progress ring with a centered label. */
export function Ring({ value, size = 52, stroke = 5, color, label }:
  { value: number | null; size?: number; stroke?: number; color?: string; label?: string }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = value == null ? 0 : Math.max(0, Math.min(100, value));
  const col = color || (pct >= 90 ? 'var(--green)' : pct >= 60 ? 'var(--amber)' : 'var(--accent)');
  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--ring-track)" strokeWidth={stroke} />
      <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={col} strokeWidth={stroke}
        strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - pct / 100)}
        transform={`rotate(-90 ${size / 2} ${size / 2})`} style={{ transition: 'stroke-dashoffset .6s ease' }} />
      <text x="50%" y="50%" dominantBaseline="central" textAnchor="middle"
        fill="var(--text)" fontSize={size * 0.27} fontWeight={700}>
        {label ?? (value == null ? '—' : `${Math.round(pct)}%`)}
      </text>
    </svg>
  );
}

/** Donut with a centered big value + caption. */
export function Donut({ value, size = 92, stroke = 11, color, center, caption }:
  { value: number | null; size?: number; stroke?: number; color?: string; center?: string; caption?: string }) {
  const r = (size - stroke) / 2;
  const c = 2 * Math.PI * r;
  const pct = value == null ? 0 : Math.max(0, Math.min(100, value));
  const col = color || (pct >= 90 ? 'var(--red)' : pct >= 75 ? 'var(--amber)' : 'var(--green)');
  return (
    <div style={{ position: 'relative', width: size, height: size, margin: '0 auto' }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`}>
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke="var(--ring-track)" strokeWidth={stroke} />
        <circle cx={size / 2} cy={size / 2} r={r} fill="none" stroke={col} strokeWidth={stroke}
          strokeLinecap="round" strokeDasharray={c} strokeDashoffset={c * (1 - pct / 100)}
          transform={`rotate(-90 ${size / 2} ${size / 2})`} style={{ transition: 'stroke-dashoffset .6s ease' }} />
      </svg>
      <div style={{ position: 'absolute', inset: 0, display: 'grid', placeItems: 'center', textAlign: 'center', lineHeight: 1.1 }}>
        <div>
          <div style={{ fontSize: size * 0.22, fontWeight: 700 }}>{center ?? (value == null ? '—' : `${Math.round(pct)}%`)}</div>
          {caption && <div style={{ fontSize: 10, color: 'var(--text-muted)' }}>{caption}</div>}
        </div>
      </div>
    </div>
  );
}

/** Lightweight SVG sparkline. */
export function Sparkline({ values, width = 130, height = 38, color = 'var(--accent)', fill = true }:
  { values: (number | null)[]; width?: number; height?: number; color?: string; fill?: boolean }) {
  const gid = React.useId(); // must run before any early return (Rules of Hooks)
  const nums = values.filter((v): v is number => v != null);
  if (nums.length < 2) return <div style={{ height, color: 'var(--text-muted)', fontSize: 11, display: 'grid', placeItems: 'center' }}>—</div>;
  const min = Math.min(...nums), max = Math.max(...nums);
  const span = max - min || 1;
  const pts = nums.map((v, i) => {
    const x = (i / (nums.length - 1)) * (width - 2) + 1;
    const y = height - 3 - ((v - min) / span) * (height - 8);
    return [x, y] as const;
  });
  const line = pts.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)},${y.toFixed(1)}`).join(' ');
  const area = `${line} L${pts[pts.length - 1][0].toFixed(1)},${height} L${pts[0][0].toFixed(1)},${height} Z`;
  return (
    <svg width="100%" height={height} viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none">
      {fill && (
        <>
          <defs><linearGradient id={gid} x1="0" y1="0" x2="0" y2="1">
            <stop offset="0%" stopColor={color} stopOpacity="0.28" />
            <stop offset="100%" stopColor={color} stopOpacity="0" />
          </linearGradient></defs>
          <path d={area} fill={`url(#${gid})`} />
        </>
      )}
      <path d={line} fill="none" stroke={color} strokeWidth={1.6} strokeLinejoin="round" strokeLinecap="round" />
    </svg>
  );
}

export function Panel({ title, count, action, onAction, children, style }:
  { title: React.ReactNode; count?: string; action?: string; onAction?: () => void; children: React.ReactNode; style?: React.CSSProperties }) {
  return (
    <section className="pg-panel" style={style}>
      <div className="pg-panel-head">
        <div className="pg-panel-title">{title}{count && <span className="count-pill">{count}</span>}</div>
        {action && <span className="pg-panel-action" onClick={onAction}>{action}</span>}
      </div>
      <div className="pg-panel-body">{children}</div>
    </section>
  );
}

export function StatusTile({ icon, iconColor, label, value, valueColor, sub, ring }:
  { icon: React.ReactNode; iconColor?: string; label: string; value: React.ReactNode; valueColor?: string; sub?: React.ReactNode; ring?: React.ReactNode }) {
  return (
    <div className="pg-tile">
      <div className="pg-tile-ico" style={{ color: iconColor }}>{icon}</div>
      <div className="pg-tile-body">
        <div className="pg-tile-label">{label}</div>
        <div className="pg-tile-value" style={{ color: valueColor }}>{value}</div>
        {sub && <div className="pg-tile-sub">{sub}</div>}
      </div>
      {ring && <div className="pg-tile-ring">{ring}</div>}
    </div>
  );
}

export function Spinner() { return <div className="pg-center"><div className="pg-spin" /></div>; }
