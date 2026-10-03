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

## 5. Finance: Create Monthly-Accrual Loans

Path:

- `Finance -> Loans`

What monthly accrual means:

- Interest is added once per month for as long as the loan is unpaid.
- Example: if the monthly interest amount is `60,000`, then after 3 full months the interest charged becomes `180,000`.
- Interest stops on the day the loan is fully paid. A cleared loan never starts owing again.
- The exact day each month's charge starts follows the company setting (charged after each completed month, or first month charged on the issue date). Ask the system administrator if unsure.
- "Current due" is principal plus interest charged so far; "Balance" is what is still owed after payments.

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

- As you type the amount, the form shows how much goes to interest, how much to principal, and the balance after. Payments always go to interest first.
- Overpayments are blocked, and the same payment cannot be saved twice by double-clicking.
- The balance updates automatically after payment.

Mistakes (managers):

- Under `Payment History`, click `Reverse` next to a wrong payment and give a reason. The payment stays on record as reversed and the balance goes back to what it was.

Discounts, waivers and write-offs (managers):

- On the loan page, use `Adjustments -> Add adjustment`. Choose interest discount, interest waiver, principal write-off or additional charge, enter the amount and the reason.
- Balances are never edited directly. Every adjustment shows on the loan page, on the loan statement PDF and in the audit trail, and can be reversed with a reason.

Group loans:

- Periods paid are worked out from the total paid, so a part-payment does not count as a whole period.

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

- `backend/app/static/images/norongir-logo.png`

Used in:

- Public website branding
- Login page branding
- PDF and branded document headers

If the logo changes:

1. Go to `Website Management -> Settings`.
2. Upload the replacement logo.
3. Save.

## 9. Manager: Dashboard, Analytics And Expenses

- `Dashboard` shows today's sales, cash received, gross profit, net profit and interest earned, each compared with yesterday. It refreshes itself every minute.
  - Sales are the full value of goods sold (including credit). Cash received is money actually collected, including loan and hire payments.
  - Loan principal repaid is never counted as income.
- Click `Retail performance`, `Finance portfolio` or `Inventory` (or use the sidebar) for the detailed pages. Each has date filters: today, last 7 days, this month, last month or a custom range.
- `Expenses`: record rent, wages, transport and other costs with the date, category and business unit. Net profit only appears once expenses are being recorded, so it is never overstated.

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
