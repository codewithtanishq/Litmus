import { useRef, useId } from 'react';
import type { KeyboardEvent } from 'react';
import './CodeEditor.css';

interface CodeEditorProps {
  value: string;
  onChange: (value: string) => void;
  language?: string;
  placeholder?: string;
  readOnly?: boolean;
  minHeight?: string;
  maxHeight?: string;
  ariaLabel?: string;
  className?: string;
}

export const CodeEditor = ({
  value,
  onChange,
  language = 'python',
  placeholder = '# Paste buggy source code here...',
  readOnly = false,
  minHeight = '180px',
  maxHeight = '380px',
  ariaLabel = 'Code editor',
  className = '',
}: CodeEditorProps) => {
  const textareaRef = useRef<HTMLTextAreaElement>(null);
  const lineNumbersRef = useRef<HTMLDivElement>(null);
  const textareaId = useId();

  // Compute line count
  const lines = value.split('\n');
  const lineCount = Math.max(lines.length, 1);

  // Sync scroll between textarea and line numbers
  const handleScroll = () => {
    if (textareaRef.current && lineNumbersRef.current) {
      lineNumbersRef.current.scrollTop = textareaRef.current.scrollTop;
    }
  };

  // Handle Tab key to insert 2 spaces instead of blurring
  const handleKeyDown = (e: KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === 'Tab' && !readOnly) {
      e.preventDefault();
      const textarea = textareaRef.current;
      if (!textarea) return;

      const start = textarea.selectionStart;
      const end = textarea.selectionEnd;

      // Insert 2 spaces
      const tabSpaces = '  ';
      const newValue = value.substring(0, start) + tabSpaces + value.substring(end);
      onChange(newValue);

      // Restore cursor position after state update
      window.requestAnimationFrame(() => {
        textarea.selectionStart = textarea.selectionEnd = start + tabSpaces.length;
      });
    }
  };

  return (
    <div 
      className={`litmus-code-editor ${className}`} 
      style={{ minHeight, maxHeight }}
    >
      <div 
        ref={lineNumbersRef}
        className="litmus-code-editor__gutter"
        aria-hidden="true"
      >
        {Array.from({ length: lineCount }).map((_, i) => (
          <div key={i + 1} className="litmus-code-editor__line-number">
            {i + 1}
          </div>
        ))}
      </div>

      <div className="litmus-code-editor__body">
        <textarea
          id={textareaId}
          ref={textareaRef}
          className="litmus-code-editor__textarea"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          onKeyDown={handleKeyDown}
          onScroll={handleScroll}
          placeholder={placeholder}
          readOnly={readOnly}
          spellCheck={false}
          autoCapitalize="off"
          autoComplete="off"
          autoCorrect="off"
          aria-label={ariaLabel}
          data-language={language}
        />
      </div>
    </div>
  );
};
