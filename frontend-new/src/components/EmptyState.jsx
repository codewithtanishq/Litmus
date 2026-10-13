import React from 'react';
import SignatureBurst from './SignatureBurst';
import { Plus, Sparkles } from 'lucide-react';

export default function EmptyState({ title, description, actionText, onAction }) {
  return (
    <div className="card-surface relative overflow-hidden py-16 px-6 text-center max-w-xl mx-auto my-8">
      {/* Signature burst graphic anchored at bottom */}
      <div className="absolute -bottom-6 left-0 right-0 pointer-events-none flex justify-center opacity-45">
        <SignatureBurst density={75} height={200} variant="light" />
      </div>

      <div className="relative z-10 max-w-sm mx-auto">
        <div className="w-12 h-12 rounded-full bg-[#EEEBFF] border border-[#E1DDFA] flex items-center justify-center mx-auto mb-4 text-[#5F4DCB]">
          <Sparkles className="w-6 h-6" />
        </div>

        <h3 className="text-lg font-semibold text-[#1E1856] tracking-tight mb-2">
          {title || "No Trial In Progress"}
        </h3>

        <p className="text-sm text-[#6B6894] leading-relaxed mb-6">
          {description || "Submit buggy code to initiate multi-agent adversarial debate, sandbox testing, and empirical adjudication."}
        </p>

        {onAction && (
          <button
            onClick={onAction}
            className="btn-pill btn-primary text-sm px-5 py-2.5 inline-flex items-center space-x-2 shadow-sm"
          >
            <Plus className="w-4 h-4" />
            <span>{actionText || "Start Courtroom Trial"}</span>
          </button>
        )}
      </div>
    </div>
  );
}
