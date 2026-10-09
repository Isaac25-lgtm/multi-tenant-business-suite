# Handoff: NoRongir maintenance (Phase 1 + most of Phases 2–3)

**Repo:** `Isaac25-lgtm/multi-tenant-business-suite` · **Branch:** `maintenance/phase-1` · **Commit:** `b63a819` (pushed)
**Do not merge to `main`.** Render auto-deploys `main`; the new migrations must first be rehearsed on a production copy (see §6).

---

## 1. Working environment

| Item | Value |
|---|---|
| App | Flask 3 + SQLAlchemy 2.1.2 + Alembic, server-rendered Jinja, PostgreSQL only |
| Local DB | PostgreSQL 18 on `localhost:5432`, database `denove_aps` (creds in `backend/.env`, git-ignored) |
| Test DB | `denove_aps_test` — **wiped by every integration test run** |
| Python | `backend/venv` (3.12 locally; Render uses 3.11 from `.python-version`) |
| Run | `cd backend && venv\Scripts\activate && python run.py` → http://localhost:5000 |
| Tests | `python -m pytest -q` (unit only) · `TEST_DATABASE_URL=postgresql://postgres:<pw>@localhost:5432/denove_aps_test python -m pytest -q` (all 107) |
| Lint | `ruff check .` (config `backend/ruff.toml`, error-class rules only) |
| CSS | Compiled Tailwind v3.4.19 → `app/static/css/tailwind.css`. **Rebuild after adding classes:** `tailwindcss -c tailwind.config.js -i app/static/css/src/tailwind.css -o app/static/css/tailwind.css --minify` (standalone CLI, no Node). Dynamic class names (`text-{{x}}-600`) will not be picked up — write full class names. |

**Uncommitted local change (keep it out of commits):** a localhost-only password bypass lives in 5 files that show as modified: `backend/.env.example`, `app/__init__.py`, `app/config.py`, `app/modules/auth/__init__.py`, `app/templates/auth/login.html`. It needs `DEV_LOGIN_BYPASS=1` **and** `FLASK_DEBUG=1`, and is disabled on Render/production. The user chose to keep it off GitHub. When committing, stage files explicitly or `git stash` these first.

---

## 2. What was agreed (Codex + Claude reviews)

- Keep the stack: Flask + PostgreSQL + Jinja + compiled Tailwind (+ selective HTMX later). No rewrite.
- Accounting correctness first, presentation second. One authoritative calculation per figure, in `app/services/`.
- Don't change live balances without reconciliation; don't mass-convert historical loans.
- Monthly-interest timing, renewal-interest treatment, group allocation rule and discount policy are **client decisions** — implemented as configurable/neutral, defaulting to existing behaviour.

---

## 3. What is done

### 3.1 Architecture
- `app/services/loan_accounting.py` — single source for loan maths: refresh (idempotent), interest-first allocation, payment preview, reversals, adjustments, group refresh, portfolio and table subtotals.
- `app/services/business_metrics.py` — sales vs cash vs gross/net profit vs interest earned; manager dashboard data.
- `app/services/analytics.py` — retail / finance-portfolio / inventory drill-downs.
- `app/services/periods.py` — shared period filter with like-for-like comparison periods.
- `app/cli.py` — ops commands (§5). `app/monitoring.py` — optional Sentry. `app/utils/integrity.py` — duplicate-submission guard.

### 3.2 Client's 7 requests
| # | Request | Status |
|---|---|---|
| 1–2 | Rename to NoRongir Investments Limited, email `norongir@gmail.com` | Done. All page titles/assistant/PDF text read `site_settings`; defaults + data migration `f2a3b4c5d6e7`; temp logo `static/images/norongir-logo.png`, favicon, touch icon; old Denove logos deleted |
| 3 | Individual-loan subtotals (Principal, Current Due, Balance) | Done (`loan_table_totals`, follows filters) |
| 4 | Separate group-loan subtotal | Done (`group_table_totals`) |
| 5 | Overview includes group principal | Done: individual / group / combined principal, interest, balance |
| 6 | Unpaid months accumulate (×3 for 3 months) | Done for `monthly_accrual`; timing via `MONTHLY_ACCRUAL_TIMING` (`arrears` default = charge on each anniversary; `advance` = first month at issue, then day *after* each anniversary). **Client must confirm which.** |
| 7 | Balances not accumulating | Root causes fixed in code (settled loans reopening; renewed loans reopening on view). Likely also data: most loans are `flat_rate` (form default + 2026-03 backfill). Verify with `finance-audit` on production. |

### 3.3 Accounting fixes
- **Critical:** paid monthly-interest loans reopened every month. Fixed via `Loan.settled_on`; accrual stops there. Migration backfills `settled_on` only for loans currently `paid`/`renewed` (no live balance change).
- Month anniversaries anchored on issue date (31 Jan → 28 Feb → 31 Mar). Minor behaviour change on month-end dates only.
- Payment reversal (manager-only, reason required, kept as `is_deleted` + `reversed_*` fields) for individual and group payments.
- Adjustments ledger `LoanAdjustment` (interest discount / waiver / principal write-off / charge), manager-only, reversible, running totals on `loans` and `group_loans` (`interest_waived`, `principal_written_off`, `charges_added`), shown on loan page and statement PDF. Interest discounts blocked on reducing-balance loans (allocation path would be inconsistent).
- Group "periods paid" derived from money paid (1 UGX tolerance); manual `periods_covered` field removed.
- Group interest income computed principal-first (current group rule) in `group_interest_collected`.
- Edit-loan-dates now recomputes via the service.
- Renewal settlements are reported separately and **not counted as cash** pending the client's renewal rule.

### 3.4 Retail / integrity / security
- `unit_cost_at_sale` snapshot on sale items; profit uses it; legacy rows flagged "estimated", stock-less items "unknown" (not 100% margin).
- Sale totals no longer include items not found in stock (bug). Part-payment `amount_paid` validated.
- Row locks + 2-minute identical-payment guard on loan, group, credit and hire payments; JS disables submit buttons briefly.
- Deleting a sale/hire twice no longer restores stock twice. Hire payments: overpayment + date-permission checks.
- Receipts: staff may edit descriptions; amounts must match the sale unless manager (stamped `EDITED COPY`, audited).
- Collateral/OCR files under `static/uploads/{collateral,ocr}` blocked from public static serving (path-normalised check); OCR preview served via authenticated `/ai/ocr/<id>/file`.
- `PII_ENCRYPTION_KEY` (MultiFernet; legacy SECRET_KEY-derived key still decrypts); undecryptable tokens return `None` instead of ciphertext.
- Audit log works outside requests and logs failures. Public order/inquiry save failures are logged.
- Fixed pre-existing crash: product photo upload on stock edit (`get_local_now` not imported).
- Removed: DuckDuckGo image scraper + `duckduckgo-search`; the manager AI chatbot (routes, widget, `chat_engine.py`, `chat.html`). `ChatMessage` model/table kept so history isn't dropped. Morning briefing and OCR kept.

### 3.5 Dashboard, analytics, expenses
- Dashboard: Sales, Cash received, Gross profit (retail), Net profit (only once expenses exist), Interest earned, receivables, loan principal outstanding, inventory; like-for-like vs yesterday; whole-card links to drill-downs; 7-day table; auto-refresh every 60 s via `/dashboard/summary` (server-rendered fragment); explicit error state instead of zeros. No recent-sales/alerts strips (client removed them).
- Drill-downs: `/dashboard/retail` (unit/branch filters, trend, top/slow items), `/dashboard/finance` (aging buckets, PAR30 vs final due date, collections, status counts, adjustments, 6-month trend, largest overdue), `/dashboard/inventory`. Collection rate deliberately not shown (needs per-instalment schedules).
- Expenses: `Expense` model, `/expenses` (manager-only), categories/business units, soft delete with reason. Net profit = gross profit + interest earned + hire income − expenses − principal write-offs.

### 3.6 UI
- Finance overview, individual and group loan lists redesigned: search, status filter tabs, one primary action + `⋯` menu, collapsible help instead of long guides, mobile card layout (`.responsive-table` with `data-label`), no row tinting by payer status.
- Loan payment form shows server-calculated interest/principal split and balance-after while typing (`/finance/loans/<id>/payment-preview`, read-only).
- New shared components: `templates/_macros.html` (kpi, ugx, pct, change), `templates/_period_filter.html`, CSS sections at end of `static/css/style.css` (KPI cards, drill cards, list toolbar, action menu, period filter, payment preview).
- Tailwind CDN script replaced by compiled CSS (loaded after `style.css` to keep old precedence). Web app manifest + theme colour (installable on phones).

### 3.7 Stack / ops
- `SQLAlchemy==2.1.2` pinned; plain `postgres://`/`postgresql://` URLs rewritten to `postgresql+psycopg2://` (2.1 defaults to psycopg v3, which isn't installed — a fresh Render build would otherwise fail to connect).
- `gunicorn` stays at **21.2.0** (what production runs). The upgrade to a supported release (26.x) was reverted because it could not be tested on Linux and there is no staging; do it once a staging environment exists.
- `sentry-sdk[flask]==2.71.0`, off unless `SENTRY_DSN`; scrubs form data, cookies, auth headers, user.
- `.github/workflows/tests.yml` (Postgres 16 service: migrate, doctor, downgrade, ruff, pytest), `.github/dependabot.yml`, `docker-compose.yml` (+ `docker/create-test-db.sql`), `requirements-dev.txt` (pytest, ruff 0.16.10).
- `render.yaml`: added `PII_ENCRYPTION_KEY`, `MONTHLY_ACCRUAL_TIMING=arrears`, `SENTRY_DSN`, `OCR_MODEL` (all `sync:false` except timing).
- `.env.example` OCR model example now `claude-haiku-4-5` (old `claude-3-5-haiku-latest` is retired).
- README and `docs/USER_GUIDE.md` updated.

### 3.8 Migrations (in order, after existing head `d8e9f0a1b2c3`)
| Revision | Purpose | Live data effect |
|---|---|---|
| `e1f2a3b4c5d6` | `loans.settled_on`, payment `reversed_*`, `unit_cost_at_sale` | Backfills `settled_on` for currently paid/renewed loans only |
| `f2a3b4c5d6e7` | Rebrand saved `website_settings` | Sets name/suffix/email; replaces "Denove" in text fields; retired logo paths → new logo (uploaded logos kept) |
| `a3b4c5d6e7f8` | `loan_adjustments` + running totals | None (zeros) |
| `b4c5d6e7f8a9` | `expenses` | None |

Full chain verified locally: empty DB → upgrade → `db-doctor` (35/35) → downgrade base.

---

## 4. Key definitions (keep consistent everywhere)

- **Current due** = principal + interest charged to date (+ charges). **Balance** = outstanding principal + outstanding interest (after payments, waivers, write-offs).
- **Sales** = full sale value on sale date (credit included). **Cash received** = cash at counter (amount_paid − later credit payments) + credit collections + hire deposits/payments + loan & group collections (renewal settlements excluded). Loan principal is never income.
- Payments are interest-first for individual loans; group loans are principal-first (existing rule, awaiting client confirmation).
- Money stays `Decimal` in services; templates format only.

---

## 5. Ops commands (`python -m flask --app run:app <cmd>`)

| Command | Use |
|---|---|
| `finance-audit [--csv f]` | Read-only; flags `reopened_after_settlement`, `flat_rate_monthly_term`, `legacy_payment_split`, `interest_overpaid` |
| `finance-backfill-settlement [--apply]` | Repairs loans reopened by the old bug; skips (lists) loans paid further after reaching zero |
| `refresh-loans` | Idempotent recalculation (optional daily Render cron) |
| `pii-reencrypt [--apply]` | After setting `PII_ENCRYPTION_KEY`; keep `SECRET_KEY` unchanged until done |
| `db-doctor` | Schema check (now includes new columns) |

---

## 6. Pending

### 6.1 Blocked on the client
1. Monthly-interest timing: `arrears` vs `advance` (switching changes live balances).
2. Renewal: is outstanding interest paid in cash, waived, or carried over? (Currently recorded as paid, reported separately, not counted as cash.)
3. Group loans: interest-first or principal-first? Should they accrue monthly too?
4. Discount policy (mechanism exists; rules/limits don't).
5. Receipt prefixes still `DNV-B-` / `DNV-H-` / `DNV-HR-` — rename?
6. Finance staff (not only managers) can delete loans — intended?
7. Final logo (horizontal + one-colour + square icon) and real product photos.

### 6.2 Blocked on production access (in this order)
1. Production backup + tested restore.
2. Staging copy (prefer anonymised; own keys). Run migrations there.
3. `SHOW timezone;` on production DB and compare `created_at` against known events (timestamps are naive; local DB is Africa/Nairobi, Render likely UTC) → then design the UTC migration.
4. `finance-audit --csv`; review flags with the client; `finance-backfill-settlement` dry run → `--apply` after sign-off. Convert misclassified flat-rate loans only with client-verified monthly amounts.
5. Set `PII_ENCRYPTION_KEY`, run `pii-reencrypt --apply`.
6. Check Render `OCR_MODEL` (if `claude-3-5-haiku*`, OCR is broken → `claude-haiku-4-5`).
7. Verify Gunicorn 26.2.0 boots on Render staging.
8. If the manager uploaded the old Denove logo via Website Settings, it still shows — re-upload or reset.
9. Merge to `main` only after the above.

### 6.3 Doable now (next work)
1. Restyle remaining staff pages to the new components: boutique/hardware index, sales, sale form, stock, credits, hires, customers, finance clients, finance payments, users, website management. Remove inline styles (~640 `style=` attributes originally) into shared CSS.
2. Storefront: loan calculator (after rule #1 is confirmed); separate boutique/hardware browsing; real photos with consistent ratios.
3. Backdated payments: allocation uses cumulative totals, so out-of-order backdated payments can misallocate interest/principal. Consider chronological re-allocation (manager-only path; staff are limited to yesterday).
4. Reversal for retail credit payments and hire payments (only loan/group reversals exist).
5. Serialise money as strings/integers in `to_dict()` (currently floats; presentation-only today).
6. Playwright: ~5 durable journeys (login, sale, credit payment, loan payment, reversal) using labels/ids.
7. Analytics performance: retail trend runs per-day summaries (dozens of queries for a month); fine at current volume, batch with GROUP BY if it slows.
8. Reference numbers use last-id+1 (race under concurrency) — low risk at this scale.
9. Decide whether to drop the `chat_messages` table (kept intentionally).
10. Some authorisation checks use the session's section rather than the user's role (no escalation found; consistency clean-up).

---

## 7. Gotchas
- Integration tests **drop and recreate** whatever `TEST_DATABASE_URL` points at; the fixture refuses names without "test".
- `conftest.py` normalises the test URL with `normalize_postgres_url`.
- Git Bash rewrites args like `/dashboard/` into Windows paths — use `MSYS_NO_PATHCONV=1` for scripts that take URL paths.
- Demo/screenshot helpers used during this work live outside the repo (Claude scratchpad); not needed.
- `askReversalReason(form, question)` in `main.js` is shared by payment reversal, adjustment reversal and expense deletion.

---

## 8. Round 3 (9 Oct 2026): client's answers applied

The client answered the questionnaire. Rules now in code (all tested; 134 tests):

| Answer | Implemented as |
|---|---|
| Option B; interest falls when principal is repaid; keeps adding after due date | `MONTHLY_ACCRUAL_TIMING` default `advance`; `accrued_interest` charges `rate x unpaid principal` on each charge date (`monthly_charge_dates`, `principal_reductions`); stops at `settled_on` |
| "15% is monthly; all loans accumulate" | Loan forms offer Monthly interest (default, rate from site settings) and Reducing balance only; a `flat_rate` request is issued as monthly. `flask finance-convert-flat-loans [--apply]` converts **open** flat loans and replays their payments. Paid/renewed flat loans untouched |
| Late charge: monthly interest only | No 5%/week engine; agreement terms state the real rule |
| Renewal interest is paid in cash | Renewal payments count as cash and interest income |
| Group instalment is "a sum of both"; no accrual; part-payment not late | Pro-rata principal/interest split (`GroupLoan.outstanding_principal`, `group_interest_collected`) |
| Discounts: managers, interest only; write-off after 6 months | Principal write-off blocked until 180 days overdue (`WRITE_OFF_MIN_DAYS_OVERDUE`) |
| Only managers delete loans | `delete_loan` / `delete_group_loan` are `@manager_required` |
| Keep `DNV-` receipt prefix; hire deposit is part-payment | Unchanged |
| Record payment method + reference | `payment_method`, `payment_reference` on all payment tables and sales; `payment_fields()` macro |
| Staff record expenses; each unit carries its own | Staff limited to their unit and today/yesterday; no "shared" unit; `unit_profit` per business |
| Monthly PDF, 3-month comparison | `/dashboard/reports/monthly?month=YYYY-MM` (`services/monthly_report.py`, `utils/report_pdf.py`) |
| SMS + WhatsApp reminders | `/finance/reminders`, `services/reminders.py`, `reminder_logs`, `flask send-loan-reminders`. SMS via Africa's Talking when `AT_USERNAME`/`AT_API_KEY` set; WhatsApp is click-to-chat |
| Colours maroon + light grey; registration no.; address | Palette in CSS variables; logo set in `static/images/`; `registration_number`, `postal_address` on site settings and every PDF header |
| No product photos | Generated name tiles in the shop; upload from stock Edit |
| Public calculator + rate | In the shop's loans section |
| Delete chat history | Migration `c5d6e7f8a9b0` drops `chat_messages` |

Also new: `replay_loan_payments` (date-ordered re-allocation, used for backdated payments, reversals,
adjustments and the conversion), site-wide collapsible help and phone-friendly tables (`main.js`).

Migration added: `c5d6e7f8a9b0` (payment method columns, registration fields, `reminder_logs`, drops `chat_messages`).

### Still pending after round 3
- **Go-live steps on production:** backup, rehearse migrations on a copy, `finance-audit`, then
  `finance-convert-flat-loans` (review the dry run with the client before `--apply`), `pii-reencrypt`.
- **Needs accounts/purchases:** Africa's Talking keys for SMS; a domain name; a designer's final logo
  (the current set is generated); real product photos.
- **Staff accounts** from answer 34 are created by the manager under Users (Chepkwemoi Femia's role was not stated).
- UTC timestamp migration; Playwright journeys; restyling remaining pages beyond the shared mobile/help pass.

### Go-live without server access (9 Oct 2026)
The team could not reach the client's Render account, so the release was made safe to deploy by a plain push to `main`:
- Migration `e1f2a3b4c5d6` first copies every existing table into the `pre_upgrade_snapshot` schema (original figures stay readable; drop it later with `DROP SCHEMA pre_upgrade_snapshot CASCADE`).
- The same migration closes loans that were fully paid and then re-opened by the old accrual bug (payment reached zero, nothing paid after, principal fully repaid).
- Settled loans are frozen in `refresh_loan_state`, so the switch to "first month on issue day" never reopens a loan paid under the old rule.
- Managers convert open flat-rate loans from **Finance > Review and convert** (`/finance/convert-flat-loans`): preview, type CONVERT, apply. No shell needed.
- Rehearsed locally: old-version database with legacy records -> upgrade -> 31 tables unchanged, 75 pages open, figures as expected; 136 tests pass on Python 3.12 and on a fresh Python 3.11 install.
- Effect on open monthly-interest loans at deploy: each gains the issue-day month (the client's Option B), so their balances rise by one month's interest.
