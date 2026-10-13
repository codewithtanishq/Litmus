import type { ReactNode } from 'react';
import type { AgentRole, Candidate, JudgeDecision } from '../../types/litmus';
import { 
  Crosshair, 
  ShieldAlert, 
  Scale, 
  AlertCircle, 
  CheckCircle2, 
  XCircle,
  Clock,
  Sparkles,
  Terminal
} from 'lucide-react';
import { DiffViewer } from './DiffViewer';
import './AgentCard.css';

interface BaseAgentCardProps {
  role: AgentRole;
  title: string;
  subtitle?: string;
  timestamp?: string;
  children: ReactNode;
  className?: string;
}

export const BaseAgentCard = ({
  role,
  title,
  subtitle,
  timestamp,
  children,
  className = '',
}: BaseAgentCardProps) => {
  const getRoleIcon = () => {
    switch (role) {
      case 'prosecutor':
        return <Crosshair size={18} className="agent-card__header-icon" />;
      case 'defender':
        return <ShieldAlert size={18} className="agent-card__header-icon" />;
      case 'judge':
        return <Scale size={18} className="agent-card__header-icon" />;
      default:
        return <Terminal size={18} className="agent-card__header-icon" />;
    }
  };

  return (
    <article 
      className={`litmus-agent-card litmus-agent-card--${role} ${className}`}
      aria-label={`${title} card`}
    >
      <header className="litmus-agent-card__header">
        <div className="litmus-agent-card__header-left">
          <div className="litmus-agent-card__role-icon-box" aria-hidden="true">
            {getRoleIcon()}
          </div>
          <div>
            <div className="litmus-agent-card__title-row">
              <span className="litmus-agent-card__role-badge">{role.toUpperCase()}</span>
              <h3 className="litmus-agent-card__title">{title}</h3>
            </div>
            {subtitle && <p className="litmus-agent-card__subtitle">{subtitle}</p>}
          </div>
        </div>

        {timestamp && (
          <time className="litmus-agent-card__timestamp">
            {timestamp}
          </time>
        )}
      </header>

      <div className="litmus-agent-card__body">
        {children}
      </div>
    </article>
  );
};

/* 1. Prosecutor Card */
interface ProsecutorCardProps {
  claim: string;
  candidateA: Candidate;
  originalCode: string;
  timestamp?: string;
}

export const ProsecutorCard = ({
  claim,
  candidateA,
  originalCode,
  timestamp,
}: ProsecutorCardProps) => {
  return (
    <BaseAgentCard
      role="prosecutor"
      title="Prosecutor Agent"
      subtitle="Adversarial hypothesis & root cause diagnosis"
      timestamp={timestamp}
    >
      <div className="agent-field-block">
        <span className="agent-field-label">PROPOSED ROOT CAUSE & HYPOTHESIS</span>
        <p className="agent-field-text">{claim}</p>
      </div>

      <div className="agent-field-block">
        <span className="agent-field-label">CANDIDATE FIX A PREVIEW</span>
        <DiffViewer
          originalCode={originalCode}
          candidateA={candidateA}
          initialSelected="fix_a"
        />
      </div>
    </BaseAgentCard>
  );
};

/* 2. Defender Card */
interface DefenderCardProps {
  challenge: string;
  objectionText?: string;
  candidateA: Candidate;
  candidateB: Candidate;
  originalCode: string;
  timestamp?: string;
}

export const DefenderCard = ({
  challenge,
  objectionText,
  candidateA,
  candidateB,
  originalCode,
  timestamp,
}: DefenderCardProps) => {
  return (
    <BaseAgentCard
      role="defender"
      title="Defender Agent"
      subtitle="Counter-hypothesis & regression boundary challenge"
      timestamp={timestamp}
    >
      {/* Prominent Objection Tag */}
      <div className="litmus-objection-banner" role="alert">
        <div className="litmus-objection-tag">
          <AlertCircle size={14} />
          <span>OBJECTION</span>
        </div>
        <p className="litmus-objection-content">
          {objectionText || 'Fix A introduces boundary regression or unhandled concurrency invariants.'}
        </p>
      </div>

      <div className="agent-field-block">
        <span className="agent-field-label">DEFENDER COUNTER-HYPOTHESIS</span>
        <p className="agent-field-text">{challenge}</p>
      </div>

      <div className="agent-field-block">
        <span className="agent-field-label">CANDIDATE FIX B PREVIEW</span>
        <DiffViewer
          originalCode={originalCode}
          candidateA={candidateA}
          candidateB={candidateB}
          initialSelected="fix_b"
        />
      </div>
    </BaseAgentCard>
  );
};

/* 3. Judge Card */
interface JudgeCardProps {
  decision: JudgeDecision;
  roundNumber?: number;
}

export const JudgeCard = ({ decision, roundNumber = 1 }: JudgeCardProps) => {
  const getVerdictBadge = () => {
    switch (decision.verdict) {
      case 'fix_b_selected':
        return (
          <span className="judge-verdict-badge judge-verdict-badge--pass">
            <CheckCircle2 size={14} /> Fix B Verified & Selected
          </span>
        );
      case 'fix_a_selected':
        return (
          <span className="judge-verdict-badge judge-verdict-badge--pass">
            <CheckCircle2 size={14} /> Fix A Verified & Selected
          </span>
        );
      case 'both_failed':
        return (
          <span className="judge-verdict-badge judge-verdict-badge--fail">
            <XCircle size={14} /> Both Candidates Failed Sandbox
          </span>
        );
      case 'inconclusive':
        return (
          <span className="judge-verdict-badge judge-verdict-badge--inconclusive">
            <Clock size={14} /> Watchdog Inconclusive (Timeout)
          </span>
        );
      case 'escalate_round_2':
        return (
          <span className="judge-verdict-badge judge-verdict-badge--warn">
            <Sparkles size={14} /> Escalated to Round 2
          </span>
        );
      default:
        return (
          <span className="judge-verdict-badge">
            Verdict: {decision.verdict}
          </span>
        );
    }
  };

  return (
    <BaseAgentCard
      role="judge"
      title="Judge Agent"
      subtitle={`Adjudication & empirical sandbox verdict (Round ${roundNumber})`}
      timestamp={decision.timestamp ? new Date(decision.timestamp).toLocaleTimeString() : undefined}
    >
      <div className="judge-verdict-header">
        {getVerdictBadge()}
      </div>

      {/* Two Visually Separated Blocks */}
      <div className="judge-blocks-grid">
        {/* Block 1: Verified Test Evidence */}
        <div className="judge-evidence-block">
          <div className="judge-block-header judge-block-header--evidence">
            <Terminal size={15} />
            <h4>VERIFIED TEST EVIDENCE</h4>
          </div>
          <ul className="judge-evidence-list">
            {decision.evidence.map((item, idx) => (
              <li key={idx} className="judge-evidence-item">
                <span className="judge-evidence-bullet" aria-hidden="true" />
                <span>{item}</span>
              </li>
            ))}
          </ul>
        </div>

        {/* Block 2: AI-Generated Explanation */}
        <div className="judge-explanation-block">
          <div className="judge-block-header judge-block-header--ai">
            <Sparkles size={15} />
            <h4>AI-GENERATED EXPLANATION</h4>
          </div>
          <p className="judge-explanation-text">
            {decision.rationale}
          </p>
        </div>
      </div>
    </BaseAgentCard>
  );
};
