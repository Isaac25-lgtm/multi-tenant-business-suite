import React from 'react';
import { useAuthStore } from '../context/AuthContext';

const BoutiquePage = () => {
  const { user } = useAuthStore();
  const isManager = user?.role === 'manager';

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-3xl font-bold mb-2">👗 Boutique</h1>
        <p className="text-text-muted">
          {isManager ? 'Manage boutique inventory and sales' : 'Record boutique sales and manage credits'}
        </p>
      </div>

      <div className="card p-8 text-center">
        <p className="text-4xl mb-4">🚧</p>
        <h2 className="text-2xl font-semibold mb-2">Under Construction</h2>
        <p className="text-text-muted">
          Boutique management interface will include:
        </p>
        <ul className="text-left max-w-md mx-auto mt-4 space-y-2 text-text-muted">
          <li>✓ Stock management (add, edit, adjust quantities)</li>
          <li>✓ Sales recording with price validation</li>
          <li>✓ Credit sales and payment tracking</li>
          <li>✓ Category management</li>
          <li>✓ Receipt generation</li>
        </ul>
      </div>
    </div>
  );
};

export default BoutiquePage;
