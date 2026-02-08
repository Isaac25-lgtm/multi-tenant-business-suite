"""
Website Management Models

These models support the public e-commerce storefront and manager control plane.
They capture demand signals (loan inquiries, order requests) and control public visibility.

CRITICAL: These tables store website-related data only.
They do NOT replace or duplicate core business tables.
"""
from datetime import datetime
from app.extensions import db


class WebsiteLoanInquiry(db.Model):
    """
    Captures public loan interest from website visitors.
    NOT a loan record - conversion happens only via manager action.
    """
    __tablename__ = 'website_loan_inquiries'

    id = db.Column(db.Integer, primary_key=True)
    
    # Applicant Information
    full_name = db.Column(db.String(200), nullable=False)
    phone = db.Column(db.String(50), nullable=False)
    email = db.Column(db.String(200), nullable=False)
    
    # Loan Request Details
    requested_amount = db.Column(db.String(100), nullable=False)  # Stored as text range
    loan_type = db.Column(db.String(50), nullable=False)  # 'individual' or 'group'
    message = db.Column(db.Text, nullable=True)
    
    # Status Workflow
    status = db.Column(db.String(20), default='new')  # new, reviewed, approved, rejected
    
    # Timestamps
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Manager Review
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reviewed_at = db.Column(db.DateTime, nullable=True)
    notes = db.Column(db.Text, nullable=True)  # Manager notes
    
    # Soft delete
    is_active = db.Column(db.Boolean, default=True)
    
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])
    
    def to_dict(self):
        return {
            'id': self.id,
            'full_name': self.full_name,
            'phone': self.phone,
            'email': self.email,
            'requested_amount': self.requested_amount,
            'loan_type': self.loan_type,
            'message': self.message,
            'status': self.status,
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'reviewed_by': self.reviewer.full_name if self.reviewer else None,
            'reviewed_at': self.reviewed_at.isoformat() if self.reviewed_at else None,
            'notes': self.notes
        }


class WebsiteOrderRequest(db.Model):
    """
    Captures cart/checkout intent from website visitors.
    NOT a sale - inventory is unaffected until staff confirmation.
    """
    __tablename__ = 'website_order_requests'

    id = db.Column(db.Integer, primary_key=True)
    
    # Customer Information
    customer_name = db.Column(db.String(200), nullable=False)
    customer_phone = db.Column(db.String(50), nullable=False)
    customer_email = db.Column(db.String(200), nullable=True)
    
    # Order Details
    items = db.Column(db.JSON, nullable=False)  # List of {product_id, product_type, name, quantity, price}
    preferred_branch = db.Column(db.String(50), nullable=True)  # 'kapchorwa', 'mbale', or null
    source = db.Column(db.String(20), default='website')
    
    # Status Workflow
    status = db.Column(db.String(20), default='new')  # new, contacted, fulfilled, cancelled
    
    # Timestamps
    submitted_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    fulfilled_at = db.Column(db.DateTime, nullable=True)
    
    # Manager/Staff Assignment
    assigned_to = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    notes = db.Column(db.Text, nullable=True)
    
    # Soft delete
    is_active = db.Column(db.Boolean, default=True)
    
    assignee = db.relationship('User', foreign_keys=[assigned_to])
    reviewer = db.relationship('User', foreign_keys=[reviewed_by])
    
    def to_dict(self):
        return {
            'id': self.id,
            'customer_name': self.customer_name,
            'customer_phone': self.customer_phone,
            'customer_email': self.customer_email,
            'items': self.items,
            'preferred_branch': self.preferred_branch,
            'status': self.status,
            'submitted_at': self.submitted_at.isoformat() if self.submitted_at else None,
            'assigned_to': self.assignee.full_name if self.assignee else None,
            'notes': self.notes
        }
    
    @property
    def total_amount(self):
        """Calculate total from items."""
        if not self.items:
            return 0
        return sum(item.get('price', 0) * item.get('quantity', 1) for item in self.items)
    
    @property
    def item_count(self):
        """Count total items."""
        if not self.items:
            return 0
        return sum(item.get('quantity', 1) for item in self.items)


class PublishedProduct(db.Model):
    """
    Controls public visibility of inventory items.
    Acts as the ONLY source of truth for what appears on the public website.
    
    Links to internal inventory but does NOT duplicate it.
    """
    __tablename__ = 'published_products'

    id = db.Column(db.Integer, primary_key=True)
    
    # Link to internal inventory
    product_type = db.Column(db.String(20), nullable=False)  # 'boutique' or 'hardware'
    product_id = db.Column(db.Integer, nullable=False)  # FK to BoutiqueStock or HardwareStock
    
    # Public Display Settings
    is_published = db.Column(db.Boolean, default=False)
    is_featured = db.Column(db.Boolean, default=False)
    display_order = db.Column(db.Integer, default=0)
    
    # Price Override (optional - if null, uses inventory price)
    public_price = db.Column(db.Numeric(12, 2), nullable=True)
    
    # Timestamps
    published_at = db.Column(db.DateTime, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Manager Control
    published_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Soft delete
    is_active = db.Column(db.Boolean, default=True)
    
    publisher = db.relationship('User', foreign_keys=[published_by])
    
    # Ensure unique product per type
    __table_args__ = (
        db.UniqueConstraint('product_type', 'product_id', name='unique_published_product'),
    )
    
    def get_inventory_item(self):
        """Retrieve the linked inventory item."""
        if self.product_type == 'boutique':
            from app.models.boutique import BoutiqueStock
            return BoutiqueStock.query.get(self.product_id)
        elif self.product_type == 'hardware':
            from app.models.hardware import HardwareStock
            return HardwareStock.query.get(self.product_id)
        return None
    
    def to_public_dict(self):
        """Return only public-safe fields for storefront."""
        item = self.get_inventory_item()
        if not item:
            return None
        
        # Use override price or inventory min_selling_price
        price = float(self.public_price) if self.public_price else float(item.min_selling_price)
        
        # Determine availability text (never expose actual quantity)
        if item.quantity <= 0:
            availability = 'Out of Stock'
        elif item.quantity <= (item.low_stock_threshold or 5):
            availability = 'Limited Stock'
        else:
            availability = 'In Stock'
        
        return {
            'id': self.id,
            'product_type': self.product_type,
            'product_id': self.product_id,
            'name': item.item_name,
            'category': item.category.name if item.category else 'Uncategorized',
            'price': price,
            'availability': availability,
            'in_stock': item.quantity > 0,
            'unit': item.unit,
            'image_url': getattr(item, 'image_url', None),
            'is_featured': self.is_featured
        }


class WebsiteImage(db.Model):
    """
    Centralized control of all public website images.
    Manages banners, product images, and category images.
    """
    __tablename__ = 'website_images'

    id = db.Column(db.Integer, primary_key=True)
    
    # Image Details
    image_type = db.Column(db.String(30), nullable=False)  # 'banner', 'product', 'category'
    file_path = db.Column(db.String(500), nullable=False)
    alt_text = db.Column(db.String(200), nullable=True)
    
    # Display Settings
    is_active = db.Column(db.Boolean, default=True)
    display_order = db.Column(db.Integer, default=0)
    
    # Optional Link
    link_url = db.Column(db.String(500), nullable=True)
    linked_product_id = db.Column(db.Integer, db.ForeignKey('published_products.id'), nullable=True)
    
    # Timestamps
    uploaded_at = db.Column(db.DateTime, default=datetime.utcnow)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Manager Control
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    uploader = db.relationship('User', foreign_keys=[uploaded_by])
    linked_product = db.relationship('PublishedProduct', foreign_keys=[linked_product_id])
    
    def to_dict(self):
        return {
            'id': self.id,
            'image_type': self.image_type,
            'file_path': self.file_path,
            'alt_text': self.alt_text,
            'is_active': self.is_active,
            'display_order': self.display_order,
            'link_url': self.link_url,
            'uploaded_at': self.uploaded_at.isoformat() if self.uploaded_at else None
        }
