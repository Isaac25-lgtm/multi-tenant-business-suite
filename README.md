<div align="center">

# 🏢 DENOVE APS

### A Full-Stack Multi-Tenant Business Management System for Retail & Microfinance Operations

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.0-000000?style=for-the-badge&logo=flask&logoColor=white)](https://flask.palletsprojects.com)
[![React](https://img.shields.io/badge/React-18.2-61DAFB?style=for-the-badge&logo=react&logoColor=black)](https://reactjs.org)
[![SQLite](https://img.shields.io/badge/SQLite-3.0-003B57?style=for-the-badge&logo=sqlite&logoColor=white)](https://sqlite.org)
[![TailwindCSS](https://img.shields.io/badge/Tailwind-3.3-06B6D4?style=for-the-badge&logo=tailwindcss&logoColor=white)](https://tailwindcss.com)

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg?style=for-the-badge)](https://opensource.org/licenses/MIT)
[![PRs Welcome](https://img.shields.io/badge/PRs-welcome-brightgreen.svg?style=for-the-badge)](http://makeapullrequest.com)

<p align="center">
  <strong>Empowering business owners to manage multiple business units from anywhere in the world</strong>
</p>

[Features](#-features) • [Installation](#-installation) • [Documentation](#-documentation) • [Contributing](#-contributing)

---

</div>

## 📋 Overview

**DENOVE APS** (Application Platform Suite) is a comprehensive business management platform designed for entrepreneurs managing multiple business verticals. Built with scalability and simplicity in mind, it provides real-time analytics, role-based access control, and complete audit trails — enabling business owners to monitor operations remotely while employees handle day-to-day transactions.

### 🎯 Problem It Solves

Small and medium business owners often struggle with:
- **Fragmented Systems** — Using different tools for inventory, sales, and lending
- **Limited Visibility** — Unable to monitor operations remotely in real-time
- **Trust Issues** — No way to track employee actions or verify transactions
- **Cash Leakage** — Poor credit tracking leads to uncollected customer balances

This system consolidates everything into one platform with complete transparency.

---

## ✨ Features

### 🔐 Authentication & Access Control
- JWT-based secure authentication with refresh tokens
- Role-based permissions (Manager/Employee)
- Business unit assignment per employee (Boutique, Hardware, Finance)
- Granular permission controls (edit, delete, backdate, clear credits)
- Session management and secure logout

### 📊 Manager Dashboard
- Real-time revenue tracking across all business units
- Day-over-day performance comparison
- Interactive charts (revenue trends, business distribution) using Recharts
- Low stock alerts with 25% threshold notifications
- Outstanding credits and loans tracking
- End-of-day summary by business unit

### 🛍️ Point of Sale (Boutique & Hardware)
- Intuitive sales entry interface
- Stock selection with real-time availability
- Price validation within manager-defined ranges
- Full and partial payment support
- Customer credit management
- Automatic stock deduction
- "Other" item support for unlisted products
- Date validation (employees limited to today/yesterday)

### 💳 Credit Management
- Customer database with auto-suggest
- Payment history tracking
- Partial payment recording
- Balance auto-calculation
- Credit clearance workflow
- Customer contact management

### 💰 Finance Module (UI Ready)
- Individual loan management interface
- Group loan support with flexible payment periods
- Configurable interest rates per loan
- Loan renewal system
- Multiple security document uploads (PDF, images)
- Automated due date calculation
- Overdue loan tracking
- Printable loan agreements

### 📈 Reports & Analytics
- Daily, weekly, monthly sales reports
- Profit margin analysis
- Stock movement reports
- Outstanding credits report
- Employee performance tracking
- Export functionality (planned)

### 📋 Audit Trail
- Complete action logging (create, edit, delete)
- Before/after value tracking for edits
- Soft delete with full record preservation
- Flagged actions highlighting
- Employee activity filtering
- Date range queries

### ⚙️ Administration
- Employee account management
- Permission configuration
- Business settings customization
- Receipt text customization
- Loan terms configuration

### 📱 Responsive Design
- Desktop optimized interface
- Tablet-friendly layouts
- Mobile-responsive views
- Touch-friendly controls

---

## 🛠️ Tech Stack

### Backend
| Technology | Version | Purpose |
|------------|---------|---------|
| **Python** | 3.10+ | Core programming language |
| **Flask** | 3.0.0 | Web framework |
| **Flask-SQLAlchemy** | 3.1.1 | ORM for database operations |
| **Flask-JWT-Extended** | 4.6.0 | Authentication & authorization |
| **Flask-CORS** | 4.0.0 | Cross-origin resource sharing |
| **Flask-Migrate** | 4.0.5 | Database migrations |
| **SQLite** | 3.0 | Development database (PostgreSQL ready) |
| **bcrypt** | 4.1.2 | Password hashing |
| **ReportLab** | 4.0.7 | PDF generation |
| **Pillow** | 10.1.0 | Image processing |
| **python-dotenv** | 1.0.0 | Environment variable management |

### Frontend
| Technology | Version | Purpose |
|------------|---------|---------|
| **React** | 18.2.0 | UI framework |
| **Vite** | 5.0.8 | Build tool and dev server |
| **Tailwind CSS** | 3.3.6 | Utility-first CSS framework |
| **Recharts** | 2.10.3 | Data visualization |
| **Axios** | 1.6.2 | HTTP client |
| **React Router** | 6.20.0 | Client-side routing |
| **Zustand** | 4.4.7 | State management |
| **date-fns** | 3.0.0 | Date manipulation |

---

## 🚀 Installation

### Prerequisites
- Python 3.10 or higher
- Node.js 18 or higher
- Git

### Quick Start

1. **Clone the repository**
```bash
git clone https://github.com/Isaac25-lgtm/multi-tenant-business-suite.git
cd multi-tenant-business-suite
```

2. **Set up the backend**
```bash
cd backend
python -m venv venv

# On Windows:
venv\Scripts\activate

# On Linux/Mac:
source venv/bin/activate

pip install -r requirements.txt
```

3. **Initialize the database**
```bash
python seed_data.py
```

4. **Set up the frontend**
```bash
cd ../frontend
npm install
```

5. **Run the development servers**

**Backend (Terminal 1):**
```bash
cd backend
python run.py
```
Backend will run on: `http://localhost:5000`

**Frontend (Terminal 2):**
```bash
cd frontend
npm run dev
```
Frontend will run on: `http://localhost:3000` (or 3001 if 3000 is in use)

6. **Access the application**
```
Frontend: http://localhost:3000
Backend API: http://localhost:5000
```

### Demo Credentials
| Role | Username | Password | Access |
|------|----------|----------|--------|
| Manager | `manager` | `admin123` | Full system access |
| Boutique Employee | `sarah` | `pass123` | Boutique only |
| Hardware Employee | `david` | `pass123` | Hardware only |
| Finance Employee | `grace` | `pass123` | Finance only |

---

## 📁 Project Structure

```
multi-tenant-business-suite/
│
├── backend/
│   ├── app/
│   │   ├── __init__.py          # Flask app factory
│   │   ├── config.py             # Configuration settings
│   │   ├── extensions.py         # Flask extensions initialization
│   │   │
│   │   ├── models/               # SQLAlchemy models
│   │   │   ├── user.py           # User/Employee model
│   │   │   ├── boutique.py      # Boutique models (Stock, Sales, Credits)
│   │   │   ├── hardware.py      # Hardware models (Stock, Sales, Credits)
│   │   │   ├── customer.py       # Customer model
│   │   │   └── audit.py         # Audit log model
│   │   │
│   │   ├── modules/              # API route modules
│   │   │   ├── auth/            # Authentication endpoints
│   │   │   ├── boutique/        # Boutique business logic
│   │   │   ├── hardware/        # Hardware business logic
│   │   │   ├── employees/       # Employee management
│   │   │   ├── customers/       # Customer management
│   │   │   └── dashboard/       # Dashboard data endpoints
│   │   │
│   │   ├── middleware/          # Custom middleware
│   │   │   └── audit.py         # Audit logging middleware
│   │   │
│   │   └── utils/               # Utility functions
│   │       ├── helpers.py       # Helper functions (permissions, validation)
│   │       └── pdf_generator.py  # PDF receipt generation
│   │
│   ├── instance/                # Database files (SQLite)
│   ├── uploads/                 # File uploads directory
│   ├── requirements.txt         # Python dependencies
│   ├── run.py                   # Application entry point
│   └── seed_data.py             # Database seeding script
│
├── frontend/
│   ├── src/
│   │   ├── App.jsx              # Main application component
│   │   ├── main.jsx             # React entry point
│   │   ├── index.css            # Global styles
│   │   │
│   │   ├── components/          # Reusable components
│   │   │   ├── Sidebar.jsx
│   │   │   ├── Header.jsx
│   │   │   └── DashboardLayout.jsx
│   │   │
│   │   ├── context/            # React context providers
│   │   │   └── AuthContext.jsx
│   │   │
│   │   ├── services/           # API service layer
│   │   │   └── api.js          # Axios configuration & endpoints
│   │   │
│   │   └── utils/              # Utility functions
│   │
│   ├── public/                 # Static assets
│   ├── package.json            # Node dependencies
│   ├── vite.config.js          # Vite configuration
│   └── tailwind.config.js      # Tailwind CSS configuration
│
└── README.md                   # This file
```

---

## 📚 API Documentation

### Authentication Endpoints
| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| POST | `/api/auth/login` | User login | No |
| POST | `/api/auth/logout` | User logout | Yes |
| GET | `/api/auth/me` | Get current user | Yes |
| PUT | `/api/auth/change-password` | Change password | Yes |

### Boutique Module
| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/boutique/stock` | List stock items | Yes |
| POST | `/api/boutique/stock` | Add stock item | Manager |
| PUT | `/api/boutique/stock/:id` | Update stock item | Manager |
| DELETE | `/api/boutique/stock/:id` | Delete stock item | Manager |
| GET | `/api/boutique/sales` | List sales | Yes |
| POST | `/api/boutique/sales` | Create sale | Yes |
| DELETE | `/api/boutique/sales/:id` | Delete sale | Yes (with permissions) |
| GET | `/api/boutique/credits` | List pending credits | Yes |
| GET | `/api/boutique/credits/cleared` | List cleared credits | Manager |
| POST | `/api/boutique/credits/:id/payment` | Record payment | Yes (with permissions) |
| GET | `/api/boutique/categories` | List categories | Yes |
| POST | `/api/boutique/categories` | Create category | Manager |

### Hardware Module
Same structure as Boutique module with `/api/hardware` prefix.

### Employee Management
| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/employees` | List employees | Manager |
| POST | `/api/employees` | Create employee | Manager |
| PUT | `/api/employees/:id` | Update employee | Manager |
| DELETE | `/api/employees/:id` | Delete employee | Manager |
| PUT | `/api/employees/:id/permissions` | Update permissions | Manager |

### Dashboard
| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/dashboard/manager` | Manager dashboard data | Manager |
| GET | `/api/dashboard/employee` | Employee dashboard data | Employee |
| GET | `/api/dashboard/notifications` | Get notifications | Yes |

### Customers
| Method | Endpoint | Description | Auth Required |
|--------|----------|-------------|---------------|
| GET | `/api/customers` | List customers | Yes |
| POST | `/api/customers` | Create customer | Yes |
| GET | `/api/customers/search` | Search customers | Yes |

---

## 🔒 Security Features

- **Password Hashing**: Bcrypt with automatic salt generation
- **JWT Tokens**: Short-lived access tokens (24h) with refresh tokens (30 days)
- **Role Validation**: Server-side permission checks on all endpoints
- **Input Validation**: Price range validation, quantity checks, date restrictions
- **Audit Logging**: Complete action trail for accountability
- **Soft Deletes**: Data preservation for recovery and auditing
- **CORS Protection**: Configured for development and production

---

## 🧪 Testing

### Backend Testing
```bash
cd backend
# Install test dependencies
pip install pytest pytest-cov

# Run tests
pytest

# With coverage
pytest --cov=app tests/
```

### Frontend Testing
```bash
cd frontend
# Install test dependencies (if configured)
npm install --save-dev @testing-library/react @testing-library/jest-dom

# Run tests
npm run test
```

---

## 🐳 Docker Deployment (Planned)

Docker configuration will be added for production deployment.

### Environment Variables
| Variable | Description | Default |
|----------|-------------|---------|
| `DATABASE_URL` | Database connection string | `sqlite:///denove_aps.db` |
| `SECRET_KEY` | Flask secret key | `dev-secret-key` |
| `JWT_SECRET_KEY` | JWT signing key | `dev-jwt-secret-key` |
| `UPLOAD_FOLDER` | File upload directory | `./uploads` |
| `MAX_CONTENT_LENGTH` | Max upload size (bytes) | `5242880` (5MB) |

---

## 🗺️ Roadmap

- [x] Core authentication system with JWT
- [x] Boutique module (POS, inventory, credits)
- [x] Hardware module (POS, inventory, credits)
- [x] Employee management with granular permissions
- [x] Manager dashboard with real-time analytics
- [x] Credit management system
- [x] Audit trail logging
- [x] PDF receipt generation
- [x] Role-based access control
- [ ] Finance module backend implementation
- [ ] Reports export (Excel/CSV)
- [ ] SMS notifications for overdue loans
- [ ] Mobile app (React Native)
- [ ] Multi-currency support
- [ ] Barcode scanning
- [ ] Cloud backup integration
- [ ] WhatsApp integration for receipts

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. **Fork the repository**
2. **Create a feature branch**
   ```bash
   git checkout -b feature/amazing-feature
   ```
3. **Commit your changes**
   ```bash
   git commit -m 'Add some amazing feature'
   ```
4. **Push to the branch**
   ```bash
   git push origin feature/amazing-feature
   ```
5. **Open a Pull Request**

### Contribution Guidelines
- Follow the existing code style (PEP 8 for Python, ESLint for JavaScript)
- Write tests for new features
- Update documentation as needed
- Keep commits atomic and well-described
- Ensure all tests pass before submitting PR

---

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 👤 Author

**Isaac Omoding**

- GitHub: [@Isaac25-lgtm](https://github.com/Isaac25-lgtm)
- Repository: [multi-tenant-business-suite](https://github.com/Isaac25-lgtm/multi-tenant-business-suite)

---

## 🙏 Acknowledgments

- [Flask Documentation](https://flask.palletsprojects.com/)
- [React Documentation](https://react.dev/)
- [Tailwind CSS](https://tailwindcss.com/)
- [Recharts](https://recharts.org/)
- [Vite](https://vitejs.dev/)

---

<div align="center">

### ⭐ Star this repository if you find it useful!

<br/>

**Built with ❤️ in Uganda 🇺🇬**

</div>
