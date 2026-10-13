import { useState } from 'react';
import type { Candidate, SandboxRun } from '../../types/litmus';
import { formatMeasured } from '../../types/litmus';
import { 
  CheckCircle2, 
  XCircle, 
  Clock, 
  AlertTriangle, 
  Loader2, 
  Terminal, 
  ChevronDown, 
  ChevronUp, 
  Copy, 
  Check, 
  ShieldCheck,
  ShieldAlert
} from 'lucide-react';
import './SandboxPanel.css';

interface SandboxPanelProps {
  id: 'fix_a' | 'fix_b';
  label: string; // 'Sandbox A (Fix A)' or 'Sandbox B (Fix B)'
  candidate?: Candidate;
  isSimulating?: boolean;
  className?: string;
}

export const SandboxPanel = ({
  id: _id,
  label,
  candidate,
  isSimulating = false,
  className = '',
}: SandboxPanelProps) => {
  const [logsExpanded, setLogsExpanded] = useState(true);
  const [copied, setCopied] = useState(false);

  const run: SandboxRun | undefined = candidate?.sandboxRun;
  const status = isSimulating ? 'running' : run?.status || 'pending';

  const handleCopyLogs = async () => {
    if (!run?.logs) return;
    try {
      await navigator.clipboard.writeText(run.logs);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback
    }
  };

  const renderStatusBadge = () => {
    switch (status) {
      case 'passed':
        return (
          <div className="sandbox-status-pill sandbox-status-pill--pass">
            <CheckCircle2 size={14} />
            <span>Passed (Exit 0)</span>
          </div>
        );
      case 'failed':
        return (
          <div className="sandbox-status-pill sandbox-status-pill--fail">
            <XCircle size={14} />
            <span>Tests Failed (Exit {run?.exitCode ?? 1})</span>
          </div>
        );
      case 'timed_out':
        return (
          <div className="sandbox-status-pill sandbox-status-pill--timeout">
            <Clock size={14} />
            <span>Watchdog Timeout (Inconclusive)</span>
          </div>
        );
      case 'execution_error':
        return (
          <div className="sandbox-status-pill sandbox-status-pill--error">
            <AlertTriangle size={14} />
            <span>Execution Error (Inconclusive)</span>
          </div>
        );
      case 'running':
      case 'preparing':
        return (
          <div className="sandbox-status-pill sandbox-status-pill--running">
            <Loader2 size={14} className="sandbox-spinner" />
            <span>Running Container...</span>
          </div>
        );
      case 'pending':
      default:
        return (
          <div className="sandbox-status-pill sandbox-status-pill--pending">
            <Clock size={14} />
            <span>Pending Execution</span>
          </div>
        );
    }
  };

  return (
    <div 
      className={`litmus-sandbox-panel litmus-sandbox-panel--${status} ${className}`}
      role="region"
      aria-label={`${label} execution results`}
    >
      {/* Header */}
      <div className="litmus-sandbox-panel__header">
        <div className="litmus-sandbox-panel__title-box">
          <div className="litmus-sandbox-panel__title-row">
            <h3 className="litmus-sandbox-panel__title">{label}</h3>
            <span className="litmus-demo-data-badge">DEMO DATA</span>
          </div>
          {candidate && (
            <span className="litmus-sandbox-panel__candidate-title">
              {candidate.title}
            </span>
          )}
        </div>

        <div className="litmus-sandbox-panel__status-wrap">
          {renderStatusBadge()}
        </div>
      </div>

      {/* Critical Distinction Notice (Tests Failed vs Sandbox/Infrastructure Timeout) */}
      {status === 'failed' && (
        <div className="sandbox-notice sandbox-notice--tests-failed" role="note">
          <ShieldAlert size={16} className="sandbox-notice-icon" />
          <div className="sandbox-notice-text">
            <strong>Test Assertions Failed:</strong> Pytest unit/boundary assertions failed inside the sandbox container. Exit code {run?.exitCode ?? 1}.
          </div>
        </div>
      )}

      {status === 'timed_out' && (
        <div className="sandbox-notice sandbox-notice--timeout" role="note">
          <AlertTriangle size={16} className="sandbox-notice-icon" />
          <div className="sandbox-notice-text">
            <strong>Infrastructure Watchdog Timeout:</strong> Container exceeded safety threshold (&gt;30000ms) and was halted by watchdog.
            <div className="sandbox-notice-governance">
              Per litmus governance, a timeout is recorded as <em>execution_inconclusive</em> — NOT classified as a defective patch.
            </div>
          </div>
        </div>
      )}

      {status === 'execution_error' && (
        <div className="sandbox-notice sandbox-notice--timeout" role="note">
          <AlertTriangle size={16} className="sandbox-notice-icon" />
          <div className="sandbox-notice-text">
            <strong>Infrastructure Environment Error:</strong> Execution environment fault. Not classified as a patch failure.
          </div>
        </div>
      )}

      {status === 'passed' && (
        <div className="sandbox-notice sandbox-notice--passed" role="note">
          <ShieldCheck size={16} className="sandbox-notice-icon" />
          <div className="sandbox-notice-text">
            <strong>Verification Invariant Satisfied:</strong> All assertions passed with zero regressions. Exit code 0.
          </div>
        </div>
      )}

      {/* Metrics Row */}
      <div className="litmus-sandbox-metrics">
        <div className="sandbox-metric">
          <span className="sandbox-metric__label">Passed</span>
          <span className="sandbox-metric__value sandbox-metric__value--pass">
            {formatMeasured(run?.passed)}
          </span>
        </div>

        <div className="sandbox-metric">
          <span className="sandbox-metric__label">Failed</span>
          <span className="sandbox-metric__value sandbox-metric__value--fail">
            {formatMeasured(run?.failed)}
          </span>
        </div>

        <div className="sandbox-metric">
          <span className="sandbox-metric__label">Total Tests</span>
          <span className="sandbox-metric__value">
            {formatMeasured(run?.total)}
          </span>
        </div>

        <div className="sandbox-metric">
          <span className="sandbox-metric__label">Exit Code</span>
          <span className="sandbox-metric__value">
            {run?.exitCode !== null && run?.exitCode !== undefined ? run.exitCode : 'Not measured'}
          </span>
        </div>

        <div className="sandbox-metric">
          <span className="sandbox-metric__label">Wall-clock</span>
          <span className="sandbox-metric__value">
            {formatMeasured(run?.durationMs, 'ms')}
          </span>
        </div>
      </div>

      {/* Expandable Console Logs Viewer */}
      <div className="litmus-sandbox-logs-section">
        <div className="litmus-sandbox-logs-header">
          <button
            type="button"
            className="litmus-sandbox-logs-toggle"
            onClick={() => setLogsExpanded(!logsExpanded)}
            aria-expanded={logsExpanded}
          >
            <Terminal size={14} />
            <span>Container Terminal Logs</span>
            {logsExpanded ? <ChevronUp size={14} /> : <ChevronDown size={14} />}
          </button>

          {run?.logs && logsExpanded && (
            <button
              type="button"
              className="litmus-sandbox-copy-logs"
              onClick={handleCopyLogs}
              aria-label="Copy terminal logs"
            >
              {copied ? <Check size={12} className="litmus-copy-icon--ok" /> : <Copy size={12} />}
              <span>{copied ? 'Copied!' : 'Copy Logs'}</span>
            </button>
          )}
        </div>

        {logsExpanded && (
          <div className="litmus-sandbox-logs-body">
            <pre className="litmus-sandbox-logs-pre">
              {run?.logs || (status === 'running' ? 'Container booting. Spawning pytest isolation runner...' : 'No execution logs recorded yet.')}
            </pre>
          </div>
        )}
      </div>
    </div>
  );
};
