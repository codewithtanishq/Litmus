import type { 
  Session, 
  CreateSessionInput, 
  DebugEvent, 
  FinalResult, 
} from '../../types/litmus';
import { getActiveDemoScenario, DEMO_SCENARIOS } from '../../demo/demoState';
import { saveCurrentSession, addRecentSession, getCurrentSession } from '../sessionStore';

// In-memory store for mock sessions and simulated results
const mockSessions = new Map<string, Session>();
const mockResults = new Map<string, FinalResult>();
const eventSubscribers = new Map<string, Set<(event: DebugEvent) => void>>();

// Initialize with demo scenarios
for (const scenario of DEMO_SCENARIOS) {
  mockSessions.set(scenario.session.id, scenario.session);
  mockResults.set(scenario.session.id, scenario.result);
}

export const MockAdapter = {
  /**
   * Create a new debugging session
   */
  async createSession(input: CreateSessionInput): Promise<Session> {
    const activeScenario = getActiveDemoScenario();
    const id = `session-${Date.now()}-${Math.random().toString(36).slice(2, 7)}`;
    const now = new Date().toISOString();

    let title = input.question.slice(0, 60);
    if (input.mode === 'file' && input.fileName) {
      title = `[File: ${input.fileName}] ${title || 'Inspect bug'}`;
    } else if (input.mode === 'repo' && input.repoUrl) {
      title = `[Repo: ${input.repoUrl.replace('https://github.com/', '')}] ${title || 'Analyze repo'}`;
    } else if (!title) {
      title = 'Python off-by-one tail drop inspection';
    }

    const session: Session = {
      id,
      title,
      mode: input.mode,
      language: input.language,
      question: input.question,
      code: input.code,
      fileName: input.fileName,
      fileSize: input.fileSize,
      fileContent: input.fileContent,
      repoUrl: input.repoUrl,
      details: input.details,
      createdAt: now,
      updatedAt: now,
      status: 'in_progress',
      isDemo: input.isDemo ?? true,
      scenarioId: input.scenarioId || activeScenario.id,
    };

    mockSessions.set(id, session);

    // Pair with the demo scenario result or a synthesized result
    const baseResult = activeScenario.result;
    const result: FinalResult = {
      ...baseResult,
      sessionId: id,
    };
    mockResults.set(id, result);

    // Save to persistence
    saveCurrentSession(session);
    addRecentSession(session);

    return session;
  },

  /**
   * Get an existing session by ID
   */
  async getSession(sessionId: string): Promise<Session | null> {
    const active = getActiveDemoScenario();
    if (active.session.id === sessionId) {
      return active.session;
    }
    if (mockSessions.has(sessionId)) {
      return mockSessions.get(sessionId)!;
    }
    const current = getCurrentSession();
    if (current && current.id === sessionId) {
      return current;
    }
    return null;
  },

  /**
   * Subscribe to debugging event stream for a session
   */
  subscribeToEvents(sessionId: string, handler: (event: DebugEvent) => void): () => void {
    if (!eventSubscribers.has(sessionId)) {
      eventSubscribers.set(sessionId, new Set());
    }
    const subs = eventSubscribers.get(sessionId)!;
    subs.add(handler);

    // Simulated event emission pipeline
    const activeScenario = getActiveDemoScenario();
    const isTimeout = activeScenario.id === 'sandbox_timeout';
    const isRound2 = activeScenario.id.startsWith('round2');

    const timeline: Array<{ delay: number; event: DebugEvent }> = [
      {
        delay: 300,
        event: {
          type: 'analysis_started',
          sessionId,
          timestamp: new Date().toISOString(),
          agent: 'system',
          message: 'Ingesting codebase context and parsing test definitions...',
        },
      },
      {
        delay: 800,
        event: {
          type: 'root_cause_located',
          sessionId,
          timestamp: new Date().toISOString(),
          agent: 'prosecutor',
          message: 'Prosecutor hypothesis generated: isolated root cause and drafted Candidate Fix A.',
        },
      },
      {
        delay: 1400,
        event: {
          type: 'round_started',
          sessionId,
          roundNumber: 1,
          timestamp: new Date().toISOString(),
          agent: 'judge',
          message: 'Round 1 debate convened. Prosecutor presents claim; Defender challenges.',
        },
      },
      {
        delay: 2000,
        event: {
          type: 'fixes_compared',
          sessionId,
          roundNumber: 1,
          timestamp: new Date().toISOString(),
          agent: 'defender',
          message: 'Defender identified regression vulnerability in Fix A; constructed Fix B.',
        },
      },
      {
        delay: 2600,
        event: {
          type: 'sandbox_started',
          sessionId,
          roundNumber: 1,
          timestamp: new Date().toISOString(),
          agent: 'judge',
          message: 'Spinning up isolated ephemeral execution sandboxes for Fix A and Fix B...',
        },
      },
      {
        delay: 3400,
        event: {
          type: 'sandbox_finished',
          sessionId,
          roundNumber: 1,
          timestamp: new Date().toISOString(),
          agent: 'judge',
          message: isTimeout 
            ? 'Candidate A triggered watchdog timeout (>30000ms). Fix B completed.'
            : 'Sandbox execution complete. Test output & exit codes captured.',
        },
      },
      {
        delay: 4200,
        event: {
          type: 'judge_decision',
          sessionId,
          roundNumber: 1,
          timestamp: new Date().toISOString(),
          agent: 'judge',
          message: isRound2
            ? 'Judge: Both Round 1 candidates failed regression suites. Escalating evidence to Round 2.'
            : isTimeout
              ? 'Judge: Candidate A timed out. Recorded as inconclusive, not defective.'
              : 'Judge: Candidate B satisfied all verification criteria. Fix A rejected on regression.',
        },
      },
    ];

    if (isRound2) {
      timeline.push(
        {
          delay: 5000,
          event: {
            type: 'round_started',
            sessionId,
            roundNumber: 2,
            timestamp: new Date().toISOString(),
            agent: 'judge',
            message: 'Round 2 convened. Agents ingest Round 1 trace logs and counter-argue.',
          },
        },
        {
          delay: 5800,
          event: {
            type: 'judge_decision',
            sessionId,
            roundNumber: 2,
            timestamp: new Date().toISOString(),
            agent: 'judge',
            message: activeScenario.id === 'round2_resolved'
              ? 'Judge: Round 2 Candidate B verified in sandbox.'
              : 'Judge: Hypothesis space exhausted. Status: unresolved.',
          },
        }
      );
    }

    timeline.push({
      delay: isRound2 ? 6500 : 4900,
      event: {
        type: 'completed',
        sessionId,
        timestamp: new Date().toISOString(),
        agent: 'system',
        message: 'Debate workflow concluded. Final verification report generated.',
      },
    });

    // Schedule timeouts
    const remainingEvents = timeline.map(t => t.event);
    const timerIds: number[] = [];

    const clearActiveTimers = () => {
      for (const tid of timerIds) {
        clearTimeout(tid);
      }
      timerIds.length = 0;
    };

    for (let i = 0; i < timeline.length; i++) {
      const item = timeline[i];
      const tid = window.setTimeout(() => {
        // remove from remaining
        const evIndex = remainingEvents.indexOf(item.event);
        if (evIndex !== -1) {
          remainingEvents.splice(evIndex, 1);
        }

        // update session status on completion
        if (item.event.type === 'completed') {
          const session = mockSessions.get(sessionId);
          if (session) {
            session.status = activeScenario.expectedStatus;
            saveCurrentSession(session);
            addRecentSession(session);
          }
        }
        subs.forEach(cb => cb(item.event));
      }, item.delay);
      timerIds.push(tid);
    }

    // Register active fast-forward hook
    MockAdapter._activeStreams.set(sessionId, {
      timerIds,
      remainingEvents,
      onFastForward: () => {
        clearActiveTimers();
        const pending = [...remainingEvents];
        remainingEvents.length = 0;
        for (const ev of pending) {
          if (ev.type === 'completed') {
            const session = mockSessions.get(sessionId);
            if (session) {
              session.status = activeScenario.expectedStatus;
              saveCurrentSession(session);
              addRecentSession(session);
            }
          }
          subs.forEach(cb => cb(ev));
        }
      },
    });

    // Return unsubscriber
    return () => {
      subs.delete(handler);
      clearActiveTimers();
      MockAdapter._activeStreams.delete(sessionId);
    };
  },

  _activeStreams: new Map<string, { timerIds: number[]; remainingEvents: DebugEvent[]; onFastForward: () => void }>(),

  /**
   * Fast-forwards all remaining timeline events immediately (used by Skip Animation)
   */
  fastForward(sessionId: string): void {
    const stream = MockAdapter._activeStreams.get(sessionId);
    if (stream) {
      stream.onFastForward();
    }
  },

  /**
   * Fetch final result for a session
   */
  async getResult(sessionId: string): Promise<FinalResult | null> {
    const active = getActiveDemoScenario();
    if (active.session.id === sessionId) {
      return {
        ...active.result,
        sessionId,
      };
    }
    if (mockResults.has(sessionId)) {
      return mockResults.get(sessionId)!;
    }
    return {
      ...active.result,
      sessionId,
    };
  },
};
