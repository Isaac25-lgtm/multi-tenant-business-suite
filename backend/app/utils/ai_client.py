"""AI client with graceful degradation.

Text chat uses an OpenAI-compatible chat completions API (DeepSeek, OpenAI,
OpenRouter, local vLLM, etc.). OCR can use either an OpenAI-compatible vision
endpoint or Anthropic's native Messages API. Providers are selected entirely
through env vars, so the app can mix DeepSeek chat with Anthropic OCR.
"""

import base64
import logging
import os
import time
from functools import lru_cache

logger = logging.getLogger(__name__)


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
        'provider': _env('OCR_PROVIDER', 'openai_compatible').lower(),
        'api_key': _env('OCR_API_KEY') or ai['api_key'],
        'base_url': _env('OCR_BASE_URL') or ai['base_url'],
        'model': _env('OCR_MODEL') or ai.get('vision_model'),
        'daily_client_limit': int(_env('OCR_DAILY_CLIENT_LIMIT', '5')),
        'warning_client_number': int(_env('OCR_WARNING_CLIENT_NUMBER', '3')),
    }


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


def get_ocr_limits():
    ocr = _ocr_config()
    return {
        'daily_client_limit': max(1, ocr['daily_client_limit']),
        'warning_client_number': max(1, ocr['warning_client_number']),
        'provider': ocr['provider'],
    }


def _post_chat(messages, *, api_key, base_url, model, max_tokens, timeout):
    """POST to an OpenAI-compatible /chat/completions endpoint."""
    import requests

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
            logger.warning('AI provider returned %s in %.1fs (model=%s)', resp.status_code, elapsed, model)
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


def _anthropic_messages_url(base_url):
    root = (base_url or 'https://api.anthropic.com').rstrip('/')
    if root.endswith('/v1/messages'):
        return root
    if root.endswith('/v1'):
        return f'{root}/messages'
    return f'{root}/v1/messages'


def _post_anthropic_message(content_blocks, *, api_key, base_url, model, max_tokens, timeout, system=None):
    """POST to Anthropic's native Messages API."""
    import requests

    url = _anthropic_messages_url(base_url)
    headers = {
        'x-api-key': api_key,
        'anthropic-version': '2023-06-01',
        'Content-Type': 'application/json',
    }
    payload = {
        'model': model,
        'max_tokens': max_tokens,
        'messages': [{'role': 'user', 'content': content_blocks}],
    }
    if system:
        payload['system'] = system

    t0 = time.monotonic()
    try:
        resp = requests.post(url, json=payload, headers=headers, timeout=timeout)
        elapsed = time.monotonic() - t0
        if resp.status_code != 200:
            logger.warning(
                'Anthropic OCR provider returned %s in %.1fs (model=%s)',
                resp.status_code, elapsed, model,
            )
            return None

        data = resp.json()
        parts = data.get('content', [])
        text_parts = [part.get('text', '') for part in parts if part.get('type') == 'text']
        content = '\n'.join(part for part in text_parts if part).strip()
        if not content:
            logger.warning('Anthropic OCR response parse error: missing text block')
            return None

        logger.debug(
            'Anthropic OCR response in %.1fs (%d input tokens / %d output tokens)',
            elapsed,
            data.get('usage', {}).get('input_tokens', 0),
            data.get('usage', {}).get('output_tokens', 0),
        )
        return content
    except requests.RequestException as exc:
        elapsed = time.monotonic() - t0
        logger.warning('Anthropic OCR provider unreachable in %.1fs: %s', elapsed, exc.__class__.__name__)
        return None
    except (KeyError, IndexError, ValueError) as exc:
        logger.warning('Anthropic OCR response parse error: %s', exc)
        return None


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
    if not ocr['enabled'] or not ocr['api_key'] or not ocr['model']:
        return None

    ai = _ai_config()
    if isinstance(image_bytes_or_b64, bytes):
        b64 = base64.b64encode(image_bytes_or_b64).decode('ascii')
    else:
        b64 = image_bytes_or_b64

    if ocr['provider'] == 'anthropic':
        return _post_anthropic_message(
            [
                {
                    'type': 'image',
                    'source': {
                        'type': 'base64',
                        'media_type': mime_type,
                        'data': b64,
                    },
                },
                {'type': 'text', 'text': prompt},
            ],
            api_key=ocr['api_key'],
            base_url=ocr['base_url'],
            model=ocr['model'],
            max_tokens=ai['max_tokens'],
            timeout=ai['timeout'],
            system=system,
        )

    messages = []
    if system:
        messages.append({'role': 'system', 'content': system})
    messages.append({
        'role': 'user',
        'content': [
            {'type': 'text', 'text': prompt},
            {'type': 'image_url', 'image_url': {'url': f'data:{mime_type};base64,{b64}'}},
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


def ai_document(document_bytes_or_b64, prompt, *, system=None, mime_type='application/pdf'):
    """Send a document prompt for OCR-capable providers. Returns response string or None."""
    ocr = _ocr_config()
    if not ocr['enabled'] or not ocr['api_key'] or not ocr['model']:
        return None
    if ocr['provider'] != 'anthropic':
        return None

    ai = _ai_config()
    if isinstance(document_bytes_or_b64, bytes):
        b64 = base64.b64encode(document_bytes_or_b64).decode('ascii')
    else:
        b64 = document_bytes_or_b64

    return _post_anthropic_message(
        [
            {
                'type': 'document',
                'source': {
                    'type': 'base64',
                    'media_type': mime_type,
                    'data': b64,
                },
            },
            {'type': 'text', 'text': prompt},
        ],
        api_key=ocr['api_key'],
        base_url=ocr['base_url'],
        model=ocr['model'],
        max_tokens=ai['max_tokens'],
        timeout=ai['timeout'],
        system=system,
    )
