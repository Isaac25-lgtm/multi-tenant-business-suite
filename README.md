<p align="center">
  <img src="backend/app/static/images/norongir-logo.png" alt="NoRongir Investments Limited" width="120" />
</p>

<h1 align="center">NoRongir Investments Limited</h1>

<p align="center">
  <strong>All-in-one business management suite for retail and microfinance operations</strong>
</p>

<p align="center">
  <a href="https://denove-aps.onrender.com">Live Demo</a> · <a href="docs/USER_GUIDE.md">User Guide</a> · <a href="docs/RENDER_DEPLOY.md">Deployment Guide</a>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11-blue?logo=python&logoColor=white" alt="Python 3.11" />
  <img src="https://img.shields.io/badge/Flask-3.0-000?logo=flask" alt="Flask 3.0" />
  <img src="https://img.shields.io/badge/PostgreSQL-16-336791?logo=postgresql&logoColor=white" alt="PostgreSQL" />
  <img src="https://img.shields.io/badge/deploy-Render-46E3B7?logo=render" alt="Render" />
  <img src="https://img.shields.io/badge/license-MIT-green" alt="License" />
</p>

---

This is a full-stack Flask application built for a multi-section retail and lending operation in Uganda. It unifies **boutique (fashion) sales**, **hardware sales**, **equipment hire**, **customer management**, **loan administration**, and a **public-facing storefront** into a single deployable platform with role-based access control.

## Key Features

| Module | Highlights |
|--------|-----------|
| **Point of Sale** | Multi-line item sales, full & credit payment modes, branded PDF receipts, day-over-day revenue tracking |
| **Inventory** | Multi-branch stock management, low-stock alerts, cost/selling price controls, product images |
| **Equipment Hire** | Deposit & daily rate tracking, return condition logging, hire payment history |
| **Microfinance** | Individual & group loans, flexible interest models, payment schedules, PDF loan agreements, collateral document uploads |
| **Customer Registry** | Shared across all sections, sensitive data encrypted at rest, business-type scoping |
| **Public Storefront** | Product showcase, featured items, loan inquiry & order submissions |
| **Website CMS** | Publish/unpublish products, manage banners & branding, inquiry inbox with one-click conversion to real loans |
| **Manager Dashboard** | Sales, cash received, gross and net profit, interest earned — each compared like-for-like with yesterday; refreshes itself every minute |
| **Manager Analytics** | Retail, finance-portfolio and inventory drill-down pages with shared date filters (today, 7 days, this/last month, custom) |
| **Loan Accounting** | One calculation service for every balance: monthly interest stops at settlement, payment reversals, approved discounts/waivers/write-offs with an audit trail |
| **Expenses** | Operating-expense ledger by category and business unit, feeding a real net-profit figure |
| **Morning Briefing** | Role-aware daily welcome with yesterday's metrics, attention flags, and optional AI narration |
| **Document OCR** | Upload documents for AI-powered text extraction with user review before save; requires a vision-capable model/provider |

## Tech Stack

- **Backend:** Flask · SQLAlchemy · Alembic
- **Database:** PostgreSQL
- **AI:** Dual-provider support — DeepSeek/OpenAI for briefing narration, Anthropic for OCR — optional, degrades gracefully
- **Security:** Encrypted PII · CSRF protection · rate limiting · comprehensive audit trail
- **Deployment:** Render · Gunicorn

## Roles & Access Control

| Role | Access |
|------|--------|
| **Manager** | Full access — all sections, user management, audit trail, website CMS |
| **Boutique** | Boutique inventory & sales, customers (if enabled) |
| **Hardware** | Hardware inventory & sales, customers (if enabled) |
| **Finance** | Loan administration, customers (if enabled) |

## Security

- Password hashing with industry-standard algorithms
- Sensitive personal data encrypted at rest
- CSRF protection on all state-changing operations
- Rate limiting on authentication and public endpoints
- Comprehensive audit trail on all operations
- Secure session management
- File upload validation and size restrictions
- Soft deletes for data integrity

## AI Features (Optional)

Two AI-powered tools are built in. All degrade gracefully — the app works fully without any AI provider configured.

| Feature | Who can use it | What it does |
|---------|---------------|--------------|
| **Morning Briefing** | All staff | Role-aware daily summary with yesterday's metrics, attention flags, and low-stock alerts. Appears as a banner on first login of the day. Managers see the full business overview; section staff see scoped data for their role. |
| **Document OCR** | All staff | Upload ID cards, receipts, collateral docs, or scanned PDFs at `/ai/ocr`. A vision-capable model extracts fields into an editable review form. Staff correct any mistakes before confirming. Daily usage is capped per client to control costs. |

### Provider setup

The app supports a **dual-provider** configuration — one provider for text (briefing narration) and a separate provider for vision/OCR. This lets you pair a cost-effective chat model with a high-quality vision model.

**Briefing narration** (OpenAI-compatible — DeepSeek, OpenAI, etc.):

```
AI_ENABLED=true
AI_API_KEY=<your-deepseek-or-openai-key>
AI_BASE_URL=https://api.deepseek.com/v1
AI_CHAT_MODEL=deepseek-chat
```

**Document OCR** (Anthropic recommended for vision quality):

```
OCR_ENABLED=true
OCR_PROVIDER=anthropic
OCR_API_KEY=<your-anthropic-key>
OCR_BASE_URL=https://api.anthropic.com
OCR_MODEL=claude-haiku-4-5
OCR_DAILY_CLIENT_LIMIT=5
OCR_WARNING_CLIENT_NUMBER=3
```

OCR can also use any OpenAI-compatible vision endpoint — set `OCR_PROVIDER=openai_compatible` and point `OCR_BASE_URL` / `OCR_MODEL` at your provider.

See `backend/.env.example` for the full list of configuration variables.

## Local Development Setup

**PostgreSQL is required** — SQLite is not supported.

```bash
# 1. Install PostgreSQL (if not already) and create the database
createdb -U postgres denove_aps

# 2. Set up the backend
cd backend
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -r requirements.txt

# 3. Configure environment
cp .env.example .env
# Edit .env — set your PostgreSQL credentials (PGUSER, PGPASSWORD, PGDATABASE)

# 4. Run database migrations
flask --app run:app db upgrade

# 5. Verify schema
flask --app run:app db-doctor

# 6. Create your admin account
flask --app run:app create-admin

# 7. Start the app
python run.py
# Open http://localhost:5000
```

If you have data in an old local SQLite database, you can migrate it:

```bash
python migrate_sqlite_to_pg.py             # auto-detects instance/denove.db
python migrate_sqlite_to_pg.py path/to.db  # explicit path
```

No local PostgreSQL? `docker compose up -d` at the repository root starts one on port 5433
(see `docker-compose.yml` for the matching `DATABASE_URL`).

## Tests

```bash
cd backend
pip install -r requirements-dev.txt
python -m pytest -q                      # unit tests; database tests are skipped

# Database integration tests need a dedicated, disposable database (it is wiped):
export TEST_DATABASE_URL=postgresql://postgres:<password>@localhost:5432/denove_aps_test
python -m pytest -q
ruff check .                             # lint
```

GitHub Actions runs the migrations, lint and the full suite against PostgreSQL on every push.

## Styling

The staff app uses a compiled Tailwind v3 stylesheet (`app/static/css/tailwind.css`) instead of the
Tailwind CDN script. After changing classes in templates, rebuild it with the
[Tailwind standalone CLI](https://github.com/tailwindlabs/tailwindcss/releases/tag/v3.4.19) (no Node.js needed):

```bash
cd backend
tailwindcss -c tailwind.config.js -i app/static/css/src/tailwind.css -o app/static/css/tailwind.css --minify
```

## Operations commands

Run from `backend/` with `python -m flask --app run:app <command>`:

| Command | Purpose |
|---|---|
| `finance-audit [--csv file]` | Read-only report of every loan with review flags (reopened after settlement, flat-rate loans on monthly terms, legacy payment splits, interest overpaid) |
| `finance-backfill-settlement [--apply]` | Stops interest on loans that were cleared but later reopened by the old accrual bug; dry run unless `--apply` |
| `refresh-loans` | Recalculates every open loan; safe to run repeatedly (optional daily job) |
| `pii-reencrypt [--apply]` | Re-encrypts stored ID numbers after setting `PII_ENCRYPTION_KEY` |
| `db-doctor` | Verifies the schema has every expected table and column |

## Loan interest rules

| Mode | Rule |
|---|---|
| Flat rate | Interest = principal × rate, charged once. Never grows. |
| Monthly interest | A fixed amount per month. `MONTHLY_ACCRUAL_TIMING=arrears` (default) charges on each monthly anniversary of the issue date; `advance` charges the first month on the issue date and each later month the day after an anniversary. Charges stop on the day the loan is settled. |
| Reducing balance | Equal monthly payments; interest on the remaining principal. |

Payments go to interest first, then principal. Discounts, waivers, write-offs and extra charges are
recorded as manager-approved adjustments with a reason; balances are never edited directly.

## Documentation

- [User Guide](docs/USER_GUIDE.md) — How to use the application
- [Render Deployment Guide](docs/RENDER_DEPLOY.md) — Production setup

## License

MIT — see [LICENSE](LICENSE) for details.

---

<p align="center">
  Built with &#9749; in Kampala, Uganda<br/>
  <a href="https://locusanalytics.tech">Locus Analytics</a>
</p>
