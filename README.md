# Denove APS

A simple, server-rendered business management system for retail and microfinance operations.

## Overview

Denove APS is a lightweight Flask application for managing:
- **Boutique** - Clothing/retail inventory and sales
- **Hardware** - Hardware store inventory and sales
- **Finance** - Individual and group loans
- **Customers** - Customer database

## Tech Stack

- **Backend**: Flask 3.0, SQLAlchemy, Jinja2 templates
- **Database**: SQLite (local), PostgreSQL (production)
- **Frontend**: Server-rendered HTML with Tailwind CSS (CDN)
- **Styling**: Minimal JavaScript, form-based submissions

## Quick Start

### 1. Clone and setup

```bash
git clone <repository-url>
cd backend
python -m venv venv

# Windows
venv\Scripts\activate

# Linux/Mac
source venv/bin/activate

pip install -r requirements.txt
```

### 2. Run the application

```bash
python run.py
```

The app will be available at `http://localhost:5000`

## Project Structure

```
backend/
├── app/
│   ├── __init__.py          # Flask app factory
│   ├── config.py            # Configuration (SQLite/PostgreSQL)
│   ├── extensions.py        # Flask extensions
│   │
│   ├── models/              # SQLAlchemy models
│   │   ├── boutique.py      # Boutique stock, sales, credits
│   │   ├── hardware.py      # Hardware stock, sales, credits
│   │   ├── customer.py      # Customer model
│   │   └── finance.py       # Loans, payments
│   │
│   ├── modules/             # Route blueprints
│   │   ├── dashboard/       # Main dashboard
│   │   ├── boutique/        # Boutique routes
│   │   ├── hardware/        # Hardware routes
│   │   ├── finance/         # Finance routes
│   │   └── customers/       # Customer routes
│   │
│   ├── templates/           # Jinja2 templates
│   │   ├── base.html        # Base layout
│   │   ├── dashboard.html   # Dashboard
│   │   ├── boutique/        # Boutique templates
│   │   ├── hardware/        # Hardware templates
│   │   ├── finance/         # Finance templates
│   │   └── customers/       # Customer templates
│   │
│   ├── static/              # Static assets
│   │   ├── css/style.css    # Custom styles
│   │   └── js/main.js       # JavaScript utilities
│   │
│   └── utils/               # Utilities
│       ├── timezone.py      # East Africa timezone
│       ├── utils.py         # Helper functions
│       └── pdf_generator.py # PDF generation
│
├── requirements.txt         # Python dependencies
└── run.py                   # Entry point
```

## Features

### Dashboard
- Real-time revenue tracking
- Sales trends (7-day chart)
- Low stock alerts
- Outstanding credits and loans

### Boutique & Hardware
- Stock management with categories
- Sales with full/partial payment
- Credit tracking and payments
- Low stock threshold alerts

### Finance
- Individual loan management
- Group loans with periodic payments
- Interest rate configuration
- Payment history tracking

### Customers
- Centralized customer database
- Filter by business type
- Quick search

## Configuration

### Local Development (SQLite)
No configuration needed. The app automatically uses SQLite.

### Production (PostgreSQL)
Set the `DATABASE_URL` environment variable:

```bash
export DATABASE_URL=postgresql://user:password@host:5432/dbname
```

## Deployment

### Render.com

1. Create a new Web Service
2. Connect your repository
3. Set environment variables:
   - `DATABASE_URL` - Your PostgreSQL connection string
   - `SECRET_KEY` - A secure random string
4. Deploy

See `render.yaml` for configuration.

## License

MIT License

---

**Built in Uganda**
