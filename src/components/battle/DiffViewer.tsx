import { useState, useMemo } from 'react';
import type { Candidate } from '../../types/litmus';
import { Copy, Check, FileCode, CheckCircle2, XCircle, AlertTriangle } from 'lucide-react';
import './DiffViewer.css';

interface DiffViewerProps {
  originalCode: string;
  candidateA: Candidate;
  candidateB?: Candidate;
  initialSelected?: 'fix_a' | 'fix_b';
  className?: string;
}

interface DiffLine {
  type: 'added' | 'removed' | 'unchanged';
  oldLineNumber?: number;
  newLineNumber?: number;
  content: string;
}

/**
 * Computes a simple line diff between original and updated text
 */
function computeDiff(original: string, updated: string): DiffLine[] {
  const origLines = (original || '').split('\n');
  const updLines = (updated || '').split('\n');
  const result: DiffLine[] = [];

  // If identical
  if (original.trim() === updated.trim()) {
    return updLines.map((content, idx) => ({
      type: 'unchanged',
      oldLineNumber: idx + 1,
      newLineNumber: idx + 1,
      content,
    }));
  }

  // Find common prefix
  let prefixCount = 0;
  while (
    prefixCount < origLines.length &&
    prefixCount < updLines.length &&
    origLines[prefixCount] === updLines[prefixCount]
  ) {
    result.push({
      type: 'unchanged',
      oldLineNumber: prefixCount + 1,
      newLineNumber: prefixCount + 1,
      content: origLines[prefixCount],
    });
    prefixCount++;
  }

  // Find common suffix
  let origSuffix = origLines.length - 1;
  let updSuffix = updLines.length - 1;
  const suffixLines: DiffLine[] = [];

  while (
    origSuffix >= prefixCount &&
    updSuffix >= prefixCount &&
    origLines[origSuffix] === updLines[updSuffix]
  ) {
    suffixLines.unshift({
      type: 'unchanged',
      oldLineNumber: origSuffix + 1,
      newLineNumber: updSuffix + 1,
      content: origLines[origSuffix],
    });
    origSuffix--;
    updSuffix--;
  }

  // Middle divergent lines
  let curOld = prefixCount + 1;
  for (let i = prefixCount; i <= origSuffix; i++) {
    result.push({
      type: 'removed',
      oldLineNumber: curOld++,
      content: origLines[i],
    });
  }

  let curNew = prefixCount + 1;
  for (let j = prefixCount; j <= updSuffix; j++) {
    result.push({
      type: 'added',
      newLineNumber: curNew++,
      content: updLines[j],
    });
  }

  // Append suffix
  result.push(...suffixLines);

  return result;
}

export const DiffViewer = ({
  originalCode,
  candidateA,
  candidateB,
  initialSelected = 'fix_a',
  className = '',
}: DiffViewerProps) => {
  const [selectedFix, setSelectedFix] = useState<'fix_a' | 'fix_b'>(initialSelected);
  const [copied, setCopied] = useState(false);

  const activeCandidate = selectedFix === 'fix_a' ? candidateA : candidateB || candidateA;

  const diffLines = useMemo(() => {
    return computeDiff(originalCode, activeCandidate.code);
  }, [originalCode, activeCandidate.code]);

  const handleCopyPatch = async () => {
    try {
      await navigator.clipboard.writeText(activeCandidate.code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback
    }
  };

  const getStatusIcon = (status?: string) => {
    switch (status) {
      case 'passed':
        return <CheckCircle2 size={13} className="diff-status-icon--pass" />;
      case 'failed':
        return <XCircle size={13} className="diff-status-icon--fail" />;
      case 'timed_out':
        return <AlertTriangle size={13} className="diff-status-icon--warn" />;
      default:
        return null;
    }
  };

  return (
    <div className={`litmus-diff-viewer ${className}`} role="region" aria-label="Patch diff viewer">
      {/* Switcher Tab Header */}
      <div className="litmus-diff-viewer__header">
        <div className="litmus-diff-tabs" role="tablist" aria-label="Candidate fix selection">
          <button
            type="button"
            role="tab"
            aria-selected={selectedFix === 'fix_a'}
            className={`litmus-diff-tab ${selectedFix === 'fix_a' ? 'litmus-diff-tab--active' : ''}`}
            onClick={() => setSelectedFix('fix_a')}
          >
            <span className="litmus-diff-tab__tag litmus-diff-tab__tag--prosecutor">PROSECUTOR</span>
            <span className="litmus-diff-tab__name">Fix A</span>
            {getStatusIcon(candidateA.sandboxRun?.status)}
          </button>

          {candidateB && (
            <button
              type="button"
              role="tab"
              aria-selected={selectedFix === 'fix_b'}
              className={`litmus-diff-tab ${selectedFix === 'fix_b' ? 'litmus-diff-tab--active' : ''}`}
              onClick={() => setSelectedFix('fix_b')}
            >
              <span className="litmus-diff-tab__tag litmus-diff-tab__tag--defender">DEFENDER</span>
              <span className="litmus-diff-tab__name">Fix B</span>
              {getStatusIcon(candidateB.sandboxRun?.status)}
            </button>
          )}
        </div>

        <button
          type="button"
          className="litmus-copy-patch-btn"
          onClick={handleCopyPatch}
          aria-label={`Copy ${selectedFix === 'fix_a' ? 'Fix A' : 'Fix B'} code to clipboard`}
        >
          {copied ? <Check size={13} className="litmus-copy-icon--ok" /> : <Copy size={13} />}
          <span>{copied ? 'Patch Copied!' : 'Copy Patch'}</span>
        </button>
      </div>

      {/* Candidate meta info */}
      <div className="litmus-diff-viewer__meta">
        <div className="litmus-diff-viewer__meta-title">
          <FileCode size={14} />
          <strong>{activeCandidate.title}</strong>
        </div>
        <p className="litmus-diff-viewer__meta-desc">
          {activeCandidate.explanation}
        </p>
      </div>

      {/* Diff Table */}
      <div className="litmus-diff-table-container">
        <div className="litmus-diff-table" role="table" aria-label="Line diff table">
          {diffLines.map((line, idx) => (
            <div
              key={idx}
              className={`litmus-diff-row litmus-diff-row--${line.type}`}
              role="row"
            >
              <div className="litmus-diff-cell litmus-diff-cell--lineno-old" aria-hidden="true">
                {line.oldLineNumber ?? ''}
              </div>
              <div className="litmus-diff-cell litmus-diff-cell--lineno-new" aria-hidden="true">
                {line.newLineNumber ?? ''}
              </div>
              <div className="litmus-diff-cell litmus-diff-cell--marker" aria-hidden="true">
                {line.type === 'added' ? '+' : line.type === 'removed' ? '-' : ' '}
              </div>
              <div className="litmus-diff-cell litmus-diff-cell--code">
                <code>{line.content || ' '}</code>
              </div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
