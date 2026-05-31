import { useEffect, useRef, useState, useCallback } from 'react';

export interface PollState<T> {
  data: T | null;
  error: string | null;
  loading: boolean;
  refresh: () => void;
}

/** Polls an async fetcher on an interval; keeps last data on transient errors. */
export function usePoll<T>(fetcher: () => Promise<T>, intervalMs = 15000): PollState<T> {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const fetcherRef = useRef(fetcher);
  fetcherRef.current = fetcher;

  const run = useCallback(async () => {
    try {
      const result = await fetcherRef.current();
      setData(result);
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : String(e));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    let active = true;
    void run();
    const id = setInterval(() => { if (active) void run(); }, intervalMs);
    return () => { active = false; clearInterval(id); };
  }, [run, intervalMs]);

  return { data, error, loading, refresh: run };
}
