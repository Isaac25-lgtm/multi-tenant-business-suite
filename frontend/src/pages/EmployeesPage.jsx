import React, { useEffect, useState } from 'react';
import { employeesAPI } from '../services/api';
import { formatDate } from '../utils/helpers';

const EmployeesPage = () => {
  const [employees, setEmployees] = useState([]);
  const [loading, setLoading] = useState(true);
  const [showCreateModal, setShowCreateModal] = useState(false);

  useEffect(() => {
    loadEmployees();
  }, []);

  const loadEmployees = async () => {
    try {
      const response = await employeesAPI.getAll();
      setEmployees(response.data.employees);
    } catch (error) {
      console.error('Error loading employees:', error);
    } finally {
      setLoading(false);
    }
  };

  if (loading) {
    return (
      <div className="flex items-center justify-center h-full">
        <div className="text-center">
          <div className="text-4xl mb-4">⏳</div>
          <p className="text-text-muted">Loading employees...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <div className="flex justify-between items-center">
        <div>
          <h1 className="text-3xl font-bold mb-2">👥 Employee Management</h1>
          <p className="text-text-muted">Manage employee accounts and permissions</p>
        </div>
        <button
          onClick={() => setShowCreateModal(true)}
          className="btn-primary"
        >
          + Add Employee
        </button>
      </div>

      <div className="card p-6">
        <div className="overflow-x-auto">
          <table className="w-full">
            <thead>
              <tr className="border-b border-border">
                <th className="text-left py-3 px-4 text-sm font-medium text-text-muted">Name</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-text-muted">Username</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-text-muted">Business</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-text-muted">Permissions</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-text-muted">Status</th>
                <th className="text-left py-3 px-4 text-sm font-medium text-text-muted">Actions</th>
              </tr>
            </thead>
            <tbody>
              {employees.map((employee) => (
                <tr key={employee.id} className="border-b border-border hover:bg-secondary transition-colors">
                  <td className="py-3 px-4 font-medium">{employee.name}</td>
                  <td className="py-3 px-4 text-sm text-text-muted">{employee.username}</td>
                  <td className="py-3 px-4">
                    <span className="badge badge-success capitalize">{employee.assigned_business}</span>
                  </td>
                  <td className="py-3 px-4 text-sm">
                    <div className="space-y-1">
                      {employee.can_edit && <span className="text-xs text-success">✓ Edit</span>}
                      {employee.can_delete && <span className="text-xs text-success ml-2">✓ Delete</span>}
                      {employee.can_backdate && <span className="text-xs text-warning ml-2">⚠ Backdate</span>}
                    </div>
                  </td>
                  <td className="py-3 px-4">
                    <span className={`badge ${employee.is_active ? 'badge-success' : 'badge-danger'}`}>
                      {employee.is_active ? 'Active' : 'Inactive'}
                    </span>
                  </td>
                  <td className="py-3 px-4">
                    <button className="text-accent hover:text-accent-hover text-sm mr-3">Edit</button>
                    <button className="text-danger hover:opacity-80 text-sm">Deactivate</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        {employees.length === 0 && (
          <div className="text-center py-8 text-text-muted">
            <p className="text-4xl mb-3">👥</p>
            <p>No employees found</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default EmployeesPage;
