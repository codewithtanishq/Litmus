import { useState, useEffect } from 'react';
import type { ReactNode } from 'react';
import { NavLink, useLocation, useNavigate } from 'react-router-dom';
import { 
  Home, 
  RotateCcw, 
  Hourglass, 
  HelpCircle, 
  LogOut, 
  Minus, 
  Square, 
  X 
} from 'lucide-react';
import { debugService } from '../../services/debugService';
import './AppLayout.css';

interface AppLayoutProps {
  children: ReactNode;
}

export const AppLayout = ({ children }: AppLayoutProps) => {
  const location = useLocation();
  const navigate = useNavigate();
  const [backendOnline, setBackendOnline] = useState<boolean | null>(null);

  useEffect(() => {
    let mounted = true;
    const verifyHealth = async () => {
      const health = await debugService.checkHealth();
      if (mounted) {
        setBackendOnline(health?.status === 'healthy');
      }
    };
    verifyHealth();
    const interval = setInterval(verifyHealth, 10000);
    return () => {
      mounted = false;
      clearInterval(interval);
    };
  }, []);

  const isHome = location.pathname === '/';
  const isBattle = location.pathname === '/battle';

  return (
    <div className="litmus-window-frame">
      {/* 1. Topmost Title Bar (Matching 2nd uploaded image) */}
      <header className="litmus-topbar">
        <div className="litmus-topbar__left">
          {/* Subtle 4-dot / diamond sparkle icon */}
          <svg 
            className="litmus-topbar__logo-icon" 
            width="16" 
            height="16" 
            viewBox="0 0 24 24" 
            fill="currentColor"
            aria-hidden="true"
          >
            <circle cx="12" cy="4" r="2.5" />
            <circle cx="12" cy="20" r="2.5" />
            <circle cx="4" cy="12" r="2.5" />
            <circle cx="20" cy="12" r="2.5" />
            <circle cx="12" cy="12" r="3" />
          </svg>
          <span className="litmus-topbar__title">Litmus</span>
          {backendOnline !== null && (
            <span 
              className={`litmus-backend-badge ${backendOnline ? 'litmus-backend-badge--online' : 'litmus-backend-badge--offline'}`}
              title={backendOnline ? 'Backend API connected (Port 8001, SQLite ledger active)' : 'Operating in Standalone / Mock fallback mode'}
            >
              <span className="litmus-backend-badge__dot" />
              {backendOnline ? 'Backend: Online (8001)' : 'Backend: Standalone'}
            </span>
          )}
        </div>

        {/* Window controls on far right */}
        <div className="litmus-topbar__controls" aria-hidden="true">
          <button type="button" className="litmus-window-btn" tabIndex={-1} aria-label="Minimize">
            <Minus size={13} />
          </button>
          <button type="button" className="litmus-window-btn" tabIndex={-1} aria-label="Maximize">
            <Square size={11} />
          </button>
          <button type="button" className="litmus-window-btn litmus-window-btn--close" tabIndex={-1} aria-label="Close">
            <X size={13} />
          </button>
        </div>
      </header>

      {/* 2. Subbar with Tabs (Dashboard, History, Debug: test_failure) */}
      <nav className="litmus-subbar" aria-label="Workspace Navigation">
        <div className="litmus-subbar__spacer" aria-hidden="true" />
        
        <div className="litmus-subbar__tabs">
          <NavLink 
            to="/" 
            className={({ isActive }) => `litmus-tab ${isActive ? 'litmus-tab--active' : ''}`}
            end
          >
            Dashboard
          </NavLink>

          <NavLink 
            to="/history" 
            className={({ isActive }) => `litmus-tab ${isActive ? 'litmus-tab--active' : ''}`}
            onClick={(e) => {
              // Smooth scroll to history section if on home
              if (isHome) {
                e.preventDefault();
                const recentsEl = document.getElementById('recent-sessions-anchor');
                recentsEl?.scrollIntoView({ behavior: 'smooth' });
              }
            }}
          >
            History
          </NavLink>

          <NavLink 
            to="/battle" 
            className={({ isActive }) => `litmus-tab ${isActive ? 'litmus-tab--active' : ''}`}
          >
            Debug: test_failure
          </NavLink>
        </div>
      </nav>

      {/* 3. Main Workspace Shell: Left Sidebar Rail + Inner Content */}
      <div className="litmus-body-container">
        {/* Left Side Bar (Identical to 2nd uploaded image) */}
        <aside className="litmus-sidebar" aria-label="Sidebar Actions">
          <div className="litmus-sidebar__top">
            <button 
              type="button" 
              className={`litmus-sidebar-btn ${isHome ? 'litmus-sidebar-btn--active' : ''}`}
              onClick={() => navigate('/')}
              title="Dashboard / Home"
              aria-label="Dashboard"
            >
              <Home size={19} />
            </button>

            <button 
              type="button" 
              className="litmus-sidebar-btn"
              onClick={() => {
                if (isHome) {
                  document.getElementById('recent-sessions-anchor')?.scrollIntoView({ behavior: 'smooth' });
                } else {
                  navigate('/');
                }
              }}
              title="History"
              aria-label="History"
            >
              <RotateCcw size={19} />
            </button>

            <button 
              type="button" 
              className={`litmus-sidebar-btn ${isBattle ? 'litmus-sidebar-btn--active' : ''}`}
              onClick={() => navigate('/battle')}
              title="Debug: test_failure"
              aria-label="Debug test failure"
            >
              <Hourglass size={19} />
            </button>
          </div>

          <div className="litmus-sidebar__bottom">
            <button 
              type="button" 
              className="litmus-sidebar-btn"
              title="Help & Documentation"
              aria-label="Help"
              onClick={() => alert('LITMUS: Adversarial multi-agent debugger. Enter a reproducible bug, and agents will debate hypotheses verified by test sandbox execution.')}
            >
              <HelpCircle size={19} />
            </button>

            <button 
              type="button" 
              className="litmus-sidebar-btn"
              title="Exit / Clear Session"
              aria-label="Exit"
              onClick={() => navigate('/')}
            >
              <LogOut size={19} />
            </button>
          </div>
        </aside>

        {/* Inner Content Area */}
        <div className="litmus-content-viewport">
          {children}
        </div>
      </div>
    </div>
  );
};
