import { create } from 'zustand';

export const useToastStore = create((set, get) => ({
  toasts: [],

  addToast: (toast) => {
    const id = Date.now();
    const newToast = {
      id,
      type: toast.type || 'info', // success, error, warning, info
      message: toast.message,
      duration: toast.duration || 5000,
    };

    set((state) => ({
      toasts: [...state.toasts, newToast],
    }));

    // Auto remove after duration
    if (newToast.duration > 0) {
      setTimeout(() => {
        get().removeToast(id);
      }, newToast.duration);
    }

    return id;
  },

  removeToast: (id) => {
    set((state) => ({
      toasts: state.toasts.filter((toast) => toast.id !== id),
    }));
  },

  // Convenience methods
  success: (message, duration) => {
    return get().addToast({ type: 'success', message, duration });
  },

  error: (message, duration) => {
    return get().addToast({ type: 'error', message, duration: duration || 7000 });
  },

  warning: (message, duration) => {
    return get().addToast({ type: 'warning', message, duration });
  },

  info: (message, duration) => {
    return get().addToast({ type: 'info', message, duration });
  },

  clearAll: () => {
    set({ toasts: [] });
  },
}));
