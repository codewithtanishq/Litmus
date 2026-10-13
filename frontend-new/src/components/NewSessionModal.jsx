import React, { useState } from 'react';
import { X, Code, FileCode, GitBranch, Play, CheckCircle2, AlertCircle, HelpCircle } from 'lucide-react';
import { createSession } from '../services/api';

const SAMPLE_PRESETS = [
  {
    name: "Off-by-One Tail Slice",
    question: "Tail element missing from slice when processing user batch",
    code: `def process_data(items):\n    # Bug: Excludes tail item from processed list\n    return items[0:len(items)-1]\n\ndef test_suite():\n    assert process_data([1, 2, 3]) == [1, 2, 3]`,
    failingTest: `def test_tail():\n    items = [10, 20, 30, 40]\n    assert process_data(items) == [10, 20, 30, 40], "Tail element omitted"`,
    scenarioId: "fix_b_passes",
  },
  {
    name: "Zero-Division Guard",
    question: "ZeroDivisionError thrown during average calculation on empty payload",
    code: `def calculate_average(scores):\n    # Bug: Unhandled zero length collection\n    total = sum(scores)\n    return total / len(scores)\n`,
    failingTest: `def test_empty_scores():\n    assert calculate_average([]) == 0.0, "Empty list must return 0.0"`,
    scenarioId: "fix_b_passes",
  },
  {
    name: "Dictionary KeyError",
    question: "KeyError raised when optional metadata config tag is missing",
    code: `def get_user_role(profile):\n    # Bug: Direct access without fallback\n    return profile["auth"]["role"]\n`,
    failingTest: `def test_missing_role():\n    assert get_user_role({"auth": {}}) == "guest"`,
    scenarioId: "fix_a_passes",
  }
];

export default function NewSessionModal({ isOpen, onClose, onSessionCreated }) {
  const [mode, setMode] = useState('code'); // 'code', 'file', 'repo'
  const [language, setLanguage] = useState('python');
  const [question, setQuestion] = useState('');
  const [code, setCode] = useState('');
  const [fileName, setFileName] = useState('solution.py');
  const [fileContent, setFileContent] = useState('');
  const [repoUrl, setRepoUrl] = useState('');
  const [failingTest, setFailingTest] = useState('');
  const [expectedBehavior, setExpectedBehavior] = useState('');
  const [errorMessage, setErrorMessage] = useState('');
  const [scenarioId, setScenarioId] = useState('fix_b_passes');
  const [isDemo, setIsDemo] = useState(false);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState(null);

  if (!isOpen) return null;

  const loadPreset = (preset) => {
    setQuestion(preset.question);
    setCode(preset.code);
    setFailingTest(preset.failingTest);
    setScenarioId(preset.scenarioId);
    setError(null);
  };

  const handleFileUpload = (e) => {
    const file = e.target.files?.[0];
    if (file) {
      setFileName(file.name);
      const reader = new FileReader();
      reader.onload = (event) => {
        const text = event.target?.result;
        setFileContent(text);
        if (!code) setCode(text);
      };
      reader.readAsText(file);
    }
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!question.trim()) {
      setError("Please describe the bug or question to be adjudicated.");
      return;
    }

    const effectiveCode = mode === 'code' ? code : (fileContent || code);
    if (!effectiveCode.trim() && mode !== 'repo') {
      setError("Please provide the buggy code snippet or upload a file.");
      return;
    }

    setIsSubmitting(true);
    setError(null);

    try {
      const payload = {
        mode,
        language,
        question: question.trim(),
        code: effectiveCode,
        fileName: mode === 'file' ? fileName : 'solution.py',
        fileSize: effectiveCode.length,
        fileContent: mode === 'file' ? effectiveCode : null,
        repoUrl: mode === 'repo' ? repoUrl : null,
        details: {
          failingTest: failingTest.trim() || undefined,
          expectedBehavior: expectedBehavior.trim() || undefined,
          errorMessage: errorMessage.trim() || undefined,
        },
        scenarioId,
        isDemo,
      };

      const session = await createSession(payload);
      setIsSubmitting(false);
      onSessionCreated(session);
      onClose();
    } catch (err) {
      setIsSubmitting(false);
      setError(err.message || "Failed to create debugging session");
    }
  };

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center p-4 overflow-y-auto bg-[#1E1856]/40 backdrop-blur-sm animate-fadeIn">
      <div className="card-surface max-w-2xl w-full p-6 sm:p-8 relative shadow-2xl max-h-[90vh] overflow-y-auto">
        {/* Header */}
        <div className="flex items-center justify-between pb-4 border-b border-[#E1DDFA]">
          <div>
            <h2 className="text-xl font-semibold text-[#1E1856] tracking-tight">Initiate Courtroom Adjudication</h2>
            <p className="text-xs text-[#6B6894] mt-0.5">Submit code for multi-agent adversarial debate and sandboxed verification.</p>
          </div>
          <button
            onClick={onClose}
            className="w-8 h-8 rounded-full flex items-center justify-center text-[#6B6894] hover:text-[#1E1856] hover:bg-[#EEEBFF] transition-colors"
          >
            <X className="w-5 h-5" />
          </button>
        </div>

        {/* Quick Presets */}
        <div className="my-4">
          <label className="text-xs font-medium text-[#6B6894] uppercase tracking-wider block mb-2">
            Load Quick Presets
          </label>
          <div className="flex flex-wrap gap-2">
            {SAMPLE_PRESETS.map((preset, idx) => (
              <button
                key={idx}
                type="button"
                onClick={() => loadPreset(preset)}
                className="text-xs px-3 py-1.5 rounded-full bg-[#EEEBFF] text-[#5F4DCB] hover:bg-[#E1DDFA] border border-[#E1DDFA] transition-all font-medium"
              >
                {preset.name}
              </button>
            ))}
          </div>
        </div>

        {error && (
          <div className="p-3 mb-4 rounded-xl bg-[#FDF2F2] border border-[#F9C6C7] text-[#D13438] text-xs flex items-center space-x-2">
            <AlertCircle className="w-4 h-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          {/* Intake Mode selector */}
          <div>
            <label className="text-xs font-medium text-[#1E1856] block mb-1.5">Intake Mode</label>
            <div className="grid grid-cols-3 gap-2">
              {[
                { id: 'code', label: 'Direct Code', icon: Code },
                { id: 'file', label: 'File Upload', icon: FileCode },
                { id: 'repo', label: 'Git Repo', icon: GitBranch },
              ].map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setMode(id)}
                  className={`flex items-center justify-center space-x-2 py-2 px-3 rounded-xl text-xs font-medium border transition-all ${
                    mode === id
                      ? 'bg-[#EEEBFF] text-[#5F4DCB] border-[#5F4DCB]'
                      : 'bg-white text-[#6B6894] border-[#E1DDFA] hover:bg-[#F6F5FF]'
                  }`}
                >
                  <Icon className="w-3.5 h-3.5" />
                  <span>{label}</span>
                </button>
              ))}
            </div>
          </div>

          {/* Bug description / question */}
          <div>
            <label className="text-xs font-medium text-[#1E1856] block mb-1">
              Bug Description or Observed Failure <span className="text-[#D13438]">*</span>
            </label>
            <input
              type="text"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="e.g. Off-by-one tail item truncation in data processing"
              className="w-full px-3.5 py-2 text-sm rounded-xl border border-[#E1DDFA] focus:outline-none focus:ring-2 focus:ring-[#5F4DCB]/30 bg-[#F6F5FF]/50"
            />
          </div>

          {/* Mode-specific input */}
          {mode === 'code' && (
            <div>
              <div className="flex items-center justify-between mb-1">
                <label className="text-xs font-medium text-[#1E1856]">
                  Buggy Source Code <span className="text-[#D13438]">*</span>
                </label>
                <span className="text-[11px] text-[#6B6894]">Python</span>
              </div>
              <textarea
                rows={6}
                value={code}
                onChange={(e) => setCode(e.target.value)}
                placeholder="def process_items(list): ..."
                className="w-full font-mono text-xs px-3.5 py-2.5 rounded-xl border border-[#E1DDFA] focus:outline-none focus:ring-2 focus:ring-[#5F4DCB]/30 bg-[#F6F5FF]/60"
              />
            </div>
          )}

          {mode === 'file' && (
            <div>
              <label className="text-xs font-medium text-[#1E1856] block mb-1">Upload Python Script</label>
              <input
                type="file"
                accept=".py,.txt"
                onChange={handleFileUpload}
                className="w-full text-xs text-[#6B6894] file:mr-3 file:py-1.5 file:px-3 file:rounded-full file:border-0 file:text-xs file:font-medium file:bg-[#EEEBFF] file:text-[#5F4DCB] hover:file:bg-[#E1DDFA]"
              />
              {fileContent && (
                <div className="mt-2 p-2 bg-[#F6F5FF] rounded-lg border border-[#E1DDFA]">
                  <div className="text-[11px] text-[#6B6894] mb-1 font-medium">{fileName} ({fileContent.length} bytes)</div>
                  <pre className="text-[11px] font-mono text-[#1E1856] max-h-32 overflow-y-auto">{fileContent}</pre>
                </div>
              )}
            </div>
          )}

          {mode === 'repo' && (
            <div>
              <label className="text-xs font-medium text-[#1E1856] block mb-1">Repository URL</label>
              <input
                type="url"
                value={repoUrl}
                onChange={(e) => setRepoUrl(e.target.value)}
                placeholder="https://github.com/org/repo"
                className="w-full px-3.5 py-2 text-sm rounded-xl border border-[#E1DDFA] focus:outline-none focus:ring-2 focus:ring-[#5F4DCB]/30 bg-[#F6F5FF]/50"
              />
            </div>
          )}

          {/* Failing test script */}
          <div>
            <label className="text-xs font-medium text-[#1E1856] block mb-1">
              Reproduction Test Suite (Optional)
            </label>
            <textarea
              rows={3}
              value={failingTest}
              onChange={(e) => setFailingTest(e.target.value)}
              placeholder="def test_scenario(): assert True"
              className="w-full font-mono text-xs px-3.5 py-2 rounded-xl border border-[#E1DDFA] focus:outline-none focus:ring-2 focus:ring-[#5F4DCB]/30 bg-[#F6F5FF]/60"
            />
          </div>

          {/* Scenario & Demo options */}
          <div className="p-3 rounded-xl bg-[#EEEBFF]/50 border border-[#E1DDFA] flex flex-wrap items-center justify-between gap-3 text-xs">
            <div>
              <span className="font-medium text-[#1E1856] block">Adjudication Sandbox Target</span>
              <span className="text-[#6B6894] text-[11px]">Select simulated outcome for deterministic validation</span>
            </div>
            <select
              value={scenarioId}
              onChange={(e) => setScenarioId(e.target.value)}
              className="bg-white border border-[#E1DDFA] rounded-lg px-2.5 py-1 text-xs text-[#1E1856] focus:outline-none"
            >
              <option value="fix_b_passes">Fix B Passes (Defender Wins)</option>
              <option value="fix_a_passes">Fix A Passes (Prosecutor Wins)</option>
              <option value="round2_resolved">Round 2 Multi-Round Resolution</option>
            </select>
          </div>

          {/* Footer controls */}
          <div className="pt-3 border-t border-[#E1DDFA] flex items-center justify-end space-x-3">
            <button
              type="button"
              onClick={onClose}
              className="btn-pill px-4 py-2 text-xs font-medium text-[#6B6894] hover:text-[#1E1856] transition-colors"
            >
              Cancel
            </button>
            <button
              type="submit"
              disabled={isSubmitting}
              className="btn-pill btn-primary text-xs px-5 py-2.5 flex items-center space-x-1.5 shadow-sm disabled:opacity-50"
            >
              {isSubmitting ? (
                <>
                  <span className="w-3.5 h-3.5 border-2 border-white/30 border-t-white rounded-full animate-spin" />
                  <span>Submitting...</span>
                </>
              ) : (
                <>
                  <Play className="w-3.5 h-3.5 fill-current" />
                  <span>Begin Courtroom Debate</span>
                </>
              )}
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}
