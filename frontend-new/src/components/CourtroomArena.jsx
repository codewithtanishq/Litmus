import React, { useState, useEffect, useRef } from 'react';
import { 
  Play, 
  FastForward, 
  RotateCcw, 
  CheckCircle2, 
  XCircle, 
  Clock, 
  Terminal, 
  Shield, 
  Scale, 
  Cpu, 
  FileText, 
  Code2, 
  AlertTriangle,
  ChevronRight,
  ExternalLink
} from 'lucide-react';
import { runSession, fastForwardSession, fetchSessionResult, connectSessionEventStream } from '../services/api';

export default function CourtroomArena({ session, onSelectResult }) {
  const [events, setEvents] = useState([]);
  const [currentStage, setCurrentStage] = useState('pending'); // 'analysis', 'prosecutor', 'defender', 'sandbox', 'judge', 'completed', 'error'
  const [candidateA, setCandidateA] = useState(null);
  const [candidateB, setCandidateB] = useState(null);
  const [sandboxA, setSandboxA] = useState(null);
  const [sandboxB, setSandboxB] = useState(null);
  const [judgeVerdict, setJudgeVerdict] = useState(null);
  const [activeCodeTab, setActiveCodeTab] = useState('diff'); // 'original', 'fix_a', 'fix_b', 'diff'
  const [isExecuting, setIsExecuting] = useState(false);
  const [executionError, setExecutionError] = useState(null);
  const [finalResult, setFinalResult] = useState(null);

  const logsEndRef = useRef(null);

  useEffect(() => {
    if (!session?.id) return;

    // Reset state for new session
    setEvents([]);
    setCurrentStage('pending');
    setCandidateA(null);
    setCandidateB(null);
    setSandboxA(null);
    setSandboxB(null);
    setJudgeVerdict(null);
    setExecutionError(null);
    setFinalResult(null);

    // Connect to SSE event stream
    setIsExecuting(true);
    const disconnect = connectSessionEventStream(
      session.id,
      (event) => {
        setEvents((prev) => [...prev, event]);
        processIncomingEvent(event);
      },
      (err) => {
        console.warn("EventStream connection notice:", err);
      },
      (completionData) => {
        setIsExecuting(false);
        if (completionData.type === 'completed' && completionData.payload?.result) {
          setFinalResult(completionData.payload.result);
        } else if (completionData.type === 'error') {
          setExecutionError(completionData.message || "Session error occurred");
        }
      }
    );

    return () => {
      disconnect();
    };
  }, [session?.id]);

  useEffect(() => {
    logsEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [events]);

  const processIncomingEvent = (event) => {
    switch (event.type) {
      case 'analysis_started':
        setCurrentStage('analysis');
        break;
      case 'root_cause_located':
        setCurrentStage('prosecutor');
        if (event.payload?.candidateA) {
          setCandidateA(event.payload.candidateA);
        }
        break;
      case 'fixes_compared':
        setCurrentStage('defender');
        if (event.payload?.candidateB) {
          setCandidateB(event.payload.candidateB);
        }
        break;
      case 'sandbox_started':
        setCurrentStage('sandbox');
        break;
      case 'sandbox_finished':
        setCurrentStage('sandbox_done');
        if (event.payload?.sandboxRunA) setSandboxA(event.payload.sandboxRunA);
        if (event.payload?.sandboxRunB) setSandboxB(event.payload.sandboxRunB);
        break;
      case 'judge_decision':
        setCurrentStage('judge');
        setJudgeVerdict(event.payload);
        break;
      case 'completed':
        setCurrentStage('completed');
        setIsExecuting(false);
        if (event.payload?.result) {
          setFinalResult(event.payload.result);
        }
        break;
      case 'error':
        setCurrentStage('error');
        setIsExecuting(false);
        setExecutionError(event.message);
        break;
      default:
        break;
    }
  };

  const handleRun = async () => {
    try {
      setIsExecuting(true);
      setExecutionError(null);
      await runSession(session.id);
    } catch (err) {
      setExecutionError(err.message);
      setIsExecuting(false);
    }
  };

  const handleFastForward = async () => {
    try {
      setIsExecuting(true);
      await fastForwardSession(session.id);
    } catch (err) {
      setExecutionError(err.message);
    }
  };

  const stageSteps = [
    { key: 'analysis', label: '1. AST Analysis', icon: Cpu },
    { key: 'prosecutor', label: '2. Prosecutor (Fix A)', icon: Scale },
    { key: 'defender', label: '3. Defender (Fix B)', icon: Shield },
    { key: 'sandbox', label: '4. Sandbox Run', icon: Terminal },
    { key: 'judge', label: '5. Judicial Ruling', icon: CheckCircle2 },
  ];

  const getStageIndex = (stage) => {
    if (stage === 'pending') return 0;
    if (stage === 'analysis') return 0;
    if (stage === 'prosecutor') return 1;
    if (stage === 'defender') return 2;
    if (stage === 'sandbox' || stage === 'sandbox_done') return 3;
    if (stage === 'judge' || stage === 'completed') return 4;
    return 0;
  };

  const activeStageIdx = getStageIndex(currentStage);

  return (
    <div className="space-y-6">
      {/* Top Banner / Session Info Card */}
      <div className="card-surface p-6">
        <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
          <div>
            <div className="flex items-center space-x-2.5 mb-1.5">
              <span className="text-xs px-2.5 py-0.5 rounded-full font-mono bg-[#EEEBFF] text-[#5F4DCB] border border-[#E1DDFA]">
                {session?.id || 'session-live'}
              </span>
              <span className={`text-xs px-2.5 py-0.5 rounded-full font-medium ${
                currentStage === 'completed'
                  ? 'bg-[#EDF7F2] text-[#2E7D5B] border border-[#BFE7D3]'
                  : currentStage === 'error'
                  ? 'bg-[#FDF2F2] text-[#D13438] border border-[#F9C6C7]'
                  : 'bg-[#EEEBFF] text-[#5F4DCB] border border-[#E1DDFA] animate-pulse'
              }`}>
                {currentStage === 'completed' ? 'Court Adjudicated' : currentStage === 'error' ? 'Trial Halted' : 'Court in Session'}
              </span>
            </div>
            <h2 className="text-xl font-semibold text-[#1E1856] tracking-tight">
              {session?.question || session?.title || 'Courtroom Debugging Trial'}
            </h2>
            <p className="text-xs text-[#6B6894] mt-1">
              Language: <span className="font-medium text-[#1E1856] capitalize">{session?.language || 'Python'}</span> • Mode: {session?.mode || 'code'} • Verified with isolated sandboxes
            </p>
          </div>

          {/* Action buttons */}
          <div className="flex items-center space-x-2.5">
            <button
              onClick={handleFastForward}
              disabled={!isExecuting}
              className="btn-pill btn-secondary text-xs px-3.5 py-2 flex items-center space-x-1.5 disabled:opacity-40"
              title="Fast forward simulated debate rounds"
            >
              <FastForward className="w-3.5 h-3.5" />
              <span>Fast-Forward</span>
            </button>

            <button
              onClick={handleRun}
              className="btn-pill btn-primary text-xs px-4 py-2 flex items-center space-x-1.5 shadow-sm"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              <span>Re-run Trial</span>
            </button>

            {finalResult && onSelectResult && (
              <button
                onClick={() => onSelectResult(finalResult)}
                className="btn-pill px-4 py-2 bg-[#221B6D] text-white hover:bg-[#3B2A9D] text-xs font-medium flex items-center space-x-1.5 transition-all shadow-sm"
              >
                <span>Full Verdict Proof</span>
                <ChevronRight className="w-3.5 h-3.5" />
              </button>
            )}
          </div>
        </div>

        {/* Stepper Progress bar */}
        <div className="mt-6 pt-5 border-t border-[#E1DDFA]">
          <div className="grid grid-cols-2 sm:grid-cols-5 gap-2">
            {stageSteps.map((step, idx) => {
              const StepIcon = step.icon;
              const isPast = idx < activeStageIdx || currentStage === 'completed';
              const isCurrent = idx === activeStageIdx && currentStage !== 'completed';

              return (
                <div
                  key={step.key}
                  className={`p-2.5 rounded-xl border transition-all ${
                    isCurrent
                      ? 'bg-[#EEEBFF] border-[#5F4DCB] shadow-sm'
                      : isPast
                      ? 'bg-white border-[#E1DDFA] text-[#1E1856]'
                      : 'bg-[#F6F5FF]/50 border-transparent text-[#6B6894]/60'
                  }`}
                >
                  <div className="flex items-center space-x-2">
                    <div className={`w-5 h-5 rounded-full flex items-center justify-center text-xs ${
                      isPast 
                        ? 'bg-[#EDF7F2] text-[#2E7D5B]' 
                        : isCurrent 
                        ? 'bg-[#5F4DCB] text-white' 
                        : 'bg-[#E1DDFA] text-[#6B6894]'
                    }`}>
                      {isPast ? <CheckCircle2 className="w-3.5 h-3.5" /> : idx + 1}
                    </div>
                    <span className="text-xs font-medium truncate">{step.label}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>

      {executionError && (
        <div className="p-4 rounded-xl bg-[#FDF2F2] border border-[#F9C6C7] text-[#D13438] text-xs flex items-start space-x-3">
          <AlertTriangle className="w-5 h-5 shrink-0 mt-0.5" />
          <div>
            <div className="font-semibold mb-0.5">Trial Pipeline Notice</div>
            <p className="leading-relaxed">{executionError}</p>
          </div>
        </div>
      )}

      {/* Main Split: Left Column (Debate Stages & Code) | Right Column (Courtroom Live Log) */}
      <div className="grid grid-cols-1 lg:grid-cols-12 gap-6">
        {/* Left Column: Candidates & Sandbox Execution Evidence */}
        <div className="lg:col-span-7 space-y-6">
          {/* Candidates Comparison Box */}
          <div className="card-surface p-6">
            <div className="flex items-center justify-between pb-3 border-b border-[#E1DDFA]">
              <div className="flex items-center space-x-2">
                <Code2 className="w-4 h-4 text-[#5F4DCB]" />
                <h3 className="text-sm font-semibold text-[#1E1856]">Adversarial Patch Proposals</h3>
              </div>

              {/* Tabs */}
              <div className="flex items-center space-x-1 bg-[#EEEBFF] p-1 rounded-full border border-[#E1DDFA]">
                <button
                  onClick={() => setActiveCodeTab('original')}
                  className={`text-xs px-3 py-1 rounded-full font-medium transition-all ${
                    activeCodeTab === 'original'
                      ? 'bg-white text-[#5F4DCB] shadow-xs'
                      : 'text-[#6B6894] hover:text-[#1E1856]'
                  }`}
                >
                  Original
                </button>
                <button
                  onClick={() => setActiveCodeTab('fix_a')}
                  className={`text-xs px-3 py-1 rounded-full font-medium transition-all ${
                    activeCodeTab === 'fix_a'
                      ? 'bg-white text-[#5F4DCB] shadow-xs'
                      : 'text-[#6B6894] hover:text-[#1E1856]'
                  }`}
                >
                  Fix A (Prosecutor)
                </button>
                <button
                  onClick={() => setActiveCodeTab('fix_b')}
                  className={`text-xs px-3 py-1 rounded-full font-medium transition-all ${
                    activeCodeTab === 'fix_b'
                      ? 'bg-white text-[#5F4DCB] shadow-xs'
                      : 'text-[#6B6894] hover:text-[#1E1856]'
                  }`}
                >
                  Fix B (Defender)
                </button>
              </div>
            </div>

            {/* Code Content */}
            <div className="mt-4">
              {activeCodeTab === 'original' && (
                <div>
                  <div className="text-xs text-[#6B6894] mb-2 font-mono">Original input submitted to court:</div>
                  <pre className="p-3.5 rounded-xl bg-[#221B6D] text-[#EEEBFF] font-mono text-xs overflow-x-auto border border-[#3B2A9D]">
                    {session?.code || "# No original code available"}
                  </pre>
                </div>
              )}

              {activeCodeTab === 'fix_a' && (
                <div>
                  <div className="flex items-center justify-between text-xs text-[#6B6894] mb-2">
                    <span className="font-semibold text-[#1E1856]">Prosecutor's Formulation:</span>
                    <span>{candidateA?.explanation || "Awaiting prosecutor node..."}</span>
                  </div>
                  <pre className="p-3.5 rounded-xl bg-[#221B6D] text-[#EEEBFF] font-mono text-xs overflow-x-auto border border-[#3B2A9D]">
                    {candidateA?.code || "# Prosecutor formulating candidate patch A..."}
                  </pre>
                </div>
              )}

              {activeCodeTab === 'fix_b' && (
                <div>
                  <div className="flex items-center justify-between text-xs text-[#6B6894] mb-2">
                    <span className="font-semibold text-[#1E1856]">Defender's Formulation:</span>
                    <span>{candidateB?.explanation || "Awaiting defender node..."}</span>
                  </div>
                  <pre className="p-3.5 rounded-xl bg-[#221B6D] text-[#EEEBFF] font-mono text-xs overflow-x-auto border border-[#3B2A9D]">
                    {candidateB?.code || "# Defender critiquing and formulating fix B..."}
                  </pre>
                </div>
              )}
            </div>
          </div>

          {/* Sandbox Execution Evidence Cards */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
            {/* Sandbox A */}
            <div className="card-surface p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-[#1E1856] flex items-center space-x-1.5">
                  <Terminal className="w-3.5 h-3.5 text-[#5F4DCB]" />
                  <span>Sandbox A (Prosecutor)</span>
                </span>
                {sandboxA && (
                  <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${
                    sandboxA.status === 'passed'
                      ? 'bg-[#EDF7F2] text-[#2E7D5B] border border-[#BFE7D3]'
                      : 'bg-[#FDF2F2] text-[#D13438] border border-[#F9C6C7]'
                  }`}>
                    {sandboxA.status === 'passed' ? 'Passed (0 Regressions)' : 'Failed (Exit Code 1)'}
                  </span>
                )}
              </div>
              <p className="text-[11px] text-[#6B6894] mb-2">Isolated execution runner with deterministic test suite</p>
              <pre className="p-2.5 rounded-lg bg-[#EEEBFF]/50 border border-[#E1DDFA] text-[11px] font-mono text-[#1E1856] max-h-28 overflow-y-auto">
                {sandboxA ? sandboxA.logs : "Waiting for sandbox dispatch..."}
              </pre>
            </div>

            {/* Sandbox B */}
            <div className="card-surface p-4">
              <div className="flex items-center justify-between mb-2">
                <span className="text-xs font-semibold text-[#1E1856] flex items-center space-x-1.5">
                  <Terminal className="w-3.5 h-3.5 text-[#5F4DCB]" />
                  <span>Sandbox B (Defender)</span>
                </span>
                {sandboxB && (
                  <span className={`text-[11px] font-medium px-2 py-0.5 rounded-full ${
                    sandboxB.status === 'passed'
                      ? 'bg-[#EDF7F2] text-[#2E7D5B] border border-[#BFE7D3]'
                      : 'bg-[#FDF2F2] text-[#D13438] border border-[#F9C6C7]'
                  }`}>
                    {sandboxB.status === 'passed' ? 'Passed (4/4 Tests)' : 'Failed'}
                  </span>
                )}
              </div>
              <p className="text-[11px] text-[#6B6894] mb-2">Isolated execution runner with boundary test assertions</p>
              <pre className="p-2.5 rounded-lg bg-[#EEEBFF]/50 border border-[#E1DDFA] text-[11px] font-mono text-[#1E1856] max-h-28 overflow-y-auto">
                {sandboxB ? sandboxB.logs : "Waiting for sandbox dispatch..."}
              </pre>
            </div>
          </div>

          {/* Judge Verdict Card (if reached) */}
          {judgeVerdict && (
            <div className="card-surface p-5 border-l-4 border-l-[#5F4DCB]">
              <div className="flex items-center space-x-2 text-[#5F4DCB] mb-2">
                <Scale className="w-4 h-4" />
                <h4 className="text-sm font-semibold text-[#1E1856]">
                  Judicial Verdict Decree: {judgeVerdict.verdict?.replace('_', ' ').toUpperCase()}
                </h4>
              </div>
              <p className="text-xs text-[#6B6894] leading-relaxed mb-3">
                {judgeVerdict.rationale}
              </p>
              {judgeVerdict.evidence && (
                <div className="space-y-1">
                  <div className="text-[11px] font-medium text-[#1E1856]">Empirical Evidence:</div>
                  {judgeVerdict.evidence.map((ev, i) => (
                    <div key={i} className="text-xs text-[#2E7D5B] flex items-center space-x-1.5">
                      <CheckCircle2 className="w-3 h-3 shrink-0" />
                      <span>{ev}</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

        {/* Right Column: Courtroom Debate Event Stream */}
        <div className="lg:col-span-5">
          <div className="card-surface p-5 flex flex-col h-[560px]">
            <div className="flex items-center justify-between pb-3 border-b border-[#E1DDFA]">
              <div className="flex items-center space-x-2">
                <Terminal className="w-4 h-4 text-[#5F4DCB]" />
                <h3 className="text-sm font-semibold text-[#1E1856]">Live Trial Event Log</h3>
              </div>
              <span className="text-[11px] text-[#6B6894] font-mono">
                {events.length} events
              </span>
            </div>

            {/* Scrollable event list */}
            <div className="flex-1 overflow-y-auto mt-3 space-y-3 pr-1">
              {events.length === 0 ? (
                <div className="h-full flex flex-col items-center justify-center text-center text-[#6B6894] text-xs p-6">
                  <Clock className="w-6 h-6 mb-2 text-[#C5C4F2] animate-spin" />
                  <span>Connecting to courtroom SSE feed...</span>
                </div>
              ) : (
                events.map((evt, idx) => {
                  const isAgent = evt.agent === 'prosecutor' || evt.agent === 'defender' || evt.agent === 'judge';
                  return (
                    <div
                      key={idx}
                      className="p-3 rounded-xl bg-[#F6F5FF] border border-[#E1DDFA] text-xs space-y-1 animate-fadeIn"
                    >
                      <div className="flex items-center justify-between text-[11px]">
                        <span className="font-semibold capitalize text-[#1E1856] flex items-center space-x-1.5">
                          {evt.agent === 'prosecutor' && <Scale className="w-3.5 h-3.5 text-[#5F4DCB]" />}
                          {evt.agent === 'defender' && <Shield className="w-3.5 h-3.5 text-[#3B2A9D]" />}
                          {evt.agent === 'judge' && <CheckCircle2 className="w-3.5 h-3.5 text-[#2E7D5B]" />}
                          <span>{evt.agent || 'System'}</span>
                        </span>
                        <span className="text-[#6B6894] font-mono text-[10px]">
                          {evt.timestamp ? new Date(evt.timestamp).toLocaleTimeString() : ''}
                        </span>
                      </div>
                      <p className="text-[#1E1856] font-normal leading-relaxed">
                        {evt.message}
                      </p>
                    </div>
                  );
                })
              )}
              <div ref={logsEndRef} />
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}
