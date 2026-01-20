import React from 'react';
import { NavLink } from 'react-router-dom';
import { useAuthStore } from '../context/AuthContext';

const Sidebar = () => {
  const { user } = useAuthStore();
  const isManager = user?.role === 'manager';
  const business = user?.assigned_business;

  const managerLinks = [
    { path: '/dashboard', label: 'Dashboard', icon: '📊' },
    { path: '/boutique', label: 'Boutique', icon: '👗' },
    { path: '/hardware', label: 'Hardware', icon: '🔨' },
    { path: '/employees', label: 'Employees', icon: '👥' },
  ];

  const boutiqueLinks = [
    { path: '/employee-dashboard', label: 'Dashboard', icon: '📊' },
    { path: '/boutique/new-sale', label: 'New Sale', icon: '💰' },
    { path: '/boutique/my-sales', label: 'My Sales', icon: '📝' },
    { path: '/boutique/credits', label: 'Credits', icon: '💳' },
    { path: '/boutique/stock', label: 'Stock', icon: '📦' },
  ];

  const hardwareLinks = [
    { path: '/employee-dashboard', label: 'Dashboard', icon: '📊' },
    { path: '/hardware/new-sale', label: 'New Sale', icon: '💰' },
    { path: '/hardware/my-sales', label: 'My Sales', icon: '📝' },
    { path: '/hardware/credits', label: 'Credits', icon: '💳' },
    { path: '/hardware/stock', label: 'Stock', icon: '📦' },
  ];

  const links = isManager ? managerLinks : (business === 'boutique' ? boutiqueLinks : hardwareLinks);

  return (
    <aside className="w-64 bg-card border-r border-border min-h-screen">
      <nav className="p-4 space-y-2">
        {links.map((link) => (
          <NavLink
            key={link.path}
            to={link.path}
            className={({ isActive }) =>
              `flex items-center space-x-3 px-4 py-3 rounded-lg transition-colors ${
                isActive
                  ? 'bg-accent text-white'
                  : 'text-text-muted hover:bg-secondary hover:text-text'
              }`
            }
          >
            <span className="text-xl">{link.icon}</span>
            <span className="font-medium">{link.label}</span>
          </NavLink>
        ))}
      </nav>
    </aside>
  );
};

export default Sidebar;
