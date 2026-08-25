import React, { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { FiMenu, FiX } from 'react-icons/fi';
import { isAmplifyAuthEnabled } from '../lib/auth';
import './Navbar.css';

function Navbar() {
  const [isOpen, setIsOpen] = useState(false);
  const location = useLocation();
  const isHomeRoute = location.pathname.startsWith('/jarvis');
  const isJarvisRoute =
    location.pathname.startsWith('/jarvis')
    || location.pathname.startsWith('/operator')
    || location.pathname.startsWith('/platform');
  const surface = 'jarvis';

  const toggleMenu = () => setIsOpen(!isOpen);
  const closeMenu = () => setIsOpen(false);
  const linkClassName = ({ isActive }) => `nav-link ${isActive ? 'active' : ''}`;
  const navItems = isJarvisRoute
    ? [
        { type: 'route', to: '/jarvis', label: 'Console' },
        { type: 'route', to: '/operator', label: 'Dashboard' },
        { type: 'route', to: '/operator/plugins', label: 'Plugins' },
        { type: 'route', to: '/operator/brain', label: 'Brain' },
        { type: 'route', to: '/operator/ledger', label: 'Ledger' },
        { type: 'route', to: '/platform', label: 'Platform Ops' },
        ...(isAmplifyAuthEnabled() ? [{ type: 'route', to: '/auth/sign-in', label: 'Sign in' }] : []),
        { type: 'route', to: '/jarvis/repo-manager', label: 'Repo Manager' },
        { type: 'route', to: '/memory', label: 'Memory Bank' },
  { type: 'route', to: '/jarvis', label: 'Jarvis' },
      ]
    : isHomeRoute
    ? [
        { type: 'anchor', href: '#chat', label: 'Chat' },
        { type: 'anchor', href: '#intake', label: 'Intake' },
        { type: 'anchor', href: '#categories', label: 'Categories' },
        { type: 'route', to: '/jarvis', label: 'Console' },
        { type: 'route', to: '/memory', label: 'Memory Bank' },
      ]
    : [
        { type: 'route', to: '/', label: 'Home' },
        { type: 'route', to: '/jarvis', label: 'Console' },
        { type: 'route', to: '/memory', label: 'Memory Bank' },
        { type: 'route', to: '/image-generator', label: 'Images' },
        { type: 'route', to: '/text-generator', label: 'Studio' },
        { type: 'route', to: '/audio-processor', label: 'Audio' },
        { type: 'route', to: '/batch-processor', label: 'Batch' },
        { type: 'route', to: '/workflows', label: 'Workflows' },
        { type: 'route', to: '/history', label: 'History' },
        { type: 'route', to: '/settings', label: 'Settings' },
      ];
  const brand = isJarvisRoute
    ? { mark: 'JARVIS', subtitle: 'Operator Console', to: '/jarvis' }
  : { mark: 'JARVIS', subtitle: 'Operator Surface', to: '/jarvis' };

  return (
    <nav className={`navbar navbar--${surface}`}>
      <div className="navbar-container">
        <NavLink to={brand.to} className="navbar-logo" onClick={closeMenu}>
          <span className="navbar-mark">{brand.mark}</span>
          <span className="navbar-subtitle">{brand.subtitle}</span>
        </NavLink>
        
        <button className="menu-toggle" onClick={toggleMenu} aria-label="Toggle navigation">
          {isOpen ? <FiX /> : <FiMenu />}
        </button>

        <ul className={`nav-menu ${isOpen ? 'active' : ''}`}>
          {navItems.map((item) => (
            <li className="nav-item" key={item.label}>
              {item.type === 'anchor' ? (
                <a href={item.href} className="nav-link" onClick={closeMenu}>
                  {item.label}
                </a>
              ) : (
                <NavLink to={item.to} className={linkClassName} onClick={closeMenu}>
                  {item.label}
                </NavLink>
              )}
            </li>
          ))}
        </ul>
      </div>
    </nav>
  );
}

export default Navbar;
