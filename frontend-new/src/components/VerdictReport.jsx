import React, { useState } from 'react';
import { 
  CheckCircle2, 
  XCircle, 
  Copy, 
  Check, 
  FileCode, 
  Scale, 
  ShieldAlert, 
  Terminal, 
  ArrowLeft,
  ChevronDown,
  ChevronUp
} from 'lucide-react';

export default function VerdictReport({ result, onBackToArena }) {
  const [copied, setCopied] = useState(false);
  const [expandedRound, setExpandedRound] = useState(0);

  if (!result) return null;

  const isVerified = result.status === 'test_verified';

  const handleCopyCode = () => {
    if (result.correctedCode) {
      navigator.clipboard.writeText(result.correctedCode);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    }
  };

  return (
    <div className="space-y-6 max-w-5xl mx-auto animate-fadeIn">
      {/* Top Navigation */}
      <div className="flex items-center justify-between">
        <button
          onClick={onBackToArena}
          className="btn-pill btn-secondary text-xs px-3.5 py-1.5 flex items-center space-x-1.5"
        >
          <ArrowLeft className="w-3.5 h-3.5" />
          <span>Back to Courtroom Arena</span>
        </button>

        <span className="text-xs text-[#6B6894] font-mono">
          Session ID: {result.sessionId}
        </span>
      </div>

      {/* Hero Verdict Status Banner */}
      <div className={`card-surface p-6 sm:p-8 border-l-8 ${
        isVerified ? 'border-l-[#2E7D5B]' : 'border-l-[#D13438]'
      }`}>
        <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
          <div className="flex items-start space-x-4">
            <div className={`w-12 h-12 rounded-2xl flex items-center justify-center shrink-0 ${
              isVerified ? 'bg-[#EDF7F2] text-[#2E7D5B]' : 'bg-[#FDF2F2] text-[#D13438]'
            }`}>
              {isVerified ? <CheckCircle2 className="w-7 h-7" /> : <XCircle className="w-7 h-7" />}
            </div>
            <div>
              <div className="flex items-center space-x-2">
                <span className={`text-xs px-2.5 py-0.5 rounded-full font-semibold uppercase tracking-wider ${
                  isVerified 
                    ? 'bg-[#EDF7F2] text-[#2E7D5B] border border-[#BFE7D3]' 
                    : 'bg-[#FDF2F2] text-[#D13438] border border-[#F9C6C7]'
                }`}>
                  {isVerified ? 'Deterministic Verdict: Verified' : 'Adjudication: Unresolved'}
                </span>
              </div>
              <h2 className="text-2xl font-light text-[#1E1856] tracking-tight mt-1">
                {isVerified ? 'Court Approved Patch Solution' : 'Bug Diagnosis Requires Further Refinement'}
              </h2>
              <p className="text-xs sm:text-sm text-[#6B6894] mt-1.5 max-w-2xl leading-relaxed">
                {result.summary}
              </p>
            </div>
          </div>

          {/* Test metrics */}
          <div className="flex items-center space-x-3 sm:border-l sm:border-[#E1DDFA] sm:pl-6">
            <div className="text-center">
              <span className="block text-2xl font-semibold text-[#D13438]">
                {result.initialFailedTests ?? 1}
              </span>
              <span className="text-[11px] text-[#6B6894]">Initial Failures</span>
            </div>
            <div className="text-[#6B6894] font-light text-xl">→</div>
            <div className="text-center">
              <span className={`block text-2xl font-semibold ${
                result.finalFailedTests === 0 ? 'text-[#2E7D5B]' : 'text-[#D13438]'
              }`}>
                {result.finalFailedTests ?? 0}
              </span>
              <span className="text-[11px] text-[#6B6894]">Final Failures</span>
            </div>
          </div>
        </div>
      </div>

      {/* Corrected Code Display */}
      {result.correctedCode && (
        <div className="card-surface p-6">
          <div className="flex items-center justify-between pb-3 border-b border-[#E1DDFA]">
            <div className="flex items-center space-x-2">
              <FileCode className="w-4 h-4 text-[#5F4DCB]" />
              <h3 className="text-sm font-semibold text-[#1E1856]">Adjudicated Corrected Source Code</h3>
            </div>
            <button
              onClick={handleCopyCode}
              className="btn-pill btn-secondary text-xs px-3 py-1 flex items-center space-x-1.5"
            >
              {copied ? <Check className="w-3.5 h-3.5 text-[#2E7D5B]" /> : <Copy className="w-3.5 h-3.5" />}
              <span>{copied ? 'Copied' : 'Copy Code'}</span>
            </button>
          </div>
          <div className="mt-4">
            <pre className="p-4 rounded-xl bg-[#221B6D] text-[#EEEBFF] font-mono text-xs overflow-x-auto border border-[#3B2A9D] leading-relaxed">
              {result.correctedCode}
            </pre>
          </div>
        </div>
      )}

      {/* Identified Errors Breakdown */}
      {result.errors && result.errors.length > 0 && (
        <div className="card-surface p-6 space-y-4">
          <h3 className="text-sm font-semibold text-[#1E1856]">Identified Defects & Resolutions</h3>
          <div className="space-y-3">
            {result.errors.map((err, idx) => (
              <div key={idx} className="p-4 rounded-xl bg-[#F6F5FF] border border-[#E1DDFA] space-y-2">
                <div className="flex items-center justify-between">
                  <span className="text-xs font-semibold text-[#1E1856]">{err.title}</span>
                  <span className="text-[11px] font-mono text-[#6B6894]">
                    {err.file} {err.line ? `: line ${err.line}` : ''}
                  </span>
                </div>
                <p className="text-xs text-[#6B6894]">{err.explanation}</p>
                {err.originalCode && err.correctedCode && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 pt-2 text-[11px] font-mono">
                    <div className="p-2 rounded bg-[#FDF2F2] border border-[#F9C6C7] text-[#D13438]">
                      <div className="font-semibold mb-0.5 text-[10px]">ORIGINAL:</div>
                      {err.originalCode}
                    </div>
                    <div className="p-2 rounded bg-[#EDF7F2] border border-[#BFE7D3] text-[#2E7D5B]">
                      <div className="font-semibold mb-0.5 text-[10px]">CORRECTED:</div>
                      {err.correctedCode}
                    </div>
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Trial Rounds Debate Breakdown */}
      {result.rounds && result.rounds.length > 0 && (
        <div className="card-surface p-6 space-y-4">
          <h3 className="text-sm font-semibold text-[#1E1856]">Courtroom Debate & Empirical Evidence Log</h3>
          <div className="space-y-4">
            {result.rounds.map((rnd, idx) => (
              <div key={idx} className="rounded-xl border border-[#E1DDFA] overflow-hidden">
                <div 
                  onClick={() => setExpandedRound(expandedRound === idx ? -1 : idx)}
                  className="p-3.5 bg-[#EEEBFF]/60 flex items-center justify-between cursor-pointer hover:bg-[#EEEBFF] transition-colors"
                >
                  <div className="flex items-center space-x-2">
                    <Scale className="w-4 h-4 text-[#5F4DCB]" />
                    <span className="text-xs font-semibold text-[#1E1856]">Round {rnd.roundNumber || idx + 1} Adjudication</span>
                    {rnd.decision && (
                      <span className="text-[10px] font-medium px-2 py-0.5 rounded-full bg-white text-[#5F4DCB] border border-[#E1DDFA]">
                        {rnd.decision.verdict}
                      </span>
                    )}
                  </div>
                  {expandedRound === idx ? <ChevronUp className="w-4 h-4 text-[#6B6894]" /> : <ChevronDown className="w-4 h-4 text-[#6B6894]" />}
                </div>

                {expandedRound === idx && (
                  <div className="p-4 space-y-4 text-xs bg-white">
                    {/* Prosecutor Claim */}
                    <div className="p-3 rounded-lg bg-[#F6F5FF] border border-[#E1DDFA]">
                      <span className="font-semibold text-[#1E1856] block mb-1">Prosecutor Accusation & Fix A:</span>
                      <p className="text-[#6B6894] mb-2">{rnd.prosecutorClaim}</p>
                      {rnd.candidateA?.sandboxRun && (
                        <div className="text-[11px] font-mono text-[#D13438] bg-[#FDF2F2] p-2 rounded border border-[#F9C6C7]">
                          Sandbox Result: {rnd.candidateA.sandboxRun.status.toUpperCase()} (Exit {rnd.candidateA.sandboxRun.exitCode}) — {rnd.candidateA.sandboxRun.logs}
                        </div>
                      )}
                    </div>

                    {/* Defender Challenge */}
                    <div className="p-3 rounded-lg bg-[#F6F5FF] border border-[#E1DDFA]">
                      <span className="font-semibold text-[#1E1856] block mb-1">Defender Critique & Fix B:</span>
                      <p className="text-[#6B6894] mb-2">{rnd.defenderChallenge}</p>
                      {rnd.candidateB?.sandboxRun && (
                        <div className="text-[11px] font-mono text-[#2E7D5B] bg-[#EDF7F2] p-2 rounded border border-[#BFE7D3]">
                          Sandbox Result: {rnd.candidateB.sandboxRun.status.toUpperCase()} (Exit {rnd.candidateB.sandboxRun.exitCode}) — {rnd.candidateB.sandboxRun.logs}
                        </div>
                      )}
                    </div>

                    {/* Decision */}
                    {rnd.decision && (
                      <div className="p-3 rounded-lg bg-[#EEEBFF] border border-[#E1DDFA]">
                        <span className="font-semibold text-[#5F4DCB] block mb-1">Judge Decree:</span>
                        <p className="text-[#1E1856]">{rnd.decision.rationale}</p>
                      </div>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Rejected Attempts & Constraint Ledger */}
      {result.rejectedAttempts && result.rejectedAttempts.length > 0 && (
        <div className="card-surface p-6 space-y-3">
          <div className="flex items-center space-x-2 text-[#D13438]">
            <ShieldAlert className="w-4 h-4" />
            <h3 className="text-sm font-semibold text-[#1E1856]">Constraint Ledger: Recorded Rejected Fixes</h3>
          </div>
          <p className="text-xs text-[#6B6894]">
            These candidate patches were discarded based on empirical sandbox failure evidence and prevented from recurring in subsequent debate rounds.
          </p>
          <div className="space-y-2 mt-2">
            {result.rejectedAttempts.map((rej, i) => (
              <div key={i} className="p-3 rounded-xl bg-[#FDF2F2] border border-[#F9C6C7] text-xs">
                <div className="font-semibold text-[#D13438] capitalize mb-1">
                  {rej.author} Candidate ({rej.attemptId}):
                </div>
                <div className="text-[#1E1856]">{rej.failureReason}</div>
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
