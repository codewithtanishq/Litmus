import { useState, useRef, useEffect } from 'react';
import { 
  DEMO_SCENARIOS, 
  getActiveDemoScenarioId, 
  setActiveDemoScenarioId,
  type DemoScenarioId 
} from '../../demo/demoState';
import { ChevronDown, Sparkles, Check, Info } from 'lucide-react';
import './DemoBadge.css';

interface DemoBadgeProps {
  className?: string;
}

export const DemoBadge = ({ className = '' }: DemoBadgeProps) => {
  const [isOpen, setIsOpen] = useState(false);
  const [activeId, setActiveId] = useState<DemoScenarioId>(getActiveDemoScenarioId());
  const dropdownRef = useRef<HTMLDivElement>(null);

  // Sync state with custom event
  useEffect(() => {
    const handleSync = (e: Event) => {
      const customEvent = e as CustomEvent<{ id: DemoScenarioId }>;
      if (customEvent.detail?.id) {
        setActiveId(customEvent.detail.id);
      } else {
        setActiveId(getActiveDemoScenarioId());
      }
    };

    window.addEventListener('litmus:demo-scenario-changed', handleSync);
    return () => window.removeEventListener('litmus:demo-scenario-changed', handleSync);
  }, []);

  // Close dropdown on outside click or escape
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setIsOpen(false);
      }
    };

    const handleClickOutside = (e: MouseEvent) => {
      if (dropdownRef.current && !dropdownRef.current.contains(e.target as Node)) {
        setIsOpen(false);
      }
    };

    if (isOpen) {
      document.addEventListener('keydown', handleKeyDown);
      document.addEventListener('mousedown', handleClickOutside);
    }
    return () => {
      document.removeEventListener('keydown', handleKeyDown);
      document.removeEventListener('mousedown', handleClickOutside);
    };
  }, [isOpen]);

  const handleSelectScenario = (id: DemoScenarioId) => {
    setActiveDemoScenarioId(id);
    setActiveId(id);
    setIsOpen(false);
  };

  const activeScenario = DEMO_SCENARIOS.find(s => s.id === activeId) || DEMO_SCENARIOS[0];

  return (
    <div className={`demo-badge-container ${className}`} ref={dropdownRef}>
      <button 
        type="button"
        className="demo-badge-button"
        onClick={() => setIsOpen(!isOpen)}
        aria-expanded={isOpen}
        aria-haspopup="dialog"
        title="Demo Mode active. Click to switch demo scenarios."
      >
        <span className="demo-badge-dot" aria-hidden="true" />
        <span className="demo-badge-label">DEMO MODE</span>
        <span className="demo-badge-scenario-tag">{activeScenario.badgeLabel}</span>
        <ChevronDown size={12} className={`demo-badge-chevron ${isOpen ? 'demo-badge-chevron--open' : ''}`} />
      </button>

      {isOpen && (
        <div className="demo-dropdown" role="dialog" aria-label="Demo Scenario Switcher">
          <div className="demo-dropdown__header">
            <div className="demo-dropdown__title">
              <Sparkles size={14} className="demo-dropdown__title-icon" />
              <span>Select Active Demo Scenario</span>
            </div>
            <p className="demo-dropdown__subtitle">
              Configures deterministic mock behavior for debate execution and sample bug inspection.
            </p>
          </div>

          <div className="demo-dropdown__list" role="menu">
            {DEMO_SCENARIOS.map((scenario) => {
              const isSelected = scenario.id === activeId;
              return (
                <button
                  key={scenario.id}
                  type="button"
                  role="menuitem"
                  className={`demo-scenario-item ${isSelected ? 'demo-scenario-item--active' : ''}`}
                  onClick={() => handleSelectScenario(scenario.id)}
                >
                  <div className="demo-scenario-item__content">
                    <div className="demo-scenario-item__header">
                      <span className="demo-scenario-item__name">{scenario.name}</span>
                      {isSelected && <Check size={14} className="demo-scenario-item__check" />}
                    </div>
                    <p className="demo-scenario-item__desc">{scenario.description}</p>
                  </div>
                </button>
              );
            })}
          </div>

          <div className="demo-dropdown__footer">
            <Info size={12} />
            <span>Frontend-only mock environment. No API keys or remote LLMs contacted.</span>
          </div>
        </div>
      )}
    </div>
  );
};
