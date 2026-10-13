import type { KeyboardEvent } from 'react';
import { CodeEditor } from '../common/CodeEditor';
import { AlertCircle } from 'lucide-react';
import type { BugDetails } from '../../types/litmus';
import './UploadCodePane.css';

interface UploadCodePaneProps {
  code: string;
  onChangeCode: (code: string) => void;
  language: string;
  question: string;
  onChangeQuestion: (q: string) => void;
  details?: BugDetails;
  onChangeDetails?: (details: BugDetails) => void;
  onSubmit: () => void;
  codeError?: string;
  questionError?: string;
}

export const UploadCodePane = ({
  code,
  onChangeCode,
  language,
  question,
  onChangeQuestion,
  onSubmit,
  codeError,
  questionError,
}: UploadCodePaneProps) => {
  // Question input Enter vs Shift+Enter
  const handleQuestionKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSubmit();
    }
  };

  return (
    <div className="upload-code-pane">
      {/* Code Editor */}
      <div className="upload-code-pane__section">
        <div className="upload-code-pane__section-header">
          <label className="upload-code-pane__label">
            Source Code with Bug <span className="field-required">*</span>
          </label>
          <span className="upload-code-pane__hint">Tab key inserts 2 spaces</span>
        </div>
        
        <CodeEditor
          value={code}
          onChange={onChangeCode}
          language={language}
          placeholder="# Paste your function, module, or reproducible bug snippet here..."
          minHeight="170px"
          ariaLabel="Source code"
        />
        {codeError && (
          <div className="composer-inline-error" role="alert">
            <AlertCircle size={15} />
            <span>{codeError}</span>
          </div>
        )}
      </div>

      {/* Question Field */}
      <div className="upload-code-pane__section">
        <div className="upload-code-pane__section-header">
          <label htmlFor="question-input" className="upload-code-pane__label">
            Debugging Question / Observed Symptom <span className="field-required">*</span>
          </label>
        </div>
        <textarea
          id="question-input"
          className={`upload-code-pane__question-input ${questionError ? 'upload-code-pane__question-input--error' : ''}`}
          rows={2}
          value={question}
          onChange={(e) => onChangeQuestion(e.target.value)}
          onKeyDown={handleQuestionKeyDown}
          placeholder="e.g. Why is chunk_with_overlap silently dropping elements on non-exact steps?"
        />
        {questionError && (
          <div className="composer-inline-error" role="alert">
            <AlertCircle size={15} />
            <span>{questionError}</span>
          </div>
        )}
      </div>
    </div>
  );
};
