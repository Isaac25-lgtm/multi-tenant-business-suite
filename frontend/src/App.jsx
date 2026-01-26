import React, { useState, useEffect, useRef } from 'react';
import { BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import api, { authAPI, boutiqueAPI, hardwareAPI, employeesAPI, customersAPI, dashboardAPI, financeAPI } from './services/api';
import ToastContainer from './components/Toast';
import { useToastStore } from './context/ToastContext';

const App = () => {
  const [currentView, setCurrentView] = useState('login');
  const [user, setUser] = useState(null);
  const [activeNav, setActiveNav] = useState('dashboard');
  const [showModal, setShowModal] = useState(null);
  const [activeTab, setActiveTab] = useState('inventory');
  const [managerTab, setManagerTab] = useState('dashboard');
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  // Data states
  const [boutiqueStock, setBoutiqueStock] = useState([]);
  const [boutiqueCategories, setBoutiqueCategories] = useState([]);
  const [boutiqueSales, setBoutiqueSales] = useState([]);
  const [boutiqueCredits, setBoutiqueCredits] = useState([]);
  const [boutiqueClearedCredits, setBoutiqueClearedCredits] = useState([]);
  const [hardwareStock, setHardwareStock] = useState([]);
  const [hardwareCategories, setHardwareCategories] = useState([]);
  const [hardwareSales, setHardwareSales] = useState([]);
  const [hardwareCredits, setHardwareCredits] = useState([]);
  const [hardwareClearedCredits, setHardwareClearedCredits] = useState([]);
  const [employees, setEmployees] = useState([]);
  const [customers, setCustomers] = useState([]);
  const [dashboardData, setDashboardData] = useState(null);
  const [loans, setLoans] = useState([]);
  const [groupLoans, setGroupLoans] = useState([]);
  const [loanPayments, setLoanPayments] = useState([]);
  const [auditLogs, setAuditLogs] = useState([]);
  const [saleItems, setSaleItems] = useState([]);

  // Form states
  const [formData, setFormData] = useState({});
  const [editingItem, setEditingItem] = useState(null);
  const [loginForm, setLoginForm] = useState({ username: '', password: '', assigned_business: '' });

  // Check for existing session
  useEffect(() => {
    const token = localStorage.getItem('token');
    const savedUser = localStorage.getItem('user');

    // Validate token is a proper JWT (has 3 parts separated by dots)
    const isValidJWT = token && token.split('.').length === 3;

    if (isValidJWT && savedUser) {
      setUser(JSON.parse(savedUser));
      setCurrentView(JSON.parse(savedUser).role === 'manager' ? 'manager' : 'employee');
    } else if (token && !isValidJWT) {
      // Clear invalid/demo token
      localStorage.removeItem('token');
      localStorage.removeItem('user');
    }
  }, []);

  // Calculate weekly revenue data from actual sales
  const getWeeklyRevenueData = () => {
    const days = ['Sun', 'Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat'];
    const today = new Date();
    const weekData = [];

    for (let i = 6; i >= 0; i--) {
      const date = new Date(today);
      date.setDate(date.getDate() - i);
      const dateStr = date.toISOString().split('T')[0];

      const boutiqueRevenue = boutiqueSales
        .filter(s => s.sale_date === dateStr)
        .reduce((sum, s) => sum + (s.total_amount || 0), 0);
      const hardwareRevenue = hardwareSales
        .filter(s => s.sale_date === dateStr)
        .reduce((sum, s) => sum + (s.total_amount || 0), 0);
      // Finance revenue from loan payments would go here
      const financeRevenue = 0;

      weekData.push({
        day: days[date.getDay()],
        boutique: boutiqueRevenue,
        hardware: hardwareRevenue,
        finance: financeRevenue
      });
    }
    return weekData;
  };

  // Calculate pie chart data from actual sales
  const getPieData = () => {
    const boutiqueTotal = boutiqueSales.reduce((sum, s) => sum + (s.total_amount || 0), 0);
    const hardwareTotal = hardwareSales.reduce((sum, s) => sum + (s.total_amount || 0), 0);
    const financeTotal = 0; // Would calculate from loan payments

    return [
      { name: 'Boutique', value: boutiqueTotal, color: '#14b8a6' },
      { name: 'Hardware', value: hardwareTotal, color: '#3b82f6' },
      { name: 'Finance', value: financeTotal, color: '#f59e0b' },
    ];
  };

  const formatMoney = (amount) => {
    if (!amount) return 'UGX 0';
    return 'UGX ' + Number(amount).toLocaleString();
  };

  // API Functions
  const handleLogin = async (manualCredentials = null) => {
    setLoading(true);
    setError('');

    // Use manual credentials if provided (for quick login buttons), otherwise use form state
    const form = manualCredentials || loginForm;

    // For development: Allow any login
    // Manager login: if username is "manager" or contains "manager"
    // Employee login: requires business unit selection

    const isManager = form.username.toLowerCase().includes('manager') || form.username.toLowerCase() === 'admin';

    if (!form.username || !form.password) {
      setError('Please enter username and password');
      setLoading(false);
      return;
    }

    if (!isManager && !form.assigned_business) {
      setError('Employees must select a business unit');
      setLoading(false);
      return;
    }

    // Login with backend
    try {
      const response = await authAPI.login(form);
      const { access_token, user } = response.data;
      localStorage.setItem('token', access_token);
      localStorage.setItem('user', JSON.stringify(user));
      setUser(user);
      setCurrentView(user.role === 'manager' ? 'manager' : 'employee');
      setActiveNav('dashboard');
    } catch (err) {
      // Show the actual error
      const errorMessage = err.response?.data?.error || 'Login failed. Make sure the backend server is running.';
      setError(errorMessage);
      console.error('Login failed:', err);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    localStorage.removeItem('token');
    localStorage.removeItem('user');
    setUser(null);
    setCurrentView('login');
    setLoginForm({ username: '', password: '', assigned_business: '' });
  };

  const loadBoutiqueData = async () => {
    try {
      const isManager = user?.role === 'manager' || user?.assigned_business === 'all';
      const promises = [
        boutiqueAPI.getStock(),
        boutiqueAPI.getCategories(),
        boutiqueAPI.getSales({ limit: 50 }),
        boutiqueAPI.getCredits()
      ];

      // Only load cleared credits for managers
      if (isManager) {
        promises.push(boutiqueAPI.getClearedCredits());
      }

      const results = await Promise.all(promises);
      const stockRes = results[0];
      const catRes = results[1];
      const salesRes = results[2];
      const creditsRes = results[3];
      const clearedRes = results[4];

      setBoutiqueStock(stockRes.data.stock || []);
      setBoutiqueCategories(catRes.data.categories || []);
      setBoutiqueSales(salesRes.data.sales || []);
      setBoutiqueCredits(creditsRes.data.credits || []);
      setBoutiqueClearedCredits(clearedRes?.data?.credits || []);
    } catch (err) {
      // Silently handle 403 (access denied) - expected for employees without access
      if (err.response?.status !== 403) {
        console.error('Error loading boutique data:', err);
      }
    }
  };

  const loadHardwareData = async () => {
    try {
      const isManager = user?.role === 'manager' || user?.assigned_business === 'all';
      const promises = [
        hardwareAPI.getStock(),
        hardwareAPI.getCategories(),
        hardwareAPI.getSales({ limit: 50 }),
        hardwareAPI.getCredits()
      ];

      // Only load cleared credits for managers
      if (isManager) {
        promises.push(hardwareAPI.getClearedCredits());
      }

      const results = await Promise.all(promises);
      const stockRes = results[0];
      const catRes = results[1];
      const salesRes = results[2];
      const creditsRes = results[3];
      const clearedRes = results[4];

      setHardwareStock(stockRes.data.stock || []);
      setHardwareCategories(catRes.data.categories || []);
      setHardwareSales(salesRes.data.sales || []);
      setHardwareCredits(creditsRes.data.credits || []);
      setHardwareClearedCredits(clearedRes?.data?.credits || []);
    } catch (err) {
      // Silently handle 403 (access denied) - expected for employees without access
      if (err.response?.status !== 403) {
        console.error('Error loading hardware data:', err);
      }
    }
  };

  const loadEmployees = async () => {
    try {
      const res = await employeesAPI.getAll();
      setEmployees(res.data.employees || []);
    } catch (err) {
      console.error('Error loading employees:', err);
    }
  };

  const loadCustomers = async () => {
    try {
      const res = await customersAPI.getAll();
      setCustomers(res.data.customers || []);
    } catch (err) {
      console.error('Error loading customers:', err);
    }
  };

  // Load data based on active nav
  useEffect(() => {
    if (currentView !== 'login' && user) {
      const isManager = user.role === 'manager' || user.assigned_business === 'all';
      const hasBoutiqueAccess = isManager || user.assigned_business === 'boutique';
      const hasHardwareAccess = isManager || user.assigned_business === 'hardware';

      // Initial load
      if (activeNav === 'boutique' && hasBoutiqueAccess) {
        loadBoutiqueData();
      }
      if (activeNav === 'hardware' && hasHardwareAccess) {
        loadHardwareData();
      }
      if (activeNav === 'employees' && isManager) {
        loadEmployees();
      }
      if (activeNav === 'dashboard') {
        if (hasBoutiqueAccess) loadBoutiqueData();
        if (hasHardwareAccess) loadHardwareData();
      }

      // Set up polling for real-time updates (every 30 seconds)
      let interval = null;
      if (activeNav === 'boutique' && hasBoutiqueAccess) {
        interval = setInterval(loadBoutiqueData, 30000);
      } else if (activeNav === 'hardware' && hasHardwareAccess) {
        interval = setInterval(loadHardwareData, 30000);
      } else if (activeNav === 'dashboard') {
        interval = setInterval(() => {
          if (hasBoutiqueAccess) loadBoutiqueData();
          if (hasHardwareAccess) loadHardwareData();
        }, 30000);
      }

      return () => {
        if (interval) clearInterval(interval);
      };
    }
  }, [activeNav, currentView, user]);

  // Load employees when accessing Settings tab
  useEffect(() => {
    if (currentView === 'manager' && managerTab === 'settings' && user) {
      loadEmployees();
    }
  }, [currentView, managerTab, user]);

  // Render login page
  if (currentView === 'login') {
    return (
      <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900">
        <div className="w-full max-w-4xl p-8">
          {/* Header */}
          <div className="text-center mb-12">
            <div className="flex justify-center mb-4">
              <div className="flex items-center gap-2 scale-150">
                <div className="flex gap-0.5">
                  <div className="w-2 h-8 bg-teal-500 rounded-sm"></div>
                  <div className="w-2 h-6 bg-teal-400 rounded-sm mt-2"></div>
                  <div className="w-2 h-7 bg-teal-500 rounded-sm mt-1"></div>
                </div>
                <div>
                  <span className="font-bold text-white text-lg">DENOVE</span>
                  <span className="text-teal-400 font-medium ml-1">APS</span>
                </div>
              </div>
            </div>
            <p className="text-slate-400 text-lg mt-6">Business Management System</p>
            <p className="text-slate-500 text-sm mt-2">Select your role to continue</p>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-8 p-4 bg-red-500/10 border border-red-500 rounded-lg text-red-400 text-center">
              {error}
            </div>
          )}

          {/* One-Click Login Buttons Grid */}
          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            {/* Manager Button */}
            <button
              onClick={async () => {
                setLoading(true);
                setError('');
                try {
                  const response = await authAPI.demoLogin('manager');
                  const { access_token, user } = response.data;
                  localStorage.setItem('token', access_token);
                  localStorage.setItem('user', JSON.stringify(user));
                  setUser(user);
                  setCurrentView('manager');
                } catch (err) {
                  setError(err.response?.data?.error || 'Login failed');
                } finally {
                  setLoading(false);
                }
              }}
              disabled={loading}
              className="group relative overflow-hidden bg-gradient-to-br from-purple-600 to-purple-800 hover:from-purple-500 hover:to-purple-700 p-8 rounded-2xl shadow-xl transition-all duration-300 hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <div className="text-6xl mb-4">👨‍💼</div>
              <h3 className="text-2xl font-bold text-white mb-2">Manager Console</h3>
              <p className="text-purple-200 text-sm">Access all business units and settings</p>
              <div className="absolute top-2 right-2 text-purple-300 opacity-0 group-hover:opacity-100 transition-opacity text-2xl">
                →
              </div>
            </button>

            {/* Boutique Button */}
            <button
              onClick={async () => {
                setLoading(true);
                setError('');
                try {
                  const response = await authAPI.demoLogin('boutique');
                  const { access_token, user } = response.data;
                  localStorage.setItem('token', access_token);
                  localStorage.setItem('user', JSON.stringify(user));
                  setUser(user);
                  setCurrentView('employee');
                } catch (err) {
                  setError(err.response?.data?.error || 'Login failed');
                } finally {
                  setLoading(false);
                }
              }}
              disabled={loading}
              className="group relative overflow-hidden bg-gradient-to-br from-pink-600 to-pink-800 hover:from-pink-500 hover:to-pink-700 p-8 rounded-2xl shadow-xl transition-all duration-300 hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <div className="text-6xl mb-4">👗</div>
              <h3 className="text-2xl font-bold text-white mb-2">Boutique</h3>
              <p className="text-pink-200 text-sm">Fashion & clothing sales</p>
              <div className="absolute top-2 right-2 text-pink-300 opacity-0 group-hover:opacity-100 transition-opacity text-2xl">
                →
              </div>
            </button>

            {/* Hardware Button */}
            <button
              onClick={async () => {
                setLoading(true);
                setError('');
                try {
                  const response = await authAPI.demoLogin('hardware');
                  const { access_token, user } = response.data;
                  localStorage.setItem('token', access_token);
                  localStorage.setItem('user', JSON.stringify(user));
                  setUser(user);
                  setCurrentView('employee');
                } catch (err) {
                  setError(err.response?.data?.error || 'Login failed');
                } finally {
                  setLoading(false);
                }
              }}
              disabled={loading}
              className="group relative overflow-hidden bg-gradient-to-br from-orange-600 to-orange-800 hover:from-orange-500 hover:to-orange-700 p-8 rounded-2xl shadow-xl transition-all duration-300 hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <div className="text-6xl mb-4">🔨</div>
              <h3 className="text-2xl font-bold text-white mb-2">Hardware</h3>
              <p className="text-orange-200 text-sm">Tools & construction materials</p>
              <div className="absolute top-2 right-2 text-orange-300 opacity-0 group-hover:opacity-100 transition-opacity text-2xl">
                →
              </div>
            </button>

            {/* Finance Button */}
            <button
              onClick={async () => {
                setLoading(true);
                setError('');
                try {
                  const response = await authAPI.demoLogin('finance');
                  const { access_token, user } = response.data;
                  localStorage.setItem('token', access_token);
                  localStorage.setItem('user', JSON.stringify(user));
                  setUser(user);
                  setCurrentView('employee');
                } catch (err) {
                  setError(err.response?.data?.error || 'Login failed');
                } finally {
                  setLoading(false);
                }
              }}
              disabled={loading}
              className="group relative overflow-hidden bg-gradient-to-br from-emerald-600 to-emerald-800 hover:from-emerald-500 hover:to-emerald-700 p-8 rounded-2xl shadow-xl transition-all duration-300 hover:scale-105 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              <div className="text-6xl mb-4">💰</div>
              <h3 className="text-2xl font-bold text-white mb-2">Finance</h3>
              <p className="text-emerald-200 text-sm">Loans & credit management</p>
              <div className="absolute top-2 right-2 text-emerald-300 opacity-0 group-hover:opacity-100 transition-opacity text-2xl">
                →
              </div>
            </button>
          </div>

          {/* Loading State */}
          {loading && (
            <div className="text-center mt-8">
              <div className="inline-block animate-spin rounded-full h-8 w-8 border-b-2 border-teal-400"></div>
              <p className="text-slate-400 mt-2">Logging in...</p>
            </div>
          )}

          {/* Info Footer */}
          <div className="mt-12 text-center text-slate-500 text-sm">
            <p>Demo Environment - No password required</p>
            <p className="mt-1">Click any button to instantly access that role</p>
          </div>
        </div>
      </div>
    );
  }

  // Logo Component
  const Logo = () => (
    <div className="flex items-center gap-2">
      <div className="flex gap-0.5">
        <div className="w-2 h-8 bg-teal-500 rounded-sm"></div>
        <div className="w-2 h-6 bg-teal-400 rounded-sm mt-2"></div>
        <div className="w-2 h-7 bg-teal-500 rounded-sm mt-1"></div>
      </div>
      <div>
        <span className="font-bold text-white text-lg">DENOVE</span>
        <span className="text-teal-400 font-medium ml-1">APS</span>
      </div>
    </div>
  );

  // Sidebar Component
  const Sidebar = ({ isManager }) => {
    const isFinanceEmployee = !isManager && user?.assigned_business === 'finances';
    const isBoutiqueEmployee = !isManager && user?.assigned_business === 'boutique';
    const isHardwareEmployee = !isManager && user?.assigned_business === 'hardware';

    return (
      <aside className="w-64 bg-slate-800 border-r border-slate-700 min-h-screen flex flex-col">
        <div className="p-5 border-b border-slate-700">
          <Logo />
          <p className="text-xs text-slate-500 mt-1">Business Management</p>
        </div>

        <nav className="flex-1 p-4 overflow-y-auto">
          {isManager ? (
            <>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 px-3">Overview</p>
              <NavItem icon="📊" label="Dashboard" id="dashboard" active={activeNav} onClick={setActiveNav} />

              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 mt-6 px-3">Business Units</p>
              <NavItem icon="👗" label="Boutique" id="boutique" active={activeNav} onClick={setActiveNav} />
              <NavItem icon="🔧" label="Hardware" id="hardware" active={activeNav} onClick={setActiveNav} />
              <NavItem icon="💰" label="Finances" id="finances" active={activeNav} onClick={setActiveNav} />

              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 mt-6 px-3">Analytics</p>
              <NavItem icon="📈" label="Reports" id="reports" active={activeNav} onClick={setActiveNav} />
              <NavItem icon="📋" label="Audit Trail" id="audit" active={activeNav} onClick={setActiveNav} />

              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 mt-6 px-3">Administration</p>
              <NavItem icon="👥" label="Employees" id="employees" active={activeNav} onClick={setActiveNav} />
              <NavItem icon="⚙️" label="Settings" id="settings" active={activeNav} onClick={setActiveNav} />
            </>
          ) : isFinanceEmployee ? (
            <>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 px-3">My Workspace</p>
              <NavItem icon="📊" label="Dashboard" id="dashboard" active={activeNav} onClick={setActiveNav} />
              <NavItem icon="➕" label="New Loan" id="newloan" active={activeNav} onClick={setActiveNav} />
              <NavItem icon="👥" label="New Group Loan" id="newgrouploan" active={activeNav} onClick={setActiveNav} />
              <NavItem icon="📋" label="Active Loans" id="activeloans" active={activeNav} onClick={setActiveNav} />
              <NavItem icon="💰" label="Record Payment" id="recordpayment" active={activeNav} onClick={setActiveNav} />
              <NavItem icon="📝" label="My Payments" id="mypayments" active={activeNav} onClick={setActiveNav} />
            </>
          ) : (
            <>
              <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider mb-3 px-3">My Workspace</p>
              <NavItem icon="📊" label="Dashboard" id="dashboard" active={activeNav} onClick={setActiveNav} />
              <NavItem icon="➕" label="New Sale" id="newsale" active={activeNav} onClick={setActiveNav} />
              <NavItem icon="📝" label="My Sales" id="mysales" active={activeNav} onClick={setActiveNav} />
              <NavItem icon="💳" label="Credits" id="credits" active={activeNav} onClick={setActiveNav} />
              <NavItem icon="📦" label="Stock" id="stock" active={activeNav} onClick={setActiveNav} />
            </>
          )}
        </nav>

        <div className="p-4 border-t border-slate-700">
          <div className="flex items-center gap-3 mb-3">
            <div className="w-10 h-10 bg-teal-500 rounded-lg flex items-center justify-center font-bold text-slate-900">
              {user?.name?.charAt(0) || 'U'}
            </div>
            <div>
              <p className="font-medium text-white text-sm">{user?.name || 'User'}</p>
              <p className="text-xs text-slate-400 capitalize">{user?.role === 'manager' ? 'Administrator' : user?.assigned_business}</p>
            </div>
          </div>
          <button
            onClick={handleLogout}
            className="w-full py-2 border border-slate-600 rounded-lg text-slate-400 text-sm hover:border-red-500 hover:text-red-400 transition-colors flex items-center justify-center gap-2"
          >
            <span>🚪</span> Logout
          </button>
        </div>
      </aside>
    );
  };

  const NavItem = ({ icon, label, id, active, onClick }) => (
    <button
      onClick={() => onClick(id)}
      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors mb-1 ${active === id
        ? 'bg-teal-500/10 text-teal-400'
        : 'text-slate-400 hover:bg-slate-700/50 hover:text-white'
        }`}
    >
      <span>{icon}</span>
      {label}
    </button>
  );

  // Stat Card Component
  const StatCard = ({ title, value, change, changeType, icon, iconBg }) => (
    <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 hover:border-teal-500/50 transition-colors">
      <div className="flex justify-between items-start mb-3">
        <div className={`w-11 h-11 ${iconBg} rounded-xl flex items-center justify-center text-xl`}>
          {icon}
        </div>
      </div>
      <p className="text-slate-400 text-sm mb-1">{title}</p>
      <p className="text-2xl font-bold text-white font-mono">{value}</p>
      {change && (
        <p className={`text-sm mt-2 ${changeType === 'up' ? 'text-green-400' : changeType === 'down' ? 'text-red-400' : 'text-slate-400'}`}>
          {changeType === 'up' ? '↑' : changeType === 'down' ? '↓' : ''} {change}
        </p>
      )}
    </div>
  );

  // Manager Dashboard
  const ManagerDashboard = () => {
    const [dashboardData, setDashboardData] = useState(null);
    const [dashboardLoading, setDashboardLoading] = useState(true);
    const toast = useToastStore();

    // Load dashboard data on mount and set up polling
    useEffect(() => {
      loadDashboardData();
      // Refresh every 30 seconds for real-time updates
      const interval = setInterval(loadDashboardData, 30000);
      return () => clearInterval(interval);
    }, []);

    const loadDashboardData = async () => {
      try {
        const res = await dashboardAPI.getManager();
        setDashboardData(res.data);
      } catch (err) {
        console.error('Error loading dashboard:', err);
      } finally {
        setDashboardLoading(false);
      }
    };

    const lowStockBoutique = boutiqueStock.filter(item => item.quantity <= item.low_stock_threshold).length;
    const lowStockHardware = hardwareStock.filter(item => item.quantity <= item.low_stock_threshold).length;
    const totalAlerts = lowStockBoutique + lowStockHardware + loans.filter(l => l.status === 'overdue').length;

    // Use dashboard API data if available, otherwise calculate from local state
    const todayRevenue = dashboardData?.stats?.today_revenue ||
      boutiqueSales.filter(s => isToday(s.sale_date)).reduce((sum, s) => sum + (s.total_amount || 0), 0) +
      hardwareSales.filter(s => isToday(s.sale_date)).reduce((sum, s) => sum + (s.total_amount || 0), 0);
    const outstandingCredits = dashboardData?.stats?.credits_outstanding ||
      boutiqueCredits.reduce((sum, c) => sum + (c.balance || 0), 0) +
      hardwareCredits.reduce((sum, c) => sum + (c.balance || 0), 0);
    const outstandingLoans = loans.reduce((sum, l) => sum + (l.balance || 0), 0);
    const todayProfit = todayRevenue * 0.3; // Simplified profit calculation

    // Business-specific data from dashboard API
    const boutiqueToday = dashboardData?.by_business?.boutique || { today: 0, transactions: 0, credits: 0, cleared_today: 0 };
    const hardwareToday = dashboardData?.by_business?.hardware || { today: 0, transactions: 0, credits: 0, cleared_today: 0 };
    const financeToday = dashboardData?.by_business?.finance || { outstanding: 0, new_loans_today: 0, repayments_today: 0, overdue_count: 0, transactions: 0 };

    // Helper function
    function isToday(dateStr) {
      const today = new Date().toDateString();
      return new Date(dateStr).toDateString() === today;
    }

    return (
      <div>
        {/* Tab Navigation */}
        <div className="mb-6 border-b border-slate-700">
          <div className="flex space-x-1">
            <button
              onClick={() => setManagerTab('dashboard')}
              className={`px-6 py-3 font-medium transition-colors relative ${
                managerTab === 'dashboard'
                  ? 'text-teal-400'
                  : 'text-slate-400 hover:text-slate-300'
              }`}
            >
              <span className="flex items-center space-x-2">
                <span>📊</span>
                <span>Dashboard</span>
              </span>
              {managerTab === 'dashboard' && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-teal-400"></div>
              )}
            </button>

            <button
              onClick={() => setManagerTab('settings')}
              className={`px-6 py-3 font-medium transition-colors relative ${
                managerTab === 'settings'
                  ? 'text-teal-400'
                  : 'text-slate-400 hover:text-slate-300'
              }`}
            >
              <span className="flex items-center space-x-2">
                <span>⚙️</span>
                <span>Settings</span>
              </span>
              {managerTab === 'settings' && (
                <div className="absolute bottom-0 left-0 right-0 h-0.5 bg-teal-400"></div>
              )}
            </button>
          </div>
        </div>

        {/* Dashboard Tab Content */}
        {managerTab === 'dashboard' && (
        <div>
        {/* Alert Banner */}
        {totalAlerts > 0 && (
          <div className="bg-amber-500/10 border border-amber-500/50 rounded-xl p-4 mb-6 flex items-center gap-3">
            <span className="text-amber-400 text-xl">⚠️</span>
            <div className="flex-1">
              <p className="text-amber-200 font-medium">{totalAlerts} items need your attention</p>
              <p className="text-amber-300/70 text-sm">
                {lowStockBoutique + lowStockHardware > 0 && `${lowStockBoutique + lowStockHardware} low stock alerts`}
                {loans.filter(l => l.status === 'overdue').length > 0 && ` • ${loans.filter(l => l.status === 'overdue').length} overdue loans`}
              </p>
            </div>
            <button onClick={() => setActiveNav(lowStockBoutique > 0 ? 'boutique' : 'hardware')} className="text-amber-400 hover:text-amber-300 text-sm font-medium">View All →</button>
          </div>
        )}

        {/* Stats Cards Row - 4 boxes */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <StatCard
            title="Today's Revenue"
            value={formatMoney(todayRevenue)}
            change="Inclusive of repayments"
            changeType="neutral"
            icon="💰"
            iconBg="bg-green-500/15"
          />
          <StatCard
            title="Outstanding Credits"
            value={formatMoney(outstandingCredits)}
            change={`${boutiqueCredits.length + hardwareCredits.length} customers`}
            icon="💳"
            iconBg="bg-amber-500/15"
          />
          <StatCard
            title="Outstanding Loans"
            value={formatMoney(financeToday.outstanding)}
            change={`${loans.filter(l => l.status !== 'paid').length} active loans`}
            icon="🏦"
            iconBg="bg-blue-500/15"
          />
          <StatCard
            title="Today's Profit"
            value={formatMoney(todayProfit)}
            change="Est. 30% margin"
            changeType="neutral"
            icon="📈"
            iconBg="bg-teal-500/15"
          />
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
          <div className="lg:col-span-2 bg-slate-800 border border-slate-700 rounded-xl p-5">
            <h3 className="font-semibold text-white mb-4">Weekly Revenue Trend</h3>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={dashboardData?.sales_trend || getWeeklyRevenueData()}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis
                  dataKey="date"
                  stroke="#64748b"
                  fontSize={12}
                  tickFormatter={(str) => {
                    const date = new Date(str);
                    return `${date.getDate()}/${date.getMonth() + 1}`;
                  }}
                />
                <YAxis stroke="#64748b" fontSize={12} tickFormatter={(v) => `${v / 1000}k`} />
                <Tooltip
                  contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
                  formatter={(value) => formatMoney(value)}
                  labelFormatter={(label) => new Date(label).toLocaleDateString()}
                />
                <Line type="monotone" dataKey="boutique" stroke="#14b8a6" strokeWidth={2} dot={false} name="Boutique" />
                <Line type="monotone" dataKey="hardware" stroke="#3b82f6" strokeWidth={2} dot={false} name="Hardware" />
                <Line type="monotone" dataKey="finance" stroke="#f59e0b" strokeWidth={2} dot={false} name="Finance Repayments" />
              </LineChart>
            </ResponsiveContainer>
            <div className="flex gap-6 mt-3 justify-center">
              <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-teal-500"></div><span className="text-xs text-slate-400">Boutique</span></div>
              <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-blue-500"></div><span className="text-xs text-slate-400">Hardware</span></div>
              <div className="flex items-center gap-2"><div className="w-3 h-3 rounded-full bg-amber-500"></div><span className="text-xs text-slate-400">Finance</span></div>
            </div>
          </div>

          <div className="bg-slate-800 border border-slate-700 rounded-xl p-5">
            <h3 className="font-semibold text-white mb-4">Revenue by Business</h3>
            <ResponsiveContainer width="100%" height={200}>
              <PieChart>
                <Pie data={getPieData()} cx="50%" cy="50%" innerRadius={50} outerRadius={80} dataKey="value">
                  {getPieData().map((entry, index) => (
                    <Cell key={index} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip formatter={(value) => formatMoney(value)} />
              </PieChart>
            </ResponsiveContainer>
            <div className="space-y-2 mt-2">
              {getPieData().map((item, i) => (
                <div key={i} className="flex justify-between items-center text-sm">
                  <div className="flex items-center gap-2">
                    <div className="w-2.5 h-2.5 rounded-full" style={{ backgroundColor: item.color }}></div>
                    <span className="text-slate-400">{item.name}</span>
                  </div>
                  <span className="text-white font-mono text-xs">{formatMoney(item.value)}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Today's Summary - 3 Business Boxes */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4 mb-6">
          <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 hover:border-teal-500/50 transition-colors">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <span className="text-xl">👗</span>
                <h4 className="font-semibold text-white">BOUTIQUE</h4>
              </div>
              {boutiqueToday.yesterday > 0 && (
                <span className={`text-sm ${boutiqueToday.today >= boutiqueToday.yesterday ? 'text-green-400' : 'text-red-400'}`}>
                  {boutiqueToday.today >= boutiqueToday.yesterday ? '↑' : '↓'} {Math.abs(Math.round((boutiqueToday.today - boutiqueToday.yesterday) / boutiqueToday.yesterday * 100))}% vs yday
                </span>
              )}
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-slate-400">Sales:</span><span className="text-white font-mono">{formatMoney(boutiqueToday.today)}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Transactions:</span><span className="text-white">{boutiqueToday.transactions}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Credits:</span><span className="text-amber-400 font-mono">{formatMoney(boutiqueToday.credits)}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Cleared:</span><span className="text-green-400 font-mono">{formatMoney(boutiqueToday.cleared_today)}</span></div>
            </div>
          </div>

          <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 hover:border-blue-500/50 transition-colors">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <span className="text-xl">🔧</span>
                <h4 className="font-semibold text-white">HARDWARE</h4>
              </div>
              {hardwareToday.yesterday > 0 && (
                <span className={`text-sm ${hardwareToday.today >= hardwareToday.yesterday ? 'text-green-400' : 'text-red-400'}`}>
                  {hardwareToday.today >= hardwareToday.yesterday ? '↑' : '↓'} {Math.abs(Math.round((hardwareToday.today - hardwareToday.yesterday) / hardwareToday.yesterday * 100))}% vs yday
                </span>
              )}
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-slate-400">Sales:</span><span className="text-white font-mono">{formatMoney(hardwareToday.today)}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Transactions:</span><span className="text-white">{hardwareToday.transactions}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Credits:</span><span className="text-amber-400 font-mono">{formatMoney(hardwareToday.credits)}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Cleared:</span><span className="text-green-400 font-mono">{formatMoney(hardwareToday.cleared_today)}</span></div>
            </div>
          </div>

          <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 hover:border-amber-500/50 transition-colors">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <span className="text-xl">💰</span>
                <h4 className="font-semibold text-white">FINANCES</h4>
              </div>
              <span className="text-slate-400 text-sm">{loans.filter(l => l.status !== 'paid').length} active</span>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-slate-400">Outstanding:</span><span className="text-white font-mono">{formatMoney(financeToday.outstanding)}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Repayments Today:</span><span className="text-green-400 font-mono">{formatMoney(financeToday.repayments_today)}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">New Loans Today:</span><span className="text-white font-mono">{formatMoney(financeToday.new_loans_today)}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Overdue:</span><span className="text-red-400 font-mono">{financeToday.overdue_count} loans</span></div>
            </div>
          </div>
        </div>

        {/* Low Stock Tables */}
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">
          <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-700 flex justify-between items-center">
              <h3 className="font-semibold text-white">Boutique Low Stock</h3>
              <button onClick={() => setActiveNav('boutique')} className="text-teal-400 text-sm hover:text-teal-300">View All →</button>
            </div>
            <div className="divide-y divide-slate-700">
              {boutiqueStock.filter(item => item.quantity <= item.low_stock_threshold).slice(0, 5).map((item, i) => (
                <div key={i} className="px-5 py-3 flex justify-between items-center">
                  <div>
                    <p className="text-white text-sm">{item.item_name}</p>
                    <p className="text-slate-400 text-xs">{item.category_name}</p>
                  </div>
                  <span className="text-red-400 font-mono text-sm">{item.quantity} left</span>
                </div>
              ))}
              {boutiqueStock.filter(item => item.quantity <= item.low_stock_threshold).length === 0 && (
                <div className="px-5 py-8 text-center text-slate-400">No low stock items</div>
              )}
            </div>
          </div>

          <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-700 flex justify-between items-center">
              <h3 className="font-semibold text-white">Hardware Low Stock</h3>
              <button onClick={() => setActiveNav('hardware')} className="text-teal-400 text-sm hover:text-teal-300">View All →</button>
            </div>
            <div className="divide-y divide-slate-700">
              {hardwareStock.filter(item => item.quantity <= item.low_stock_threshold).slice(0, 5).map((item, i) => (
                <div key={i} className="px-5 py-3 flex justify-between items-center">
                  <div>
                    <p className="text-white text-sm">{item.item_name}</p>
                    <p className="text-slate-400 text-xs">{item.category_name}</p>
                  </div>
                  <span className="text-red-400 font-mono text-sm">{item.quantity} left</span>
                </div>
              ))}
              {hardwareStock.filter(item => item.quantity <= item.low_stock_threshold).length === 0 && (
                <div className="px-5 py-8 text-center text-slate-400">No low stock items</div>
              )}
            </div>
          </div>
        </div>
        </div>
        )}

        {/* Settings Tab Content */}
        {managerTab === 'settings' && (
        <div>
          <div className="flex justify-between items-center mb-6">
            <div>
              <h2 className="text-2xl font-bold text-white mb-1">Employee Management</h2>
              <p className="text-slate-400 text-sm">Create and manage employee accounts for your business units</p>
            </div>
            <button
              onClick={() => {
                setShowModal('addEmployee');
                setFormData({
                  username: '',
                  password: '',
                  name: '',
                  assigned_business: 'boutique',
                  can_backdate: false,
                  backdate_limit: 1,
                  can_edit: true,
                  can_delete: true,
                  can_clear_credits: true,
                  is_active: true
                });
              }}
              className="px-6 py-3 bg-teal-500 hover:bg-teal-600 text-white font-medium rounded-lg transition-colors flex items-center gap-2"
            >
              <span className="text-lg">+</span>
              <span>Add Employee</span>
            </button>
          </div>

          {/* Employee Table */}
          <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full">
                <thead className="bg-slate-900 border-b border-slate-700">
                  <tr>
                    <th className="text-left py-4 px-6 text-sm font-semibold text-slate-300">Name</th>
                    <th className="text-left py-4 px-6 text-sm font-semibold text-slate-300">Username</th>
                    <th className="text-left py-4 px-6 text-sm font-semibold text-slate-300">Business</th>
                    <th className="text-left py-4 px-6 text-sm font-semibold text-slate-300">Permissions</th>
                    <th className="text-left py-4 px-6 text-sm font-semibold text-slate-300">Status</th>
                    <th className="text-left py-4 px-6 text-sm font-semibold text-slate-300">Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {employees.map((employee) => (
                    <tr key={employee.id} className="border-b border-slate-700 hover:bg-slate-750 transition-colors">
                      <td className="py-4 px-6 font-medium text-white">{employee.name}</td>
                      <td className="py-4 px-6 text-slate-400">{employee.username}</td>
                      <td className="py-4 px-6">
                        <span className={`px-3 py-1 rounded-full text-xs font-medium capitalize ${
                          employee.assigned_business === 'boutique' ? 'bg-pink-500/20 text-pink-400' :
                          employee.assigned_business === 'hardware' ? 'bg-orange-500/20 text-orange-400' :
                          employee.assigned_business === 'finances' ? 'bg-emerald-500/20 text-emerald-400' :
                          'bg-purple-500/20 text-purple-400'
                        }`}>
                          {employee.assigned_business === 'finances' ? 'finance' : employee.assigned_business}
                        </span>
                      </td>
                      <td className="py-4 px-6">
                        <div className="flex flex-wrap gap-2">
                          {employee.can_edit && (
                            <span className="text-xs text-teal-400 bg-teal-500/10 px-2 py-1 rounded">✓ Edit</span>
                          )}
                          {employee.can_delete && (
                            <span className="text-xs text-teal-400 bg-teal-500/10 px-2 py-1 rounded">✓ Delete</span>
                          )}
                          {employee.can_backdate && (
                            <span className="text-xs text-amber-400 bg-amber-500/10 px-2 py-1 rounded">⚠ Backdate ({employee.backdate_limit}d)</span>
                          )}
                        </div>
                      </td>
                      <td className="py-4 px-6">
                        <span className={`px-3 py-1 rounded-full text-xs font-medium ${
                          employee.is_active
                            ? 'bg-green-500/20 text-green-400'
                            : 'bg-red-500/20 text-red-400'
                        }`}>
                          {employee.is_active ? 'Active' : 'Inactive'}
                        </span>
                      </td>
                      <td className="py-4 px-6">
                        <div className="flex space-x-3">
                          <button
                            onClick={() => {
                              setEditingItem(employee);
                              setFormData({ ...employee, password: '' });
                              setShowModal('editEmployee');
                            }}
                            className="text-teal-400 hover:text-teal-300 text-sm font-medium transition-colors"
                          >
                            Edit
                          </button>
                          {employee.is_active ? (
                            <button
                              onClick={async () => {
                                if (confirm(`Deactivate ${employee.name}?`)) {
                                  try {
                                    await employeesAPI.delete(employee.id);
                                    loadEmployees();
                                  } catch (err) {
                                    alert('Error deactivating employee');
                                  }
                                }
                              }}
                              className="text-red-400 hover:text-red-300 text-sm font-medium transition-colors"
                            >
                              Deactivate
                            </button>
                          ) : (
                            <button
                              onClick={async () => {
                                try {
                                  await employeesAPI.update(employee.id, { is_active: true });
                                  loadEmployees();
                                } catch (err) {
                                  alert('Error reactivating employee');
                                }
                              }}
                              className="text-green-400 hover:text-green-300 text-sm font-medium transition-colors"
                            >
                              Reactivate
                            </button>
                          )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {employees.length === 0 && (
              <div className="text-center py-16 text-slate-500">
                <div className="text-6xl mb-4">👥</div>
                <p className="text-lg">No employees found</p>
                <p className="text-sm mt-2">Click "Add Employee" to create your first employee account</p>
              </div>
            )}
          </div>
        </div>
        )}
      </div>
    );
  };

  // Generic Business Page (Boutique/Hardware)
  const BusinessPage = ({ type }) => {
    const toast = useToastStore();
    const isBoutique = type === 'boutique';
    const stock = isBoutique ? boutiqueStock : hardwareStock;
    const categories = isBoutique ? boutiqueCategories : hardwareCategories;
    const sales = isBoutique ? boutiqueSales : hardwareSales;
    const credits = isBoutique ? boutiqueCredits : hardwareCredits;
    const clearedCredits = isBoutique ? boutiqueClearedCredits : hardwareClearedCredits;
    const stockAPI = isBoutique ? boutiqueAPI : hardwareAPI;

    // Local state for modals - prevents parent re-render from resetting inputs
    const [localFormData, setLocalFormData] = useState({});
    const [localShowModal, setLocalShowModal] = useState(null);
    const [localEditingItem, setLocalEditingItem] = useState(null);

    // Local state for quantity adjustment modal
    const [adjustmentData, setAdjustmentData] = useState({ adjustment: '', reason: '' });

    const handleAddStock = async () => {
      try {
        await stockAPI.addStock(localFormData);
        setLocalShowModal(null);
        setLocalFormData({});
        isBoutique ? loadBoutiqueData() : loadHardwareData();
        toast.success('Stock item added successfully');
      } catch (err) {
        setError(err.response?.data?.error || 'Failed to add item');
      }
    };

    const handleEditStock = async () => {
      try {
        await stockAPI.updateStock(localEditingItem.id, localFormData);
        setLocalShowModal(null);
        setLocalFormData({});
        setLocalEditingItem(null);
        isBoutique ? loadBoutiqueData() : loadHardwareData();
        toast.success('Stock item updated successfully');
      } catch (err) {
        setError(err.response?.data?.error || 'Failed to update item');
      }
    };

    const handleDeleteStock = async (id) => {
      if (!window.confirm('Are you sure you want to delete this item?')) return;
      try {
        await stockAPI.deleteStock(id);
        isBoutique ? loadBoutiqueData() : loadHardwareData();
        toast.success('Stock item deleted successfully');
      } catch (err) {
        setError(err.response?.data?.error || 'Failed to delete item');
      }
    };

    const handleAdjustQuantity = async () => {
      try {
        const adjustment = parseInt(adjustmentData.adjustment || 0);
        if (adjustment === 0 || isNaN(adjustment)) {
          toast.error('Please enter a valid quantity');
          return;
        }

        // Calculate new total quantity (current + adjustment)
        const newQuantity = localEditingItem.quantity + adjustment;

        if (newQuantity < 0) {
          toast.error('Cannot reduce quantity below 0');
          return;
        }

        await stockAPI.adjustQuantity(localEditingItem.id, {
          quantity: newQuantity
        });
        setLocalShowModal(null);
        setAdjustmentData({ adjustment: '', reason: '' });
        setLocalEditingItem(null);
        isBoutique ? loadBoutiqueData() : loadHardwareData();
        toast.success(`Quantity ${adjustment > 0 ? 'increased' : 'decreased'} successfully`);
      } catch (err) {
        console.error('Adjustment error:', err);
        toast.error(err.response?.data?.error || 'Failed to adjust quantity');
      }
    };

    const openAdjustQuantityModal = (item) => {
      setLocalEditingItem(item);
      setAdjustmentData({ adjustment: '', reason: '' });
      setLocalShowModal('adjustQuantity');
    };

    const handleAddCategory = async () => {
      try {
        await stockAPI.createCategory({ name: localFormData.categoryName });
        setLocalShowModal(null);
        setLocalFormData({});
        isBoutique ? loadBoutiqueData() : loadHardwareData();
        toast.success('Category added successfully');
      } catch (err) {
        setError(err.response?.data?.error || 'Failed to add category');
      }
    };

    const handleDownloadReceipt = async (saleId) => {
      try {
        const response = await stockAPI.getReceipt(saleId);
        const blob = new Blob([response.data], { type: 'application/pdf' });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `receipt_${saleId}.pdf`;
        link.click();
        window.URL.revokeObjectURL(url);
        toast.success('Receipt downloaded');
      } catch (err) {
        toast.error('Failed to download receipt');
      }
    };

    const openEditModal = (item) => {
      setLocalEditingItem(item);
      setLocalFormData({
        item_name: item.item_name,
        category_id: item.category_id,
        quantity: item.quantity,
        unit: item.unit,
        cost_price: item.cost_price,
        min_selling_price: item.min_selling_price,
        max_selling_price: item.max_selling_price,
        low_stock_threshold: item.low_stock_threshold,
      });
      setLocalShowModal('editStock');
    };

    const [selectedSale, setSelectedSale] = useState(null);

    const viewSaleDetails = (sale) => {
      setSelectedSale(sale);
      setLocalShowModal('viewSale');
    };

    return (
      <div>
        <div className="flex gap-2 mb-6 border-b border-slate-700 pb-2">
          {[
            { id: 'inventory', label: 'Inventory' },
            { id: 'sales', label: 'All Sales' },
            { id: 'credits', label: 'Credits' },
            { id: 'cleared', label: 'Cleared Credits' }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${activeTab === tab.id ? 'bg-teal-500/15 text-teal-400' : 'text-slate-400 hover:text-white'
                }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {activeTab === 'inventory' && (
          <>
            <div className="flex gap-3 mb-4">
              <div className="flex-1 relative">
                <input
                  type="text"
                  placeholder="Search items..."
                  className="w-full pl-10 pr-4 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-teal-500"
                />
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500">🔍</span>
              </div>
              <button
                onClick={() => { setLocalShowModal('addCategory'); setLocalFormData({}); }}
                className="px-4 py-2.5 bg-slate-700 hover:bg-slate-600 text-white font-medium rounded-lg flex items-center gap-2 transition-colors"
              >
                <span>📁</span> Add Category
              </button>
              <button
                onClick={() => { setLocalShowModal('addStock'); setLocalFormData({ unit: 'pieces', low_stock_threshold: 5 }); }}
                className="px-4 py-2.5 bg-teal-500 hover:bg-teal-600 text-slate-900 font-medium rounded-lg flex items-center gap-2 transition-colors"
              >
                <span>+</span> Add Item
              </button>
            </div>

            <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="bg-slate-900/50">
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Item</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Category</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Stock</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Cost</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Price Range</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700">
                  {stock.map((item, i) => (
                    <tr key={i} className={`hover:bg-slate-700/30 ${item.quantity <= item.low_stock_threshold ? 'bg-red-500/5' : ''}`}>
                      <td className="px-4 py-3 text-white flex items-center gap-2">
                        {item.quantity <= item.low_stock_threshold && <span className="text-red-400">⚠️</span>}
                        {item.item_name}
                      </td>
                      <td className="px-4 py-3 text-slate-400">{item.category_name || 'Uncategorized'}</td>
                      <td className={`px-4 py-3 font-mono ${item.quantity <= item.low_stock_threshold ? 'text-red-400' : 'text-white'}`}>
                        {item.quantity} {item.unit}
                      </td>
                      <td className="px-4 py-3 text-slate-400 font-mono">{Number(item.cost_price).toLocaleString()}</td>
                      <td className="px-4 py-3 text-white font-mono">
                        {Math.round(item.min_selling_price / 1000)}K - {Math.round(item.max_selling_price / 1000)}K
                      </td>
                      <td className="px-4 py-3">
                        <div className="flex items-center gap-1">
                          <button
                            onClick={() => openAdjustQuantityModal(item)}
                            className="px-2 py-1 text-xs bg-teal-500/10 hover:bg-teal-500/20 border border-teal-500/30 rounded text-teal-400 hover:text-teal-300 font-medium transition-colors"
                            title="Quick adjust quantity"
                          >
                            📦 Adjust Qty
                          </button>
                          <button
                            onClick={() => openEditModal(item)}
                            className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white"
                            title="Edit item"
                          >✏️</button>
                          <button
                            onClick={() => handleDeleteStock(item.id)}
                            className="p-1.5 hover:bg-red-500/20 rounded text-slate-400 hover:text-red-400"
                            title="Delete item"
                          >🗑️</button>
                        </div>
                      </td>
                    </tr>
                  ))}
                  {stock.length === 0 && (
                    <tr>
                      <td colSpan="6" className="px-4 py-8 text-center text-slate-400">
                        No items in stock. Click "Add Item" to add your first item.
                      </td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </>
        )}

        {activeTab === 'sales' && (
          <div>
            <div className="flex gap-3 mb-4">
              <button
                onClick={() => setLocalShowModal('newSale')}
                className="px-4 py-2.5 bg-teal-500 hover:bg-teal-600 text-slate-900 font-medium rounded-lg flex items-center gap-2 transition-colors"
              >
                <span>+</span> New Sale
              </button>
            </div>
            <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="bg-slate-900/50">
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Date</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Items</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Total</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Status</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Sold By</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700">
                  {sales.map((sale, i) => (
                    <tr key={i} className="hover:bg-slate-700/30">
                      <td className="px-4 py-3 text-slate-400">{new Date(sale.sale_date).toLocaleDateString()}</td>
                      <td className="px-4 py-3 text-white">
                        {sale.items?.map(item => `${item.item_name}${item.quantity > 1 ? ` (${item.quantity})` : ''}`).join(', ') || sale.customer_name || 'Walk-in'}
                      </td>
                      <td className="px-4 py-3 text-white font-mono">{formatMoney(sale.total_amount)}</td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 text-xs rounded-full ${sale.payment_status === 'paid' ? 'bg-green-500/15 text-green-400' :
                          sale.payment_status === 'partial' ? 'bg-amber-500/15 text-amber-400' :
                            'bg-red-500/15 text-red-400'
                          }`}>
                          {sale.payment_status}
                        </span>
                      </td>
                      <td className="px-4 py-3 text-slate-400">{sale.created_by_name || sale.employee_name || 'Unknown'}</td>
                      <td className="px-4 py-3">
                        <button onClick={() => viewSaleDetails(sale)} className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white" title="View Details">👁️</button>
                        <button onClick={() => toast.info('Edit functionality coming soon')} className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white" title="Edit Sale">✏️</button>
                        <button
                          onClick={() => handleDownloadReceipt(sale.id)}
                          className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white"
                          title="Download Receipt"
                        >🖨️</button>
                      </td>
                    </tr>
                  ))}
                  {sales.length === 0 && (
                    <tr>
                      <td colSpan="6" className="px-4 py-8 text-center text-slate-400">No sales recorded yet.</td>
                    </tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {activeTab === 'credits' && (
          <div className="space-y-4">
            {credits.map((credit, i) => (
              <div key={i} className="bg-slate-800 border border-slate-700 rounded-xl p-4">
                <div className="flex justify-between items-start mb-3">
                  <div>
                    <h4 className="font-medium text-white">{credit.customer_name}</h4>
                    <p className="text-slate-400 text-sm">{credit.customer_phone}</p>
                  </div>
                  <span className="px-2.5 py-1 bg-amber-500/15 text-amber-400 text-xs font-medium rounded-full">
                    {credit.payment_status}
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-4 text-sm mb-3">
                  <div><p className="text-slate-500">Sale Date</p><p className="text-white">{new Date(credit.sale_date).toLocaleDateString()}</p></div>
                  <div><p className="text-slate-500">Total Amount</p><p className="text-white font-mono">{formatMoney(credit.total_amount)}</p></div>
                  <div><p className="text-slate-500">Balance Due</p><p className="text-amber-400 font-mono font-semibold">{formatMoney(credit.balance)}</p></div>
                </div>
                <button
                  onClick={() => { setLocalShowModal('recordPayment'); setLocalEditingItem(credit); setLocalFormData({ amount: credit.balance }); }}
                  className="mt-2 w-full py-2 bg-teal-500/15 text-teal-400 rounded-lg font-medium hover:bg-teal-500/25 transition-colors"
                >
                  Record Payment
                </button>
              </div>
            ))}
            {credits.length === 0 && (
              <div className="bg-slate-800 border border-slate-700 rounded-xl p-8 text-center text-slate-400">
                No pending credits.
              </div>
            )}
          </div>
        )}

        {activeTab === 'cleared' && (
          <div className="space-y-4">
            {clearedCredits.length > 0 ? clearedCredits.map((credit, i) => (
              <div key={i} className="bg-slate-800 border border-slate-700 rounded-xl p-4">
                <div className="flex justify-between items-start mb-2">
                  <div>
                    <h4 className="font-medium text-white">{credit.customer_name}</h4>
                    <p className="text-slate-400 text-sm">{credit.customer_phone}</p>
                  </div>
                  <span className="px-2.5 py-1 bg-green-500/15 text-green-400 text-xs font-medium rounded-full">
                    Cleared 🟢
                  </span>
                </div>
                <div className="grid grid-cols-3 gap-4 text-sm">
                  <div>
                    <p className="text-slate-500">Original Amount</p>
                    <p className="text-white font-mono">{formatMoney(credit.total_amount)}</p>
                  </div>
                  <div>
                    <p className="text-slate-500">Cleared Date</p>
                    <p className="text-white">{new Date(credit.cleared_date || credit.updated_at).toLocaleDateString()}</p>
                  </div>
                  <div>
                    <p className="text-slate-500">Payments Made</p>
                    <p className="text-white">{credit.payment_count || 'N/A'}</p>
                  </div>
                </div>
              </div>
            )) : (
              <div className="bg-slate-800 border border-slate-700 rounded-xl p-8 text-center text-slate-400">
                No cleared credits yet.
              </div>
            )}
          </div>
        )}

        {/* Add Stock Modal */}
        {(localShowModal === 'addStock' || localShowModal === 'editStock') && (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-slate-800 border border-slate-700 rounded-2xl w-full max-w-lg shadow-2xl">
              <div className="flex justify-between items-center p-5 border-b border-slate-700">
                <h3 className="text-lg font-semibold text-white">{localShowModal === 'addStock' ? 'Add New Item' : 'Edit Item'}</h3>
                <button onClick={() => { setLocalShowModal(null); setLocalFormData({}); setLocalEditingItem(null); }} className="w-8 h-8 bg-slate-700 hover:bg-slate-600 rounded-lg flex items-center justify-center text-slate-400 hover:text-white">✕</button>
              </div>
              <div className="p-5 space-y-4 max-h-96 overflow-y-auto">
                <div>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Item Name *</label>
                  <input
                    type="text"
                    value={localFormData.item_name || ''}
                    onChange={(e) => setLocalFormData({ ...localFormData, item_name: e.target.value })}
                    placeholder="e.g., Ladies Dress - Floral"
                    className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Category</label>
                  <select
                    value={localFormData.category_id || ''}
                    onChange={(e) => setLocalFormData({ ...localFormData, category_id: e.target.value })}
                    className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                  >
                    <option value="">-- Select Category --</option>
                    {categories.map(cat => (
                      <option key={cat.id} value={cat.id}>{cat.name}</option>
                    ))}
                  </select>
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Quantity *</label>
                    <input
                      type="number"
                      value={localFormData.quantity || ''}
                      onChange={(e) => setLocalFormData({ ...localFormData, quantity: e.target.value })}
                      placeholder="0"
                      className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Unit</label>
                    <select
                      value={localFormData.unit || 'pieces'}
                      onChange={(e) => setLocalFormData({ ...localFormData, unit: e.target.value })}
                      className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                    >
                      <option value="pieces">pieces</option>
                      <option value="pairs">pairs</option>
                      <option value="bags">bags</option>
                      <option value="kgs">kgs</option>
                      <option value="rolls">rolls</option>
                      <option value="bottles">bottles</option>
                      <option value="boxes">boxes</option>
                    </select>
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Cost Price (UGX) *</label>
                  <input
                    type="number"
                    value={localFormData.cost_price || ''}
                    onChange={(e) => setLocalFormData({ ...localFormData, cost_price: e.target.value })}
                    placeholder="e.g., 45000"
                    className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Min Selling Price *</label>
                    <input
                      type="number"
                      value={localFormData.min_selling_price || ''}
                      onChange={(e) => setLocalFormData({ ...localFormData, min_selling_price: e.target.value })}
                      placeholder="e.g., 80000"
                      className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Max Selling Price *</label>
                    <input
                      type="number"
                      value={localFormData.max_selling_price || ''}
                      onChange={(e) => setLocalFormData({ ...localFormData, max_selling_price: e.target.value })}
                      placeholder="e.g., 95000"
                      className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Low Stock Alert Threshold</label>
                  <input
                    type="number"
                    value={localFormData.low_stock_threshold || 5}
                    onChange={(e) => setLocalFormData({ ...localFormData, low_stock_threshold: e.target.value })}
                    placeholder="5"
                    className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                  />
                </div>
              </div>
              <div className="p-5 border-t border-slate-700 flex gap-3 justify-end">
                <button onClick={() => { setLocalShowModal(null); setLocalFormData({}); setLocalEditingItem(null); }} className="px-5 py-2.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium">Cancel</button>
                <button
                  onClick={localShowModal === 'addStock' ? handleAddStock : handleEditStock}
                  className="px-5 py-2.5 bg-teal-500 hover:bg-teal-600 text-slate-900 rounded-lg font-semibold"
                >
                  {localShowModal === 'addStock' ? 'Add Item' : 'Save Changes'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Adjust Quantity Modal */}
        {localShowModal === 'adjustQuantity' && (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-slate-800 border border-slate-700 rounded-2xl w-full max-w-md shadow-2xl">
              <div className="flex justify-between items-center p-5 border-b border-slate-700">
                <h3 className="text-lg font-semibold text-white">📦 Adjust Stock Quantity</h3>
                <button onClick={() => { setLocalShowModal(null); setAdjustmentData({ adjustment: '', reason: '' }); setLocalEditingItem(null); }} className="w-8 h-8 bg-slate-700 hover:bg-slate-600 rounded-lg flex items-center justify-center text-slate-400 hover:text-white">✕</button>
              </div>
              <div className="p-5 space-y-4">
                {localEditingItem && (
                  <div className="bg-slate-900 border border-slate-700 rounded-lg p-4">
                    <div className="flex justify-between items-center mb-2">
                      <span className="text-slate-400 text-sm">Item:</span>
                      <span className="text-white font-medium">{localEditingItem.item_name}</span>
                    </div>
                    <div className="flex justify-between items-center">
                      <span className="text-slate-400 text-sm">Current Stock:</span>
                      <span className={`font-mono font-semibold ${localEditingItem.quantity <= localEditingItem.low_stock_threshold ? 'text-red-400' : 'text-teal-400'}`}>
                        {localEditingItem.quantity} {localEditingItem.unit}
                        {localEditingItem.quantity <= localEditingItem.low_stock_threshold && <span className="ml-2">⚠️ Critically Low</span>}
                      </span>
                    </div>
                    <div className="mt-2 pt-2 border-t border-slate-700 flex justify-between items-center">
                      <span className="text-slate-400 text-sm">Alert Threshold:</span>
                      <span className="text-amber-400 font-mono text-sm">{localEditingItem.low_stock_threshold} {localEditingItem.unit}</span>
                    </div>
                  </div>
                )}

                <div>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">
                    Adjustment Amount *
                    <span className="text-slate-500 normal-case ml-2">(Use + to add, - to subtract)</span>
                  </label>
                  <input
                    type="number"
                    value={adjustmentData.adjustment || ''}
                    onChange={(e) => setAdjustmentData({ ...adjustmentData, adjustment: e.target.value })}
                    placeholder="e.g., +50 or -10"
                    className="w-full px-4 py-3 bg-slate-900 border border-slate-700 rounded-lg text-white text-lg font-mono"
                    autoFocus
                  />
                  {adjustmentData.adjustment && localEditingItem && (
                    <p className="mt-2 text-sm">
                      <span className="text-slate-400">New quantity will be: </span>
                      <span className={`font-mono font-semibold ${
                        (localEditingItem.quantity + parseInt(adjustmentData.adjustment || 0)) <= localEditingItem.low_stock_threshold
                          ? 'text-red-400'
                          : 'text-teal-400'
                      }`}>
                        {localEditingItem.quantity + parseInt(adjustmentData.adjustment || 0)} {localEditingItem.unit}
                      </span>
                      {(localEditingItem.quantity + parseInt(adjustmentData.adjustment || 0)) <= localEditingItem.low_stock_threshold &&
                        <span className="text-red-400 ml-2">⚠️ Will remain critically low</span>
                      }
                      {localEditingItem.quantity <= localEditingItem.low_stock_threshold &&
                       (localEditingItem.quantity + parseInt(adjustmentData.adjustment || 0)) > localEditingItem.low_stock_threshold &&
                        <span className="text-green-400 ml-2">✓ Will be above threshold</span>
                      }
                    </p>
                  )}
                </div>

                <div>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Reason (Optional)</label>
                  <input
                    type="text"
                    value={adjustmentData.reason || ''}
                    onChange={(e) => setAdjustmentData({ ...adjustmentData, reason: e.target.value })}
                    placeholder="e.g., New stock arrival, Damaged items removed"
                    className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                  />
                </div>

                <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-3">
                  <p className="text-amber-400 text-xs">
                    <strong>💡 Tip:</strong> Use positive numbers to add stock (+50), negative to subtract (-10).
                    Stock levels update everywhere instantly.
                  </p>
                </div>
              </div>
              <div className="p-5 border-t border-slate-700 flex gap-3 justify-end">
                <button
                  onClick={() => { setLocalShowModal(null); setAdjustmentData({ adjustment: '', reason: '' }); setLocalEditingItem(null); }}
                  className="px-5 py-2.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium"
                >
                  Cancel
                </button>
                <button
                  onClick={handleAdjustQuantity}
                  disabled={!adjustmentData.adjustment || adjustmentData.adjustment === '0'}
                  className="px-5 py-2.5 bg-teal-500 hover:bg-teal-600 text-slate-900 rounded-lg font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  Apply Adjustment
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Add Category Modal */}
        {localShowModal === 'addCategory' && (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-slate-800 border border-slate-700 rounded-2xl w-full max-w-md shadow-2xl">
              <div className="flex justify-between items-center p-5 border-b border-slate-700">
                <h3 className="text-lg font-semibold text-white">Add New Category</h3>
                <button onClick={() => { setLocalShowModal(null); setLocalFormData({}); }} className="w-8 h-8 bg-slate-700 hover:bg-slate-600 rounded-lg flex items-center justify-center text-slate-400 hover:text-white">✕</button>
              </div>
              <div className="p-5">
                <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Category Name</label>
                <input
                  type="text"
                  value={localFormData.categoryName || ''}
                  onChange={(e) => setLocalFormData({ ...localFormData, categoryName: e.target.value })}
                  placeholder="e.g., Dresses, Shoes, Building Materials"
                  className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                />
              </div>
              <div className="p-5 border-t border-slate-700 flex gap-3 justify-end">
                <button onClick={() => { setLocalShowModal(null); setLocalFormData({}); }} className="px-5 py-2.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium">Cancel</button>
                <button onClick={handleAddCategory} className="px-5 py-2.5 bg-teal-500 hover:bg-teal-600 text-slate-900 rounded-lg font-semibold">Add Category</button>
              </div>
            </div>
          </div>
        )}

        {/* View Sale Details Modal */}
        {localShowModal === 'viewSale' && selectedSale && (
          <div className="fixed inset-0 bg-black/70 flex items-center justify-center z-50 p-4">
            <div className="bg-slate-800 border border-slate-700 rounded-2xl w-full max-w-lg shadow-2xl">
              <div className="px-6 py-4 border-b border-slate-700 flex justify-between items-center">
                <h3 className="font-semibold text-white">Sale Details</h3>
                <button onClick={() => { setLocalShowModal(null); setSelectedSale(null); }} className="text-slate-400 hover:text-white text-xl">✕</button>
              </div>
              <div className="p-6 space-y-4 max-h-[60vh] overflow-y-auto">
                <div className="grid grid-cols-2 gap-4 text-sm">
                  <div><span className="text-slate-400">Sale ID:</span><br /><span className="text-white font-mono">#{selectedSale.id}</span></div>
                  <div><span className="text-slate-400">Date:</span><br /><span className="text-white">{new Date(selectedSale.sale_date).toLocaleDateString()}</span></div>
                  <div><span className="text-slate-400">Customer:</span><br /><span className="text-white">{selectedSale.customer_name || 'Walk-in'}</span></div>
                  <div><span className="text-slate-400">Sold By:</span><br /><span className="text-white">{selectedSale.created_by_name || 'Unknown'}</span></div>
                </div>

                <div className="border-t border-slate-700 pt-4">
                  <h4 className="text-xs font-medium text-slate-400 uppercase mb-2">Items</h4>
                  <div className="space-y-2">
                    {selectedSale.items?.map((item, i) => (
                      <div key={i} className="flex justify-between text-sm bg-slate-900/50 rounded-lg p-3">
                        <span className="text-white">{item.item_name} × {item.quantity}</span>
                        <span className="text-white font-mono">{formatMoney(item.price_per_unit * item.quantity)}</span>
                      </div>
                    ))}
                  </div>
                </div>

                <div className="border-t border-slate-700 pt-4 space-y-2 text-sm">
                  <div className="flex justify-between"><span className="text-slate-400">Total Amount:</span><span className="text-white font-mono font-semibold">{formatMoney(selectedSale.total_amount)}</span></div>
                  <div className="flex justify-between"><span className="text-slate-400">Amount Paid:</span><span className="text-green-400 font-mono">{formatMoney(selectedSale.amount_paid)}</span></div>
                  {selectedSale.balance > 0 && (
                    <div className="flex justify-between"><span className="text-slate-400">Balance:</span><span className="text-amber-400 font-mono">{formatMoney(selectedSale.balance)}</span></div>
                  )}
                  <div className="flex justify-between"><span className="text-slate-400">Payment Status:</span>
                    <span className={`px-2 py-0.5 text-xs rounded-full ${selectedSale.payment_status === 'paid' ? 'bg-green-500/15 text-green-400' : 'bg-amber-500/15 text-amber-400'}`}>
                      {selectedSale.payment_status}
                    </span>
                  </div>
                </div>
              </div>
              <div className="p-5 border-t border-slate-700 flex gap-3 justify-end">
                <button onClick={() => handleDownloadReceipt(selectedSale.id)} className="px-4 py-2.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm">🖨️ Print Receipt</button>
                <button onClick={() => { setLocalShowModal(null); setSelectedSale(null); }} className="px-5 py-2.5 bg-teal-500 hover:bg-teal-600 text-slate-900 rounded-lg font-medium">Close</button>
              </div>
            </div>
          </div>
        )}

        {/* New Sale Modal */}
        {localShowModal === 'newSale' && (
          <NewSaleModal
            stock={stock}
            stockAPI={stockAPI}
            onClose={() => setLocalShowModal(null)}
            onSuccess={() => { setLocalShowModal(null); isBoutique ? loadBoutiqueData() : loadHardwareData(); }}
            formatMoney={formatMoney}
          />
        )}
      </div>
    );
  };

  // New Sale Modal Component (used by both Manager and Employee)
  const NewSaleModal = ({ stock, stockAPI, onClose, onSuccess, formatMoney }) => {
    const toast = useToastStore();
    const [saleItems, setSaleItems] = useState([]);
    const [paymentType, setPaymentType] = useState('full');
    const [selectedItemId, setSelectedItemId] = useState('');
    const [quantity, setQuantity] = useState(1);
    const [price, setPrice] = useState('');
    const [saleDate, setSaleDate] = useState('today');
    const [customerName, setCustomerName] = useState('');
    const [customerPhone, setCustomerPhone] = useState('');
    const [amountPaid, setAmountPaid] = useState('');
    const [otherItemName, setOtherItemName] = useState('');
    const [saleError, setSaleError] = useState('');
    const [saleLoading, setSaleLoading] = useState(false);

    const selectedItem = stock.find(item => item.id === parseInt(selectedItemId));

    const addItemToSale = () => {
      if (!selectedItemId) {
        setSaleError('Please select an item');
        return;
      }
      if (!price || price <= 0) {
        setSaleError('Please enter a valid price');
        return;
      }
      if (quantity <= 0) {
        setSaleError('Please enter a valid quantity');
        return;
      }

      if (selectedItemId !== 'other' && selectedItem) {
        if (price < selectedItem.min_selling_price || price > selectedItem.max_selling_price) {
          setSaleError(`Price must be between ${formatMoney(selectedItem.min_selling_price)} and ${formatMoney(selectedItem.max_selling_price)}`);
          return;
        }
        if (quantity > selectedItem.quantity) {
          setSaleError(`Only ${selectedItem.quantity} ${selectedItem.unit} available in stock`);
          return;
        }
      }

      const newItem = {
        id: Date.now(),
        stock_id: selectedItemId === 'other' ? null : parseInt(selectedItemId),
        item_name: selectedItemId === 'other' ? otherItemName : selectedItem?.item_name,
        quantity: parseInt(quantity),
        unit_price: parseFloat(price),
        total: parseInt(quantity) * parseFloat(price),
        is_other: selectedItemId === 'other'
      };

      setSaleItems([...saleItems, newItem]);
      setSelectedItemId('');
      setQuantity(1);
      setPrice('');
      setOtherItemName('');
      setSaleError('');
    };

    const removeItem = (itemId) => {
      setSaleItems(saleItems.filter(item => item.id !== itemId));
    };

    const totalAmount = saleItems.reduce((sum, item) => sum + item.total, 0);
    const balanceDue = paymentType === 'partial' ? totalAmount - (parseFloat(amountPaid) || 0) : 0;

    const handleCompleteSale = async () => {
      setSaleError('');

      if (saleItems.length === 0) {
        setSaleError('Please add at least one item to the sale');
        return;
      }

      if (paymentType === 'partial') {
        if (!customerName.trim()) {
          setSaleError('Customer name is required for credit sales');
          return;
        }
        if (!customerPhone.trim()) {
          setSaleError('Customer phone is required for credit sales');
          return;
        }
        if (!amountPaid || parseFloat(amountPaid) <= 0) {
          setSaleError('Please enter the amount being paid now');
          return;
        }
      }

      const saleData = {
        sale_date: saleDate === 'today' ? new Date().toISOString().split('T')[0] : new Date(Date.now() - 86400000).toISOString().split('T')[0],
        items: saleItems.map(item => ({
          stock_id: item.stock_id,
          item_name: item.item_name,
          quantity: item.quantity,
          unit_price: item.unit_price,
          is_other: item.is_other
        })),
        payment_type: paymentType === 'full' ? 'full' : 'part',
        amount_paid: paymentType === 'full' ? totalAmount : parseFloat(amountPaid),
        customer_name: paymentType === 'partial' ? customerName : null,
        customer_phone: paymentType === 'partial' ? customerPhone : null
      };

      setSaleLoading(true);
      try {
        await stockAPI.createSale(saleData);
        toast.success('Sale completed successfully!');
        onSuccess();
      } catch (err) {
        setSaleError(err.response?.data?.error || 'Failed to complete sale. Please try again.');
        setSaleLoading(false);
      }
    };

    return (
      <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
        <div className="bg-slate-800 border border-slate-700 rounded-2xl w-full max-w-2xl shadow-2xl max-h-[90vh] overflow-y-auto">
          <div className="flex justify-between items-center p-5 border-b border-slate-700 sticky top-0 bg-slate-800">
            <h3 className="text-lg font-semibold text-white">New Sale</h3>
            <button onClick={onClose} className="w-8 h-8 bg-slate-700 hover:bg-slate-600 rounded-lg flex items-center justify-center text-slate-400 hover:text-white">✕</button>
          </div>

          <div className="p-5 space-y-4">
            {saleError && (
              <div className="p-3 bg-red-500/10 border border-red-500/50 rounded-lg text-red-400 text-sm flex justify-between items-center">
                {saleError}
                <button onClick={() => setSaleError('')} className="text-red-400 hover:text-red-300">✕</button>
              </div>
            )}

            <div className="grid grid-cols-2 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Date</label>
                <select
                  value={saleDate}
                  onChange={(e) => setSaleDate(e.target.value)}
                  className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                >
                  <option value="today">Today - {new Date().toLocaleDateString()}</option>
                  <option value="yesterday">Yesterday - {new Date(Date.now() - 86400000).toLocaleDateString()}</option>
                </select>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Select Item</label>
                <select
                  value={selectedItemId}
                  onChange={(e) => {
                    setSelectedItemId(e.target.value);
                    const item = stock.find(s => s.id === parseInt(e.target.value));
                    if (item) setPrice(item.min_selling_price);
                  }}
                  className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                >
                  <option value="">-- Select item --</option>
                  {stock.map(item => (
                    <option key={item.id} value={item.id}>
                      {item.item_name} ({item.quantity} avail)
                    </option>
                  ))}
                  <option value="other">⚠️ OTHER (manual entry)</option>
                </select>
              </div>
            </div>

            {selectedItemId === 'other' && (
              <div>
                <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Item Name</label>
                <input
                  type="text"
                  value={otherItemName}
                  onChange={(e) => setOtherItemName(e.target.value)}
                  placeholder="Enter item name"
                  className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                />
              </div>
            )}

            {selectedItem && (
              <div className="bg-slate-900/50 rounded-lg p-3 text-sm">
                <p className="text-slate-400">Price range: <span className="text-white font-mono">{formatMoney(selectedItem.min_selling_price)} - {formatMoney(selectedItem.max_selling_price)}</span></p>
              </div>
            )}

            <div className="grid grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Quantity</label>
                <input
                  type="number"
                  value={quantity}
                  onChange={(e) => setQuantity(parseInt(e.target.value) || 1)}
                  min="1"
                  className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Price (UGX)</label>
                <input
                  type="number"
                  value={price}
                  onChange={(e) => setPrice(e.target.value)}
                  placeholder="Enter price"
                  className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                />
              </div>
              <div className="flex items-end">
                <button
                  onClick={addItemToSale}
                  className="w-full px-4 py-2.5 bg-teal-500/15 text-teal-400 rounded-lg font-medium hover:bg-teal-500/25"
                >
                  + Add
                </button>
              </div>
            </div>

            {saleItems.length > 0 && (
              <div className="bg-slate-900 rounded-lg p-4 border border-slate-700">
                <h4 className="text-sm font-medium text-slate-400 mb-3">ITEMS IN THIS SALE</h4>
                <div className="space-y-2">
                  {saleItems.map(item => (
                    <div key={item.id} className="flex justify-between items-center py-2 border-b border-slate-700 last:border-0">
                      <div className="flex-1">
                        <span className="text-white">{item.item_name}</span>
                        {item.is_other && <span className="text-amber-400 text-xs ml-2">(OTHER)</span>}
                        <span className="text-slate-400 text-sm ml-2">x{item.quantity} @ {formatMoney(item.unit_price)}</span>
                      </div>
                      <div className="flex items-center gap-3">
                        <span className="text-white font-mono">{formatMoney(item.total)}</span>
                        <button onClick={() => removeItem(item.id)} className="text-red-400 hover:text-red-300">✕</button>
                      </div>
                    </div>
                  ))}
                </div>
                <div className="border-t border-slate-600 mt-3 pt-3 flex justify-between">
                  <span className="font-semibold text-white">TOTAL:</span>
                  <span className="font-bold text-white font-mono text-lg">{formatMoney(totalAmount)}</span>
                </div>
              </div>
            )}

            <div>
              <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-3">Payment Type</label>
              <div className="flex gap-4">
                <label className="flex items-center gap-2 text-white cursor-pointer">
                  <input type="radio" name="modalPayment" value="full" checked={paymentType === 'full'} onChange={() => setPaymentType('full')} className="accent-teal-500" />
                  Full Payment
                </label>
                <label className="flex items-center gap-2 text-white cursor-pointer">
                  <input type="radio" name="modalPayment" value="partial" checked={paymentType === 'partial'} onChange={() => setPaymentType('partial')} className="accent-teal-500" />
                  Part Payment (Credit)
                </label>
              </div>
            </div>

            {paymentType === 'partial' && (
              <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-4 space-y-4">
                <h4 className="text-amber-400 font-medium">Customer Details</h4>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Customer Name *</label>
                    <input
                      type="text"
                      value={customerName}
                      onChange={(e) => setCustomerName(e.target.value)}
                      placeholder="Enter name"
                      className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Phone *</label>
                    <input
                      type="text"
                      value={customerPhone}
                      onChange={(e) => setCustomerPhone(e.target.value)}
                      placeholder="0700 000 000"
                      className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Amount Paying Now *</label>
                  <input
                    type="number"
                    value={amountPaid}
                    onChange={(e) => setAmountPaid(e.target.value)}
                    placeholder="Enter amount"
                    className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                  />
                  {amountPaid && totalAmount > 0 && (
                    <p className="text-amber-400 text-sm mt-2">Balance Due: {formatMoney(balanceDue)}</p>
                  )}
                </div>
              </div>
            )}
          </div>

          <div className="p-5 border-t border-slate-700 flex gap-3 justify-end sticky bottom-0 bg-slate-800">
            <button onClick={onClose} className="px-5 py-2.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium">Cancel</button>
            <button
              onClick={handleCompleteSale}
              disabled={saleItems.length === 0 || saleLoading}
              className={`px-5 py-2.5 rounded-lg font-semibold ${saleItems.length === 0 || saleLoading
                ? 'bg-slate-600 text-slate-400 cursor-not-allowed'
                : 'bg-teal-500 hover:bg-teal-600 text-slate-900'
                }`}
            >
              {saleLoading ? 'Processing...' : 'Complete Sale'}
            </button>
          </div>
        </div>
      </div>
    );
  };

  // Employees Page
  const EmployeesPage = () => {
    const toast = useToastStore();

    const handleAddEmployee = async () => {
      try {
        await employeesAPI.create(formData);
        setShowModal(null);
        setFormData({});
        loadEmployees();
        toast.success('Employee added successfully');
      } catch (err) {
        setError(err.response?.data?.error || 'Failed to add employee');
      }
    };

    const handleEditEmployee = async () => {
      try {
        await employeesAPI.update(editingItem.id, formData);
        setShowModal(null);
        setFormData({});
        setEditingItem(null);
        loadEmployees();
        toast.success('Employee updated successfully');
      } catch (err) {
        setError(err.response?.data?.error || 'Failed to update employee');
      }
    };

    const handleDeleteEmployee = async (id) => {
      if (!window.confirm('Are you sure you want to deactivate this employee?')) return;
      try {
        await employeesAPI.delete(id);
        loadEmployees();
        toast.success('Employee deactivated successfully');
      } catch (err) {
        setError(err.response?.data?.error || 'Failed to delete employee');
      }
    };

    return (
      <div>
        <div className="flex gap-3 mb-4">
          <button
            onClick={() => { setShowModal('addEmployee'); setFormData({ is_active: true, can_edit: true, can_delete: false, can_backdate: false, can_clear_credits: true }); }}
            className="px-4 py-2.5 bg-teal-500 hover:bg-teal-600 text-slate-900 font-medium rounded-lg flex items-center gap-2 transition-colors"
          >
            <span>+</span> Add Employee
          </button>
        </div>

        <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="bg-slate-900/50">
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Name</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Username</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Business</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Status</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700">
              {employees.filter(e => e.role === 'employee').map((emp, i) => (
                <tr key={i} className="hover:bg-slate-700/30">
                  <td className="px-4 py-3 text-white">{emp.name}</td>
                  <td className="px-4 py-3 text-slate-400 font-mono">{emp.username}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 text-xs rounded-full ${emp.assigned_business === 'boutique' ? 'bg-teal-500/15 text-teal-400' :
                      emp.assigned_business === 'hardware' ? 'bg-blue-500/15 text-blue-400' :
                        'bg-amber-500/15 text-amber-400'
                      }`}>
                      {emp.assigned_business}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 text-xs rounded-full ${emp.is_active ? 'bg-green-500/15 text-green-400' : 'bg-red-500/15 text-red-400'}`}>
                      {emp.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <button
                      onClick={() => {
                        setEditingItem(emp);
                        setFormData({
                          name: emp.name,
                          username: emp.username,
                          assigned_business: emp.assigned_business,
                          is_active: emp.is_active,
                          can_edit: emp.can_edit,
                          can_delete: emp.can_delete,
                          can_backdate: emp.can_backdate,
                          can_clear_credits: emp.can_clear_credits,
                        });
                        setShowModal('editEmployee');
                      }}
                      className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white"
                    >✏️</button>
                    <button
                      onClick={() => handleDeleteEmployee(emp.id)}
                      className="p-1.5 hover:bg-red-500/20 rounded text-slate-400 hover:text-red-400"
                    >🗑️</button>
                  </td>
                </tr>
              ))}
              {employees.filter(e => e.role === 'employee').length === 0 && (
                <tr>
                  <td colSpan="5" className="px-4 py-8 text-center text-slate-400">No employees yet. Click "Add Employee" to add one.</td>
                </tr>
              )}
            </tbody>
          </table>
        </div>

        {/* Add/Edit Employee Modal */}
        {(showModal === 'addEmployee' || showModal === 'editEmployee') && (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-slate-800 border border-slate-700 rounded-2xl w-full max-w-lg shadow-2xl">
              <div className="flex justify-between items-center p-5 border-b border-slate-700">
                <h3 className="text-lg font-semibold text-white">{showModal === 'addEmployee' ? 'Add New Employee' : 'Edit Employee'}</h3>
                <button onClick={() => { setShowModal(null); setFormData({}); setEditingItem(null); }} className="w-8 h-8 bg-slate-700 hover:bg-slate-600 rounded-lg flex items-center justify-center text-slate-400 hover:text-white">✕</button>
              </div>
              <div className="p-5 space-y-4 max-h-96 overflow-y-auto">
                <div>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Full Name *</label>
                  <input
                    type="text"
                    value={formData.name || ''}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="e.g., Sarah Nakato"
                    className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Username *</label>
                  <input
                    type="text"
                    value={formData.username || ''}
                    onChange={(e) => setFormData({ ...formData, username: e.target.value })}
                    placeholder="e.g., sarah"
                    className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                  />
                </div>
                {showModal === 'addEmployee' && (
                  <div>
                    <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Password *</label>
                    <input
                      type="password"
                      value={formData.password || ''}
                      onChange={(e) => setFormData({ ...formData, password: e.target.value })}
                      placeholder="Enter password"
                      className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                    />
                  </div>
                )}
                <div>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Assigned Business *</label>
                  <select
                    value={formData.assigned_business || ''}
                    onChange={(e) => setFormData({ ...formData, assigned_business: e.target.value })}
                    className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                  >
                    <option value="">-- Select Business --</option>
                    <option value="boutique">Boutique</option>
                    <option value="hardware">Hardware</option>
                    <option value="finances">Finances</option>
                  </select>
                </div>
                <div className="pt-2">
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-3">Permissions</label>
                  <div className="space-y-2">
                    <label className="flex items-center gap-2 text-white text-sm">
                      <input type="checkbox" checked={formData.can_edit || false} onChange={(e) => setFormData({ ...formData, can_edit: e.target.checked })} className="rounded" />
                      Can edit sales
                    </label>
                    <label className="flex items-center gap-2 text-white text-sm">
                      <input type="checkbox" checked={formData.can_delete || false} onChange={(e) => setFormData({ ...formData, can_delete: e.target.checked })} className="rounded" />
                      Can delete sales
                    </label>
                    <label className="flex items-center gap-2 text-white text-sm">
                      <input type="checkbox" checked={formData.can_backdate || false} onChange={(e) => setFormData({ ...formData, can_backdate: e.target.checked })} className="rounded" />
                      Can backdate entries
                    </label>
                    <label className="flex items-center gap-2 text-white text-sm">
                      <input type="checkbox" checked={formData.can_clear_credits || false} onChange={(e) => setFormData({ ...formData, can_clear_credits: e.target.checked })} className="rounded" />
                      Can clear credits
                    </label>
                    <label className="flex items-center gap-2 text-white text-sm">
                      <input type="checkbox" checked={formData.is_active !== false} onChange={(e) => setFormData({ ...formData, is_active: e.target.checked })} className="rounded" />
                      Account is active
                    </label>
                  </div>
                </div>
              </div>
              <div className="p-5 border-t border-slate-700 flex gap-3 justify-end">
                <button onClick={() => { setShowModal(null); setFormData({}); setEditingItem(null); }} className="px-5 py-2.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium">Cancel</button>
                <button
                  onClick={showModal === 'addEmployee' ? handleAddEmployee : handleEditEmployee}
                  className="px-5 py-2.5 bg-teal-500 hover:bg-teal-600 text-slate-900 rounded-lg font-semibold"
                >
                  {showModal === 'addEmployee' ? 'Add Employee' : 'Save Changes'}
                </button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  };

  // Reports Page
  const ReportsPage = () => (
    <div>
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 mb-6">
        <h3 className="font-semibold text-white mb-4">Generate Report</h3>
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Report Type</label>
            <select className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white">
              <option>Daily Sales Summary</option>
              <option>Weekly Sales Report</option>
              <option>Monthly Sales Report</option>
              <option>Profit Report</option>
              <option>Stock Report</option>
              <option>Credits Outstanding</option>
              <option>Loans Portfolio</option>
              <option>Employee Performance</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Business</label>
            <select className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white">
              <option>All Businesses</option>
              <option>Boutique</option>
              <option>Hardware</option>
              <option>Finances</option>
            </select>
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Employee</label>
            <select className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white">
              <option>All Employees</option>
              {employees.filter(e => e.role === 'employee').map(emp => (
                <option key={emp.id} value={emp.id}>{emp.name}</option>
              ))}
            </select>
          </div>
          <div className="flex items-end gap-2">
            <button className="flex-1 px-4 py-2.5 bg-teal-500 hover:bg-teal-600 text-slate-900 font-medium rounded-lg">Generate Report</button>
            <button className="px-4 py-2.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg">📥 Export to Excel</button>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-4 mt-4">
          <div>
            <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Date From</label>
            <input type="date" className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Date To</label>
            <input type="date" className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white" />
          </div>
        </div>
      </div>

      <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-700">
          <h3 className="font-semibold text-white">Weekly Sales Overview</h3>
        </div>
        <div className="p-5">
          <ResponsiveContainer width="100%" height={300}>
            <BarChart data={getWeeklyRevenueData()}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="day" stroke="#64748b" />
              <YAxis stroke="#64748b" tickFormatter={(v) => `${v / 1000000}M`} />
              <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155' }} formatter={(v) => formatMoney(v)} />
              <Bar dataKey="boutique" fill="#14b8a6" radius={[4, 4, 0, 0]} name="Boutique" />
              <Bar dataKey="hardware" fill="#3b82f6" radius={[4, 4, 0, 0]} name="Hardware" />
              <Bar dataKey="finance" fill="#f59e0b" radius={[4, 4, 0, 0]} name="Finance" />
            </BarChart>
          </ResponsiveContainer>
        </div>
        <div className="px-5 pb-5">
          <table className="w-full">
            <thead>
              <tr className="border-b border-slate-700">
                <th className="text-left py-2 text-xs font-semibold text-slate-400 uppercase">Day</th>
                <th className="text-right py-2 text-xs font-semibold text-slate-400 uppercase">Boutique</th>
                <th className="text-right py-2 text-xs font-semibold text-slate-400 uppercase">Hardware</th>
                <th className="text-right py-2 text-xs font-semibold text-slate-400 uppercase">Finance</th>
                <th className="text-right py-2 text-xs font-semibold text-slate-400 uppercase">Total</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700">
              {revenueData.map((day, i) => (
                <tr key={i}>
                  <td className="py-2 text-white">{day.day}</td>
                  <td className="py-2 text-right font-mono text-slate-300">{formatMoney(day.boutique)}</td>
                  <td className="py-2 text-right font-mono text-slate-300">{formatMoney(day.hardware)}</td>
                  <td className="py-2 text-right font-mono text-slate-300">{formatMoney(day.finance)}</td>
                  <td className="py-2 text-right font-mono text-white font-semibold">{formatMoney(day.boutique + day.hardware + day.finance)}</td>
                </tr>
              ))}
            </tbody>
            <tfoot>
              <tr className="border-t-2 border-slate-600">
                <td className="py-2 font-semibold text-white">TOTAL</td>
                <td className="py-2 text-right font-mono text-teal-400 font-semibold">{formatMoney(revenueData.reduce((s, d) => s + d.boutique, 0))}</td>
                <td className="py-2 text-right font-mono text-blue-400 font-semibold">{formatMoney(revenueData.reduce((s, d) => s + d.hardware, 0))}</td>
                <td className="py-2 text-right font-mono text-amber-400 font-semibold">{formatMoney(revenueData.reduce((s, d) => s + d.finance, 0))}</td>
                <td className="py-2 text-right font-mono text-white font-bold">{formatMoney(revenueData.reduce((s, d) => s + d.boutique + d.hardware + d.finance, 0))}</td>
              </tr>
            </tfoot>
          </table>
        </div>
      </div>
    </div>
  );

  // Finance Page (Manager View)
  const FinancePage = () => {
    const [financeTab, setFinanceTab] = useState('individual');
    const [loans, setLoans] = useState([]);
    const [groupLoans, setGroupLoans] = useState([]);
    const [payments, setPayments] = useState([]);
    const [loading, setLoading] = useState(true);
    const toast = useToastStore();

    // Load finance data
    useEffect(() => {
      loadFinanceData();
    }, []);

    const loadFinanceData = async () => {
      setLoading(true);
      try {
        const [loansRes, groupLoansRes, paymentsRes] = await Promise.all([
          financeAPI.getLoans(),
          financeAPI.getGroupLoans(),
          financeAPI.getAllPayments()
        ]);
        setLoans(loansRes.data);
        setGroupLoans(groupLoansRes.data);
        setPayments(paymentsRes.data);
      } catch (err) {
        console.error('Error loading finance data:', err);
        toast.error('Failed to load finance data');
      } finally {
        setLoading(false);
      }
    };

    const handleDeleteLoan = async (id) => {
      if (!confirm('Are you sure you want to delete this loan?')) return;
      try {
        await financeAPI.deleteLoan(id);
        toast.success('Loan deleted successfully');
        loadFinanceData();
      } catch (err) {
        toast.error('Failed to delete loan');
      }
    };

    const handleDeleteGroupLoan = async (id) => {
      if (!confirm('Are you sure you want to delete this group loan?')) return;
      try {
        await financeAPI.deleteGroupLoan(id);
        toast.success('Group loan deleted successfully');
        loadFinanceData();
      } catch (err) {
        toast.error('Failed to delete group loan');
      }
    };


    return (
      <div>
        <div className="flex gap-2 mb-6 border-b border-slate-700 pb-2">
          {[
            { id: 'individual', label: 'Individual Loans' },
            { id: 'group', label: 'Group Loans' },
            { id: 'payments', label: 'All Payments' }
          ].map(tab => (
            <button
              key={tab.id}
              onClick={() => setFinanceTab(tab.id)}
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${financeTab === tab.id ? 'bg-teal-500/15 text-teal-400' : 'text-slate-400 hover:text-white'
                }`}
            >
              {tab.label}
            </button>
          ))}
        </div>

        {financeTab === 'individual' && (
          <>
            <div className="flex gap-3 mb-4">
              <div className="flex-1 relative">
                <input type="text" placeholder="Search by name or NIN..." className="w-full pl-10 pr-4 py-2.5 bg-slate-800 border border-slate-700 rounded-lg text-white placeholder-slate-500" />
                <span className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-500">🔍</span>
              </div>
              <button onClick={() => setShowModal('newLoan')} className="px-4 py-2.5 bg-teal-500 hover:bg-teal-600 text-slate-900 font-medium rounded-lg flex items-center gap-2">
                <span>+</span> New Loan
              </button>
            </div>
            <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="bg-slate-900/50">
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Client</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">NIN</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Principal</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Rate</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Total</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Balance</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Due Date</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Status</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700">
                  {loading ? (
                    <tr><td colSpan="9" className="px-4 py-8 text-center text-slate-400">Loading loans...</td></tr>
                  ) : loans.length === 0 ? (
                    <tr><td colSpan="9" className="px-4 py-8 text-center text-slate-400">No loans found. Create a new loan to get started.</td></tr>
                  ) : loans.map((loan) => (
                    <tr key={loan.id} className="hover:bg-slate-700/30">
                      <td className="px-4 py-3 text-white">{loan.client?.name || 'Unknown'}</td>
                      <td className="px-4 py-3 text-slate-400 font-mono text-sm">{loan.client?.nin || '-'}</td>
                      <td className="px-4 py-3 text-white font-mono">{formatMoney(loan.principal)}</td>
                      <td className="px-4 py-3 text-slate-400">{loan.interest_rate}%</td>
                      <td className="px-4 py-3 text-white font-mono">{formatMoney(loan.total_amount)}</td>
                      <td className="px-4 py-3 text-amber-400 font-mono font-semibold">{formatMoney(loan.balance)}</td>
                      <td className="px-4 py-3 text-slate-400">{new Date(loan.due_date).toLocaleDateString()}</td>
                      <td className="px-4 py-3">
                        <span className="text-lg">
                          {loan.status === 'overdue' ? '🔴' : loan.status === 'due_soon' ? '🟡' : loan.status === 'paid' ? '✅' : '🟢'}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <button className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white" title="View">👁️</button>
                        <button className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white" title="Record Payment">💰</button>
                        <button onClick={() => handleDeleteLoan(loan.id)} className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-red-400" title="Delete">🗑️</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {financeTab === 'group' && (
          <>
            <div className="flex gap-3 mb-4">
              <button onClick={() => setShowModal('newGroupLoan')} className="px-4 py-2.5 bg-teal-500 hover:bg-teal-600 text-slate-900 font-medium rounded-lg flex items-center gap-2">
                <span>+</span> New Group Loan
              </button>
            </div>
            <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
              <table className="w-full">
                <thead>
                  <tr className="bg-slate-900/50">
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Group Name</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Members</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Total</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Per Period</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Periods Left</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Status</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700">
                  {loading ? (
                    <tr><td colSpan="7" className="px-4 py-8 text-center text-slate-400">Loading group loans...</td></tr>
                  ) : groupLoans.length === 0 ? (
                    <tr><td colSpan="7" className="px-4 py-8 text-center text-slate-400">No group loans found.</td></tr>
                  ) : groupLoans.map((loan) => (
                    <tr key={loan.id} className="hover:bg-slate-700/30">
                      <td className="px-4 py-3 text-white font-medium">{loan.group_name}</td>
                      <td className="px-4 py-3 text-slate-400">{loan.member_count}</td>
                      <td className="px-4 py-3 text-white font-mono">{formatMoney(loan.total_amount)}</td>
                      <td className="px-4 py-3 text-white font-mono">{formatMoney(loan.amount_per_period)}/wk</td>
                      <td className="px-4 py-3 text-slate-400">{loan.periods_left} of {loan.total_periods}</td>
                      <td className="px-4 py-3"><span className="text-lg">{loan.status === 'overdue' ? '🔴' : loan.status === 'paid' ? '✅' : '🟢'}</span></td>
                      <td className="px-4 py-3">
                        <button className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white" title="View">👁️</button>
                        <button className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white" title="Record Payment">💰</button>
                        <button onClick={() => handleDeleteGroupLoan(loan.id)} className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-red-400" title="Delete">🗑️</button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </>
        )}

        {financeTab === 'payments' && (
          <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="bg-slate-900/50">
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Date</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Client/Group</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Amount</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Balance After</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Received By</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700">
                {loading ? (
                  <tr><td colSpan="5" className="px-4 py-8 text-center text-slate-400">Loading payments...</td></tr>
                ) : payments.length === 0 ? (
                  <tr><td colSpan="5" className="px-4 py-8 text-center text-slate-400">No payments recorded yet.</td></tr>
                ) : payments.map((payment) => (
                  <tr key={payment.id} className="hover:bg-slate-700/30">
                    <td className="px-4 py-3 text-slate-400">{new Date(payment.date).toLocaleDateString()}</td>
                    <td className="px-4 py-3 text-white">{payment.client}</td>
                    <td className="px-4 py-3 text-green-400 font-mono font-semibold">{formatMoney(payment.amount)}</td>
                    <td className="px-4 py-3 text-white font-mono">{formatMoney(payment.balance_after)}</td>
                    <td className="px-4 py-3 text-slate-400">{payment.received_by}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* New Loan Modal */}
        {showModal === 'newLoan' && (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-slate-800 border border-slate-700 rounded-2xl w-full max-w-xl shadow-2xl max-h-[90vh] overflow-y-auto">
              <div className="flex justify-between items-center p-5 border-b border-slate-700 sticky top-0 bg-slate-800">
                <h3 className="text-lg font-semibold text-white">Issue New Loan</h3>
                <button onClick={() => setShowModal(null)} className="w-8 h-8 bg-slate-700 hover:bg-slate-600 rounded-lg flex items-center justify-center text-slate-400 hover:text-white">✕</button>
              </div>
              <div className="p-5 space-y-4">
                <div>
                  <h4 className="text-sm font-medium text-slate-300 mb-3">CLIENT INFORMATION</h4>
                  <div className="grid grid-cols-2 gap-4">
                    <div className="col-span-2">
                      <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Full Name *</label>
                      <input type="text" placeholder="Enter client name" className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white" />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">NIN *</label>
                      <input type="text" placeholder="CM1234567890" className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white" />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Phone *</label>
                      <input type="text" placeholder="0700 000 000" className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white" />
                    </div>
                    <div className="col-span-2">
                      <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Address</label>
                      <input type="text" placeholder="Enter address" className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white" />
                    </div>
                  </div>
                </div>

                <div className="border-t border-slate-700 pt-4">
                  <h4 className="text-sm font-medium text-slate-300 mb-3">LOAN DETAILS</h4>
                  <div className="grid grid-cols-2 gap-4">
                    <div>
                      <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Principal Amount (UGX) *</label>
                      <input type="number" placeholder="500000" className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white" />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Interest Rate (%) *</label>
                      <input type="number" defaultValue="10" className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white" />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Interest Amount</label>
                      <div className="px-4 py-2.5 bg-slate-900/50 border border-slate-700 rounded-lg text-slate-400">UGX 50,000 (auto)</div>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Total Repayment</label>
                      <div className="px-4 py-2.5 bg-slate-900/50 border border-slate-700 rounded-lg text-white font-mono">UGX 550,000</div>
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Duration (weeks) *</label>
                      <input type="number" defaultValue="4" className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white" />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Due Date</label>
                      <div className="px-4 py-2.5 bg-slate-900/50 border border-slate-700 rounded-lg text-slate-400">Feb 21, 2026 (auto)</div>
                    </div>
                  </div>
                </div>

                <div className="border-t border-slate-700 pt-4">
                  <h4 className="text-sm font-medium text-slate-300 mb-3">SECURITY DOCUMENTS</h4>
                  <div className="border-2 border-dashed border-slate-600 rounded-lg p-4 text-center">
                    <div className="text-3xl mb-2">📎</div>
                    <p className="text-slate-400 text-sm mb-2">Upload ID/Collateral Photo</p>
                    <button className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm">Choose Files</button>
                  </div>
                </div>
              </div>
              <div className="p-5 border-t border-slate-700 flex gap-3 justify-between sticky bottom-0 bg-slate-800">
                <button className="px-4 py-2.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm">🖨️ Print Loan Agreement</button>
                <div className="flex gap-3">
                  <button onClick={() => setShowModal(null)} className="px-5 py-2.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium">Cancel</button>
                  <button className="px-5 py-2.5 bg-teal-500 hover:bg-teal-600 text-slate-900 rounded-lg font-semibold">Issue Loan</button>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  };

  // Audit Trail Page (Manager Only)
  const AuditTrailPage = () => {
    const [auditLogs, setAuditLogs] = useState([]);
    const [loading, setLoading] = useState(true);
    const [filters, setFilters] = useState({
      employee_id: '',
      action: '',
      module: '',
      start_date: '',
      end_date: ''
    });

    useEffect(() => {
      loadAuditLogs();
    }, []);

    const loadAuditLogs = async () => {
      setLoading(true);
      try {
        const params = {};
        if (filters.employee_id) params.employee_id = filters.employee_id;
        if (filters.action) params.action = filters.action;
        if (filters.module) params.module = filters.module;
        if (filters.start_date) params.start_date = filters.start_date;
        if (filters.end_date) params.end_date = filters.end_date;

        const res = await dashboardAPI.getAuditLogs(params);
        setAuditLogs(res.data.audit_logs || []);
      } catch (err) {
        console.error('Error loading audit logs:', err);
      } finally {
        setLoading(false);
      }
    };

    const formatTimestamp = (isoString) => {
      if (!isoString) return 'N/A';
      const date = new Date(isoString);
      return date.toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
        hour12: true
      });
    };

    const handleFilterChange = (field, value) => {
      setFilters(prev => ({ ...prev, [field]: value }));
    };

    const applyFilters = () => {
      loadAuditLogs();
    };

    return (
      <div>
        {/* Filters */}
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-6 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Employee</label>
              <select
                value={filters.employee_id}
                onChange={(e) => handleFilterChange('employee_id', e.target.value)}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm"
              >
                <option value="">All</option>
                {employees.map(emp => (
                  <option key={emp.id} value={emp.id}>{emp.name}</option>
                ))}
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Action</label>
              <select
                value={filters.action}
                onChange={(e) => handleFilterChange('action', e.target.value)}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm"
              >
                <option value="">All</option>
                <option value="create">CREATE</option>
                <option value="update">EDIT</option>
                <option value="delete">DELETE</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Business</label>
              <select
                value={filters.module}
                onChange={(e) => handleFilterChange('module', e.target.value)}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm"
              >
                <option value="">All</option>
                <option value="boutique">Boutique</option>
                <option value="hardware">Hardware</option>
                <option value="finances">Finance</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Date From</label>
              <input
                type="date"
                value={filters.start_date}
                onChange={(e) => handleFilterChange('start_date', e.target.value)}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Date To</label>
              <input
                type="date"
                value={filters.end_date}
                onChange={(e) => handleFilterChange('end_date', e.target.value)}
                className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm"
              />
            </div>
            <div className="flex items-end">
              <button
                onClick={applyFilters}
                className="w-full px-4 py-2 bg-teal-500 hover:bg-teal-600 text-slate-900 rounded-lg font-semibold"
              >
                Apply Filters
              </button>
            </div>
          </div>
        </div>

        {/* Audit Log Table */}
        <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="bg-slate-900/50">
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Timestamp</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">User</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Action</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Business</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Details</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Flag</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700">
              {loading ? (
                <tr><td colSpan="6" className="px-4 py-8 text-center text-slate-400">Loading audit logs...</td></tr>
              ) : auditLogs.length === 0 ? (
                <tr><td colSpan="6" className="px-4 py-8 text-center text-slate-400">No audit logs found</td></tr>
              ) : auditLogs.map((log) => (
                <tr key={log.id} className={`hover:bg-slate-700/30 ${log.is_flagged ? 'bg-amber-500/5' : ''}`}>
                  <td className="px-4 py-3 text-slate-400 text-sm">{formatTimestamp(log.created_at)}</td>
                  <td className="px-4 py-3 text-white">{log.user_name || 'Unknown'}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 text-xs rounded-full ${log.action === 'create' ? 'bg-green-500/15 text-green-400' :
                      log.action === 'update' ? 'bg-amber-500/15 text-amber-400' :
                        log.action === 'delete' ? 'bg-red-500/15 text-red-400' :
                          'bg-blue-500/15 text-blue-400'
                      }`}>
                      {log.action?.toUpperCase()}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-400 capitalize">{log.module}</td>
                  <td className="px-4 py-3 text-white text-sm">{log.description}</td>
                  <td className="px-4 py-3">
                    {log.is_flagged && (
                      <span className="text-amber-400" title={log.flag_reason}>⚠️</span>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  };

  // Settings Page (Manager Only)
  const SettingsPage = () => (
    <div className="space-y-6">
      {/* Business Information */}
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-6">
        <h3 className="font-semibold text-white mb-4">Business Information</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Business Name</label>
            <input type="text" defaultValue="Denove APS" className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Phone Number</label>
            <input type="text" defaultValue="+256 700 000 000" className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Email</label>
            <input type="email" defaultValue="info@denoveaps.com" className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Address</label>
            <input type="text" defaultValue="Kampala, Uganda" className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white" />
          </div>
        </div>
        <div className="mt-4 flex justify-end">
          <button className="px-5 py-2.5 bg-teal-500 hover:bg-teal-600 text-slate-900 rounded-lg font-semibold">Save Changes</button>
        </div>
      </div>

      {/* Loan Defaults */}
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-6">
        <h3 className="font-semibold text-white mb-4">Loan Defaults</h3>
        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
          <div>
            <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Default Interest Rate (%)</label>
            <input type="number" defaultValue="10" className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Max Loan Duration (weeks)</label>
            <input type="number" defaultValue="12" className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white" />
          </div>
        </div>
        <div className="mt-4 flex justify-end">
          <button className="px-5 py-2.5 bg-teal-500 hover:bg-teal-600 text-slate-900 rounded-lg font-semibold">Save Changes</button>
        </div>
      </div>

      {/* Receipt Settings */}
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-6">
        <h3 className="font-semibold text-white mb-4">Receipt Settings</h3>
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Receipt Footer Text</label>
            <input type="text" defaultValue="Thank you for shopping with us!" className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white" />
          </div>
          <div>
            <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Loan Terms & Conditions</label>
            <textarea rows="3" defaultValue="Payment must be made by due date. Late payments may incur penalties as determined by lender." className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white resize-none" />
          </div>
        </div>
        <div className="mt-4 flex justify-end">
          <button className="px-5 py-2.5 bg-teal-500 hover:bg-teal-600 text-slate-900 rounded-lg font-semibold">Save Changes</button>
        </div>
      </div>
    </div>
  );

  // Employee Dashboard - Different for Finance vs Boutique/Hardware
  const EmployeeDashboard = () => {
    const isFinance = user?.assigned_business === 'finances';
    const isBoutique = user?.assigned_business === 'boutique';
    const businessName = user?.assigned_business?.charAt(0).toUpperCase() + user?.assigned_business?.slice(1);

    // Helper to check if date is today
    const isToday = (dateStr) => {
      if (!dateStr) return false;
      const salesDate = new Date(dateStr).toDateString();
      const today = new Date().toDateString();
      return salesDate === today;
    };

    // Get today's sales from real data (boutique or hardware based on employee assignment)
    const salesData = isBoutique ? boutiqueSales : hardwareSales;
    const todaySales = salesData
      .filter(sale => isToday(sale.sale_date))
      .map(sale => ({
        id: sale.id,
        reference: sale.reference_number,
        time: sale.created_at ? new Date(sale.created_at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true }) : 'N/A',
        items: sale.items?.map(item => item.item_name).join(', ') || 'Items',
        total: sale.total_amount,
        status: sale.payment_type === 'full' ? 'paid' : (sale.is_credit_cleared ? 'paid' : 'credit')
      }));

    // Calculate totals from real data
    const totalSalesToday = todaySales.reduce((sum, s) => sum + (s.total || 0), 0);
    const creditsData = isBoutique ? boutiqueCredits : hardwareCredits;
    const totalPendingCredits = creditsData.reduce((sum, c) => sum + (c.balance || 0), 0);
    const stockAPI = isBoutique ? boutiqueAPI : hardwareAPI;

    // Action handlers for sale actions
    const handleDeleteSale = async (saleId) => {
      if (!window.confirm('Are you sure you want to delete this sale? Stock will be restored.')) {
        return;
      }
      try {
        await stockAPI.deleteSale(saleId);
        // Reload data after deletion
        if (isBoutique) {
          loadBoutiqueData();
        } else {
          loadHardwareData();
        }
      } catch (err) {
        alert(err.response?.data?.error || 'Failed to delete sale');
      }
    };

    const handlePrintReceipt = async (saleId, reference) => {
      try {
        const response = await stockAPI.getReceipt(saleId);
        // Create a download link and trigger it
        const blob = new Blob([response.data], { type: 'application/pdf' });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `receipt_${reference || saleId}.pdf`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
      } catch (err) {
        alert(err.response?.data?.error || 'Failed to generate receipt');
      }
    };

    // State for editing sale
    const [editingSale, setEditingSale] = useState(null);
    const [editAmountPaid, setEditAmountPaid] = useState('');

    const handleEditSale = (saleId) => {
      // Find the original sale data from salesData
      const originalSale = salesData.find(s => s.id === saleId);
      if (originalSale) {
        setEditingSale(originalSale);
        setEditAmountPaid(originalSale.amount_paid);
      }
    };

    const handleSaveEdit = async () => {
      if (!editingSale) return;

      try {
        await stockAPI.updateSale(editingSale.id, {
          amount_paid: parseFloat(editAmountPaid)
        });
        // Reload data after edit
        if (isBoutique) {
          loadBoutiqueData();
        } else {
          loadHardwareData();
        }
        setEditingSale(null);
        setEditAmountPaid('');
      } catch (err) {
        alert(err.response?.data?.error || 'Failed to update sale');
      }
    };

    // Sample today's payments for Finance employees
    const todayPayments = [
      { client: 'John Mukasa', amount: 50000, balanceAfter: 400000 },
      { client: 'Kyebando Women', amount: 275000, balanceAfter: 2200000 },
    ];

    if (isFinance) {
      return (
        <div>
          <div className="bg-teal-500/10 border border-teal-500/30 rounded-xl p-4 mb-6">
            <p className="text-teal-300">👋 Welcome back, {user?.name}! You're working in <strong>Finances</strong> today.</p>
          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
            <StatCard
              title="Payments Today"
              value={formatMoney(350000)}
              change="3 payments"
              icon="💰"
              iconBg="bg-green-500/15"
            />
            <StatCard
              title="Active Loans"
              value="12 loans"
              change="2 overdue"
              changeType="down"
              icon="📋"
              iconBg="bg-amber-500/15"
            />
          </div>

          <div className="mb-6">
            <button
              onClick={() => setShowModal('recordLoanPayment')}
              className="bg-slate-800 border border-slate-700 rounded-xl p-5 hover:border-teal-500 transition-colors text-left group w-full md:w-auto"
            >
              <div className="w-12 h-12 bg-green-500/15 rounded-xl flex items-center justify-center text-2xl mb-3 group-hover:bg-green-500/25">💰</div>
              <h4 className="font-semibold text-white">Record Payment</h4>
              <p className="text-sm text-slate-400">Collect loan repayment</p>
            </button>
          </div>

          <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
            <div className="px-5 py-4 border-b border-slate-700">
              <h3 className="font-semibold text-white">My Payments - Today</h3>
            </div>
            <table className="w-full">
              <thead>
                <tr className="bg-slate-900/50">
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Client</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Amount</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Balance After</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Actions</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700">
                {todayPayments.map((payment, i) => (
                  <tr key={i} className="hover:bg-slate-700/30">
                    <td className="px-4 py-3 text-white">{payment.client}</td>
                    <td className="px-4 py-3 text-green-400 font-mono font-semibold">{formatMoney(payment.amount)}</td>
                    <td className="px-4 py-3 text-white font-mono">{formatMoney(payment.balanceAfter)}</td>
                    <td className="px-4 py-3">
                      <button className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white">✏️</button>
                      <button className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white">🖨️</button>
                    </td>
                  </tr>
                ))}
                {todayPayments.length === 0 && (
                  <tr><td colSpan="4" className="px-4 py-8 text-center text-slate-400">No payments recorded today.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      );
    }

    // Boutique or Hardware Employee Dashboard
    return (
      <div>
        <div className="bg-teal-500/10 border border-teal-500/30 rounded-xl p-4 mb-6">
          <p className="text-teal-300">👋 Welcome back, {user?.name}! You're working in <strong>{businessName}</strong> today.</p>
        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4 mb-6">
          <StatCard
            title="My Sales Today"
            value={formatMoney(totalSalesToday)}
            change={`${todaySales.length} transaction${todaySales.length !== 1 ? 's' : ''}`}
            icon="🛍️"
            iconBg="bg-teal-500/15"
          />
          <StatCard
            title="Pending Credits"
            value={formatMoney(totalPendingCredits)}
            change={`${creditsData.length} customer${creditsData.length !== 1 ? 's' : ''}`}
            icon="💳"
            iconBg="bg-amber-500/15"
          />
        </div>

        <div className="grid grid-cols-2 gap-4 mb-6">
          <button
            onClick={() => setActiveNav('newsale')}
            className="bg-slate-800 border border-slate-700 rounded-xl p-5 hover:border-teal-500 transition-colors text-left group"
          >
            <div className="w-12 h-12 bg-teal-500/15 rounded-xl flex items-center justify-center text-2xl mb-3 group-hover:bg-teal-500/25">➕</div>
            <h4 className="font-semibold text-white">New Sale</h4>
            <p className="text-sm text-slate-400">Record a new transaction</p>
          </button>
          <button
            onClick={() => setActiveNav('credits')}
            className="bg-slate-800 border border-slate-700 rounded-xl p-5 hover:border-teal-500 transition-colors text-left group"
          >
            <div className="w-12 h-12 bg-amber-500/15 rounded-xl flex items-center justify-center text-2xl mb-3 group-hover:bg-amber-500/25">💰</div>
            <h4 className="font-semibold text-white">Clear Credit</h4>
            <p className="text-sm text-slate-400">Record customer payment</p>
          </button>
        </div>

        <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-700">
            <h3 className="font-semibold text-white">Today's Transactions</h3>
          </div>
          <table className="w-full">
            <thead>
              <tr className="bg-slate-900/50">
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Time</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Items</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Total</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Status</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700">
              {todaySales.length === 0 ? (
                <tr>
                  <td colSpan="5" className="px-4 py-8 text-center text-slate-400">
                    No sales recorded today. Click "New Sale" to add one.
                  </td>
                </tr>
              ) : (
                todaySales.map((sale) => (
                  <tr key={sale.id || sale.reference} className="hover:bg-slate-700/30">
                    <td className="px-4 py-3 text-slate-400">{sale.time}</td>
                    <td className="px-4 py-3 text-white">{sale.items}</td>
                    <td className="px-4 py-3 text-white font-mono">{formatMoney(sale.total)}</td>
                    <td className="px-4 py-3">
                      <span className={`px-2 py-0.5 text-xs rounded-full ${sale.status === 'paid' ? 'bg-green-500/15 text-green-400' : 'bg-amber-500/15 text-amber-400'
                        }`}>
                        {sale.status === 'paid' ? '🟢 Paid' : '🟡 Credit'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <button onClick={() => handleEditSale(sale.id)} title="Edit sale" className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-amber-400">✏️</button>
                      <button onClick={() => handleDeleteSale(sale.id)} title="Delete sale" className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-red-400">🗑️</button>
                      <button onClick={() => handlePrintReceipt(sale.id, sale.reference)} title="Download receipt" className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-teal-400">🖨️</button>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
          <div className="px-5 py-3 border-t border-slate-700">
            <button className="text-teal-400 hover:text-teal-300 text-sm font-medium">View Yesterday's Sales →</button>
          </div>
        </div>

        {/* Edit Sale Modal */}
        {editingSale && (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-slate-800 border border-slate-700 rounded-2xl w-full max-w-md shadow-2xl">
              <div className="flex justify-between items-center p-5 border-b border-slate-700">
                <h3 className="text-lg font-semibold text-white">Edit Sale - {editingSale.reference_number}</h3>
                <button onClick={() => setEditingSale(null)} className="w-8 h-8 bg-slate-700 hover:bg-slate-600 rounded-lg flex items-center justify-center text-slate-400 hover:text-white">✕</button>
              </div>
              <div className="p-5 space-y-4">
                <div>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Sale Date</label>
                  <div className="px-4 py-2.5 bg-slate-900/50 border border-slate-700 rounded-lg text-slate-300">{editingSale.sale_date}</div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Total Amount</label>
                  <div className="px-4 py-2.5 bg-slate-900/50 border border-slate-700 rounded-lg text-white font-mono">{formatMoney(editingSale.total_amount)}</div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Amount Paid (UGX)</label>
                  <input
                    type="number"
                    value={editAmountPaid}
                    onChange={(e) => setEditAmountPaid(e.target.value)}
                    max={editingSale.total_amount}
                    min={0}
                    className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white font-mono"
                  />
                </div>
                {editAmountPaid && (
                  <div className="bg-slate-900/50 rounded-lg p-3">
                    <p className="text-slate-400 text-sm">Balance: <span className={`font-mono font-semibold ${(editingSale.total_amount - parseFloat(editAmountPaid)) > 0 ? 'text-amber-400' : 'text-green-400'}`}>
                      {formatMoney(editingSale.total_amount - parseFloat(editAmountPaid || 0))}
                    </span></p>
                  </div>
                )}
              </div>
              <div className="p-5 border-t border-slate-700 flex gap-3 justify-end">
                <button onClick={() => setEditingSale(null)} className="px-5 py-2.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium">Cancel</button>
                <button onClick={handleSaveEdit} className="px-5 py-2.5 bg-teal-500 hover:bg-teal-600 text-slate-900 rounded-lg font-semibold">Save Changes</button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  };

  // Employee Pages - New Sale
  const NewSalePage = () => {
    const [saleItems, setSaleItems] = useState([]);
    const [paymentType, setPaymentType] = useState('full');
    const [selectedItemId, setSelectedItemId] = useState('');
    const [quantity, setQuantity] = useState(1);
    const [price, setPrice] = useState('');
    const [saleDate, setSaleDate] = useState('today');
    const [customerName, setCustomerName] = useState('');
    const [customerPhone, setCustomerPhone] = useState('');
    const [amountPaid, setAmountPaid] = useState('');
    const [otherItemName, setOtherItemName] = useState('');
    const [saleError, setSaleError] = useState('');
    const [saleSuccess, setSaleSuccess] = useState('');

    const stock = user?.assigned_business === 'boutique' ? boutiqueStock : hardwareStock;
    const stockAPI = user?.assigned_business === 'boutique' ? boutiqueAPI : hardwareAPI;

    const selectedItem = stock.find(item => item.id === parseInt(selectedItemId));

    const addItemToSale = () => {
      if (!selectedItemId) {
        setSaleError('Please select an item');
        return;
      }
      if (!price || price <= 0) {
        setSaleError('Please enter a valid price');
        return;
      }
      if (quantity <= 0) {
        setSaleError('Please enter a valid quantity');
        return;
      }

      // Check price range for non-OTHER items
      if (selectedItemId !== 'other' && selectedItem) {
        if (price < selectedItem.min_selling_price || price > selectedItem.max_selling_price) {
          setSaleError(`Price must be between ${formatMoney(selectedItem.min_selling_price)} and ${formatMoney(selectedItem.max_selling_price)}`);
          return;
        }
        if (quantity > selectedItem.quantity) {
          setSaleError(`Only ${selectedItem.quantity} ${selectedItem.unit} available in stock`);
          return;
        }
      }

      const newItem = {
        id: Date.now(),
        stock_id: selectedItemId === 'other' ? null : parseInt(selectedItemId),
        item_name: selectedItemId === 'other' ? otherItemName : selectedItem?.item_name,
        quantity: parseInt(quantity),
        unit_price: parseFloat(price),
        total: parseInt(quantity) * parseFloat(price),
        is_other: selectedItemId === 'other'
      };

      setSaleItems([...saleItems, newItem]);
      setSelectedItemId('');
      setQuantity(1);
      setPrice('');
      setOtherItemName('');
      setSaleError('');
    };

    const removeItem = (itemId) => {
      setSaleItems(saleItems.filter(item => item.id !== itemId));
    };

    const totalAmount = saleItems.reduce((sum, item) => sum + item.total, 0);
    const balanceDue = paymentType === 'partial' ? totalAmount - (parseFloat(amountPaid) || 0) : 0;

    const handleCompleteSale = async () => {
      setSaleError('');
      setSaleSuccess('');

      if (saleItems.length === 0) {
        setSaleError('Please add at least one item to the sale');
        return;
      }

      if (paymentType === 'partial') {
        if (!customerName.trim()) {
          setSaleError('Customer name is required for credit sales');
          return;
        }
        if (!customerPhone.trim()) {
          setSaleError('Customer phone is required for credit sales');
          return;
        }
        // Allow amount paid to be 0 (full credit) or any positive value less than total
        const paidAmount = parseFloat(amountPaid) || 0;
        if (paidAmount < 0) {
          setSaleError('Amount paid cannot be negative');
          return;
        }
        if (paidAmount >= totalAmount) {
          setSaleError('For full payment, please select "Full Payment" option');
          return;
        }
      }

      const saleData = {
        sale_date: saleDate === 'today' ? new Date().toISOString().split('T')[0] : new Date(Date.now() - 86400000).toISOString().split('T')[0],
        items: saleItems.map(item => ({
          stock_id: item.stock_id,
          item_name: item.item_name,
          quantity: item.quantity,
          unit_price: item.unit_price,
          is_other: item.is_other
        })),
        payment_type: paymentType === 'full' ? 'full' : 'part',
        amount_paid: paymentType === 'full' ? totalAmount : (parseFloat(amountPaid) || 0),
        customer_name: paymentType === 'partial' ? customerName : null,
        customer_phone: paymentType === 'partial' ? customerPhone : null
      };

      try {
        await stockAPI.createSale(saleData);
        setSaleSuccess('Sale completed successfully!');
        // Reset form
        setSaleItems([]);
        setPaymentType('full');
        setCustomerName('');
        setCustomerPhone('');
        setAmountPaid('');
        // Reload stock data
        if (user?.assigned_business === 'boutique') {
          loadBoutiqueData();
        } else {
          loadHardwareData();
        }
        // Navigate to dashboard after 2 seconds
        setTimeout(() => {
          setActiveNav('dashboard');
        }, 2000);
      } catch (err) {
        setSaleError(err.response?.data?.error || 'Failed to complete sale. Please try again.');
      }
    };

    return (
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-6">
        <h3 className="font-semibold text-white mb-6">NEW SALE</h3>

        {saleError && (
          <div className="mb-4 p-3 bg-red-500/10 border border-red-500/50 rounded-lg text-red-400 text-sm flex justify-between items-center">
            {saleError}
            <button onClick={() => setSaleError('')} className="text-red-400 hover:text-red-300">✕</button>
          </div>
        )}

        {saleSuccess && (
          <div className="mb-4 p-3 bg-green-500/10 border border-green-500/50 rounded-lg text-green-400 text-sm">
            ✅ {saleSuccess}
          </div>
        )}

        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Date</label>
            <select
              value={saleDate}
              onChange={(e) => setSaleDate(e.target.value)}
              className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
            >
              <option value="today">Today - {new Date().toLocaleDateString()}</option>
              <option value="yesterday">Yesterday - {new Date(Date.now() - 86400000).toLocaleDateString()}</option>
            </select>
            <p className="text-xs text-slate-500 mt-1">(Cannot select older dates)</p>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Select Item</label>
            <select
              value={selectedItemId}
              onChange={(e) => {
                setSelectedItemId(e.target.value);
                const item = stock.find(s => s.id === parseInt(e.target.value));
                if (item) {
                  setPrice(item.min_selling_price);
                }
              }}
              className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
            >
              <option value="">-- Select item --</option>
              {stock.map(item => (
                <option key={item.id} value={item.id}>
                  {item.item_name} ({item.quantity} avail) • {Math.round(item.min_selling_price / 1000)}K-{Math.round(item.max_selling_price / 1000)}K
                </option>
              ))}
              <option value="other">⚠️ OTHER (manual entry)</option>
            </select>
          </div>

          {selectedItemId === 'other' && (
            <div>
              <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Item Name (Other)</label>
              <input
                type="text"
                value={otherItemName}
                onChange={(e) => setOtherItemName(e.target.value)}
                placeholder="Enter item name"
                className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
              />
              <p className="text-xs text-amber-400 mt-1">⚠️ This item is not in stock. Manager will be notified.</p>
            </div>
          )}

          {selectedItem && (
            <div className="bg-slate-900/50 rounded-lg p-3 text-sm">
              <p className="text-slate-400">Price range: <span className="text-white font-mono">{formatMoney(selectedItem.min_selling_price)} - {formatMoney(selectedItem.max_selling_price)}</span></p>
              <p className="text-slate-400">Available: <span className="text-white">{selectedItem.quantity} {selectedItem.unit}</span></p>
            </div>
          )}

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Quantity</label>
              <input
                type="number"
                value={quantity}
                onChange={(e) => setQuantity(parseInt(e.target.value) || 1)}
                min="1"
                className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
              />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Price (UGX)</label>
              <input
                type="number"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
                placeholder="Enter price"
                className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
              />
            </div>
          </div>

          <button
            onClick={addItemToSale}
            className="text-teal-400 hover:text-teal-300 text-sm font-medium bg-teal-500/10 px-4 py-2 rounded-lg hover:bg-teal-500/20 transition-colors"
          >
            + Add Item to Sale
          </button>

          {saleItems.length > 0 && (
            <div className="bg-slate-900 rounded-lg p-4 border border-slate-700">
              <h4 className="text-sm font-medium text-slate-400 mb-3">ITEMS IN THIS SALE</h4>
              <div className="space-y-2">
                {saleItems.map((item, index) => (
                  <div key={item.id} className="flex justify-between items-center py-2 border-b border-slate-700 last:border-0">
                    <div className="flex-1">
                      <span className="text-white">{item.item_name}</span>
                      {item.is_other && <span className="text-amber-400 text-xs ml-2">(OTHER)</span>}
                      <span className="text-slate-400 text-sm ml-2">x{item.quantity} @ {formatMoney(item.unit_price)}</span>
                    </div>
                    <div className="flex items-center gap-3">
                      <span className="text-white font-mono">{formatMoney(item.total)}</span>
                      <button onClick={() => removeItem(item.id)} className="text-red-400 hover:text-red-300 text-sm">✕</button>
                    </div>
                  </div>
                ))}
              </div>
              <div className="border-t border-slate-600 mt-3 pt-3 flex justify-between">
                <span className="font-semibold text-white">TOTAL:</span>
                <span className="font-bold text-white font-mono text-lg">{formatMoney(totalAmount)}</span>
              </div>
            </div>
          )}

          <div>
            <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-3">Payment Type</label>
            <div className="flex gap-4">
              <label className="flex items-center gap-2 text-white cursor-pointer">
                <input type="radio" name="payment" value="full" checked={paymentType === 'full'} onChange={() => setPaymentType('full')} className="accent-teal-500" />
                Full Payment
              </label>
              <label className="flex items-center gap-2 text-white cursor-pointer">
                <input type="radio" name="payment" value="partial" checked={paymentType === 'partial'} onChange={() => setPaymentType('partial')} className="accent-teal-500" />
                Part Payment (Credit)
              </label>
            </div>
          </div>

          {paymentType === 'partial' && (
            <div className="bg-amber-500/10 border border-amber-500/30 rounded-lg p-4 space-y-4">
              <h4 className="text-amber-400 font-medium">Customer Details (Required for credit)</h4>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Customer Name *</label>
                  <input
                    type="text"
                    value={customerName}
                    onChange={(e) => setCustomerName(e.target.value)}
                    placeholder="Enter customer name"
                    className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Phone Number *</label>
                  <input
                    type="text"
                    value={customerPhone}
                    onChange={(e) => setCustomerPhone(e.target.value)}
                    placeholder="0700 000 000"
                    className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                  />
                </div>
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Amount Paying Now (UGX) *</label>
                <input
                  type="number"
                  value={amountPaid}
                  onChange={(e) => setAmountPaid(e.target.value)}
                  placeholder="Enter amount"
                  className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                />
              </div>
              {amountPaid && totalAmount > 0 && (
                <div className="bg-slate-900 rounded-lg p-3">
                  <p className="text-slate-400 text-sm">Balance Due: <span className="text-amber-400 font-mono font-semibold">{formatMoney(balanceDue)}</span></p>
                </div>
              )}
            </div>
          )}

          <div className="flex gap-3 pt-4">
            <button
              onClick={() => setActiveNav('dashboard')}
              className="px-5 py-2.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium"
            >
              Cancel
            </button>
            <button
              onClick={handleCompleteSale}
              disabled={saleItems.length === 0}
              className={`px-5 py-2.5 rounded-lg font-semibold transition-colors ${saleItems.length === 0
                ? 'bg-slate-600 text-slate-400 cursor-not-allowed'
                : 'bg-teal-500 hover:bg-teal-600 text-slate-900'
                }`}
            >
              Complete Sale
            </button>
          </div>
        </div>
      </div>
    );
  };

  // Employee Pages - My Sales
  const MySalesPage = () => {
    const isBoutique = user?.assigned_business === 'boutique';
    const salesData = isBoutique ? boutiqueSales : hardwareSales;
    const stockAPI = isBoutique ? boutiqueAPI : hardwareAPI;

    // Helper to check if date is today or yesterday
    const isToday = (dateStr) => {
      if (!dateStr) return false;
      return new Date(dateStr).toDateString() === new Date().toDateString();
    };
    const isYesterday = (dateStr) => {
      if (!dateStr) return false;
      const yesterday = new Date(Date.now() - 86400000).toDateString();
      return new Date(dateStr).toDateString() === yesterday;
    };

    // Filter sales by date
    const todaySales = salesData.filter(sale => isToday(sale.sale_date));
    const yesterdaySales = salesData.filter(sale => isYesterday(sale.sale_date));

    // Calculate totals
    const todayTotal = todaySales.reduce((sum, s) => sum + (s.total_amount || 0), 0);
    const yesterdayTotal = yesterdaySales.reduce((sum, s) => sum + (s.total_amount || 0), 0);

    // State for editing
    const [editingSale, setEditingSale] = useState(null);
    const [editAmountPaid, setEditAmountPaid] = useState('');

    // Action handlers
    const handleEditSale = (sale) => {
      setEditingSale(sale);
      setEditAmountPaid(sale.amount_paid);
    };

    const handleSaveEdit = async () => {
      if (!editingSale) return;
      try {
        await stockAPI.updateSale(editingSale.id, {
          amount_paid: parseFloat(editAmountPaid) || 0
        });
        if (isBoutique) loadBoutiqueData();
        else loadHardwareData();
        setEditingSale(null);
      } catch (err) {
        alert(err.response?.data?.error || 'Failed to update sale');
      }
    };

    const handleDeleteSale = async (saleId) => {
      if (!window.confirm('Are you sure you want to delete this sale?')) return;
      try {
        await stockAPI.deleteSale(saleId);
        if (isBoutique) loadBoutiqueData();
        else loadHardwareData();
      } catch (err) {
        alert(err.response?.data?.error || 'Failed to delete sale');
      }
    };

    const handlePrintReceipt = async (saleId, reference) => {
      try {
        const response = await stockAPI.getReceipt(saleId);
        const blob = new Blob([response.data], { type: 'application/pdf' });
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `receipt_${reference || saleId}.pdf`;
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        window.URL.revokeObjectURL(url);
      } catch (err) {
        alert(err.response?.data?.error || 'Failed to generate receipt');
      }
    };

    // Render sales table
    const renderSalesTable = (sales, title, total) => (
      <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
        <div className="px-5 py-4 border-b border-slate-700 flex justify-between items-center">
          <h3 className="font-semibold text-white">{title}</h3>
          <span className="text-teal-400 font-mono">Total: {formatMoney(total)}</span>
        </div>
        <table className="w-full">
          <thead>
            <tr className="bg-slate-900/50">
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Time</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Items</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Total</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Status</th>
              <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Actions</th>
            </tr>
          </thead>
          <tbody className="divide-y divide-slate-700">
            {sales.length === 0 ? (
              <tr><td colSpan="5" className="px-4 py-6 text-center text-slate-400">No sales recorded</td></tr>
            ) : sales.map((sale) => (
              <tr key={sale.id} className="hover:bg-slate-700/30">
                <td className="px-4 py-3 text-slate-400">
                  {sale.created_at ? new Date(sale.created_at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: true }) : 'N/A'}
                </td>
                <td className="px-4 py-3 text-white">{sale.items?.map(i => i.item_name).join(', ') || 'Items'}</td>
                <td className="px-4 py-3 text-white font-mono">{formatMoney(sale.total_amount)}</td>
                <td className="px-4 py-3">
                  <span className={`px-2 py-0.5 text-xs rounded-full ${sale.payment_type === 'full' || sale.is_credit_cleared ? 'bg-green-500/15 text-green-400' : 'bg-amber-500/15 text-amber-400'}`}>
                    {sale.payment_type === 'full' || sale.is_credit_cleared ? '🟢 Paid' : '🟡 Credit'}
                  </span>
                </td>
                <td className="px-4 py-3">
                  <button onClick={() => handleEditSale(sale)} title="Edit" className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-amber-400">✏️</button>
                  <button onClick={() => handleDeleteSale(sale.id)} title="Delete" className="p-1.5 hover:bg-red-500/20 rounded text-slate-400 hover:text-red-400">🗑️</button>
                  <button onClick={() => handlePrintReceipt(sale.id, sale.reference_number)} title="Print" className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-teal-400">🖨️</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    );

    return (
      <div className="space-y-6">
        {renderSalesTable(todaySales, `TODAY - ${new Date().toLocaleDateString()}`, todayTotal)}
        {renderSalesTable(yesterdaySales, `YESTERDAY - ${new Date(Date.now() - 86400000).toLocaleDateString()}`, yesterdayTotal)}
        <p className="text-center text-slate-500 text-sm">Older sales are not visible to employees</p>

        {/* Edit Sale Modal */}
        {editingSale && (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-slate-800 border border-slate-700 rounded-2xl w-full max-w-md shadow-2xl">
              <div className="flex justify-between items-center p-5 border-b border-slate-700">
                <h3 className="text-lg font-semibold text-white">Edit Sale - {editingSale.reference_number}</h3>
                <button onClick={() => setEditingSale(null)} className="w-8 h-8 bg-slate-700 hover:bg-slate-600 rounded-lg flex items-center justify-center text-slate-400 hover:text-white">✕</button>
              </div>
              <div className="p-5 space-y-4">
                <div>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Total Amount</label>
                  <div className="px-4 py-2.5 bg-slate-900/50 border border-slate-700 rounded-lg text-white font-mono">{formatMoney(editingSale.total_amount)}</div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Amount Paid (UGX)</label>
                  <input
                    type="number"
                    value={editAmountPaid}
                    onChange={(e) => setEditAmountPaid(e.target.value)}
                    className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white font-mono"
                  />
                </div>
                <div className="bg-slate-900/50 rounded-lg p-3">
                  <p className="text-slate-400 text-sm">Balance: <span className="font-mono font-semibold text-amber-400">
                    {formatMoney(editingSale.total_amount - (parseFloat(editAmountPaid) || 0))}
                  </span></p>
                </div>
              </div>
              <div className="p-5 border-t border-slate-700 flex gap-3 justify-end">
                <button onClick={() => setEditingSale(null)} className="px-5 py-2.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium">Cancel</button>
                <button onClick={handleSaveEdit} className="px-5 py-2.5 bg-teal-500 hover:bg-teal-600 text-slate-900 rounded-lg font-semibold">Save Changes</button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  };

  // Employee Pages - Credits
  const EmployeeCreditsPage = () => {
    const credits = user?.assigned_business === 'boutique' ? boutiqueCredits : hardwareCredits;

    return (
      <div className="space-y-4">
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-semibold text-white">PENDING CREDITS</h3>
          <span className="text-amber-400 font-mono">Outstanding: {formatMoney(90000)}</span>
        </div>

        {credits.length > 0 ? credits.map((credit, i) => (
          <div key={i} className="bg-slate-800 border border-slate-700 rounded-xl p-4">
            <div className="flex justify-between items-start mb-3">
              <div>
                <h4 className="font-medium text-white">{credit.customer_name}</h4>
                <p className="text-slate-400 text-sm">📞 {credit.customer_phone}</p>
              </div>
              <span className="px-2.5 py-1 bg-amber-500/15 text-amber-400 text-xs font-medium rounded-full">
                🟡 Pending
              </span>
            </div>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4 text-sm mb-3">
              <div><p className="text-slate-500">Sale Date</p><p className="text-white">{new Date(credit.sale_date).toLocaleDateString()}</p></div>
              <div><p className="text-slate-500">Total</p><p className="text-white font-mono">{formatMoney(credit.total_amount)}</p></div>
              <div><p className="text-slate-500">Paid</p><p className="text-green-400 font-mono">{formatMoney(credit.amount_paid || 0)}</p></div>
              <div><p className="text-slate-500">Balance</p><p className="text-amber-400 font-mono font-semibold">{formatMoney(credit.balance)}</p></div>
            </div>
            <button
              onClick={() => { setShowModal('recordPayment'); setEditingItem(credit); }}
              className="w-full py-2 bg-teal-500/15 text-teal-400 rounded-lg font-medium hover:bg-teal-500/25 transition-colors"
            >
              Record Payment
            </button>
          </div>
        )) : (
          <div className="bg-slate-800 border border-slate-700 rounded-xl p-8 text-center text-slate-400">
            No pending credits.
          </div>
        )}

        <button className="text-teal-400 hover:text-teal-300 text-sm font-medium">View Cleared Credits →</button>
      </div>
    );
  };

  // Employee Pages - Stock (View Only)
  const EmployeeStockPage = () => {
    const stock = user?.assigned_business === 'boutique' ? boutiqueStock : hardwareStock;

    return (
      <div>
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-semibold text-white">AVAILABLE STOCK</h3>
          <span className="text-slate-400 text-sm">(View Only)</span>
        </div>

        <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="bg-slate-900/50">
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Item</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Available</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Price Range</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700">
              {stock.map((item, i) => (
                <tr key={i} className={`hover:bg-slate-700/30 ${item.quantity <= item.low_stock_threshold ? 'bg-red-500/5' : ''}`}>
                  <td className="px-4 py-3 text-white flex items-center gap-2">
                    {item.quantity <= item.low_stock_threshold && <span className="text-red-400">⚠️</span>}
                    {item.item_name}
                  </td>
                  <td className={`px-4 py-3 font-mono ${item.quantity <= item.low_stock_threshold ? 'text-red-400' : 'text-white'}`}>
                    {item.quantity} {item.unit}
                  </td>
                  <td className="px-4 py-3 text-white font-mono">
                    UGX {Number(item.min_selling_price).toLocaleString()} - {Number(item.max_selling_price).toLocaleString()}
                  </td>
                </tr>
              ))}
              {stock.length === 0 && (
                <tr><td colSpan="3" className="px-4 py-8 text-center text-slate-400">No items in stock.</td></tr>
              )}
            </tbody>
          </table>
        </div>

        <p className="text-center text-slate-500 text-sm mt-4">Contact manager to add or update stock items</p>
      </div>
    );
  };

  // Finance Employee Pages - Active Loans
  const ActiveLoansPage = () => {
    const [activeTab, setActiveTab] = useState('individual');
    const [loans, setLoans] = useState([]);
    const [groupLoans, setGroupLoans] = useState([]);
    const [loading, setLoading] = useState(true);
    const [editingLoan, setEditingLoan] = useState(null);
    const [editForm, setEditForm] = useState({});
    const toast = useToastStore();

    useEffect(() => {
      loadLoans();
    }, []);

    const loadLoans = async () => {
      setLoading(true);
      try {
        const [loansRes, groupLoansRes] = await Promise.all([
          financeAPI.getLoans(),
          financeAPI.getGroupLoans()
        ]);
        setLoans(loansRes.data || []);
        setGroupLoans(groupLoansRes.data || []);
      } catch (err) {
        console.error('Error loading loans:', err);
        toast.error('Failed to load loans');
      } finally {
        setLoading(false);
      }
    };

    const handleDeleteLoan = async (id, type) => {
      if (!window.confirm(`Are you sure you want to delete this ${type} loan?`)) return;
      try {
        if (type === 'individual') {
          await financeAPI.deleteLoan(id);
        } else {
          await financeAPI.deleteGroupLoan(id);
        }
        toast.success(`${type === 'individual' ? 'Loan' : 'Group loan'} deleted successfully`);
        loadLoans();
      } catch (err) {
        toast.error(err.response?.data?.error || 'Failed to delete loan');
      }
    };

    const handleEditLoan = (loan, type) => {
      setEditingLoan({ ...loan, type });
      setEditForm(type === 'individual' ? {
        principal: loan.principal,
        interest_rate: loan.interest_rate,
        duration_weeks: loan.duration_weeks
      } : {
        group_name: loan.group_name,
        member_count: loan.member_count,
        total_amount: loan.total_amount,
        amount_per_period: loan.amount_per_period,
        total_periods: loan.total_periods
      });
    };

    const handleSaveEdit = async () => {
      if (!editingLoan) return;
      try {
        if (editingLoan.type === 'individual') {
          await financeAPI.updateLoan(editingLoan.id, editForm);
        } else {
          await financeAPI.updateGroupLoan(editingLoan.id, editForm);
        }
        toast.success('Loan updated successfully');
        setEditingLoan(null);
        loadLoans();
      } catch (err) {
        toast.error(err.response?.data?.error || 'Failed to update loan');
      }
    };

    const handlePrintLoan = (loan) => {
      // For now, simpler print or download stub
      const loanDetails = `
        LOAN AGREEMENT
        --------------
        Client: ${loan.client?.name || loan.group_name || 'N/A'}
        Amount: ${formatMoney(loan.total_amount)}
        Balance: ${formatMoney(loan.balance)}
        Due Date: ${loan.due_date ? new Date(loan.due_date).toLocaleDateString() : 'N/A'}
      `;
      // Create a temporary window to print
      const printWindow = window.open('', '_blank');
      printWindow.document.write(`<pre>${loanDetails}</pre>`);
      printWindow.document.close();
      printWindow.print();
    };

    return (
      <div>
        <div className="flex justify-between items-center mb-6">
          <h3 className="text-lg font-semibold text-white">ACTIVE LOANS</h3>
          <div className="flex gap-2">
            <button
              onClick={() => setActiveTab('individual')}
              className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${activeTab === 'individual' ? 'bg-teal-500/20 text-teal-400' : 'text-slate-400 hover:text-white'}`}
            >
              Individual Loans
            </button>
            <button
              onClick={() => setActiveTab('group')}
              className={`px-3 py-1.5 rounded-lg text-sm transition-colors ${activeTab === 'group' ? 'bg-teal-500/20 text-teal-400' : 'text-slate-400 hover:text-white'}`}
            >
              Group Loans
            </button>
          </div>
        </div>

        {activeTab === 'individual' ? (
          <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="bg-slate-900/50">
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Client</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Total Due</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Balance</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Due Date</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Status</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700">
                {loading ? (
                  <tr><td colSpan="6" className="px-4 py-8 text-center text-slate-400">Loading loans...</td></tr>
                ) : loans.length === 0 ? (
                  <tr><td colSpan="6" className="px-4 py-8 text-center text-slate-400">No active loans found.</td></tr>
                ) : loans.map((loan) => (
                  <tr key={loan.id} className="hover:bg-slate-700/30">
                    <td className="px-4 py-3 text-white">{loan.client?.name || 'Unknown'}</td>
                    <td className="px-4 py-3 text-white font-mono">{formatMoney(loan.total_amount)}</td>
                    <td className="px-4 py-3 text-amber-400 font-mono font-semibold">{formatMoney(loan.balance)}</td>
                    <td className="px-4 py-3 text-slate-400">{new Date(loan.due_date).toLocaleDateString()}</td>
                    <td className="px-4 py-3">
                      <span className="text-lg" title={loan.status}>
                        {loan.status === 'overdue' ? '🔴' : loan.status === 'due_soon' ? '🟡' : loan.status === 'paid' ? '✅' : '🟢'}
                      </span>
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2">
                        <button onClick={() => handleEditLoan(loan, 'individual')} title="Edit" className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-amber-400">✏️</button>
                        <button onClick={() => handleDeleteLoan(loan.id, 'individual')} title="Delete" className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-red-400">🗑️</button>
                        <button onClick={() => handlePrintLoan(loan)} title="Print Document" className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-teal-400">🖨️</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        ) : (
          <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
            <table className="w-full">
              <thead>
                <tr className="bg-slate-900/50">
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Group Name</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Members</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Total Due</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Balance</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Period Pay</th>
                  <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Action</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-700">
                {loading ? (
                  <tr><td colSpan="6" className="px-4 py-8 text-center text-slate-400">Loading group loans...</td></tr>
                ) : groupLoans.length === 0 ? (
                  <tr><td colSpan="6" className="px-4 py-8 text-center text-slate-400">No active group loans found.</td></tr>
                ) : groupLoans.map((loan) => (
                  <tr key={loan.id} className="hover:bg-slate-700/30">
                    <td className="px-4 py-3 text-white">{loan.group_name}</td>
                    <td className="px-4 py-3 text-slate-400">{loan.member_count}</td>
                    <td className="px-4 py-3 text-white font-mono">{formatMoney(loan.total_amount)}</td>
                    <td className="px-4 py-3 text-amber-400 font-mono font-semibold">{formatMoney(loan.balance)}</td>
                    <td className="px-4 py-3 text-slate-400 font-mono">{formatMoney(loan.amount_per_period)}</td>
                    <td className="px-4 py-3">
                      <div className="flex gap-2">
                        <button onClick={() => handleEditLoan(loan, 'group')} title="Edit" className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-amber-400">✏️</button>
                        <button onClick={() => handleDeleteLoan(loan.id, 'group')} title="Delete" className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-red-400">🗑️</button>
                        <button onClick={() => handlePrintLoan(loan)} title="Print Document" className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-teal-400">🖨️</button>
                      </div>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {/* Edit Loan Modal */}
        {editingLoan && (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-slate-800 border border-slate-700 rounded-2xl w-full max-w-md shadow-2xl">
              <div className="flex justify-between items-center p-5 border-b border-slate-700">
                <h3 className="text-lg font-semibold text-white">Edit {editingLoan.type === 'individual' ? 'Loan' : 'Group Loan'}</h3>
                <button onClick={() => setEditingLoan(null)} className="w-8 h-8 bg-slate-700 hover:bg-slate-600 rounded-lg flex items-center justify-center text-slate-400 hover:text-white">✕</button>
              </div>
              <div className="p-5 space-y-4">
                {editingLoan.type === 'individual' ? (
                  <>
                    <div>
                      <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Principal</label>
                      <input
                        type="number"
                        value={editForm.principal || ''}
                        onChange={(e) => setEditForm({ ...editForm, principal: e.target.value })}
                        className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Interest Rate (%)</label>
                      <input
                        type="number"
                        value={editForm.interest_rate || ''}
                        onChange={(e) => setEditForm({ ...editForm, interest_rate: e.target.value })}
                        className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                      />
                    </div>
                  </>
                ) : (
                  <>
                    <div>
                      <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Group Name</label>
                      <input
                        type="text"
                        value={editForm.group_name || ''}
                        onChange={(e) => setEditForm({ ...editForm, group_name: e.target.value })}
                        className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Total Amount</label>
                      <input
                        type="number"
                        value={editForm.total_amount || ''}
                        onChange={(e) => setEditForm({ ...editForm, total_amount: e.target.value })}
                        className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                      />
                    </div>
                  </>
                )}
              </div>
              <div className="p-5 border-t border-slate-700 flex gap-3 justify-end">
                <button onClick={() => setEditingLoan(null)} className="px-5 py-2.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium">Cancel</button>
                <button onClick={handleSaveEdit} className="px-5 py-2.5 bg-teal-500 hover:bg-teal-600 text-slate-900 rounded-lg font-semibold">Save Changes</button>
              </div>
            </div>
          </div>
        )}
      </div>
    );
  };

  // Finance Employee Pages - New Loan (Create Loan)
  const NewLoanPage = () => {
    const [clients, setClients] = useState([]);
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const [showNewClientForm, setShowNewClientForm] = useState(false);
    const [selectedFiles, setSelectedFiles] = useState(null);
    const fileInputRef = useRef(null);

    // Combined form state for smoother UI flow
    const [formData, setFormData] = useState({
      client_id: '',
      principal: '',
      interest_rate: '10',
      duration_weeks: '4',
      // New client fields if needed
      name: '',
      phone: '',
      nin: '',
      address: ''
    });

    const toast = useToastStore();

    useEffect(() => {
      loadClients();
    }, []);

    const loadClients = async () => {
      try {
        const res = await financeAPI.getClients();
        setClients(res.data || []);
      } catch (err) {
        console.error('Error loading clients:', err);
      } finally {
        setLoading(false);
      }
    };

    // Derived values
    const principal = parseFloat(formData.principal) || 0;
    const interestRate = parseFloat(formData.interest_rate) || 0;
    const interestAmount = principal * (interestRate / 100);
    const totalAmount = principal + interestAmount;
    const durationWeeks = parseInt(formData.duration_weeks) || 4;

    const dueDate = new Date();
    dueDate.setDate(dueDate.getDate() + (durationWeeks * 7));
    const dueDateStr = dueDate.toLocaleDateString(undefined, { year: 'numeric', month: 'short', day: 'numeric' });

    const handleClientChange = (e) => {
      const value = e.target.value;
      if (value === 'new') {
        setShowNewClientForm(true);
        setFormData({ ...formData, client_id: '' });
      } else {
        setShowNewClientForm(false);
        setFormData({ ...formData, client_id: value });
      }
    };

    const handleFileChange = (e) => {
      if (e.target.files && e.target.files.length > 0) {
        setSelectedFiles(e.target.files);
      }
    };

    const handlePrintAgreement = () => {
      const clientName = showNewClientForm ? formData.name : clients.find(c => c.id == formData.client_id)?.name || '_________________';
      const clientNIN = showNewClientForm ? formData.nin : clients.find(c => c.id == formData.client_id)?.nin || '_________________';
      const clientPhone = showNewClientForm ? formData.phone : clients.find(c => c.id == formData.client_id)?.phone || '_________________';
      const address = showNewClientForm ? formData.address : clients.find(c => c.id == formData.client_id)?.address || '_________________';

      const agreementContent = `
        <html>
        <head>
          <title>Loan Agreement - Devs Apps</title>
          <style>
            body { font-family: 'Times New Roman', serif; padding: 40px; max-width: 800px; margin: 0 auto; line-height: 1.6; }
            h1 { text-align: center; text-decoration: underline; margin-bottom: 20px; }
            h2 { font-size: 16px; margin-top: 20px; text-decoration: underline; }
            p { margin-bottom: 15px; }
            .header { text-align: center; margin-bottom: 30px; }
            .section { margin-bottom: 20px; }
            .details-table { width: 100%; border-collapse: collapse; margin-bottom: 20px; }
            .details-table td { padding: 8px; border: 1px solid #ccc; }
            .details-table td:first-child { font-weight: bold; width: 40%; background: #f9f9f9; }
            .signatures { margin-top: 50px; display: flex; justify-content: space-between; }
            .sig-block { width: 45%; border-top: 1px solid #000; padding-top: 10px; text-align: center; }
            .footer { margin-top: 50px; font-size: 10px; text-align: center; border-top: 1px solid #eee; padding-top: 10px; }
          </style>
        </head>
        <body>
          <div class="header">
            <h1>LOAN AGREEMENT</h1>
            <p><strong>Devs Apps Financial Services</strong></p>
          </div>

          <p>This Loan Agreement is made on <strong>${new Date().toLocaleDateString()}</strong> between:</p>

          <div class="section">
            <p><strong>LENDER:</strong> Devs Apps Financial Services</p>
            <p><strong>BORROWER:</strong> ${clientName} (NIN: ${clientNIN})</p>
            <p><strong>ADDRESS:</strong> ${address}</p>
            <p><strong>PHONE:</strong> ${clientPhone}</p>
          </div>

          <div class="section">
            <h2>LOAN DETAILS</h2>
            <table class="details-table">
              <tr><td>Principal Amount</td><td>UGX ${formatMoney(principal)}</td></tr>
              <tr><td>Interest Rate</td><td>${interestRate}%</td></tr>
              <tr><td>Interest Amount</td><td>UGX ${formatMoney(interestAmount)}</td></tr>
              <tr><td>Total Repayment Amount</td><td>UGX ${formatMoney(totalAmount)}</td></tr>
              <tr><td>Loan Duration</td><td>${durationWeeks} Weeks</td></tr>
              <tr><td>Due Date</td><td>${dueDateStr}</td></tr>
            </table>
          </div>

          <div class="section">
            <h2>TERMS AND CONDITIONS</h2>
            <ol>
              <li>The Borrower agrees to repay the Principal Amount plus Interest by the Due Date specified above.</li>
              <li>In case of default, Devs Apps reserves the right to take legal action or seize provided collateral.</li>
              <li>Late payments may attract an additional penalty fee.</li>
              <li>All payments shall be made directly to Devs Apps authorized agents.</li>
            </ol>
          </div>

          <div class="signatures">
            <div class="sig-block">
              <p>Borrower's Signature</p>
            </div>
            <div class="sig-block">
              <p>Lender's Representative</p>
            </div>
          </div>

          <div class="footer">
            <p>Devs Apps Financial Services • Kampala, Uganda • Generated on ${new Date().toLocaleString()}</p>
          </div>
          
          <script>window.print();</script>
        </body>
        </html>
      `;

      const win = window.open('', '_blank');
      win.document.write(agreementContent);
      win.document.close();
    };

    const handleSubmitLoan = async () => {
      if (showNewClientForm) {
        if (!formData.name || !formData.phone) {
          toast.error('Client name and phone are required');
          return;
        }
      } else if (!formData.client_id) {
        toast.error('Please select a client');
        return;
      }

      if (principal <= 0) {
        toast.error('Please enter a valid principal amount');
        return;
      }

      setSubmitting(true);
      try {
        let clientId = formData.client_id;

        // Create client first if new
        if (showNewClientForm) {
          const clientRes = await financeAPI.createClient({
            name: formData.name,
            phone: formData.phone,
            nin: formData.nin,
            address: formData.address
          });
          clientId = clientRes.data.id;
        }

        // Create loan
        const loanRes = await financeAPI.createLoan({
          client_id: parseInt(clientId),
          principal: principal,
          interest_rate: interestRate,
          duration_weeks: durationWeeks
        });

        if (selectedFiles && selectedFiles.length > 0) {
          const uploadData = new FormData();
          Array.from(selectedFiles).forEach(file => {
            uploadData.append('files', file);
          });
          await financeAPI.uploadLoanDocuments(loanRes.data.id, uploadData);
        }

        toast.success('Loan issued successfully!');
        setActiveNav('activeloans');
      } catch (err) {
        toast.error(err.response?.data?.error || 'Failed to issue loan');
      } finally {
        setSubmitting(false);
      }
    };

    return (
      <div className="max-w-xl mx-auto">
        <div className="bg-slate-800 border border-slate-700 rounded-2xl w-full shadow-2xl overflow-hidden">
          <div className="flex justify-between items-center p-5 border-b border-slate-700 sticky top-0 bg-slate-800 z-10">
            <h3 className="text-lg font-semibold text-white">Issue New Loan</h3>
          </div>

          <div className="p-5 space-y-4">
            <div>
              <h4 className="text-sm font-medium text-slate-300 mb-3">CLIENT INFORMATION</h4>
              <div className="grid grid-cols-2 gap-4">
                <div className="col-span-2">
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Select / New Client *</label>
                  <select
                    value={showNewClientForm ? 'new' : formData.client_id}
                    onChange={handleClientChange}
                    className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white mb-2"
                  >
                    <option value="">-- Select Existing Client --</option>
                    {clients.map(c => (
                      <option key={c.id} value={c.id}>{c.name} - {c.phone}</option>
                    ))}
                    <option value="new">+ Create New Client</option>
                  </select>
                </div>

                {showNewClientForm && (
                  <>
                    <div className="col-span-2">
                      <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Full Name *</label>
                      <input
                        type="text"
                        value={formData.name}
                        onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                        placeholder="Enter client name"
                        className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">NIN</label>
                      <input
                        type="text"
                        value={formData.nin}
                        onChange={(e) => setFormData({ ...formData, nin: e.target.value })}
                        placeholder="CM1234567890"
                        className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                      />
                    </div>
                    <div>
                      <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Phone *</label>
                      <input
                        type="text"
                        value={formData.phone}
                        onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                        placeholder="0700 000 000"
                        className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                      />
                    </div>
                    <div className="col-span-2">
                      <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Address</label>
                      <input
                        type="text"
                        value={formData.address}
                        onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                        placeholder="Enter address"
                        className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                      />
                    </div>
                  </>
                )}
              </div>
            </div>

            <div className="border-t border-slate-700 pt-4">
              <h4 className="text-sm font-medium text-slate-300 mb-3">LOAN DETAILS</h4>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Principal Amount (UGX) *</label>
                  <input
                    type="number"
                    value={formData.principal}
                    onChange={(e) => setFormData({ ...formData, principal: e.target.value })}
                    placeholder="500000"
                    className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Interest Rate (%) *</label>
                  <input
                    type="number"
                    value={formData.interest_rate}
                    onChange={(e) => setFormData({ ...formData, interest_rate: e.target.value })}
                    className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Interest Amount</label>
                  <div className="px-4 py-2.5 bg-slate-900/50 border border-slate-700 rounded-lg text-slate-400">
                    {formatMoney(interestAmount)} (auto)
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Total Repayment</label>
                  <div className="px-4 py-2.5 bg-slate-900/50 border border-slate-700 rounded-lg text-white font-mono">
                    {formatMoney(totalAmount)}
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Duration (weeks) *</label>
                  <input
                    type="number"
                    value={formData.duration_weeks}
                    onChange={(e) => setFormData({ ...formData, duration_weeks: e.target.value })}
                    className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Due Date</label>
                  <div className="px-4 py-2.5 bg-slate-900/50 border border-slate-700 rounded-lg text-slate-400">
                    {dueDateStr} (auto)
                  </div>
                </div>
              </div>
            </div>

            <div className="border-t border-slate-700 pt-4">
              <h4 className="text-sm font-medium text-slate-300 mb-3">SECURITY DOCUMENTS</h4>
              <div
                className={`border-2 border-dashed ${selectedFiles ? 'border-teal-500 bg-teal-500/10' : 'border-slate-600'} rounded-lg p-4 text-center group cursor-pointer hover:border-teal-500/50 hover:bg-slate-700/30 transition-all`}
                onClick={() => fileInputRef.current.click()}
              >
                <div className="text-3xl mb-2">📎</div>
                <p className="text-slate-400 text-sm mb-2 group-hover:text-teal-400">
                  {selectedFiles ? `${selectedFiles.length} file(s) selected` : 'Upload ID/Collateral Photo'}
                </p>
                <button className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm transition-colors">
                  {selectedFiles ? 'Change Files' : 'Choose Files'}
                </button>
                <input
                  type="file"
                  multiple
                  ref={fileInputRef}
                  onChange={handleFileChange}
                  className="hidden"
                  accept="image/*,application/pdf"
                />
              </div>
            </div>
          </div>

          <div className="p-5 border-t border-slate-700 flex gap-3 justify-between sticky bottom-0 bg-slate-800">
            <button
              onClick={handlePrintAgreement}
              className="px-4 py-2.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm flex items-center gap-2"
            >
              <span>🖨️</span> Print Loan Agreement
            </button>
            <div className="flex gap-3">
              <button
                onClick={() => setActiveNav('dashboard')}
                className="px-5 py-2.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmitLoan}
                disabled={submitting}
                className="px-5 py-2.5 bg-teal-500 hover:bg-teal-600 text-slate-900 rounded-lg font-semibold disabled:opacity-50"
              >
                {submitting ? 'Issuing...' : 'Issue Loan'}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  };

  // Finance Employee Pages - New Group Loan (Create Group Loan)
  const NewGroupLoanPage = () => {
    const [submitting, setSubmitting] = useState(false);
    const [groupForm, setGroupForm] = useState({
      group_name: '',
      member_count: '',
      total_amount: '',
      amount_per_period: '',
      total_periods: '4'
    });
    const toast = useToastStore();

    const handleSubmitGroupLoan = async () => {
      if (!groupForm.group_name) {
        toast.error('Please enter the group name');
        return;
      }
      if (!groupForm.member_count || parseInt(groupForm.member_count) <= 0) {
        toast.error('Please enter the number of members');
        return;
      }
      if (!groupForm.total_amount || parseFloat(groupForm.total_amount) <= 0) {
        toast.error('Please enter the total amount');
        return;
      }
      if (!groupForm.amount_per_period || parseFloat(groupForm.amount_per_period) <= 0) {
        toast.error('Please enter the amount per period');
        return;
      }

      setSubmitting(true);
      try {
        await financeAPI.createGroupLoan({
          group_name: groupForm.group_name,
          member_count: parseInt(groupForm.member_count),
          total_amount: parseFloat(groupForm.total_amount),
          amount_per_period: parseFloat(groupForm.amount_per_period),
          total_periods: parseInt(groupForm.total_periods)
        });
        toast.success('Group loan created successfully!');
        setActiveNav('activeloans');
      } catch (err) {
        toast.error(err.response?.data?.error || 'Failed to create group loan');
      } finally {
        setSubmitting(false);
      }
    };

    return (
      <div className="max-w-xl mx-auto">
        <div className="bg-slate-800 border border-slate-700 rounded-2xl w-full shadow-2xl overflow-hidden">
          <div className="flex justify-between items-center p-5 border-b border-slate-700 sticky top-0 bg-slate-800 z-10">
            <h3 className="text-lg font-semibold text-white">Issue New Group Loan</h3>
          </div>

          <div className="p-5 space-y-4">
            <div>
              <h4 className="text-sm font-medium text-slate-300 mb-3">GROUP INFORMATION</h4>
              <div className="space-y-4">
                {/* Group Name */}
                <div>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Group Name *</label>
                  <input
                    type="text"
                    value={groupForm.group_name}
                    onChange={(e) => setGroupForm({ ...groupForm, group_name: e.target.value })}
                    placeholder="e.g., Kyebando Women's Group"
                    className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                  />
                </div>

                {/* Member Count */}
                <div>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Number of Members *</label>
                  <input
                    type="number"
                    value={groupForm.member_count}
                    onChange={(e) => setGroupForm({ ...groupForm, member_count: e.target.value })}
                    placeholder="Enter member count"
                    className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                  />
                </div>
              </div>
            </div>

            <div className="border-t border-slate-700 pt-4">
              <h4 className="text-sm font-medium text-slate-300 mb-3">LOAN DETAILS</h4>
              <div className="grid grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Total Amount (UGX) *</label>
                  <input
                    type="number"
                    value={groupForm.total_amount}
                    onChange={(e) => setGroupForm({ ...groupForm, total_amount: e.target.value })}
                    placeholder="Total loan amount"
                    className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Amount Per Period (UGX) *</label>
                  <input
                    type="number"
                    value={groupForm.amount_per_period}
                    onChange={(e) => setGroupForm({ ...groupForm, amount_per_period: e.target.value })}
                    placeholder="Weekly/Monthly payment"
                    className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Total Periods *</label>
                  <select
                    value={groupForm.total_periods}
                    onChange={(e) => setGroupForm({ ...groupForm, total_periods: e.target.value })}
                    className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                  >
                    <option value="4">4 Periods</option>
                    <option value="8">8 Periods</option>
                    <option value="12">12 Periods</option>
                    <option value="16">16 Periods</option>
                    <option value="24">24 Periods</option>
                  </select>
                </div>
              </div>

              {/* Summary */}
              {parseFloat(groupForm.total_amount) > 0 && (
                <div className="bg-slate-900 border border-slate-700 rounded-lg p-4 space-y-2 mt-4">
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">Total Amount:</span>
                    <span className="text-teal-400 font-mono">{formatMoney(parseFloat(groupForm.total_amount) || 0)}</span>
                  </div>
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">Per Period Payment:</span>
                    <span className="text-amber-400 font-mono">{formatMoney(parseFloat(groupForm.amount_per_period) || 0)}</span>
                  </div>
                </div>
              )}
            </div>

            <div className="border-t border-slate-700 pt-4">
              <h4 className="text-sm font-medium text-slate-300 mb-3">SECURITY DOCUMENTS</h4>
              <div className="border-2 border-dashed border-slate-600 rounded-lg p-4 text-center group cursor-pointer hover:border-teal-500/50 hover:bg-slate-700/30 transition-all">
                <div className="text-3xl mb-2">📎</div>
                <p className="text-slate-400 text-sm mb-2 group-hover:text-teal-400">Upload Agreement/Collateral Photo</p>
                <button className="px-4 py-2 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm transition-colors">Choose Files</button>
              </div>
            </div>
          </div>

          <div className="p-5 border-t border-slate-700 flex gap-3 justify-between sticky bottom-0 bg-slate-800">
            <button className="px-4 py-2.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg text-sm flex items-center gap-2">
              <span>🖨️</span> Print Group Agreement
            </button>
            <div className="flex gap-3">
              <button
                onClick={() => setActiveNav('dashboard')}
                className="px-5 py-2.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium"
              >
                Cancel
              </button>
              <button
                onClick={handleSubmitGroupLoan}
                disabled={submitting || !groupForm.group_name || !groupForm.total_amount}
                className="px-5 py-2.5 bg-teal-500 hover:bg-teal-600 text-slate-900 rounded-lg font-semibold disabled:opacity-50"
              >
                {submitting ? 'Creating...' : 'Issue Group Loan'}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  };

  // Finance Employee Pages - Record Payment
  const RecordPaymentPage = () => {
    const [loanType, setLoanType] = useState('individual'); // individual, group
    const [loans, setLoans] = useState([]);
    const [groupLoans, setGroupLoans] = useState([]);
    const [selectedLoanId, setSelectedLoanId] = useState('');
    const [amount, setAmount] = useState('');
    const [paymentDate, setPaymentDate] = useState('today');
    const [loading, setLoading] = useState(true);
    const [submitting, setSubmitting] = useState(false);
    const toast = useToastStore();

    useEffect(() => {
      loadData();
    }, []);

    const loadData = async () => {
      setLoading(true);
      try {
        const [loansRes, groupsRes] = await Promise.all([
          financeAPI.getLoans(),
          financeAPI.getGroupLoans()
        ]);
        setLoans(loansRes.data || []);
        setGroupLoans(groupsRes.data || []);
      } catch (err) {
        console.error(err);
        toast.error('Failed to load loans');
      } finally {
        setLoading(false);
      }
    };

    const selectedLoan = loanType === 'individual'
      ? loans.find(l => l.id === parseInt(selectedLoanId))
      : groupLoans.find(l => l.id === parseInt(selectedLoanId));

    const balanceAfter = selectedLoan ? selectedLoan.balance - (parseFloat(amount) || 0) : 0;

    const handleSubmit = async () => {
      if (!selectedLoanId || !amount) {
        toast.error('Please select a loan and enter amount');
        return;
      }

      setSubmitting(true);
      try {
        if (loanType === 'individual') {
          await financeAPI.recordLoanPayment(selectedLoanId, {
            amount: parseFloat(amount),
            payment_date: paymentDate
          });
        } else {
          await financeAPI.recordGroupPayment(selectedLoanId, {
            amount: parseFloat(amount),
            payment_date: paymentDate
          });
        }
        toast.success('Payment recorded successfully');
        loadData();
        setAmount('');
        setSelectedLoanId('');
        // Optional: Stay on page to record more or navigate away? 
        // User might have multiple payments to record, so staying is better.
      } catch (err) {
        toast.error(err.response?.data?.error || 'Failed to record payment');
      } finally {
        setSubmitting(false);
      }
    };

    return (
      <div className="max-w-lg">
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-6">
          <h3 className="font-semibold text-white mb-6">Record Loan Payment</h3>

          <div className="space-y-4">
            {/* Loan Type Toggle */}
            <div>
              <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Loan Type</label>
              <div className="flex bg-slate-900 rounded-lg p-1">
                <button
                  onClick={() => { setLoanType('individual'); setSelectedLoanId(''); }}
                  className={`flex-1 py-2 text-sm font-medium rounded-md transition-all ${loanType === 'individual' ? 'bg-teal-500 text-slate-900 shadow' : 'text-slate-400 hover:text-white'}`}
                >
                  Individual Loan
                </button>
                <button
                  onClick={() => { setLoanType('group'); setSelectedLoanId(''); }}
                  className={`flex-1 py-2 text-sm font-medium rounded-md transition-all ${loanType === 'group' ? 'bg-teal-500 text-slate-900 shadow' : 'text-slate-400 hover:text-white'}`}
                >
                  Group Loan
                </button>
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Select {loanType === 'individual' ? 'Client' : 'Group'}</label>
              <select
                value={selectedLoanId}
                onChange={(e) => setSelectedLoanId(e.target.value)}
                className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                disabled={loading}
              >
                <option value="">-- Select {loanType === 'individual' ? 'client' : 'group'} --</option>
                {loading ? (
                  <option disabled>Loading...</option>
                ) : loanType === 'individual' ? (
                  loans.filter(l => l.status !== 'paid').map(loan => (
                    <option key={loan.id} value={loan.id}>
                      {loan.client?.name || 'Unknown'} - {formatMoney(loan.balance)} due
                    </option>
                  ))
                ) : (
                  groupLoans.filter(l => l.status !== 'paid').map(loan => (
                    <option key={loan.id} value={loan.id}>
                      {loan.group_name} - {formatMoney(loan.balance)} due
                    </option>
                  ))
                )}
              </select>
            </div>

            {selectedLoan && (
              <div className="bg-slate-900 rounded-lg p-3 border border-slate-700 space-y-2">
                <div className="flex justify-between text-sm">
                  <span className="text-slate-400">Total Outstanding:</span>
                  <span className="text-amber-400 font-mono font-semibold">{formatMoney(selectedLoan.balance)}</span>
                </div>
                {loanType === 'group' && (
                  <div className="flex justify-between text-sm">
                    <span className="text-slate-400">Target Per Period:</span>
                    <span className="text-white font-mono">{formatMoney(selectedLoan.amount_per_period)}</span>
                  </div>
                )}
              </div>
            )}

            <div>
              <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Payment Date</label>
              <select
                value={paymentDate}
                onChange={(e) => setPaymentDate(e.target.value)}
                className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
              >
                <option value="today">Today - {new Date().toLocaleDateString()}</option>
                <option value="yesterday">Yesterday - {new Date(Date.now() - 86400000).toLocaleDateString()}</option>
              </select>
            </div>

            <div>
              <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Payment Amount (UGX)</label>
              <input
                type="number"
                value={amount}
                onChange={(e) => setAmount(e.target.value)}
                placeholder="Enter amount"
                className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white font-mono"
              />
            </div>

            {amount && selectedLoan && (
              <div className="bg-slate-900 rounded-lg p-3 border border-slate-700">
                <p className="text-slate-400 text-sm flex justify-between">
                  <span>Balance After Payment:</span>
                  <span className={`font-mono font-bold ${balanceAfter <= 0 ? 'text-green-500' : 'text-white'}`}>
                    {formatMoney(balanceAfter)}
                  </span>
                </p>
                {balanceAfter <= 0 && (
                  <p className="text-green-400 text-xs mt-1 text-center">🎉 Loan will be fully paid!</p>
                )}
              </div>
            )}

            <div className="flex gap-3 pt-4">
              <button onClick={() => setActiveNav('dashboard')} className="px-5 py-2.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium">Cancel</button>
              <button
                onClick={handleSubmit}
                disabled={submitting || !selectedLoanId || !amount}
                className="flex-1 px-5 py-2.5 bg-teal-500 hover:bg-teal-600 text-slate-900 rounded-lg font-semibold disabled:opacity-50 disabled:cursor-not-allowed"
              >
                {submitting ? 'Recording...' : 'Record Payment'}
              </button>
            </div>
          </div>
        </div>
      </div>
    );
  };

  // Finance Employee Pages - My Payments
  const MyPaymentsPage = () => {
    const todayPayments = [
      { client: 'John Mukasa', amount: 50000, balanceAfter: 400000 },
      { client: 'Kyebando Women', amount: 275000, balanceAfter: 2200000 },
    ];

    const yesterdayPayments = [
      { client: 'Peter Okello', amount: 100000, balanceAfter: 920000 },
    ];

    return (
      <div className="space-y-6">
        <div className="flex justify-between items-center">
          <h3 className="text-lg font-semibold text-white">MY PAYMENTS - Today + Yesterday</h3>
        </div>

        {/* Today */}
        <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
          <div className="px-5 py-3 border-b border-slate-700 bg-slate-900/50">
            <h4 className="font-medium text-white">Today - {new Date().toLocaleDateString()}</h4>
          </div>
          <table className="w-full">
            <thead>
              <tr className="bg-slate-900/30">
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Client</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Amount</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Balance After</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700">
              {todayPayments.map((payment, i) => (
                <tr key={i} className="hover:bg-slate-700/30">
                  <td className="px-4 py-3 text-white">{payment.client}</td>
                  <td className="px-4 py-3 text-green-400 font-mono font-semibold">{formatMoney(payment.amount)}</td>
                  <td className="px-4 py-3 text-white font-mono">{formatMoney(payment.balanceAfter)}</td>
                  <td className="px-4 py-3">
                    <button className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white">✏️</button>
                    <button className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white">🖨️</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {/* Yesterday */}
        <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
          <div className="px-5 py-3 border-b border-slate-700 bg-slate-900/50">
            <h4 className="font-medium text-white">Yesterday - {new Date(Date.now() - 86400000).toLocaleDateString()}</h4>
          </div>
          <table className="w-full">
            <thead>
              <tr className="bg-slate-900/30">
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Client</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Amount</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Balance After</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700">
              {yesterdayPayments.map((payment, i) => (
                <tr key={i} className="hover:bg-slate-700/30">
                  <td className="px-4 py-3 text-white">{payment.client}</td>
                  <td className="px-4 py-3 text-green-400 font-mono font-semibold">{formatMoney(payment.amount)}</td>
                  <td className="px-4 py-3 text-white font-mono">{formatMoney(payment.balanceAfter)}</td>
                  <td className="px-4 py-3">
                    <button className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white">✏️</button>
                    <button className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white">🖨️</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <p className="text-center text-slate-500 text-sm">Older payments are not visible to employees</p>
      </div>
    );
  };

  // Main App Layout
  const MainLayout = ({ children, title, subtitle, isManager }) => (
    <div className="min-h-screen bg-slate-900 flex">
      <ToastContainer />
      <Sidebar isManager={isManager} />
      <main className="flex-1 p-6 overflow-auto">
        <div className="flex justify-between items-start mb-6">
          <div>
            <h1 className="text-2xl font-bold text-white">{title}</h1>
            {subtitle && <p className="text-slate-400 mt-1">{subtitle}</p>}
          </div>
          <div className="text-right">
            <p className="text-sm text-slate-400">Today</p>
            <p className="text-white font-medium">{new Date().toLocaleDateString('en-US', { month: 'long', day: 'numeric', year: 'numeric' })}</p>
          </div>
        </div>
        {error && (
          <div className="mb-4 p-3 bg-red-500/10 border border-red-500/50 rounded-lg text-red-400 text-sm flex justify-between items-center">
            {error}
            <button onClick={() => setError('')} className="text-red-400 hover:text-red-300">✕</button>
          </div>
        )}
        {children}
      </main>
    </div>
  );

  // Render based on current view
  if (currentView === 'login') {
    return (
      <>
        <ToastContainer />
        <LoginPage />
      </>
    );
  }

  if (currentView === 'manager') {
    const getContent = () => {
      switch (activeNav) {
        case 'dashboard': return <ManagerDashboard />;
        case 'boutique': return <BusinessPage type="boutique" />;
        case 'hardware': return <BusinessPage type="hardware" />;
        case 'finances': return <FinancePage />;
        case 'employees': return <EmployeesPage />;
        case 'reports': return <ReportsPage />;
        case 'audit': return <AuditTrailPage />;
        case 'settings': return <SettingsPage />;
        default: return <ManagerDashboard />;
      }
    };

    const getTitle = () => {
      switch (activeNav) {
        case 'dashboard': return 'Dashboard';
        case 'boutique': return 'Boutique';
        case 'hardware': return 'Hardware';
        case 'finances': return 'Finances';
        case 'reports': return 'Reports';
        case 'audit': return 'Audit Trail';
        case 'employees': return 'Employee Management';
        case 'settings': return 'Settings';
        default: return 'Dashboard';
      }
    };

    return (
      <MainLayout title={getTitle()} subtitle={`Welcome back, ${user?.name || 'Manager'}`} isManager={true}>
        {getContent()}
      </MainLayout>
    );
  }

  if (currentView === 'employee') {
    const isFinance = user?.assigned_business === 'finances';
    const businessName = user?.assigned_business?.charAt(0).toUpperCase() + user?.assigned_business?.slice(1);

    const getEmployeeContent = () => {
      switch (activeNav) {
        case 'dashboard': return <EmployeeDashboard />;
        case 'newsale': return <NewSalePage />;
        case 'mysales': return <MySalesPage />;
        case 'credits': return <EmployeeCreditsPage />;
        case 'stock': return <EmployeeStockPage />;
        case 'activeloans': return <ActiveLoansPage />;
        case 'newloan': return <NewLoanPage />;
        case 'newgrouploan': return <NewGroupLoanPage />;
        case 'recordpayment': return <RecordPaymentPage />;
        case 'mypayments': return <MyPaymentsPage />;
        default: return <EmployeeDashboard />;
      }
    };

    const getEmployeeTitle = () => {
      switch (activeNav) {
        case 'dashboard': return 'My Dashboard';
        case 'newsale': return 'New Sale';
        case 'mysales': return 'My Sales';
        case 'credits': return 'Credits';
        case 'stock': return 'Stock';
        case 'activeloans': return 'Active Loans';
        case 'newloan': return 'New Loan';
        case 'newgrouploan': return 'New Group Loan';
        case 'recordpayment': return 'Record Payment';
        case 'mypayments': return 'My Payments';
        default: return 'My Dashboard';
      }
    };

    return (
      <MainLayout title={getEmployeeTitle()} subtitle={businessName} isManager={false}>
        {getEmployeeContent()}
      </MainLayout>
    );
  }

  return null;
};

export default App;
