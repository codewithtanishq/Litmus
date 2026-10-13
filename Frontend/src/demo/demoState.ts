import { SCENARIO_1_SESSION, SCENARIO_1_RESULT } from './scenarios/scenario1_verified';
import { 
  SCENARIO_2_SESSION, 
  SCENARIO_2_RESULT_UNRESOLVED, 
  SCENARIO_2_RESULT_RESOLVED 
} from './scenarios/scenario2_unresolved';
import { SCENARIO_3_SESSION, SCENARIO_3_RESULT } from './scenarios/scenario3_timeout';
import type { Session, FinalResult } from '../types/litmus';

export type DemoScenarioId = 
  | 'fix_b_passes' 
  | 'round2_unresolved' 
  | 'round2_resolved' 
  | 'sandbox_timeout';

export interface DemoScenarioConfig {
  id: DemoScenarioId;
  name: string;
  badgeLabel: string;
  description: string;
  expectedStatus: 'test_verified' | 'unresolved' | 'execution_inconclusive';
  session: Session;
  result: FinalResult;
}

export const DEMO_SCENARIOS: DemoScenarioConfig[] = [
  {
    id: 'fix_b_passes',
    name: 'Scenario 1: Verified (Fix B Passes)',
    badgeLabel: 'Verified (Fix B)',
    description: 'Fix A fails boundary check, Fix B passes all sandbox tests -> test_verified (Python off-by-one bug).',
    expectedStatus: 'test_verified',
    session: SCENARIO_1_SESSION,
    result: SCENARIO_1_RESULT,
  },
  {
    id: 'round2_unresolved',
    name: 'Scenario 2A: Unresolved (Both Fail Round 1 & 2)',
    badgeLabel: 'Unresolved (Rounds 1 & 2)',
    description: 'Both fail in round 1, evidence feeds round 2 -> unresolved (concurrency race condition).',
    expectedStatus: 'unresolved',
    session: SCENARIO_2_SESSION,
    result: SCENARIO_2_RESULT_UNRESOLVED,
  },
  {
    id: 'round2_resolved',
    name: 'Scenario 2B: Resolved in Round 2',
    badgeLabel: 'Resolved (Round 2)',
    description: 'Both fail in round 1, evidence feeds round 2 -> test_verified in round 2.',
    expectedStatus: 'test_verified',
    session: { ...SCENARIO_2_SESSION, status: 'test_verified' },
    result: SCENARIO_2_RESULT_RESOLVED,
  },
  {
    id: 'sandbox_timeout',
    name: 'Scenario 3: Watchdog Timeout (Inconclusive)',
    badgeLabel: 'Inconclusive (Timeout)',
    description: 'Sandbox container watchdog timeout (30s limit) -> execution_inconclusive (not defective patch).',
    expectedStatus: 'execution_inconclusive',
    session: SCENARIO_3_SESSION,
    result: SCENARIO_3_RESULT,
  },
];

// Active demo scenario stored in localStorage with event listener for synchronized tab/component updates
const DEMO_SCENARIO_KEY = 'litmus.active_demo_scenario';

export function getActiveDemoScenarioId(): DemoScenarioId {
  try {
    const saved = localStorage.getItem(DEMO_SCENARIO_KEY);
    if (saved && DEMO_SCENARIOS.some(s => s.id === saved)) {
      return saved as DemoScenarioId;
    }
  } catch {
    // ignore
  }
  return 'fix_b_passes';
}

export function setActiveDemoScenarioId(id: DemoScenarioId): void {
  try {
    localStorage.setItem(DEMO_SCENARIO_KEY, id);
    window.dispatchEvent(new CustomEvent('litmus:demo-scenario-changed', { detail: { id } }));
  } catch {
    // ignore
  }
}

export function getActiveDemoScenario(): DemoScenarioConfig {
  const activeId = getActiveDemoScenarioId();
  return DEMO_SCENARIOS.find(s => s.id === activeId) ?? DEMO_SCENARIOS[0];
}

/**
 * Returns the realistic sample bug for the landing page "Try a sample bug" button.
 */
export function getSampleBug() {
  const scenario = getActiveDemoScenario();
  return {
    language: scenario.session.language,
    code: scenario.session.code || '',
    question: scenario.session.question,
    details: {
      failingTest: scenario.session.details?.failingTest || '',
      expectedBehavior: scenario.session.details?.expectedBehavior || '',
      errorMessage: scenario.session.details?.errorMessage || '',
    },
  };
}
