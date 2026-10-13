import type { FinalResult, Round, Candidate, Session } from '../../types/litmus';

export const SCENARIO_1_SESSION: Session = {
  id: 'demo-session-verified-01',
  title: 'Sliding window token overlap off-by-one tail drop',
  mode: 'code',
  language: 'python',
  question: 'Why is `chunk_with_overlap` silently dropping the final 3 tokens in test_chunk_with_overlap_preserves_tail?',
  code: `def chunk_with_overlap(tokens: list[str], chunk_size: int, overlap: int) -> list[list[str]]:
    """
    Splits tokens into overlapping chunks of size chunk_size
    with an overlap count of overlap.
    """
    if not tokens or chunk_size <= 0:
        return []
    if overlap >= chunk_size:
        raise ValueError("overlap must be strictly less than chunk_size")

    step = chunk_size - overlap
    chunks = []

    # BUG (Off-by-one): Loop terminates prematurely at len(tokens) - chunk_size,
    # silently discarding the residual tail slice when tokens do not evenly divide.
    for i in range(0, len(tokens) - chunk_size, step):
        chunks.append(tokens[i : i + chunk_size])

    return chunks`,
  details: {
    failingTest: `def test_chunk_with_overlap_preserves_tail():
    tokens = ["tok1", "tok2", "tok3", "tok4", "tok5", "tok6", "tok7", "tok8"]
    chunks = chunk_with_overlap(tokens, chunk_size=3, overlap=1)

    assert len(chunks) == 4, f"Expected 4 chunks, got {len(chunks)}"
    assert chunks[-1] == ["tok7", "tok8"], f"Expected tail ['tok7', 'tok8'], got {chunks[-1]}"
    
    flattened = set()
    for c in chunks:
        flattened.update(c)
    assert flattened == set(tokens), f"Tokens missing: {set(tokens) - flattened}"`,
    expectedBehavior: 'All tokens must be preserved across overlapping chunks without dropping residual tail tokens.',
    errorMessage: 'AssertionError: Expected 4 chunks, got 2. Tokens missing: {\'tok6\', \'tok7\', \'tok8\'}',
  },
  createdAt: '2026-10-13T10:00:00Z',
  updatedAt: '2026-10-13T10:02:15Z',
  status: 'test_verified',
  isDemo: true,
  scenarioId: 'fix_b_passes',
};

const candidateA: Candidate = {
  id: 'fix_a',
  author: 'prosecutor',
  title: 'Range boundary extension to len(tokens)',
  code: `def chunk_with_overlap(tokens: list[str], chunk_size: int, overlap: int) -> list[list[str]]:
    if not tokens or chunk_size <= 0:
        return []
    if overlap >= chunk_size:
        raise ValueError("overlap must be strictly less than chunk_size")

    step = chunk_size - overlap
    chunks = []

    # Fix A: Extend boundary naively
    for i in range(0, len(tokens), step):
        chunk = tokens[i : i + chunk_size]
        if chunk:
            chunks.append(chunk)

    return chunks`,
  explanation: 'Prosecutor identified loop termination at len(tokens) - chunk_size as root cause. Removing subtraction permits iteration to reach the tail.',
  sandboxRun: {
    status: 'failed',
    passed: 3,
    failed: 1,
    total: 4,
    exitCode: 1,
    logs: `==================== FAILURES ====================
FAILED test_chunk_with_overlap.py::test_boundary_exact_multiple
AssertionError: Final chunk index overlaps beyond token boundary
assert len(chunks) == 3, got 4 (empty tail slice appended)
==================== 1 failed, 3 passed in 0.18s ====================`,
    durationMs: 184,
  },
};

const candidateB: Candidate = {
  id: 'fix_b',
  author: 'defender',
  title: 'While-loop with explicit boundary clamp & remainder check',
  code: `def chunk_with_overlap(tokens: list[str], chunk_size: int, overlap: int) -> list[list[str]]:
    if not tokens or chunk_size <= 0:
        return []
    if overlap >= chunk_size:
        raise ValueError("overlap must be strictly less than chunk_size")

    step = chunk_size - overlap
    chunks = []
    i = 0
    n = len(tokens)

    while i < n:
        chunk = tokens[i : min(i + chunk_size, n)]
        chunks.append(chunk)
        if i + chunk_size >= n:
            break
        i += step

    return chunks`,
  explanation: 'Defender countered that naive range indexing produces zero-length slices or duplicate indices when n % step == 0. Using a guarded while loop with min-clamp cleanly terminates.',
  sandboxRun: {
    status: 'passed',
    passed: 4,
    failed: 0,
    total: 4,
    exitCode: 0,
    logs: `==================== test session starts ====================
test_chunk_with_overlap.py::test_basic_overlap PASSED        [ 25%]
test_chunk_with_overlap.py::test_preserves_tail PASSED       [ 50%]
test_chunk_with_overlap.py::test_boundary_exact_multiple PASSED [ 75%]
test_chunk_with_overlap.py::test_single_chunk PASSED         [100%]
==================== 4 passed in 0.12s ====================`,
    durationMs: 122,
  },
};

export const SCENARIO_1_ROUNDS: Round[] = [
  {
    roundNumber: 1,
    prosecutorClaim: 'Root cause is premature loop upper bound `len(tokens) - chunk_size`. Expanding range ceiling remedies tail omission.',
    candidateA,
    defenderChallenge: 'Prosecutor’s Fix A appends out-of-bounds trailing slice when token length is an exact multiple of the window step. Fix B introduces safe while-stepping with min bounds clamp.',
    candidateB,
    decision: {
      roundNumber: 1,
      verdict: 'fix_b_selected',
      rationale: 'Fix A failed pytest regression suite (test_boundary_exact_multiple). Fix B passed all 4 test vectors with zero regressions in the sandbox environment.',
      evidence: [
        'Candidate A: Exit code 1, 1 failed assertion in boundary test.',
        'Candidate B: Exit code 0, 4/4 assertions passed.',
        'Deterministic execution verified in isolated ephemeral sandbox container.'
      ],
      timestamp: '2026-10-13T10:02:14Z',
    },
  },
];

export const SCENARIO_1_RESULT: FinalResult = {
  sessionId: 'demo-session-verified-01',
  status: 'test_verified',
  initialFailedTests: 1,
  finalFailedTests: 0,
  errors: [
    {
      id: 'err-1',
      title: 'Off-by-one window boundary truncation',
      file: 'chunker.py',
      line: 16,
      originalCode: 'for i in range(0, len(tokens) - chunk_size, step):',
      correctedCode: `while i < n:
    chunk = tokens[i : min(i + chunk_size, n)]
    chunks.append(chunk)
    if i + chunk_size >= n:
        break
    i += step`,
      explanation: 'Replaced rigid range stepper with bounds-checked window cursor.',
      verificationStatus: 'verified',
    },
  ],
  correctedCode: candidateB.code,
  summary: 'Prosecutor’s Fix A failed sandbox regression test test_boundary_exact_multiple. Defender’s Fix B resolved the off-by-one truncation while passing all 4 unit and boundary test suites.',
  rounds: SCENARIO_1_ROUNDS,
  rejectedAttempts: [
    {
      attemptId: 'att-1',
      author: 'prosecutor',
      code: candidateA.code,
      failureReason: 'Caused regression: appends duplicate empty slice when len(tokens) % step == 0',
    },
  ],
  limitations: [
    'Assumes tokens list supports slice operations and non-negative integer sizing.'
  ],
};
