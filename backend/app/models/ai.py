"""Models for AI features: morning briefing, manager chat, OCR extractions."""

import json

from app.extensions import db
from app.utils.timezone import get_local_now


class DailyBriefing(db.Model):
    """Cached daily briefing data (deterministic metrics + optional AI narration)."""
    __tablename__ = 'daily_briefings'

    id = db.Column(db.Integer, primary_key=True)
    briefing_date = db.Column(db.Date, nullable=False)
    scope = db.Column(db.String(30), nullable=False)  # 'manager', 'boutique', 'hardware', 'finance'
    branch = db.Column(db.String(10))  # 'K', 'B', or None
    metrics_json = db.Column(db.Text, nullable=False)  # deterministic metrics as JSON
    ai_narrative = db.Column(db.Text)  # optional AI-generated summary
    created_at = db.Column(db.DateTime, default=get_local_now)

    __table_args__ = (
        db.UniqueConstraint('briefing_date', 'scope', 'branch', name='uq_briefing_date_scope_branch'),
    )


class BriefingDismissal(db.Model):
    """Tracks when a user dismissed their briefing for a given day."""
    __tablename__ = 'briefing_dismissals'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    briefing_date = db.Column(db.Date, nullable=False)
    dismissed_at = db.Column(db.DateTime, default=get_local_now)

    __table_args__ = (
        db.UniqueConstraint('user_id', 'briefing_date', name='uq_user_briefing_date'),
    )


class ChatMessage(db.Model):
    """Audit log for manager AI chat interactions."""
    __tablename__ = 'chat_messages'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    role = db.Column(db.String(20), nullable=False)  # 'user' or 'assistant'
    content = db.Column(db.Text, nullable=False)
    intent = db.Column(db.String(50))  # classified intent, e.g. 'overdue_loans'
    created_at = db.Column(db.DateTime, default=get_local_now)


class OcrExtraction(db.Model):
    """Stores OCR extraction results for user review before save."""
    __tablename__ = 'ocr_extractions'

    id = db.Column(db.Integer, primary_key=True)
    uploaded_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    original_filename = db.Column(db.String(255), nullable=False)
    file_path = db.Column(db.String(512), nullable=False)
    file_type = db.Column(db.String(20))  # 'pdf', 'jpg', etc.
    document_type = db.Column(db.String(50))  # 'national_id', 'receipt', 'collateral', 'general'
    raw_ocr_text = db.Column(db.Text)  # raw provider response
    extracted_fields_json = db.Column(db.Text)  # structured extraction as JSON
    corrected_fields_json = db.Column(db.Text)  # user-corrected final values
    status = db.Column(db.String(20), default='pending')  # 'pending', 'reviewed', 'confirmed', 'failed'
    reviewed_by = db.Column(db.Integer, db.ForeignKey('users.id'))
    reviewed_at = db.Column(db.DateTime)
    linked_entity = db.Column(db.String(50))  # 'customer', 'loan_client', 'loan_document'
    linked_entity_id = db.Column(db.Integer)
    created_at = db.Column(db.DateTime, default=get_local_now)
    updated_at = db.Column(db.DateTime, default=get_local_now, onupdate=get_local_now)

    @property
    def parsed_fields(self):
        source = self.corrected_fields_json or self.extracted_fields_json
        if not source:
            return {}
        try:
            return json.loads(source)
        except (TypeError, ValueError, json.JSONDecodeError):
            return {}

    @property
    def public_file_path(self):
        raw = str(self.file_path or '').replace('\\', '/')
        if not raw:
            return None
        marker = '/static/'
        if marker in raw:
            return raw.split(marker, 1)[1]
        if raw.startswith('static/'):
            return raw.split('static/', 1)[1]
        if raw.startswith('uploads/'):
            return raw
        return None
