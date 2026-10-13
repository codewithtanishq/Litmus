import { useRef, useEffect } from 'react';
import type { DebugEvent } from '../../types/litmus';
import { 
  Terminal, 
  Search, 
  GitCommit, 
  Cpu, 
  Scale, 
  CheckCircle2, 
  AlertTriangle 
} from 'lucide-react';
import './EventTimeline.css';

interface EventTimelineProps {
  events: DebugEvent[];
  className?: string;
}

function getEventIcon(type: DebugEvent['type']) {
  switch (type) {
    case 'analysis_started':
      return <Search size={13} />;
    case 'root_cause_located':
      return <Terminal size={13} />;
    case 'fixes_compared':
      return <GitCommit size={13} />;
    case 'sandbox_started':
    case 'sandbox_finished':
      return <Cpu size={13} />;
    case 'judge_decision':
      return <Scale size={13} />;
    case 'completed':
      return <CheckCircle2 size={13} />;
    case 'error':
      return <AlertTriangle size={13} />;
    default:
      return <Terminal size={13} />;
  }
}

function formatRelativeTime(isoString: string): string {
  try {
    const d = new Date(isoString);
    return d.toLocaleTimeString([], { hour12: false, minute: '2-digit', second: '2-digit' });
  } catch {
    return '00:00';
  }
}

export const EventTimeline = ({ events, className = '' }: EventTimelineProps) => {
  const containerRef = useRef<HTMLDivElement>(null);

  // Auto-scroll horizontally to the latest event chip
  useEffect(() => {
    if (containerRef.current) {
      containerRef.current.scrollLeft = containerRef.current.scrollWidth;
    }
  }, [events.length]);

  if (events.length === 0) {
    return (
      <div className={`litmus-event-timeline litmus-event-timeline--empty ${className}`}>
        <span className="litmus-event-timeline__empty-text">Awaiting debug stream events...</span>
      </div>
    );
  }

  return (
    <div 
      className={`litmus-event-timeline ${className}`} 
      role="region" 
      aria-label="Real-time debug event activity strip"
    >
      <div className="litmus-event-timeline__label">
        <span className="litmus-event-timeline__label-dot" aria-hidden="true" />
        <span>ACTIVITY ({events.length})</span>
      </div>

      <div className="litmus-event-timeline__strip" ref={containerRef}>
        {events.map((evt, idx) => {
          const isLatest = idx === events.length - 1;
          const agentClass = evt.agent ? `litmus-event-chip--${evt.agent}` : 'litmus-event-chip--system';

          return (
            <div
              key={`${evt.type}-${evt.timestamp}-${idx}`}
              className={`litmus-event-chip ${agentClass} ${isLatest ? 'litmus-event-chip--latest' : ''}`}
              title={`${evt.message} (${evt.timestamp})`}
            >
              <span className="litmus-event-chip__icon" aria-hidden="true">
                {getEventIcon(evt.type)}
              </span>
              <span className="litmus-event-chip__time">
                {formatRelativeTime(evt.timestamp)}
              </span>
              <span className="litmus-event-chip__agent">
                {evt.agent ? evt.agent.toUpperCase() : 'SYS'}
              </span>
              <span className="litmus-event-chip__msg">
                {evt.message}
              </span>
            </div>
          );
        })}
      </div>
    </div>
  );
};
