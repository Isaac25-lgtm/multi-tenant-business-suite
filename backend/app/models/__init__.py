# Import all models here for Flask-Migrate to detect them
from app.models.user import User
from app.models.customer import Customer
from app.models.boutique import (
    BoutiqueCategory, BoutiqueStock, BoutiqueSale, 
    BoutiqueSaleItem, BoutiqueCreditPayment
)
from app.models.hardware import (
    HardwareCategory, HardwareStock, HardwareSale,
    HardwareSaleItem, HardwareCreditPayment
)
from app.models.audit import AuditLog

__all__ = [
    'User', 'Customer', 
    'BoutiqueCategory', 'BoutiqueStock', 'BoutiqueSale', 'BoutiqueSaleItem', 'BoutiqueCreditPayment',
    'HardwareCategory', 'HardwareStock', 'HardwareSale', 'HardwareSaleItem', 'HardwareCreditPayment',
    'AuditLog'
]
