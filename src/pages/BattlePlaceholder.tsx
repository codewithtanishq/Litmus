import { Link, useLocation } from 'react-router-dom';
import { getCurrentSession } from '../services/sessionStore';
import { StatusChip } from '../components/common/StatusChip';
import { Hourglass, ArrowLeft } from 'lucide-react';
import './PlaceholderPage.css';

export const BattlePlaceholder = () => {
  const location = useLocation();
  const session = getCurrentSession();
  const sessionId = (location.state as { sessionId?: string })?.sessionId || session?.id;

  return (
    <div className="placeholder-page">
      <div className="placeholder-container">
        <div className="placeholder-header-badge">
          <Hourglass size={14} className="placeholder-header-icon" />
          <span>DEBUG WORKSPACE</span>
        </div>

        <h1 className="placeholder-title">Debug: test_failure</h1>
        <p className="placeholder-subtitle">
          Empirical test-failure inspection and reproduction workspace.
        </p>

        {/* Active Session Overview - strictly no prosecutor, defender, judge, or sandbox execution panels */}
        {session ? (
          <div className="placeholder-session-card">
            <div className="placeholder-session-card__header">
              <span className="placeholder-session-card__tag">Active Session</span>
              <StatusChip status={session.status} size="sm" />
            </div>
            <div className="placeholder-session-card__title">{session.title}</div>
            <div className="placeholder-session-card__details">
              <span>Mode: <strong>{session.mode}</strong></span>
              <span>Language: <strong>{session.language}</strong></span>
              <span>ID: <code className="placeholder-code">{sessionId || session.id}</code></span>
            </div>
            {session.question && (
              <div style={{ marginTop: '14px', fontSize: '16px', color: 'var(--color-text-secondary)', lineHeight: 1.5 }}>
                <strong style={{ color: 'var(--color-text-primary)' }}>Observed Question / Symptom:</strong> {session.question}
              </div>
            )}
          </div>
        ) : (
          <div className="placeholder-session-card">
            <div className="placeholder-session-card__title">No Active Test Failure Session</div>
            <p style={{ marginTop: '8px', fontSize: '16px', color: 'var(--color-text-secondary)' }}>
              Select a session or submit your reproducible bug from the dashboard to initiate debugging.
            </p>
          </div>
        )}

        <div className="placeholder-nav-actions">
          <Link to="/" className="placeholder-btn placeholder-btn--primary">
            <ArrowLeft size={16} />
            <span>Back to Dashboard</span>
          </Link>
        </div>
      </div>
    </div>
  );
};
