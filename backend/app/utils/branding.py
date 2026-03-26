from decimal import Decimal
from types import SimpleNamespace


DEFAULT_SITE_SETTINGS = {
    'company_name': 'Denove',
    'company_suffix': 'APS',
    'tagline': 'Fashion, Hardware & Finance',
    'announcement_text': 'Trusted products, practical finance, and dependable service across Uganda.',
    'hero_title': 'Fashion, hardware and financial freedom',
    'hero_description': (
        'Quality clothing, building materials, and accessible lending from one trusted local partner.'
    ),
    'contact_phone': '+256 788 066 808',
    'whatsapp_number': '256788066808',
    'contact_email': 'hello@denove.ug',
    'headquarters': 'Kapchorwa',
    'service_area': 'Uganda',
    'loan_min_amount': Decimal('200000'),
    'loan_max_amount': Decimal('5000000'),
    'loan_interest_rate': Decimal('10.00'),
    'loan_interest_rate_label': 'interest per month',
    'loan_repayment_note': 'Flexible weekly or monthly repayment',
    'loan_approval_hours': 48,
    'footer_description': (
        'Your one-stop partner for boutique shopping, hardware supplies, and business-friendly finance.'
    ),
    'logo_path': 'images/denove.jpg',
}

BUILTIN_LOGO_PATHS = {
    'images/denove-logo.svg',
    'images/denovo.png',
    'images/denove.jpg',
}


def get_site_settings():
    settings = None
    try:
        from app.models.website import WebsiteSettings

        settings = WebsiteSettings.query.first()
    except Exception:
        settings = None

    merged = DEFAULT_SITE_SETTINGS.copy()
    if settings:
        for key in merged:
            value = getattr(settings, key, None)
            if value not in (None, ''):
                merged[key] = value

    # Keep user-uploaded logos, but migrate the old built-in defaults to the new denove.jpg.
    if merged.get('logo_path') in BUILTIN_LOGO_PATHS:
        merged['logo_path'] = DEFAULT_SITE_SETTINGS['logo_path']

    return SimpleNamespace(**merged)


def get_company_display_name(settings=None):
    settings = settings or get_site_settings()
    company_name = (settings.company_name or '').strip()
    company_suffix = (settings.company_suffix or '').strip()
    return f'{company_name} {company_suffix}'.strip()
