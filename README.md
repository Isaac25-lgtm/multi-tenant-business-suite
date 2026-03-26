# Denove APS

**Denove APS** is a full-stack Flask business management suite built for a multi-section retail and lending operation in Uganda. It manages boutique (fashion) sales, hardware sales, equipment hire, customer records, loan administration, and a public-facing storefront — all from a single deployable application with role-based access control.

---

## Table of Contents

- [Features Overview](#features-overview)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Quick Start (Local Development)](#quick-start-local-development)
- [Modules](#modules)
  - [Authentication & Access Control](#authentication--access-control)
  - [Dashboard](#dashboard)
  - [Boutique](#boutique)
  - [Hardware](#hardware)
  - [Finance (Loans)](#finance-loans)
  - [Customers](#customers)
  - [Website Management](#website-management)
  - [Public Storefront](#public-storefront)
- [Data Models](#data-models)
- [Utilities](#utilities)
- [Security](#security)
- [Deployment (Render)](#deployment-render)
- [Environment Variables](#environment-variables)
- [CLI Commands](#cli-commands)
- [Documentation](#documentation)

---

## Features Overview

| Area | Capabilities |
|------|-------------|
| **Boutique** | Multi-branch stock management, sales (full/credit), equipment hire & returns, PDF receipts, category management, auto-fetched product images |
| **Hardware** | Stock inventory, sales (full/credit), credit tracking, PDF receipts, category management |
| **Finance** | Loan clients with payer reputation, individual & group loans, flat-rate or monthly-accrual interest, payment tracking, PDF agreements, document uploads |
| **Customers** | Shared customer registry scoped by section, NIN encryption at rest, business type tagging |
| **Storefront** | Public product showcase, featured items, loan inquiry submission, cart-based order requests, rate-limited APIs |
| **Website Management** | Publish/unpublish products, manage banners & images, branding settings (logo, contact, loan terms), loan inquiry inbox with conversion to real loans, order request fulfillment |
| **Auth & Security** | Section-based login portals, role-based access control, login rate limiting, CSRF protection, audit trail, session management, PII encryption |
| **Deployment** | Render Blueprint with PostgreSQL, persistent upload disk, Alembic migrations, gunicorn with health checks |

---

## Architecture

- **Framework**: Flask 3.0 with the app factory pattern
- **Database**: SQLite (local development) / PostgreSQL (production via `DATABASE_URL`)
- **ORM**: Flask-SQLAlchemy with Flask-Migrate (Alembic)
- **Templates**: Jinja2 with auto-escaping
- **PDF Generation**: ReportLab with Pillow for image handling
- **Encryption**: Fernet symmetric encryption (cryptography library) for PII
- **WSGI Server**: Gunicorn (production), Flask dev server (local)
- **Styling**: Custom CSS with responsive design

---

## Project Structure

```
backend/
├── app/
│   ├── __init__.py              # App factory, blueprint registration, CLI commands
│   ├── config.py                # Configuration (dev/prod, DB, security)
│   ├── extensions.py            # SQLAlchemy, Migrate, CSRFProtect
│   ├── models/
│   │   ├── __init__.py          # Model imports
│   │   ├── user.py              # User, AuditLog, RateLimitState
│   │   ├── customer.py          # Customer (encrypted NIN)
│   │   ├── finance.py           # LoanClient, Loan, LoanPayment, GroupLoan, GroupLoanPayment, LoanDocument
│   │   ├── boutique.py          # BoutiqueCategory, BoutiqueStock, BoutiqueSale, BoutiqueSaleItem,
│   │   │                        #   BoutiqueCreditPayment, BoutiqueHire, BoutiqueHirePayment
│   │   ├── hardware.py          # HardwareCategory, HardwareStock, HardwareSale, HardwareSaleItem,
│   │   │                        #   HardwareCreditPayment
│   │   └── website.py           # WebsiteLoanInquiry, WebsiteOrderRequest, PublishedProduct,
│   │                            #   ProductImage, WebsiteSettings, WebsiteImage
│   ├── modules/
│   │   ├── auth/                # Login, rate limiting, access decorators
│   │   ├── dashboard/           # Unified manager dashboard
│   │   ├── boutique/            # Boutique stock, sales, hires, credits
│   │   ├── hardware/            # Hardware stock, sales, credits
│   │   ├── finance/             # Loan clients, individual & group loans, payments
│   │   ├── customers/           # Shared customer registry
│   │   ├── website_management/  # Product publishing, branding, inquiries
│   │   └── storefront/          # Public-facing pages & APIs
│   ├── templates/
│   │   ├── base.html            # Main layout with sidebar navigation
│   │   ├── audit_trail.html     # Audit log viewer
│   │   ├── auth/                # Login page
│   │   ├── boutique/            # Stock, sales, hires, credits, receipts (12 templates)
│   │   ├── hardware/            # Stock, sales, credits, receipts (8 templates)
│   │   ├── finance/             # Clients, loans, group loans, agreements (11 templates)
│   │   ├── customers/           # Customer list
│   │   ├── website_management/  # Products, images, inquiries, orders, settings (8 templates)
│   │   ├── storefront/          # Public storefront
│   │   ├── users/               # User CRUD (list, create, edit, view)
│   │   └── errors/              # 404, 500
│   ├── static/
│   │   ├── css/                 # style.css, storefront.css
│   │   ├── js/                  # main.js
│   │   ├── images/              # Logos (denove.jpg, denove-logo.svg, denovo.png)
│   │   └── uploads/             # User-uploaded files (products, profiles, website, collateral, documents)
│   └── utils/
│       ├── pii.py               # Fernet encrypt/decrypt for NINs
│       ├── rate_limit.py        # Persistent DB-backed rate limiting
│       ├── timezone.py          # EAT (UTC+3) / CET-CEST dual timezone
│       ├── pdf_generator.py     # Receipt & agreement PDF generation
│       ├── branding.py          # Site settings with DB overrides
│       ├── uploads.py           # File validation & safe storage
│       ├── image_fetch.py       # DuckDuckGo auto image fetching
│       └── utils.py             # Currency formatting, reference numbers, date ranges
├── migrations/
│   └── versions/                # Alembic migration scripts
├── run.py                       # WSGI entry point
├── seed_data.py                 # Disabled (directs to flask create-admin)
├── gunicorn.conf.py             # Gunicorn production config
├── Procfile                     # Render process type
├── requirements.txt             # Python dependencies
└── .env.example                 # Local environment template
```

---

## Quick Start (Local Development)

1. **Clone the repository:**
   ```bash
   git clone https://github.com/Isaac25-lgtm/multi-tenant-business-suite.git
   cd multi-tenant-business-suite/backend
   ```

2. **Create and activate a virtual environment:**
   ```bash
   python -m venv venv
   # Windows
   venv\Scripts\activate
   # macOS/Linux
   source venv/bin/activate
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Copy environment config:**
   ```bash
   cp .env.example .env
   ```

5. **Apply database migrations:**
   ```bash
   python -m flask --app run:app db upgrade
   ```

6. **Create an admin (manager) account:**
   ```bash
   python -m flask --app run:app create-admin
   ```
   You will be prompted for a username, password (min 8 characters), and full name.

7. **Run the app:**
   ```bash
   python run.py
   ```

8. **Open in browser:** [http://127.0.0.1:5000](http://127.0.0.1:5000)

The public storefront loads at `/`. Log in at `/auth/login`.

---

## Modules

### Authentication & Access Control

**URL prefix:** `/auth`

| Route | Method | Description |
|-------|--------|-------------|
| `/auth/login` | GET | Login page (neutral — auto-detects section from user role) |
| `/auth/login/<section>` | GET | Section-specific login portal (manager, boutique, hardware, finance) |
| `/auth/login` | POST | Authenticate with username + password |
| `/auth/logout` | POST | End session |

**Roles:** `manager`, `boutique`, `hardware`, `finance`

**Access flags per user:** `can_access_boutique`, `can_access_hardware`, `can_access_finance`, `can_access_customers`

- **Managers** have full access to all sections including user management and the audit trail.
- **Section workers** are restricted to their assigned section(s) plus customers (if enabled).
- Login attempts are rate-limited: **5 attempts per 5 minutes**, with a **15-minute lockout** on violation.
- Sessions are validated on every request by reloading the user from the database, so deactivating an account takes effect immediately.
- Login page shows a user dropdown — users select their name and enter a password.

### Dashboard

**URL prefix:** `/dashboard` (manager only)

A unified overview showing real-time KPIs across all sections:
- Today's sales and revenue (boutique + hardware) with day-over-day comparison
- Pending credits and outstanding balances
- Active loans, overdue count, and total outstanding
- Recent payments and inventory value

### Boutique

**URL prefix:** `/boutique`

Manages fashion/clothing inventory and sales across multiple branches.

| Feature | Description |
|---------|-------------|
| **Branches** | Kapchorwa (`K`) and Mbale (`B`) — employees are assigned to a branch; managers see all |
| **Categories** | Organize stock into categories |
| **Stock** | Add/edit inventory with cost price, min/max selling price, quantity, low-stock threshold, and product images (auto-fetched from DuckDuckGo or manually uploaded) |
| **Sales** | Create sales with multiple line items, full or credit payment, customer linking |
| **Credits** | Track partial payments on credit sales until balance is cleared |
| **Equipment Hire** | Rent out items with deposit, daily rate, expected return date, and return condition tracking |
| **PDF Receipts** | Branded receipts with Denove styling, payment details, and signature blocks |
| **Date Restrictions** | Employees can only enter data for today or yesterday; managers have no restriction |

### Hardware

**URL prefix:** `/hardware`

Manages building materials and hardware inventory. Same feature set as boutique (stock, sales, credits, PDF receipts) but without branch separation or equipment hire.

### Finance (Loans)

**URL prefix:** `/finance`

Full loan administration system.

| Feature | Description |
|---------|-------------|
| **Loan Clients** | Borrower registry with payer reputation (good / poor / neutral), phone, address, encrypted NIN |
| **Individual Loans** | Issue loans with principal, interest rate, duration (weeks or months) |
| **Interest Modes** | `flat_rate` (interest calculated upfront) or `monthly_accrual` (compounds each month) |
| **Group Loans** | Collective loans with multiple members, shared payment schedules, period-based tracking |
| **Payments** | Record payments against loans; auto-updates balance and status (active/overdue/paid) |
| **Loan Documents** | Upload collateral agreements, security documents (PDF) |
| **PDF Agreements** | Generate branded loan agreement documents for individual and group loans |
| **Client Conversion** | Website loan inquiries can be converted directly into loan clients with a linked loan |

### Customers

**URL prefix:** `/customers`

Shared customer registry used across boutique, hardware, and finance.

- Customers have a `business_type` field (boutique, hardware, finance) for scoping.
- NIN (National Identification Number) is encrypted at rest using Fernet encryption.
- Managers see all customers; section workers see only customers from their section.
- AJAX search endpoint for quick customer lookup in sale and loan forms.

### Website Management

**URL prefix:** `/website` (manager access, with section-scoped access for workers)

Controls what appears on the public storefront and handles incoming demand.

| Feature | Description |
|---------|-------------|
| **Product Publishing** | Publish/unpublish stock items to the storefront, set public pricing, mark as featured |
| **Multi-Image Products** | Upload multiple images per product with display ordering |
| **Website Images** | Manage banners, category images, and promotional graphics |
| **Loan Inquiries** | Inbox for public loan inquiry submissions — review, approve, reject, or convert to real loan clients |
| **Order Requests** | Inbox for cart-based order submissions — contact customer, fulfill, or cancel |
| **Website Settings** | Configure company name, tagline, logo, contact details, WhatsApp number, loan terms (min/max amounts, interest rate, approval hours), and footer content |

**Section-scoped access:**
- Boutique/hardware workers see only their product type
- Finance workers see only loan inquiries
- Managers see everything

### Public Storefront

**URL prefix:** `/` (no authentication required)

| Route | Method | Description |
|-------|--------|-------------|
| `/` | GET | Home page with featured products, banners, loan info, inquiry & order forms |
| `/shop` | GET | Full product listing |
| `/api/loan-inquiry` | POST | Submit a loan inquiry (rate-limited: 5 per 15 min) |
| `/api/order-request` | POST | Submit an order from cart (rate-limited: 5 per 15 min) |

- Only displays products from the `PublishedProduct` table (manager-controlled visibility).
- Never exposes actual stock quantities — shows "In Stock", "Limited", or "Out of Stock".
- Public API endpoints are CSRF-exempt but rate-limited and validated.
- Real-time toast notifications for new orders (via polling).

---

## Data Models

### Users & System

| Model | Table | Purpose |
|-------|-------|---------|
| `User` | `users` | Accounts with role, access flags, branch assignment, profile |
| `AuditLog` | `audit_logs` | Action tracking (username, section, action, entity, details, IP) |
| `RateLimitState` | `rate_limit_states` | Persistent rate limit counters |

### Boutique (7 models)

| Model | Table | Purpose |
|-------|-------|---------|
| `BoutiqueCategory` | `boutique_categories` | Product categories |
| `BoutiqueStock` | `boutique_stock` | Inventory with branch, pricing, images |
| `BoutiqueSale` | `boutique_sales` | Sale transactions (full/credit) |
| `BoutiqueSaleItem` | `boutique_sale_items` | Line items per sale |
| `BoutiqueCreditPayment` | `boutique_credit_payments` | Credit clearance payments |
| `BoutiqueHire` | `boutique_hires` | Equipment rental tracking |
| `BoutiqueHirePayment` | `boutique_hire_payments` | Hire payment records |

### Hardware (5 models)

| Model | Table | Purpose |
|-------|-------|---------|
| `HardwareCategory` | `hardware_categories` | Product categories |
| `HardwareStock` | `hardware_stock` | Inventory with pricing, images |
| `HardwareSale` | `hardware_sales` | Sale transactions (full/credit) |
| `HardwareSaleItem` | `hardware_sale_items` | Line items per sale |
| `HardwareCreditPayment` | `hardware_credit_payments` | Credit clearance payments |

### Finance (6 models)

| Model | Table | Purpose |
|-------|-------|---------|
| `LoanClient` | `loan_clients` | Borrowers with payer reputation |
| `Loan` | `loans` | Individual loans (flat-rate or monthly-accrual interest) |
| `LoanPayment` | `loan_payments` | Payment records per loan |
| `GroupLoan` | `group_loans` | Collective loans with member JSON |
| `GroupLoanPayment` | `group_loan_payments` | Group payment records |
| `LoanDocument` | `loan_documents` | Uploaded collateral and agreements |

### Website (5 models)

| Model | Table | Purpose |
|-------|-------|---------|
| `PublishedProduct` | `published_products` | Controls storefront visibility |
| `ProductImage` | `product_images` | Multiple images per product |
| `WebsiteSettings` | `website_settings` | Branding, contact, loan terms |
| `WebsiteImage` | `website_images` | Banners and promotional images |
| `WebsiteLoanInquiry` | `website_loan_inquiries` | Public loan inquiry submissions |
| `WebsiteOrderRequest` | `website_order_requests` | Public cart order submissions |

### Customers (1 model)

| Model | Table | Purpose |
|-------|-------|---------|
| `Customer` | `customers` | Shared registry with encrypted NIN |

---

## Utilities

| Utility | File | Purpose |
|---------|------|---------|
| **PII Encryption** | `utils/pii.py` | Fernet encrypt/decrypt for NIN fields using SECRET_KEY |
| **Rate Limiting** | `utils/rate_limit.py` | Database-backed throttling with configurable windows and block durations |
| **Timezone** | `utils/timezone.py` | East Africa Time (UTC+3) as primary; dual display with CET/CEST for Germany; DST-aware |
| **PDF Generator** | `utils/pdf_generator.py` | Branded receipts, hire contracts, and loan agreements using ReportLab |
| **Branding** | `utils/branding.py` | Merges DB settings over defaults for company name, logo, contact, loan terms |
| **File Uploads** | `utils/uploads.py` | Content-based validation (Pillow for images, header check for PDFs), safe filenames, 5MB limit |
| **Image Fetch** | `utils/image_fetch.py` | Background thread fetches product images via DuckDuckGo search API |
| **General** | `utils/utils.py` | Currency formatting (`UGX X,XXX`), reference number generation (`DNV-B-00001`), date range parsing |

---

## Security

| Measure | Implementation |
|---------|---------------|
| **Authentication** | Password hashing via Werkzeug; null password hashes are rejected (cannot log in) |
| **Rate Limiting** | Login: 5 attempts / 5 min, 15-min block. Public APIs: 5 / 15 min, 30-min block. Persistent in DB |
| **CSRF Protection** | Flask-WTF CSRFProtect on all forms; only public API endpoints are exempt |
| **Session Security** | `HTTPOnly`, `SameSite=Lax`, `Secure` flag in production, validated against DB on every request |
| **PII Encryption** | National ID numbers encrypted at rest with Fernet (AES-128-CBC) |
| **Audit Trail** | Every create, update, delete, and login is logged with username, section, IP, and JSON details |
| **File Upload Validation** | Extension whitelist + content-type verification via Pillow/header inspection |
| **Input Validation** | Server-side validation on all form inputs; financial amounts checked for valid ranges |
| **Soft Deletes** | Sales, loans, and payments are soft-deleted (flagged, not removed) for audit integrity |
| **Secret Key Enforcement** | Production refuses to start with weak or missing SECRET_KEY (must be 32+ chars) |

---

## Deployment (Render)

The repository includes [`render.yaml`](render.yaml) for one-click Render Blueprint deployment.

| Setting | Value |
|---------|-------|
| **Service name** | `denove-aps` |
| **Runtime** | Python 3.11.11 |
| **Plan** | Starter |
| **Region** | Oregon |
| **WSGI** | Gunicorn (1 worker, 4 threads, 120s timeout) |
| **Health check** | `GET /healthz` |
| **Persistent disk** | 5 GB at `/opt/render/project/src/backend/app/static/uploads` |

**Build pipeline:**
1. `pip install -r requirements.txt`
2. `flask db-ensure` (stamps existing DB if unversioned)
3. `flask db upgrade` (applies pending migrations)

**Database:** PostgreSQL (set `DATABASE_URL` manually in Render dashboard). Connection pool is configured with keepalives, pre-ping, and 5-minute recycle for Neon/serverless PostgreSQL compatibility.

**Typical URL:** `https://denove-aps.onrender.com`

---

## Environment Variables

Copy `backend/.env.example` to `backend/.env` for local development.

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `FLASK_ENV` | No | `development` | Set to `production` for production |
| `FLASK_DEBUG` | No | `0` | Set to `1` for debug mode with hot reload |
| `SECRET_KEY` | **Yes (prod)** | `local-dev-only-...` | Must be 32+ characters in production |
| `DATABASE_URL` | No | (SQLite) | PostgreSQL connection string for production |
| `UPLOAD_FOLDER` | No | `uploads` | Path for file uploads |
| `MAX_CONTENT_LENGTH` | No | `5242880` | Max upload size in bytes (default 5 MB) |
| `SESSION_COOKIE_SECURE` | No | `0` | Set to `1` in production (requires HTTPS) |

---

## CLI Commands

Run from the `backend/` directory with the virtual environment activated.

| Command | Description |
|---------|-------------|
| `flask --app run:app db upgrade` | Apply pending database migrations |
| `flask --app run:app db-ensure` | Stamp an existing unversioned database so migrations work (safe to run multiple times) |
| `flask --app run:app create-admin` | Create a manager account (prompts for username, password, full name) |

---

## Documentation

| Document | Description |
|----------|-------------|
| [User Guide](docs/USER_GUIDE.md) | How to use the application |
| [Render Deployment Guide](docs/RENDER_DEPLOY.md) | Step-by-step production deployment |
| [Environment Example](backend/.env.example) | Local development environment template |

---

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| Flask | 3.0.0 | Web framework |
| Flask-SQLAlchemy | 3.1.1 | ORM |
| Flask-Migrate | 4.0.5 | Database migrations (Alembic) |
| Flask-WTF | 1.2.2 | CSRF protection & form handling |
| python-dotenv | 1.0.0 | Environment variable loading |
| reportlab | 4.2.0 | PDF generation |
| Pillow | 11.0.0 | Image processing & validation |
| python-dateutil | 2.8.2 | Date arithmetic |
| gunicorn | 21.2.0 | Production WSGI server |
| psycopg2-binary | 2.9.10 | PostgreSQL driver |
| duckduckgo-search | >= 7.0.0 | Auto product image fetching |

---

## Repository

GitHub: [https://github.com/Isaac25-lgtm/multi-tenant-business-suite](https://github.com/Isaac25-lgtm/multi-tenant-business-suite)
