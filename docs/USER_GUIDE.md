# Denove APS User Guide

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
4. Upload the Denove logo if needed.
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

## 5. Finance: Create Monthly-Accrual Loans

Path:

- `Finance -> Loans`

What monthly accrual means:

- Interest grows every full month after the issue date.
- Example: if the monthly interest amount is `60,000`, then after 3 full months the accrued interest becomes `180,000`.
- The system refreshes the loan due amount automatically when the loan is viewed or processed.

How to create one:

1. Open `Finance -> Loans`.
2. Click `New Loan`.
3. Select the client.
4. Choose the monthly accrual interest mode.
5. Enter the principal.
6. Enter the monthly interest amount.
7. Use a monthly duration.
8. Save the loan.

Important note:

- Monthly accrual loans must use a monthly duration, not weekly duration.

## 6. Finance: Record Loan Payments

Path:

- `Finance -> Loans -> View Loan`

What happens:

- The system refreshes accrued interest before validating the payment.
- Overpayments are blocked.
- The balance updates automatically after payment.

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

Current shared logo:

- `backend/app/static/images/denove.jpg`

Used in:

- Public website branding
- Login page branding
- PDF and branded document headers

If the logo changes:

1. Go to `Website Management -> Settings`.
2. Upload the replacement logo.
3. Save.

## 9. Manager: Set Passwords For Users

Path:

- `Dashboard -> Users -> View/Edit User`

Use this when:

- A user account shows `needs password setup` on login
- A user forgot a password
- You are activating an older account that never had a password

## 10. Daily Operations Checklist

- Managers:
  - Review `Website Management -> Loan Inquiries`
  - Review `Website Management -> Order Requests`
  - Check `Website Management -> Settings` after branding changes

- Finance staff:
  - Update payer status for reliable and risky clients
  - Approve inquiries and link them to clients
  - Review monthly-accrual loans regularly

- All staff:
  - Use the account dropdown when signing in
  - Report any account marked `needs password setup`
