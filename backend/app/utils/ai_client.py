"""OpenAI-compatible AI client with graceful degradation.

Supports any provider that exposes an OpenAI-compatible chat completions API
(DeepSeek, OpenAI, OpenRouter, local vLLM, etc.).  Provider is selected
entirely through env vars — no vendor lock-in in code.

Usage::

    from app.utils.ai_client import ai_chat, ai_vision, is_ai_enabled, is_ocr_enabled

    # Text chat
    result = ai_chat("Summarise these metrics", system="You are a business analyst.")

    # Vision / OCR
    result = ai_vision(image_b64, "Extract fields from this document.")
"""

import base64
import logging
import os
import time
from functools import lru_cache

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Configuration helpers (read once, cached)
# ---------------------------------------------------------------------------

def _env(name, default=None):
    return (os.getenv(name) or '').strip() or default


@lru_cache(maxsize=1)
def _ai_config():
    return {
        'enabled': _env('AI_ENABLED', 'false').lower() in ('1', 'true', 'yes'),
        'api_key': _env('AI_API_KEY'),
        'base_url': _env('AI_BASE_URL', 'https://api.openai.com/v1'),
        'chat_model': _env('AI_CHAT_MODEL', 'gpt-4o-mini'),
        'vision_model': _env('AI_VISION_MODEL'),
        'timeout': int(_env('AI_TIMEOUT_SECONDS', '15')),
        'max_tokens': int(_env('AI_MAX_TOKENS', '1024')),
        'briefing_enabled': _env('AI_DAILY_BRIEFING_ENABLED', 'true').lower() in ('1', 'true', 'yes'),
        'chat_enabled': _env('AI_MANAGER_CHAT_ENABLED', 'true').lower() in ('1', 'true', 'yes'),
    }


@lru_cache(maxsize=1)
def _ocr_config():
    ai = _ai_config()
    return {
        'enabled': _env('OCR_ENABLED', 'false').lower() in ('1', 'true', 'yes'),
        'api_key': _env('OCR_API_KEY') or ai['api_key'],
        'base_url': _env('OCR_BASE_URL') or ai['base_url'],
        'model': _env('OCR_MODEL') or ai.get('vision_model'),
    }


# ---------------------------------------------------------------------------
# Public helpers
# ---------------------------------------------------------------------------

def is_ai_enabled():
    cfg = _ai_config()
    return cfg['enabled'] and bool(cfg['api_key'])


def is_briefing_ai_enabled():
    return is_ai_enabled() and _ai_config()['briefing_enabled']


def is_chat_enabled():
    return is_ai_enabled() and _ai_config()['chat_enabled']


def is_ocr_enabled():
    ocr = _ocr_config()
    return ocr['enabled'] and bool(ocr['api_key']) and bool(ocr['model'])


# ---------------------------------------------------------------------------
# Low-level HTTP call (uses requests, no openai SDK dependency)
# ---------------------------------------------------------------------------

def _post_chat(messages, *, api_key, base_url, model, max_tokens, timeout):
    """POST to an OpenAI-compatible /chat/completions endpoint."""
    import requests  # lazy import — only needed when AI is actually called

    url = f"{base_url.rstrip('/')}/chat/completions"
    headers = {
        'Authorization': f'Bearer {api_key}',
        'Content-Type': 'application/json',
    }
    payload = {
        'model': model,
        'messages': messages,
        'max_tokens': max_tokens,
        'temperature': 0.3,
    }

    t0 = time.monotonic()
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
        elapsed = time.monotonic() - t0
        if resp.status_code != 200:
            logger.warning(
                'AI provider returned %s in %.1fs (model=%s)',
                resp.status_code, elapsed, model,
            )
            return None
        data = resp.json()
        content = data['choices'][0]['message']['content']
        logger.debug('AI response in %.1fs (%d tokens)', elapsed, data.get('usage', {}).get('total_tokens', 0))
        return content
    except requests.RequestException as exc:
        elapsed = time.monotonic() - t0
        logger.warning('AI provider unreachable in %.1fs: %s', elapsed, exc.__class__.__name__)
        return None
    except (KeyError, IndexError, ValueError) as exc:
        logger.warning('AI response parse error: %s', exc)
        return None


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def ai_chat(prompt, *, system=None):
    """Send a text chat completion. Returns response string or None on failure."""
    if not is_ai_enabled():
        return None

    cfg = _ai_config()
    messages = []
    if system:
        messages.append({'role': 'system', 'content': system})
    messages.append({'role': 'user', 'content': prompt})

    return _post_chat(
        messages,
        api_key=cfg['api_key'],
        base_url=cfg['base_url'],
        model=cfg['chat_model'],
        max_tokens=cfg['max_tokens'],
        timeout=cfg['timeout'],
    )


def ai_chat_multi(messages, *, system=None):
    """Send a multi-turn conversation. messages is a list of {role, content} dicts."""
    if not is_ai_enabled():
        return None

    cfg = _ai_config()
    full_messages = []
    if system:
        full_messages.append({'role': 'system', 'content': system})
    full_messages.extend(messages)

    return _post_chat(
        full_messages,
        api_key=cfg['api_key'],
        base_url=cfg['base_url'],
        model=cfg['chat_model'],
        max_tokens=cfg['max_tokens'],
        timeout=cfg['timeout'],
    )


def ai_vision(image_bytes_or_b64, prompt, *, system=None, mime_type='image/jpeg'):
    """Send an image + text prompt for vision/OCR. Returns response string or None."""
    ocr = _ocr_config()
    if not ocr['enabled'] or not ocr['api_key']:
        return None

    ai = _ai_config()

    # Ensure base64 string
    if isinstance(image_bytes_or_b64, bytes):
        b64 = base64.b64encode(image_bytes_or_b64).decode('ascii')
    else:
        b64 = image_bytes_or_b64

    messages = []
    if system:
        messages.append({'role': 'system', 'content': system})
    messages.append({
        'role': 'user',
        'content': [
            {'type': 'text', 'text': prompt},
            {
                'type': 'image_url',
                'image_url': {'url': f'data:{mime_type};base64,{b64}'},
            },
        ],
    })

    return _post_chat(
        messages,
        api_key=ocr['api_key'],
        base_url=ocr['base_url'],
        model=ocr['model'],
        max_tokens=ai['max_tokens'],
        timeout=ai['timeout'],
    )
