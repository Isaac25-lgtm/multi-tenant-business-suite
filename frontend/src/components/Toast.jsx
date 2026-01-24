import React from 'react';
import { useToastStore } from '../context/ToastContext';

const ToastIcon = ({ type }) => {
  switch (type) {
    case 'success':
      return <span className="text-lg">✓</span>;
    case 'error':
      return <span className="text-lg">✕</span>;
    case 'warning':
      return <span className="text-lg">⚠</span>;
    case 'info':
    default:
      return <span className="text-lg">ℹ</span>;
  }
};

const Toast = ({ toast }) => {
  const { removeToast } = useToastStore();

  const bgColors = {
    success: 'bg-green-500/15 border-green-500/50 text-green-400',
    error: 'bg-red-500/15 border-red-500/50 text-red-400',
    warning: 'bg-amber-500/15 border-amber-500/50 text-amber-400',
    info: 'bg-blue-500/15 border-blue-500/50 text-blue-400',
  };

  return (
    <div
      className={`flex items-center gap-3 px-4 py-3 rounded-lg border backdrop-blur-sm shadow-lg animate-slide-in ${bgColors[toast.type] || bgColors.info}`}
      role="alert"
    >
      <div className="flex-shrink-0">
        <ToastIcon type={toast.type} />
      </div>
      <p className="flex-1 text-sm font-medium">{toast.message}</p>
      <button
        onClick={() => removeToast(toast.id)}
        className="flex-shrink-0 opacity-70 hover:opacity-100 transition-opacity"
      >
        ✕
      </button>
    </div>
  );
};

const ToastContainer = () => {
  const { toasts } = useToastStore();

  if (toasts.length === 0) return null;

  return (
    <div className="fixed top-4 right-4 z-50 flex flex-col gap-2 max-w-sm w-full">
      {toasts.map((toast) => (
        <Toast key={toast.id} toast={toast} />
      ))}
    </div>
  );
};

export default ToastContainer;
