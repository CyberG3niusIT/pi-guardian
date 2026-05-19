import { useCallback, useEffect, useRef, useState } from 'react';
import { fetchHealth, ApiRequestError } from '../api/client';
import type { ConnectionState } from '../types';
import { CONFIG } from '../config';

interface HealthCheckResult {
  state: ConnectionState;
  lastCheck: string | null;
  error: string | null;
  refresh: () => void;
}

export function useHealthCheck(intervalMs = CONFIG.healthInterval): HealthCheckResult {
  const [state, setState] = useState<ConnectionState>('checking');
  const [lastCheck, setLastCheck] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);

  const check = useCallback(async () => {
    setState('checking');
    try {
      await fetchHealth();
      setState('connected');
      setError(null);
      setLastCheck(new Date().toLocaleTimeString('de-DE'));
    } catch (err) {
      setState('error');
      setError(err instanceof ApiRequestError ? err.message : 'Verbindungsfehler');
    }
  }, []);

  useEffect(() => {
    void check();
    timerRef.current = setInterval(() => { void check(); }, intervalMs);
    return () => {
      if (timerRef.current !== null) clearInterval(timerRef.current);
    };
  }, [check, intervalMs]);

  return { state, lastCheck, error, refresh: check };
}
