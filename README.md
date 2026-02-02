<div align="center">

# 🏪 Denove APS

### Multi-Tenant Business Management Suite

A production-ready, full-stack business management platform powering retail operations and microfinance services for SMEs in East Africa.

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15-336791?style=for-the-badge&logo=postgresql&logoColor=white)](https://postgresql.org)
[![Tailwind CSS](https://img.shields.io/badge/Tailwind-3.0-38B2AC?style=for-the-badge&logo=tailwind-css&logoColor=white)](https://tailwindcss.com)
[![License](https://img.shields.io/badge/License-MIT-green?style=for-the-badge)](LICENSE)

[Live Demo](https://denove-aps.onrender.com) · [Report Bug](https://github.com/Isaac25-lgtm/multi-tenant-business-suite/issues) · [Request Feature](https://github.com/Isaac25-lgtm/multi-tenant-business-suite/issues)

</div>

---

## 📋 Table of Contents

- [About The Project](#-about-the-project)
- [Key Features](#-key-features)
- [Tech Stack](#-tech-stack)
- [Architecture](#-architecture)
- [Getting Started](#-getting-started)
- [Database Schema](#-database-schema)
- [Deployment](#-deployment)
- [Roadmap](#-roadmap)
- [Contributing](#-contributing)
- [License](#-license)

---

## 🎯 About The Project

**Denove APS** addresses the critical need for affordable, integrated business management software tailored for small and medium enterprises in emerging markets. Many SMEs in East Africa operate multiple business lines—retail shops, hardware stores, and microfinance services—yet struggle to find unified systems that don't require expensive subscriptions or complex infrastructure.

### The Problem
- SMEs manage inventory, sales, credits, and loans across disconnected spreadsheets
- Existing solutions are either too expensive or overly complex
- No unified view of business performance across multiple verticals
- Manual tracking leads to revenue leakage and poor decision-making
- Multi-branch operations lack centralized monitoring

### The Solution
A lightweight, server-rendered application that provides real-time business intelligence, automated credit tracking, and comprehensive loan management—all accessible from any device with a browser.

---

## ✨ Key Features

### 🛍️ Point of Sale & Inventory
- **Real-time stock tracking** with low-stock alerts and configurable thresholds
- **Multi-branch support** for boutique operations (separate inventory per branch)
- **Multi-category inventory** supporting clothing/retail and hardware verticals
- **Flexible payment options**: Full payment, partial payment, or credit sales
- **Automated profit calculation** with cost and selling price management
- **Manager controls**: Reactivate or permanently delete out-of-stock items

### 💳 Credit Management
- **Customer credit tracking** with payment history and aging reports
- **Partial payment processing** with automatic balance updates
- **Credit-to-cash conversion** when customers clear balances
- **Visual indicators** for overdue accounts

### 🏦 Microfinance Module
- **Individual loans** with customizable interest rates and terms
- **Group lending** supporting village savings and loan associations (VSLAs)
- **Payment scheduling** with periodic installment tracking
- **Loan agreement PDFs** with company branding and preview before generation
- **Date editing** for managers to correct loan terms
- **Loan portfolio analytics** including outstanding balances and payment status

### 📊 Business Intelligence Dashboard
- **Real-time revenue aggregation** across all business units
- **7-day sales trend visualization** with interactive charts
- **Outstanding credits and loans summary** at a glance
- **Low stock alerts** prioritized by urgency
- **Multi-branch monitoring** for managers

### 👥 User Management
- **Employee profiles** with profile pictures and contact information
- **Role-based access control** (Manager, Boutique, Hardware, Finance)
- **Branch assignment** for boutique staff
- **Granular permissions**: Control access to each module independently
- **User activation/deactivation** without data loss

### 🏢 Multi-Branch Operations
- **Boutique branches**: Separate data for Branch K (Kikuubo) and Branch B (Bugolobi)
- **Branch-specific login**: Staff see only their assigned branch
- **Manager overview**: View all branches or filter by specific branch
- **Branch switching**: Easy navigation between branches for managers

### 🔐 Enterprise Features
- **Complete audit trail** for all transactions
- **PDF receipt generation** with company logo header
- **Company branding** with customizable logo in navigation and documents
- **Dark mode support** for comfortable viewing
- **Session-based authentication** with secure password hashing

---

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|-------|------------|---------|
| **Backend** | Python 3.10+, Flask 3.0 | Application server & routing |
| **ORM** | SQLAlchemy 2.0 | Database abstraction |
| **Database** | SQLite / PostgreSQL | Local dev / Production |
| **Templates** | Jinja2 | Server-side rendering |
| **Styling** | Tailwind CSS 3.0 | Utility-first CSS framework |
| **PDF Generation** | ReportLab | Receipts, loan agreements, reports |
| **Authentication** | Werkzeug Security | Password hashing & verification |
| **Deployment** | Render, Gunicorn | Cloud hosting & WSGI server |

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        CLIENT BROWSER                           │
│                    (Server-Rendered HTML)                       │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                         FLASK APP                               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │  Dashboard  │  │  Boutique   │  │  Hardware   │             │
│  │   Module    │  │   Module    │  │   Module    │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐             │
│  │  Finance    │  │  Customers  │  │    Auth     │             │
│  │   Module    │  │   Module    │  │   Module    │             │
│  └─────────────┘  └─────────────┘  └─────────────┘             │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│                      SQLAlchemy ORM                             │
│         (Models: Stock, Sales, Credits, Loans, Users)           │
└─────────────────────────────────────────────────────────────────┘
                                │
                                ▼
┌─────────────────────────────────────────────────────────────────┐
│              PostgreSQL (Production) / SQLite (Dev)             │
└─────────────────────────────────────────────────────────────────┘
```

### Project Structure
```
backend/
├── app/
│   ├── __init__.py          # App factory pattern
│   ├── config.py            # Environment-based configuration
│   ├── extensions.py        # Flask extension initialization
│   │
│   ├── models/              # Domain models
│   │   ├── user.py          # User, authentication & permissions
│   │   ├── boutique.py      # Retail inventory, sales & credits
│   │   ├── hardware.py      # Hardware inventory, sales & credits
│   │   ├── customer.py      # Customer management
│   │   └── finance.py       # Loans, groups & payments
│   │
│   ├── modules/             # Feature blueprints (MVC pattern)
│   │   ├── auth/            # Authentication & authorization
│   │   ├── dashboard/       # Analytics, reporting & user management
│   │   ├── boutique/        # Retail operations (multi-branch)
│   │   ├── hardware/        # Hardware operations
│   │   ├── finance/         # Microfinance operations
│   │   └── customers/       # Customer management
│   │
│   ├── templates/           # Jinja2 templates
│   │   ├── base.html        # Base layout with navigation
│   │   ├── boutique/        # Boutique templates
│   │   ├── hardware/        # Hardware templates
│   │   ├── finance/         # Finance templates (loans, agreements)
│   │   ├── customers/       # Customer templates
│   │   └── users/           # User management templates
│   │
│   ├── static/
│   │   ├── css/style.css    # Custom styles & dark mode
│   │   ├── js/main.js       # JavaScript utilities
│   │   └── images/          # Logo and assets
│   │
│   └── utils/
│       ├── timezone.py      # East Africa timezone (EAT)
│       ├── utils.py         # Helper functions
│       └── pdf_generator.py # PDF generation with branding
│
├── requirements.txt
├── render.yaml              # Infrastructure as code
└── run.py                   # Application entry point
```

---

## 🚀 Getting Started

### Prerequisites
- Python 3.10 or higher
- pip (Python package manager)
- Git

### Installation

1. **Clone the repository**
   ```bash
   git clone https://github.com/Isaac25-lgtm/multi-tenant-business-suite.git
   cd multi-tenant-business-suite/backend
   ```

2. **Create virtual environment**
   ```bash
   python -m venv venv

   # Windows
   venv\Scripts\activate

   # Linux/Mac
   source venv/bin/activate
   ```

3. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

4. **Run the application**
   ```bash
   python run.py
   ```

5. **Access the application**
   ```
   http://localhost:5000
   ```

### Default Login Credentials

| Role | Username | Password |
|------|----------|----------|
| Manager | `admin` | `admin123` |
| Boutique | `boutique` | `boutique123` |
| Hardware | `hardware` | `hardware123` |
| Finance | `finance` | `finance123` |

> **Note**: Change default passwords immediately in production!

### Environment Variables

| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | SQLite (local) |
| `SECRET_KEY` | Flask session secret | Auto-generated |
| `FLASK_ENV` | Environment mode | `development` |

---

## 🗄️ Database Schema

### Core Entities

```
┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│    Users     │     │  Customers   │     │   Branches   │
├──────────────┤     ├──────────────┤     ├──────────────┤
│ id           │     │ id           │     │ K: Kikuubo   │
│ username     │     │ name         │     │ B: Bugolobi  │
│ password_hash│     │ phone        │     └──────────────┘
│ role         │     │ email        │
│ full_name    │     │ address      │
│ profile_pic  │     │ business_type│
│ boutique_branch    └──────────────┘
│ can_access_* │
└──────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│BoutiqueStock │     │BoutiqueSale  │     │CreditPayment │
├──────────────┤     ├──────────────┤     ├──────────────┤
│ id           │     │ id           │     │ id           │
│ item_name    │     │ reference_no │     │ sale_id      │
│ branch       │     │ branch       │     │ amount       │
│ quantity     │     │ customer_id  │     │ payment_date │
│ cost_price   │     │ total_amount │     │ balance      │
│ selling_price│     │ amount_paid  │     └──────────────┘
│ threshold    │     │ balance      │
│ is_active    │     │ is_credit    │
└──────────────┘     └──────────────┘

┌──────────────┐     ┌──────────────┐     ┌──────────────┐
│    Loan      │     │  LoanGroup   │     │ LoanPayment  │
├──────────────┤     ├──────────────┤     ├──────────────┤
│ id           │     │ id           │     │ id           │
│ customer_id  │     │ name         │     │ loan_id      │
│ amount       │     │ members      │     │ amount       │
│ interest_rate│     │ total_amount │     │ payment_date │
│ start_date   │     │ interest_rate│     │ period       │
│ end_date     │     │ period_type  │     └──────────────┘
│ status       │     │ agreement_pdf│
└──────────────┘     └──────────────┘
```

---

## ☁️ Deployment

### Render.com (Recommended)

The project includes `render.yaml` for one-click deployment:

1. Fork this repository
2. Connect to [Render](https://render.com)
3. Create a new **Blueprint** and select the repo
4. Configure environment variables:
   - `DATABASE_URL`: Your PostgreSQL connection string
   - `SECRET_KEY`: A secure random string
5. Deploy

### Manual Deployment

```bash
# Install production dependencies
pip install gunicorn psycopg2-binary

# Run with Gunicorn
gunicorn -w 4 -b 0.0.0.0:8000 "app:create_app()"
```

### Docker (Coming Soon)

```dockerfile
# Dockerfile support planned for future release
```

---

## 🗺️ Roadmap

### Completed ✅
- [x] Core POS functionality
- [x] Credit management system
- [x] Microfinance module (individual & group loans)
- [x] Multi-branch boutique operations
- [x] Role-based access control
- [x] User management with profiles
- [x] Audit trail logging
- [x] PDF generation with company branding
- [x] Loan date editing for managers
- [x] Stock reactivation/deletion controls
- [x] Dark mode support

### In Progress 🚧
- [ ] Mobile-responsive PWA optimization
- [ ] Excel/CSV report exports
- [ ] Email notifications

### Planned 📋
- [ ] Mobile money integration (MTN MoMo, Airtel Money)
- [ ] SMS notifications for payment reminders
- [ ] Multi-currency support
- [ ] Offline-first capability with sync
- [ ] Receipt printing integration
- [ ] Inventory barcode scanning
- [ ] Customer loyalty program

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

### Development Guidelines
- Follow PEP 8 for Python code
- Use meaningful commit messages
- Add tests for new features
- Update documentation as needed

---

## 📄 License

Distributed under the MIT License. See `LICENSE` for more information.

---

## 📬 Contact

[![GitHub](https://img.shields.io/badge/GitHub-Isaac25--lgtm-181717?style=flat&logo=github)](https://github.com/Isaac25-lgtm)

**Project Link**: [https://github.com/Isaac25-lgtm/multi-tenant-business-suite](https://github.com/Isaac25-lgtm/multi-tenant-business-suite)

---

<div align="center">

**Built with ❤️ in Uganda**

*Empowering SMEs with accessible technology*

</div>
