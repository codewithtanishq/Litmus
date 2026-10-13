import { useRef, useState } from 'react';
import type { ChangeEvent, DragEvent, KeyboardEvent } from 'react';
import { UploadCloud, FileCode, X, AlertCircle } from 'lucide-react';
import './UploadFilePane.css';

const ALLOWED_EXTENSIONS = ['.py', '.js', '.ts', '.java', '.cpp', '.c', '.txt', '.zip'];
const MAX_FILE_SIZE_BYTES = 1024 * 1024; // 1 MB

interface UploadFilePaneProps {
  fileName: string;
  fileSize?: number;
  fileContent?: string;
  onFileSelect: (data: { name: string; size: number; content?: string }) => void;
  onFileRemove: () => void;
  question: string;
  onChangeQuestion: (q: string) => void;
  onSubmit: () => void;
  fileError?: string;
  questionError?: string;
}

export const UploadFilePane = ({
  fileName,
  fileSize,
  fileContent,
  onFileSelect,
  onFileRemove,
  question,
  onChangeQuestion,
  onSubmit,
  fileError,
  questionError,
}: UploadFilePaneProps) => {
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [localFileError, setLocalFileError] = useState<string | null>(null);

  const formatFileSize = (bytes: number): string => {
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / (1024 * 1024)).toFixed(2)} MB`;
  };

  const processFile = (file: File) => {
    setLocalFileError(null);
    const ext = '.' + file.name.split('.').pop()?.toLowerCase();

    // Check extension
    if (!ALLOWED_EXTENSIONS.includes(ext)) {
      setLocalFileError(
        `Unsupported file type "${ext}". Supported types: ${ALLOWED_EXTENSIONS.join(', ')}`
      );
      return;
    }

    // Check size limit (1 MB)
    if (file.size > MAX_FILE_SIZE_BYTES) {
      setLocalFileError(
        `File exceeds maximum limit of 1 MB (${formatFileSize(file.size)}). Please upload a smaller file.`
      );
      return;
    }

    // If .zip, don't read as text
    if (ext === '.zip') {
      onFileSelect({
        name: file.name,
        size: file.size,
        content: '[Zip archive container metadata recorded. Repository unpack simulated in sandbox.]',
      });
      return;
    }

    // Read text file
    const reader = new FileReader();
    reader.onload = (e) => {
      const text = (e.target?.result as string) || '';
      onFileSelect({
        name: file.name,
        size: file.size,
        content: text,
      });
    };
    reader.onerror = () => {
      setLocalFileError('Failed to read text contents of the selected file.');
    };
    reader.readAsText(file);
  };

  const handleFileChange = (e: ChangeEvent<HTMLInputElement>) => {
    if (e.target.files && e.target.files[0]) {
      processFile(e.target.files[0]);
    }
  };

  const handleDrop = (e: DragEvent<HTMLDivElement>) => {
    e.preventDefault();
    setIsDragging(false);
    if (e.dataTransfer.files && e.dataTransfer.files[0]) {
      processFile(e.dataTransfer.files[0]);
    }
  };

  const handleQuestionKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      onSubmit();
    }
  };

  const activeError = fileError || localFileError;

  return (
    <div className="upload-file-pane">
      {/* File Drop Area */}
      <div className="upload-file-pane__section">
        <label className="upload-file-pane__label">
          Source File: <span className="field-required">*</span>
        </label>

        {!fileName ? (
          <div
            className={`file-drop-zone ${isDragging ? 'file-drop-zone--dragging' : ''} ${activeError ? 'file-drop-zone--error' : ''}`}
            onDragOver={(e) => { e.preventDefault(); setIsDragging(true); }}
            onDragLeave={() => setIsDragging(false)}
            onDrop={handleDrop}
            onClick={() => fileInputRef.current?.click()}
            role="button"
            tabIndex={0}
            aria-label="Upload source file"
            onKeyDown={(e) => { if (e.key === 'Enter' || e.key === ' ') fileInputRef.current?.click(); }}
          >
            <input
              type="file"
              ref={fileInputRef}
              style={{ display: 'none' }}
              onChange={handleFileChange}
              accept=".py,.js,.ts,.java,.cpp,.c,.txt,.zip"
            />
            <UploadCloud size={28} className="file-drop-zone__icon" />
            <div className="file-drop-zone__text">
              <span className="file-drop-zone__title">Click to upload or drag & drop</span>
              <span className="file-drop-zone__subtitle">
                .py, .js, .ts, .java, .cpp, .c, .txt, .zip (Max 1 MB)
              </span>
            </div>
          </div>
        ) : (
          <div className="file-selected-card">
            <div className="file-selected-card__info">
              <FileCode size={20} className="file-selected-card__icon" />
              <div className="file-selected-card__meta">
                <span className="file-selected-card__name">{fileName}</span>
                <span className="file-selected-card__size">
                  {fileSize ? formatFileSize(fileSize) : 'Text source'} &bull; Ready for debate
                </span>
              </div>
            </div>
            <button
              type="button"
              className="file-selected-card__remove"
              onClick={onFileRemove}
              aria-label="Remove selected file"
              title="Remove file"
            >
              <X size={16} />
            </button>
          </div>
        )}

        {activeError && (
          <div className="composer-inline-error" role="alert">
            <AlertCircle size={13} />
            <span>{activeError}</span>
          </div>
        )}

        {fileName && fileContent && fileName.endsWith('.zip') && (
          <div className="zip-notice-box">
            <span>Note: Zip archive detected. Sandbox execution will unpack and inspect repository contents.</span>
          </div>
        )}
      </div>

      {/* Question Field */}
      <div className="upload-file-pane__section">
        <div className="upload-file-pane__section-header">
          <label htmlFor="file-question-input" className="upload-file-pane__label">
            Debugging Question / What went wrong?: <span className="field-required">*</span>
          </label>
          <span className="upload-file-pane__hint">Press Enter to submit &bull; Shift+Enter for new line</span>
        </div>
        <textarea
          id="file-question-input"
          className={`upload-file-pane__question-input ${questionError ? 'upload-file-pane__question-input--error' : ''}`}
          rows={2}
          value={question}
          onChange={(e) => onChangeQuestion(e.target.value)}
          onKeyDown={handleQuestionKeyDown}
          placeholder="e.g. Inspect this file for concurrency deadlocks and off-by-one errors"
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
