import type { Session } from '../types/litmus';

const CURRENT_SESSION_KEY = 'litmus.session';
const RECENT_SESSIONS_KEY = 'litmus.recent_sessions';
const MAX_RECENT_SESSIONS = 10;

/**
 * Validates whether an object is a plausible Session
 */
function isValidSession(obj: unknown): obj is Session {
  if (!obj || typeof obj !== 'object') return false;
  const s = obj as Record<string, unknown>;
  return (
    typeof s.id === 'string' &&
    typeof s.title === 'string' &&
    typeof s.mode === 'string' &&
    typeof s.question === 'string' &&
    typeof s.createdAt === 'string' &&
    typeof s.status === 'string'
  );
}

/**
 * Retrieve current session from sessionStorage.
 * Handles missing or corrupt data safely.
 */
export function getCurrentSession(): Session | null {
  try {
    const raw = sessionStorage.getItem(CURRENT_SESSION_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw);
    if (isValidSession(parsed)) {
      return parsed;
    }
    console.warn('[SessionStore] Invalid current session format in sessionStorage, resetting.');
    sessionStorage.removeItem(CURRENT_SESSION_KEY);
    return null;
  } catch (err) {
    console.error('[SessionStore] Failed to read current session from sessionStorage:', err);
    try {
      sessionStorage.removeItem(CURRENT_SESSION_KEY);
    } catch {
      // ignore
    }
    return null;
  }
}

/**
 * Save current session into sessionStorage.
 */
export function saveCurrentSession(session: Session): void {
  try {
    sessionStorage.setItem(CURRENT_SESSION_KEY, JSON.stringify(session));
  } catch (err) {
    console.error('[SessionStore] Failed to save current session to sessionStorage:', err);
  }
}

/**
 * Clear current session from sessionStorage.
 */
export function clearCurrentSession(): void {
  try {
    sessionStorage.removeItem(CURRENT_SESSION_KEY);
  } catch (err) {
    console.error('[SessionStore] Failed to clear current session:', err);
  }
}

/**
 * Retrieve recent sessions from localStorage.
 * Handles missing or corrupt data safely.
 */
export function getRecentSessions(): Session[] {
  try {
    const raw = localStorage.getItem(RECENT_SESSIONS_KEY);
    if (!raw) return [];
    const parsed = JSON.parse(raw);
    if (Array.isArray(parsed)) {
      const validSessions = parsed.filter(isValidSession);
      return validSessions;
    }
    console.warn('[SessionStore] Recent sessions was not an array, resetting.');
    localStorage.removeItem(RECENT_SESSIONS_KEY);
    return [];
  } catch (err) {
    console.error('[SessionStore] Failed to read recent sessions from localStorage:', err);
    try {
      localStorage.removeItem(RECENT_SESSIONS_KEY);
    } catch {
      // ignore
    }
    return [];
  }
}

/**
 * Add or update a session in recent sessions list in localStorage.
 */
export function addRecentSession(session: Session): void {
  try {
    const recents = getRecentSessions();
    const filtered = recents.filter(s => s.id !== session.id);
    const updated = [session, ...filtered].slice(0, MAX_RECENT_SESSIONS);
    localStorage.setItem(RECENT_SESSIONS_KEY, JSON.stringify(updated));
    // notify listeners
    window.dispatchEvent(new CustomEvent('litmus:recent-sessions-changed'));
  } catch (err) {
    console.error('[SessionStore] Failed to save recent session to localStorage:', err);
  }
}

/**
 * Clear all recent sessions.
 */
export function clearRecentSessions(): void {
  try {
    localStorage.removeItem(RECENT_SESSIONS_KEY);
    window.dispatchEvent(new CustomEvent('litmus:recent-sessions-changed'));
  } catch (err) {
    console.error('[SessionStore] Failed to clear recent sessions:', err);
  }
}
