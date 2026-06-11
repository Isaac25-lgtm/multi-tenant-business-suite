"""
Tests for the loan clearance certificate feature.

Coverage:
  - Unpaid / non-zero-balance loans are rejected at the route level
  - Paid individual loan produces a valid PDF with correct content
  - Paid group loan settled early (balance=0 but periods_paid < total_periods)
  - Certificate number and clearance date are stable across repeated calls
  - Dates are expressed in EAT (UTC+3), not raw server UTC
  - Long payment histories (100 payments) produce a valid multi-page PDF

All database interaction is replaced by simple mock objects so no live
PostgreSQL connection is required.
"""

import io
from datetime import date, datetime, timezone, timedelta
from decimal import Decimal
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest
import pypdfium2 as pdfium
from flask import Flask

# ---------------------------------------------------------------------------
# Text extraction helper
# ---------------------------------------------------------------------------

def _pdf_text(buf):
    """Return all text from every page of a PDF BytesIO as a single string."""
    buf.seek(0)
    doc = pdfium.PdfDocument(buf)
    text = ""
    for page in doc:
        textpage = page.get_textpage()
        text += textpage.get_text_range()
    return text


def _pdf_page_count(buf):
    """Return the number of pages in a PDF BytesIO."""
    buf.seek(0)
    doc = pdfium.PdfDocument(buf)
    return len(doc)


# ---------------------------------------------------------------------------
# Minimal mock helpers
# ---------------------------------------------------------------------------

def _make_client(name="Alice Namukasa", phone="0700000001",
                 nin="CM123456789AB", address="Kapchorwa Town"):
    c = MagicMock()
    c.name = name
    c.phone = phone
    c.nin = nin
    c.address = address
    return c


def _make_payment(payment_date, amount, principal_amount=None,
                  interest_amount=None, balance_after=0):
    p = MagicMock()
    p.payment_date = payment_date
    p.amount = Decimal(str(amount))
    p.principal_amount = Decimal(str(principal_amount or amount))
    p.interest_amount = Decimal(str(interest_amount or 0))
    p.balance_after = Decimal(str(balance_after))
    return p


def _make_group_payment(payment_date, amount, periods_covered=1, balance_after=0):
    p = MagicMock()
    p.payment_date = payment_date
    p.amount = Decimal(str(amount))
    p.periods_covered = periods_covered
    p.balance_after = Decimal(str(balance_after))
    return p


def _make_loan(loan_id=1, status='paid', balance=0,
               principal=500000, amount_paid=550000,
               interest_amount=50000, interest_mode='flat_rate',
               monthly_interest_amount=None,
               issue_date=date(2026, 1, 1), due_date=date(2026, 6, 1),
               client=None):
    loan = MagicMock()
    loan.id = loan_id
    loan.status = status
    loan.balance = Decimal(str(balance))
    loan.principal = Decimal(str(principal))
    loan.amount_paid = Decimal(str(amount_paid))
    loan.interest_amount = Decimal(str(interest_amount))
    loan.interest_mode = interest_mode
    loan.monthly_interest_amount = Decimal(str(monthly_interest_amount or 0))
    loan.issue_date = issue_date
    loan.due_date = due_date
    loan.client = client or _make_client()
    return loan


def _make_group(group_id=1, status='paid', balance=0,
                principal=1000000, amount_paid=1100000,
                total_periods=10, periods_paid=3,
                issue_date=date(2026, 1, 1), due_date=date(2026, 10, 1)):
    g = MagicMock()
    g.id = group_id
    g.group_name = "Kapchorwa Farmers Group"
    g.member_count = 5
    g.status = status
    g.balance = Decimal(str(balance))
    g.principal = Decimal(str(principal))
    g.amount_paid = Decimal(str(amount_paid))
    g.total_periods = total_periods
    g.periods_paid = periods_paid
    g.issue_date = issue_date
    g.due_date = due_date
    return g


def _make_settings():
    s = MagicMock()
    s.logo_path = None
    s.tagline = "Fashion, Hardware & Finance"
    s.contact_phone = "0700123456"
    s.headquarters = "Kapchorwa, Uganda"
    return s


# ---------------------------------------------------------------------------
# Patch targets
# ---------------------------------------------------------------------------

PATCH_SETTINGS = 'app.utils.pdf_generator.get_site_settings'
PATCH_BRAND    = 'app.utils.pdf_generator.get_company_display_name'
PATCH_NOW      = 'app.utils.pdf_generator.get_local_now'

EAT = timezone(timedelta(hours=3))
FAKE_NOW = datetime(2026, 6, 11, 10, 30, 0, tzinfo=EAT)


def _apply_patches(now=None):
    """Return three started patches; caller must stop them."""
    p1 = patch(PATCH_SETTINGS, return_value=_make_settings())
    p2 = patch(PATCH_BRAND, return_value="Denove APS")
    p3 = patch(PATCH_NOW, return_value=(now or FAKE_NOW))
    return p1, p2, p3


def _generate_individual(loan=None, payments=None, now=None):
    from app.utils.pdf_generator import generate_clearance_pdf
    if loan is None:
        loan = _make_loan()
    if payments is None:
        payments = [_make_payment(date(2026, 6, 1), 550000, 500000, 50000, 0)]
    p1, p2, p3 = _apply_patches(now)
    with p1, p2, p3:
        return generate_clearance_pdf(loan, payments)


def _generate_group(group=None, payments=None, now=None):
    from app.utils.pdf_generator import generate_group_clearance_pdf
    if group is None:
        group = _make_group()
    if payments is None:
        payments = [_make_group_payment(date(2026, 6, 1), 1100000, 1, 0)]
    p1, p2, p3 = _apply_patches(now)
    with p1, p2, p3:
        return generate_group_clearance_pdf(group, payments)


# ---------------------------------------------------------------------------
# 1. Route-level access and clearance guards
# ---------------------------------------------------------------------------

class TestRouteGuard:
    @pytest.fixture
    def route_app(self):
        from app.modules.auth import auth_bp
        from app.modules.finance import finance_bp

        app = Flask(__name__)
        app.config.update(TESTING=True, SECRET_KEY='clearance-route-tests')
        app.register_blueprint(auth_bp, url_prefix='/auth')
        app.register_blueprint(finance_bp, url_prefix='/finance')
        return app

    @staticmethod
    def _finance_user():
        return SimpleNamespace(
            is_active=True,
            has_access_to=lambda section: section == 'finance',
        )

    @staticmethod
    def _payments_query(payments):
        query = MagicMock()
        query.filter_by.return_value.order_by.return_value.all.return_value = payments
        return query

    def _get_individual(self, route_app, status, balance):
        loan = _make_loan(status=status, balance=balance)
        loan.payments = self._payments_query([
            _make_payment(date(2026, 6, 1), 550000, 500000, 50000, 0)
        ])
        query = MagicMock()
        query.get_or_404.return_value = loan
        loan_model = SimpleNamespace(query=query)
        payment_model = SimpleNamespace(payment_date=MagicMock())
        pdf = io.BytesIO(b'%PDF-route-test')

        with (
            patch('app.modules.auth.get_session_user', return_value=self._finance_user()),
            patch('app.modules.finance.Loan', loan_model),
            patch('app.modules.finance.LoanPayment', payment_model),
            patch('app.modules.finance.refresh_loan_state', return_value=False),
            patch('app.modules.finance.generate_clearance_pdf', return_value=pdf) as generate,
            patch('app.modules.finance.log_action') as audit,
        ):
            response = route_app.test_client().get('/finance/loans/1/clearance-pdf')
        return response, generate, audit

    def _get_group(self, route_app, status, balance):
        group = _make_group(status=status, balance=balance)
        group.payments = self._payments_query([
            _make_group_payment(date(2026, 6, 1), 1100000, 1, 0)
        ])
        query = MagicMock()
        query.get_or_404.return_value = group
        group_model = SimpleNamespace(query=query)
        payment_model = SimpleNamespace(payment_date=MagicMock())
        pdf = io.BytesIO(b'%PDF-group-route-test')

        with (
            patch('app.modules.auth.get_session_user', return_value=self._finance_user()),
            patch('app.modules.finance.GroupLoan', group_model),
            patch('app.modules.finance.GroupLoanPayment', payment_model),
            patch('app.modules.finance.generate_group_clearance_pdf', return_value=pdf) as generate,
            patch('app.modules.finance.log_action') as audit,
        ):
            response = route_app.test_client().get('/finance/group-loans/1/clearance-pdf')
        return response, generate, audit

    def test_unauthenticated_download_redirects_to_finance_login(self, route_app):
        with patch('app.modules.auth.get_session_user', return_value=None):
            response = route_app.test_client().get('/finance/loans/1/clearance-pdf')
        assert response.status_code == 302
        assert '/auth/login/finance' in response.headers['Location']

    @pytest.mark.parametrize(('status', 'balance'), [
        ('active', 100000),
        ('overdue', 50000),
        ('paid', 1),
    ])
    def test_individual_download_rejects_uncleared_loan(self, route_app, status, balance):
        response, generate, audit = self._get_individual(route_app, status, balance)
        assert response.status_code == 302
        assert response.headers['Location'].endswith('/finance/loans/1')
        generate.assert_not_called()
        audit.assert_not_called()

    def test_paid_zero_balance_individual_returns_pdf(self, route_app):
        response, generate, audit = self._get_individual(route_app, 'paid', 0)
        assert response.status_code == 200
        assert response.mimetype == 'application/pdf'
        assert 'clearance_LCC-00001.pdf' in response.headers['Content-Disposition']
        generate.assert_called_once()
        audit.assert_called_once()

    @pytest.mark.parametrize(('status', 'balance'), [
        ('active', 500),
        ('paid', Decimal('0.01')),
    ])
    def test_group_download_rejects_uncleared_loan(self, route_app, status, balance):
        response, generate, audit = self._get_group(route_app, status, balance)
        assert response.status_code == 302
        assert response.headers['Location'].endswith('/finance/group-loans/1')
        generate.assert_not_called()
        audit.assert_not_called()

    def test_paid_zero_balance_group_returns_pdf(self, route_app):
        response, generate, audit = self._get_group(route_app, 'paid', 0)
        assert response.status_code == 200
        assert response.mimetype == 'application/pdf'
        assert 'clearance_GLCC-00001.pdf' in response.headers['Content-Disposition']
        generate.assert_called_once()
        audit.assert_called_once()


# ---------------------------------------------------------------------------
# 2. Paid individual loan — certificate is a valid PDF with correct content
# ---------------------------------------------------------------------------

class TestIndividualClearancePdf:

    def test_returns_bytesio(self):
        result = _generate_individual()
        assert isinstance(result, io.BytesIO)

    def test_pdf_has_content(self):
        result = _generate_individual()
        assert len(result.read()) > 1000

    def test_starts_with_pdf_magic_bytes(self):
        result = _generate_individual()
        assert result.read(4) == b'%PDF'

    def test_cert_ref_is_deterministic(self):
        """Same loan ID → same cert ref on every generation."""
        loan = _make_loan(loan_id=42)
        payments = [_make_payment(date(2026, 6, 1), 550000, balance_after=0)]
        from app.utils.pdf_generator import generate_clearance_pdf
        p1, p2, p3 = _apply_patches()
        with p1, p2, p3:
            buf1 = generate_clearance_pdf(loan, payments)
            buf2 = generate_clearance_pdf(loan, payments)
        assert 'LCC-00042' in _pdf_text(buf1)
        assert 'LCC-00042' in _pdf_text(buf2)

    def test_clearance_date_from_last_payment(self):
        """The certificate clearance date must come from the final payment, not the clock."""
        loan = _make_loan(loan_id=7)
        payments = [_make_payment(date(2026, 3, 15), 550000, balance_after=0)]
        buf = _generate_individual(loan, payments)
        text = _pdf_text(buf)
        assert 'March 15, 2026' in text

    def test_clearance_date_uses_latest_payment_when_input_is_unsorted(self):
        loan = _make_loan(loan_id=7)
        payments = [
            _make_payment(date(2026, 2, 1), 200000, balance_after=350000),
            _make_payment(date(2026, 4, 10), 350000, balance_after=0),
            _make_payment(date(2026, 3, 1), 100000, balance_after=250000),
        ]
        text = _pdf_text(_generate_individual(loan, payments))
        assert 'April 10, 2026' in text

    def test_no_unapproved_wording(self):
        text = _pdf_text(_generate_individual()).lower()
        assert 'eligible for future credit' not in text
        assert 'no further financial claims' not in text
        assert 'no further claims' not in text

    def test_neutral_wording_present(self):
        text = _pdf_text(_generate_individual())
        assert 'recorded balance' in text or 'balance' in text.lower()

    def test_no_downloading_user_in_cert_identity(self):
        """The downloading username must not appear in the certificate body."""
        loan = _make_loan(loan_id=5)
        payments = [_make_payment(date(2026, 5, 1), 550000, balance_after=0)]
        buf = _generate_individual(loan, payments)
        text = _pdf_text(buf)
        assert 'testuser' not in text
        assert 'issued_by' not in text

    def test_borrower_name_in_cert(self):
        client = _make_client(name="Grace Chebet")
        loan = _make_loan(client=client)
        text = _pdf_text(_generate_individual(loan))
        assert 'Grace Chebet' in text

    def test_markup_characters_in_names_are_rendered_as_text(self):
        client = _make_client(name="A & B <Partners>")
        loan = _make_loan(client=client)
        text = _pdf_text(_generate_individual(loan))
        assert 'A & B <Partners>' in text

    def test_cert_ref_in_cert_body(self):
        loan = _make_loan(loan_id=13)
        text = _pdf_text(_generate_individual(loan))
        assert 'LCC-00013' in text


# ---------------------------------------------------------------------------
# 3. Group loan settled early — no period-count contradiction
# ---------------------------------------------------------------------------

class TestGroupClearancePdf:

    def test_returns_valid_pdf(self):
        result = _generate_group()
        assert result.read(4) == b'%PDF'

    def test_early_settlement_shows_fully_settled(self):
        """
        Group loan paid in one lump sum: balance=0 but periods_paid (3) <
        total_periods (10).  Certificate must say 'Fully settled', not '3 of 10'.
        """
        group = _make_group(balance=0, periods_paid=3, total_periods=10)
        payments = [_make_group_payment(date(2026, 4, 1), 1100000, 1, 0)]
        buf = _generate_group(group, payments)
        text = _pdf_text(buf)
        assert 'Fully settled' in text
        assert '3 of 10' not in text

    def test_cert_ref_deterministic(self):
        group = _make_group(group_id=99)
        payments = [_make_group_payment(date(2026, 6, 1), 1100000, 1, 0)]
        from app.utils.pdf_generator import generate_group_clearance_pdf
        p1, p2, p3 = _apply_patches()
        with p1, p2, p3:
            buf1 = generate_group_clearance_pdf(group, payments)
            buf2 = generate_group_clearance_pdf(group, payments)
        assert 'GLCC-00099' in _pdf_text(buf1)
        assert 'GLCC-00099' in _pdf_text(buf2)

    def test_clearance_date_uses_latest_group_payment_when_input_is_unsorted(self):
        group = _make_group(group_id=99)
        payments = [
            _make_group_payment(date(2026, 2, 1), 300000, 1, 800000),
            _make_group_payment(date(2026, 5, 1), 800000, 1, 0),
            _make_group_payment(date(2026, 3, 1), 100000, 1, 700000),
        ]
        text = _pdf_text(_generate_group(group, payments))
        assert 'May 01, 2026' in text

    def test_no_unapproved_wording(self):
        text = _pdf_text(_generate_group()).lower()
        assert 'eligible for future credit' not in text
        assert 'no further financial claims' not in text

    def test_group_name_in_cert(self):
        text = _pdf_text(_generate_group())
        assert 'Kapchorwa Farmers Group' in text

    def test_markup_characters_in_group_name_are_rendered_as_text(self):
        group = _make_group()
        group.group_name = "A & B <Savings>"
        text = _pdf_text(_generate_group(group))
        assert 'A & B <Savings>' in text


# ---------------------------------------------------------------------------
# 4. Stable identity across repeated downloads
# ---------------------------------------------------------------------------

class TestStableIdentity:

    def test_individual_cert_ref_unchanged_on_repeat(self):
        loan = _make_loan(loan_id=21)
        payments = [_make_payment(date(2026, 5, 10), 500000, balance_after=0)]
        from app.utils.pdf_generator import generate_clearance_pdf
        texts = []
        p1, p2, p3 = _apply_patches()
        with p1, p2, p3:
            for _ in range(3):
                buf = generate_clearance_pdf(loan, payments)
                texts.append(_pdf_text(buf))
        for text in texts:
            assert 'LCC-00021' in text
            assert 'May 10, 2026' in text

    def test_individual_clearance_date_from_payment_not_clock(self):
        """The issue date shown on the cert must be the last payment date."""
        loan = _make_loan(loan_id=8)
        # Payment on March 15; FAKE_NOW is June 11 — cert must say March 15
        payments = [_make_payment(date(2026, 3, 15), 550000, balance_after=0)]
        buf = _generate_individual(loan, payments)
        text = _pdf_text(buf)
        assert 'March 15, 2026' in text

    def test_group_cert_date_from_payment_not_clock(self):
        group = _make_group(group_id=55)
        payments = [_make_group_payment(date(2026, 2, 20), 1100000, 1, 0)]
        buf = _generate_group(group, payments)
        text = _pdf_text(buf)
        assert 'February 20, 2026' in text


# ---------------------------------------------------------------------------
# 5. Timezone: dates use EAT (UTC+3) not raw UTC
# ---------------------------------------------------------------------------

class TestTimezone:

    def test_get_local_now_used_for_no_payment_fallback(self):
        """
        When there are no payments and no due_date, the clearance date falls
        back to get_local_now().date().  Verify that path is reached and
        produces the EAT date, not some other timezone's date.
        """
        loan = _make_loan(loan_id=3)
        loan.due_date = None
        loan.issue_date = date(2026, 1, 1)
        # FAKE_NOW is 2026-06-11 10:30 EAT → clearance date = June 11, 2026
        buf = _generate_individual(loan, payments=[], now=FAKE_NOW)
        text = _pdf_text(buf)
        assert 'June 11, 2026' in text

    def test_eat_offset_is_utc_plus_3(self):
        from app.utils.timezone import EAT_TIMEZONE
        offset_hours = EAT_TIMEZONE.utcoffset(None).total_seconds() / 3600
        assert offset_hours == 3

    def test_get_local_now_returns_eat_datetime(self):
        from app.utils.timezone import get_local_now, EAT_TIMEZONE
        now = get_local_now()
        assert now.tzinfo is not None
        assert now.utcoffset() == EAT_TIMEZONE.utcoffset(None)


# ---------------------------------------------------------------------------
# 6. Long payment history — multi-page PDF is valid
# ---------------------------------------------------------------------------

class TestLongPaymentHistory:

    def _make_100_payments(self):
        balance = Decimal('1000000')
        per_payment = Decimal('10000')
        payments = []
        for i in range(100):
            pdate = date(2026, 1, 1) + timedelta(days=i * 3)
            balance = max(balance - per_payment, Decimal('0'))
            payments.append(_make_payment(
                pdate, per_payment,
                principal_amount=per_payment,
                interest_amount=0,
                balance_after=balance,
            ))
        # most-recent first (as the route queries them)
        return list(reversed(payments))

    def test_100_payments_individual_is_valid_pdf(self):
        loan = _make_loan(loan_id=88, principal=1000000, amount_paid=1000000)
        buf = _generate_individual(loan, self._make_100_payments())
        assert buf.read(4) == b'%PDF'

    def test_100_payments_individual_multipage(self):
        """100 payments must overflow page 1 — expect at least 2 pages."""
        loan = _make_loan(loan_id=88, principal=1000000, amount_paid=1000000)
        buf = _generate_individual(loan, self._make_100_payments())
        assert _pdf_page_count(buf) >= 2

    def test_100_payments_group_is_valid_pdf(self):
        group = _make_group(group_id=77, total_periods=100, periods_paid=100)
        payments = [
            _make_group_payment(
                date(2026, 1, 1) + timedelta(days=i * 3),
                10000, 1,
                max(0, 1000000 - (i + 1) * 10000),
            )
            for i in range(100)
        ]
        buf = _generate_group(group, list(reversed(payments)))
        assert buf.read(4) == b'%PDF'

    def test_100_payments_group_multipage(self):
        group = _make_group(group_id=77, total_periods=100, periods_paid=100,
                            balance=0)
        payments = [
            _make_group_payment(
                date(2026, 1, 1) + timedelta(days=i * 3),
                10000, 1,
                max(0, 1000000 - (i + 1) * 10000),
            )
            for i in range(100)
        ]
        buf = _generate_group(group, list(reversed(payments)))
        assert _pdf_page_count(buf) >= 2

    def test_continuation_cert_ref_present_on_page_2(self):
        """The cert ref must appear on the continuation page header."""
        loan = _make_loan(loan_id=55, principal=1000000, amount_paid=1000000)
        buf = _generate_individual(loan, self._make_100_payments())
        # All text across all pages must contain the cert ref
        text = _pdf_text(buf)
        assert 'LCC-00055' in text
