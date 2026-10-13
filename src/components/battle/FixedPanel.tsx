import type { ReactNode } from 'react';
import './FixedPanel.css';

interface FixedPanelProps {
  title: ReactNode;
  subtitle?: ReactNode;
  badge?: ReactNode;
  headerActions?: ReactNode;
  children: ReactNode;
  variant?: 'charcoal' | 'arena' | 'surface';
  className?: string;
  bodyClassName?: string;
  ariaLabel?: string;
  id?: string;
  footer?: ReactNode;
}

export const FixedPanel = ({
  title,
  subtitle,
  badge,
  headerActions,
  children,
  variant = 'surface',
  className = '',
  bodyClassName = '',
  ariaLabel,
  id,
  footer,
}: FixedPanelProps) => {
  return (
    <section
      id={id}
      className={`litmus-fixed-panel litmus-fixed-panel--${variant} ${className}`}
      aria-label={ariaLabel || (typeof title === 'string' ? title : 'Panel')}
    >
      <header className="litmus-fixed-panel__header">
        <div className="litmus-fixed-panel__titles">
          <div className="litmus-fixed-panel__title-row">
            {typeof title === 'string' ? (
              <h2 className="litmus-fixed-panel__title">{title}</h2>
            ) : (
              title
            )}
            {badge && <div className="litmus-fixed-panel__badge">{badge}</div>}
          </div>
          {subtitle && <p className="litmus-fixed-panel__subtitle">{subtitle}</p>}
        </div>

        {headerActions && (
          <div className="litmus-fixed-panel__actions">
            {headerActions}
          </div>
        )}
      </header>

      <div className={`litmus-fixed-panel__body ${bodyClassName}`}>
        {children}
      </div>

      {footer && (
        <footer className="litmus-fixed-panel__footer">
          {footer}
        </footer>
      )}
    </section>
  );
};
