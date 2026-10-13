import { useState } from 'react';
import type { RejectedAttempt } from '../../types/litmus';
import { ShieldX, ChevronDown, ChevronUp, Copy, Check, GitPullRequest } from 'lucide-react';
import './RejectionMemory.css';

interface RejectionMemoryProps {
  rejectedAttempts: RejectedAttempt[];
  className?: string;
}

export const RejectionMemory = ({
  rejectedAttempts,
  className = '',
}: RejectionMemoryProps) => {
  const [expandedId, setExpandedId] = useState<string | null>(
    rejectedAttempts.length > 0 ? rejectedAttempts[0].attemptId : null
  );
  const [copiedId, setCopiedId] = useState<string | null>(null);

  if (rejectedAttempts.length === 0) {
    return (
      <div className={`litmus-rejection-memory litmus-rejection-memory--empty ${className}`}>
        <p className="litmus-rejection-memory__empty-text">
          No rejected attempts recorded. All candidates under verification.
        </p>
      </div>
    );
  }

  const handleCopyCode = async (attemptId: string, code: string) => {
    try {
      await navigator.clipboard.writeText(code);
      setCopiedId(attemptId);
      setTimeout(() => setCopiedId(null), 2000);
    } catch {
      // fallback
    }
  };

  const getDifferentialHint = (author: string, index: number): string => {
    if (author.toLowerCase() === 'prosecutor') {
      return index === 0
        ? 'Replaced naive range boundary expansion with guarded while-loop and min bounds clamp.'
        : 'Subsequent attempt isolates key-level events rather than acquiring a coarse re-entrant global lock.';
    }
    return index === 1
      ? 'Optimistic store synchronizer failed thundering herd; replaced with single-flight Task promise multiplexing.'
      : 'Task future cache unbounded retention replaced with weakref cycle collector.';
  };

  return (
    <section 
      className={`litmus-rejection-memory ${className}`}
      aria-label="Rejection memory adversarial history"
    >
      <div className="litmus-rejection-memory__header">
        <div className="litmus-rejection-memory__title-row">
          <ShieldX size={18} className="litmus-rejection-memory__icon" />
          <h3 className="litmus-rejection-memory__title">
            Rejection Memory ({rejectedAttempts.length})
          </h3>
        </div>
        <p className="litmus-rejection-memory__subtitle">
          Failed candidate traces archived to prevent cyclical regressions in subsequent rounds.
        </p>
      </div>

      <div className="litmus-rejection-memory__list">
        {rejectedAttempts.map((attempt, idx) => {
          const isExpanded = expandedId === attempt.attemptId;
          const authorTag = attempt.author.toUpperCase();

          return (
            <div 
              key={attempt.attemptId} 
              className={`litmus-rejection-card ${isExpanded ? 'litmus-rejection-card--expanded' : ''}`}
            >
              <div 
                className="litmus-rejection-card__summary"
                onClick={() => setExpandedId(isExpanded ? null : attempt.attemptId)}
                role="button"
                tabIndex={0}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    setExpandedId(isExpanded ? null : attempt.attemptId);
                  }
                }}
                aria-expanded={isExpanded}
              >
                <div className="litmus-rejection-card__meta">
                  <span className="litmus-rejection-card__id">{attempt.attemptId}</span>
                  <span className={`litmus-rejection-card__author litmus-rejection-card__author--${attempt.author}`}>
                    {authorTag}
                  </span>
                  <span className="litmus-rejection-card__reason-preview">
                    {attempt.failureReason}
                  </span>
                </div>

                <div className="litmus-rejection-card__toggle">
                  {isExpanded ? <ChevronUp size={16} /> : <ChevronDown size={16} />}
                </div>
              </div>

              {isExpanded && (
                <div className="litmus-rejection-card__body">
                  {/* Grid showing What was tried, Why rejected, and Difference */}
                  <div className="litmus-rejection-details-grid">
                    <div className="litmus-rejection-detail-item">
                      <span className="rejection-detail-label">WHY REJECTED</span>
                      <p className="rejection-detail-value rejection-detail-value--reason">
                        {attempt.failureReason}
                      </p>
                    </div>

                    <div className="litmus-rejection-detail-item">
                      <span className="rejection-detail-label">
                        <GitPullRequest size={12} />
                        HOW NEXT ATTEMPT DIFFERS
                      </span>
                      <p className="rejection-detail-value rejection-detail-value--diff">
                        {getDifferentialHint(attempt.author, idx)}
                      </p>
                    </div>
                  </div>

                  {/* Rejected code snippet */}
                  <div className="litmus-rejection-code-box">
                    <div className="litmus-rejection-code-header">
                      <span className="rejection-code-title">WHAT WAS TRIED (DISCARDED PATCH)</span>
                      <button
                        type="button"
                        className="rejection-copy-btn"
                        onClick={() => handleCopyCode(attempt.attemptId, attempt.code)}
                        aria-label="Copy rejected candidate code"
                      >
                        {copiedId === attempt.attemptId ? (
                          <Check size={12} className="litmus-copy-icon--ok" />
                        ) : (
                          <Copy size={12} />
                        )}
                        <span>{copiedId === attempt.attemptId ? 'Copied' : 'Copy'}</span>
                      </button>
                    </div>
                    <pre className="litmus-rejection-code-pre">
                      <code>{attempt.code}</code>
                    </pre>
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>
    </section>
  );
};
