import type { FinalResult, Round, Candidate, Session } from '../../types/litmus';

export const SCENARIO_2_SESSION: Session = {
  id: 'demo-session-unresolved-02',
  title: 'Async lock lease expiry and stale cache write race condition',
  mode: 'code',
  language: 'python',
  question: 'High-throughput async cache workers overwrite refreshed data during lease renewal spikes.',
  code: `import asyncio
import time

class LeaseCache:
    def __init__(self, ttl: float):
        self.ttl = ttl
        self.store = {}
        self.lock = asyncio.Lock()

    async def get_or_set(self, key: str, fetcher):
        # BUG: Race window between lease expiration check and store assignment
        entry = self.store.get(key)
        now = time.time()
        if entry and now - entry['timestamp'] < self.ttl:
            return entry['val']

        val = await fetcher()
        self.store[key] = {'val': val, 'timestamp': time.time()}
        return val`,
  details: {
    failingTest: `async def test_concurrent_thundering_herd():
    cache = LeaseCache(ttl=0.1)
    call_count = 0
    async def fetch():
        nonlocal call_count
        call_count += 1
        await asyncio.sleep(0.05)
        return f"val_{call_count}"

    results = await asyncio.gather(*[cache.get_or_set("k1", fetch) for _ in range(10)])
    assert len(set(results)) == 1, f"Expected 1 unique cached result, got {len(set(results))}"`,
    expectedBehavior: 'Single flight execution per cache key; concurrent requests await in-flight refresh without duplicate fetch calls.',
    errorMessage: 'AssertionError: Expected 1 unique cached result, got 4 (concurrent thundering herd stampede)',
  },
  createdAt: '2026-10-13T10:15:00Z',
  updatedAt: '2026-10-13T10:18:40Z',
  status: 'unresolved',
  isDemo: true,
  scenarioId: 'round2_unresolved',
};

// Round 1 Candidates
const round1CandidateA: Candidate = {
  id: 'fix_a',
  author: 'prosecutor',
  title: 'Global mutex wrap on get_or_set',
  code: `async def get_or_set(self, key: str, fetcher):
    async with self.lock:
        entry = self.store.get(key)
        if entry and time.time() - entry['timestamp'] < self.ttl:
            return entry['val']
        val = await fetcher()
        self.store[key] = {'val': val, 'timestamp': time.time()}
        return val`,
  explanation: 'Prosecutor locks the entire fetch lifecycle to eliminate concurrency races.',
  sandboxRun: {
    status: 'failed',
    passed: 2,
    failed: 2,
    total: 4,
    exitCode: 1,
    logs: `FAILED test_cache.py::test_interleaved_keys_throughput - TimeoutError: Global lock serializes disparate keys, throughput fell by 91%
FAILED test_cache.py::test_reentrant_deadlock - Deadlock detected in nested fetcher evaluation
2 failed, 2 passed in 1.45s`,
    durationMs: 1450,
  },
};

const round1CandidateB: Candidate = {
  id: 'fix_b',
  author: 'defender',
  title: 'Optimistic CAS double-check without fetch serialization',
  code: `async def get_or_set(self, key: str, fetcher):
    entry = self.store.get(key)
    if entry and time.time() - entry['timestamp'] < self.ttl:
        return entry['val']
    val = await fetcher()
    async with self.lock:
        self.store[key] = {'val': val, 'timestamp': time.time()}
    return val`,
  explanation: 'Defender moves fetch outside the lock to preserve throughput, only synchronizing store write.',
  sandboxRun: {
    status: 'failed',
    passed: 3,
    failed: 1,
    total: 4,
    exitCode: 1,
    logs: `FAILED test_cache.py::test_concurrent_thundering_herd - AssertionError: Expected 1 unique cached result, got 5
1 failed, 3 passed in 0.32s`,
    durationMs: 320,
  },
};

// Round 2 Candidates
const round2CandidateA: Candidate = {
  id: 'fix_a',
  author: 'prosecutor',
  title: 'Key-level async Event dictionary',
  code: `class LeaseCache:
    def __init__(self, ttl: float):
        self.ttl = ttl
        self.store = {}
        self.in_flight = {}

    async def get_or_set(self, key: str, fetcher):
        if key in self.in_flight:
            await self.in_flight[key]
            return self.store[key]['val']
        evt = asyncio.Event()
        self.in_flight[key] = evt
        try:
            val = await fetcher()
            self.store[key] = {'val': val, 'timestamp': time.time()}
            evt.set()
            return val
        finally:
            self.in_flight.pop(key, None)`,
  explanation: 'Round 2 Prosecutor introduces per-key single-flight events, fed by evidence from Round 1 deadlock reports.',
  sandboxRun: {
    status: 'failed',
    passed: 3,
    failed: 1,
    total: 4,
    exitCode: 1,
    logs: `FAILED test_cache.py::test_fetcher_exception_propagation - KeyError: 'k1' when fetcher raises and waiters unblock before store set.
1 failed, 3 passed in 0.45s`,
    durationMs: 450,
  },
};

const round2CandidateB: Candidate = {
  id: 'fix_b',
  author: 'defender',
  title: 'Future promise caching with weakref cleanup',
  code: `class LeaseCache:
    def __init__(self, ttl: float):
        self.ttl = ttl
        self.store = {}
        self.tasks = {}

    async def get_or_set(self, key: str, fetcher):
        entry = self.store.get(key)
        if entry and time.time() - entry['timestamp'] < self.ttl:
            return entry['val']
        if key not in self.tasks or self.tasks[key].done():
            self.tasks[key] = asyncio.create_task(fetcher())
        val = await self.tasks[key]
        self.store[key] = {'val': val, 'timestamp': time.time()}
        return val`,
  explanation: 'Round 2 Defender caches the task future directly to multiplex concurrent callers.',
  sandboxRun: {
    status: 'failed',
    passed: 3,
    failed: 1,
    total: 4,
    exitCode: 1,
    logs: `FAILED test_cache.py::test_memory_leak_on_high_cardinality - Memory leak: tasks dictionary unbounded growth under transient key access.
1 failed, 3 passed in 0.62s`,
    durationMs: 620,
  },
};

export const SCENARIO_2_ROUNDS: Round[] = [
  {
    roundNumber: 1,
    prosecutorClaim: 'Global lock solves atomic state transition. Any concurrency issues are secondary to race correctness.',
    candidateA: round1CandidateA,
    defenderChallenge: 'Global lock causes severe throughput degradation and deadlocks on re-entrant calls. Optimistic sync outside lock is required.',
    candidateB: round1CandidateB,
    decision: {
      roundNumber: 1,
      verdict: 'both_failed',
      rationale: 'Both Round 1 candidates failed sandbox verification. Candidate A deadlocked in nested evaluations; Candidate B failed thundering herd mitigation. Escalating evidence to Round 2.',
      evidence: [
        'Candidate A: Exit code 1, re-entrant deadlock in sandbox.',
        'Candidate B: Exit code 1, thundering herd assertion failed (5 redundant executions).',
        'Both candidates rejected; round 2 synthesis initiated with captured trace logs.'
      ],
      timestamp: '2026-10-13T10:16:30Z',
    },
  },
  {
    roundNumber: 2,
    prosecutorClaim: 'Per-key event synchronization addresses cross-key lock serialization without global contention.',
    candidateA: round2CandidateA,
    defenderChallenge: 'Per-key events fail exception boundary guarantees. Multiplexed Task future caching is superior.',
    candidateB: round2CandidateB,
    decision: {
      roundNumber: 2,
      verdict: 'both_failed',
      rationale: 'After 2 rounds of adversarial synthesis, both candidates remain unable to satisfy safety invariants without secondary defects (exception propagation failure vs unbounded memory leaks). Result flagged unresolved for human review.',
      evidence: [
        'Round 2 Candidate A: Unhandled KeyError on fetcher error propagation.',
        'Round 2 Candidate B: Unbounded dictionary retention fails memory leak invariant.',
        'Total rounds: 2. Safety criterion: unverified.'
      ],
      timestamp: '2026-10-13T10:18:38Z',
    },
  },
];

export const SCENARIO_2_RESULT_UNRESOLVED: FinalResult = {
  sessionId: 'demo-session-unresolved-02',
  status: 'unresolved',
  initialFailedTests: 1,
  finalFailedTests: 1,
  errors: [
    {
      id: 'err-2',
      title: 'Distributed stampede and unhandled asynchronous race condition',
      file: 'cache.py',
      line: 14,
      originalCode: 'val = await fetcher()\nself.store[key] = {\'val\': val, \'timestamp\': time.time()}',
      correctedCode: '# Unresolved: Requires atomic single-flight primitive with safe exception disposal',
      explanation: 'Both adversarial rounds failed to synthesize a patch that simultaneously prevented race conditions without introducing deadlocks or memory leaks.',
      verificationStatus: 'failed',
    },
  ],
  correctedCode: null,
  summary: 'Both Prosecutor and Defender patches failed sandbox test suites across Round 1 and Round 2. Bug marked unresolved to prevent deploying regressive patches.',
  rounds: SCENARIO_2_ROUNDS,
  rejectedAttempts: [
    { attemptId: 'att-2-1', author: 'prosecutor', code: round1CandidateA.code, failureReason: 'Global mutex deadlocks nested fetchers' },
    { attemptId: 'att-2-2', author: 'defender', code: round1CandidateB.code, failureReason: 'Optimistic CAS failed thundering herd mitigation' },
    { attemptId: 'att-2-3', author: 'prosecutor', code: round2CandidateA.code, failureReason: 'KeyError on fetcher exception propagation' },
    { attemptId: 'att-2-4', author: 'defender', code: round2CandidateB.code, failureReason: 'Memory leak: unbounded retention of finished tasks' },
  ],
  limitations: [
    'Requires external single-flight or async-semaphore coordinator library.',
    'Test suite requires mock time harness to guarantee deterministic execution.'
  ],
};

// Also support a selectable variant where Round 2 resolves!
export const SCENARIO_2_RESULT_RESOLVED: FinalResult = {
  sessionId: 'demo-session-unresolved-02',
  status: 'test_verified',
  initialFailedTests: 1,
  finalFailedTests: 0,
  errors: [
    {
      id: 'err-2',
      title: 'Async lock lease thundering herd stampede',
      file: 'cache.py',
      line: 14,
      originalCode: 'val = await fetcher()\nself.store[key] = {\'val\': val, \'timestamp\': time.time()}',
      correctedCode: `async def get_or_set(self, key: str, fetcher):
    async with self.key_locks[key]:
        entry = self.store.get(key)
        if entry and time.time() - entry['timestamp'] < self.ttl:
            return entry['val']
        val = await fetcher()
        self.store[key] = {'val': val, 'timestamp': time.time()}
        return val`,
      explanation: 'Synthesized per-key lock dictionary with bounded weak references.',
      verificationStatus: 'verified',
    },
  ],
  correctedCode: `# Resolved in Round 2 via bounded single-flight coordinator`,
  summary: 'Round 1 both failed; Round 2 resolved using evidence feedback loop.',
  rounds: SCENARIO_2_ROUNDS,
  rejectedAttempts: [
    { attemptId: 'att-2-1', author: 'prosecutor', code: round1CandidateA.code, failureReason: 'Global mutex deadlocks nested fetchers' },
    { attemptId: 'att-2-2', author: 'defender', code: round1CandidateB.code, failureReason: 'Optimistic CAS failed thundering herd mitigation' },
  ],
  limitations: ['Verified for thread-safe event loop only.'],
};
