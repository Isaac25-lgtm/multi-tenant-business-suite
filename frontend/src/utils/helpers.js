/**
 * Format number as currency with thousands separator
 */
export const formatCurrency = (amount) => {
  if (amount === null || amount === undefined) return 'UGX 0';
  return `UGX ${Number(amount).toLocaleString('en-US', { maximumFractionDigits: 0 })}`;
};

/**
 * Format date to readable string
 */
export const formatDate = (dateString) => {
  if (!dateString) return '';
  const date = new Date(dateString);
  return date.toLocaleDateString('en-US', { 
    year: 'numeric', 
    month: 'long', 
    day: 'numeric' 
  });
};

/**
 * Format date to input value (YYYY-MM-DD)
 */
export const formatDateForInput = (date) => {
  if (!date) return '';
  const d = new Date(date);
  const year = d.getFullYear();
  const month = String(d.getMonth() + 1).padStart(2, '0');
  const day = String(d.getDate()).padStart(2, '0');
  return `${year}-${month}-${day}`;
};

/**
 * Get today's date in YYYY-MM-DD format
 */
export const getToday = () => {
  return formatDateForInput(new Date());
};

/**
 * Get yesterday's date in YYYY-MM-DD format
 */
export const getYesterday = () => {
  const yesterday = new Date();
  yesterday.setDate(yesterday.getDate() - 1);
  return formatDateForInput(yesterday);
};

/**
 * Calculate percentage change
 */
export const calculatePercentageChange = (current, previous) => {
  if (previous === 0) return current > 0 ? 100 : 0;
  return ((current - previous) / previous) * 100;
};

/**
 * Get status badge color
 */
export const getStatusColor = (status) => {
  const colors = {
    active: 'success',
    cleared: 'success',
    pending: 'warning',
    overdue: 'danger',
    full: 'success',
    part: 'warning',
  };
  return colors[status] || 'secondary';
};

/**
 * Validate price in range
 */
export const validatePriceRange = (price, minPrice, maxPrice) => {
  const p = Number(price);
  const min = Number(minPrice);
  const max = Number(maxPrice);
  return p >= min && p <= max;
};

/**
 * Debounce function
 */
export const debounce = (func, wait) => {
  let timeout;
  return function executedFunction(...args) {
    const later = () => {
      clearTimeout(timeout);
      func(...args);
    };
    clearTimeout(timeout);
    timeout = setTimeout(later, wait);
  };
};
