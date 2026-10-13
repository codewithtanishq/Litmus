import { useState, useEffect } from 'react';
import { Link } from 'react-router-dom';
import { getCurrentSession } from '../services/sessionStore';
import { debugService } from '../services/debugService';
import { StatusChip } from '../components/common/StatusChip';
import { formatMeasured, type FinalResult } from '../types/litmus';
import { 
  FileCheck, 
  ArrowLeft, 
  AlertTriangle, 
  Terminal, 
  Layers
} from 'lucide-react';
import './PlaceholderPage.css';

export const ResultsPlaceholder = () => {
  const session = getCurrentSession();
  const [result, setResult] = useState<FinalResult | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    async function loadResult() {
      if (session) {
        const res = await debugService.getResult(session.id);
        setResult(res);
      } else {
        // Fallback to active demo result
        const res = await debugService.getResult('demo-session-verified-01');
        setResult(res);
      }
      setLoading(false);
    }
    loadResult();
  }, [session]);

  return (
    <div className="placeholder-page">
      <div className="placeholder-container">
        <div className="placeholder-header-badge">
          <FileCheck size={14} className="placeholder-header-icon" />
          <span>PHASE 4 PREVIEW</span>
        </div>

        <h1 className="placeholder-title">Final Adjudication & Fix Report</h1>
        <p className="placeholder-subtitle">
          Comprehensive synthesis of adversarial debate, sandbox evidence, and verified patch.
        </p>

        {loading ? (
          <div className="placeholder-loading">Loading adjudication report...</div>
        ) : result ? (
          <div className="placeholder-report-card">
            <div className="placeholder-report-card__header">
              <div className="placeholder-report-card__status-row">
                <span className="placeholder-report-card__title">Verification Status</span>
                <StatusChip status={result.status} size="md" />
              </div>
              <p className="placeholder-report-card__summary">{result.summary}</p>
            </div>

            {/* Test Metrics grid - demonstrating "Not measured" handling for null values */}
            <div className="placeholder-metrics-grid">
              <div className="placeholder-metric">
                <span className="placeholder-metric__label">Initial Failed Tests</span>
                <span className="placeholder-metric__value">
                  {formatMeasured(result.initialFailedTests)}
                </span>
              </div>

              <div className="placeholder-metric">
                <span className="placeholder-metric__label">Final Failed Tests</span>
                <span className="placeholder-metric__value">
                  {formatMeasured(result.finalFailedTests)}
                </span>
              </div>

              <div className="placeholder-metric">
                <span className="placeholder-metric__label">Debate Rounds</span>
                <span className="placeholder-metric__value">
                  {formatMeasured(result.rounds?.length)}
                </span>
              </div>

              <div className="placeholder-metric">
                <span className="placeholder-metric__label">Rejected Attempts</span>
                <span className="placeholder-metric__value">
                  {formatMeasured(result.rejectedAttempts?.length)}
                </span>
              </div>
            </div>

            {/* Corrected Code if present */}
            {result.correctedCode && (
              <div className="placeholder-code-preview">
                <div className="placeholder-code-preview__header">
                  <Terminal size={14} />
                  <span>Verified Solution Code</span>
                </div>
                <pre className="placeholder-code-block">
                  <code>{result.correctedCode}</code>
                </pre>
              </div>
            )}

            {/* Limitations */}
            {result.limitations && result.limitations.length > 0 && (
              <div className="placeholder-limitations">
                <div className="placeholder-limitations__header">
                  <AlertTriangle size={14} />
                  <span>Identified Limitations & Watchpoints</span>
                </div>
                <ul className="placeholder-limitations__list">
                  {result.limitations.map((lim, i) => (
                    <li key={i}>{lim}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        ) : (
          <div className="placeholder-empty">No results found for current session.</div>
        )}

        <div className="placeholder-nav-actions">
          <Link to="/" className="placeholder-btn placeholder-btn--secondary">
            <ArrowLeft size={14} />
            <span>Back to Composer</span>
          </Link>
          <Link to="/battle" className="placeholder-btn placeholder-btn--primary">
            <Layers size={14} />
            <span>Go to Battle</span>
          </Link>
        </div>
      </div>
    </div>
  );
};
