import { useState, useId } from 'react';
import { Copy, Check } from 'lucide-react';
import './CodeHighlighter.css';

interface CodeHighlighterProps {
  code: string;
  language?: string;
  showLineNumbers?: boolean;
  maxHeight?: string;
  ariaLabel?: string;
  className?: string;
}

const KEYWORDS = new Set([
  'def', 'class', 'return', 'if', 'elif', 'else', 'while', 'for', 'in', 'break', 'continue',
  'import', 'from', 'as', 'try', 'except', 'finally', 'raise', 'with', 'async', 'await',
  'assert', 'pass', 'lambda', 'yield', 'global', 'nonlocal', 'is', 'not', 'and', 'or',
  'function', 'const', 'let', 'var', 'export', 'default', 'interface', 'type', 'enum',
  'package', 'func', 'struct', 'impl', 'fn', 'pub', 'mut', 'val', 'val_'
]);

const LITERALS = new Set([
  'True', 'False', 'None', 'true', 'false', 'null', 'undefined', 'self', 'this'
]);

function highlightToken(token: string): { type: string; text: string } {
  if (KEYWORDS.has(token)) return { type: 'keyword', text: token };
  if (LITERALS.has(token)) return { type: 'literal', text: token };
  if (/^\d+(\.\d+)?$/.test(token)) return { type: 'number', text: token };
  return { type: 'plain', text: token };
}

function parseLine(line: string) {
  const parts: Array<{ type: string; text: string }> = [];
  let i = 0;

  while (i < line.length) {
    // Comments
    if (line[i] === '#' || (line[i] === '/' && line[i + 1] === '/')) {
      parts.push({ type: 'comment', text: line.slice(i) });
      break;
    }

    // Strings
    if (line[i] === '"' || line[i] === "'") {
      const quote = line[i];
      let end = i + 1;
      while (end < line.length && line[end] !== quote) {
        if (line[end] === '\\') end++;
        end++;
      }
      if (end < line.length) end++; // consume matching quote
      parts.push({ type: 'string', text: line.slice(i, end) });
      i = end;
      continue;
    }

    // Word tokens (identifiers, keywords)
    if (/[a-zA-Z_]/.test(line[i])) {
      let end = i + 1;
      while (end < line.length && /[a-zA-Z0-9_]/.test(line[end])) {
        end++;
      }
      const word = line.slice(i, end);
      parts.push(highlightToken(word));
      i = end;
      continue;
    }

    // Numbers
    if (/[0-9]/.test(line[i])) {
      let end = i + 1;
      while (end < line.length && /[0-9.]/.test(line[end])) {
        end++;
      }
      parts.push({ type: 'number', text: line.slice(i, end) });
      i = end;
      continue;
    }

    // Punctuation / Operators / Whitespace
    parts.push({ type: 'plain', text: line[i] });
    i++;
  }

  return parts;
}

export const CodeHighlighter = ({
  code,
  language = 'python',
  showLineNumbers = true,
  maxHeight,
  ariaLabel = 'Source code viewer',
  className = '',
}: CodeHighlighterProps) => {
  const [copied, setCopied] = useState(false);
  const codeId = useId();

  const lines = (code || '').split('\n');

  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      // fallback
    }
  };

  return (
    <div 
      className={`litmus-code-highlighter ${className}`}
      style={{ maxHeight }}
      role="region"
      aria-label={ariaLabel}
    >
      <div className="litmus-code-highlighter__bar">
        <span className="litmus-code-highlighter__lang-tag">{language}</span>
        <button
          type="button"
          className="litmus-code-highlighter__copy-btn"
          onClick={handleCopy}
          aria-label="Copy code to clipboard"
          title="Copy code"
        >
          {copied ? <Check size={13} className="litmus-copy-icon--ok" /> : <Copy size={13} />}
          <span>{copied ? 'Copied!' : 'Copy'}</span>
        </button>
      </div>

      <div className="litmus-code-highlighter__viewport" id={codeId}>
        <pre className="litmus-code-highlighter__pre">
          {lines.map((lineText, idx) => {
            const lineNum = idx + 1;
            const tokens = parseLine(lineText);
            return (
              <div key={lineNum} className="litmus-code-highlighter__line">
                {showLineNumbers && (
                  <span className="litmus-code-highlighter__lineno" aria-hidden="true">
                    {lineNum}
                  </span>
                )}
                <span className="litmus-code-highlighter__content">
                  {tokens.length > 0 ? (
                    tokens.map((tok, tIdx) => (
                      <span key={tIdx} className={`tok-${tok.type}`}>
                        {tok.text}
                      </span>
                    ))
                  ) : (
                    '\u00A0'
                  )}
                </span>
              </div>
            );
          })}
        </pre>
      </div>
    </div>
  );
};
