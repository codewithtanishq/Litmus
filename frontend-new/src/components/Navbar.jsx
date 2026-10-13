import React, { useEffect, useState } from 'react';
import { ShieldCheck, Cpu, Terminal, Plus, Sparkles, Activity, AlertCircle } from 'lucide-react';
import { fetchHealth } from '../services/api';

export default function Navbar({ activeTab, setActiveTab, onNewCaseClick }) {
  const [health, setHealth] = useState(null);
  const [isHealthLoading, setIsHealthLoading] = useState(true);

  useEffect(() => {
    let mounted = true;
    const checkSystemHealth = async () => {
      try {
        const data = await fetchHealth();
        if (mounted) {
          setHealth(data);
          setIsHealthLoading(false);
        }
      } catch (err) {
        if (mounted) {
          setHealth({ status: 'offline', error: err.message });
          setIsHealthLoading(false);
        }
      }
    };

    checkSystemHealth();
    const interval = setInterval(checkSystemHealth, 25000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  const isHealthy = health?.status === 'healthy';
  const ollamaOnline = health?.services?.ollama?.available;

  const isHero = activeTab === 'hero';

  return (
    <header className={`sticky top-0 z-50 transition-all duration-300 ${isHero ? 'glass-nav-dark' : 'glass-nav'}`}>
      <div className="max-w-7xl mx-auto px-4 sm:px-6 lg:px-8 h-16 flex items-center justify-between">
        {/* Brand identity */}
        <div className="flex items-center space-x-3 cursor-pointer" onClick={() => setActiveTab('hero')}>
          <div className="w-9 h-9 rounded-full bg-[#221B6D] flex items-center justify-center text-white shadow-sm ring-1 ring-[#5F4DCB]/30">
            <Sparkles className="w-5 h-5 text-[#C5C4F2]" />
          </div>
          <div>
            <span className={`font-semibold text-lg tracking-tight ${isHero ? 'text-white' : 'text-[#1E1856]'}`}>
              Litmus
            </span>
            <span className={`hidden sm:inline-block ml-2 text-xs px-2 py-0.5 rounded-full font-medium border ${
              isHero ? 'bg-white/10 text-[#C5C4F2] border-white/15' : 'bg-[#EEEBFF] text-[#5F4DCB] border-[#E1DDFA]'
            }`}>
              Adversarial Courtroom
            </span>
          </div>
        </div>

        {/* Navigation tabs */}
        <nav className="flex items-center space-x-1 sm:space-x-2">
          <button
            onClick={() => setActiveTab('hero')}
            className={`px-3 py-1.5 rounded-full text-xs sm:text-sm font-medium transition-colors ${
              isHero
                ? 'bg-white/15 text-white border border-white/20'
                : 'text-[#6B6894] hover:text-[#1E1856] hover:bg-[#F6F5FF]'
            }`}
          >
            Overview
          </button>
          <button
            onClick={() => setActiveTab('arena')}
            className={`px-3 py-1.5 rounded-full text-xs sm:text-sm font-medium transition-colors ${
              activeTab === 'arena'
                ? 'bg-[#EEEBFF] text-[#5F4DCB] border border-[#E1DDFA]'
                : isHero
                ? 'text-[#C5C4F2] hover:text-white hover:bg-white/10'
                : 'text-[#6B6894] hover:text-[#1E1856] hover:bg-[#F6F5FF]'
            }`}
          >
            Courtroom Arena
          </button>
          <button
            onClick={() => setActiveTab('sessions')}
            className={`px-3 py-1.5 rounded-full text-xs sm:text-sm font-medium transition-colors ${
              activeTab === 'sessions'
                ? 'bg-[#EEEBFF] text-[#5F4DCB] border border-[#E1DDFA]'
                : isHero
                ? 'text-[#C5C4F2] hover:text-white hover:bg-white/10'
                : 'text-[#6B6894] hover:text-[#1E1856] hover:bg-[#F6F5FF]'
            }`}
          >
            Trials Archive
          </button>
        </nav>

        {/* Right side: System health badge & New Case button */}
        <div className="flex items-center space-x-3">
          <div 
            className={`hidden md:flex items-center space-x-1.5 text-xs px-2.5 py-1 rounded-full border transition-colors ${
              isHealthy
                ? isHero 
                  ? 'bg-white/10 text-[#C5C4F2] border-white/20' 
                  : 'bg-[#EDF7F2] text-[#2E7D5B] border-[#BFE7D3]'
                : 'bg-[#FDF2F2] text-[#D13438] border-[#F9C6C7]'
            }`}
            title={health ? `Ollama: ${ollamaOnline ? 'Ready' : 'Offline'} | Sandbox: Host/Docker` : 'Checking system health'}
          >
            <span className={`w-2 h-2 rounded-full ${isHealthy ? (isHero ? 'bg-[#C5C4F2] animate-pulse' : 'bg-[#2E7D5B] animate-pulse') : 'bg-[#D13438]'}`} />
            <span className="font-medium">
              {isHealthLoading ? 'Connecting...' : isHealthy ? (ollamaOnline ? 'System Ready' : 'Deterministic Mode') : 'Backend Offline'}
            </span>
          </div>

          <button
            onClick={onNewCaseClick}
            className="btn-pill btn-primary text-xs sm:text-sm px-4 py-2 flex items-center space-x-1.5 shadow-sm"
          >
            <Plus className="w-4 h-4" />
            <span>New Case</span>
          </button>
        </div>
      </div>
    </header>
  );
}
