// Main JavaScript for Denove APS

// ============ DARK MODE ============
function toggleTheme() {
    const html = document.documentElement;
    const currentTheme = html.getAttribute('data-theme');
    const newTheme = currentTheme === 'dark' ? 'light' : 'dark';

    html.setAttribute('data-theme', newTheme);
    localStorage.setItem('theme', newTheme);
    updateThemeIcon(newTheme);
}

function updateThemeIcon(theme) {
    const sunIcon = document.getElementById('sun-icon');
    const moonIcon = document.getElementById('moon-icon');

    if (sunIcon && moonIcon) {
        if (theme === 'dark') {
            sunIcon.classList.add('hidden');
            moonIcon.classList.remove('hidden');
        } else {
            sunIcon.classList.remove('hidden');
            moonIcon.classList.add('hidden');
        }
    }
}

// Initialize theme on page load
document.addEventListener('DOMContentLoaded', function() {
    const savedTheme = localStorage.getItem('theme') || 'light';
    document.documentElement.setAttribute('data-theme', savedTheme);
    updateThemeIcon(savedTheme);
});

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

// ============ DATE RESTRICTIONS FOR EMPLOYEES ============
function initDateRestrictions(isManager) {
    const dateInputs = document.querySelectorAll('input[type="date"].date-restricted-input');
    const today = new Date();
    const yesterday = new Date(today);
    yesterday.setDate(yesterday.getDate() - 1);

    const todayStr = today.toISOString().split('T')[0];
    const yesterdayStr = yesterday.toISOString().split('T')[0];

    dateInputs.forEach(input => {
        if (!isManager) {
            // Employees can only select today or yesterday
            input.setAttribute('min', yesterdayStr);
            input.setAttribute('max', todayStr);

            input.addEventListener('change', function() {
                const selectedDate = this.value;
                if (selectedDate < yesterdayStr || selectedDate > todayStr) {
                    this.classList.add('border-red-500');
                    alert('You can only enter data for today or yesterday. Contact a manager for older entries.');
                    this.value = todayStr;
                } else {
                    this.classList.remove('border-red-500');
                }
            });
        }
    });
}

// ============ LOAN AGREEMENT PREVIEW ============
function previewLoanAgreement(loanType, loanData) {
    const modal = document.getElementById('agreement-preview-modal');
    if (!modal) return;

    // Populate the agreement preview
    populateAgreementPreview(loanType, loanData);
    modal.classList.add('active');
}

function populateAgreementPreview(loanType, data) {
    // Update editable fields in the agreement preview
    const fields = {
        'agreement-company-name': 'DENOVE APS',
        'agreement-client-name': data.clientName || data.groupName || '',
        'agreement-principal': formatCurrency(data.principal || 0),
        'agreement-interest-rate': (data.interestRate || 0) + '%',
        'agreement-total-amount': formatCurrency(data.totalAmount || 0),
        'agreement-duration': data.duration || '',
        'agreement-issue-date': data.issueDate || new Date().toISOString().split('T')[0],
        'agreement-due-date': data.dueDate || ''
    };

    for (const [id, value] of Object.entries(fields)) {
        const element = document.getElementById(id);
        if (element) {
            if (element.tagName === 'INPUT' || element.tagName === 'TEXTAREA') {
                element.value = value;
            } else {
                element.textContent = value;
            }
        }
    }
}

function downloadAgreement(format) {
    // Collect all editable field values
    const agreementData = collectAgreementData();

    if (format === 'pdf') {
        // Submit form to generate PDF
        const form = document.getElementById('agreement-download-form');
        if (form) {
            // Update hidden fields with current values
            for (const [key, value] of Object.entries(agreementData)) {
                let input = form.querySelector(`input[name="${key}"]`);
                if (!input) {
                    input = document.createElement('input');
                    input.type = 'hidden';
                    input.name = key;
                    form.appendChild(input);
                }
                input.value = value;
            }
            form.submit();
        }
    }
}

function collectAgreementData() {
    const editableFields = document.querySelectorAll('.agreement-preview .editable-field');
    const data = {};

    editableFields.forEach(field => {
        const name = field.getAttribute('data-field') || field.id;
        data[name] = field.value || field.textContent;
    });

    return data;
}

// ============ COLLATERAL UPLOAD ============
function initCollateralUpload() {
    const uploadZone = document.querySelector('.upload-zone');
    const fileInput = document.getElementById('collateral-file');

    if (uploadZone && fileInput) {
        uploadZone.addEventListener('click', () => fileInput.click());

        uploadZone.addEventListener('dragover', (e) => {
            e.preventDefault();
            uploadZone.classList.add('dragover');
        });

        uploadZone.addEventListener('dragleave', () => {
            uploadZone.classList.remove('dragover');
        });

        uploadZone.addEventListener('drop', (e) => {
            e.preventDefault();
            uploadZone.classList.remove('dragover');
            const files = e.dataTransfer.files;
            if (files.length > 0) {
                handleCollateralFile(files[0]);
            }
        });

        fileInput.addEventListener('change', () => {
            if (fileInput.files.length > 0) {
                handleCollateralFile(fileInput.files[0]);
            }
        });
    }
}

function handleCollateralFile(file) {
    const allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'application/pdf'];
    const maxSize = 10 * 1024 * 1024; // 10MB

    if (!allowedTypes.includes(file.type)) {
        alert('Invalid file type. Please upload an image (JPG, PNG, GIF) or PDF.');
        return;
    }

    if (file.size > maxSize) {
        alert('File is too large. Maximum size is 10MB.');
        return;
    }

    displayUploadedFile(file);
}

function displayUploadedFile(file) {
    const container = document.getElementById('uploaded-files-container');
    if (!container) return;

    const fileExt = file.name.split('.').pop().toUpperCase();
    const fileDiv = document.createElement('div');
    fileDiv.className = 'uploaded-file';
    fileDiv.innerHTML = `
        <div class="file-icon">${fileExt}</div>
        <div class="flex-1">
            <p class="font-medium text-sm">${file.name}</p>
            <p class="text-xs text-gray-500">${(file.size / 1024).toFixed(1)} KB</p>
        </div>
        <button type="button" onclick="this.parentElement.remove()" class="text-red-600 hover:underline text-sm">Remove</button>
    `;
    container.appendChild(fileDiv);
}
