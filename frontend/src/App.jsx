import React, { useState, useEffect } from 'react';
import { BarChart, Bar, LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer } from 'recharts';
import api, { authAPI, boutiqueAPI, hardwareAPI, employeesAPI, customersAPI, dashboardAPI } from './services/api';

const App = () => {
  const [currentView, setCurrentView] = useState('login');
  const [user, setUser] = useState(null);
  const [activeNav, setActiveNav] = useState('dashboard');
  const [showModal, setShowModal] = useState(null);
  const [activeTab, setActiveTab] = useState('inventory');
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
    if (token && savedUser) {
      setUser(JSON.parse(savedUser));
      setCurrentView(JSON.parse(savedUser).role === 'manager' ? 'manager' : 'employee');
    }
  }, []);

  // Sample chart data
  const revenueData = [
    { day: 'Mon', boutique: 450000, hardware: 680000, finance: 150000 },
    { day: 'Tue', boutique: 520000, hardware: 720000, finance: 200000 },
    { day: 'Wed', boutique: 480000, hardware: 650000, finance: 180000 },
    { day: 'Thu', boutique: 590000, hardware: 800000, finance: 220000 },
    { day: 'Fri', boutique: 620000, hardware: 750000, finance: 190000 },
    { day: 'Sat', boutique: 700000, hardware: 900000, finance: 250000 },
    { day: 'Sun', boutique: 380000, hardware: 450000, finance: 100000 },
  ];

  const pieData = [
    { name: 'Boutique', value: 3740000, color: '#14b8a6' },
    { name: 'Hardware', value: 4950000, color: '#3b82f6' },
    { name: 'Finance', value: 1290000, color: '#f59e0b' },
  ];

  const formatMoney = (amount) => {
    if (!amount) return 'UGX 0';
    return 'UGX ' + Number(amount).toLocaleString();
  };

  // API Functions
  const handleLogin = async () => {
    setLoading(true);
    setError('');
    
    // For development: Allow any login
    // Manager login: if username is "manager" or contains "manager"
    // Employee login: requires business unit selection
    
    const isManager = loginForm.username.toLowerCase().includes('manager') || loginForm.username.toLowerCase() === 'admin';
    
    if (!loginForm.username || !loginForm.password) {
      setError('Please enter username and password');
      setLoading(false);
      return;
    }
    
    if (!isManager && !loginForm.assigned_business) {
      setError('Employees must select a business unit');
      setLoading(false);
      return;
    }
    
    // Try to login with backend first
    try {
      const response = await authAPI.login(loginForm);
      const { access_token, user } = response.data;
      localStorage.setItem('token', access_token);
      localStorage.setItem('user', JSON.stringify(user));
      setUser(user);
      setCurrentView(user.role === 'manager' ? 'manager' : 'employee');
      setActiveNav('dashboard');
    } catch (err) {
      // If backend login fails, use demo mode
      console.log('Backend login failed, using demo mode');
      const demoUser = {
        id: Date.now(),
        username: loginForm.username,
        name: isManager ? 'Manager' : loginForm.username,
        role: isManager ? 'manager' : 'employee',
        assigned_business: isManager ? 'all' : loginForm.assigned_business,
        is_active: true,
        can_edit: true,
        can_delete: isManager,
        can_backdate: isManager,
        can_clear_credits: true,
      };
      localStorage.setItem('user', JSON.stringify(demoUser));
      localStorage.setItem('token', 'demo-token-' + Date.now());
      setUser(demoUser);
      setCurrentView(isManager ? 'manager' : 'employee');
      setActiveNav('dashboard');
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
      const [stockRes, catRes, salesRes, creditsRes] = await Promise.all([
        boutiqueAPI.getStock(),
        boutiqueAPI.getCategories(),
        boutiqueAPI.getSales({ limit: 50 }),
        boutiqueAPI.getCredits()
      ]);
      setBoutiqueStock(stockRes.data.stock || []);
      setBoutiqueCategories(catRes.data.categories || []);
      setBoutiqueSales(salesRes.data.sales || []);
      setBoutiqueCredits(creditsRes.data.credits || []);
    } catch (err) {
      console.error('Error loading boutique data:', err);
    }
  };

  const loadHardwareData = async () => {
    try {
      const [stockRes, catRes, salesRes, creditsRes] = await Promise.all([
        hardwareAPI.getStock(),
        hardwareAPI.getCategories(),
        hardwareAPI.getSales({ limit: 50 }),
        hardwareAPI.getCredits()
      ]);
      setHardwareStock(stockRes.data.stock || []);
      setHardwareCategories(catRes.data.categories || []);
      setHardwareSales(salesRes.data.sales || []);
      setHardwareCredits(creditsRes.data.credits || []);
    } catch (err) {
      console.error('Error loading hardware data:', err);
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
    if (currentView !== 'login') {
      if (activeNav === 'boutique') loadBoutiqueData();
      if (activeNav === 'hardware') loadHardwareData();
      if (activeNav === 'employees') loadEmployees();
      if (activeNav === 'dashboard') {
        loadBoutiqueData();
        loadHardwareData();
      }
    }
  }, [activeNav, currentView]);

  // Render login page
  if (currentView === 'login') {
    return (
      <div className="min-h-screen bg-gradient-to-br from-slate-900 via-slate-800 to-slate-900 flex items-center justify-center p-4">
        <div className="absolute top-0 right-0 w-96 h-96 bg-teal-500/10 rounded-full blur-3xl"></div>
        <div className="absolute bottom-0 left-0 w-72 h-72 bg-teal-500/5 rounded-full blur-3xl"></div>
        
        <div className="bg-slate-800 border border-slate-700 rounded-2xl p-8 w-full max-w-md relative z-10 shadow-2xl">
          <div className="text-center mb-8">
            <div className="flex justify-center mb-4">
              <div className="flex items-center gap-2 scale-125">
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
            <p className="text-slate-400 text-sm">Business Management System</p>
          </div>

          {error && (
            <div className="mb-4 p-3 bg-red-500/10 border border-red-500/50 rounded-lg text-red-400 text-sm">
              {error}
            </div>
          )}
          
          <div className="space-y-5">
            <div>
              <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Username</label>
              <input 
                type="text" 
                placeholder="Enter your username"
                value={loginForm.username}
                onChange={(e) => setLoginForm({...loginForm, username: e.target.value})}
                onKeyPress={(e) => e.key === 'Enter' && handleLogin()}
                className="w-full px-4 py-3 bg-slate-900 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-teal-500 focus:ring-1 focus:ring-teal-500/50"
              />
            </div>
            
            <div>
              <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Password</label>
              <input 
                type="password" 
                placeholder="Enter your password"
                value={loginForm.password}
                onChange={(e) => setLoginForm({...loginForm, password: e.target.value})}
                onKeyPress={(e) => e.key === 'Enter' && handleLogin()}
                className="w-full px-4 py-3 bg-slate-900 border border-slate-700 rounded-lg text-white placeholder-slate-500 focus:outline-none focus:border-teal-500"
              />
            </div>
            
            <div>
              <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">
                Business Unit {loginForm.username.toLowerCase().includes('manager') || loginForm.username.toLowerCase() === 'admin' ? '(not required for managers)' : '(required for employees)'}
              </label>
              <select 
                value={loginForm.assigned_business}
                onChange={(e) => setLoginForm({...loginForm, assigned_business: e.target.value})}
                disabled={loginForm.username.toLowerCase().includes('manager') || loginForm.username.toLowerCase() === 'admin'}
                className={`w-full px-4 py-3 bg-slate-900 border border-slate-700 rounded-lg text-white focus:outline-none focus:border-teal-500 ${
                  loginForm.username.toLowerCase().includes('manager') || loginForm.username.toLowerCase() === 'admin' ? 'opacity-50 cursor-not-allowed' : ''
                }`}
              >
                <option value="">-- Select Business --</option>
                <option value="boutique">👗 Boutique</option>
                <option value="hardware">🔧 Hardware</option>
                <option value="finances">💰 Finances</option>
              </select>
              {loginForm.username && (
                <p className={`text-xs mt-2 ${loginForm.username.toLowerCase().includes('manager') || loginForm.username.toLowerCase() === 'admin' ? 'text-teal-400' : 'text-amber-400'}`}>
                  {loginForm.username.toLowerCase().includes('manager') || loginForm.username.toLowerCase() === 'admin' 
                    ? '✓ You will login as Manager with access to all businesses' 
                    : loginForm.assigned_business 
                      ? `✓ You will login as Employee in ${loginForm.assigned_business.charAt(0).toUpperCase() + loginForm.assigned_business.slice(1)}`
                      : '⚠ Please select which business you work in'
                  }
                </p>
              )}
            </div>
            
            <button 
              onClick={handleLogin}
              disabled={loading || !loginForm.username || !loginForm.password}
              className="w-full py-3.5 bg-teal-500 hover:bg-teal-600 text-slate-900 font-semibold rounded-lg transition-all hover:-translate-y-0.5 hover:shadow-lg hover:shadow-teal-500/25 disabled:opacity-50 disabled:cursor-not-allowed"
            >
              {loading ? 'Signing in...' : 'Sign In'}
            </button>
          </div>

          <div className="mt-8 pt-6 border-t border-slate-700">
            <p className="text-xs text-slate-500 text-center mb-3">Quick Login:</p>
            <div className="grid grid-cols-1 gap-2 text-xs">
              <button 
                onClick={() => {
                  setLoginForm({ username: 'manager', password: 'admin123', assigned_business: '' });
                }}
                className="p-3 bg-teal-500/10 hover:bg-teal-500/20 border border-teal-500/30 rounded-lg text-teal-400 hover:text-teal-300 transition-colors"
              >
                👔 Login as Manager (full access to all businesses)
              </button>
              <div className="grid grid-cols-3 gap-2 mt-2">
                <button 
                  onClick={() => setLoginForm({ username: 'sarah', password: 'pass123', assigned_business: 'boutique' })}
                  className="p-2 bg-slate-700/50 hover:bg-slate-700 rounded text-slate-400 hover:text-white transition-colors"
                >
                  👗 Boutique Staff
                </button>
                <button 
                  onClick={() => setLoginForm({ username: 'david', password: 'pass123', assigned_business: 'hardware' })}
                  className="p-2 bg-slate-700/50 hover:bg-slate-700 rounded text-slate-400 hover:text-white transition-colors"
                >
                  🔧 Hardware Staff
                </button>
                <button 
                  onClick={() => setLoginForm({ username: 'grace', password: 'pass123', assigned_business: 'finances' })}
                  className="p-2 bg-slate-700/50 hover:bg-slate-700 rounded text-slate-400 hover:text-white transition-colors"
                >
                  💰 Finance Staff
                </button>
              </div>
            </div>
            <p className="text-xs text-slate-600 text-center mt-3">
              For now, any username/password works. Manager will set up real credentials later.
            </p>
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
      className={`w-full flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors mb-1 ${
        active === id 
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
    const lowStockBoutique = boutiqueStock.filter(item => item.quantity <= item.low_stock_threshold).length;
    const lowStockHardware = hardwareStock.filter(item => item.quantity <= item.low_stock_threshold).length;
    const totalAlerts = lowStockBoutique + lowStockHardware + loans.filter(l => l.status === 'overdue').length;
    
    // Calculate totals
    const todayRevenue = boutiqueSales.filter(s => isToday(s.sale_date)).reduce((sum, s) => sum + (s.total_amount || 0), 0) +
                         hardwareSales.filter(s => isToday(s.sale_date)).reduce((sum, s) => sum + (s.total_amount || 0), 0);
    const outstandingCredits = boutiqueCredits.reduce((sum, c) => sum + (c.balance || 0), 0) +
                               hardwareCredits.reduce((sum, c) => sum + (c.balance || 0), 0);
    const outstandingLoans = loans.reduce((sum, l) => sum + (l.balance || 0), 0);
    const todayProfit = todayRevenue * 0.3; // Simplified profit calculation

    // Helper function
    function isToday(dateStr) {
      const today = new Date().toDateString();
      return new Date(dateStr).toDateString() === today;
    }

    return (
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
            <button className="text-amber-400 hover:text-amber-300 text-sm font-medium">View All →</button>
          </div>
        )}

        {/* Stats Cards Row - 4 boxes */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4 mb-6">
          <StatCard 
            title="Today's Revenue" 
            value={formatMoney(todayRevenue)} 
            change="↑ 12% from yesterday"
            changeType="up"
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
            value={formatMoney(outstandingLoans)} 
            change={`${loans.filter(l => l.status !== 'paid').length} active loans`}
            icon="🏦"
            iconBg="bg-blue-500/15"
          />
          <StatCard 
            title="Today's Profit" 
            value={formatMoney(todayProfit)} 
            change="↑ 8% from yesterday"
            changeType="up"
            icon="📈"
            iconBg="bg-teal-500/15"
          />
        </div>

        {/* Charts Row */}
        <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-6">
          <div className="lg:col-span-2 bg-slate-800 border border-slate-700 rounded-xl p-5">
            <h3 className="font-semibold text-white mb-4">Weekly Revenue Trend</h3>
            <ResponsiveContainer width="100%" height={250}>
              <LineChart data={revenueData}>
                <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
                <XAxis dataKey="day" stroke="#64748b" fontSize={12} />
                <YAxis stroke="#64748b" fontSize={12} tickFormatter={(v) => `${v/1000000}M`} />
                <Tooltip 
                  contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #334155', borderRadius: '8px' }}
                  formatter={(value) => formatMoney(value)}
                />
                <Line type="monotone" dataKey="boutique" stroke="#14b8a6" strokeWidth={2} dot={false} name="Boutique" />
                <Line type="monotone" dataKey="hardware" stroke="#3b82f6" strokeWidth={2} dot={false} name="Hardware" />
                <Line type="monotone" dataKey="finance" stroke="#f59e0b" strokeWidth={2} dot={false} name="Finance" />
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
                <Pie data={pieData} cx="50%" cy="50%" innerRadius={50} outerRadius={80} dataKey="value">
                  {pieData.map((entry, index) => (
                    <Cell key={index} fill={entry.color} />
                  ))}
                </Pie>
                <Tooltip formatter={(value) => formatMoney(value)} />
              </PieChart>
            </ResponsiveContainer>
            <div className="space-y-2 mt-2">
              {pieData.map((item, i) => (
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
              <span className="text-green-400 text-sm">↑ 15% vs yday</span>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-slate-400">Sales:</span><span className="text-white font-mono">{formatMoney(620000)}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Transactions:</span><span className="text-white">12</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Credits:</span><span className="text-amber-400 font-mono">{formatMoney(85000)}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Cleared:</span><span className="text-green-400 font-mono">{formatMoney(120000)}</span></div>
            </div>
          </div>
          
          <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 hover:border-blue-500/50 transition-colors">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <span className="text-xl">🔧</span>
                <h4 className="font-semibold text-white">HARDWARE</h4>
              </div>
              <span className="text-green-400 text-sm">↑ 8% vs yday</span>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-slate-400">Sales:</span><span className="text-white font-mono">{formatMoney(780000)}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Transactions:</span><span className="text-white">8</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Credits:</span><span className="text-amber-400 font-mono">{formatMoney(150000)}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Cleared:</span><span className="text-green-400 font-mono">{formatMoney(200000)}</span></div>
            </div>
          </div>
          
          <div className="bg-slate-800 border border-slate-700 rounded-xl p-5 hover:border-amber-500/50 transition-colors">
            <div className="flex items-center justify-between mb-4">
              <div className="flex items-center gap-2">
                <span className="text-xl">💰</span>
                <h4 className="font-semibold text-white">FINANCES</h4>
              </div>
              <span className="text-red-400 text-sm">↓ 5% vs yday</span>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between"><span className="text-slate-400">Received:</span><span className="text-white font-mono">{formatMoney(350000)}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">New Loans:</span><span className="text-white font-mono">{formatMoney(500000)}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Overdue:</span><span className="text-red-400 font-mono">{formatMoney(230000)}</span></div>
              <div className="flex justify-between"><span className="text-slate-400">Active:</span><span className="text-white">{loans.length || 12} loans</span></div>
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
    );
  };

  // Generic Business Page (Boutique/Hardware)
  const BusinessPage = ({ type }) => {
    const isBoutique = type === 'boutique';
    const stock = isBoutique ? boutiqueStock : hardwareStock;
    const categories = isBoutique ? boutiqueCategories : hardwareCategories;
    const sales = isBoutique ? boutiqueSales : hardwareSales;
    const credits = isBoutique ? boutiqueCredits : hardwareCredits;
    const clearedCredits = isBoutique ? boutiqueClearedCredits : hardwareClearedCredits;
    const stockAPI = isBoutique ? boutiqueAPI : hardwareAPI;

    const handleAddStock = async () => {
      try {
        await stockAPI.addStock(formData);
        setShowModal(null);
        setFormData({});
        isBoutique ? loadBoutiqueData() : loadHardwareData();
      } catch (err) {
        setError(err.response?.data?.error || 'Failed to add item');
      }
    };

    const handleEditStock = async () => {
      try {
        await stockAPI.updateStock(editingItem.id, formData);
        setShowModal(null);
        setFormData({});
        setEditingItem(null);
        isBoutique ? loadBoutiqueData() : loadHardwareData();
      } catch (err) {
        setError(err.response?.data?.error || 'Failed to update item');
      }
    };

    const handleDeleteStock = async (id) => {
      if (!window.confirm('Are you sure you want to delete this item?')) return;
      try {
        await stockAPI.deleteStock(id);
        isBoutique ? loadBoutiqueData() : loadHardwareData();
      } catch (err) {
        setError(err.response?.data?.error || 'Failed to delete item');
      }
    };

    const handleAddCategory = async () => {
      try {
        await stockAPI.createCategory({ name: formData.categoryName });
        setShowModal(null);
        setFormData({});
        isBoutique ? loadBoutiqueData() : loadHardwareData();
      } catch (err) {
        setError(err.response?.data?.error || 'Failed to add category');
      }
    };

    const openEditModal = (item) => {
      setEditingItem(item);
      setFormData({
        item_name: item.item_name,
        category_id: item.category_id,
        quantity: item.quantity,
        unit: item.unit,
        cost_price: item.cost_price,
        min_selling_price: item.min_selling_price,
        max_selling_price: item.max_selling_price,
        low_stock_threshold: item.low_stock_threshold,
      });
      setShowModal('editStock');
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
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                activeTab === tab.id ? 'bg-teal-500/15 text-teal-400' : 'text-slate-400 hover:text-white'
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
                onClick={() => { setShowModal('addStock'); setFormData({ unit: 'pieces', low_stock_threshold: 5 }); }}
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
                        {Math.round(item.min_selling_price/1000)}K - {Math.round(item.max_selling_price/1000)}K
                      </td>
                      <td className="px-4 py-3">
                        <button 
                          onClick={() => openEditModal(item)}
                          className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white"
                        >✏️</button>
                        <button 
                          onClick={() => handleDeleteStock(item.id)}
                          className="p-1.5 hover:bg-red-500/20 rounded text-slate-400 hover:text-red-400"
                        >🗑️</button>
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
                onClick={() => setShowModal('newSale')}
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
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Reference</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Customer</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Total</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Status</th>
                    <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Actions</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-700">
                  {sales.map((sale, i) => (
                    <tr key={i} className="hover:bg-slate-700/30">
                      <td className="px-4 py-3 text-slate-400">{new Date(sale.sale_date).toLocaleDateString()}</td>
                      <td className="px-4 py-3 text-white font-mono">{sale.reference_number}</td>
                      <td className="px-4 py-3 text-white">{sale.customer_name || 'Walk-in'}</td>
                      <td className="px-4 py-3 text-white font-mono">{formatMoney(sale.total_amount)}</td>
                      <td className="px-4 py-3">
                        <span className={`px-2 py-0.5 text-xs rounded-full ${
                          sale.payment_status === 'paid' ? 'bg-green-500/15 text-green-400' : 
                          sale.payment_status === 'partial' ? 'bg-amber-500/15 text-amber-400' : 
                          'bg-red-500/15 text-red-400'
                        }`}>
                          {sale.payment_status}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <button className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white">👁️</button>
                        <button className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white">🖨️</button>
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
                  onClick={() => { setShowModal('recordPayment'); setEditingItem(credit); setFormData({ amount: credit.balance }); }}
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
        {(showModal === 'addStock' || showModal === 'editStock') && (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-slate-800 border border-slate-700 rounded-2xl w-full max-w-lg shadow-2xl">
              <div className="flex justify-between items-center p-5 border-b border-slate-700">
                <h3 className="text-lg font-semibold text-white">{showModal === 'addStock' ? 'Add New Item' : 'Edit Item'}</h3>
                <button onClick={() => { setShowModal(null); setFormData({}); setEditingItem(null); }} className="w-8 h-8 bg-slate-700 hover:bg-slate-600 rounded-lg flex items-center justify-center text-slate-400 hover:text-white">✕</button>
              </div>
              <div className="p-5 space-y-4 max-h-96 overflow-y-auto">
                <div>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Item Name *</label>
                  <input 
                    type="text"
                    value={formData.item_name || ''}
                    onChange={(e) => setFormData({...formData, item_name: e.target.value})}
                    placeholder="e.g., Ladies Dress - Floral"
                    className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Category</label>
                  <select 
                    value={formData.category_id || ''}
                    onChange={(e) => setFormData({...formData, category_id: e.target.value})}
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
                      value={formData.quantity || ''}
                      onChange={(e) => setFormData({...formData, quantity: e.target.value})}
                      placeholder="0"
                      className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Unit</label>
                    <select 
                      value={formData.unit || 'pieces'}
                      onChange={(e) => setFormData({...formData, unit: e.target.value})}
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
                    value={formData.cost_price || ''}
                    onChange={(e) => setFormData({...formData, cost_price: e.target.value})}
                    placeholder="e.g., 45000"
                    className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                  />
                </div>
                <div className="grid grid-cols-2 gap-4">
                  <div>
                    <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Min Selling Price *</label>
                    <input 
                      type="number"
                      value={formData.min_selling_price || ''}
                      onChange={(e) => setFormData({...formData, min_selling_price: e.target.value})}
                      placeholder="e.g., 80000"
                      className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                    />
                  </div>
                  <div>
                    <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Max Selling Price *</label>
                    <input 
                      type="number"
                      value={formData.max_selling_price || ''}
                      onChange={(e) => setFormData({...formData, max_selling_price: e.target.value})}
                      placeholder="e.g., 95000"
                      className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                    />
                  </div>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Low Stock Alert Threshold</label>
                  <input 
                    type="number"
                    value={formData.low_stock_threshold || 5}
                    onChange={(e) => setFormData({...formData, low_stock_threshold: e.target.value})}
                    placeholder="5"
                    className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                  />
                </div>
              </div>
              <div className="p-5 border-t border-slate-700 flex gap-3 justify-end">
                <button onClick={() => { setShowModal(null); setFormData({}); setEditingItem(null); }} className="px-5 py-2.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium">Cancel</button>
                <button 
                  onClick={showModal === 'addStock' ? handleAddStock : handleEditStock}
                  className="px-5 py-2.5 bg-teal-500 hover:bg-teal-600 text-slate-900 rounded-lg font-semibold"
                >
                  {showModal === 'addStock' ? 'Add Item' : 'Save Changes'}
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Add Category Modal */}
        {showModal === 'addCategory' && (
          <div className="fixed inset-0 bg-black/70 backdrop-blur-sm flex items-center justify-center z-50 p-4">
            <div className="bg-slate-800 border border-slate-700 rounded-2xl w-full max-w-md shadow-2xl">
              <div className="flex justify-between items-center p-5 border-b border-slate-700">
                <h3 className="text-lg font-semibold text-white">Add New Category</h3>
                <button onClick={() => { setShowModal(null); setFormData({}); }} className="w-8 h-8 bg-slate-700 hover:bg-slate-600 rounded-lg flex items-center justify-center text-slate-400 hover:text-white">✕</button>
              </div>
              <div className="p-5">
                <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Category Name</label>
                <input 
                  type="text"
                  value={formData.categoryName || ''}
                  onChange={(e) => setFormData({...formData, categoryName: e.target.value})}
                  placeholder="e.g., Dresses, Shoes, Building Materials"
                  className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                />
              </div>
              <div className="p-5 border-t border-slate-700 flex gap-3 justify-end">
                <button onClick={() => { setShowModal(null); setFormData({}); }} className="px-5 py-2.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium">Cancel</button>
                <button onClick={handleAddCategory} className="px-5 py-2.5 bg-teal-500 hover:bg-teal-600 text-slate-900 rounded-lg font-semibold">Add Category</button>
              </div>
            </div>
          </div>
        )}

        {/* New Sale Modal */}
        {showModal === 'newSale' && (
          <NewSaleModal 
            stock={stock} 
            stockAPI={stockAPI} 
            onClose={() => setShowModal(null)} 
            onSuccess={() => { setShowModal(null); isBoutique ? loadBoutiqueData() : loadHardwareData(); }}
            formatMoney={formatMoney}
          />
        )}
      </div>
    );
  };

  // New Sale Modal Component (used by both Manager and Employee)
  const NewSaleModal = ({ stock, stockAPI, onClose, onSuccess, formatMoney }) => {
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
              className={`px-5 py-2.5 rounded-lg font-semibold ${
                saleItems.length === 0 || saleLoading
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
    const handleAddEmployee = async () => {
      try {
        await employeesAPI.create(formData);
        setShowModal(null);
        setFormData({});
        loadEmployees();
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
      } catch (err) {
        setError(err.response?.data?.error || 'Failed to update employee');
      }
    };

    const handleDeleteEmployee = async (id) => {
      if (!window.confirm('Are you sure you want to delete this employee?')) return;
      try {
        await employeesAPI.delete(id);
        loadEmployees();
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
                    <span className={`px-2 py-0.5 text-xs rounded-full ${
                      emp.assigned_business === 'boutique' ? 'bg-teal-500/15 text-teal-400' :
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
                    onChange={(e) => setFormData({...formData, name: e.target.value})}
                    placeholder="e.g., Sarah Nakato"
                    className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                  />
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Username *</label>
                  <input 
                    type="text"
                    value={formData.username || ''}
                    onChange={(e) => setFormData({...formData, username: e.target.value})}
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
                      onChange={(e) => setFormData({...formData, password: e.target.value})}
                      placeholder="Enter password"
                      className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white"
                    />
                  </div>
                )}
                <div>
                  <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Assigned Business *</label>
                  <select 
                    value={formData.assigned_business || ''}
                    onChange={(e) => setFormData({...formData, assigned_business: e.target.value})}
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
                      <input type="checkbox" checked={formData.can_edit || false} onChange={(e) => setFormData({...formData, can_edit: e.target.checked})} className="rounded" />
                      Can edit sales
                    </label>
                    <label className="flex items-center gap-2 text-white text-sm">
                      <input type="checkbox" checked={formData.can_delete || false} onChange={(e) => setFormData({...formData, can_delete: e.target.checked})} className="rounded" />
                      Can delete sales
                    </label>
                    <label className="flex items-center gap-2 text-white text-sm">
                      <input type="checkbox" checked={formData.can_backdate || false} onChange={(e) => setFormData({...formData, can_backdate: e.target.checked})} className="rounded" />
                      Can backdate entries
                    </label>
                    <label className="flex items-center gap-2 text-white text-sm">
                      <input type="checkbox" checked={formData.can_clear_credits || false} onChange={(e) => setFormData({...formData, can_clear_credits: e.target.checked})} className="rounded" />
                      Can clear credits
                    </label>
                    <label className="flex items-center gap-2 text-white text-sm">
                      <input type="checkbox" checked={formData.is_active !== false} onChange={(e) => setFormData({...formData, is_active: e.target.checked})} className="rounded" />
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
            <BarChart data={revenueData}>
              <CartesianGrid strokeDasharray="3 3" stroke="#334155" />
              <XAxis dataKey="day" stroke="#64748b" />
              <YAxis stroke="#64748b" tickFormatter={(v) => `${v/1000000}M`} />
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
    
    // Sample loan data
    const sampleLoans = [
      { id: 1, client: 'John Mukasa', nin: 'CM1234567890', principal: 500000, rate: 10, total: 550000, balance: 400000, dueDate: '2026-02-17', status: 'active' },
      { id: 2, client: 'Grace Nambi', nin: 'CF9876543210', principal: 300000, rate: 10, total: 330000, balance: 330000, dueDate: '2026-01-20', status: 'overdue' },
      { id: 3, client: 'Peter Okello', nin: 'CM5566778899', principal: 1000000, rate: 12, total: 1120000, balance: 920000, dueDate: '2026-03-01', status: 'active' },
    ];
    
    const sampleGroupLoans = [
      { id: 1, name: 'Kyebando Women', members: 5, total: 2750000, perPeriod: 275000, periodsLeft: 8, totalPeriods: 10, status: 'active' },
      { id: 2, name: 'Kawempe Traders', members: 8, total: 4400000, perPeriod: 550000, periodsLeft: 6, totalPeriods: 8, status: 'active' },
    ];
    
    const samplePayments = [
      { date: '2026-01-20', client: 'John Mukasa', amount: 50000, balanceAfter: 400000, receivedBy: 'Grace' },
      { date: '2026-01-20', client: 'Kyebando Women', amount: 275000, balanceAfter: 2200000, receivedBy: 'Grace' },
      { date: '2026-01-19', client: 'Peter Okello', amount: 200000, balanceAfter: 920000, receivedBy: 'Manager' },
    ];

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
              className={`px-4 py-2 rounded-lg text-sm font-medium transition-colors ${
                financeTab === tab.id ? 'bg-teal-500/15 text-teal-400' : 'text-slate-400 hover:text-white'
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
                  {sampleLoans.map((loan, i) => (
                    <tr key={i} className="hover:bg-slate-700/30">
                      <td className="px-4 py-3 text-white">{loan.client}</td>
                      <td className="px-4 py-3 text-slate-400 font-mono text-sm">{loan.nin}</td>
                      <td className="px-4 py-3 text-white font-mono">{formatMoney(loan.principal)}</td>
                      <td className="px-4 py-3 text-slate-400">{loan.rate}%</td>
                      <td className="px-4 py-3 text-white font-mono">{formatMoney(loan.total)}</td>
                      <td className="px-4 py-3 text-amber-400 font-mono font-semibold">{formatMoney(loan.balance)}</td>
                      <td className="px-4 py-3 text-slate-400">{new Date(loan.dueDate).toLocaleDateString()}</td>
                      <td className="px-4 py-3">
                        <span className={`text-lg ${loan.status === 'overdue' ? '' : ''}`}>
                          {loan.status === 'overdue' ? '🔴' : loan.status === 'due_soon' ? '🟡' : '🟢'}
                        </span>
                      </td>
                      <td className="px-4 py-3">
                        <button className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white">👁️</button>
                        <button className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white">💰</button>
                        <button className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white">🖨️</button>
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
                  {sampleGroupLoans.map((loan, i) => (
                    <tr key={i} className="hover:bg-slate-700/30">
                      <td className="px-4 py-3 text-white font-medium">{loan.name}</td>
                      <td className="px-4 py-3 text-slate-400">{loan.members}</td>
                      <td className="px-4 py-3 text-white font-mono">{formatMoney(loan.total)}</td>
                      <td className="px-4 py-3 text-white font-mono">{formatMoney(loan.perPeriod)}/wk</td>
                      <td className="px-4 py-3 text-slate-400">{loan.periodsLeft} of {loan.totalPeriods}</td>
                      <td className="px-4 py-3"><span className="text-lg">🟢</span></td>
                      <td className="px-4 py-3">
                        <button className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white">👁️</button>
                        <button className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white">💰</button>
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
                {samplePayments.map((payment, i) => (
                  <tr key={i} className="hover:bg-slate-700/30">
                    <td className="px-4 py-3 text-slate-400">{payment.date}</td>
                    <td className="px-4 py-3 text-white">{payment.client}</td>
                    <td className="px-4 py-3 text-green-400 font-mono font-semibold">{formatMoney(payment.amount)}</td>
                    <td className="px-4 py-3 text-white font-mono">{formatMoney(payment.balanceAfter)}</td>
                    <td className="px-4 py-3 text-slate-400">{payment.receivedBy}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    );
  };

  // Audit Trail Page (Manager Only)
  const AuditTrailPage = () => {
    const sampleAuditLogs = [
      { timestamp: '2026-01-20 10:45 AM', employee: 'Sarah', action: 'CREATE', business: 'Boutique', details: 'Sale #127', flagged: false },
      { timestamp: '2026-01-20 10:30 AM', employee: 'Sarah', action: 'EDIT', business: 'Boutique', details: 'Sale #125 - Price: 80,000 → 85,000', flagged: true },
      { timestamp: '2026-01-20 09:15 AM', employee: 'David', action: 'CREATE', business: 'Hardware', details: 'Sale #089', flagged: false },
      { timestamp: '2026-01-20 09:00 AM', employee: 'Grace', action: 'PAYMENT', business: 'Finance', details: 'Loan #045 - UGX 50,000', flagged: false },
      { timestamp: '2026-01-19 04:30 PM', employee: 'Sarah', action: 'DELETE', business: 'Boutique', details: 'Sale #122', flagged: true },
      { timestamp: '2026-01-19 02:00 PM', employee: 'Sarah', action: 'CREATE', business: 'Boutique', details: 'Sale "OTHER" - Gold Necklace', flagged: true },
    ];

    return (
      <div>
        {/* Filters */}
        <div className="bg-slate-800 border border-slate-700 rounded-xl p-4 mb-6">
          <div className="grid grid-cols-1 md:grid-cols-5 gap-4">
            <div>
              <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Employee</label>
              <select className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm">
                <option>All</option>
                <option>Sarah</option>
                <option>David</option>
                <option>Grace</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Action</label>
              <select className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm">
                <option>All</option>
                <option>CREATE</option>
                <option>EDIT</option>
                <option>DELETE</option>
                <option>PAYMENT</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Business</label>
              <select className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm">
                <option>All</option>
                <option>Boutique</option>
                <option>Hardware</option>
                <option>Finance</option>
              </select>
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Date From</label>
              <input type="date" className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm" />
            </div>
            <div>
              <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Date To</label>
              <input type="date" className="w-full px-3 py-2 bg-slate-900 border border-slate-700 rounded-lg text-white text-sm" />
            </div>
          </div>
        </div>

        {/* Audit Log Table */}
        <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
          <table className="w-full">
            <thead>
              <tr className="bg-slate-900/50">
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Timestamp</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Employee</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Action</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Business</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Details</th>
                <th className="text-left px-4 py-3 text-xs font-semibold text-slate-400 uppercase">Flag</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-700">
              {sampleAuditLogs.map((log, i) => (
                <tr key={i} className={`hover:bg-slate-700/30 ${log.flagged ? 'bg-amber-500/5' : ''}`}>
                  <td className="px-4 py-3 text-slate-400 text-sm">{log.timestamp}</td>
                  <td className="px-4 py-3 text-white">{log.employee}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 text-xs rounded-full ${
                      log.action === 'CREATE' ? 'bg-green-500/15 text-green-400' :
                      log.action === 'EDIT' ? 'bg-amber-500/15 text-amber-400' :
                      log.action === 'DELETE' ? 'bg-red-500/15 text-red-400' :
                      'bg-blue-500/15 text-blue-400'
                    }`}>
                      {log.action}
                    </span>
                  </td>
                  <td className="px-4 py-3 text-slate-400">{log.business}</td>
                  <td className="px-4 py-3 text-white text-sm">{log.details}</td>
                  <td className="px-4 py-3">{log.flagged && <span className="text-amber-400">⚠️</span>}</td>
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
    const businessName = user?.assigned_business?.charAt(0).toUpperCase() + user?.assigned_business?.slice(1);
    
    // Sample today's sales for Boutique/Hardware employees
    const todaySales = [
      { time: '10:45 AM', items: 'Ladies Dress, Perfume', total: 205000, status: 'paid' },
      { time: '09:20 AM', items: 'Kids Shoes (2)', total: 90000, status: 'credit' },
      { time: '09:00 AM', items: 'Hand Bag', total: 30000, status: 'paid' },
    ];
    
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
            value={formatMoney(325000)} 
            change="5 transactions"
            icon="🛍️"
            iconBg="bg-teal-500/15"
          />
          <StatCard 
            title="Pending Credits" 
            value={formatMoney(90000)} 
            change="2 customers"
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
              {todaySales.map((sale, i) => (
                <tr key={i} className="hover:bg-slate-700/30">
                  <td className="px-4 py-3 text-slate-400">{sale.time}</td>
                  <td className="px-4 py-3 text-white">{sale.items}</td>
                  <td className="px-4 py-3 text-white font-mono">{formatMoney(sale.total)}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 text-xs rounded-full ${
                      sale.status === 'paid' ? 'bg-green-500/15 text-green-400' : 'bg-amber-500/15 text-amber-400'
                    }`}>
                      {sale.status === 'paid' ? '🟢 Paid' : '🟡 Credit'}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <button className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white">✏️</button>
                    <button className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white">🗑️</button>
                    <button className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white">🖨️</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          <div className="px-5 py-3 border-t border-slate-700">
            <button className="text-teal-400 hover:text-teal-300 text-sm font-medium">View Yesterday's Sales →</button>
          </div>
        </div>
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
        if (!amountPaid || parseFloat(amountPaid) <= 0) {
          setSaleError('Please enter the amount being paid now');
          return;
        }
        if (parseFloat(amountPaid) >= totalAmount) {
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
        amount_paid: paymentType === 'full' ? totalAmount : parseFloat(amountPaid),
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
                  {item.item_name} ({item.quantity} avail) • {Math.round(item.min_selling_price/1000)}K-{Math.round(item.max_selling_price/1000)}K
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
              className={`px-5 py-2.5 rounded-lg font-semibold transition-colors ${
                saleItems.length === 0 
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
    const todaySales = [
      { time: '10:45 AM', items: 'Ladies Dress, Perfume', total: 205000, status: 'paid' },
      { time: '09:20 AM', items: 'Kids Shoes (2)', total: 90000, status: 'credit' },
      { time: '09:00 AM', items: 'Hand Bag', total: 30000, status: 'paid' },
    ];
    
    const yesterdaySales = [
      { time: '04:30 PM', items: 'Perfume (2)', total: 240000, status: 'paid' },
      { time: '11:00 AM', items: 'Kids Shoes', total: 40000, status: 'paid' },
    ];
    
    return (
      <div className="space-y-6">
        {/* Today's Sales */}
        <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-700 flex justify-between items-center">
            <h3 className="font-semibold text-white">TODAY - {new Date().toLocaleDateString()}</h3>
            <span className="text-teal-400 font-mono">Total: {formatMoney(325000)}</span>
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
              {todaySales.map((sale, i) => (
                <tr key={i} className="hover:bg-slate-700/30">
                  <td className="px-4 py-3 text-slate-400">{sale.time}</td>
                  <td className="px-4 py-3 text-white">{sale.items}</td>
                  <td className="px-4 py-3 text-white font-mono">{formatMoney(sale.total)}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 text-xs rounded-full ${sale.status === 'paid' ? 'bg-green-500/15 text-green-400' : 'bg-amber-500/15 text-amber-400'}`}>
                      {sale.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <button className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white">✏️</button>
                    <button className="p-1.5 hover:bg-red-500/20 rounded text-slate-400 hover:text-red-400">🗑️</button>
                    <button className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white">🖨️</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        
        {/* Yesterday's Sales */}
        <div className="bg-slate-800 border border-slate-700 rounded-xl overflow-hidden">
          <div className="px-5 py-4 border-b border-slate-700 flex justify-between items-center">
            <h3 className="font-semibold text-white">YESTERDAY - {new Date(Date.now() - 86400000).toLocaleDateString()}</h3>
            <span className="text-teal-400 font-mono">Total: {formatMoney(280000)}</span>
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
              {yesterdaySales.map((sale, i) => (
                <tr key={i} className="hover:bg-slate-700/30">
                  <td className="px-4 py-3 text-slate-400">{sale.time}</td>
                  <td className="px-4 py-3 text-white">{sale.items}</td>
                  <td className="px-4 py-3 text-white font-mono">{formatMoney(sale.total)}</td>
                  <td className="px-4 py-3">
                    <span className={`px-2 py-0.5 text-xs rounded-full ${sale.status === 'paid' ? 'bg-green-500/15 text-green-400' : 'bg-amber-500/15 text-amber-400'}`}>
                      {sale.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <button className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white">✏️</button>
                    <button className="p-1.5 hover:bg-red-500/20 rounded text-slate-400 hover:text-red-400">🗑️</button>
                    <button className="p-1.5 hover:bg-slate-700 rounded text-slate-400 hover:text-white">🖨️</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        
        <p className="text-center text-slate-500 text-sm">Older sales are not visible to employees</p>
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
  
  // Finance Employee Pages - Active Loans (View Only)
  const ActiveLoansPage = () => {
    const sampleLoans = [
      { client: 'John Mukasa', totalDue: 550000, balance: 400000, dueDate: '2026-02-17', status: 'active' },
      { client: 'Grace Nambi', totalDue: 330000, balance: 330000, dueDate: '2026-01-20', status: 'overdue' },
      { client: 'Peter Okello', totalDue: 1120000, balance: 920000, dueDate: '2026-03-01', status: 'active' },
    ];
    
    return (
      <div>
        <div className="flex justify-between items-center mb-4">
          <h3 className="text-lg font-semibold text-white">ACTIVE LOANS</h3>
          <span className="text-slate-400 text-sm">(View Only)</span>
        </div>
        
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
              {sampleLoans.map((loan, i) => (
                <tr key={i} className="hover:bg-slate-700/30">
                  <td className="px-4 py-3 text-white">{loan.client}</td>
                  <td className="px-4 py-3 text-white font-mono">{formatMoney(loan.totalDue)}</td>
                  <td className="px-4 py-3 text-amber-400 font-mono font-semibold">{formatMoney(loan.balance)}</td>
                  <td className="px-4 py-3 text-slate-400">{new Date(loan.dueDate).toLocaleDateString()}</td>
                  <td className="px-4 py-3">
                    <span className="text-lg">{loan.status === 'overdue' ? '🔴' : '🟢'}</span>
                  </td>
                  <td className="px-4 py-3">
                    <button 
                      onClick={() => setShowModal('recordLoanPayment')}
                      className="px-3 py-1 bg-teal-500/15 text-teal-400 rounded text-sm hover:bg-teal-500/25"
                    >
                      Pay
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    );
  };
  
  // Finance Employee Pages - Record Payment
  const RecordPaymentPage = () => (
    <div className="max-w-lg">
      <div className="bg-slate-800 border border-slate-700 rounded-xl p-6">
        <h3 className="font-semibold text-white mb-6">Record Loan Payment</h3>
        
        <div className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Select Loan</label>
            <select className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white">
              <option value="">-- Select client --</option>
              <option>John Mukasa - UGX 400,000 due</option>
              <option>Grace Nambi - UGX 330,000 due</option>
              <option>Peter Okello - UGX 920,000 due</option>
            </select>
          </div>
          
          <div className="bg-slate-900 rounded-lg p-3 border border-slate-700">
            <p className="text-slate-400 text-sm">Current Balance: <span className="text-amber-400 font-mono font-semibold">UGX 400,000</span></p>
          </div>
          
          <div>
            <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Payment Date</label>
            <select className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white">
              <option>Today - {new Date().toLocaleDateString()}</option>
              <option>Yesterday - {new Date(Date.now() - 86400000).toLocaleDateString()}</option>
            </select>
          </div>
          
          <div>
            <label className="block text-xs font-medium text-slate-400 uppercase tracking-wide mb-2">Payment Amount (UGX)</label>
            <input type="number" placeholder="Enter amount" className="w-full px-4 py-2.5 bg-slate-900 border border-slate-700 rounded-lg text-white" />
          </div>
          
          <div className="bg-slate-900 rounded-lg p-3 border border-slate-700">
            <p className="text-slate-400 text-sm">Balance After Payment: <span className="text-white font-mono">UGX ---</span></p>
          </div>
          
          <div className="flex gap-3 pt-4">
            <button onClick={() => setActiveNav('dashboard')} className="px-5 py-2.5 bg-slate-700 hover:bg-slate-600 text-white rounded-lg font-medium">Cancel</button>
            <button className="px-5 py-2.5 bg-teal-500 hover:bg-teal-600 text-slate-900 rounded-lg font-semibold">Record Payment</button>
          </div>
        </div>
      </div>
    </div>
  );
  
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
    return <LoginPage />;
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
