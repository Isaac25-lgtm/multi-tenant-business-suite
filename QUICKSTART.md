# 🚀 DENOVE APS - Quick Start Guide

## Get Started in 5 Minutes!

### Step 1: Install Backend Dependencies

```bash
cd backend
python -m venv venv

# Activate virtual environment
# Windows:
venv\Scripts\activate
# macOS/Linux:
source venv/bin/activate

# Install packages
pip install -r requirements.txt
```

### Step 2: Setup Database & Demo Data

```bash
python seed_data.py
```

This creates:
- ✅ Database with all tables
- ✅ Manager account
- ✅ 3 Employee accounts (Sarah, David, Grace)
- ✅ Sample stock items for Boutique and Hardware
- ✅ Sample customers

### Step 3: Start Backend Server

```bash
python run.py
```

Backend will run on `http://localhost:5000`

### Step 4: Install Frontend Dependencies

Open a **new terminal window**:

```bash
cd frontend
npm install
```

### Step 5: Start Frontend Server

```bash
npm run dev
```

Frontend will run on `http://localhost:3000`

### Step 6: Login!

Open your browser to `http://localhost:3000`

**Try Manager Account:**
- Username: `manager`
- Password: `admin123`

**Or Try Employee Account:**
- Username: `sarah`
- Password: `pass123`
- Business: Boutique

---

## 🎯 What You Can Do Now

### As Manager:
- ✅ View dashboard with real-time analytics
- ✅ See all 3 businesses overview
- ✅ View sales trends (7-day chart)
- ✅ See revenue breakdown by business
- ✅ Check low stock alerts
- ✅ Manage employees
- ✅ Access boutique and hardware modules

### As Employee (Sarah - Boutique):
- ✅ View personal dashboard
- ✅ See today's sales
- ✅ View pending credits
- ✅ Quick actions (New Sale, View Credits)
- ✅ See recent transactions
- ✅ Access only Boutique data

---

## 📊 System Status

### ✅ Fully Functional:
- Authentication & Authorization
- User Management
- Role-based Access Control
- Manager Dashboard with Charts
- Employee Dashboard
- Boutique Backend API (complete)
- Hardware Backend API (complete)
- Customer Management
- Audit Logging
- PDF Receipt Generation
- Database Models & Relationships

### 🚧 In Progress (Frontend UI):
- Boutique full interface (stock management, sales forms, credits)
- Hardware full interface
- Finance module (loans, group loans)
- Reports & Analytics pages
- Complete CRUD modals and forms

---

## 🔧 Troubleshooting

### Backend won't start?
```bash
# Make sure virtual environment is activated
# Check if port 5000 is free
# Reinstall dependencies
pip install -r requirements.txt
```

### Frontend won't start?
```bash
# Clear and reinstall
rm -rf node_modules
npm install
npm run dev
```

### Can't login?
```bash
# Reseed the database
cd backend
python seed_data.py
```

### API connection errors?
- Make sure backend is running on port 5000
- Check frontend vite.config.js proxy settings
- Try restarting both servers

---

## 📝 Demo Accounts Reference

| Role | Username | Password | Access |
|------|----------|----------|--------|
| Manager | manager | admin123 | All businesses |
| Employee | sarah | pass123 | Boutique only |
| Employee | david | pass123 | Hardware only |
| Employee | grace | pass123 | Finances only |

---

## 🎨 Color Scheme

The system uses a professional dark theme:

- **Primary**: Dark Navy (#0f172a)
- **Accent**: Teal (#14b8a6)
- **Success**: Green (#22c55e)
- **Warning**: Orange (#f59e0b)
- **Danger**: Red (#ef4444)

---

## 📦 What's Included

### Backend (Flask + SQLAlchemy):
- 15+ API endpoints
- 9 database models
- JWT authentication
- Audit middleware
- PDF generation
- Role-based decorators
- Date validation helpers

### Frontend (React + Tailwind):
- 6 main pages
- 4 reusable components
- API service layer
- Auth state management
- Responsive design
- Custom styling system

---

## 🌟 Next Steps

1. **Explore the Dashboards** - Login as manager and employee to see different views
2. **Check the Code** - Browse backend/app and frontend/src to understand structure
3. **Read the README** - Full documentation in README.md
4. **Test the API** - Use Postman/Thunder Client with the demo accounts
5. **Customize** - Update colors, add features, extend functionality

---

## 💡 Tips

- The manager can see **everything** across all businesses
- Employees can only see **their business** and **today + yesterday**
- All actions are **logged** in the audit trail
- Stock automatically **decreases** when items are sold
- Low stock alerts appear at **25% of initial quantity**
- Credits are tracked **per customer** with payment history
- Backdating has **limits** to prevent data manipulation

---

## 🎓 Learning Resources

- **Flask**: https://flask.palletsprojects.com/
- **React**: https://react.dev/
- **Tailwind CSS**: https://tailwindcss.com/
- **SQLAlchemy**: https://www.sqlalchemy.org/
- **Recharts**: https://recharts.org/

---

**Need Help?** Check the full README.md for detailed documentation!

**Happy Coding! 🚀**
