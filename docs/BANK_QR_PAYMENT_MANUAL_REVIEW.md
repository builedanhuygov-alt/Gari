# GARI AI LAB — Vietnamese Bank QR Payment & Manual Admin Verification

## 1. Overview & Architecture

### Overview
GARI AI LAB employs a **Vietnamese Bank QR payment workflow (VietQR / NAPAS 24/7)** with **server-side manual admin review and approval**. This flow eliminates reliance on external third-party webhook services while maintaining strict zero-trust security and financial reconciliation standards.

### Key Architectural Pillars
1. **Static VietQR / MoMo QR Payment Asset:**
   - Employs the provided static VietQR/MoMo payment image (`frontend2/images/vietqr_momo.jpg`) as an immutable static asset.
   - Preserved as an unaltered visual asset: no regeneration, redrawing, or dynamic modification of the QR contents.
   - Displayed alongside recipient details visible on the QR card:
     * **Network / Method:** MoMo / VietQR (NAPAS 24/7)
     * **Beneficiary Name:** `BUI LE DAN HUY`
     * **Beneficiary Account / Identifier:** `*******193`
   - Server-side canonical pricing strictly enforced:
     * **Personal Plan:** 129,000 VND / month
     * **Business Plan:** 299,000 VND / month
2. **Order Reference Linked to Authenticated User's UID:**
   - Format: `GARI-U<user_id>-<order_code>` (e.g. `GARI-U42-84920155`).
   - **Do not use UID alone:** Using the user's UID alone is strictly forbidden because a customer may purchase multiple subscriptions, renewals, or add-ons over time. The combined format guarantees absolute uniqueness per purchase order while linking back to the user account.
3. **User Action: "I have transferred" (`pending_review`):**
   - After completing the transfer in their banking app, the user clicks **"Tôi đã chuyển khoản"**.
   - Transitions order status from `pending` to `pending_review`.
   - **CRITICAL SECURITY INVARIANT:** This action **NEVER grants VIP** or modifies user entitlements. The user remains on their existing plan.
4. **Admin-Only Manual Payment Review Action:**
   - Platform administrators inspect the corporate bank statement.
   - An authorized admin confirms the payment via `POST /api/admin/billing/orders/{order_code}/confirm`.
   - Admin authorization is strictly verified server-side (`get_current_admin_user`). Frontend role flags are never trusted.
   - Atomically updates order to `paid`, cancels previous active subscriptions, activates the 30-day VIP plan, and generates an invoice.
   - Idempotent: repeated confirmation calls return success without double-granting subscriptions or altering period dates.
5. **Preserved Audit Records:**
   - Every confirmation records: `admin_id`, `order_reference`, `amount`, `bank_tx_reference`, `confirmed_at`, and `admin_notes` in `payment_audit_log` and `payment_orders`.


---

## 2. End-to-End Payment Flow

```
[ Authenticated User ]
       |
       | 1. POST /api/billing/checkout { plan_id: "personal" }
       v
[ GARI Backend Server ]
       | 2. Computes canonical amount (129,000 VND; client amount ignored)
       | 3. Generates 8-digit order code (e.g. 84920155)
       | 4. Formats order reference: GARI-U<uid>-84920155
       | 5. Generates VietQR URL (img.vietqr.io)
       v
[ User Browser / Frontend Modal ]
       | 6. Shows VietQR, recipient bank details, exact amount, and transfer syntax
       | 7. User transfers money via their Mobile Banking App (Vietcombank, MB, etc.)
       | 8. User clicks "Tôi Đã Chuyển Khoản" ("I have transferred")
       v
[ GARI Backend Server ]
       | 9. POST /api/billing/orders/{order_code}/transferred
       | 10. Order transitions to 'pending_review' with timestamp
       |     * USER ENTITLEMET REMAINS FREE. NO VIP GRANTED. *
       v
[ Platform Administrator ]
       | 11. Inspects bank account statement for matching reference and credit
       | 12. POST /api/admin/billing/orders/{order_code}/confirm
       |     Headers: { Authorization: Bearer <ADMIN_TOKEN> }
       |     Body: { bank_tx_reference: "FT2601928374", admin_notes: "Matched in MB" }
       v
[ GARI Backend Server (Atomic Transaction) ]
       | 13. Verifies admin role server-side (403 for non-admins)
       | 14. Checks idempotency (already paid? return success without double-grant)
       | 15. ATOMIC COMMIT:
       |     - payment_orders.payment_status = 'paid'
       |     - Supersedes older subscriptions
       |     - Inserts 30-day active subscription into 'subscriptions' & 'user_subscriptions'
       |     - Inserts paid invoice into 'invoices'
       |     - Records audit trail in 'payment_audit_log'
       v
[ User Browser / Polling ]
       | 16. GET /api/billing/orders/{order_code}/status detects 'paid'
       v 17. Displays celebration view and unlocks VIP Pro models
```

---

## 3. Server-Side Configuration

Configure the receiving bank account in your server environment:

```env
# ------------------------------------------------------------------------------
# Bank QR Payment Configuration (VietQR / Manual Admin Review)
# ------------------------------------------------------------------------------
PAYMENT_PROVIDER=bank_qr

# Recipient Vietnamese Bank Account (VietQR NAPAS standard)
BANK_QR_BANK_ID=MB                           # Bank code (e.g. MB, VCB, TCB, ACB, TPB)
BANK_QR_ACCOUNT_NUMBER=0333333333            # Recipient bank account number
BANK_QR_ACCOUNT_NAME=CONG TY TNHH GARI AI    # Recipient account owner name

# Public Checkout Safety Switch (0 = disabled, 1 = enabled)
# Keep disabled (0) by default until bank account and pricing are verified.
PAYMENT_PUBLIC_CHECKOUT_ENABLED=0

# Order Expiration (minutes)
PAYMENT_ORDER_EXPIRY_MINUTES=15
```

### Safe Configuration Validation
Run the configuration validation tool to verify readiness without printing sensitive data:
```bash
python tools/validate_payment_config.py
```

---

## 4. API Endpoints Reference

### Public / Authenticated User Endpoints
- `GET /api/billing/payment-config`: Returns gateway readiness and checkout switch status.
- `POST /api/billing/checkout`:
  - Body: `{"plan_id": "personal"}` (Optional: `org_id`, `idempotency_key`).
  - Returns: `order_code`, `order_reference` (`GARI-U<uid>-<order_code>`), `amount`, `bank_id`, `account_number`, `account_name`, `qr_code_url`.
- `POST /api/billing/orders/{order_code}/transferred`:
  - User reports they transferred funds.
  - Body: `{"notes": "optional transfer note"}`.
  - Transitions order to `pending_review`. **Never grants VIP.**
- `GET /api/billing/orders/{order_code}/status`:
  - Authoritative status polling (`pending`, `pending_review`, `paid`, `expired`, `rejected`).

### Admin-Only Endpoints
*All admin endpoints require an authenticated user with `is_admin = 1`. Non-admins receive `403 Forbidden`.*

- `GET /api/admin/billing/orders?status=pending_review&limit=50`:
  - Lists payment orders awaiting manual verification with user emails and timestamps.
- `POST /api/admin/billing/orders/{order_code}/confirm`:
  - Body: `{"bank_tx_reference": "FT2601928374", "admin_notes": "Verified in MB statement"}`.
  - Transitions order to `paid`, grants 30-day VIP subscription, creates invoice, and writes audit record.
  - Idempotent: repeated calls do not duplicate grants.
- `POST /api/admin/billing/orders/{order_code}/reject`:
  - Body: `{"reason": "No matching bank transfer found after 24 hours", "admin_notes": "optional"}`.
  - Transitions order to `rejected`.

---

## 5. Automated Test Suite Results

Test command:
```bash
python -m unittest tests/test_pricing_audit.py tests/test_vouchers.py tests/test_voucher_api.py tests/test_bank_qr_sepay.py
```

Result:
```
Ran 36 tests in 1.530s
OK (100% Pass)
```

Verified test coverage:
1. `test_01`: Public checkout disabled by default (`PAYMENT_PUBLIC_CHECKOUT_ENABLED=0`).
2. `test_02`: Valid checkout creates pending order with trusted pricing and static VietQR / MoMo QR asset reference (`/static/frontend2/images/vietqr_momo.jpg`).
3. `test_03`: Multiple orders by same user have distinct, unique references (UID alone is never used).
4. `test_04`: User reports transfer -> status transitions to `pending_review`. **Verified zero-trust: VIP is NEVER granted!**
5. `test_05`: Unauthenticated (401) and unauthorized users (403) cannot report transfer for orders they don't own.
6. `test_06`: Non-admin callers cannot confirm payment (403 Forbidden).
7. `test_07`: Authorized admin confirms payment: order marked `paid`, 30-day subscription granted atomically, and paid invoice created.
8. `test_08`: Duplicate admin confirmation is idempotent: no double subscriptions, no end-date extensions.
9. `test_09`: Audit trail preserves admin ID, order reference, amount, bank tx reference, and confirmation timestamp.
10. `test_10`: Admin can reject invalid orders (`rejected` status, no VIP).
11. `test_11`: Admin can list and filter payment orders for review.
12. `test_12`: Subscription grant failure triggers database rollback; order is not marked paid.
13. `test_13`: Tampered client amount, invalid plan ID, or non-existent order code cannot grant VIP.
14. `test_14`: Admin can confirm payment using the formatted order reference string (`GARI-U<uid>-<order_code>`).

