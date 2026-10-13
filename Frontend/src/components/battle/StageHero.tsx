import type { ChessPieceType } from './ChessPiece';
import { ChessPiece } from './ChessPiece';
import { FastForward, Pause, Play } from 'lucide-react';
import './StageHero.css';

interface StageHeroProps {
  currentPiece: ChessPieceType;
  statusMessage: string;
  roundNumber: number;
  stepIndex: number; // 0 to 4
  onSkipAnimation?: () => void;
  isCompleted?: boolean;
  isPaused?: boolean;
  onTogglePause?: () => void;
}

const STEPS: Array<{ piece: ChessPieceType; label: string }> = [
  { piece: 'pawn', label: '1. Ingest' },
  { piece: 'knight', label: '2. Locate' },
  { piece: 'bishop', label: '3. Compare' },
  { piece: 'rook', label: '4. Sandboxes' },
  { piece: 'queen', label: '5. Adjudicate' },
];

export const StageHero = ({
  currentPiece,
  statusMessage,
  roundNumber = 1,
  stepIndex,
  onSkipAnimation,
  isCompleted = false,
  isPaused = false,
  onTogglePause,
}: StageHeroProps) => {
  return (
    <div className="litmus-stage-hero" role="region" aria-label="Adversarial reasoning stage progression">
      <div className="litmus-stage-hero__top-row">
        {/* Round Badge */}
        <div className="litmus-stage-hero__badges">
          {roundNumber > 1 ? (
            <span className="litmus-stage-hero__round-badge litmus-stage-hero__round-badge--r2">
              Round {roundNumber}
            </span>
          ) : (
            <span className="litmus-stage-hero__round-badge">
              Round 1
            </span>
          )}
          {isCompleted && (
            <span className="litmus-stage-hero__completed-badge">
              Adjudication Terminal
            </span>
          )}
        </div>

        {/* Action Controls */}
        <div className="litmus-stage-hero__controls">
          {onTogglePause && !isCompleted && (
            <button
              type="button"
              className="litmus-hero-control-btn"
              onClick={onTogglePause}
              title={isPaused ? 'Resume live debate stream' : 'Pause debate stream'}
              aria-label={isPaused ? 'Resume stream' : 'Pause stream'}
            >
              {isPaused ? <Play size={14} /> : <Pause size={14} />}
              <span>{isPaused ? 'Resume' : 'Pause'}</span>
            </button>
          )}

          {onSkipAnimation && !isCompleted && (
            <button
              type="button"
              className="litmus-hero-control-btn litmus-hero-control-btn--skip"
              onClick={onSkipAnimation}
              title="Skip live playback and evaluate all rounds immediately"
              aria-label="Skip animation"
            >
              <FastForward size={14} />
              <span>Skip animation</span>
            </button>
          )}
        </div>
      </div>

      {/* Main Chess Piece Display Stage */}
      <div className="litmus-stage-hero__stage">
        <div className="litmus-stage-hero__piece-wrapper" key={`${currentPiece}-${roundNumber}`}>
          <div className="litmus-stage-hero__glow" aria-hidden="true" />
          <ChessPiece
            type={currentPiece}
            size={72}
            className="litmus-stage-hero__piece-svg"
            glow={true}
          />
        </div>

        {/* Real-time Status line */}
        <div className="litmus-stage-hero__status-area">
          <p className="litmus-stage-hero__status-text" aria-live="polite">
            {statusMessage}
          </p>
        </div>
      </div>

      {/* 5-Step Stepper Indicator */}
      <div className="litmus-stage-hero__stepper" aria-label="Reasoning steps progression">
        {STEPS.map((step, idx) => {
          const isActive = idx === stepIndex;
          const isPassed = idx < stepIndex;

          return (
            <div
              key={step.piece}
              className={`litmus-step-item ${isActive ? 'litmus-step-item--active' : ''} ${
                isPassed ? 'litmus-step-item--passed' : ''
              }`}
            >
              <div className="litmus-step-item__node">
                <ChessPiece
                  type={step.piece}
                  size={16}
                  className="litmus-step-item__icon"
                />
              </div>
              <span className="litmus-step-item__label">{step.label}</span>
              {idx < STEPS.length - 1 && (
                <div
                  className={`litmus-step-item__connector ${
                    idx < stepIndex ? 'litmus-step-item__connector--passed' : ''
                  }`}
                  aria-hidden="true"
                />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
};
