import { describe, it, expect, beforeEach } from 'vitest';
import { 
  getCurrentSession, 
  saveCurrentSession, 
  clearCurrentSession,
  getRecentSessions, 
  addRecentSession, 
  clearRecentSessions 
} from '../services/sessionStore';
import type { Session } from '../types/litmus';

describe('sessionStore', () => {
  const dummySession: Session = {
    id: 'test-session-123',
    title: 'Test Off By One Bug',
    mode: 'code',
    language: 'python',
    question: 'Why does slice drop the last element?',
    code: 'def slice(): pass',
    createdAt: new Date().toISOString(),
    updatedAt: new Date().toISOString(),
    status: 'in_progress',
  };

  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
  });

  describe('sessionStorage (litmus.session)', () => {
    it('saves and retrieves current session cleanly', () => {
      saveCurrentSession(dummySession);
      const retrieved = getCurrentSession();
      expect(retrieved).not.toBeNull();
      expect(retrieved?.id).toBe(dummySession.id);
      expect(retrieved?.title).toBe(dummySession.title);
    });

    it('returns null and clears if data is corrupt in sessionStorage', () => {
      sessionStorage.setItem('litmus.session', '{invalid-json');
      const retrieved = getCurrentSession();
      expect(retrieved).toBeNull();
      expect(sessionStorage.getItem('litmus.session')).toBeNull();
    });

    it('clears current session', () => {
      saveCurrentSession(dummySession);
      clearCurrentSession();
      expect(getCurrentSession()).toBeNull();
    });
  });

  describe('localStorage (litmus.recent_sessions)', () => {
    it('adds and lists recent sessions with recency ordering', () => {
      const session2: Session = { ...dummySession, id: 'test-session-456', title: 'Second bug' };
      addRecentSession(dummySession);
      addRecentSession(session2);

      const list = getRecentSessions();
      expect(list.length).toBe(2);
      expect(list[0].id).toBe('test-session-456'); // Most recent first
      expect(list[1].id).toBe('test-session-123');
    });

    it('handles corrupt JSON in localStorage safely', () => {
      localStorage.setItem('litmus.recent_sessions', 'not-a-json-array');
      const list = getRecentSessions();
      expect(list).toEqual([]);
    });

    it('clears recent sessions', () => {
      addRecentSession(dummySession);
      expect(getRecentSessions().length).toBe(1);
      clearRecentSessions();
      expect(getRecentSessions().length).toBe(0);
    });
  });
});
