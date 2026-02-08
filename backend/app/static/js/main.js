// ============ DENOVE APS - MAIN JS ============

// ============ SIDEBAR TOGGLE (MOBILE) ============
function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    if (sidebar) {
        sidebar.classList.toggle('open');
    }
    if (overlay) {
        overlay.classList.toggle('active');
    }
}

function closeSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebar-overlay');
    if (sidebar) sidebar.classList.remove('open');
    if (overlay) overlay.classList.remove('active');
}

// Close sidebar on ESC
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeSidebar();
    }
});

// ============ FORMAT CURRENCY ============
function formatCurrency(amount) {
    return 'UGX ' + Number(amount).toLocaleString('en-US', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    });
}

// ============ CONFIRM DELETE ============
function confirmDelete(message) {
    return confirm(message || 'Are you sure you want to delete this item?');
}

// ============ MODALS ============
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

// ============ FLASH MESSAGES AUTO-HIDE ============
document.addEventListener('DOMContentLoaded', function() {
    const flashMessages = document.querySelectorAll('.flash-message');
    flashMessages.forEach(function(message) {
        setTimeout(function() {
            message.style.transition = 'opacity 0.3s, transform 0.3s';
            message.style.opacity = '0';
            message.style.transform = 'translateY(-10px)';
            setTimeout(function() {
                message.remove();
            }, 300);
        }, 5000);
    });
});

// ============ FORM VALIDATION ============
function validateForm(formId) {
    const form = document.getElementById(formId);
    if (!form) return true;

    const requiredFields = form.querySelectorAll('[required]');
    let isValid = true;

    requiredFields.forEach(function(field) {
        if (!field.value.trim()) {
            field.style.borderColor = '#ef4444';
            isValid = false;
        } else {
            field.style.borderColor = '';
        }
    });

    return isValid;
}

// ============ CALCULATE TOTALS FOR SALES ============
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

// ============ PRINT RECEIPT ============
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
            input.setAttribute('min', yesterdayStr);
            input.setAttribute('max', todayStr);

            input.addEventListener('change', function() {
                const selectedDate = this.value;
                if (selectedDate < yesterdayStr || selectedDate > todayStr) {
                    this.style.borderColor = '#ef4444';
                    alert('You can only enter data for today or yesterday. Contact a manager for older entries.');
                    this.value = todayStr;
                } else {
                    this.style.borderColor = '';
                }
            });
        }
    });
}

// ============ LOAN AGREEMENT PREVIEW ============
function previewLoanAgreement(loanType, loanData) {
    const modal = document.getElementById('agreement-preview-modal');
    if (!modal) return;

    populateAgreementPreview(loanType, loanData);
    modal.classList.add('active');
}

function populateAgreementPreview(loanType, data) {
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
    const agreementData = collectAgreementData();

    if (format === 'pdf') {
        const form = document.getElementById('agreement-download-form');
        if (form) {
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
    const maxSize = 10 * 1024 * 1024;

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
    fileDiv.style.cssText = 'display:flex;align-items:center;gap:12px;padding:10px;background:var(--navy-50);border-radius:10px;margin-top:8px;';
    fileDiv.innerHTML = `
        <div style="width:36px;height:36px;background:var(--terra-50);color:var(--terra-600);border-radius:8px;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;">${fileExt}</div>
        <div style="flex:1;min-width:0;">
            <p style="font-weight:600;font-size:13px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;">${file.name}</p>
            <p style="font-size:11px;color:var(--navy-400);">${(file.size / 1024).toFixed(1)} KB</p>
        </div>
        <button type="button" onclick="this.parentElement.remove()" style="color:#ef4444;font-size:12px;font-weight:600;cursor:pointer;">Remove</button>
    `;
    container.appendChild(fileDiv);
}
