import React from 'react';
import type { Page, ConnectionState } from '../types';
import { StatusBadge } from './StatusBadge';
import { routerAddress, CONFIG } from '../config';

interface Props {
  current: Page;
  onNavigate: (page: Page) => void;
  connectionState: ConnectionState;
}

/* ── SVG Icons (fully inline, zero external deps) ─────────── */

function IconDashboard() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <rect x="1" y="1" width="6" height="6" rx="1.5" fill="currentColor" fillOpacity="0.9"/>
      <rect x="9" y="1" width="6" height="6" rx="1.5" fill="currentColor" fillOpacity="0.45"/>
      <rect x="1" y="9" width="6" height="6" rx="1.5" fill="currentColor" fillOpacity="0.45"/>
      <rect x="9" y="9" width="6" height="6" rx="1.5" fill="currentColor" fillOpacity="0.65"/>
    </svg>
  );
}

function IconAgents() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="5" r="2.8" stroke="currentColor" strokeWidth="1.5"/>
      <circle cx="2.5" cy="12.5" r="1.8" stroke="currentColor" strokeWidth="1.3"/>
      <circle cx="13.5" cy="12.5" r="1.8" stroke="currentColor" strokeWidth="1.3"/>
      <path d="M8 7.8 L4.3 10.7M8 7.8 L11.7 10.7" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
    </svg>
  );
}

function IconMemory() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <rect x="1.5" y="3.5" width="13" height="9" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
      <line x1="5" y1="3.5" x2="5" y2="12.5" stroke="currentColor" strokeWidth="1.2"/>
      <line x1="11" y1="3.5" x2="11" y2="12.5" stroke="currentColor" strokeWidth="1.2"/>
      <circle cx="3" cy="8" r="0.9" fill="currentColor"/>
      <circle cx="8" cy="8" r="0.9" fill="currentColor"/>
      <circle cx="13" cy="8" r="0.9" fill="currentColor"/>
    </svg>
  );
}

function IconModels() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <polygon points="8,1.5 14.5,5 14.5,11 8,14.5 1.5,11 1.5,5"
               stroke="currentColor" strokeWidth="1.4" fill="none"/>
      <circle cx="8" cy="8" r="2.2" fill="currentColor" fillOpacity="0.6"/>
    </svg>
  );
}

function IconClients() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <rect x="2" y="5" width="12" height="8.5" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
      <path d="M5 5V3.8C5 2.8 5.8 2 6.8 2H9.2C10.2 2 11 2.8 11 3.8V5"
            stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
      <line x1="2" y1="9.5" x2="14" y2="9.5" stroke="currentColor" strokeWidth="1.2"/>
    </svg>
  );
}

function IconLogs() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <rect x="2" y="1.5" width="12" height="13" rx="1.5" stroke="currentColor" strokeWidth="1.4"/>
      <line x1="5" y1="5.5" x2="11" y2="5.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
      <line x1="5" y1="8" x2="11" y2="8" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
      <line x1="5" y1="10.5" x2="8.5" y2="10.5" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round"/>
    </svg>
  );
}

function IconSettings() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="2.2" stroke="currentColor" strokeWidth="1.4"/>
      <path d="M8 1.5V3M8 13V14.5M1.5 8H3M13 8H14.5M3.4 3.4L4.5 4.5M11.5 11.5L12.6 12.6M12.6 3.4L11.5 4.5M4.5 11.5L3.4 12.6"
            stroke="currentColor" strokeWidth="1.4" strokeLinecap="round"/>
    </svg>
  );
}

function IconDiagnostics() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <polyline points="1.5,10 4,5.5 6.5,9.5 9.5,3.5 12,8 14.5,6"
                stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

function IconHistory() {
  return (
    <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
      <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.4"/>
      <polyline points="8,4.5 8,8.5 10.5,10.5"
                stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  );
}

const NAV_ICONS: Record<string, () => React.ReactElement> = {
  dashboard:   IconDashboard,
  agents:      IconAgents,
  memory:      IconMemory,
  models:      IconModels,
  clients:     IconClients,
  logs:        IconLogs,
  settings:    IconSettings,
  diagnostics: IconDiagnostics,
  history:     IconHistory,
};

/* ── Navigation groups ─────────────────────────────────────── */

interface NavItem { page: Page; label: string; icon: string; }


const NAV_GROUPS: { label: string; items: NavItem[] }[] = [
  {
    label: 'Platform',
    items: [
      { page: 'dashboard',   label: 'Dashboard',    icon: 'dashboard'   },
      { page: 'agents',      label: 'Agenten',       icon: 'agents'      },
      { page: 'memory',      label: 'Memory',        icon: 'memory'      },
    ],
  },
  {
    label: 'Intelligence',
    items: [
      { page: 'models',      label: 'Modelle',       icon: 'models'      },
    ],
  },
  {
    label: 'Operations',
    items: [
      { page: 'clients',     label: 'Clients',       icon: 'clients'     },
      { page: 'logs',        label: 'Logs',          icon: 'logs'        },
      { page: 'history',     label: 'Verlauf',       icon: 'history'     },
      { page: 'diagnostics', label: 'Diagnose',      icon: 'diagnostics' },
      { page: 'settings',    label: 'Einstellungen', icon: 'settings'    },
    ],
  },
];

export function Sidebar({ current, onNavigate, connectionState }: Props) {
  return (
    <aside className="sidebar">
      {/* Brand */}
      <div className="sidebar__brand">
        <div className="sidebar__logo">π</div>
        <div className="sidebar__brand-text">
          <span className="sidebar__name">PI Guardian</span>
          <span className="sidebar__sub">AI Platform</span>
        </div>
      </div>

      {/* Connection status */}
      <div className="sidebar__status">
        <StatusBadge state={connectionState} />
      </div>

      {/* Grouped navigation */}
      <nav className="sidebar__nav">
        {NAV_GROUPS.map((group) => (
          <div key={group.label}>
            <div className="sidebar__group-label">{group.label}</div>
            {group.items.map((item) => {
              const Icon = NAV_ICONS[item.icon];
              return (
                <button
                  key={item.page}
                  className={`sidebar__link${current === item.page ? ' sidebar__link--active' : ''}`}
                  onClick={() => onNavigate(item.page)}
                  title={item.label}
                >
                  <span className="sidebar__icon">
                    {Icon && <Icon />}
                  </span>
                  <span className="sidebar__label">{item.label}</span>
                </button>
              );
            })}
          </div>
        ))}
      </nav>

      {/* Footer */}
      <div className="sidebar__footer">
        <span className="sidebar__meta">{routerAddress()}</span>
        <span className="sidebar__meta">v{CONFIG.version}</span>
      </div>
    </aside>
  );
}
