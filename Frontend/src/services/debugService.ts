import type { 
  Session, 
  CreateSessionInput, 
  DebugEvent, 
  FinalResult 
} from '../types/litmus';
import { MockAdapter } from './mock/mockAdapter';
import { getRecentSessions, getCurrentSession } from './sessionStore';

/**
 * Litmus Debug Service Layer
 * Delegated to the deterministic MockAdapter (can be swapped with an API adapter in the future).
 */
export const debugService = {
  /**
   * Create a new debugging session
   */
  async createSession(input: CreateSessionInput): Promise<Session> {
    return MockAdapter.createSession(input);
  },

  /**
   * Subscribe to live debate events (Prosecutor, Defender, Judge, Sandbox)
   * Returns an unsubscribe function.
   */
  subscribeToEvents(sessionId: string, handler: (event: DebugEvent) => void): () => void {
    return MockAdapter.subscribeToEvents(sessionId, handler);
  },

  /**
   * Get the final outcome / result report for a session
   */
  async getResult(sessionId: string): Promise<FinalResult | null> {
    return MockAdapter.getResult(sessionId);
  },

  /**
   * Get session metadata
   */
  async getSession(sessionId: string): Promise<Session | null> {
    return MockAdapter.getSession(sessionId);
  },

  /**
   * Get recent sessions
   */
  async getRecentSessions(): Promise<Session[]> {
    return getRecentSessions();
  },

  /**
   * Fast-forward live event playback for a session (skip animation)
   */
  fastForward(sessionId: string): void {
    MockAdapter.fastForward(sessionId);
  },

  /**
   * Get current active session
   */
  getCurrentSession(): Session | null {
    return getCurrentSession();
  },
};
