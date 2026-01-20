import React from 'react';
import { Navigate } from 'react-router-dom';
import { useAuthStore } from '../context/AuthContext';

const ProtectedRoute = ({ children, managerOnly = false }) => {
  const { isAuthenticated, user } = useAuthStore();

  if (!isAuthenticated) {
    return <Navigate to="/login" replace />;
  }

  if (managerOnly && user?.role !== 'manager') {
    return <Navigate to="/employee-dashboard" replace />;
  }

  return children;
};

export default ProtectedRoute;
