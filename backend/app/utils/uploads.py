"""Shared file upload validation utility.

Validates both extension and file content before saving.
Images are verified with Pillow; PDFs are checked by header.
"""
import io
from PIL import Image
from werkzeug.utils import secure_filename as _secure_filename

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
ALLOWED_DOCUMENT_EXTENSIONS = {'pdf'}
ALLOWED_ALL_EXTENSIONS = ALLOWED_IMAGE_EXTENSIONS | ALLOWED_DOCUMENT_EXTENSIONS


def _has_allowed_ext(filename, allowed):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


def _get_ext(filename):
    if '.' in filename:
        return filename.rsplit('.', 1)[1].lower()
    return ''


def allowed_image(filename):
    """Check if file has an allowed image extension."""
    return _has_allowed_ext(filename, ALLOWED_IMAGE_EXTENSIONS)


def allowed_document(filename):
    """Check if file has an allowed document extension (PDF)."""
    return _has_allowed_ext(filename, ALLOWED_DOCUMENT_EXTENSIONS)


def allowed_file(filename):
    """Check if file has any allowed extension (images + documents)."""
    return _has_allowed_ext(filename, ALLOWED_ALL_EXTENSIONS)


def safe_filename(filename):
    """Wrapper around werkzeug's secure_filename."""
    return _secure_filename(filename)


def validate_and_save_image(file_storage, save_path):
    """Validate image content with Pillow, then save.

    Returns True on success, False if the file is not a valid image.
    Resets the file stream before saving so the original bytes are preserved.
    """
    try:
        file_storage.stream.seek(0)
        img = Image.open(file_storage.stream)
        img.verify()  # Checks for corruption / non-image data
    except Exception:
        return False
    file_storage.stream.seek(0)
    file_storage.save(save_path)
    return True


def validate_and_save_document(file_storage, save_path):
    """Validate document content by checking the file header, then save.

    Currently supports PDF (%PDF- header).
    Returns True on success, False if the file is not a valid document.
    """
    ext = _get_ext(file_storage.filename or '')
    file_storage.stream.seek(0)
    header = file_storage.stream.read(8)
    file_storage.stream.seek(0)

    if ext == 'pdf':
        if not header.startswith(b'%PDF-'):
            return False
        file_storage.save(save_path)
        return True

    return False


def validate_and_save(file_storage, save_path):
    """Validate and save any allowed file (image or document).

    Returns True on success, False if validation fails.
    """
    ext = _get_ext(file_storage.filename or '')
    if ext in ALLOWED_IMAGE_EXTENSIONS:
        return validate_and_save_image(file_storage, save_path)
    if ext in ALLOWED_DOCUMENT_EXTENSIONS:
        return validate_and_save_document(file_storage, save_path)
    return False
