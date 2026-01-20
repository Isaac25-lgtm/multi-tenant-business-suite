import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuthStore } from '../context/AuthContext';

const LoginPage = () => {
  const [credentials, setCredentials] = useState({
    username: '',
    password: '',
    assigned_business: '',
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  
  const navigate = useNavigate();
  const login = useAuthStore((state) => state.login);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const user = await login(credentials);
      
      // Redirect based on role
      if (user.role === 'manager') {
        navigate('/dashboard');
      } else {
        navigate('/employee-dashboard');
      }
    } catch (err) {
      setError(err.response?.data?.error || 'Login failed. Please try again.');
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-gradient-to-br from-primary-dark via-primary-light to-secondary">
      <div className="w-full max-w-md">
        <div className="card p-8">
          {/* Logo/Brand */}
          <div className="text-center mb-8">
            <h1 className="text-4xl font-bold text-accent mb-2">DENOVE APS</h1>
            <p className="text-text-muted">Business Management System</p>
          </div>

          {/* Error Message */}
          {error && (
            <div className="mb-6 p-4 bg-danger bg-opacity-10 border border-danger rounded-lg text-danger text-sm">
              {error}
            </div>
          )}

          {/* Login Form */}
          <form onSubmit={handleSubmit} className="space-y-6">
            <div>
              <label className="label">Username</label>
              <input
                type="text"
                className="input"
                value={credentials.username}
                onChange={(e) => setCredentials({ ...credentials, username: e.target.value })}
                placeholder="Enter your username"
                required
              />
            </div>

            <div>
              <label className="label">Password</label>
              <input
                type="password"
                className="input"
                value={credentials.password}
                onChange={(e) => setCredentials({ ...credentials, password: e.target.value })}
                placeholder="Enter your password"
                required
              />
            </div>

            <div>
              <label className="label">Business Unit (Optional)</label>
              <select
                className="input"
                value={credentials.assigned_business}
                onChange={(e) => setCredentials({ ...credentials, assigned_business: e.target.value })}
              >
                <option value="">-- Select Business --</option>
                <option value="boutique">Boutique</option>
                <option value="hardware">Hardware</option>
                <option value="finances">Finances</option>
              </select>
              <p className="text-xs text-text-muted mt-1">
                Employees should select their assigned business
              </p>
            </div>

            <button
              type="submit"
              className="w-full btn-primary py-3 text-lg"
              disabled={loading}
            >
              {loading ? 'Logging in...' : 'Login'}
            </button>
          </form>

          {/* Demo Credentials */}
          <div className="mt-8 pt-6 border-t border-border">
            <p className="text-xs text-text-muted text-center mb-3">Demo Credentials:</p>
            <div className="text-xs text-text-muted space-y-1">
              <p>Manager: <span className="text-accent">manager / admin123</span></p>
              <p>Sarah (Boutique): <span className="text-accent">sarah / pass123</span></p>
              <p>David (Hardware): <span className="text-accent">david / pass123</span></p>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};

export default LoginPage;
