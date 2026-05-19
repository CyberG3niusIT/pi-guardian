import { afterEach, describe, expect, it, vi } from 'vitest';

import { fetchHealth, fetchRouteHistory, sendRoute } from '../src/api/client';

afterEach(() => {
  vi.unstubAllGlobals();
});

describe('router api client', () => {
  it('uses the nginx /api proxy prefix for health requests', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ status: 'ok' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    vi.stubGlobal('fetch', fetchMock);

    await fetchHealth();

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/health',
      expect.objectContaining({
        credentials: 'include',
      }),
    );
  });

  it('builds history urls at the router root behind /api', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify([]), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    vi.stubGlobal('fetch', fetchMock);

    await fetchRouteHistory(8);

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/history?limit=8',
      expect.objectContaining({
        credentials: 'include',
      }),
    );
  });

  it('sends route requests with the active backend schema', async () => {
    const fetchMock = vi.fn().mockResolvedValue(
      new Response(JSON.stringify({ request_id: 'test', response: 'ok' }), {
        status: 200,
        headers: { 'Content-Type': 'application/json' },
      }),
    );

    vi.stubGlobal('fetch', fetchMock);

    await sendRoute('Diagnose Router', 'qwen2.5-coder:1.5b');

    expect(fetchMock).toHaveBeenCalledWith(
      '/api/route',
      expect.objectContaining({
        method: 'POST',
        credentials: 'include',
        body: JSON.stringify({
          prompt: 'Diagnose Router',
          preferred_model: 'qwen2.5-coder:1.5b',
          stream: false,
        }),
      }),
    );
  });
});
