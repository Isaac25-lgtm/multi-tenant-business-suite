# 🧪 DENOVE APS - API Testing Guide

## Quick Start

This guide helps you test the Denove APS API using tools like:
- **Postman** (recommended)
- **Thunder Client** (VS Code extension)
- **cURL** (command line)
- **Insomnia**

## Base URL

```
http://localhost:5000/api
```

---

## 1. Authentication

### Login (Get JWT Token)

**Endpoint:** `POST /auth/login`

**Request Body:**
```json
{
  "username": "manager",
  "password": "admin123"
}
```

**Response:**
```json
{
  "access_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "refresh_token": "eyJ0eXAiOiJKV1QiLCJhbGc...",
  "user": {
    "id": 1,
    "username": "manager",
    "name": "Manager",
    "role": "manager",
    "assigned_business": "all",
    "is_active": true,
    "can_edit": true,
    "can_delete": true
  }
}
```

**📝 Important:** Copy the `access_token` - you'll need it for all subsequent requests!

---

### Using the Token

For all protected endpoints, add this header:

```
Authorization: Bearer YOUR_ACCESS_TOKEN_HERE
```

---

## 2. Testing Employee Endpoints (Manager Only)

### Get All Employees

**Endpoint:** `GET /employees`

**Headers:**
```
Authorization: Bearer YOUR_TOKEN
```

**Response:**
```json
{
  "employees": [
    {
      "id": 2,
      "username": "sarah",
      "name": "Sarah Nakato",
      "role": "employee",
      "assigned_business": "boutique",
      "is_active": true,
      "can_backdate": false,
      "backdate_limit": 1,
      "can_edit": true,
      "can_delete": true,
      "can_clear_credits": true
    }
  ]
}
```

### Create New Employee

**Endpoint:** `POST /employees`

**Headers:**
```
Authorization: Bearer YOUR_TOKEN
```

**Request Body:**
```json
{
  "username": "john",
  "password": "pass123",
  "name": "John Doe",
  "assigned_business": "boutique",
  "can_backdate": false,
  "backdate_limit": 1,
  "can_edit": true,
  "can_delete": false,
  "can_clear_credits": true
}
```

---

## 3. Testing Boutique Endpoints

### Get All Stock Items

**Endpoint:** `GET /boutique/stock`

**Headers:**
```
Authorization: Bearer YOUR_TOKEN
```

**Response:**
```json
{
  "stock": [
    {
      "id": 1,
      "item_name": "Ladies Dress - Floral",
      "category_id": 1,
      "category_name": "Dresses",
      "quantity": 20,
      "initial_quantity": 20,
      "unit": "pieces",
      "cost_price": 45000,
      "min_selling_price": 80000,
      "max_selling_price": 95000,
      "low_stock_threshold": 5,
      "is_active": true,
      "is_low_stock": false
    }
  ]
}
```

### Add Stock Item (Manager Only)

**Endpoint:** `POST /boutique/stock`

**Headers:**
```
Authorization: Bearer YOUR_TOKEN
```

**Request Body:**
```json
{
  "item_name": "Summer Dress",
  "category_id": 1,
  "quantity": 50,
  "unit": "pieces",
  "cost_price": 30000,
  "min_selling_price": 50000,
  "max_selling_price": 70000
}
```

**Response:**
```json
{
  "message": "Stock item added successfully",
  "stock": {
    "id": 6,
    "item_name": "Summer Dress",
    "quantity": 50,
    "low_stock_threshold": 12
  }
}
```

### Create a Sale

**Endpoint:** `POST /boutique/sales`

**Headers:**
```
Authorization: Bearer YOUR_TOKEN
```

**Request Body (Full Payment):**
```json
{
  "sale_date": "2026-01-20",
  "payment_type": "full",
  "items": [
    {
      "stock_id": 1,
      "quantity": 2,
      "unit_price": 85000
    },
    {
      "stock_id": 3,
      "quantity": 1,
      "unit_price": 120000
    }
  ],
  "amount_paid": 290000
}
```

**Request Body (Part Payment with Customer):**
```json
{
  "sale_date": "2026-01-20",
  "payment_type": "part",
  "items": [
    {
      "stock_id": 1,
      "quantity": 1,
      "unit_price": 85000
    }
  ],
  "amount_paid": 50000,
  "customer_name": "Jane Doe",
  "customer_phone": "0700123456",
  "customer_address": "Kampala"
}
```

**Response:**
```json
{
  "message": "Sale created successfully",
  "sale": {
    "id": 1,
    "reference_number": "DNV-B-00001",
    "sale_date": "2026-01-20",
    "total_amount": 85000,
    "amount_paid": 50000,
    "balance": 35000,
    "payment_type": "part",
    "is_credit_cleared": false,
    "items": [
      {
        "item_name": "Ladies Dress - Floral",
        "quantity": 1,
        "unit_price": 85000,
        "subtotal": 85000,
        "is_other_item": false
      }
    ]
  }
}
```

### Get Pending Credits

**Endpoint:** `GET /boutique/credits`

**Headers:**
```
Authorization: Bearer YOUR_TOKEN
```

**Response:**
```json
{
  "credits": [
    {
      "id": 1,
      "reference_number": "DNV-B-00001",
      "sale_date": "2026-01-20",
      "customer": {
        "id": 1,
        "name": "Jane Doe",
        "phone": "0700123456"
      },
      "total_amount": 85000,
      "amount_paid": 50000,
      "balance": 35000
    }
  ]
}
```

### Record Credit Payment

**Endpoint:** `POST /boutique/credits/1/payment`

**Headers:**
```
Authorization: Bearer YOUR_TOKEN
```

**Request Body:**
```json
{
  "amount": 20000,
  "payment_date": "2026-01-21"
}
```

**Response:**
```json
{
  "message": "Payment recorded successfully",
  "sale": {
    "id": 1,
    "balance": 15000,
    "is_credit_cleared": false
  },
  "payment": {
    "id": 1,
    "amount": 20000,
    "remaining_balance": 15000,
    "payment_date": "2026-01-21"
  }
}
```

---

## 4. Testing Dashboard Endpoints

### Get Manager Dashboard

**Endpoint:** `GET /dashboard/manager`

**Headers:**
```
Authorization: Bearer YOUR_TOKEN (Manager)
```

**Response:**
```json
{
  "stats": {
    "today_revenue": 500000,
    "yesterday_revenue": 450000,
    "credits_outstanding": 125000,
    "low_stock_alerts": 3
  },
  "by_business": {
    "boutique": {
      "today": 250000,
      "yesterday": 200000,
      "credits": 75000,
      "low_stock": 2
    },
    "hardware": {
      "today": 250000,
      "yesterday": 250000,
      "credits": 50000,
      "low_stock": 1
    }
  },
  "sales_trend": [
    {
      "date": "2026-01-14",
      "boutique": 180000,
      "hardware": 220000,
      "total": 400000
    }
  ]
}
```

### Get Employee Dashboard

**Endpoint:** `GET /dashboard/employee`

**Headers:**
```
Authorization: Bearer YOUR_TOKEN (Employee)
```

**Response:**
```json
{
  "stats": {
    "my_sales_today": 150000,
    "sales_count_today": 3,
    "pending_credits": 35000,
    "credits_count": 2
  },
  "recent_sales": [
    {
      "id": 1,
      "reference_number": "DNV-B-00001",
      "sale_date": "2026-01-20",
      "total_amount": 85000,
      "amount_paid": 50000,
      "balance": 35000,
      "payment_type": "part"
    }
  ]
}
```

---

## 5. Testing Hardware Endpoints

**All hardware endpoints follow the same structure as boutique:**

- `GET /hardware/stock`
- `POST /hardware/stock`
- `POST /hardware/sales`
- `GET /hardware/credits`
- etc.

Just replace `/boutique/` with `/hardware/` in the URLs.

Reference numbers will be `DNV-H-XXXXX` instead of `DNV-B-XXXXX`.

---

## 6. Testing Customer Endpoints

### Search Customers (Autocomplete)

**Endpoint:** `GET /customers/search?q=jane&business_type=boutique`

**Headers:**
```
Authorization: Bearer YOUR_TOKEN
```

**Response:**
```json
{
  "customers": [
    {
      "id": 1,
      "name": "Jane Doe",
      "phone": "0700123456",
      "address": "Kampala",
      "business_type": "boutique"
    }
  ]
}
```

---

## 7. Common Error Responses

### 401 Unauthorized (No Token)
```json
{
  "msg": "Missing Authorization Header"
}
```

### 401 Unauthorized (Invalid Credentials)
```json
{
  "error": "Invalid username or password"
}
```

### 403 Forbidden (Insufficient Permissions)
```json
{
  "error": "Manager access required"
}
```

### 400 Bad Request (Validation Error)
```json
{
  "error": "Price for Ladies Dress - Floral must be between 80000 and 95000"
}
```

### 404 Not Found
```json
{
  "error": "Stock item not found"
}
```

---

## 8. Complete Testing Workflow

### Step 1: Setup
1. Start backend: `cd backend && python run.py`
2. Verify server is running: `http://localhost:5000`

### Step 2: Authenticate
1. Login as manager to get token
2. Save the token for future requests

### Step 3: Test Manager Functions
1. Get all employees
2. Create a new employee
3. View stock items
4. Add new stock item
5. View dashboard

### Step 4: Test Employee Functions
1. Logout manager
2. Login as employee (sarah)
3. View employee dashboard
4. Create a sale
5. View credits

### Step 5: Test Business Logic
1. Create part payment sale
2. Check credit appears in credits list
3. Record credit payment
4. Verify balance updates
5. Check stock quantity decreased

---

## 9. Postman Collection

Create a collection with these variables:

**Variables:**
```
base_url: http://localhost:5000/api
token: (empty - will be set after login)
```

**Collection Structure:**
```
Denove APS
├── Auth
│   ├── Login (Manager)
│   ├── Login (Employee)
│   └── Get Current User
├── Employees
│   ├── Get All
│   ├── Create
│   └── Update
├── Boutique
│   ├── Stock
│   │   ├── Get All
│   │   ├── Add Item
│   │   └── Adjust Quantity
│   ├── Sales
│   │   ├── Create Sale (Full)
│   │   └── Create Sale (Part)
│   └── Credits
│       ├── Get Pending
│       └── Record Payment
├── Hardware
│   └── (Same as Boutique)
└── Dashboard
    ├── Manager
    └── Employee
```

---

## 10. cURL Examples

### Login
```bash
curl -X POST http://localhost:5000/api/auth/login \
  -H "Content-Type: application/json" \
  -d '{
    "username": "manager",
    "password": "admin123"
  }'
```

### Get Stock (with token)
```bash
curl -X GET http://localhost:5000/api/boutique/stock \
  -H "Authorization: Bearer YOUR_TOKEN_HERE"
```

### Create Sale
```bash
curl -X POST http://localhost:5000/api/boutique/sales \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer YOUR_TOKEN_HERE" \
  -d '{
    "sale_date": "2026-01-20",
    "payment_type": "full",
    "items": [
      {
        "stock_id": 1,
        "quantity": 1,
        "unit_price": 85000
      }
    ],
    "amount_paid": 85000
  }'
```

---

## 11. Testing Checklist

### Authentication ✅
- [ ] Login with manager account
- [ ] Login with employee account
- [ ] Invalid credentials return 401
- [ ] Token expires after 24 hours
- [ ] Logout works correctly

### Authorization ✅
- [ ] Manager can access all endpoints
- [ ] Employee can only access assigned business
- [ ] Manager-only endpoints reject employees
- [ ] Business access is enforced

### Boutique Module ✅
- [ ] Can list stock items
- [ ] Manager can add stock (employee cannot)
- [ ] Can create full payment sale
- [ ] Can create part payment sale
- [ ] Stock quantity decreases after sale
- [ ] Credits appear in credits list
- [ ] Can record credit payment
- [ ] Balance updates correctly

### Date Restrictions ✅
- [ ] Employee can create sale for today
- [ ] Employee can create sale for yesterday
- [ ] Employee cannot create sale for older dates
- [ ] Manager can create sale for any date

### Price Validation ✅
- [ ] Employee must price within min-max range
- [ ] Sale rejected if price too low
- [ ] Sale rejected if price too high
- [ ] Manager can set any price

### Stock Management ✅
- [ ] Low stock alert appears at 25%
- [ ] Cannot sell more than available quantity
- [ ] Stock quantity updates in real-time

---

**Happy Testing! 🧪**

For issues or questions, check the main README.md or PROJECT_STATUS.md
