import React, { useEffect, useState } from 'react';
import { dashboardAPI } from '../services/api';
import { formatCurrency, calculatePercentageChange } from '../utils/helpers';
import { LineChart, Line, PieChart, Pie, Cell, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

const ManagerDashboard = () => {
  const [data, setData] = useState(null);
  const [notifications, setNotifications] = useState([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    loadDashboardData();
    loadNotifications();
  }, []);

  const loadDashboardData = async () => {
    try {
      const response = await dashboardAPI.getManager();
      setData(response.data);
    } catch (error) {
      console.error('Error loading dashboard:', error);
    } finally {
      setLoading(false);
    }
  };

  const loadNotifications = async () => {
    try {
      const response = await dashboardAPI.getNotifications();
      setNotifications(response.data.notifications);
    } catch (error) {
      console.error('Error loading notifications:', error);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="text-4xl mb-4">⏳</div>
          <p className="text-text-muted">Loading dashboard...</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="text-center text-danger">Failed to load dashboard data</div>
    );
  }

  const { stats, by_business, sales_trend } = data;
  const percentageChange = calculatePercentageChange(stats.today_revenue, stats.yesterday_revenue);

  // Prepare pie chart data
  const revenueByBusiness = [
    { name: 'Boutique', value: by_business.boutique.today },
    { name: 'Hardware', value: by_business.hardware.today },
    { name: 'Finance', value: by_business.finance.repayments_today },
  ];

  const COLORS = ['#14b8a6', '#f59e0b', '#8b5cf6'];

  return (
    <div className="space-y-6">
      {/* Page Header */}
      <div>
        <h1 className="text-3xl font-bold mb-2">Manager Dashboard</h1>
        <p className="text-text-muted">Welcome back! Here's your business overview.</p>
      </div>

      {/* Notifications */}
      {notifications.length > 0 && (
        <div className="card p-4">
          <h3 className="font-semibold mb-3 flex items-center">
            <span className="text-xl mr-2">🔔</span>
            Alerts ({notifications.length})
          </h3>
          <div className="space-y-2">
            {notifications.map((notif, index) => (
              <div
                key={index}
                className={`p-3 rounded-lg text-sm ${
                  notif.severity === 'warning' ? 'bg-warning bg-opacity-10 text-warning' : 'bg-danger bg-opacity-10 text-danger'
                }`}
              >
                {notif.message}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <div className="card p-6">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-text-muted text-sm font-medium">Today's Revenue</h3>
            <span className="text-2xl">💰</span>
          </div>
          <p className="text-3xl font-bold font-mono">{formatCurrency(stats.today_revenue)}</p>
          <p className={`text-sm mt-2 ${percentageChange >= 0 ? 'text-success' : 'text-danger'}`}>
            {percentageChange >= 0 ? '↑' : '↓'} {Math.abs(percentageChange).toFixed(1)}% from yesterday
          </p>
        </div>

        <div className="card p-6">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-text-muted text-sm font-medium">Credits Outstanding</h3>
            <span className="text-2xl">💳</span>
          </div>
          <p className="text-3xl font-bold font-mono">{formatCurrency(stats.credits_outstanding)}</p>
          <p className="text-sm text-text-muted mt-2">Pending customer payments</p>
        </div>

        <div className="card p-6">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-text-muted text-sm font-medium">Low Stock Alerts</h3>
            <span className="text-2xl">⚠️</span>
          </div>
          <p className="text-3xl font-bold">{stats.low_stock_alerts}</p>
          <p className="text-sm text-text-muted mt-2">Items need restocking</p>
        </div>

        <div className="card p-6">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-text-muted text-sm font-medium">Yesterday's Revenue</h3>
            <span className="text-2xl">📊</span>
          </div>
          <p className="text-3xl font-bold font-mono">{formatCurrency(stats.yesterday_revenue)}</p>
          <p className="text-sm text-text-muted mt-2">Previous day comparison</p>
        </div>
      </div>

      {/* Charts Section */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Revenue Trend */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold mb-4">7-Day Revenue Trend</h3>
          <ResponsiveContainer width="100%" height={300}>
            <LineChart data={sales_trend}>
              <CartesianGrid strokeDasharray="3 3" stroke="#475569" />
              <XAxis 
                dataKey="date" 
                stroke="#94a3b8"
                tickFormatter={(value) => new Date(value).toLocaleDateString('en-US', { month: 'short', day: 'numeric' })}
              />
              <YAxis stroke="#94a3b8" />
              <Tooltip 
                contentStyle={{ backgroundColor: '#1e293b', border: '1px solid #475569' }}
                labelStyle={{ color: '#f8fafc' }}
                formatter={(value) => formatCurrency(value)}
              />
              <Legend />
              <Line type="monotone" dataKey="boutique" stroke="#14b8a6" name="Boutique" strokeWidth={2} />
              <Line type="monotone" dataKey="hardware" stroke="#f59e0b" name="Hardware" strokeWidth={2} />
              <Line type="monotone" dataKey="finance" stroke="#8b5cf6" name="Finance" strokeWidth={2} />
            </LineChart>
          </ResponsiveContainer>
        </div>

        {/* Revenue by Business */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold mb-4">Today's Revenue by Business</h3>
          <ResponsiveContainer width="100%" height={300}>
            <PieChart>
              <Pie
                data={revenueByBusiness}
                cx="50%"
                cy="50%"
                labelLine={false}
                label={({ name, percent }) => `${name}: ${(percent * 100).toFixed(0)}%`}
                outerRadius={100}
                fill="#8884d8"
                dataKey="value"
              >
                {revenueByBusiness.map((entry, index) => (
                  <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                ))}
              </Pie>
              <Tooltip formatter={(value) => formatCurrency(value)} />
            </PieChart>
          </ResponsiveContainer>
        </div>
      </div>

      {/* Business Breakdown */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">
        {/* Boutique */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center">
            <span className="text-2xl mr-2">👗</span>
            Boutique Summary
          </h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-text-muted">Today's Sales</span>
              <span className="font-mono font-semibold">{formatCurrency(by_business.boutique.today)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-text-muted">Credits Outstanding</span>
              <span className="font-mono font-semibold">{formatCurrency(by_business.boutique.credits)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-text-muted">Low Stock Items</span>
              <span className="font-semibold">{by_business.boutique.low_stock}</span>
            </div>
          </div>
        </div>

        {/* Hardware */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center">
            <span className="text-2xl mr-2">🔨</span>
            Hardware Summary
          </h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-text-muted">Today's Sales</span>
              <span className="font-mono font-semibold">{formatCurrency(by_business.hardware.today)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-text-muted">Credits Outstanding</span>
              <span className="font-mono font-semibold">{formatCurrency(by_business.hardware.credits)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-text-muted">Low Stock Items</span>
              <span className="font-semibold">{by_business.hardware.low_stock}</span>
            </div>
          </div>
        </div>

        {/* Finance */}
        <div className="card p-6">
          <h3 className="text-lg font-semibold mb-4 flex items-center">
            <span className="text-2xl mr-2">💰</span>
            Finance Summary
          </h3>
          <div className="space-y-3">
            <div className="flex justify-between items-center">
              <span className="text-text-muted">Today's Repayments</span>
              <span className="font-mono font-semibold">{formatCurrency(by_business.finance.repayments_today)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-text-muted">Loans Outstanding</span>
              <span className="font-mono font-semibold">{formatCurrency(by_business.finance.outstanding)}</span>
            </div>
            <div className="flex justify-between items-center">
              <span className="text-text-muted">Overdue Loans</span>
              <span className="font-semibold text-danger">{by_business.finance.overdue_count}</span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default ManagerDashboard;
