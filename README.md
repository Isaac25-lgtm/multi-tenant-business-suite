<p align="center">
  <img src="backend/app/static/images/denove-logo.svg" alt="Denove APS" width="180" />
</p>

<h1 align="center">Denove APS</h1>

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

Denove APS is a full-stack Flask application built for a multi-section retail and lending operation in Uganda. It unifies **boutique (fashion) sales**, **hardware sales**, **equipment hire**, **customer management**, **loan administration**, and a **public-facing storefront** into a single deployable platform with role-based access control.

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
| **Manager Dashboard** | Real-time KPIs across all sections — sales, credits, loans, inventory value — with day-over-day comparisons |

## Tech Stack

- **Backend:** Flask · SQLAlchemy · Alembic
- **Database:** PostgreSQL
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
