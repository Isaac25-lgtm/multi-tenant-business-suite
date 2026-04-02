"""OCR extraction engine using vision-capable AI models.

Extracts structured fields from uploaded document images. For PDFs, the engine
tries plain-text extraction first and then falls back to rasterizing the first
page for AI vision OCR when a vision model is configured.
"""

import base64
import json
import logging
import os
import tempfile

logger = logging.getLogger(__name__)

MIME_TYPES = {
    'jpg': 'image/jpeg',
    'jpeg': 'image/jpeg',
    'png': 'image/png',
    'gif': 'image/gif',
    'webp': 'image/webp',
}

# Document type → extraction prompt
EXTRACTION_PROMPTS = {
    'national_id': (
        "Extract the following fields from this Ugandan National ID card image:\n"
        "- full_name\n- nin (National Identification Number)\n- date_of_birth\n"
        "- sex\n- nationality\n- district_of_birth\n- card_number\n"
        "Return ONLY a JSON object with these keys. Use null for fields you cannot read."
    ),
    'receipt': (
        "Extract the following fields from this receipt/payment document:\n"
        "- date\n- total_amount\n- payer_name\n- reference_number\n- items (list)\n"
        "Return ONLY a JSON object with these keys. Use null for fields you cannot read."
    ),
    'collateral': (
        "Extract any visible text and structured information from this collateral document. "
        "Look for:\n- document_title\n- owner_name\n- property_description\n"
        "- registration_number\n- date\n- issuing_authority\n"
        "Return ONLY a JSON object with these keys. Use null for fields you cannot read."
    ),
    'general': (
        "Extract all visible text and any structured information from this document. "
        "Return a JSON object with:\n- document_type (your best guess)\n"
        "- extracted_text (all visible text)\n- key_fields (a dict of any structured data you can identify)"
    ),
}

SYSTEM_PROMPT = (
    "You are a document OCR extraction system. You receive images of documents "
    "and extract structured data from them. Always respond with valid JSON only — "
    "no markdown, no explanation, no code fences. If a field is not readable, use null."
)


def extract_from_image(image_path, document_type='general'):
    """Run OCR/vision extraction on an image file.

    Returns:
        dict with keys:
            success (bool)
            raw_text (str or None) — raw AI response
            fields (dict) — parsed structured fields
            error (str or None)
    """
    from app.utils.ai_client import is_ocr_enabled, ai_vision

    if not is_ocr_enabled():
        return {
            'success': False,
            'raw_text': None,
            'fields': _empty_fields(document_type),
            'error': 'OCR provider not configured. Please enter fields manually.',
        }

    try:
        with open(image_path, 'rb') as f:
            image_bytes = f.read()
    except OSError as exc:
        logger.warning('Cannot read file for OCR: %s', exc)
        return {
            'success': False,
            'raw_text': None,
            'fields': _empty_fields(document_type),
            'error': 'Cannot read the uploaded file.',
        }

    prompt = EXTRACTION_PROMPTS.get(document_type, EXTRACTION_PROMPTS['general'])

    try:
        ext = os.path.splitext(image_path)[1].lower().lstrip('.')
        mime_type = MIME_TYPES.get(ext, 'image/jpeg')
        raw = ai_vision(image_bytes, prompt, system=SYSTEM_PROMPT, mime_type=mime_type)
    except Exception as exc:
        logger.warning('OCR extraction failed: %s', exc.__class__.__name__)
        return {
            'success': False,
            'raw_text': None,
            'fields': _empty_fields(document_type),
            'error': 'OCR provider returned an error. Please enter fields manually.',
        }

    if not raw:
        return {
            'success': False,
            'raw_text': None,
            'fields': _empty_fields(document_type),
            'error': 'OCR provider did not return a response. Please enter fields manually.',
        }

    # Parse JSON from response (strip any markdown fences)
    cleaned = raw.strip()
    if cleaned.startswith('```'):
        lines = cleaned.split('\n')
        cleaned = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:])

    try:
        fields = json.loads(cleaned)
    except json.JSONDecodeError:
        logger.debug('OCR returned non-JSON: %s', cleaned[:200])
        fields = {'extracted_text': cleaned}

    return {
        'success': True,
        'raw_text': raw,
        'fields': fields,
        'error': None,
    }


def extract_from_pdf(pdf_path, document_type='general'):
    """Extract text from a PDF.

    Strategy:
    1. Try machine-readable text extraction via ``pdftotext``.
    2. If that fails and OCR is configured, render the first page to PNG and
       send it through the vision OCR path.
    3. Fall back to manual entry if neither path is available.
    """
    from app.utils.ai_client import ai_document, is_ocr_enabled

    # For PDFs, try text extraction first.
    try:
        import subprocess
        # Try pdftotext if available (lightweight)
        result = subprocess.run(
            ['pdftotext', pdf_path, '-'],
            capture_output=True, text=True, timeout=10,
        )
        if result.returncode == 0 and result.stdout.strip():
            return {
                'success': True,
                'raw_text': result.stdout,
                'fields': {'extracted_text': result.stdout.strip()},
                'error': None,
            }
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        pass

    if is_ocr_enabled():
        try:
            with open(pdf_path, 'rb') as f:
                pdf_bytes = f.read()
            prompt = EXTRACTION_PROMPTS.get(document_type, EXTRACTION_PROMPTS['general'])
            raw = ai_document(pdf_bytes, prompt, system=SYSTEM_PROMPT, mime_type='application/pdf')
            if raw:
                cleaned = raw.strip()
                if cleaned.startswith('```'):
                    lines = cleaned.split('\n')
                    cleaned = '\n'.join(lines[1:-1] if lines[-1].strip() == '```' else lines[1:])
                try:
                    fields = json.loads(cleaned)
                except json.JSONDecodeError:
                    logger.debug('OCR returned non-JSON for PDF: %s', cleaned[:200])
                    fields = {'extracted_text': cleaned}
                return {
                    'success': True,
                    'raw_text': raw,
                    'fields': fields,
                    'error': None,
                }
        except OSError as exc:
            logger.warning('Cannot read PDF for OCR: %s', exc)

        rendered = _render_pdf_first_page(pdf_path)
        if rendered:
            try:
                return extract_from_image(rendered, document_type)
            finally:
                try:
                    os.remove(rendered)
                except OSError:
                    pass

    return {
        'success': False,
        'raw_text': None,
        'fields': _empty_fields(document_type),
        'error': 'PDF OCR is unavailable right now. Please enter fields manually.',
    }


def _render_pdf_first_page(pdf_path):
    """Render the first page of a PDF to a temporary PNG path.

    Requires ``pypdfium2``. If the library is missing or rendering fails,
    returns ``None`` so the caller can fall back gracefully.
    """
    try:
        import pypdfium2 as pdfium
    except ImportError:
        logger.warning('PDF OCR fallback unavailable: pypdfium2 not installed')
        return None

    try:
        pdf = pdfium.PdfDocument(pdf_path)
        if len(pdf) < 1:
            return None
        page = pdf[0]
        bitmap = page.render(scale=2.0)
        image = bitmap.to_pil()
        with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp:
            image.save(tmp.name, format='PNG')
            return tmp.name
    except Exception as exc:
        logger.warning('PDF OCR render failed: %s', exc.__class__.__name__)
        return None


def _empty_fields(document_type):
    """Return empty field templates for manual entry."""
    templates = {
        'national_id': {
            'full_name': '', 'nin': '', 'date_of_birth': '',
            'sex': '', 'nationality': '', 'district_of_birth': '',
        },
        'receipt': {
            'date': '', 'total_amount': '', 'payer_name': '',
            'reference_number': '', 'items': '',
        },
        'collateral': {
            'document_title': '', 'owner_name': '', 'property_description': '',
            'registration_number': '', 'date': '', 'issuing_authority': '',
        },
        'general': {
            'extracted_text': '',
        },
    }
    return templates.get(document_type, templates['general'])
