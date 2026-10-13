import React, { useState } from 'react';
import Navbar from './components/Navbar';
import HeroBanner from './components/HeroBanner';
import CourtroomArena from './components/CourtroomArena';
import VerdictReport from './components/VerdictReport';
import SessionHistory from './components/SessionHistory';
import NewSessionModal from './components/NewSessionModal';
import EmptyState from './components/EmptyState';
import { createSession } from './services/api';

export default function App() {
  const [activeTab, setActiveTab] = useState('hero'); // 'hero', 'arena', 'sessions', 'verdict'
  const [currentSession, setCurrentSession] = useState(null);
  const [activeResult, setActiveResult] = useState(null);
  const [isModalOpen, setIsModalOpen] = useState(false);

  const handleStartDemo = async () => {
    try {
      const demoSession = await createSession({
        mode: 'code',
        language: 'python',
        question: 'Off-by-one tail item truncation in batch processor',
        code: `def process_batch(items):\n    # Bug: Excludes the tail element\n    return items[0:len(items)-1]\n\ndef test_suite():\n    assert process_batch([1, 2, 3]) == [1, 2, 3]`,
        scenarioId: 'fix_b_passes',
        isDemo: true,
      });
      setCurrentSession(demoSession);
      setActiveTab('arena');
    } catch (err) {
      console.error("Failed to launch demo session:", err);
      // Fallback synthetic session object if backend fails
      setCurrentSession({
        id: `demo-${Date.now()}`,
        question: 'Off-by-one tail item truncation in batch processor',
        code: `def process_batch(items):\n    # Bug: Excludes the tail element\n    return items[0:len(items)-1]`,
        language: 'python',
        mode: 'code',
        status: 'in_progress',
      });
      setActiveTab('arena');
    }
  };

  const handleSessionCreated = (session) => {
    setCurrentSession(session);
    setActiveTab('arena');
  };

  const handleSelectSessionFromHistory = (session) => {
    setCurrentSession(session);
    setActiveTab('arena');
  };

  const handleSelectResult = (result) => {
    setActiveResult(result);
    setActiveTab('verdict');
  };

  return (
    <div className="min-h-screen bg-[#F6F5FF] text-[#1E1856] flex flex-col font-sans">
      {/* Light glass navbar */}
      <Navbar
        activeTab={activeTab}
        setActiveTab={setActiveTab}
        onNewCaseClick={() => setIsModalOpen(true)}
      />

      {/* Main Content Area */}
      <main className="flex-1 flex flex-col">
        {activeTab === 'hero' && (
          <HeroBanner
            onStartDemo={handleStartDemo}
            onNewCaseClick={() => setIsModalOpen(true)}
          />
        )}

        {activeTab === 'arena' && (
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 w-full">
            {currentSession ? (
              <CourtroomArena
                session={currentSession}
                onSelectResult={handleSelectResult}
              />
            ) : (
              <EmptyState
                title="No Active Courtroom Debate"
                description="Select a past trial from the archive, launch a quick demo, or initiate a new trial to start the debate."
                actionText="Start Adjudication"
                onAction={() => setIsModalOpen(true)}
              />
            )}
          </div>
        )}

        {activeTab === 'sessions' && (
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 w-full">
            <SessionHistory
              onSelectSession={handleSelectSessionFromHistory}
              onNewCaseClick={() => setIsModalOpen(true)}
            />
          </div>
        )}

        {activeTab === 'verdict' && (
          <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 py-8 w-full">
            <VerdictReport
              result={activeResult}
              onBackToArena={() => setActiveTab('arena')}
            />
          </div>
        )}
      </main>

      {/* Modal for creating a new session */}
      <NewSessionModal
        isOpen={isModalOpen}
        onClose={() => setIsModalOpen(false)}
        onSessionCreated={handleSessionCreated}
      />

      {/* Footer (shown on app subviews, not on the hero landing) */}
      {activeTab !== 'hero' && (
        <footer className="border-t border-[#E1DDFA] py-6 px-4 bg-[#F6F5FF] text-center text-xs text-[#6B6894]">
          <div className="max-w-7xl mx-auto flex flex-col sm:flex-row items-center justify-between gap-2">
            <span>Litmus Multi-Agent Courtroom Debugger • LangGraph & Deterministic Sandbox Verifier</span>
            <span>Theme: Indigo & Violet Spectral Foundation</span>
          </div>
        </footer>
      )}
    </div>
  );
}
