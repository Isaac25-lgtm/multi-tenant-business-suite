"""AI module — morning briefing, manager chatbot, OCR extraction.

All routes require authentication. The chatbot is manager-only.
OCR and briefing are role-aware.
"""

import json
import logging
import os
from datetime import datetime, time, timedelta

from flask import (
    Blueprint, jsonify, render_template, request, session,
    flash, redirect, url_for, current_app,
)
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.ai import BriefingDismissal, ChatMessage, OcrExtraction
from app.modules.auth import manager_required, get_session_user, log_action
from app.utils.timezone import EAT_TIMEZONE, get_local_today, get_local_now
from app.utils.uploads import allowed_file, validate_and_save

logger = logging.getLogger(__name__)

ai_bp = Blueprint('ai', __name__)


def _normalize_client_reference(value):
    return ' '.join((value or '').strip().lower().split())


def _local_day_bounds(day=None):
    target_day = day or get_local_today()
    start = datetime.combine(target_day, time.min, tzinfo=EAT_TIMEZONE)
    end = start + timedelta(days=1)
    return start, end


def _get_today_ai_client_refs():
    start, end = _local_day_bounds()
    refs = set()
    rows = OcrExtraction.query.filter(
        OcrExtraction.used_ai.is_(True),
        OcrExtraction.created_at >= start,
        OcrExtraction.created_at < end,
    ).all()
    for row in rows:
        normalized = _normalize_client_reference(row.client_reference)
        if normalized:
            refs.add(normalized)
    return refs


def _get_ocr_quota_status(client_reference=None):
    from app.utils.ai_client import get_ocr_limits

    limits = get_ocr_limits()
    used_refs = _get_today_ai_client_refs()
    normalized = _normalize_client_reference(client_reference)
    is_new_client = bool(normalized) and normalized not in used_refs
    used_count = len(used_refs)
    next_new_client_number = used_count + (1 if is_new_client else 0)
    limit_reached_for_new_client = is_new_client and used_count >= limits['daily_client_limit']
    warning_active = (
        is_new_client
        and next_new_client_number >= limits['warning_client_number']
        and next_new_client_number <= limits['daily_client_limit']
    )
    return {
        'used_count': used_count,
        'limit': limits['daily_client_limit'],
        'warning_number': limits['warning_client_number'],
        'is_new_client': is_new_client,
        'limit_reached_for_new_client': limit_reached_for_new_client,
        'next_new_client_number': next_new_client_number,
        'provider': limits['provider'],
        'used_refs': sorted(used_refs),
    }


# ============================================================================
# Morning Briefing
# ============================================================================

@ai_bp.route('/briefing')
def briefing():
    """Show the morning briefing page (accessible by any authenticated user)."""
    user = get_session_user()
    if not user:
        return redirect(url_for('auth.login'))

    today = get_local_today()
    current_section = session.get('section') or user.role
    if current_section not in {'manager', 'boutique', 'hardware', 'finance'}:
        current_section = user.role
    scope = 'manager' if user.role == 'manager' else current_section
    branch = user.boutique_branch if scope == 'boutique' else None

    # Auto-dismiss only when the page is loaded directly (not inside the modal
    # iframe). The modal's close button calls /briefing/dismiss explicitly.
    # We rely on an explicit query flag first, and fall back to browser fetch
    # metadata headers where available.
    is_iframe = (
        request.args.get('embedded') == '1'
        or request.headers.get('Sec-Fetch-Dest') == 'iframe'
    )
    if not is_iframe:
        try:
            existing = BriefingDismissal.query.filter_by(
                user_id=user.id, briefing_date=today
            ).first()
            if not existing:
                db.session.add(BriefingDismissal(user_id=user.id, briefing_date=today))
                db.session.commit()
        except Exception:
            db.session.rollback()

    try:
        from app.utils.briefing_engine import get_or_create_briefing
        metrics, ai_narrative = get_or_create_briefing(scope, branch, today)
    except Exception as exc:
        logger.warning('Briefing generation failed: %s', exc.__class__.__name__)
        metrics = {}
        ai_narrative = None

    return render_template(
        'ai/briefing.html',
        metrics=metrics,
        ai_narrative=ai_narrative,
        scope=scope,
        branch=branch,
        briefing_date=today,
        user=user,
    )


@ai_bp.route('/briefing/dismiss', methods=['POST'])
def dismiss_briefing():
    """Record that the user has seen their briefing for today."""
    user = get_session_user()
    if not user:
        return jsonify({'error': 'unauthorized'}), 401

    today = get_local_today()
    existing = BriefingDismissal.query.filter_by(
        user_id=user.id, briefing_date=today
    ).first()
    if not existing:
        try:
            dismissal = BriefingDismissal(user_id=user.id, briefing_date=today)
            db.session.add(dismissal)
            db.session.commit()
        except Exception:
            db.session.rollback()

    return jsonify({'ok': True})


@ai_bp.route('/briefing/check')
def check_briefing():
    """Check if user should see the morning briefing (not yet dismissed today)."""
    user = get_session_user()
    if not user:
        return jsonify({'show': False})

    today = get_local_today()
    try:
        dismissed = BriefingDismissal.query.filter_by(
            user_id=user.id, briefing_date=today
        ).first()
        return jsonify({'show': not bool(dismissed), 'date': today.isoformat()})
    except Exception as exc:
        logger.warning('Briefing check unavailable: %s', exc.__class__.__name__)
        return jsonify({'show': False, 'date': today.isoformat()})


# ============================================================================
# Manager AI Chatbot
# ============================================================================

@ai_bp.route('/chat')
@manager_required
def chat_page():
    """Render the AI chatbot interface (manager only)."""
    from app.utils.ai_client import is_chat_enabled
    from app.utils.chat_engine import SUGGESTED_PROMPTS

    return render_template(
        'ai/chat.html',
        chat_enabled=is_chat_enabled(),
        suggested_prompts=SUGGESTED_PROMPTS,
    )


@ai_bp.route('/chat/send', methods=['POST'])
@manager_required
def chat_send():
    """Process a chat message and return structured + narrated response."""
    user = get_session_user()
    data = request.get_json(silent=True) or {}
    message = (data.get('message') or '').strip()

    if not message:
        return jsonify({'error': 'Empty message'}), 400
    if len(message) > 1000:
        return jsonify({'error': 'Message too long (max 1000 characters)'}), 400

    # Log the user's message
    try:
        user_msg = ChatMessage(user_id=user.id, role='user', content=message)
        db.session.add(user_msg)
        db.session.flush()
    except Exception:
        db.session.rollback()

    # Process through intent engine
    from app.utils.chat_engine import process_chat_message, classify_intent
    intent = classify_intent(message)

    try:
        result = process_chat_message(message)
    except Exception as exc:
        logger.warning('Chat processing failed: %s', exc.__class__.__name__)
        result = {
            'intent': 'error',
            'summary': 'Sorry, something went wrong processing your request.',
        }

    # Log the assistant response
    try:
        response_text = result.get('ai_narrative') or result.get('summary', '')
        assistant_msg = ChatMessage(
            user_id=user.id, role='assistant',
            content=response_text[:2000], intent=intent,
        )
        db.session.add(assistant_msg)
        db.session.commit()
    except Exception:
        db.session.rollback()

    return jsonify(result)


# ============================================================================
# OCR Extraction
# ============================================================================

@ai_bp.route('/ocr/upload', methods=['POST'])
def ocr_upload():
    """Upload a document for OCR extraction."""
    user = get_session_user()
    if not user:
        return jsonify({'error': 'unauthorized'}), 401

    if 'file' not in request.files:
        flash('No file selected.', 'error')
        return redirect(request.referrer or url_for('ai.ocr_page'))

    file = request.files['file']
    if not file or not file.filename:
        flash('No file selected.', 'error')
        return redirect(request.referrer or url_for('ai.ocr_page'))

    if not allowed_file(file.filename):
        flash('File type not allowed. Use PDF, JPG, PNG, GIF, or WebP.', 'error')
        return redirect(request.referrer or url_for('ai.ocr_page'))

    document_type = request.form.get('document_type', 'general')
    client_reference = (request.form.get('client_reference') or '').strip()
    if not client_reference:
        flash('Add a client reference so the daily OCR credit limit can be tracked.', 'error')
        return redirect(request.referrer or url_for('ai.ocr_page'))

    filename = secure_filename(file.filename)
    ext = filename.rsplit('.', 1)[-1].lower() if '.' in filename else ''

    # Save the file
    upload_dir = os.path.join(current_app.config['UPLOAD_FOLDER'], 'ocr')
    os.makedirs(upload_dir, exist_ok=True)
    save_name = f"ocr_{user.id}_{int(get_local_now().timestamp())}_{filename}"
    save_path = os.path.join(upload_dir, save_name)
    static_root = os.path.join(current_app.root_path, 'static')
    relative_path = os.path.relpath(save_path, static_root).replace('\\', '/')

    if not validate_and_save(file, save_path):
        flash('File validation failed.', 'error')
        return redirect(request.referrer or url_for('ai.ocr_page'))

    # Run OCR extraction
    from app.utils.ai_client import is_ocr_enabled
    from app.utils.ocr_engine import _empty_fields, extract_from_image, extract_from_pdf

    quota = _get_ocr_quota_status(client_reference)
    used_ai = is_ocr_enabled() and not quota['limit_reached_for_new_client']

    if used_ai:
        if ext == 'pdf':
            result = extract_from_pdf(save_path, document_type)
        else:
            result = extract_from_image(save_path, document_type)
        used_ai = bool(result.get('success'))
    else:
        result = {
            'success': False,
            'raw_text': None,
            'fields': _empty_fields(document_type),
            'error': (
                f"Today's AI OCR limit of {quota['limit']} client references has been reached. "
                'You can still upload and review documents manually.'
            ),
        }

    # Save extraction record
    extraction = OcrExtraction(
        uploaded_by=user.id,
        original_filename=filename,
        file_path=relative_path,
        file_type=ext,
        document_type=document_type,
        client_reference=client_reference,
        raw_ocr_text=result.get('raw_text'),
        extracted_fields_json=json.dumps(result.get('fields', {})),
        used_ai=used_ai,
        fallback_reason=None if used_ai else (
            'daily_limit'
            if quota['limit_reached_for_new_client']
            else 'provider_unavailable'
        ),
        status='pending',
    )
    db.session.add(extraction)
    db.session.commit()

    log_action(
        session.get('username', 'unknown'), session.get('section', 'ai'),
        'create', 'ocr_extraction', extraction.id,
        {
            'filename': filename,
            'document_type': document_type,
            'ocr_success': result.get('success'),
            'used_ai': used_ai,
            'client_reference': client_reference,
            'fallback_reason': extraction.fallback_reason,
        },
    )

    if quota['is_new_client'] and quota['next_new_client_number'] == quota['warning_number']:
        flash(
            f"This is AI OCR client {quota['next_new_client_number']} of {quota['limit']} for today. "
            'After the fifth unique client reference, uploads will switch to manual review to save credits.',
            'warning',
        )

    if result.get('error'):
        flash(result['error'], 'info')

    return redirect(url_for('ai.ocr_review', id=extraction.id))


@ai_bp.route('/ocr')
def ocr_page():
    """OCR upload page."""
    user = get_session_user()
    if not user:
        return redirect(url_for('auth.login'))

    from app.utils.ai_client import is_ocr_enabled

    recent = OcrExtraction.query.filter_by(
        uploaded_by=user.id
    ).order_by(OcrExtraction.created_at.desc()).limit(10).all()

    quota = _get_ocr_quota_status()
    return render_template(
        'ai/ocr_upload.html',
        ocr_enabled=is_ocr_enabled(),
        recent=recent,
        quota=quota,
    )


@ai_bp.route('/ocr/<int:id>/review')
def ocr_review(id):
    """Review and correct OCR extraction results."""
    user = get_session_user()
    if not user:
        return redirect(url_for('auth.login'))

    extraction = OcrExtraction.query.get_or_404(id)

    # Only the uploader or a manager can review
    if extraction.uploaded_by != user.id and user.role != 'manager':
        flash('You do not have access to this extraction.', 'error')
        return redirect(url_for('ai.ocr_page'))

    fields = extraction.parsed_fields

    return render_template(
        'ai/ocr_review.html',
        extraction=extraction,
        fields=fields,
    )


@ai_bp.route('/ocr/<int:id>/confirm', methods=['POST'])
def ocr_confirm(id):
    """Confirm corrected OCR fields."""
    user = get_session_user()
    if not user:
        return jsonify({'error': 'unauthorized'}), 401

    extraction = OcrExtraction.query.get_or_404(id)
    if extraction.uploaded_by != user.id and user.role != 'manager':
        flash('Access denied.', 'error')
        return redirect(url_for('ai.ocr_page'))

    # Collect corrected fields from the form
    corrected = {}
    for key in request.form:
        if key.startswith('field_'):
            field_name = key[6:]  # strip 'field_' prefix
            corrected[field_name] = request.form[key].strip()

    extraction.corrected_fields_json = json.dumps(corrected)
    extraction.status = 'confirmed'
    extraction.reviewed_by = user.id
    extraction.reviewed_at = get_local_now()

    client_reference = (request.form.get('client_reference') or '').strip()
    if client_reference:
        extraction.client_reference = client_reference

    # Optionally link to an entity
    link_entity = request.form.get('link_entity')
    link_id = request.form.get('link_entity_id', type=int)
    if link_entity and link_id:
        extraction.linked_entity = link_entity
        extraction.linked_entity_id = link_id

    db.session.commit()

    log_action(
        session.get('username', 'unknown'), session.get('section', 'ai'),
        'update', 'ocr_extraction', extraction.id,
        {'action': 'confirmed', 'fields': list(corrected.keys())},
    )

    flash('OCR extraction confirmed and saved.', 'success')
    return redirect(url_for('ai.ocr_page'))
