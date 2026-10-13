import type { FinalResult, Round, Candidate, Session } from '../../types/litmus';

export const SCENARIO_3_SESSION: Session = {
  id: 'demo-session-timeout-03',
  title: 'Regex backtracking catastrophe on nested markdown parser',
  mode: 'code',
  language: 'python',
  question: 'Input string with repeated nested formatting brackets hangs the parser indefinitely.',
  code: `import re

# Regex with catastrophic backtracking potential on unbalanced nested delimiters
MARKDOWN_BOLD_ITALIC_PATTERN = re.compile(
    r"^(\\*|_)+([^*_]+(?:(\\*|_)+[^*_]+)*)+(\\*|_)+$"
)

def parse_inline_tokens(text: str) -> bool:
    if not text:
        return False
    return bool(MARKDOWN_BOLD_ITALIC_PATTERN.match(text))`,
  details: {
    failingTest: `def test_malicious_nested_delimiters():
    # 28 asterisks followed by non-matching token
    payload = "*" * 28 + "!"
    # Expected: Fast rejection (< 50ms)
    assert parse_inline_tokens(payload) is False`,
    expectedBehavior: 'Linear time scan or bounded stack regex parser without exponential backtracking.',
    errorMessage: 'PytestTimeoutError: Test test_malicious_nested_delimiters timed out after 30.0s',
  },
  createdAt: '2026-10-13T10:30:00Z',
  updatedAt: '2026-10-13T10:33:12Z',
  status: 'execution_inconclusive',
  isDemo: true,
  scenarioId: 'sandbox_timeout',
};

const timeoutCandidateA: Candidate = {
  id: 'fix_a',
  author: 'prosecutor',
  title: 'Atomic grouping syntax emulation using lookahead',
  code: `import re

# Prosecutor patch attempt using simulated atomic groupings
MARKDOWN_PATTERN = re.compile(
    r"^(?=(\\*|_)+)\\1(?=([^*_]+))\\2(?=(\\*|_)+)\\3$"
)

def parse_inline_tokens(text: str) -> bool:
    if not text:
        return False
    return bool(MARKDOWN_PATTERN.match(text))`,
  explanation: 'Prosecutor attempted regex lookahead emulation to prevent backtracking branch exploration.',
  sandboxRun: {
    status: 'timed_out',
    passed: null, // Not measured
    failed: null, // Not measured
    total: null,  // Not measured
    exitCode: null, // Not measured
    durationMs: 30000,
    logs: `[SANDBOX WATCHDOG ALERT]
Execution exceeded 30000ms wall-clock safety threshold.
Container signal SIGKILL dispatched to PID 4129.
Exit code: null (Killed by watchdog).
Metrics:
- Test assertions completed: Not measured (interrupted)
- Memory peak: 184MB
- CPU utilization: 99.8% (single thread compute saturation)

NOTE: This execution is flagged execution_inconclusive.
Per litmus governance, a watchdog timeout is NOT presented as a defective patch.`,
  },
};

const candidateBTimeout: Candidate = {
  id: 'fix_b',
  author: 'defender',
  title: 'Iterative deterministic pushdown token scanner',
  code: `def parse_inline_tokens(text: str) -> bool:
    if not text:
        return False
    # Defender linear O(N) single-pass stack scanner
    stack = []
    has_content = False
    for ch in text:
        if ch in ('*', '_'):
            if stack and stack[-1] == ch and has_content:
                stack.pop()
            else:
                stack.append(ch)
        else:
            has_content = True
    return len(stack) == 0 and has_content`,
  explanation: 'Defender replaces regex backtracking engine with a deterministic O(N) finite stack automaton.',
  sandboxRun: {
    status: 'passed',
    passed: 3,
    failed: 0,
    total: 3,
    exitCode: 0,
    durationMs: 48,
    logs: `test_parser.py::test_basic_formatting PASSED
test_parser.py::test_malicious_nested_delimiters PASSED [time=0.002s]
test_parser.py::test_unbalanced_delimiters PASSED
3 passed in 0.05s`,
  },
};

export const SCENARIO_3_ROUNDS: Round[] = [
  {
    roundNumber: 1,
    prosecutorClaim: 'Refactoring regular expression with lookahead prevents catastrophic state explosion.',
    candidateA: timeoutCandidateA,
    defenderChallenge: 'Python standard re module does not support atomic groupings natively; regex still backtracks indefinitely. A deterministic state machine is required.',
    candidateB: candidateBTimeout,
    decision: {
      roundNumber: 1,
      verdict: 'inconclusive',
      rationale: 'Candidate A sandbox was terminated by safety watchdog after exceeding 30000ms limit. Outcome is classified as execution_inconclusive — not classified as a defective patch.',
      evidence: [
        'Candidate A: Watchdog timeout (30.0s limit reached). Unmeasured test assertions.',
        'Candidate B: Verified in 48ms.',
        'Adjudication rule: Timeout runs are recorded as inconclusive rather than confirmed defective.'
      ],
      timestamp: '2026-10-13T10:33:10Z',
    },
  },
];

export const SCENARIO_3_RESULT: FinalResult = {
  sessionId: 'demo-session-timeout-03',
  status: 'execution_inconclusive',
  initialFailedTests: 1,
  finalFailedTests: null, // Not measured
  errors: [
    {
      id: 'err-3',
      title: 'Catastrophic regular expression backtracking execution timeout',
      file: 'markdown.py',
      line: 4,
      originalCode: 'MARKDOWN_BOLD_ITALIC_PATTERN = re.compile(r"^(\\*|_)+([^*_]+(?:(\\*|_)+[^*_]+)*)+(\\*|_)+$")',
      correctedCode: candidateBTimeout.code,
      explanation: 'Candidate A timed out in sandbox. Result is execution_inconclusive. Candidate B demonstrates deterministic linear evaluation alternative.',
      verificationStatus: 'unverified',
    },
  ],
  correctedCode: candidateBTimeout.code,
  summary: 'A sandbox run exceeded the 30000ms execution threshold and was halted by watchdog. The status is execution_inconclusive (not classified as defective patch). Test results for timed-out run are not measured.',
  rounds: SCENARIO_3_ROUNDS,
  rejectedAttempts: [
    {
      attemptId: 'att-3-1',
      author: 'prosecutor',
      code: timeoutCandidateA.code,
      failureReason: 'Sandbox timeout (30000ms exceeded). Inconclusive test measurement.',
    },
  ],
  limitations: [
    'Execution halted by sandbox safety watchdog.',
    'Test assertions and exit code for timed-out container were not measured.',
  ],
};
