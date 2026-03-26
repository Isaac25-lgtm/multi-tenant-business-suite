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
| **Inventory** | Multi-branch stock management, low-stock alerts, cost/selling price controls, auto-fetched product images |
| **Equipment Hire** | Deposit & daily rate tracking, return condition logging, hire payment history |
| **Microfinance** | Individual & group loans, flat-rate or monthly-accrual interest, payment schedules, PDF loan agreements, collateral document uploads |
| **Customer Registry** | Shared across all sections, NIN encrypted at rest (Fernet/AES-128-CBC), business-type scoping |
| **Public Storefront** | Product showcase, featured items, loan inquiry & cart-based order submissions, rate-limited APIs |
| **Website CMS** | Publish/unpublish products, manage banners & branding, loan inquiry inbox with one-click conversion to real loans |
| **Manager Dashboard** | Real-time KPIs across all sections — sales, credits, loans, inventory value — with day-over-day comparisons |

## Tech Stack

- **Backend:** Flask 3.0 · SQLAlchemy · Alembic (Flask-Migrate)
- **Database:** SQLite (dev) · PostgreSQL (prod)
- **PDF:** ReportLab + Pillow
- **Security:** Fernet PII encryption · Flask-WTF CSRF · DB-backed rate limiting · audit trail
- **Deployment:** Render Blueprint · Gunicorn · persistent upload disk

## Getting Started

```bash
cd backend

# Set up environment
python -m venv venv && source venv/bin/activate   # Windows: venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env

# Initialize database & create admin
flask --app run:app db upgrade
flask --app run:app create-admin

# Run
python run.py
```

Open **http://127.0.0.1:5000** — the public storefront loads at `/`, admin login at `/auth/login`.

## Architecture

```
backend/
├── app/
│   ├── __init__.py          # App factory & blueprint registration
│   ├── config.py            # Dev/prod configuration
│   ├── models/              # SQLAlchemy models (24 tables)
│   ├── modules/             # Feature blueprints
│   │   ├── auth/            # Login, rate limiting, role decorators
│   │   ├── dashboard/       # Manager KPI dashboard
│   │   ├── boutique/        # Fashion stock, sales, hires, credits
│   │   ├── hardware/        # Hardware stock, sales, credits
│   │   ├── finance/         # Loan clients, loans, payments
│   │   ├── customers/       # Shared customer registry
│   │   ├── website_management/  # CMS & inquiry inbox
│   │   └── storefront/      # Public-facing pages & APIs
│   ├── templates/           # Jinja2 templates (50+)
│   ├── static/              # CSS, JS, uploads
│   └── utils/               # PII encryption, PDF gen, rate limiting, etc.
├── migrations/              # Alembic version scripts
├── run.py                   # WSGI entry point
└── gunicorn.conf.py         # Production server config
```

## Roles & Access Control

| Role | Access |
|------|--------|
| **Manager** | Full access — all sections, user management, audit trail, website CMS |
| **Boutique** | Boutique inventory & sales, customers (if enabled) |
| **Hardware** | Hardware inventory & sales, customers (if enabled) |
| **Finance** | Loan administration, customers (if enabled) |

- Login rate-limited: **5 attempts / 5 min**, 15-minute lockout
- Sessions validated against the database on every request
- Deactivating a user takes effect immediately

## Security

| Layer | Implementation |
|-------|---------------|
| Authentication | Werkzeug password hashing; null hashes rejected |
| PII Protection | National IDs encrypted at rest (Fernet / AES-128-CBC) |
| CSRF | Flask-WTF on all forms; public APIs exempt but rate-limited |
| Sessions | HTTPOnly, SameSite=Lax, Secure in production |
| Audit Trail | Every CUD operation logged with user, section, IP, and details |
| File Uploads | Extension whitelist + content-type verification (Pillow/header), 5 MB limit |
| Data Integrity | Soft deletes on sales, loans, and payments |
| Secret Key | Production refuses to start with weak or missing key (32+ chars required) |

## Deployment

One-click deployment via the included `render.yaml` Blueprint:

| Setting | Value |
|---------|-------|
| Runtime | Python 3.11 |
| Server | Gunicorn (1 worker, 4 threads, 120s timeout) |
| Health check | `GET /healthz` |
| Persistent disk | 5 GB for uploads |
| Database | PostgreSQL (external — configure `DATABASE_URL`) |

See the full [Render Deployment Guide →](docs/RENDER_DEPLOY.md)

## Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `SECRET_KEY` | **Yes** (prod) | Encryption & session key (32+ characters) |
| `DATABASE_URL` | No | PostgreSQL connection string (defaults to SQLite) |
| `FLASK_ENV` | No | `development` or `production` |
| `FLASK_DEBUG` | No | `1` for hot reload |
| `SESSION_COOKIE_SECURE` | No | `1` in production (requires HTTPS) |

## Documentation

- [User Guide](docs/USER_GUIDE.md) — How to use the application
- [Render Deployment Guide](docs/RENDER_DEPLOY.md) — Step-by-step production setup
- [Environment Example](backend/.env.example) — Local dev template

## License

MIT — see [LICENSE](LICENSE) for details.

---

<p align="center">
  Built with &#9749; in Kampala, Uganda<br/>
  <a href="https://locusanalytics.tech">Locus Analytics</a>
</p>
