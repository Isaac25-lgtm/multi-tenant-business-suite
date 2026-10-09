# NoRongir Investments Limited — User Guide

This guide explains the main workflows added and updated in the system.

## 1. Signing In

1. Open the login page.
2. Choose your account from the dropdown list.
3. Enter your password.
4. Click `Sign In`.

Notes:

- If your account says `needs password setup`, ask a manager to set a password for you.
- Managers can set passwords from the manager user edit screen.

## 2. Manager: Set Up Website Branding And Public Loan Settings

Path:

- `Website Management -> Settings`

What you can control there:

- Company name and suffix
- Tagline and homepage text
- Contact phone, WhatsApp, and email
- Public loan interest rate shown on the website
- Loan amount range and approval turnaround message
- Shared logo used on the website and branded documents

How to use it:

1. Open `Website Management`.
2. Click `Settings`.
3. Update the branding or public loan values you want.
4. Upload the company logo if needed.
5. Save changes.

## 3. Manager Or Finance: Approve Website Loan Inquiries And Add Them To Finance Clients

Path:

- `Website Management -> Loan Inquiries`

How it works:

- A person submits a loan inquiry on the public website.
- Staff open the inquiry detail page.
- When the inquiry is approved, the checkbox for adding the person to the finance client list is available.
- If checked, the system creates a new finance client or links to an existing one with the same phone number.

Recommended workflow:

1. Open `Website Management -> Loan Inquiries`.
2. Click `Review Now` or `View`.
3. Read the applicant details.
4. Change the status to `Approved`.
5. Leave `add or link this applicant to the Finance client list` checked.
6. Save.
7. Open `Finance -> Clients` to confirm the person is available there.

## 4. Finance: Mark Good Payers And Poor Payers

Path:

- `Finance -> Clients`

What this does:

- Good payers are highlighted in green.
- Poor payers are highlighted in red.
- Unmarked clients keep the default appearance.
- These labels also show in the loans list and loan detail pages.

How to set a status for a client:

1. Open `Finance -> Clients`.
2. Add a new client or click `Edit` on an existing one.
3. Choose one of:
   - `Unmarked`
   - `Good Payer`
   - `Poor Payer`
4. Save.

How to filter clients:

- Use the buttons at the top of the client list:
  - `All`
  - `Good Payers`
  - `Poor Payers`
  - `Unmarked`

## 5. Finance: Issue A Loan

Path:

- `Finance -> Individual Loans -> New loan`

How interest works (every individual loan):

- The rate is **per month** (the company rate is 15%).
- The first month's interest is charged on the day the loan is issued. Each later month is charged the day after the monthly date passes.
- Interest is charged on the **unpaid principal**, so it goes down when principal is repaid. Example: 1,000,000 at 10% is 100,000 a month; after 500,000 of principal is repaid the next month is 50,000.
- Interest keeps adding every month after the due date until the loan is fully paid, then stops. A cleared loan never starts owing again.
- "Current due" is principal plus all interest charged so far; "Balance" is what is still owed after payments.

How to issue one:

1. Click `New loan` and choose the borrower.
2. Enter the principal. The plan is `Monthly interest` and the rate is filled in from the company rate; change it only if this loan has a different rate.
3. Enter the duration and click `Preview Agreement` to check the figures and upload collateral, then issue.

## 6. Finance: Record Loan Payments

Path:

- `Finance -> Individual Loans -> Record payment`

What happens:

- As you type the amount, the form shows how much goes to interest, how much to principal, and the balance after. Payments always go to interest first.
- Choose how it was paid (cash, mobile money, bank) and enter the reference number if there is one.
- Overpayments are blocked, and the same payment cannot be saved twice by double-clicking.
- If a manager enters an older payment late, the system re-works the later payments in date order automatically.

Mistakes (managers):

- Under `Payment History`, click `Reverse` next to a wrong payment and give a reason. The payment stays on record as reversed.

Discounts and write-offs (managers only):

- On the loan page, use `Adjustments -> Add adjustment`. A discount or waiver reduces **interest** only.
- Principal can be written off only once a loan is 6 months overdue.
- Every adjustment needs a reason, shows on the loan statement and audit trail, and can be reversed.

Renewals:

- The borrower pays the interest owed in cash; the remaining principal carries into a new loan starting from the old due date.

Deleting loans:

- Only managers can delete a loan.

Group loans:

- The total to repay is fixed and is paid in equal instalments (for example 1,400,000 over 14 weeks is 100,000 a week). Each instalment is part principal and part interest. Nothing extra is added when a group is late.

Reminders:

- `Finance -> Reminders` lists loans due within 3 days and overdue loans, with the message already written. `WhatsApp` opens the chat ready to send. `SMS` appears once the SMS account has been set up.

## 7. Website Management: Publish Products To The Public Website

Path:

- `Website Management -> Products`

How to use it:

1. Choose a boutique or hardware product.
2. Publish it.
3. Optionally set a public price and featured flag.
4. Save.

Only published items appear on the public website.

## 8. Logo And Branded Documents

Current shared logo (temporary until the final NoRongir logo is ready):

- `backend/app/static/images/norongir-logo.png` (square), plus `norongir-logo-horizontal.png` and `norongir-logo-mono.png` (one colour, for printing)

Used in:

- Public website branding
- Login page branding
- PDF and branded document headers

If the logo changes:

1. Go to `Website Management -> Settings`.
2. Upload the replacement logo.
3. Save.

## 9. Dashboard, Analytics, Expenses And The Monthly Report

- `Dashboard` (managers) shows today's sales, cash received, gross profit, net profit and interest earned, each compared with yesterday. It refreshes itself every minute.
  - Sales are the full value of goods sold (including credit). Cash received is money actually collected, including loan and hire payments.
  - Loan principal repaid is never counted as income.
- Click `Retail performance`, `Finance portfolio` or `Inventory` (or use the sidebar) for the detailed pages. Each has date filters: today, last 7 days, this month, last month or a custom range.
- `Expenses`: every unit records its own costs. Staff record expenses for their own unit (today or yesterday); managers can record for any unit and any date, and only managers can delete.
- `Monthly report`: on the dashboard, pick a month and click `Download PDF`. It compares that month with the two before it: sales, gross profit, expenses, net profit, the three businesses side by side, weekly profit, stock, and the best and least selling products.

Receipts:

- Staff may change item descriptions or customer details on a receipt, but the amounts must match the recorded sale. Only a manager can issue a receipt with different amounts; it is stamped `EDITED COPY` and logged.

## 10. Manager: Set Passwords For Users

Path:

- `Dashboard -> Users -> View/Edit User`

Use this when:

- A user account shows `needs password setup` on login
- A user forgot a password
- You are activating an older account that never had a password

## 11. Daily Operations Checklist

- Managers:
  - Review `Website Management -> Loan Inquiries`
  - Review `Website Management -> Order Requests`
  - Check `Website Management -> Settings` after branding changes
  - Record the day's expenses
  - Review `Finance Analytics` for overdue loans

- Finance staff:
  - Update payer status for reliable and risky clients
  - Approve inquiries and link them to clients
  - Review monthly-accrual loans regularly

- All staff:
  - Use the account dropdown when signing in
  - Report any account marked `needs password setup`
