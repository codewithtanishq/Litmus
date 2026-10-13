import { useState, useEffect } from 'react';
import type { KeyboardEvent } from 'react';
import { useNavigate } from 'react-router-dom';
import { 
  Code2, 
  Upload, 
  GitBranch, 
  ArrowUp, 
  RotateCcw,
  AlertCircle 
} from 'lucide-react';
import { UploadCodePane } from './UploadCodePane';
import { UploadFilePane } from './UploadFilePane';
import { GithubRepoPane, GITHUB_URL_REGEX } from './GithubRepoPane';
import { ComposerActions } from './ComposerActions';
import { debugService } from '../../services/debugService';
import { getSampleBug } from '../../demo/demoState';
import type { InputMode, BugDetails } from '../../types/litmus';
import './Composer.css';

const SUPPORTED_LANGUAGES = [
  { value: 'python', label: 'Python (pytest)' },
  { value: 'typescript', label: 'TypeScript (vitest/jest)' },
  { value: 'javascript', label: 'JavaScript' },
  { value: 'go', label: 'Go (testing)' },
  { value: 'rust', label: 'Rust (cargo test)' },
  { value: 'java', label: 'Java (JUnit)' },
  { value: 'cpp', label: 'C++ (GTest)' },
];

export const Composer = () => {
  const navigate = useNavigate();

  // Mode selection state: Default is 'code', starts with all three shown initially
  const [mode, setMode] = useState<InputMode>('code');
  const [isLocked, setIsLocked] = useState(false);

  // Upload Code state
  const [code, setCode] = useState('');
  const [language, setLanguage] = useState('python');
  const [codeQuestion, setCodeQuestion] = useState('');
  const [details, setDetails] = useState<BugDetails>({
    failingTest: '',
    expectedBehavior: '',
    errorMessage: '',
  });

  // Upload File state
  const [fileName, setFileName] = useState('');
  const [fileSize, setFileSize] = useState<number | undefined>();
  const [fileContent, setFileContent] = useState<string | undefined>();
  const [fileQuestion, setFileQuestion] = useState('');

  // GitHub Repo state
  const [repoUrl, setRepoUrl] = useState('');
  const [repoQuestion, setRepoQuestion] = useState('');

  // Validation & Submission state
  const [errors, setErrors] = useState<{
    code?: string;
    file?: string;
    repo?: string;
    question?: string;
    global?: string;
  }>({});
  const [isSubmitting, setIsSubmitting] = useState(false);

  // Listen to sample bug changes if active scenario changes
  useEffect(() => {
    const handleScenarioChange = () => {};
    window.addEventListener('litmus:demo-scenario-changed', handleScenarioChange);
    return () => window.removeEventListener('litmus:demo-scenario-changed', handleScenarioChange);
  }, []);

  // Compute validation state for current mode
  const isInputValid = (): boolean => {
    if (mode === 'code') {
      return code.trim().length > 0 && codeQuestion.trim().length > 0;
    }
    if (mode === 'file') {
      return fileName.length > 0 && fileQuestion.trim().length > 0;
    }
    if (mode === 'repo') {
      return GITHUB_URL_REGEX.test(repoUrl.trim()) && repoQuestion.trim().length > 0;
    }
    return false;
  };

  // Keyboard shortcut Ctrl/Cmd+Enter anywhere in composer submits
  const handleComposerKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
      e.preventDefault();
      handleSubmit();
    }
  };

  // Explicit mode selection locks the choice and hides other two
  const handleSelectMode = (newMode: InputMode) => {
    setMode(newMode);
    setIsLocked(true);
    setErrors({});
  };

  const handleUnlockMode = () => {
    setIsLocked(false);
  };

  // Quick Action: Try a sample bug (must NOT submit by itself)
  const handleLoadSample = () => {
    const sample = getSampleBug();
    setMode('code');
    setIsLocked(true);
    setLanguage(sample.language);
    setCode(sample.code);
    setCodeQuestion(sample.question);
    setDetails({
      failingTest: sample.details.failingTest,
      expectedBehavior: sample.details.expectedBehavior,
      errorMessage: sample.details.errorMessage,
    });
    setErrors({});
  };

  // Quick Action: Clear
  const handleClear = () => {
    setCode('');
    setCodeQuestion('');
    setDetails({ failingTest: '', expectedBehavior: '', errorMessage: '' });
    setFileName('');
    setFileSize(undefined);
    setFileContent(undefined);
    setFileQuestion('');
    setRepoUrl('');
    setRepoQuestion('');
    setErrors({});
  };

  const hasAnyInput = Boolean(
    code.trim() ||
    codeQuestion.trim() ||
    fileName ||
    fileQuestion.trim() ||
    repoUrl.trim() ||
    repoQuestion.trim()
  );

  // Form submission handler
  const handleSubmit = async () => {
    if (isSubmitting) return; // Prevent duplicate submissions

    const newErrors: typeof errors = {};

    if (mode === 'code') {
      if (!code.trim()) {
        newErrors.code = 'Source code is required to initiate adversarial debugging.';
      }
      if (!codeQuestion.trim()) {
        newErrors.question = 'Please provide a debugging question or symptom.';
      }
    } else if (mode === 'file') {
      if (!fileName) {
        newErrors.file = 'Please upload a source file (.py, .ts, .js, etc.).';
      }
      if (!fileQuestion.trim()) {
        newErrors.question = 'Please describe the observed defect or question.';
      }
    } else if (mode === 'repo') {
      if (!repoUrl.trim()) {
        newErrors.repo = 'GitHub repository URL is required.';
      } else if (!GITHUB_URL_REGEX.test(repoUrl.trim())) {
        newErrors.repo = 'Invalid format. Use "https://github.com/owner/repository".';
      }
      if (!repoQuestion.trim()) {
        newErrors.question = 'Please specify the debugging scope or issue.';
      }
    }

    if (Object.keys(newErrors).length > 0) {
      setErrors(newErrors);
      return;
    }

    // Set submitting flag to block duplicate submits
    setIsSubmitting(true);
    setErrors({});

    try {
      const question = 
        mode === 'code' ? codeQuestion.trim() :
        mode === 'file' ? fileQuestion.trim() :
        repoQuestion.trim();

      const session = await debugService.createSession({
        mode,
        language,
        question,
        code: mode === 'code' ? code : undefined,
        fileName: mode === 'file' ? fileName : undefined,
        fileSize: mode === 'file' ? fileSize : undefined,
        fileContent: mode === 'file' ? fileContent : undefined,
        repoUrl: mode === 'repo' ? repoUrl.trim() : undefined,
        details: mode === 'code' ? details : undefined,
      });

      // Navigate to /battle with the existing router
      navigate('/battle', { state: { sessionId: session.id } });
    } catch (err) {
      console.error('Session creation failed:', err);
      setErrors({ global: 'Failed to initiate debugging session. Please try again.' });
      setIsSubmitting(false);
    }
  };

  const getModeLabel = (m: InputMode) => {
    switch (m) {
      case 'code': return 'Upload Code';
      case 'file': return 'Upload File';
      case 'repo': return 'GitHub Repo';
    }
  };

  return (
    <div className="litmus-composer-wrapper" onKeyDown={handleComposerKeyDown}>
      <div className="litmus-composer">
        {/* Mode Selector Header with 3 Options and Language Dropdown in One Row */}
        <div className="litmus-composer__header">
          <div className="litmus-composer__header-left">
            {!isLocked ? (
              // All three shown initially
              <div className="composer-mode-tabs" role="tablist" aria-label="Input Mode Selector">
                <button
                  type="button"
                  role="tab"
                  aria-selected={mode === 'code'}
                  className={`composer-mode-tab ${mode === 'code' ? 'composer-mode-tab--active' : ''}`}
                  onClick={() => handleSelectMode('code')}
                >
                  <Code2 size={16} />
                  <span>Upload Code</span>
                </button>

                <button
                  type="button"
                  role="tab"
                  aria-selected={mode === 'file'}
                  className={`composer-mode-tab ${mode === 'file' ? 'composer-mode-tab--active' : ''}`}
                  onClick={() => handleSelectMode('file')}
                >
                  <Upload size={16} />
                  <span>Upload File</span>
                </button>

                <button
                  type="button"
                  role="tab"
                  aria-selected={mode === 'repo'}
                  className={`composer-mode-tab ${mode === 'repo' ? 'composer-mode-tab--active' : ''}`}
                  onClick={() => handleSelectMode('repo')}
                >
                  <GitBranch size={16} />
                  <span>GitHub Repo</span>
                </button>
              </div>
            ) : (
              // Locked mode: other two hidden, with small "Change" control
              <div className="composer-mode-locked">
                <div className="composer-mode-locked__badge">
                  {mode === 'code' && <Code2 size={15} className="composer-mode-locked__icon" />}
                  {mode === 'file' && <Upload size={15} className="composer-mode-locked__icon" />}
                  {mode === 'repo' && <GitBranch size={15} className="composer-mode-locked__icon" />}
                  <span className="composer-mode-locked__text">{getModeLabel(mode)}</span>
                </div>

                <button
                  type="button"
                  className="composer-mode-change-btn"
                  onClick={handleUnlockMode}
                  title="Change input source mode"
                >
                  <RotateCcw size={13} />
                  <span>Change</span>
                </button>
              </div>
            )}
          </div>

          {/* Single Language Dropdown on the right side of the composer header */}
          <div className="composer-language-selector">
            <label htmlFor="composer-lang-select" className="composer-language-label">
              Language:
            </label>
            <select
              id="composer-lang-select"
              className="composer-language-dropdown"
              value={language}
              onChange={(e) => setLanguage(e.target.value)}
              aria-label="Select coding language"
            >
              {SUPPORTED_LANGUAGES.map((l) => (
                <option key={l.value} value={l.value}>
                  {l.label}
                </option>
              ))}
            </select>
          </div>
        </div>

        {/* Global Error Banner if any */}
        {errors.global && (
          <div className="composer-global-error" role="alert">
            <AlertCircle size={15} />
            <span>{errors.global}</span>
          </div>
        )}

        {/* Composer Content Body */}
        <div className="litmus-composer__body">
          {mode === 'code' && (
            <UploadCodePane
              code={code}
              onChangeCode={setCode}
              language={language}
              question={codeQuestion}
              onChangeQuestion={setCodeQuestion}
              details={details}
              onChangeDetails={setDetails}
              onSubmit={handleSubmit}
              codeError={errors.code}
              questionError={errors.question}
            />
          )}

          {mode === 'file' && (
            <UploadFilePane
              fileName={fileName}
              fileSize={fileSize}
              fileContent={fileContent}
              onFileSelect={({ name, size, content }) => {
                setFileName(name);
                setFileSize(size);
                setFileContent(content);
                setErrors((prev) => ({ ...prev, file: undefined }));
              }}
              onFileRemove={() => {
                setFileName('');
                setFileSize(undefined);
                setFileContent(undefined);
              }}
              question={fileQuestion}
              onChangeQuestion={setFileQuestion}
              onSubmit={handleSubmit}
              fileError={errors.file}
              questionError={errors.question}
            />
          )}

          {mode === 'repo' && (
            <GithubRepoPane
              repoUrl={repoUrl}
              onChangeRepoUrl={(url) => {
                setRepoUrl(url);
                setErrors((prev) => ({ ...prev, repo: undefined }));
              }}
              question={repoQuestion}
              onChangeQuestion={setRepoQuestion}
              onSubmit={handleSubmit}
              repoError={errors.repo}
              questionError={errors.question}
            />
          )}
        </div>

        {/* Footer with Circular Send-Arrow Button */}
        <div className="litmus-composer__footer">
          <div className="litmus-composer__footer-info">
            <span className="litmus-composer__footer-tip">
              Enter submits &bull; Shift+Enter inserts newline
            </span>
          </div>

          <button
            type="button"
            className="litmus-send-button"
            disabled={!isInputValid() || isSubmitting}
            onClick={handleSubmit}
            aria-label="Initiate adversarial debate"
            title={
              !isInputValid()
                ? 'Fill required fields to start debate'
                : isSubmitting
                ? 'Creating session...'
                : 'Debate the Cause. Run the Fix.'
            }
          >
            <ArrowUp size={20} className="litmus-send-button__icon" />
          </button>
        </div>
      </div>

      {/* Quick Actions Under Composer */}
      <ComposerActions
        onLoadSample={handleLoadSample}
        onClear={handleClear}
        hasInput={hasAnyInput}
      />
    </div>
  );
};
