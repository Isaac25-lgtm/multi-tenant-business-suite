import axios from 'axios';
import { useToastStore } from '../context/ToastContext';

const API_BASE_URL = import.meta.env.VITE_API_URL || '/api';

// Create axios instance
const api = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add token to requests
api.interceptors.request.use((config) => {
  const token = localStorage.getItem('token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle response errors
api.interceptors.response.use(
  (response) => response,
  (error) => {
    const toast = useToastStore.getState();

    // Handle different error types
    if (error.response) {
      const status = error.response.status;
      const message = error.response.data?.error || error.response.data?.message;

      switch (status) {
        case 401:
          localStorage.removeItem('token');
          localStorage.removeItem('user');
          toast.error('Session expired. Please login again.');
          window.location.href = '/login';
          break;
        case 403:
          // Only show toast if there's a specific message
          if (message) {
            toast.error(message);
          }
          break;
        case 500:
          toast.error('Server error. Please try again later.');
          break;
        // Don't show toasts for 400, 404, 422 - let components handle these
        default:
          break;
      }
    } else if (error.request) {
      // Network error
      toast.error('Network error. Please check your connection.');
    }

    return Promise.reject(error);
  }
);

// Auth API
export const authAPI = {
  login: (credentials) => api.post('/auth/login', credentials),
  logout: () => api.post('/auth/logout'),
  me: () => api.get('/auth/me'),
  changePassword: (data) => api.put('/auth/change-password', data),
};

// Employees API
export const employeesAPI = {
  getAll: () => api.get('/employees'),
  create: (data) => api.post('/employees', data),
  get: (id) => api.get(`/employees/${id}`),
  update: (id, data) => api.put(`/employees/${id}`, data),
  delete: (id) => api.delete(`/employees/${id}`),
  updatePermissions: (id, data) => api.put(`/employees/${id}/permissions`, data),
};

// Customers API
export const customersAPI = {
  getAll: (params) => api.get('/customers', { params }),
  search: (query, businessType) => api.get('/customers/search', { params: { q: query, business_type: businessType } }),
  create: (data) => api.post('/customers', data),
  get: (id) => api.get(`/customers/${id}`),
  update: (id, data) => api.put(`/customers/${id}`, data),
};

// Boutique API
export const boutiqueAPI = {
  // Categories
  getCategories: () => api.get('/boutique/categories'),
  createCategory: (data) => api.post('/boutique/categories', data),

  // Stock
  getStock: (params) => api.get('/boutique/stock', { params }),
  addStock: (data) => api.post('/boutique/stock', data),
  updateStock: (id, data) => api.put(`/boutique/stock/${id}`, data),
  adjustQuantity: (id, data) => api.put(`/boutique/stock/${id}/quantity`, data),
  deleteStock: (id) => api.delete(`/boutique/stock/${id}`),

  // Sales
  getSales: (params) => api.get('/boutique/sales', { params }),
  getSale: (id) => api.get(`/boutique/sales/${id}`),
  createSale: (data) => api.post('/boutique/sales', data),
  updateSale: (id, data) => api.put(`/boutique/sales/${id}`, data),
  deleteSale: (id) => api.delete(`/boutique/sales/${id}`),
  getReceipt: (id) => api.get(`/boutique/sales/${id}/receipt`, { responseType: 'blob' }),

  // Credits
  getCredits: () => api.get('/boutique/credits'),
  getClearedCredits: () => api.get('/boutique/credits/cleared'),
  getCreditDetails: (id) => api.get(`/boutique/credits/${id}`),
  recordPayment: (id, data) => api.post(`/boutique/credits/${id}/payment`, data),
};

// Hardware API (same structure as boutique)
export const hardwareAPI = {
  // Categories
  getCategories: () => api.get('/hardware/categories'),
  createCategory: (data) => api.post('/hardware/categories', data),

  // Stock
  getStock: (params) => api.get('/hardware/stock', { params }),
  addStock: (data) => api.post('/hardware/stock', data),
  updateStock: (id, data) => api.put(`/hardware/stock/${id}`, data),
  adjustQuantity: (id, data) => api.put(`/hardware/stock/${id}/quantity`, data),
  deleteStock: (id) => api.delete(`/hardware/stock/${id}`),

  // Sales
  getSales: (params) => api.get('/hardware/sales', { params }),
  getSale: (id) => api.get(`/hardware/sales/${id}`),
  createSale: (data) => api.post('/hardware/sales', data),
  updateSale: (id, data) => api.put(`/hardware/sales/${id}`, data),
  deleteSale: (id) => api.delete(`/hardware/sales/${id}`),
  getReceipt: (id) => api.get(`/hardware/sales/${id}/receipt`, { responseType: 'blob' }),

  // Credits
  getCredits: () => api.get('/hardware/credits'),
  getClearedCredits: () => api.get('/hardware/credits/cleared'),
  getCreditDetails: (id) => api.get(`/hardware/credits/${id}`),
  recordPayment: (id, data) => api.post(`/hardware/credits/${id}/payment`, data),
};

// Dashboard API
export const dashboardAPI = {
  getManager: () => api.get('/dashboard/manager'),
  getEmployee: () => api.get('/dashboard/employee'),
  getNotifications: () => api.get('/dashboard/notifications'),
  getAuditLogs: (params) => api.get('/dashboard/audit', { params }),
};

// Finance API
export const financeAPI = {
  // Clients
  getClients: () => api.get('/finance/clients'),
  createClient: (data) => api.post('/finance/clients', data),

  // Individual Loans
  getLoans: () => api.get('/finance/loans'),
  getLoan: (id) => api.get(`/finance/loans/${id}`),
  createLoan: (data) => api.post('/finance/loans', data),
  updateLoan: (id, data) => api.put(`/finance/loans/${id}`, data),
  deleteLoan: (id) => api.delete(`/finance/loans/${id}`),
  recordLoanPayment: (id, data) => api.post(`/finance/loans/${id}/payment`, data),
  uploadLoanDocuments: (id, formData) => api.post(`/finance/loans/${id}/documents`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),

  // Group Loans
  getGroupLoans: () => api.get('/finance/group-loans'),
  createGroupLoan: (data) => api.post('/finance/group-loans', data),
  updateGroupLoan: (id, data) => api.put(`/finance/group-loans/${id}`, data),
  deleteGroupLoan: (id) => api.delete(`/finance/group-loans/${id}`),
  recordGroupPayment: (id, data) => api.post(`/finance/group-loans/${id}/payment`, data),
  uploadGroupLoanDocuments: (id, formData) => api.post(`/finance/group-loans/${id}/documents`, formData, {
    headers: { 'Content-Type': 'multipart/form-data' }
  }),


  // All Payments
  getAllPayments: () => api.get('/finance/payments'),

  // Stats
  getStats: () => api.get('/finance/stats'),
};

export default api;

