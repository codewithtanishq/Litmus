import { useState, useEffect, useRef, useTransition } from 'react';
import { useLocation, useNavigate, Link } from 'react-router-dom';
import type { 
  Session, 
  FinalResult, 
  DebugEvent, 
  Round
} from '../types/litmus';
import { debugService } from '../services/debugService';
import { getCurrentSession } from '../services/sessionStore';
import { getActiveDemoScenario, type DemoScenarioId } from '../demo/demoState';
import { FixedPanel } from '../components/battle/FixedPanel';
import { StageHero } from '../components/battle/StageHero';
import { EventTimeline } from '../components/battle/EventTimeline';
import { CodeHighlighter } from '../components/battle/CodeHighlighter';
import { ProsecutorCard, DefenderCard, JudgeCard } from '../components/battle/AgentCard';
import { SandboxPanel } from '../components/battle/SandboxPanel';
import { RoundHistory } from '../components/battle/RoundHistory';
import { DemoBadge } from '../components/common/DemoBadge';
import type { ChessPieceType } from '../components/battle/ChessPiece';
import { 
  Hourglass, 
  ArrowLeft, 
  RotateCcw, 
  ChevronDown, 
  ChevronUp, 
  FileText, 
  GitBranch, 
  ExternalLink, 
  AlertTriangle, 
  XCircle, 
  HelpCircle,
  MessagesSquare,
  Cpu,
  Layers
} from 'lucide-react';
import './BattlePage.css';

export const BattlePage = () => {
  const location = useLocation();
  const navigate = useNavigate();
  const [, startTransition] = useTransition();

  // 1. Session and Result Data State
  const [session, setSession] = useState<Session | null>(null);
  const [result, setResult] = useState<FinalResult | null>(null);
  const [isLoadingSession, setIsLoadingSession] = useState(true);

  // 2. Real-time Event Stream and Stage Progression
  const [events, setEvents] = useState<DebugEvent[]>([]);
  const [currentPiece, setCurrentPiece] = useState<ChessPieceType>('pawn');
  const [stepIndex, setStepIndex] = useState(0); // 0 to 4
  const [statusMessage, setStatusMessage] = useState('Analyzing uploaded code');
  const [currentRoundNumber, setCurrentRoundNumber] = useState(1);
  const [isCompleted, setIsCompleted] = useState(false);
  const [terminalState, setTerminalState] = useState<{
    status: 'unresolved' | 'execution_inconclusive' | 'error';
    title: string;
    description: string;
  } | null>(null);

  // 3. Unlocked role milestones mapped strictly to real events
  const [unlockedRoles, setUnlockedRoles] = useState({
    prosecutor: false,
    defender: false,
    sandboxStarted: false,
    sandboxFinished: false,
    judgeRound1: false,
    judgeRound2: false,
  });

  // 4. Active Right Panel Tab ('debate' | 'sandboxes' | 'rounds')
  const [activeTab, setActiveTab] = useState<'debate' | 'sandboxes' | 'rounds'>('debate');

  // 5. Left Panel Collapsible Details
  const [collapseState, setCollapseState] = useState({
    failingTest: true,
    expectedBehavior: true,
    errorMessage: true,
  });

    // Keep track of unsubscribe handler
  const unsubscribeRef = useRef<(() => void) | null>(null);
  const [runCount, setRunCount] = useState(0);

  // Lifecycle effect: loads session, result, and initiates event stream
  useEffect(() => {
    let isCancelled = false;

    // Event dispatch router mapped strictly to prompt specifications
    const handleIncomingEvent = (event: DebugEvent, res: FinalResult | null) => {
      setEvents(prev => [...prev, event]);

      switch (event.type) {
        case 'analysis_started':
          setCurrentPiece('pawn');
          setStepIndex(0);
          setStatusMessage('Analyzing uploaded code');
          break;

        case 'root_cause_located':
          setCurrentPiece('knight');
          setStepIndex(1);
          setStatusMessage('Locating the root cause');
          setUnlockedRoles(prev => ({ ...prev, prosecutor: true }));
          break;

        case 'round_started':
          if (event.roundNumber && event.roundNumber > 1) {
            // For round 2+, show "Round N" badge and restart progression from Knight
            setCurrentRoundNumber(event.roundNumber);
            setCurrentPiece('knight');
            setStepIndex(1);
            setStatusMessage('Locating the root cause (Round 2 synthesis)');
          }
          break;

        case 'fixes_compared':
          setCurrentPiece('bishop');
          setStepIndex(2);
          setStatusMessage('Comparing possible fixes');
          setUnlockedRoles(prev => ({ ...prev, defender: true }));
          break;

        case 'sandbox_started':
          setCurrentPiece('rook');
          setStepIndex(3);
          setStatusMessage('Reviewing affected lines and running sandboxes');
          setUnlockedRoles(prev => ({ ...prev, sandboxStarted: true }));
          break;

        case 'sandbox_finished':
          setCurrentPiece('rook');
          setStepIndex(3);
          setStatusMessage('Reviewing affected lines and running sandboxes');
          setUnlockedRoles(prev => ({ ...prev, sandboxFinished: true }));
          break;

        case 'judge_decision':
          setCurrentPiece('queen');
          setStepIndex(4);
          setStatusMessage('Validating the proposed correction');
          if (event.roundNumber === 2) {
            setUnlockedRoles(prev => ({ ...prev, judgeRound2: true }));
          } else {
            setUnlockedRoles(prev => ({ ...prev, judgeRound1: true }));
          }
          break;

        case 'completed': {
          setIsCompleted(true);
          // Genuine terminal event arrived from service layer
          const finalStatus = res?.status || 'test_verified';

          if (finalStatus === 'test_verified') {
            // Terminal verified: Navigate to /checkmate when genuine completed event arrives
            startTransition(() => {
              navigate('/checkmate', { state: { sessionId: event.sessionId } });
            });
          } else if (finalStatus === 'unresolved') {
            // Terminal unresolved: Stay on arena with clear banner & Retry / Home
            setTerminalState({
              status: 'unresolved',
              title: 'Adjudication Complete: Bug Unresolved (Round 2 Escalation Exhausted)',
              description: 'Both adversarial candidate patches introduced secondary test regressions in sandboxes. Automated resolution was halted to protect code safety.',
            });
          } else if (finalStatus === 'execution_inconclusive') {
            // Terminal inconclusive (watchdog timeout): Stay on arena
            setTerminalState({
              status: 'execution_inconclusive',
              title: 'Adjudication Complete: Watchdog Timeout (Inconclusive Execution)',
              description: 'Candidate A sandbox container exceeded 30000ms wall-clock safety threshold. Per litmus governance, timeout is recorded as execution_inconclusive — NOT classified as a defective patch.',
            });
          }
          break;
        }

        case 'error':
          setTerminalState({
            status: 'error',
            title: 'Adjudication Pipeline Error',
            description: event.message || 'An error occurred during sandbox evaluation.',
          });
          break;
      }
    };

    const loadAndSubscribe = async () => {
      setEvents([]);
      setTerminalState(null);
      setIsCompleted(false);
      setCurrentPiece('pawn');
      setStepIndex(0);
      setStatusMessage('Analyzing uploaded code');
      setCurrentRoundNumber(1);
      setUnlockedRoles({
        prosecutor: false,
        defender: false,
        sandboxStarted: false,
        sandboxFinished: false,
        judgeRound1: false,
        judgeRound2: false,
      });

      const locationSessionId = (location.state as { sessionId?: string })?.sessionId;
      let activeSession = locationSessionId ? await debugService.getSession(locationSessionId) : null;

      if (!activeSession) {
        activeSession = getCurrentSession();
      }

      if (!activeSession) {
        const demoScenario = getActiveDemoScenario();
        if (demoScenario?.session) {
          activeSession = demoScenario.session;
        }
      }

      if (isCancelled) return;

      if (!activeSession) {
        setIsLoadingSession(false);
        return;
      }

      setSession(activeSession);
      const res = await debugService.getResult(activeSession.id);
      if (isCancelled) return;

      setResult(res);
      setIsLoadingSession(false);

      if (unsubscribeRef.current) {
        unsubscribeRef.current();
        unsubscribeRef.current = null;
      }

      const unsub = debugService.subscribeToEvents(activeSession.id, (event: DebugEvent) => {
        if (!isCancelled) {
          handleIncomingEvent(event, res);
        }
      });
      unsubscribeRef.current = unsub;
    };

    void loadAndSubscribe();

    const handleScenarioChange = (e: Event) => {
      const customEvent = e as CustomEvent<{ id: DemoScenarioId }>;
      if (customEvent.detail?.id) {
        setRunCount(c => c + 1);
      }
    };

    window.addEventListener('litmus:demo-scenario-changed', handleScenarioChange);

    return () => {
      isCancelled = true;
      window.removeEventListener('litmus:demo-scenario-changed', handleScenarioChange);
      if (unsubscribeRef.current) {
        unsubscribeRef.current();
        unsubscribeRef.current = null;
      }
    };
  }, [location.state, runCount, navigate]);

  // Handler: Skip Animation
  const handleSkipAnimation = () => {
    if (!session || isCompleted) return;
    debugService.fastForward(session.id);
  };

  // Handler: Retry Terminal Run
  const handleRetry = () => {
    setRunCount(c => c + 1);
  };

  // Extract session details safely
  const originalCode = session?.code || session?.fileContent || '';
  const currentRound: Round | undefined = result?.rounds?.[currentRoundNumber - 1] || result?.rounds?.[0];
  const round1: Round | undefined = result?.rounds?.[0];
  const round2: Round | undefined = result?.rounds?.[1];

  // If session data is missing or corrupt (e.g. direct visit with cleared storage)
  if (!isLoadingSession && !session) {
    return (
      <main className="litmus-battle-page litmus-battle-page--empty" id="main-content">
        <div className="battle-empty-card">
          <div className="battle-empty-card__header">
            <AlertTriangle size={24} className="battle-empty-card__icon" />
            <h2>No Active Debugging Session Found</h2>
          </div>
          <p className="battle-empty-card__desc">
            Session data is missing or has expired. Please select a sample bug or submit your reproducible code from the dashboard.
          </p>
          <div className="battle-empty-card__actions">
            <Link to="/" className="battle-empty-btn battle-empty-btn--primary">
              <ArrowLeft size={16} />
              <span>Back to Dashboard</span>
            </Link>
          </div>
        </div>
      </main>
    );
  }

  return (
    <main className="litmus-battle-page" id="main-content">
      {/* Top Bar Strip: DEMO MODE Badge + Back Link */}
      <div className="litmus-battle-topstrip">
        <div className="battle-topstrip-left">
          <Link to="/" className="battle-back-link" title="Return to Dashboard">
            <ArrowLeft size={15} />
            <span>Dashboard</span>
          </Link>
          <span className="battle-topstrip-divider" aria-hidden="true">/</span>
          <span className="battle-topstrip-title">Debug Arena: {session?.title || 'Adversarial Debate'}</span>
        </div>

        <div className="battle-topstrip-right">
          <DemoBadge />
        </div>
      </div>

      {/* Terminal Error / Inconclusive Banner (stays on the arena as required) */}
      {terminalState && (
        <section 
          className={`litmus-terminal-banner litmus-terminal-banner--${terminalState.status}`}
          role="alert"
          aria-live="assertive"
        >
          <div className="terminal-banner__left">
            {terminalState.status === 'unresolved' && <XCircle size={22} className="terminal-banner__icon" />}
            {terminalState.status === 'execution_inconclusive' && <HelpCircle size={22} className="terminal-banner__icon" />}
            {terminalState.status === 'error' && <AlertTriangle size={22} className="terminal-banner__icon" />}

            <div className="terminal-banner__content">
              <h3 className="terminal-banner__title">{terminalState.title}</h3>
              <p className="terminal-banner__desc">{terminalState.description}</p>
            </div>
          </div>

          <div className="terminal-banner__actions">
            <button
              type="button"
              className="terminal-btn terminal-btn--retry"
              onClick={handleRetry}
              aria-label="Retry debugging session"
            >
              <RotateCcw size={14} />
              <span>Retry Session</span>
            </button>
            <button
              type="button"
              className="terminal-btn terminal-btn--home"
              onClick={() => navigate('/')}
              aria-label="Back to home dashboard"
            >
              <ArrowLeft size={14} />
              <span>Back to Home</span>
            </button>
          </div>
        </section>
      )}

      {/* MAIN TWO-PANEL ARENA LAYOUT */}
      <div className="litmus-arena-layout">
        {/* ======================================================== */}
        {/* LEFT PANEL: "UPLOADED QUERY" (Fixed width & height, Charcoal) */}
        {/* ======================================================== */}
        <FixedPanel
          title="UPLOADED QUERY"
          subtitle={session?.id ? `Session ID: ${session.id}` : undefined}
          variant="charcoal"
          className="litmus-arena-panel litmus-arena-panel--left"
          bodyClassName="litmus-query-panel-body"
          badge={
            <span className="litmus-mode-badge">
              {session?.mode?.toUpperCase() || 'CODE'}
            </span>
          }
        >
          {/* Question / Bug description */}
          <div className="query-section">
            <h3 className="query-section-heading">Observed Defect / Question</h3>
            <div className="query-question-box">
              <p className="query-question-text">{session?.question}</p>
            </div>
          </div>

          {/* Mode 1: Upload Code */}
          {session?.mode === 'code' && (
            <>
              <div className="query-section">
                <div className="query-section-header-row">
                  <h3 className="query-section-heading">Buggy Source Code</h3>
                  <span className="query-lang-tag">{session.language || 'python'}</span>
                </div>
                {/* Scrollable line-numbered code viewer; never truncated */}
                <CodeHighlighter
                  code={session.code || ''}
                  language={session.language || 'python'}
                  maxHeight="320px"
                  ariaLabel="Uploaded buggy code"
                />
              </div>

              {/* Collapsible Section: Failing Test */}
              {session.details?.failingTest && (
                <div className="query-collapsible-section">
                  <button
                    type="button"
                    className="query-collapsible-trigger"
                    onClick={() => setCollapseState(p => ({ ...p, failingTest: !p.failingTest }))}
                    aria-expanded={collapseState.failingTest}
                  >
                    <span>Failing Test Vector</span>
                    {collapseState.failingTest ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                  </button>
                  {collapseState.failingTest && (
                    <div className="query-collapsible-content">
                      <CodeHighlighter
                        code={session.details.failingTest}
                        language={session.language || 'python'}
                        maxHeight="220px"
                        ariaLabel="Failing test vector code"
                      />
                    </div>
                  )}
                </div>
              )}

              {/* Collapsible Section: Expected Behavior */}
              {session.details?.expectedBehavior && (
                <div className="query-collapsible-section">
                  <button
                    type="button"
                    className="query-collapsible-trigger"
                    onClick={() => setCollapseState(p => ({ ...p, expectedBehavior: !p.expectedBehavior }))}
                    aria-expanded={collapseState.expectedBehavior}
                  >
                    <span>Expected Invariant</span>
                    {collapseState.expectedBehavior ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                  </button>
                  {collapseState.expectedBehavior && (
                    <div className="query-collapsible-content">
                      <p className="query-plain-box">{session.details.expectedBehavior}</p>
                    </div>
                  )}
                </div>
              )}

              {/* Collapsible Section: Error Message */}
              {session.details?.errorMessage && (
                <div className="query-collapsible-section">
                  <button
                    type="button"
                    className="query-collapsible-trigger"
                    onClick={() => setCollapseState(p => ({ ...p, errorMessage: !p.errorMessage }))}
                    aria-expanded={collapseState.errorMessage}
                  >
                    <span>Error Output / Stack Trace</span>
                    {collapseState.errorMessage ? <ChevronUp size={15} /> : <ChevronDown size={15} />}
                  </button>
                  {collapseState.errorMessage && (
                    <div className="query-collapsible-content">
                      <pre className="query-terminal-box">
                        <code>{session.details.errorMessage}</code>
                      </pre>
                    </div>
                  )}
                </div>
              )}
            </>
          )}

          {/* Mode 2: Upload File */}
          {session?.mode === 'file' && (
            <div className="query-section">
              <h3 className="query-section-heading">Uploaded File Artifact</h3>
              <div className="query-file-card">
                <FileText size={20} className="query-file-icon" />
                <div className="query-file-info">
                  <strong className="query-file-name">{session.fileName || 'source_file'}</strong>
                  <span className="query-file-size">
                    {session.fileSize ? `${Math.round(session.fileSize / 1024)} KB` : 'Local artifact'}
                  </span>
                </div>
              </div>

              {session.fileContent && (
                <div style={{ marginTop: '14px' }}>
                  <h4 className="query-section-heading">Parsed Contents</h4>
                  <CodeHighlighter
                    code={session.fileContent}
                    language={session.language || 'text'}
                    maxHeight="340px"
                    ariaLabel="Parsed file text contents"
                  />
                </div>
              )}
            </div>
          )}

          {/* Mode 3: GitHub Repo */}
          {session?.mode === 'repo' && (
            <div className="query-section">
              <h3 className="query-section-heading">GitHub Repository Scope</h3>
              <div className="query-repo-card">
                <GitBranch size={18} className="query-repo-icon" />
                <a 
                  href={session.repoUrl} 
                  target="_blank" 
                  rel="noreferrer" 
                  className="query-repo-link"
                >
                  <span>{session.repoUrl}</span>
                  <ExternalLink size={13} />
                </a>
              </div>

              <div className="query-repo-status">
                <span className="query-repo-not-retrieved">
                  Repository contents: Offline Mock Environment. (Files not retrieved).
                </span>
                <p className="query-repo-hint">
                  Use "Upload Code" or "Upload File" to test full adversarial execution suites in isolated sandboxes.
                </p>
              </div>
            </div>
          )}
        </FixedPanel>

        {/* ======================================================== */}
        {/* RIGHT PANEL: "JUDGE AGENT" (Fills width, balanced height) */}
        {/* ======================================================== */}
        <FixedPanel
          title="JUDGE AGENT"
          subtitle="Empirical Adjudication & Multi-Agent Reasoning"
          variant="arena"
          className="litmus-arena-panel litmus-arena-panel--right"
          bodyClassName="litmus-judge-panel-body"
          badge={
            <span className="litmus-arena-badge">
              {currentRoundNumber > 1 ? `ROUND ${currentRoundNumber}` : 'ROUND 1'}
            </span>
          }
        >
          {/* A) STAGE HERO (Pawn -> Knight -> Bishop -> Rook -> Queen) */}
          <StageHero
            currentPiece={currentPiece}
            statusMessage={statusMessage}
            roundNumber={currentRoundNumber}
            stepIndex={stepIndex}
            onSkipAnimation={handleSkipAnimation}
            isCompleted={isCompleted}
          />

          {/* B) COMPACT EVENT TIMELINE / ACTIVITY STRIP */}
          <EventTimeline events={events} />

          {/* C) TABS: "Debate", "Sandboxes", "Rounds" */}
          <div className="litmus-arena-tabs-container">
            <div className="litmus-arena-tabs" role="tablist" aria-label="Adjudication Arena Views">
              <button
                type="button"
                role="tab"
                aria-selected={activeTab === 'debate'}
                className={`litmus-arena-tab ${activeTab === 'debate' ? 'litmus-arena-tab--active' : ''}`}
                onClick={() => setActiveTab('debate')}
              >
                <MessagesSquare size={16} />
                <span>Debate</span>
                {unlockedRoles.prosecutor && (
                  <span className="arena-tab-badge arena-tab-badge--active">Active</span>
                )}
              </button>

              <button
                type="button"
                role="tab"
                aria-selected={activeTab === 'sandboxes'}
                className={`litmus-arena-tab ${activeTab === 'sandboxes' ? 'litmus-arena-tab--active' : ''}`}
                onClick={() => setActiveTab('sandboxes')}
              >
                <Cpu size={16} />
                <span>Sandboxes</span>
                {unlockedRoles.sandboxStarted && (
                  <span className="arena-tab-badge arena-tab-badge--running">
                    {unlockedRoles.sandboxFinished ? 'Complete' : 'Running'}
                  </span>
                )}
              </button>

              <button
                type="button"
                role="tab"
                aria-selected={activeTab === 'rounds'}
                className={`litmus-arena-tab ${activeTab === 'rounds' ? 'litmus-arena-tab--active' : ''}`}
                onClick={() => setActiveTab('rounds')}
              >
                <Layers size={16} />
                <span>Rounds</span>
                <span className="arena-tab-badge">
                  {result?.rounds?.length || 1}
                </span>
              </button>
            </div>

            {/* TAB CONTENT 1: DEBATE */}
            {activeTab === 'debate' && (
              <div className="litmus-tab-pane litmus-tab-pane--debate" role="tabpanel">
                {/* 1. Prosecutor Card */}
                {unlockedRoles.prosecutor && currentRound?.candidateA ? (
                  <ProsecutorCard
                    claim={currentRound.prosecutorClaim}
                    candidateA={currentRound.candidateA}
                    originalCode={originalCode}
                    timestamp={events.find(e => e.type === 'root_cause_located')?.timestamp}
                  />
                ) : (
                  <div className="role-card-placeholder">
                    <Hourglass size={18} className="role-placeholder-icon" />
                    <span>Awaiting Prosecutor hypothesis formulation...</span>
                  </div>
                )}

                {/* 2. Defender Card */}
                {unlockedRoles.defender && currentRound?.candidateB ? (
                  <DefenderCard
                    challenge={currentRound.defenderChallenge}
                    objectionText={
                      currentRoundNumber === 1
                        ? 'Fix A introduces boundary regression or unhandled concurrency invariant.'
                        : 'Fix A fails exception propagation invariants; Key-level events trigger unhandled KeyError.'
                    }
                    candidateA={currentRound.candidateA}
                    candidateB={currentRound.candidateB}
                    originalCode={originalCode}
                    timestamp={events.find(e => e.type === 'fixes_compared')?.timestamp}
                  />
                ) : (
                  <div className="role-card-placeholder">
                    <Hourglass size={18} className="role-placeholder-icon" />
                    <span>Awaiting Defender counter-analysis and Fix B synthesis...</span>
                  </div>
                )}

                {/* 3. Judge Card */}
                {unlockedRoles.judgeRound1 && currentRound?.decision ? (
                  <JudgeCard
                    decision={
                      currentRoundNumber === 2 && round2?.decision
                        ? round2.decision
                        : round1?.decision || currentRound.decision
                    }
                    roundNumber={currentRoundNumber}
                  />
                ) : (
                  <div className="role-card-placeholder">
                    <Hourglass size={18} className="role-placeholder-icon" />
                    <span>Awaiting sandbox runs before Judge formal adjudication...</span>
                  </div>
                )}
              </div>
            )}

            {/* TAB CONTENT 2: SANDBOXES */}
            {activeTab === 'sandboxes' && (
              <div className="litmus-tab-pane litmus-tab-pane--sandboxes" role="tabpanel">
                <div className="sandboxes-grid">
                  {/* Sandbox A (Fix A) */}
                  <SandboxPanel
                    id="fix_a"
                    label="Sandbox A (Fix A)"
                    candidate={currentRound?.candidateA}
                    isSimulating={unlockedRoles.sandboxStarted && !unlockedRoles.sandboxFinished}
                  />

                  {/* Sandbox B (Fix B) */}
                  <SandboxPanel
                    id="fix_b"
                    label="Sandbox B (Fix B)"
                    candidate={currentRound?.candidateB}
                    isSimulating={unlockedRoles.sandboxStarted && !unlockedRoles.sandboxFinished}
                  />
                </div>
              </div>
            )}

            {/* TAB CONTENT 3: ROUNDS */}
            {activeTab === 'rounds' && (
              <div className="litmus-tab-pane litmus-tab-pane--rounds" role="tabpanel">
                <RoundHistory
                  rounds={result?.rounds || []}
                  rejectedAttempts={result?.rejectedAttempts || []}
                  originalCode={originalCode}
                  currentActiveRound={currentRoundNumber}
                />
              </div>
            )}
          </div>
        </FixedPanel>
      </div>
    </main>
  );
};
