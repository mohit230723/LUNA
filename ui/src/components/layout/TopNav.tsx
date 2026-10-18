import React, { useState } from 'react';
import { NavLink, useLocation } from 'react-router-dom';
import { Compass, Menu, X } from 'lucide-react';
import { Badge } from '../ui/Badge';
import { Button } from '../ui/Button';
import { IconButton } from '../ui/IconButton';
import { useHealth } from '../../state/hooks';
import styles from './TopNav.module.css';

export interface TopNavProps {
  compact?: boolean;
}

export const TopNav: React.FC<TopNavProps> = ({ compact = false }) => {
  const [mobileMenuOpen, setMobileMenuOpen] = useState(false);
  const location = useLocation();
  const { isOnline } = useHealth();
  const isPlatform = location.pathname.startsWith('/platform');

  const navLinks = [
    { to: '/', label: 'HOME' },
    { to: '/how-it-works', label: 'HOW IT WORKS' },
    { to: '/skills', label: 'SKILL ATLAS' },
    { to: '/platform', label: 'PLATFORM' },
  ];

  return (
    <nav
      className={`${styles.nav} ${compact || isPlatform ? styles.compact : ''} ${isPlatform ? styles.sticky : ''}`}
      role="navigation"
      aria-label="Main Navigation"
    >
      <div className={styles.inner}>
        {/* Left: Brand */}
        <NavLink to="/" className={styles.brand} aria-label="LUNA OS Home">
          <Compass size={24} strokeWidth={1.5} className={styles.compassIcon} aria-hidden="true" />
          <span className={styles.wordmark}>LUNA</span>
        </NavLink>

        {/* Center: Desktop Links */}
        <div className={styles.links}>
          {navLinks.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.to === '/'}
              className={({ isActive }) =>
                `${styles.navLink} ${isActive ? styles.activeLink : ''}`
              }
            >
              {link.label}
            </NavLink>
          ))}
        </div>

        {/* Right Action */}
        <div className={styles.rightAction}>
          {isPlatform ? (
            <Badge hasPulseDot={isOnline} size="compact">
              {isOnline ? 'BACKEND ONLINE' : 'BACKEND OFFLINE'}
            </Badge>
          ) : (
            <NavLink to="/platform" tabIndex={-1}>
              <Button showArrow className={styles.ctaButton}>
                TRY THE PLATFORM
              </Button>
            </NavLink>
          )}

          {/* Mobile Menu Button */}
          <IconButton
            className={styles.mobileMenuButton}
            aria-label={mobileMenuOpen ? 'Close menu' : 'Open menu'}
            onClick={() => setMobileMenuOpen(!mobileMenuOpen)}
          >
            {mobileMenuOpen ? <X size={20} strokeWidth={1.5} /> : <Menu size={20} strokeWidth={1.5} />}
          </IconButton>
        </div>
      </div>

      {/* Mobile Drawer */}
      {mobileMenuOpen && (
        <div className={styles.mobileMenu}>
          {navLinks.map((link) => (
            <NavLink
              key={link.to}
              to={link.to}
              end={link.to === '/'}
              onClick={() => setMobileMenuOpen(false)}
              className={({ isActive }) =>
                `${styles.mobileNavLink} ${isActive ? styles.mobileActiveLink : ''}`
              }
            >
              {link.label}
            </NavLink>
          ))}
        </div>
      )}
    </nav>
  );
};
