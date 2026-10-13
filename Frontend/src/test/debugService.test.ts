import { describe, it, expect, beforeEach } from 'vitest';
import { debugService } from '../services/debugService';
import { formatMeasured, type DebugEvent } from '../types/litmus';
import { SCENARIO_1_SESSION, SCENARIO_1_RESULT } from '../demo/scenarios/scenario1_verified';
import { SCENARIO_2_SESSION, SCENARIO_2_RESULT_UNRESOLVED } from '../demo/scenarios/scenario2_unresolved';
import { SCENARIO_3_SESSION, SCENARIO_3_RESULT } from '../demo/scenarios/scenario3_timeout';
import { setActiveDemoScenarioId } from '../demo/demoState';

describe('debugService & Demo Data', () => {
  beforeEach(() => {
    sessionStorage.clear();
    localStorage.clear();
    setActiveDemoScenarioId('fix_b_passes');
  });

  describe('Demo Scenarios Data Integrity', () => {
    it('Scenario 1 is flagged isDemo: true and test_verified with realistic Python off-by-one bug', () => {
      expect(SCENARIO_1_SESSION.isDemo).toBe(true);
      expect(SCENARIO_1_SESSION.language).toBe('python');
      expect(SCENARIO_1_SESSION.code).toContain('chunk_with_overlap');
      expect(SCENARIO_1_SESSION.details?.failingTest).toContain('test_chunk_with_overlap_preserves_tail');
      expect(SCENARIO_1_SESSION.details?.errorMessage).toContain('AssertionError');
      expect(SCENARIO_1_RESULT.status).toBe('test_verified');
      expect(SCENARIO_1_RESULT.rounds[0].candidateA.sandboxRun?.status).toBe('failed');
      expect(SCENARIO_1_RESULT.rounds[0].candidateB.sandboxRun?.status).toBe('passed');
    });

    it('Scenario 2 is flagged isDemo: true and represents both failing Round 1 -> unresolved', () => {
      expect(SCENARIO_2_SESSION.isDemo).toBe(true);
      expect(SCENARIO_2_SESSION.status).toBe('unresolved');
      expect(SCENARIO_2_RESULT_UNRESOLVED.status).toBe('unresolved');
      expect(SCENARIO_2_RESULT_UNRESOLVED.rounds.length).toBe(2);
      expect(SCENARIO_2_RESULT_UNRESOLVED.rounds[0].decision.verdict).toBe('both_failed');
    });

    it('Scenario 3 is flagged isDemo: true and represents sandbox watchdog timeout -> execution_inconclusive', () => {
      expect(SCENARIO_3_SESSION.isDemo).toBe(true);
      expect(SCENARIO_3_RESULT.status).toBe('execution_inconclusive');
      const candidateRun = SCENARIO_3_RESULT.rounds[0].candidateA.sandboxRun;
      expect(candidateRun?.status).toBe('timed_out');
      expect(candidateRun?.passed).toBeNull();
      expect(candidateRun?.failed).toBeNull();
      expect(candidateRun?.exitCode).toBeNull();
      expect(candidateRun?.logs).toContain('NOT presented as a defective patch');
      expect(SCENARIO_3_RESULT.finalFailedTests).toBeNull();
    });
  });

  describe('formatMeasured helper', () => {
    it('returns "Not measured" for null and undefined', () => {
      expect(formatMeasured(null)).toBe('Not measured');
      expect(formatMeasured(undefined)).toBe('Not measured');
    });

    it('returns formatted value with optional suffix when measured', () => {
      expect(formatMeasured(0)).toBe('0');
      expect(formatMeasured(4, ' tests')).toBe('4 tests');
      expect(formatMeasured('OK')).toBe('OK');
    });
  });

  describe('debugService session creation & retrieval', () => {
    it('creates a session, stores it, and can fetch results', async () => {
      const session = await debugService.createSession({
        mode: 'code',
        language: 'python',
        question: 'Why did the test fail on boundary?',
        code: 'def test(): pass',
      });

      expect(session.id).toBeDefined();
      expect(session.status).toBe('in_progress');
      expect(session.isDemo).toBe(true);

      const retrieved = await debugService.getSession(session.id);
      expect(retrieved?.id).toBe(session.id);

      const result = await debugService.getResult(session.id);
      expect(result).not.toBeNull();
      expect(result?.sessionId).toBe(session.id);
    });

    it('subscribes to live debug events and unsubscribes cleanly', async () => {
      const events: DebugEvent[] = [];
      const session = await debugService.createSession({
        mode: 'code',
        language: 'python',
        question: 'Testing event stream',
        code: 'def dummy(): pass',
      });

      const unsubscribe = debugService.subscribeToEvents(session.id, (evt) => {
        events.push(evt);
      });

      expect(typeof unsubscribe).toBe('function');
      unsubscribe();
    });
  });
});
