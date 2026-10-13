import { Link } from 'react-router-dom';
import { getCurrentSession } from '../services/sessionStore';
import { StatusChip } from '../components/common/StatusChip';
import { Scale, ArrowLeft, ArrowRight, CheckCircle2 } from 'lucide-react';
import './PlaceholderPage.css';

export const CheckmatePlaceholder = () => {
  const session = getCurrentSession();

  return (
    <div className="placeholder-page">
      <div className="placeholder-container">
        <div className="placeholder-header-badge">
          <Scale size={14} className="placeholder-header-icon" />
          <span>PHASE 3 PREVIEW</span>
        </div>

        <h1 className="placeholder-title">Checkmate Arena</h1>
        <p className="placeholder-subtitle">
          The Judge executes test sandboxes, confronts evidence, and issues verdicts.
        </p>

        {session && (
          <div className="placeholder-session-card">
            <div className="placeholder-session-card__header">
              <span className="placeholder-session-card__tag">Active Session</span>
              <StatusChip status={session.status} size="sm" />
            </div>
            <div className="placeholder-session-card__title">{session.title}</div>
            <div className="placeholder-session-card__details">
              <span>Sandbox Runs: <strong>Isolated Ephemeral Container</strong></span>
              <span>Adjudication: <strong>Evidence-driven</strong></span>
            </div>
          </div>
        )}

        <div className="placeholder-info-box">
          <CheckCircle2 size={16} className="placeholder-info-icon" />
          <p>
            This page is slated for subsequent tasks. In production, this view displays live sandbox terminal logs, test exit codes, regression matrices, and the Judge's formal opinion.
          </p>
        </div>

        <div className="placeholder-nav-actions">
          <Link to="/battle" className="placeholder-btn placeholder-btn--secondary">
            <ArrowLeft size={14} />
            <span>Back to Battle</span>
          </Link>
          <Link to="/results" className="placeholder-btn placeholder-btn--primary">
            <span>View Results Report</span>
            <ArrowRight size={14} />
          </Link>
        </div>
      </div>
    </div>
  );
};
