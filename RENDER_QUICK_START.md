# ⚡ Render Deployment - Quick Start

**Fast deployment guide for DENOVE APS on Render.com**

---

## 🚀 5-Minute Deployment

### Prerequisites
- GitHub repository pushed: `https://github.com/Isaac25-lgtm/multi-tenant-business-suite`
- Render.com account (free tier works)

---

## Step-by-Step

### 1️⃣ Create PostgreSQL Database (2 min)

1. Go to https://dashboard.render.com
2. Click **"New +"** → **"PostgreSQL"**
3. Settings:
   - Name: `denove-aps-db`
   - Plan: **Free** (or Starter for production)
   - Region: Choose closest
4. Click **"Create Database"**
5. **Copy the Internal Database URL** (you'll need it)

---

### 2️⃣ Deploy Backend (3 min)

1. Click **"New +"** → **"Web Service"**
2. Connect GitHub repo: `multi-tenant-business-suite`
3. Settings:
   ```
   Name: denove-aps-backend
   Root Directory: backend
   Environment: Python 3
   Build Command: pip install -r requirements.txt
   Start Command: gunicorn -w 4 -b 0.0.0.0:$PORT run:app
   ```
4. **Environment Variables:**
   ```
   DATABASE_URL = <paste Internal Database URL from step 1>
   SECRET_KEY = <generate random string>
   JWT_SECRET_KEY = <generate random string>
   FLASK_ENV = production
   UPLOAD_FOLDER = /opt/render/project/src/uploads
   MAX_CONTENT_LENGTH = 5242880
   ```
5. Click **"Create Web Service"**
6. Wait for deployment (~5 min)
7. **Note your backend URL**: `https://denove-aps-backend.onrender.com`

**Generate Secret Keys:**
```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

---

### 3️⃣ Deploy Frontend (2 min)

1. Click **"New +"** → **"Static Site"**
2. Connect same GitHub repo
3. Settings:
   ```
   Name: denove-aps-frontend
   Root Directory: frontend
   Build Command: npm install && npm run build
   Publish Directory: dist
   ```
4. **Environment Variable:**
   ```
   VITE_API_URL = https://denove-aps-backend.onrender.com
   ```
   (Replace with your actual backend URL)
5. Click **"Create Static Site"**
6. Wait for deployment (~3 min)

---

### 4️⃣ Initialize Database (1 min)

1. Go to backend service dashboard
2. Click **"Shell"** tab
3. Run:
   ```bash
   cd backend
   python seed_data.py
   ```
   OR visit: `https://denove-aps-backend.onrender.com/seed_db`

---

### 5️⃣ Test (1 min)

1. Visit your frontend URL
2. Login with:
   - Username: `manager`
   - Password: `admin123`

---

## ✅ Done!

Your app is now live at:
- **Frontend**: `https://denove-aps-frontend.onrender.com`
- **Backend**: `https://denove-aps-backend.onrender.com`

---

## 🔧 Troubleshooting

**Backend won't start?**
- Check build logs
- Verify `gunicorn` is in `requirements.txt` ✅ (it is)
- Check environment variables are set

**Database connection error?**
- Use **Internal Database URL** (not external)
- Ensure database is running (not paused)

**Frontend can't connect?**
- Verify `VITE_API_URL` matches your backend URL exactly
- Check backend is running

**Need help?**
- See full guide: `RENDER_DEPLOYMENT.md`
- Render docs: https://render.com/docs

---

## 📝 Environment Variables Checklist

### Backend
- [ ] `DATABASE_URL` (from PostgreSQL)
- [ ] `SECRET_KEY` (random string)
- [ ] `JWT_SECRET_KEY` (random string)
- [ ] `FLASK_ENV=production`
- [ ] `UPLOAD_FOLDER=/opt/render/project/src/uploads`
- [ ] `MAX_CONTENT_LENGTH=5242880`

### Frontend
- [ ] `VITE_API_URL` (your backend URL)

---

**🎉 Happy Deploying!**
