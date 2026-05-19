import React from 'react';
import { act } from 'react';
import { createRoot, type Root } from 'react-dom/client';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';

import { Dashboard } from '../src/pages/Dashboard';

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const mockedApi = vi.hoisted(() => ({
  fetchServiceStatus: vi.fn(),
  fetchSettings: vi.fn(),
}));

vi.mock('../src/api/client', async () => {
  const actual = await vi.importActual<typeof import('../src/api/client')>('../src/api/client');
  return {
    ...actual,
    fetchServiceStatus: mockedApi.fetchServiceStatus,
    fetchSettings: mockedApi.fetchSettings,
  };
});

describe('Dashboard', () => {
  let container: HTMLDivElement;
  let root: Root;

  beforeEach(() => {
    mockedApi.fetchServiceStatus.mockReset();
    mockedApi.fetchSettings.mockReset();
    container = document.createElement('div');
    document.body.appendChild(container);
    root = createRoot(container);
  });

  afterEach(() => {
    act(() => root.unmount());
    container.remove();
  });

  it('renders router status, settings and service status', async () => {
    mockedApi.fetchServiceStatus.mockResolvedValue({
      service: 'pi-guardian-router',
      active: true,
      uptime: '12min',
      pid: 1234,
      memory_usage: '96MB',
      cpu_percent: 4.2,
    });
    mockedApi.fetchSettings.mockResolvedValue({
      router_host: '127.0.0.1',
      router_port: 8071,
      ollama_host: '192.168.50.240',
      ollama_port: 11434,
      timeout: 30,
      default_model: 'qwen2.5-coder:1.5b',
      large_model: 'qwen2.5-coder:3b',
      logging_level: 'INFO',
      stream_default: false,
      require_api_key: true,
      escalation_threshold: 'medium',
    });

    await act(async () => {
      root.render(
        <Dashboard
          connectionState="connected"
          lastCheck="16:05:00"
          healthError={null}
          onRefresh={() => undefined}
        />,
      );
    });

    expect(container.textContent).toContain('Systemübersicht');
    expect(container.textContent).toContain('qwen2.5-coder:1.5b');
    expect(container.textContent).toContain('qwen2.5-coder:3b');
    expect(container.textContent).toContain('Aktiv');
    expect(container.textContent).toContain('12min');
  });

  it('renders the health error without crashing', async () => {
    mockedApi.fetchServiceStatus.mockRejectedValue(new Error('service unavailable'));
    mockedApi.fetchSettings.mockRejectedValue(new Error('settings unavailable'));

    await act(async () => {
      root.render(
        <Dashboard
          connectionState="error"
          lastCheck={null}
          healthError="Router nicht erreichbar"
          onRefresh={() => undefined}
        />,
      );
    });

    expect(container.textContent).toContain('Router nicht erreichbar');
    expect(container.textContent).toContain('Service Monitor');
  });
});
