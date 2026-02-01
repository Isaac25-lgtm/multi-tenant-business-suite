# Import all models here for Flask-Migrate to detect them
from app.models.customer import Customer
from app.models.user import User, AuditLog
from app.models.boutique import (
    BoutiqueCategory, BoutiqueStock, BoutiqueSale,
    BoutiqueSaleItem, BoutiqueCreditPayment
)
from app.models.hardware import (
    HardwareCategory, HardwareStock, HardwareSale,
    HardwareSaleItem, HardwareCreditPayment
)
from app.models.finance import (
    LoanClient, Loan, LoanPayment,
    GroupLoan, GroupLoanPayment, LoanDocument
)

__all__ = [
    'Customer', 'User', 'AuditLog',
    'BoutiqueCategory', 'BoutiqueStock', 'BoutiqueSale', 'BoutiqueSaleItem', 'BoutiqueCreditPayment',
    'HardwareCategory', 'HardwareStock', 'HardwareSale', 'HardwareSaleItem', 'HardwareCreditPayment',
    'LoanClient', 'Loan', 'LoanPayment', 'GroupLoan', 'GroupLoanPayment', 'LoanDocument'
]
