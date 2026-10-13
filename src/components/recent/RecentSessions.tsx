import { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  History, 
  Trash2, 
  Code2, 
  FileCode, 
  GitBranch, 
  ArrowRight,
  Sparkles
} from 'lucide-react';
import { StatusChip } from '../common/StatusChip';
import { 
  getRecentSessions, 
  clearRecentSessions, 
  saveCurrentSession 
} from '../../services/sessionStore';
import type { Session } from '../../types/litmus';
import './RecentSessions.css';

interface RecentSessionsProps {
  onSelectSample?: () => void;
}

export const RecentSessions = ({ onSelectSample }: RecentSessionsProps) => {
  const navigate = useNavigate();
  const [sessions, setSessions] = useState<Session[]>(getRecentSessions());

  useEffect(() => {
    const handleRecentChange = () => {
      setSessions(getRecentSessions());
    };

    window.addEventListener('litmus:recent-sessions-changed', handleRecentChange);
    return () => window.removeEventListener('litmus:recent-sessions-changed', handleRecentChange);
  }, []);

  const handleOpenSession = (session: Session) => {
    saveCurrentSession(session);
    if (session.status === 'in_progress') {
      navigate('/battle', { state: { sessionId: session.id } });
    } else {
      navigate('/results', { state: { sessionId: session.id } });
    }
  };

  const handleClearHistory = () => {
    clearRecentSessions();
    setSessions([]);
  };

  const formatDate = (dateString: string): string => {
    try {
      const d = new Date(dateString);
      if (isNaN(d.getTime())) return 'Recently';
      return d.toLocaleDateString(undefined, {
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
      });
    } catch {
      return 'Recently';
    }
  };

  const getModeIcon = (mode: string) => {
    switch (mode) {
      case 'file': return <FileCode size={13} className="recent-item__mode-icon" />;
      case 'repo': return <GitBranch size={13} className="recent-item__mode-icon" />;
      default: return <Code2 size={13} className="recent-item__mode-icon" />;
    }
  };

  return (
    <section className="recent-sessions-container" aria-label="Recent debugging sessions">
      <div className="recent-sessions__header">
        <div className="recent-sessions__title">
          <History size={14} className="recent-sessions__title-icon" />
          <span>Recent Sessions</span>
        </div>

        {sessions.length > 0 && (
          <button
            type="button"
            className="recent-sessions__clear-btn"
            onClick={handleClearHistory}
            title="Clear recent session history"
          >
            <Trash2 size={12} />
            <span>Clear history</span>
          </button>
        )}
      </div>

      {sessions.length === 0 ? (
        <div className="recent-sessions__empty">
          <p className="recent-sessions__empty-title">
            No recent debugging sessions yet
          </p>
          <p className="recent-sessions__empty-desc">
            Submit code above or click "Try a sample bug" to launch an adversarial Prosecutor vs Defender debate.
          </p>
          {onSelectSample && (
            <button
              type="button"
              className="recent-sessions__empty-action"
              onClick={onSelectSample}
            >
              <Sparkles size={13} />
              <span>Load sample off-by-one bug</span>
            </button>
          )}
        </div>
      ) : (
        <div className="recent-sessions__list" role="list">
          {sessions.map((session) => (
            <div
              key={session.id}
              className="recent-session-card"
              role="listitem"
              onClick={() => handleOpenSession(session)}
              tabIndex={0}
              onKeyDown={(e) => {
                if (e.key === 'Enter') handleOpenSession(session);
              }}
            >
              <div className="recent-session-card__main">
                <div className="recent-session-card__headline">
                  {getModeIcon(session.mode)}
                  <span className="recent-session-card__title">
                    {session.title}
                  </span>
                </div>

                <div className="recent-session-card__meta">
                  <span className="recent-session-card__lang font-mono">
                    {session.language}
                  </span>
                  <span className="recent-session-card__dot">&bull;</span>
                  <span className="recent-session-card__time">
                    {formatDate(session.updatedAt || session.createdAt)}
                  </span>
                  {session.isDemo && (
                    <>
                      <span className="recent-session-card__dot">&bull;</span>
                      <span className="recent-session-card__demo-pill">DEMO</span>
                    </>
                  )}
                </div>
              </div>

              <div className="recent-session-card__right">
                <StatusChip status={session.status} size="sm" />
                <ArrowRight size={14} className="recent-session-card__arrow" />
              </div>
            </div>
          ))}
        </div>
      )}
    </section>
  );
};
