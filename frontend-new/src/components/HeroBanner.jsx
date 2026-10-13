import React from 'react';
import { ArrowRight, Play } from 'lucide-react';
import HeroBurst from './HeroBurst';

export default function HeroBanner({ onStartDemo, onNewCaseClick }) {
  return (
    <div
      className="relative overflow-hidden min-h-[calc(100vh-4rem)] flex flex-col justify-center items-center px-4 sm:px-6 lg:px-8 py-16 sm:py-24 text-white"
      style={{
        position: 'relative',
        overflow: 'hidden',
        background: 'linear-gradient(160deg, #221B6D, #3B2A9D 55%, #5F4DCB)',
      }}
    >
      <HeroBurst size={0.75} />

      <div
        className="absolute inset-0 pointer-events-none"
        style={{
          position: 'absolute',
          inset: 0,
          pointerEvents: 'none',
          background: 'radial-gradient(ellipse at 50% 40%, rgba(34, 27, 109, 0.6) 0%, transparent 60%)',
        }}
      />

      <div
        className="relative max-w-4xl mx-auto text-center z-10 my-auto"
        style={{
          position: 'relative',
          zIndex: 1,
        }}
      >
        {/* Headline with tight tracking, light & regular weights */}
        <h1 className="text-4xl sm:text-6xl md:text-7xl font-light tracking-tight text-white mb-6 leading-[1.1]">
          Debate the Cause
          <span className="block font-normal bg-gradient-to-r from-white via-[#E1DDFA] to-[#C5C4F2] bg-clip-text text-transparent mt-2">
            Run the Fix
          </span>
        </h1>

        <p className="text-base sm:text-lg text-[#C5C4F2]/90 max-w-xl mx-auto font-light leading-relaxed mb-10">
          Adversarial multi-agent debugging adjudicated deterministically in isolated execution sandboxes.
        </p>

        {/* Action buttons */}
        <div className="flex flex-wrap items-center justify-center gap-4">
          <button
            onClick={onNewCaseClick}
            className="btn-pill px-7 py-3.5 bg-white text-[#221B6D] font-medium text-sm hover:bg-[#F6F5FF] hover:shadow-xl transition-all flex items-center space-x-2 shadow-sm"
          >
            <span>Open Courtroom Trial</span>
            <ArrowRight className="w-4 h-4 text-[#5F4DCB]" />
          </button>

          <button
            onClick={onStartDemo}
            className="btn-pill px-7 py-3.5 bg-white/10 hover:bg-white/15 text-white border border-white/20 font-medium text-sm backdrop-blur-md transition-all flex items-center space-x-2"
          >
            <Play className="w-4 h-4 fill-current text-[#C5C4F2]" />
            <span>Launch Quick Demo</span>
          </button>
        </div>
      </div>
    </div>
  );
}


