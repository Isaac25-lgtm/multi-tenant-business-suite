# 🚀 DENOVE APS - Render Deployment Guide

Complete step-by-step guide to deploy DENOVE APS on Render.com

---

## 📋 Table of Contents

1. [Prerequisites](#prerequisites)
2. [Overview](#overview)
3. [Step 1: Prepare Your Repository](#step-1-prepare-your-repository)
4. [Step 2: Create PostgreSQL Database](#step-2-create-postgresql-database)
5. [Step 3: Deploy Backend Service](#step-3-deploy-backend-service)
6. [Step 4: Deploy Frontend Service](#step-4-deploy-frontend-service)
7. [Step 5: Configure Environment Variables](#step-5-configure-environment-variables)
8. [Step 6: Initialize Database](#step-6-initialize-database)
9. [Step 7: Test Deployment](#step-7-test-deployment)
10. [Troubleshooting](#troubleshooting)
11. [Production Considerations](#production-considerations)

---

## Prerequisites

- ✅ GitHub account with your repository pushed
- ✅ Render.com account (free tier available)
- ✅ Basic understanding of environment variables
- ✅ Your repository URL: `https://github.com/Isaac25-lgtm/multi-tenant-business-suite`

---

## Overview

We'll deploy three services on Render:

1. **PostgreSQL Database** - For production data storage
2. **Backend Web Service** - Flask API (Python)
3. **Frontend Static Site** - React application

**Estimated Cost:**
- Free tier: $0/month (with limitations)
- Paid tier: ~$7/month (PostgreSQL) + $7/month (Web Service) = ~$14/month

---

## Step 1: Prepare Your Repository

### 1.1 Create Production Configuration Files

#### Create `render.yaml` (Optional - for Blueprint deployment)

```yaml
services:
  - type: web
    name: denove-aps-backend
    env: python
    plan: starter
    buildCommand: pip install -r backend/requirements.txt
    startCommand: cd backend && gunicorn -w 4 -b 0.0.0.0:$PORT run:app
    envVars:
      - key: DATABASE_URL
        fromDatabase:
          name: denove-aps-db
          property: connectionString
      - key: SECRET_KEY
        generateValue: true
      - key: JWT_SECRET_KEY
        generateValue: true
      - key: FLASK_ENV
        value: production
      - key: UPLOAD_FOLDER
        value: /opt/render/project/src/uploads

  - type: web
    name: denove-aps-frontend
    env: static
    buildCommand: cd frontend && npm install && npm run build
    staticPublishPath: ./frontend/dist
    envVars:
      - key: VITE_API_URL
        value: https://denove-aps-backend.onrender.com

databases:
  - name: denove-aps-db
    plan: starter
    databaseName: denove_aps
    user: denove_user
```

#### Create `Procfile` for Backend

Create `backend/Procfile`:

```
web: gunicorn -w 4 -b 0.0.0.0:$PORT run:app
```

#### Update `backend/run.py` for Production

The current `run.py` needs to be updated for production. We'll create a production-ready version.

---

## Step 2: Create PostgreSQL Database

1. **Log in to Render Dashboard**
   - Go to https://dashboard.render.com
   - Sign up/Log in with GitHub

2. **Create New PostgreSQL Database**
   - Click **"New +"** → **"PostgreSQL"**
   - Configure:
     - **Name**: `denove-aps-db`
     - **Database**: `denove_aps`
     - **User**: `denove_user`
     - **Region**: Choose closest to your users
     - **Plan**: Free (or Starter for production)
   - Click **"Create Database"**

3. **Save Connection String**
   - Once created, go to database dashboard
   - Copy the **"Internal Database URL"** (for backend)
   - Copy the **"External Database URL"** (if needed)
   - Format: `postgresql://user:password@host:port/dbname`

---

## Step 3: Deploy Backend Service

### 3.1 Create Web Service

1. **Click "New +" → "Web Service"**

2. **Connect Repository**
   - Select **"Build and deploy from a Git repository"**
   - Connect your GitHub account if not connected
   - Select repository: `Isaac25-lgtm/multi-tenant-business-suite`

3. **Configure Service**
   - **Name**: `denove-aps-backend`
   - **Region**: Same as database
   - **Branch**: `main`
   - **Root Directory**: `backend`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn -w 4 -b 0.0.0.0:$PORT run:app`

### 3.2 Set Environment Variables

Click **"Environment"** tab and add:

```bash
# Database
DATABASE_URL=<from PostgreSQL service - Internal Database URL>

# Flask
SECRET_KEY=<generate a strong random string>
FLASK_ENV=production

# JWT
JWT_SECRET_KEY=<generate a strong random string>

# File Uploads
UPLOAD_FOLDER=/opt/render/project/src/uploads
MAX_CONTENT_LENGTH=5242880

# CORS (optional - for custom frontend URL)
ALLOWED_ORIGINS=https://denove-aps-frontend.onrender.com
```

**Generate Secret Keys:**
```bash
# Use Python to generate secure keys:
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

### 3.3 Deploy

- Click **"Create Web Service"**
- Render will build and deploy your backend
- Wait for deployment to complete (~5-10 minutes)
- Note your service URL: `https://denove-aps-backend.onrender.com`

---

## Step 4: Deploy Frontend Service

### 4.1 Create Static Site

1. **Click "New +" → "Static Site"**

2. **Connect Repository**
   - Select your GitHub repository
   - Branch: `main`

3. **Configure Build**
   - **Name**: `denove-aps-frontend`
   - **Root Directory**: `frontend`
   - **Build Command**: `npm install && npm run build`
   - **Publish Directory**: `dist`

### 4.2 Set Environment Variables

Add to **"Environment Variables"**:

```bash
VITE_API_URL=https://denove-aps-backend.onrender.com
```

**Important:** Replace with your actual backend URL from Step 3.

### 4.3 Deploy

- Click **"Create Static Site"**
- Wait for build and deployment
- Note your frontend URL: `https://denove-aps-frontend.onrender.com`

---

## Step 5: Configure Environment Variables

### Backend Environment Variables Summary

Ensure all these are set in your backend service:

| Variable | Description | Example |
|----------|-------------|---------|
| `DATABASE_URL` | PostgreSQL connection string | `postgresql://user:pass@host:5432/db` |
| `SECRET_KEY` | Flask secret key | `your-secret-key-here` |
| `JWT_SECRET_KEY` | JWT signing key | `your-jwt-secret-here` |
| `FLASK_ENV` | Environment mode | `production` |
| `UPLOAD_FOLDER` | File upload directory | `/opt/render/project/src/uploads` |
| `MAX_CONTENT_LENGTH` | Max upload size | `5242880` |

### Frontend Environment Variables

| Variable | Description | Example |
|----------|-------------|---------|
| `VITE_API_URL` | Backend API URL | `https://denove-aps-backend.onrender.com` |

---

## Step 6: Initialize Database

### Option 1: Using Render Shell (Recommended)

1. Go to your backend service dashboard
2. Click **"Shell"** tab
3. Run:

```bash
cd backend
python seed_data.py
```

### Option 2: Using Database Seeding Endpoint

1. Temporarily add a seeding route (for one-time use)
2. Visit: `https://denove-aps-backend.onrender.com/seed_db`
3. Remove the route after seeding

### Option 3: Manual Database Setup

1. Connect to PostgreSQL using a database client
2. Run migrations manually
3. Insert initial data

---

## Step 7: Test Deployment

### 7.1 Test Backend

1. **Health Check:**
   ```bash
   curl https://denove-aps-backend.onrender.com/api/auth/me
   ```
   Should return 401 (unauthorized) - this is expected

2. **Test Login:**
   ```bash
   curl -X POST https://denove-aps-backend.onrender.com/api/auth/login \
     -H "Content-Type: application/json" \
     -d '{"username":"manager","password":"admin123"}'
   ```

### 7.2 Test Frontend

1. Visit your frontend URL
2. Try logging in with demo credentials:
   - Username: `manager`
   - Password: `admin123`

### 7.3 Verify Database Connection

Check backend logs in Render dashboard to ensure database connection is successful.

---

## Troubleshooting

### Issue: Backend won't start

**Symptoms:** Service shows "Build failed" or "Deploy failed"

**Solutions:**
1. Check build logs for errors
2. Ensure `gunicorn` is in `requirements.txt`
3. Verify `Procfile` or start command is correct
4. Check Python version compatibility

### Issue: Database connection errors

**Symptoms:** "OperationalError" or "Connection refused"

**Solutions:**
1. Verify `DATABASE_URL` is set correctly
2. Use **Internal Database URL** (not external)
3. Ensure database is in same region
4. Check database is running (not paused)

### Issue: Frontend can't connect to backend

**Symptoms:** API calls fail, CORS errors

**Solutions:**
1. Verify `VITE_API_URL` is set correctly
2. Update CORS settings in backend
3. Check backend URL is accessible
4. Ensure backend service is running

### Issue: Static files not loading

**Symptoms:** 404 errors for assets

**Solutions:**
1. Verify build command completed successfully
2. Check `dist` folder exists after build
3. Ensure publish directory is `dist`
4. Check file paths in `index.html`

### Issue: Environment variables not working

**Symptoms:** Using default values instead of set variables

**Solutions:**
1. Restart service after adding variables
2. Verify variable names match exactly
3. Check for typos in variable names
4. Rebuild service

### Issue: Database migrations not running

**Symptoms:** Tables don't exist

**Solutions:**
1. Run `db.create_all()` in Python shell
2. Use Flask-Migrate if configured
3. Manually create tables
4. Check database permissions

---

## Production Considerations

### 1. Security

- ✅ Use strong, randomly generated secret keys
- ✅ Enable HTTPS (automatic on Render)
- ✅ Never commit secrets to repository
- ✅ Use environment variables for all sensitive data
- ✅ Regularly update dependencies
- ✅ Enable database backups

### 2. Performance

- **Database:**
  - Upgrade to paid PostgreSQL plan for better performance
  - Add database indexes for frequently queried fields
  - Enable connection pooling

- **Backend:**
  - Use multiple Gunicorn workers (already configured: `-w 4`)
  - Enable caching (Redis) for frequently accessed data
  - Optimize database queries

- **Frontend:**
  - Enable CDN for static assets
  - Optimize bundle size
  - Use lazy loading for routes

### 3. Monitoring

- Set up health check endpoints
- Monitor error logs in Render dashboard
- Set up uptime monitoring (UptimeRobot, Pingdom)
- Track API response times

### 4. Scaling

- **Horizontal Scaling:**
  - Add more backend instances
  - Use load balancer (Render handles this)

- **Database Scaling:**
  - Upgrade PostgreSQL plan
  - Add read replicas for heavy read workloads

### 5. Backup Strategy

- **Database Backups:**
  - Render provides automatic daily backups (paid plans)
  - Export database regularly
  - Store backups in separate location

- **File Backups:**
  - Upload folder files need separate backup solution
  - Consider using S3 or similar for file storage

### 6. Custom Domain

1. Go to your service settings
2. Click **"Custom Domains"**
3. Add your domain
4. Update DNS records as instructed
5. SSL certificate is automatic

---

## Quick Reference

### Service URLs

After deployment, you'll have:

- **Backend API**: `https://denove-aps-backend.onrender.com`
- **Frontend**: `https://denove-aps-frontend.onrender.com`
- **Database**: Internal connection only

### Important Commands

```bash
# Check backend logs
# (In Render dashboard → Logs tab)

# Restart service
# (In Render dashboard → Manual Deploy → Clear build cache & deploy)

# Access database shell
# (In Render dashboard → Database → Connect → psql)
```

### Environment Variables Template

Save this for reference:

```bash
# Backend
DATABASE_URL=postgresql://...
SECRET_KEY=...
JWT_SECRET_KEY=...
FLASK_ENV=production
UPLOAD_FOLDER=/opt/render/project/src/uploads
MAX_CONTENT_LENGTH=5242880

# Frontend
VITE_API_URL=https://denove-aps-backend.onrender.com
```

---

## Next Steps After Deployment

1. ✅ Test all functionality
2. ✅ Update CORS settings if needed
3. ✅ Set up monitoring
4. ✅ Configure custom domain (optional)
5. ✅ Set up automated backups
6. ✅ Update documentation with production URLs
7. ✅ Share access with team

---

## Support & Resources

- **Render Documentation**: https://render.com/docs
- **Render Status**: https://status.render.com
- **Render Community**: https://community.render.com
- **Project Repository**: https://github.com/Isaac25-lgtm/multi-tenant-business-suite

---

## Checklist

Before going live, ensure:

- [ ] Database is created and connected
- [ ] Backend service is deployed and running
- [ ] Frontend service is deployed and accessible
- [ ] All environment variables are set
- [ ] Database is seeded with initial data
- [ ] Login functionality works
- [ ] API endpoints are accessible
- [ ] CORS is configured correctly
- [ ] HTTPS is enabled (automatic)
- [ ] Error logging is working
- [ ] Backup strategy is in place

---

**🎉 Congratulations! Your DENOVE APS application is now live on Render!**

For questions or issues, refer to the troubleshooting section or check Render's documentation.
