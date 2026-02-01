// Main JavaScript for Denove APS

// Mobile menu toggle
document.addEventListener('DOMContentLoaded', function() {
    const mobileMenuBtn = document.getElementById('mobile-menu-btn');
    const mobileMenu = document.getElementById('mobile-menu');

    if (mobileMenuBtn && mobileMenu) {
        mobileMenuBtn.addEventListener('click', function() {
            mobileMenu.classList.toggle('hidden');
        });
    }
});

// Format currency
function formatCurrency(amount) {
    return 'UGX ' + Number(amount).toLocaleString('en-US', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    });
}

// Confirm delete action
function confirmDelete(message) {
    return confirm(message || 'Are you sure you want to delete this item?');
}

// Show/hide modal
function showModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('active');
    }
}

function hideModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('active');
    }
}

// Close modal on backdrop click
document.addEventListener('click', function(e) {
    if (e.target.classList.contains('modal')) {
        e.target.classList.remove('active');
    }
});

// Auto-hide flash messages after 5 seconds
document.addEventListener('DOMContentLoaded', function() {
    const flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach(function(message) {
        setTimeout(function() {
            message.style.opacity = '0';
            setTimeout(function() {
                message.remove();
            }, 300);
        }, 5000);
    });
});

// Form validation helper
function validateForm(formId) {
    const form = document.getElementById(formId);
    if (!form) return true;

    const requiredFields = form.querySelectorAll('[required]');
    let isValid = true;

    requiredFields.forEach(function(field) {
        if (!field.value.trim()) {
            field.classList.add('border-red-500');
            isValid = false;
        } else {
            field.classList.remove('border-red-500');
        }
    });

    return isValid;
}

// Calculate totals for sales forms
function calculateTotal() {
    const items = document.querySelectorAll('.sale-item');
    let total = 0;

    items.forEach(function(item) {
        const quantity = parseFloat(item.querySelector('.item-quantity')?.value) || 0;
        const price = parseFloat(item.querySelector('.item-price')?.value) || 0;
        const subtotal = quantity * price;

        const subtotalField = item.querySelector('.item-subtotal');
        if (subtotalField) {
            subtotalField.textContent = formatCurrency(subtotal);
        }

        total += subtotal;
    });

    const totalField = document.getElementById('sale-total');
    if (totalField) {
        totalField.textContent = formatCurrency(total);
    }

    return total;
}

// Print receipt
function printReceipt() {
    window.print();
}
