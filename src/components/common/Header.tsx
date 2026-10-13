import { NavLink } from 'react-router-dom';
import { DemoBadge } from './DemoBadge';
import { Swords, Scale } from 'lucide-react';
import './Header.css';

export const Header = () => {
  return (
    <header className="litmus-header">
      <div className="litmus-header__left">
        <NavLink to="/" className="litmus-wordmark" aria-label="Litmus Home">
          <span className="litmus-wordmark__main">LITMUS</span>
          <span className="litmus-wordmark__tag">DEBATE &bull; RUN</span>
        </NavLink>
        
        <nav className="litmus-header__nav" aria-label="Main Navigation">
          <NavLink 
            to="/" 
            className={({ isActive }) => `litmus-nav-link ${isActive ? 'litmus-nav-link--active' : ''}`}
            end
          >
            Home
          </NavLink>
          <NavLink 
            to="/battle" 
            className={({ isActive }) => `litmus-nav-link ${isActive ? 'litmus-nav-link--active' : ''}`}
          >
            <Swords size={13} className="litmus-nav-link__icon" />
            Battle
          </NavLink>
          <NavLink 
            to="/checkmate" 
            className={({ isActive }) => `litmus-nav-link ${isActive ? 'litmus-nav-link--active' : ''}`}
          >
            <Scale size={13} className="litmus-nav-link__icon" />
            Checkmate
          </NavLink>
          <NavLink 
            to="/results" 
            className={({ isActive }) => `litmus-nav-link ${isActive ? 'litmus-nav-link--active' : ''}`}
          >
            Results
          </NavLink>
        </nav>
      </div>

      <div className="litmus-header__right">
        <DemoBadge />
      </div>
    </header>
  );
};
