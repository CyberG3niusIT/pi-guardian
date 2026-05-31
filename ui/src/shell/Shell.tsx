import React, { useEffect, useState } from 'react';
import { Icon } from '../shared/icons';
import { usePoll } from '../shared/hooks';
import { guardian } from '../shared/api';
import { fmtDuration } from '../shared/format';
import GuardianOverview from '../ui_guardian/Overview';
import GuardianActions from '../ui_guardian/Actions';

type TabId = 'guardian-overview' | 'guardian-actions' | 'router';

const TABS: { id: TabId; label: string }[] = [
  { id: 'guardian-overview', label: 'Guardian Overview' },
  { id: 'guardian-actions', label: 'Guardian Actions' },
  { id: 'router', label: 'Router' },
];

const GUARDIAN_NAV = [
  { id: 'overview', label: 'Overview', icon: Icon.home },
  { id: 'alerts', label: 'Alerts', icon: Icon.bell, badge: true },
  { id: 'services', label: 'Services', icon: Icon.server },
  { id: 'containers', label: 'Containers', icon: Icon.box },
  { id: 'policies', label: 'Policies', icon: Icon.policy },
  { id: 'events', label: 'Events', icon: Icon.events },
  { id: 'logs', label: 'Logs', icon: Icon.logs },
  { id: 'settings', label: 'Settings', icon: Icon.cog },
];

const ACTIONS_NAV = [
  { id: 'recovery', label: 'Recovery', icon: Icon.bolt },
  { id: 'history', label: 'Historie', icon: Icon.events },
  { id: 'safety', label: 'Sicherheit', icon: Icon.policy },
  { id: 'settings', label: 'Settings', icon: Icon.cog },
];

const ROUTER_NAV = [
  { id: 'overview', label: 'Overview', icon: Icon.home },
  { id: 'routes', label: 'Routes', icon: Icon.route },
  { id: 'providers', label: 'Providers', icon: Icon.providers },
  { id: 'adapters', label: 'Adapters', icon: Icon.adapters },
  { id: 'skills', label: 'Skills', icon: Icon.skills },
  { id: 'policies', label: 'Policies', icon: Icon.policy },
  { id: 'queue', label: 'Queue', icon: Icon.queue },
  { id: 'audit', label: 'Audit Log', icon: Icon.audit },
  { id: 'settings', label: 'Settings', icon: Icon.cog },
];

function useTheme(): [string, () => void] {
  const [theme, setTheme] = useState<string>(() => localStorage.getItem('pg-theme') || 'dark');
  useEffect(() => {
    document.documentElement.setAttribute('data-theme', theme);
    localStorage.setItem('pg-theme', theme);
  }, [theme]);
  return [theme, () => setTheme((t) => (t === 'dark' ? 'light' : 'dark'))];
}

function DeviceCard() {
  const { data } = usePoll(guardian.systemInfo, 30000);
  const rows: [string, string][] = data ? [
    ['Model', data.model?.replace(' Model B', '').replace(/Rev.*/, '').trim() || '—'],
    ['OS', data.os || '—'],
    ['Kernel', data.kernel || '—'],
    ['Uptime', fmtDuration(data.uptime_seconds)],
    ['Load Avg', [data.load_avg_1m, data.load_avg_5m, data.load_avg_15m].map((x) => (x == null ? '—' : x.toFixed(2))).join(' ')],
    ['CPU Temp', data.cpu_temperature_c != null ? `${data.cpu_temperature_c.toFixed(1)} °C` : '—'],
    ['CPUs', data.cpu_count != null ? String(data.cpu_count) : '—'],
  ] : [];
  return (
    <div className="pg-device">
      <div className="pg-device-head"><span className="dot" />{data?.hostname || 'pi-guardian'}</div>
      <div className="pg-device-ip">{data?.ip || '—'}</div>
      {rows.map(([k, v]) => (
        <div className="pg-device-row" key={k}><span className="k">{k}</span><span className="v">{v}</span></div>
      ))}
    </div>
  );
}

function Sidebar({ tab, section, onSection }:
  { tab: TabId; section: string; onSection: (s: string) => void }) {
  const nav = tab === 'router' ? ROUTER_NAV : tab === 'guardian-actions' ? ACTIONS_NAV : GUARDIAN_NAV;
  return (
    <aside className="pg-sidebar">
      {nav.map((item) => (
        <div key={item.id}
          className={`pg-nav-item ${section === item.id ? 'active' : ''}`}
          onClick={() => onSection(item.id)}>
          <span className="ico">{item.icon()}</span>
          {item.label}
        </div>
      ))}
      <DeviceCard />
      <div style={{ textAlign: 'center', fontSize: 11, color: 'var(--text-muted)', paddingTop: 10 }}>v0.3.0</div>
    </aside>
  );
}

function Placeholder({ title }: { title: string }) {
  return (
    <div className="pg-placeholder">
      <div style={{ fontSize: 30, opacity: .4 }}>{Icon.bolt({ size: 30 })}</div>
      <div style={{ fontSize: 15, fontWeight: 600, color: 'var(--text-dim)' }}>{title}</div>
      <div>Dieser Bereich wird als Nächstes gebaut.</div>
    </div>
  );
}

export default function Shell() {
  const [tab, setTab] = useState<TabId>('guardian-overview');
  const [section, setSection] = useState('overview');
  const [theme, toggleTheme] = useTheme();

  // Alerts badge count (live).
  const { data: events } = usePoll(() => guardian.events(20), 20000);
  const alertCount = events?.events.filter((e) => e.type === 'alert' || e.severity === 'critical' || e.severity === 'warn').length ?? 0;

  function switchTab(t: TabId) {
    setTab(t);
    setSection(t === 'guardian-actions' ? 'recovery' : 'overview');
  }

  let content: React.ReactNode;
  if (tab === 'guardian-overview' && section === 'overview') content = <GuardianOverview onJump={setSection} />;
  else if (tab === 'guardian-overview') content = <Placeholder title={`Guardian · ${section}`} />;
  else if (tab === 'guardian-actions') content = <GuardianActions />;
  else content = <Placeholder title="Router" />;

  return (
    <div className="pg-app">
      <header className="pg-header">
        <div className="pg-brand">
          <div className="pg-brand-logo">{Icon.shield({ size: 22 })}</div>
          <div>
            <div className="pg-brand-title">PI Guardian</div>
            <div className="pg-brand-sub">Infrastructure Monitoring &amp; Control</div>
          </div>
        </div>
        <nav className="pg-tabs">
          {TABS.map((t) => (
            <button key={t.id} className={`pg-tab ${tab === t.id ? 'active' : ''}`} onClick={() => switchTab(t.id)}>
              {t.label}
            </button>
          ))}
        </nav>
        <div className="pg-header-spacer" />
        <div className="pg-header-actions">
          <button className="pg-iconbtn" title="Alerts">{Icon.bell()}</button>
          <button className="pg-iconbtn" title="Hilfe">{Icon.help()}</button>
          <button className="pg-iconbtn" title="Theme" onClick={toggleTheme}>{theme === 'dark' ? Icon.sun() : Icon.moon()}</button>
          <div className="pg-user">
            <div className="pg-user-meta">
              <div className="pg-user-name">admin</div>
              <div className="pg-user-role">Administrator</div>
            </div>
            <div className="pg-avatar">{Icon.shield({ size: 16 })}<span className="dot" /></div>
          </div>
        </div>
      </header>
      <div className="pg-body">
        <Sidebar tab={tab} section={section} onSection={setSection} />
        <main className="pg-main">{content}</main>
      </div>
    </div>
  );
}

export { type TabId };
