import React, { useEffect, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { dashboardAPI } from '../services/api';
import { useAuthStore } from '../context/AuthContext';
import { formatCurrency, formatDate } from '../utils/helpers';

const EmployeeDashboard = () => {
  const [data, setData] = useState(null);
  const [loading, setLoading] = useState(true);
  const { user } = useAuthStore();
  const navigate = useNavigate();

  useEffect(() => {
    loadDashboardData();
  }, []);

  const loadDashboardData = async () => {
    try {
      const response = await dashboardAPI.getEmployee();
      setData(response.data);
    } catch (error) {
      console.error('Error loading dashboard:', error);
    } finally {
      setLoading(false);
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

  const { stats, recent_sales } = data;
  const businessName = user.assigned_business.charAt(0).toUpperCase() + user.assigned_business.slice(1);
  const newSalePath = `/${user.assigned_business}/new-sale`;
  const creditsPath = `/${user.assigned_business}/credits`;

  return (
    <div className="space-y-6">
      {/* Welcome Message */}
      <div className="card p-6">
        <h1 className="text-3xl font-bold mb-2">Welcome, {user.name}!</h1>
        <p className="text-text-muted">
          {businessName} Employee Dashboard - {new Date().toLocaleDateString('en-US', { weekday: 'long', month: 'long', day: 'numeric', year: 'numeric' })}
        </p>
      </div>

      {/* Stats Cards */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
        <div className="card p-6">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-text-muted text-sm font-medium">My Sales Today</h3>
            <span className="text-2xl">💰</span>
          </div>
          <p className="text-3xl font-bold font-mono">{formatCurrency(stats.my_sales_today)}</p>
          <p className="text-sm text-text-muted mt-2">{stats.sales_count_today} transactions</p>
        </div>

        <div className="card p-6">
          <div className="flex items-center justify-between mb-2">
            <h3 className="text-text-muted text-sm font-medium">Pending Credits</h3>
            <span className="text-2xl">💳</span>
          </div>
          <p className="text-3xl font-bold font-mono">{formatCurrency(stats.pending_credits)}</p>
          <p className="text-sm text-text-muted mt-2">{stats.credits_count} customers</p>
        </div>

        <div className="card p-6 flex items-center justify-center">
          <div className="text-center">
            <p className="text-text-muted text-sm mb-3">Quick Actions</p>
            <div className="space-y-2">
              <button
                onClick={() => navigate(newSalePath)}
                className="btn-primary w-full"
              >
                📝 New Sale
              </button>
              <button
                onClick={() => navigate(creditsPath)}
                className="btn-secondary w-full"
              >
                💳 View Credits
              </button>
            </div>
          </div>
        </div>
      </div>

      {/* Recent Transactions */}
      <div className="card p-6">
        <h2 className="text-xl font-semibold mb-4">Today's Transactions</h2>
        
        {recent_sales.length === 0 ? (
          <div className="text-center py-8 text-text-muted">
            <p className="text-4xl mb-3">📭</p>
            <p>No transactions yet today</p>
            <button
              onClick={() => navigate(newSalePath)}
              className="btn-primary mt-4"
            >
              Create Your First Sale
            </button>
          </div>
        ) : (
          <div className="overflow-x-auto">
            <table className="w-full">
              <thead>
                <tr className="border-b border-border">
                  <th className="text-left py-3 px-4 text-sm font-medium text-text-muted">Reference</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-text-muted">Date</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-text-muted">Customer</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-text-muted">Amount</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-text-muted">Payment</th>
                  <th className="text-left py-3 px-4 text-sm font-medium text-text-muted">Balance</th>
                </tr>
              </thead>
              <tbody>
                {recent_sales.map((sale) => (
                  <tr key={sale.id} className="border-b border-border hover:bg-secondary transition-colors">
                    <td className="py-3 px-4 font-mono text-sm">{sale.reference_number}</td>
                    <td className="py-3 px-4 text-sm">{formatDate(sale.sale_date)}</td>
                    <td className="py-3 px-4 text-sm">{sale.customer?.name || '-'}</td>
                    <td className="py-3 px-4 font-mono text-sm">{formatCurrency(sale.total_amount)}</td>
                    <td className="py-3 px-4">
                      <span className={`badge ${sale.payment_type === 'full' ? 'badge-success' : 'badge-warning'}`}>
                        {sale.payment_type === 'full' ? 'Full' : 'Part'}
                      </span>
                    </td>
                    <td className="py-3 px-4 font-mono text-sm">
                      {sale.balance > 0 ? formatCurrency(sale.balance) : '-'}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}
      </div>
    </div>
  );
};

export default EmployeeDashboard;
