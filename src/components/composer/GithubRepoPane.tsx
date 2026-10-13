import type { KeyboardEvent } from 'react';
import { AlertCircle } from 'lucide-react';
import './GithubRepoPane.css';

interface GithubRepoPaneProps {
  repoUrl: string;
  onChangeRepoUrl: (url: string) => void;
  question: string;
  onChangeQuestion: (q: string) => void;
  onSubmit: () => void;
  repoError?: string;
  questionError?: string;
}

export const GITHUB_URL_REGEX = /^https:\/\/github\.com\/[A-Za-z0-9_.-]+\/[A-Za-z0-9_.-]+(\/)?$/;

export const GithubRepoPane = ({
  repoUrl,
  onChangeRepoUrl,
  question,
  onChangeQuestion,
  onSubmit,
  repoError,
  questionError,
}: GithubRepoPaneProps) => {
  const handleQuestionKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSubmit();
    }
  };

  const handleRepoKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (e.key === 'Enter') {
      e.preventDefault();
      onSubmit();
    }
  };

  return (
    <div className="github-repo-pane">
      {/* Repo URL Input */}
      <div className="github-repo-pane__section">
        <label htmlFor="repo-url-input" className="github-repo-pane__label">
          GitHub Repository URL: <span className="field-required">*</span>
        </label>
        
        <div className={`github-repo-pane__input-wrapper ${repoError ? 'github-repo-pane__input-wrapper--error' : ''}`}>
          <svg 
            className="github-repo-pane__icon" 
            width="16" 
            height="16" 
            viewBox="0 0 24 24" 
            fill="none" 
            stroke="currentColor" 
            strokeWidth="2" 
            strokeLinecap="round" 
            strokeLinejoin="round"
            aria-hidden="true"
          >
            <path d="M15 22v-4a4.8 4.8 0 0 0-1-3.5c3 0 6-2 6-5.5.08-1.25-.27-2.48-1-3.5.28-1.15.28-2.35 0-3.5 0 0-1 0-3 1.5-2.64-.5-5.36-.5-8 0C6 2 5 2 5 2c-.3 1.15-.3 2.35 0 3.5A5.403 5.403 0 0 0 4 9c0 3.5 3 5.5 6 5.5-.39.49-.68 1.05-.85 1.65-.17.6-.22 1.23-.15 1.85v4" />
            <path d="M9 18c-4.51 2-5-2-7-2" />
          </svg>
          <input
            id="repo-url-input"
            type="url"
            className="github-repo-pane__input"
            value={repoUrl}
            onChange={(e) => onChangeRepoUrl(e.target.value.trim())}
            onKeyDown={handleRepoKeyDown}
            placeholder="https://github.com/owner/repository"
            spellCheck={false}
            autoCapitalize="off"
            autoComplete="off"
          />
        </div>
        
        {repoError && (
          <div className="composer-inline-error" role="alert">
            <AlertCircle size={13} />
            <span>{repoError}</span>
          </div>
        )}
        <span className="github-repo-pane__hint">
          Format must match: <code className="github-repo-pane__code">https://github.com/owner/repo</code>
        </span>
      </div>

      {/* Question Field */}
      <div className="github-repo-pane__section">
        <div className="github-repo-pane__section-header">
          <label htmlFor="repo-question-input" className="github-repo-pane__label">
            Debugging Scope / Target Issue: <span className="field-required">*</span>
          </label>
          <span className="github-repo-pane__hint">Press Enter to submit &bull; Shift+Enter for new line</span>
        </div>
        <textarea
          id="repo-question-input"
          className={`github-repo-pane__question-input ${questionError ? 'github-repo-pane__question-input--error' : ''}`}
          rows={2}
          value={question}
          onChange={(e) => onChangeQuestion(e.target.value)}
          onKeyDown={handleQuestionKeyDown}
          placeholder="e.g. Pinpoint root cause of issue #42 where token stream stalls on empty buffer"
        />
        {questionError && (
          <div className="composer-inline-error" role="alert">
            <AlertCircle size={13} />
            <span>{questionError}</span>
          </div>
        )}
      </div>
    </div>
  );
};
