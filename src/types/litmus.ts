/**
 * LITMUS Shared Type Definitions
 * "Debate the Cause. Run the Fix."
 */

export type InputMode = 'code' | 'file' | 'repo';

export type SessionStatus = 
  | 'in_progress'
  | 'test_verified'
  | 'unresolved'
  | 'execution_inconclusive';

export type SandboxRunStatus = 
  | 'pending'
  | 'preparing'
  | 'running'
  | 'passed'
  | 'failed'
  | 'timed_out'
  | 'execution_error';

export type JudgeVerdict = 
  | 'fix_a_selected'
  | 'fix_b_selected'
  | 'both_failed'
  | 'inconclusive'
  | 'escalate_round_2';

export type FinalResultStatus = 
  | 'test_verified'
  | 'unresolved'
  | 'execution_inconclusive';

export type DebugEventType = 
  | 'analysis_started'
  | 'root_cause_located'
  | 'fixes_compared'
  | 'sandbox_started'
  | 'sandbox_finished'
  | 'judge_decision'
  | 'round_started'
  | 'completed'
  | 'error';

export type AgentRole = 'prosecutor' | 'defender' | 'judge' | 'system';

export interface BugDetails {
  failingTest?: string;
  expectedBehavior?: string;
  errorMessage?: string;
}

export interface Session {
  id: string;
  title: string;
  mode: InputMode;
  language: string;
  question: string;
  code?: string;
  fileName?: string;
  fileSize?: number;
  fileContent?: string;
  repoUrl?: string;
  details?: BugDetails;
  createdAt: string;
  updatedAt: string;
  status: SessionStatus;
  isDemo?: boolean;
  scenarioId?: string;
}

export interface SandboxRun {
  status: SandboxRunStatus;
  passed: number | null;
  failed: number | null;
  total: number | null;
  exitCode: number | null;
  logs: string | null;
  durationMs?: number | null;
}

export interface Candidate {
  id: 'fix_a' | 'fix_b';
  author: 'prosecutor' | 'defender';
  title: string;
  code: string;
  diff?: string;
  explanation: string;
  sandboxRun?: SandboxRun;
}

export interface JudgeDecision {
  roundNumber: number;
  verdict: JudgeVerdict;
  rationale: string;
  evidence: string[];
  timestamp: string;
}

export interface Round {
  roundNumber: number;
  prosecutorClaim: string;
  candidateA: Candidate;
  defenderChallenge: string;
  candidateB: Candidate;
  decision: JudgeDecision;
}

export interface BugErrorItem {
  id: string;
  title: string;
  file: string;
  line: number | null;
  originalCode: string;
  correctedCode: string;
  explanation: string;
  verificationStatus: 'verified' | 'failed' | 'unverified';
}

export interface RejectedAttempt {
  attemptId: string;
  author: string;
  code: string;
  failureReason: string;
}

export interface FinalResult {
  sessionId: string;
  status: FinalResultStatus;
  initialFailedTests: number | null;
  finalFailedTests: number | null;
  errors: BugErrorItem[];
  correctedCode: string | null;
  summary: string;
  rounds: Round[];
  rejectedAttempts: RejectedAttempt[];
  limitations: string[];
}

export interface DebugEvent {
  type: DebugEventType;
  sessionId: string;
  roundNumber?: number;
  timestamp: string;
  agent?: AgentRole;
  message: string;
  payload?: unknown;
}

export interface CreateSessionInput {
  mode: InputMode;
  language: string;
  question: string;
  code?: string;
  fileName?: string;
  fileSize?: number;
  fileContent?: string;
  repoUrl?: string;
  details?: BugDetails;
  scenarioId?: string;
  isDemo?: boolean;
}

/**
 * Helper to display "Not measured" for unmeasured metrics as required
 */
export function formatMeasured(value: number | string | null | undefined, suffix = ''): string {
  if (value === null || value === undefined) {
    return 'Not measured';
  }
  return `${value}${suffix}`;
}
