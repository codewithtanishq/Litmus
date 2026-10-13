import React, { useState, useEffect } from 'react';
import { Search, Scale, ArrowRight, RefreshCw, Clock, CheckCircle2, AlertCircle, FileCode } from 'lucide-react';
import { fetchSessions } from '../services/api';
import EmptyState from './EmptyState';

export default function SessionHistory({ onSelectSession, onNewCaseClick }) {
  const [sessions, setSessions] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [searchQuery, setSearchQuery] = useState('');

  const loadSessions = async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await fetchSessions();
      setSessions(data);
    } catch (err) {
      setError(err.message || "Failed to load courtroom trials");
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadSessions();
  }, []);

  const filteredSessions = sessions.filter((s) => {
    const q = searchQuery.toLowerCase();
    return (
      (s.title && s.title.toLowerCase().includes(q)) ||
      (s.question && s.question.toLowerCase().includes(q)) ||
      (s.id && s.id.toLowerCase().includes(q))
    );
  });

  return (
    <div className="space-y-6 max-w-6xl mx-auto animate-fadeIn">
      {/* Header bar */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h2 className="text-xl font-semibold text-[#1E1856] tracking-tight">Courtroom Archive & Historical Trials</h2>
          <p className="text-xs text-[#6B6894] mt-0.5">Persistent records of multi-agent debug sessions stored in SQLite repository.</p>
        </div>

        <div className="flex items-center space-x-2">
          {/* Search box */}
          <div className="relative">
            <Search className="w-3.5 h-3.5 text-[#6B6894] absolute left-3 top-1/2 -translate-y-1/2" />
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              placeholder="Search trials by bug or ID..."
              className="pl-8 pr-3 py-1.5 text-xs rounded-full border border-[#E1DDFA] bg-white focus:outline-none focus:ring-2 focus:ring-[#5F4DCB]/30 w-52 sm:w-64"
            />
          </div>

          <button
            onClick={loadSessions}
            disabled={loading}
            className="w-8 h-8 rounded-full border border-[#E1DDFA] bg-white text-[#6B6894] hover:text-[#1E1856] flex items-center justify-center transition-colors disabled:opacity-50"
            title="Refresh history"
          >
            <RefreshCw className={`w-3.5 h-3.5 ${loading ? 'animate-spin' : ''}`} />
          </button>
        </div>
      </div>

      {error && (
        <div className="p-3.5 rounded-xl bg-[#FDF2F2] border border-[#F9C6C7] text-[#D13438] text-xs flex items-center space-x-2">
          <AlertCircle className="w-4 h-4 shrink-0" />
          <span>{error}</span>
        </div>
      )}

      {loading ? (
        <div className="card-surface p-12 text-center">
          <div className="w-6 h-6 border-2 border-[#5F4DCB] border-t-transparent rounded-full animate-spin mx-auto mb-3" />
          <p className="text-xs text-[#6B6894]">Loading trials from SQLite repository...</p>
        </div>
      ) : filteredSessions.length === 0 ? (
        <EmptyState
          title={searchQuery ? "No Matching Trials Found" : "No Trials in Court Archive"}
          description={
            searchQuery
              ? `No sessions matched "${searchQuery}". Try a different keyword.`
              : "No historical debugging trials exist yet. Initiate your first case to see it archived here."
          }
          actionText="Open First Case"
          onAction={onNewCaseClick}
        />
      ) : (
        <div className="card-surface overflow-hidden">
          <div className="overflow-x-auto">
            <table className="w-full text-left border-collapse text-xs">
              <thead>
                <tr className="bg-[#EEEBFF]/60 border-b border-[#E1DDFA] text-[#6B6894]">
                  <th className="py-3 px-4 font-medium">Session ID & Case</th>
                  <th className="py-3 px-4 font-medium">Language</th>
                  <th className="py-3 px-4 font-medium">Mode</th>
                  <th className="py-3 px-4 font-medium">Status</th>
                  <th className="py-3 px-4 font-medium">Date Initiated</th>
                  <th className="py-3 px-4 font-medium text-right">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-[#E1DDFA]">
                {filteredSessions.map((s) => {
                  const isVerified = s.status === 'test_verified';
                  return (
                    <tr 
                      key={s.id} 
                      className="hover:bg-[#F6F5FF]/60 transition-colors cursor-pointer group"
                      onClick={() => onSelectSession(s)}
                    >
                      <td className="py-3.5 px-4">
                        <div className="font-medium text-[#1E1856] text-xs group-hover:text-[#5F4DCB] transition-colors max-w-sm truncate">
                          {s.question || s.title}
                        </div>
                        <div className="font-mono text-[10px] text-[#6B6894] mt-0.5">
                          {s.id}
                        </div>
                      </td>
                      <td className="py-3.5 px-4 font-mono text-[11px] text-[#1E1856] capitalize">
                        {s.language || 'python'}
                      </td>
                      <td className="py-3.5 px-4">
                        <span className="text-[11px] px-2 py-0.5 rounded-full bg-[#EEEBFF] text-[#5F4DCB] border border-[#E1DDFA]">
                          {s.mode || 'code'}
                        </span>
                      </td>
                      <td className="py-3.5 px-4">
                        <span className={`text-[11px] px-2.5 py-0.5 rounded-full font-medium inline-flex items-center space-x-1 ${
                          isVerified
                            ? 'bg-[#EDF7F2] text-[#2E7D5B] border border-[#BFE7D3]'
                            : 'bg-[#EEEBFF] text-[#5F4DCB] border border-[#E1DDFA]'
                        }`}>
                          <span className={`w-1.5 h-1.5 rounded-full ${isVerified ? 'bg-[#2E7D5B]' : 'bg-[#5F4DCB]'}`} />
                          <span>{isVerified ? 'Verified' : 'In Progress'}</span>
                        </span>
                      </td>
                      <td className="py-3.5 px-4 text-[#6B6894] font-mono text-[11px]">
                        {s.createdAt ? new Date(s.createdAt).toLocaleDateString() : '—'}
                      </td>
                      <td className="py-3.5 px-4 text-right">
                        <button
                          onClick={(e) => {
                            e.stopPropagation();
                            onSelectSession(s);
                          }}
                          className="btn-pill btn-secondary text-xs px-3 py-1 inline-flex items-center space-x-1 opacity-90 group-hover:opacity-100"
                        >
                          <span>Review</span>
                          <ArrowRight className="w-3 h-3" />
                        </button>
                      </td>
                    </tr>
                  );
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  );
}
