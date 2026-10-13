import { useState } from 'react';
import type { Round, RejectedAttempt } from '../../types/litmus';
import { RejectionMemory } from './RejectionMemory';
import { 
  GitBranch, 
  CheckCircle2, 
  XCircle, 
  Clock, 
  ArrowRight,
  ShieldCheck,
  AlertTriangle 
} from 'lucide-react';
import { formatMeasured } from '../../types/litmus';
import './RoundHistory.css';

interface RoundHistoryProps {
  rounds: Round[];
  rejectedAttempts: RejectedAttempt[];
  originalCode: string;
  currentActiveRound?: number;
  className?: string;
}

export const RoundHistory = ({
  rounds,
  rejectedAttempts,
  currentActiveRound = 1,
  className = '',
}: RoundHistoryProps) => {
  const [selectedRoundNum, setSelectedRoundNum] = useState<number>(
    rounds.length > 0 ? rounds[rounds.length - 1].roundNumber : 1
  );

  const activeRound = rounds.find(r => r.roundNumber === selectedRoundNum) || rounds[0];

  const getVerdictChip = (verdict: string) => {
    switch (verdict) {
      case 'fix_b_selected':
        return <span className="round-verdict-chip round-verdict-chip--pass"><CheckCircle2 size={13} /> Fix B Selected</span>;
      case 'fix_a_selected':
        return <span className="round-verdict-chip round-verdict-chip--pass"><CheckCircle2 size={13} /> Fix A Selected</span>;
      case 'both_failed':
        return <span className="round-verdict-chip round-verdict-chip--fail"><XCircle size={13} /> Both Failed (Round Escalated)</span>;
      case 'inconclusive':
        return <span className="round-verdict-chip round-verdict-chip--warn"><Clock size={13} /> Watchdog Inconclusive</span>;
      default:
        return <span className="round-verdict-chip">{verdict}</span>;
    }
  };

  return (
    <div className={`litmus-round-history ${className}`} role="region" aria-label="Round progression history">
      {/* Stepper Header */}
      <div className="litmus-round-stepper">
        <div className="litmus-round-stepper__title-row">
          <GitBranch size={16} className="round-stepper-icon" />
          <h3 className="litmus-round-stepper__title">Adversarial Rounds Stepper</h3>
        </div>

        <div className="litmus-round-tabs" role="tablist" aria-label="Rounds selection">
          {rounds.map((round) => {
            const isSelected = round.roundNumber === selectedRoundNum;
            const isLive = round.roundNumber === currentActiveRound;

            return (
              <button
                key={round.roundNumber}
                type="button"
                role="tab"
                aria-selected={isSelected}
                className={`litmus-round-tab ${isSelected ? 'litmus-round-tab--active' : ''}`}
                onClick={() => setSelectedRoundNum(round.roundNumber)}
              >
                <span>Round {round.roundNumber}</span>
                {isLive && <span className="round-tab-live-dot" title="Active debate round" />}
              </button>
            );
          })}
        </div>
      </div>

      {activeRound ? (
        <div className="litmus-round-detail">
          {/* Round Meta Banner */}
          <div className="litmus-round-meta-banner">
            <div className="round-meta-badge">ROUND {activeRound.roundNumber} DEBATE TRACE</div>
            <div className="round-meta-verdict">
              {getVerdictChip(activeRound.decision.verdict)}
            </div>
          </div>

          {/* Adversarial Hypotheses Comparison */}
          <div className="litmus-round-hypotheses-grid">
            <div className="round-hypo-box round-hypo-box--prosecutor">
              <span className="round-hypo-tag round-hypo-tag--prosecutor">PROSECUTOR CLAIM</span>
              <p className="round-hypo-text">{activeRound.prosecutorClaim}</p>
              <div className="round-fix-preview">
                <strong>Fix A:</strong> {activeRound.candidateA.title}
              </div>
            </div>

            <div className="round-hypo-box round-hypo-box--defender">
              <span className="round-hypo-tag round-hypo-tag--defender">DEFENDER CHALLENGE</span>
              <p className="round-hypo-text">{activeRound.defenderChallenge}</p>
              <div className="round-fix-preview">
                <strong>Fix B:</strong> {activeRound.candidateB.title}
              </div>
            </div>
          </div>

          {/* Sandbox Outcomes Comparison Matrix */}
          <div className="litmus-round-sandbox-matrix">
            <h4 className="sandbox-matrix-title">SANDBOX EXECUTION MATRIX</h4>
            <div className="sandbox-matrix-cards">
              {/* Fix A Sandbox */}
              <div className="sandbox-matrix-card">
                <div className="matrix-card-header">
                  <span className="matrix-card-title">Sandbox A (Fix A)</span>
                  <span className={`matrix-status-pill matrix-status-pill--${activeRound.candidateA.sandboxRun?.status}`}>
                    {activeRound.candidateA.sandboxRun?.status === 'passed' ? 'PASSED' :
                     activeRound.candidateA.sandboxRun?.status === 'timed_out' ? 'TIMED OUT' : 'FAILED'}
                  </span>
                </div>
                <div className="matrix-stats-row">
                  <span>Passed: <strong>{formatMeasured(activeRound.candidateA.sandboxRun?.passed)}</strong></span>
                  <span>Failed: <strong>{formatMeasured(activeRound.candidateA.sandboxRun?.failed)}</strong></span>
                  <span>Exit: <strong>{activeRound.candidateA.sandboxRun?.exitCode ?? 'Not measured'}</strong></span>
                </div>
              </div>

              {/* Fix B Sandbox */}
              <div className="sandbox-matrix-card">
                <div className="matrix-card-header">
                  <span className="matrix-card-title">Sandbox B (Fix B)</span>
                  <span className={`matrix-status-pill matrix-status-pill--${activeRound.candidateB.sandboxRun?.status}`}>
                    {activeRound.candidateB.sandboxRun?.status === 'passed' ? 'PASSED' :
                     activeRound.candidateB.sandboxRun?.status === 'timed_out' ? 'TIMED OUT' : 'FAILED'}
                  </span>
                </div>
                <div className="matrix-stats-row">
                  <span>Passed: <strong>{formatMeasured(activeRound.candidateB.sandboxRun?.passed)}</strong></span>
                  <span>Failed: <strong>{formatMeasured(activeRound.candidateB.sandboxRun?.failed)}</strong></span>
                  <span>Exit: <strong>{activeRound.candidateB.sandboxRun?.exitCode ?? 'Not measured'}</strong></span>
                </div>
              </div>
            </div>
          </div>

          {/* Judge Decision & Evidence in Round */}
          <div className="litmus-round-decision-box">
            <h4 className="round-decision-title">
              <ShieldCheck size={16} />
              JUDGE ADJUDICATION & RATIONALE
            </h4>
            <p className="round-decision-text">
              {activeRound.decision.rationale}
            </p>
            <ul className="round-evidence-list">
              {activeRound.decision.evidence.map((ev, eIdx) => (
                <li key={eIdx} className="round-evidence-item">
                  <span className="round-evidence-dot" aria-hidden="true" />
                  <span>{ev}</span>
                </li>
              ))}
            </ul>
          </div>

          {/* Failure evidence that shaped next round */}
          {activeRound.roundNumber < rounds.length && (
            <div className="litmus-feedback-bridge">
              <div className="feedback-bridge-header">
                <ArrowRight size={16} />
                <span>FAILURE EVIDENCE FED TO ROUND {activeRound.roundNumber + 1}</span>
              </div>
              <p className="feedback-bridge-text">
                Captured deadlock stack traces and concurrency stampede logs were injected into agent system context. Round {activeRound.roundNumber + 1} synthesized counter-patches directly addressing these failure invariants.
              </p>
            </div>
          )}
        </div>
      ) : (
        <div className="litmus-round-empty">
          <AlertTriangle size={18} />
          <span>No rounds data available yet.</span>
        </div>
      )}

      {/* Embedded Rejection Memory Component */}
      <RejectionMemory rejectedAttempts={rejectedAttempts} />
    </div>
  );
};
