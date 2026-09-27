from app.models.user import User, Role
from app.models.customer import Customer, Dealer
from app.models.product import Product, ProductModel, WarrantyPolicy
from app.models.warranty import ProductRegistration, Invoice, Warranty
from app.models.claim import Claim, ClaimDocument, ClaimStatusHistory
from app.models.service import (ServiceCenter, Technician, ServiceAssignment,
                                 Inspection, Repair, RepairPart,
                                 ReplacementRecord, Refund)
from app.models.support import Notification, Feedback, Complaint, AuditLog

__all__ = [
    'User', 'Role',
    'Customer', 'Dealer',
    'Product', 'ProductModel', 'WarrantyPolicy',
    'ProductRegistration', 'Invoice', 'Warranty',
    'Claim', 'ClaimDocument', 'ClaimStatusHistory',
    'ServiceCenter', 'Technician', 'ServiceAssignment',
    'Inspection', 'Repair', 'RepairPart',
    'ReplacementRecord', 'Refund',
    'Notification', 'Feedback', 'Complaint', 'AuditLog',
]
