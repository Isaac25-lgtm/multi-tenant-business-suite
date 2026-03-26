# Denove APS

Denove APS is a Flask-based business suite for boutique sales, hardware sales, finance loans, customer management, and a public storefront with website management controls.

## What Is Included

- Boutique and hardware stock, sales, and credit tracking
- Finance clients, individual loans, group loans, payments, and PDF agreements
- Public storefront for products and loan inquiries
- Website Management for branding, logo, contact info, publishing products, and inquiry handling
- User accounts with role-based access
- Audit logging, CSRF protection, rate limiting, and Render-ready deployment settings

## Recent Improvements

- Denove branding and shared logo support
- Website settings page for logo, company details, and public loan settings
- Monthly-accrual loan support
- Finance client payer highlighting: good payer, poor payer, or unmarked
- Auto-linking of approved website loan inquiries into the finance client list
- Login dropdown so users can choose their account name and enter a password
- Render deployment tuning, health checks, persistent uploads, and Gunicorn config

## Quick Start

1. Open a terminal in `backend/`.
2. Create and activate a virtual environment.
3. Install dependencies:

```bash
pip install -r requirements.txt
```

4. Apply migrations:

```bash
python -m flask --app run:app db upgrade
```

5. Run the app:

```bash
python run.py
```

6. Open `http://127.0.0.1:5000/`

## Login

- The login page now shows an account dropdown instead of requiring users to type usernames.
- Users select their account name and then enter their password.
- If an account shows `needs password setup`, a manager must open that user in the manager area and set a password before the user can sign in.

## Documentation

- User guide: [docs/USER_GUIDE.md](docs/USER_GUIDE.md)
- Render deployment guide: [docs/RENDER_DEPLOY.md](docs/RENDER_DEPLOY.md)
- Local environment example: [backend/.env.example](backend/.env.example)

## Deployment

This repo includes [render.yaml](render.yaml) for Render Blueprint deployments and [backend/gunicorn.conf.py](backend/gunicorn.conf.py) for production startup tuning.

Expected public service name:

- `denove-aps`

Typical default Render URL:

- `https://denove-aps.onrender.com`

## Repo

- GitHub: `https://github.com/Isaac25-lgtm/multi-tenant-business-suite`
