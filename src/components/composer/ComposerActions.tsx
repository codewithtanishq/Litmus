import { Sparkles, Trash2 } from 'lucide-react';
import './ComposerActions.css';

interface ComposerActionsProps {
  onLoadSample: () => void;
  onClear: () => void;
  hasInput: boolean;
}

export const ComposerActions = ({
  onLoadSample,
  onClear,
  hasInput,
}: ComposerActionsProps) => {
  return (
    <div className="composer-actions">
      <div className="composer-actions__left">
        <button
          type="button"
          className="composer-action-btn composer-action-btn--sample"
          onClick={onLoadSample}
          title="Fill composer with realistic Python off-by-one bug (does not submit)"
        >
          <Sparkles size={13} className="composer-action-btn__icon" />
          <span>Try a sample bug</span>
        </button>

        {hasInput && (
          <button
            type="button"
            className="composer-action-btn composer-action-btn--clear"
            onClick={onClear}
            title="Reset composer inputs"
          >
            <Trash2 size={13} className="composer-action-btn__icon" />
            <span>Clear</span>
          </button>
        )}
      </div>

      <div className="composer-actions__right">
        <span className="composer-actions__hint">
          Prosecutor vs Defender &bull; Adjudicated by test sandboxes
        </span>
      </div>
    </div>
  );
};
