import { useEffect, useState } from 'react';
import { Sidebar } from './components/Sidebar';
import { Dashboard } from './pages/Dashboard';
import { Diagnostics } from './pages/Diagnostics';
import { Models } from './pages/Models';
import { Clients } from './pages/Clients';
import { Settings } from './pages/Settings';
import { Logs } from './pages/Logs';
import { Agents } from './pages/Agents';
import { History } from './pages/History';
import { Memory } from './pages/Memory';
import { bootstrapSession } from './auth/bootstrap';
import { useHealthCheck } from './hooks/useHealthCheck';
import type { Page } from './types';

type AuthState = 'bootstrapping' | 'ready' | 'forbidden' | 'error';

function BootScreen() {
  return (
    <div className="boot-screen">
      <div className="sidebar__logo" style={{ fontSize: '2rem', marginBottom: '1rem' }}>π</div>
      <p className="text--muted">Verbinde mit Router…</p>
    </div>
  );
}

function ErrorScreen({ message }: { message: string }) {
  return (
    <div className="boot-screen">
      <div className="sidebar__logo" style={{ fontSize: '2rem', marginBottom: '1rem' }}>π</div>
      <div className="alert alert--error" style={{ maxWidth: '420px' }}>
        <strong>Verbindungsfehler</strong>
        <p style={{ marginTop: '0.5rem' }}>{message}</p>
      </div>
      <button
        className="btn"
        style={{ marginTop: '1.5rem' }}
        onClick={() => window.location.reload()}
      >
        Erneut versuchen
      </button>
    </div>
  );
}

export default function App() {
  const [authState, setAuthState] = useState<AuthState>('bootstrapping');
  const [page, setPage] = useState<Page>('dashboard');
  const health = useHealthCheck();

  useEffect(() => {
    bootstrapSession().then((result) => {
      if (result === 'ok') setAuthState('ready');
      else if (result === 'forbidden') setAuthState('forbidden');
      else setAuthState('error');
    });
  }, []);

  if (authState === 'bootstrapping') return <BootScreen />;

  if (authState === 'forbidden') {
    return (
      <ErrorScreen message="IP-Adresse nicht erlaubt. Zugang nur aus dem Heimnetz (192.168.50.0/24)." />
    );
  }

  if (authState === 'error') {
    return (
      <ErrorScreen message="Bootstrap fehlgeschlagen – ist der Router (Port 8071) erreichbar?" />
    );
  }

  function renderPage() {
    switch (page) {
      case 'dashboard':
        return (
          <Dashboard
            connectionState={health.state}
            lastCheck={health.lastCheck}
            healthError={health.error}
            onRefresh={health.refresh}
          />
        );
      case 'diagnostics':
        return <Diagnostics connectionState={health.state} onRefresh={health.refresh} />;
      case 'models':
        return <Models />;
      case 'clients':
        return <Clients />;
      case 'settings':
        return <Settings />;
      case 'logs':
        return <Logs />;
      case 'agents':
        return <Agents />;
      case 'history':
        return <History />;
      case 'memory':
        return <Memory />;
      default:
        return (
          <Dashboard
            connectionState={health.state}
            lastCheck={health.lastCheck}
            healthError={health.error}
            onRefresh={health.refresh}
          />
        );
    }
  }

  return (
    <div className="app">
      <Sidebar current={page} onNavigate={setPage} connectionState={health.state} />
      {renderPage()}
    </div>
  );
}
