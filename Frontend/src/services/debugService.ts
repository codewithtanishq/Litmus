import type { 
  Session, 
  CreateSessionInput, 
  DebugEvent, 
  FinalResult 
} from '../types/litmus';
import { MockAdapter } from './mock/mockAdapter';
import { getRecentSessions as getStoredRecentSessions, saveCurrentSession, addRecentSession, getCurrentSession as getStoredCurrentSession } from './sessionStore';

export interface BackendHealth {
  status: string;
  database?: {
    status: string;
    session_count?: number;
  };
  services?: {
    ollama?: { available: boolean };
    sandbox?: { docker_available: boolean; host_execution_allowed: boolean };
  };
}

/**
 * Litmus Debug Service Layer
 * Connects React UI to FastAPI backend over REST & Server-Sent Events (SSE),
 * with resilient offline fallback to MockAdapter.
 */
export const debugService = {
  /**
   * Check Backend operational status
   */
  async checkHealth(): Promise<BackendHealth | null> {
    try {
      const res = await fetch('/api/health', { method: 'GET' });
      if (res.ok) {
        return await res.json();
      }
      return null;
    } catch {
      return null;
    }
  },

  /**
   * Create a new debugging session
   */
  async createSession(input: CreateSessionInput): Promise<Session> {
    try {
      const res = await fetch('/api/sessions', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(input),
      });

      if (res.ok) {
        const session: Session = await res.json();
        saveCurrentSession(session);
        addRecentSession(session);
        return session;
      }
    } catch (err) {
      console.warn('[DebugService] Backend unreachable, falling back to local adapter:', err);
    }

    return MockAdapter.createSession(input);
  },

  /**
   * Subscribe to live debate events (Prosecutor, Defender, Judge, Sandbox)
   * Uses real-time Server-Sent Events (SSE) with fallback to MockAdapter.
   */
  subscribeToEvents(sessionId: string, handler: (event: DebugEvent) => void): () => void {
    let eventSource: EventSource | null = null;
    let fallbackCleanup: (() => void) | null = null;
    let receivedAnyRealEvent = false;

    try {
      eventSource = new EventSource(`/api/sessions/${encodeURIComponent(sessionId)}/events`);

      eventSource.onmessage = (e) => {
        try {
          const parsed = JSON.parse(e.data);
          if (parsed && parsed.type && parsed.type !== 'connected') {
            receivedAnyRealEvent = true;
            handler(parsed as DebugEvent);
          }
        } catch (err) {
          console.error('[DebugService] Failed to parse SSE event:', err);
        }
      };

      eventSource.onerror = () => {
        // If SSE fails and no events have arrived yet, fall back to mock stream
        if (!receivedAnyRealEvent && !fallbackCleanup) {
          console.warn('[DebugService] SSE failed, switching to local mock event stream');
          fallbackCleanup = MockAdapter.subscribeToEvents(sessionId, handler);
        }
        if (eventSource) {
          eventSource.close();
          eventSource = null;
        }
      };
    } catch (err) {
      console.warn('[DebugService] Failed to initialize SSE, falling back to local adapter:', err);
      fallbackCleanup = MockAdapter.subscribeToEvents(sessionId, handler);
    }

    return () => {
      if (eventSource) {
        eventSource.close();
      }
      if (fallbackCleanup) {
        fallbackCleanup();
      }
    };
  },

  /**
   * Get the final outcome / result report for a session
   */
  async getResult(sessionId: string): Promise<FinalResult | null> {
    try {
      const res = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}/result`);
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn('[DebugService] Failed to fetch result from backend:', err);
    }

    return MockAdapter.getResult(sessionId);
  },

  /**
   * Get session metadata
   */
  async getSession(sessionId: string): Promise<Session | null> {
    try {
      const res = await fetch(`/api/sessions/${encodeURIComponent(sessionId)}`);
      if (res.ok) {
        return await res.json();
      }
    } catch (err) {
      console.warn('[DebugService] Failed to fetch session from backend:', err);
    }

    return MockAdapter.getSession(sessionId);
  },

  /**
   * Get recent sessions from SQLite DB + local storage
   */
  async getRecentSessions(): Promise<Session[]> {
    try {
      const res = await fetch('/api/sessions');
      if (res.ok) {
        const backendSessions: Session[] = await res.json();
        const localSessions = getStoredRecentSessions();
        // Merge without duplicates
        const map = new Map<string, Session>();
        backendSessions.forEach(s => map.set(s.id, s));
        localSessions.forEach(s => {
          if (!map.has(s.id)) map.set(s.id, s);
        });
        return Array.from(map.values()).sort(
          (a, b) => new Date(b.createdAt).getTime() - new Date(a.createdAt).getTime()
        );
      }
    } catch (err) {
      console.warn('[DebugService] Failed to fetch sessions from backend:', err);
    }

    return getStoredRecentSessions();
  },

  /**
   * Fast-forward live event playback for a session
   */
  fastForward(sessionId: string): void {
    try {
      fetch(`/api/sessions/${encodeURIComponent(sessionId)}/fast-forward`, { method: 'POST' }).catch(() => {});
    } catch {
      // ignore
    }
    MockAdapter.fastForward(sessionId);
  },

  /**
   * Get current active session
   */
  getCurrentSession(): Session | null {
    return getStoredCurrentSession();
  },
};
