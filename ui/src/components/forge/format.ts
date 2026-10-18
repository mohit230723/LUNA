/** Shared formatting helpers for the Forge mission-control components. */

export function parseTs(ts: string): number | null {
  if (!ts) return null;
  const n = Date.parse(ts);
  return Number.isNaN(n) ? null : n;
}

/** "just now", "5m ago", "2h ago", "3d ago". */
export function ago(ts: string, now: number): string {
  const t = parseTs(ts);
  if (t === null) return 'never';
  const s = Math.max(0, Math.floor((now - t) / 1000));
  if (s < 60) return 'just now';
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

/** Remaining time until ``ts`` as mm:ss (minutes may exceed 59), or null when unset/expired. */
export function countdown(ts: string, now: number): string | null {
  const t = parseTs(ts);
  if (t === null) return null;
  const s = Math.floor((t - now) / 1000);
  if (s <= 0) return null;
  const mm = String(Math.floor(s / 60)).padStart(2, '0');
  const ss = String(s % 60).padStart(2, '0');
  return `${mm}:${ss}`;
}

export const asString = (v: unknown): string => (typeof v === 'string' ? v : '');
export const asNumber = (v: unknown): number | null => (typeof v === 'number' && Number.isFinite(v) ? v : null);
export const asArray = (v: unknown): unknown[] => (Array.isArray(v) ? v : []);
