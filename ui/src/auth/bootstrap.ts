export type BootstrapResult = 'ok' | 'forbidden' | 'error';

export async function bootstrapSession(): Promise<BootstrapResult> {
  try {
    const res = await fetch('/api/auth/bootstrap', {
      method: 'POST',
      credentials: 'include',
    });
    if (res.status === 204) return 'ok';
    if (res.status === 403) return 'forbidden';
    return 'error';
  } catch {
    return 'error';
  }
}
