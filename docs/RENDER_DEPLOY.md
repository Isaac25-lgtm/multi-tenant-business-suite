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

Set these in the Render dashboard - they are **not** auto-generated:

- `DATABASE_URL` - Your Render PostgreSQL connection string
- `SECRET_KEY` - A stable random string, 64+ characters. Generate one with:
  ```
  python -c "import secrets; print(secrets.token_urlsafe(64))"
  ```
  **Important:** Do NOT use `generateValue: true` - that creates a new key on every deploy, which breaks encrypted data (customer NINs, loan client NINs).

This repo already defines:

- `FLASK_APP=run:app`
- `FLASK_ENV=production`
- `PYTHON_VERSION=3.11.11`
- `PYTHONUNBUFFERED=1`
- `SESSION_COOKIE_SECURE=1`

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

## Pre-Deploy Sequence

The `preDeployCommand` in `render.yaml` runs three steps in order:

1. `python -m flask --app run:app db-ensure` - Checks whether the database is safely ready for migrations.
   - Empty DB: passes (upgrade will create everything).
   - Already versioned: passes.
   - Has tables but no Alembic tracking: **fails with instructions** (prevents silently stamping a mismatched schema as current).
2. `python -m flask --app run:app db upgrade` - Applies all pending Alembic migrations.
3. `python -m flask --app run:app db-doctor` - Verifies every production-critical table and column exists.
   If anything is missing, the deploy **fails before the new code goes live**.

## Diagnosing Existing Schema Drift

If your Render database was previously stamped at HEAD but is actually missing tables or columns (causing 500 errors), run this from the Render Shell:

```bash
python -m flask --app run:app db-doctor
```

If it reports missing items:

1. Check your current Alembic version:
   ```bash
   python -m flask --app run:app db current
   ```
2. If the version is at HEAD but items are missing, the DB was falsely stamped.
   Fix it by stamping the **actual** last-applied revision and re-running upgrade:
   ```bash
   python -m flask --app run:app db stamp 4694bf24ca95    # baseline example - adjust to your actual state
   python -m flask --app run:app db upgrade               # applies the missing migrations
   python -m flask --app run:app db-doctor                # verify everything is now present
   ```

## If Deploy Fails

Check these first:

1. `DATABASE_URL` is set to a PostgreSQL connection string
2. `SECRET_KEY` is set to a stable 64+ char string (not auto-generated)
3. The migration command succeeds (`python -m flask --app run:app db upgrade`)
4. `python -m flask --app run:app db-doctor` passes
5. The health check path is still `/healthz`
6. The persistent disk mount path still matches the Flask static upload path
