# Render Deployment Guide

This project is set up for Render using the root [render.yaml](../render.yaml) file.

## What The Render Setup Does

- Deploys the `backend/` folder as a Python web service
- Starts the app with Gunicorn using [backend/gunicorn.conf.py](../backend/gunicorn.conf.py)
- Runs database migration preparation and upgrades before deploy
- Exposes a health check at `/healthz`
- Stores uploaded files on a persistent disk mounted to the Flask static uploads directory
- Uses small-instance-friendly worker and connection pool settings

## Render Service Settings In This Repo

- Service name: `denove-aps`
- Branch: `main`
- Root directory: `backend`
- Region: `oregon`
- Plan: `starter`
- Instances: `1`

## Important Paths

- App root on Render: `backend/`
- Persistent upload disk mount:
  - `/opt/render/project/src/backend/app/static/uploads`

That path is important because product images, profile pictures, website images, and collateral uploads must remain inside the Flask static directory to be served correctly.

## Required Manual Environment Variables

Set these in the Render dashboard if they are not already set:

- `DATABASE_URL`

This repo already defines or generates:

- `FLASK_ENV=production`
- `PYTHON_VERSION=3.11.11`
- `PYTHONUNBUFFERED=1`
- `SESSION_COOKIE_SECURE=1`
- `SECRET_KEY` with `generateValue: true`

## How To Deploy On Render

1. Push this repo to GitHub.
2. Open Render.
3. Create a new Blueprint service from the GitHub repo.
4. Confirm the service name is `denove-aps`.
5. Set `DATABASE_URL` to your Render Postgres database or other PostgreSQL instance.
6. Apply the Blueprint.
7. Wait for the pre-deploy migration commands to complete.
8. Visit `/healthz` after deploy to confirm the service is healthy.

## Post-Deploy Checklist

After each deploy, verify:

1. `/healthz` returns `200`
2. The homepage loads
3. Login page loads with the account dropdown
4. Website settings page saves correctly
5. Uploaded logo or product images still load
6. Finance loan pages open correctly
7. Website loan inquiry approval still links clients into Finance

## Why The App Uses One Instance

The Render config intentionally uses `numInstances: 1` because uploads are stored on a persistent disk attached to the web service. This keeps uploaded files available across restarts without introducing cross-instance file consistency problems.

## If You Change The Logo Or Upload Handling

Keep uploads inside:

- `backend/app/static/uploads`

If that path changes in Flask code, update both:

- `render.yaml`
- the upload handling code

## If Deploy Fails

Check these first:

1. `DATABASE_URL` is set
2. The migration command succeeds
3. `SECRET_KEY` exists
4. The health check path is still `/healthz`
5. The persistent disk mount path still matches the Flask static upload path
