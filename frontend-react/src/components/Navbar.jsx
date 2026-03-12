import React, { useState, useRef, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

export default function Navbar({ onDetailsOpen, onReportsOpen, userName }) {
  const navigate = useNavigate();
  const { user, isAuthenticated, logout } = useAuth();
  const [showDropdown, setShowDropdown] = useState(false);
  const [showMenu, setShowMenu] = useState(false);
  const dropdownRef = useRef(null);
  const userBtnRef = useRef(null);

  // Display priority: auth user name > prop userName > fallback
  const displayName = user?.name || user?.email || userName || '';

  useEffect(() => {
    const handleOutsideClick = (event) => {
      if (
        dropdownRef.current && !dropdownRef.current.contains(event.target) &&
        userBtnRef.current && !userBtnRef.current.contains(event.target)
      ) {
        setShowDropdown(false);
      }
    };
    if (showDropdown) document.addEventListener('click', handleOutsideClick);
    return () => document.removeEventListener('click', handleOutsideClick);
  }, [showDropdown]);

  const handleDetailsClick = () => {
    setShowDropdown(false);
    onDetailsOpen();
  };

  const handleReportsClick = () => {
    setShowDropdown(false);
    onReportsOpen();
  };

  const handleLogout = () => {
    setShowDropdown(false);
    logout();
    navigate('/login');
  };

  const handleLoginClick = () => {
    setShowDropdown(false);
    navigate('/login');
  };

  return (
    <nav className="navbar-home">
      <a className="logo" href="/">
        <img src="/logo.jpg" alt="ReportEase Logo" className="logo-img" />
        <span className="logo-name">Report<span>Ease</span></span>
      </a>

      <ul className="nav-links" id="navLinks" style={{ display: showMenu ? 'flex' : '' }}>
        <li><a href="#features" onClick={() => setShowMenu(false)}>Features</a></li>
        <li><a href="#how" onClick={() => setShowMenu(false)}>How It Works</a></li>
        <li><a href="#about" onClick={() => setShowMenu(false)}>About</a></li>
      </ul>

      <div className="nav-right">
        <a className="nav-cta" href="/upload" onClick={() => setShowMenu(false)}>Upload Report</a>

        <button
          className="user-btn"
          ref={userBtnRef}
          id="userBtn"
          onClick={() => setShowDropdown(!showDropdown)}
          aria-label="User menu"
        >
          <svg viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/>
            <circle cx="12" cy="7" r="4"/>
          </svg>
        </button>

        {showDropdown && (
          <div className="user-dropdown open" id="userDropdown" ref={dropdownRef}>
            <div className="dropdown-header">
              <strong>{isAuthenticated ? 'Welcome back' : 'Guest user'}</strong>
              <span>{displayName || (isAuthenticated ? 'Account' : 'Not signed in')}</span>
            </div>

            <button className="dropdown-item" onClick={handleReportsClick}>
              <svg viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round">
                <path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/>
                <polyline points="14 2 14 8 20 8"/>
                <line x1="16" y1="13" x2="8" y2="13"/>
                <line x1="16" y1="17" x2="8" y2="17"/>
              </svg>
              My Reports
            </button>

            <button className="dropdown-item" onClick={handleDetailsClick}>
              <svg viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round">
                <path d="M20 21v-2a4 4 0 00-4-4H8a4 4 0 00-4 4v2"/>
                <circle cx="12" cy="7" r="4"/>
              </svg>
              My Details
            </button>

            <div className="dropdown-divider"></div>

            {isAuthenticated ? (
              <button className="dropdown-item danger" onClick={handleLogout}>
                <svg viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round">
                  <path d="M9 21H5a2 2 0 01-2-2V5a2 2 0 012-2h4"/>
                  <polyline points="16 17 21 12 16 7"/>
                  <line x1="21" y1="12" x2="9" y2="12"/>
                </svg>
                Log Out
              </button>
            ) : (
              <button className="dropdown-item" onClick={handleLoginClick}>
                <svg viewBox="0 0 24 24" fill="none" strokeWidth="2" strokeLinecap="round">
                  <path d="M15 3h4a2 2 0 012 2v14a2 2 0 01-2 2h-4"/>
                  <polyline points="10 17 15 12 10 7"/>
                  <line x1="15" y1="12" x2="3" y2="12"/>
                </svg>
                Sign In
              </button>
            )}
          </div>
        )}

        <div className="hamburger" onClick={() => setShowMenu(!showMenu)}>
          <span></span><span></span><span></span>
        </div>
      </div>
    </nav>
  );
}
