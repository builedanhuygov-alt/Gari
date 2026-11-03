# GARI AI LAB — Vietnamese Bank QR & SePay Payment Integration

> [!NOTE]
> **Update:** GARI's active bank payment workflow has transitioned to **VietQR with Manual Admin Payment Review** to eliminate third-party webhook dependencies and enforce strict human verification before granting VIP subscriptions. See [BANK_QR_PAYMENT_MANUAL_REVIEW.md](file:///d:/leaf-diseases-detector-main/docs/BANK_QR_PAYMENT_MANUAL_REVIEW.md) for the active manual review specification.

## 1. Overview & Provider Selection

### Why Vietnamese Bank QR (VietQR) + SePay Was Selected
In Vietnam, bank transfer via standard QR code (VietQR / NAPAS 24/7) is the dominant payment method for agricultural households, cooperatives, agricultural engineers, and agribusinesses. Unlike third-party payment gateways that require buyers to create intermediate e-wallet accounts, pay high merchant transaction fees (1.5% - 3.5%), or navigate complex checkout redirects, VietQR allows direct, zero-fee interbank transfers from all 40+ Vietnamese banking applications (Vietcombank, MB Bank, Techcombank, ACB, VPBank, etc.).

**SePay** acts as the transaction notification listener:
- **No intermediary holding of funds:** Money flows directly from the user's bank account into GARI's business bank account instantly.
- **Automated Webhook:** As soon as the receiving bank records the credit transaction, SePay detects the bank balance movement and sends an HTTPS webhook to GARI's backend within seconds.
- **Deterministic Order Matching:** Each checkout order receives a dynamic VietQR containing recipient bank credentials, exact server-calculated amount, and a unique transfer syntax (`GARI-<order_code>`).
- **Simplicity & Zero-Trust Security:** No payment amounts from the client are trusted. Webhooks are authenticated with constant-time token comparison, idempotent execution, and atomic subscription activation.

---

## 2. Architecture & Data Flow

```
[ User Browser / App ]
       |
       | 1. POST /api/billing/checkout { plan_id: "personal" }
       v
[ GARI Backend Server ]
       | 2. Calculates server pricing (Personal: 129,000 VND / Business: 299,000 VND)
       | 3. Creates pending payment order in SQLite (order_code: 8-digit unique, 15-min expiry)
       | 4. Generates dynamic VietQR NAPAS URL (img.vietqr.io)
       v
[ User Browser / App ]
       | 5. Displays Bank QR Modal: QR image, Bank name, Account No, Amount, Syntax (GARI-<code'>)
       | 6. User scans QR code in Mobile Banking App and confirms transfer
       v
[ Vietnamese Banking System (NAPAS) ]
       | 7. Transfers funds directly to GARI's corporate bank account
       v
[ SePay Webhook Listener ]
       | 8. Detects credit transaction on GARI's bank account
       | 9. POST https://app.gari.vn/api/billing/webhook/sepay
       |    Header: "Authorization: Apikey <PAYMENT_WEBHOOK_SECRET>"
       v
[ GARI Backend Webhook Engine ]
       | 10. Authenticates API key (constant-time hmac.compare_digest)
       | 11. Checks direction ('in') & recipient account number
       | 12. Matches regex `GARI[\s\-_:]*(\d+)` to pending order in database
       | 13. Validates exact amount (strictly rejects underpayment & overpayment)
       | 14. Checks order expiration (15-min window + 10-min grace period)
       | 15. Enforces durable idempotency (UNIQUE provider, event_id constraint)
       | 16. ATOMIC TRANSACTION:
       |     - Marks payment_orders as 'paid'
       |     - Supersedes older active subscriptions
       |     - Inserts 30-day VIP subscription into `subscriptions` & `user_subscriptions`
       |     - Generates paid invoice record in `invoices`
       v
[ User Browser / Frontend Polling ]
       | 17. GET /api/billing/orders/{order_code}/status every 2.5s detects 'paid'
       v 18. Shows celebration modal, updates UI to VIP, and unlocks Pro AI models
```

---

## 3. Server-Side Configuration & Environment Variables

Add the following environment variables to your deployment environment or `.env` file. Never commit real values or API keys to git repositories.

| Variable | Required | Description | Example / Default |
| :--- | :---: | :--- | :--- |
| `PAYMENT_PROVIDER` | Yes | Payment gateway provider identifier | `sepay` |
| `BANK_QR_BANK_ID` | Yes | Receiving Bank short name / NAPAS bin | `MB` (MBBank), `VCB` (Vietcombank), `TCB` (Techcombank), `ACB` |
| `BANK_QR_ACCOUNT_NUMBER` | Yes | Receiving corporate bank account number | `0333333333` |
| `BANK_QR_ACCOUNT_NAME` | Yes | Receiving account holder full name (uppercase) | `CONG TY TNHH GARI AI` |
| `PAYMENT_WEBHOOK_SECRET` | Yes | Secret API Token set in SePay Webhook configuration | Generated random alphanumeric string (>= 32 chars) |
| `PAYMENT_WEBHOOK_URL` | Optional | Authoritative public HTTPS webhook endpoint URL | `https://app.gari.vn/api/billing/webhook/sepay` |
| `PAYMENT_PUBLIC_CHECKOUT_ENABLED` | Yes | **Safety Switch:** Set to `0` during setup. Enable with `1` only after testing | `0` (Safe Default) |
| `PAYMENT_ORDER_EXPIRY_MINUTES` | Optional | Expiration window for pending Bank QR transfer | `15` |

### Configuration Validator Tool
A safe configuration verification script is available in the project. It checks for variable presence and reports readiness without ever printing secret values or credentials:

```bash
# Run safe config validator
python tools/validate_payment_config.py
```

---

## 4. Setup Guide: Step-by-Step SePay & Webhook Configuration

### Step 1: Create a SePay Account & Connect Bank
1. Visit [https://sepay.vn](https://sepay.vn) and create a merchant account.
2. Navigate to **Ngân hàng (Bank Accounts)** and link your business bank account (e.g. MB Bank, Vietcombank, ACB, etc.).
3. Follow SePay's bank connection guide (either via Corporate Internet Banking or automated SMS/App notification listener).

### Step 2: Configure Webhook in SePay Dashboard
1. In the SePay dashboard, navigate to **Tích hợp Webhook (Webhooks)** > **Tạo Webhook mới**.
2. **URL Webhook:** Enter your production HTTPS endpoint:
   ```
   https://<your-domain>/api/billing/webhook/sepay
   ```
   *(Note: The webhook endpoint MUST use HTTPS with a valid SSL/TLS certificate. Self-signed certificates and plain HTTP will be rejected).*
3. **Phương thức xác thực (Authentication):** Select `API Key` / `Bearer Token`.
4. **API Key / Secret Token:** Generate a strong random key (e.g. `openssl rand -hex 24`) and paste it into the SePay API Key field.
5. In your production server environment, configure:
   ```env
   PAYMENT_WEBHOOK_SECRET=<the_same_key_generated_above>
   ```

### Step 3: Test Webhook Delivery via SePay Simulator
1. In the SePay dashboard, open the **Test Webhook / Giả lập giao dịch** tool.
2. Select your linked bank account.
3. Set transaction direction to **Nhận tiền (in)**.
4. Set amount to **129,000** (Personal) or **299,000** (Business).
5. In the transfer content field, enter `GARI-<order_code>` using a real pending order code created from your test checkout.
6. Click **Gửi thử Webhook (Send Test)** and verify in SePay that HTTP status `200 OK` is returned.

### Step 4: Enable Public Checkout
Once the webhook delivers HTTP 200 and the subscription card in GARI reflects the active paid plan, enable public checkout:
```env
PAYMENT_PUBLIC_CHECKOUT_ENABLED=1
```

---

## 5. Webhook Security & Idempotency Specifications

1. **Authentication:**
   - Evaluated using `hmac.compare_digest` in `gari_payment.verify_sepay_webhook_auth` to prevent timing attacks.
   - Accepts `Authorization: Apikey <TOKEN>`, `Authorization: Bearer <TOKEN>`, or `X-SePay-Secret: <TOKEN>`.
2. **Order Matching:**
   - Content parsed via regex `r"GARI[\s\-_:]*(\d+)"`.
   - Rejects payloads without an order reference (`PaymentOrderReferenceMissingError`, HTTP 400).
   - Rejects non-existent orders (`PaymentOrderNotFoundError`, HTTP 404).
3. **Amount & Direction Validation:**
   - Direction MUST be `transferType == 'in'`. Outgoing transfers are logged and safely ignored (`ignored: true`).
   - Exact amount matching:
     - Underpayment (`transferAmount < order.amount`): Flags order as `review_required` with `failure_reason = 'underpayment'`, rejects with HTTP 400, and does NOT grant VIP.
     - Overpayment (`transferAmount > order.amount`): Flags order as `review_required` with `failure_reason = 'overpayment'`, rejects with HTTP 400, and does NOT grant VIP until manual administrator reconciliation.
4. **Idempotency & Replay Protection:**
   - SePay transaction ID (`id`) is stored in `payment_webhook_events` with database-level `UNIQUE(provider, event_id)` constraint.
   - Subsequent deliveries of the same transaction return `{ success: True, duplicate: True }` and do not extend or duplicate subscriptions.
5. **Atomic Transactions:**
   - Updating `payment_orders`, canceling previous subscriptions, inserting into `subscriptions` & `user_subscriptions`, and generating the paid invoice in `invoices` are all performed inside an atomic SQLite transaction block under `_PAYMENT_LOCK`.

---

## 6. Changed Files & Deliverables Summary

1. `database/migrations_bank_qr.py`:
   - Pre-migration WAL-consistent database backup.
   - Extends `payment_orders` with: `order_reference`, `bank_id`, `account_number`, `account_name`, `qr_code_url`, `expires_at`, `provider_tx_id`.
   - Created unique index on `payment_orders(order_reference)` and index on `payment_orders(expires_at)`.
2. `gari_payment.py`:
   - Complete Vietnamese Bank QR (VietQR) + SePay engine.
   - Authoritative pricing enforcement (`get_canonical_order_pricing`).
   - Dynamic configuration getters reading environment variables.
   - Constant-time webhook authenticator (`verify_sepay_webhook_auth`).
   - Atomic and idempotent webhook processor (`process_sepay_webhook`).
   - Server-side status polling helper (`get_order_status`).
3. `api_server.py`:
   - `POST /api/billing/checkout`: Creates Bank QR pending order and returns VietQR URL and transfer syntax.
   - `POST /api/billing/webhook/sepay`: Authenticated webhook receiver.
   - `GET /api/billing/orders/{order_code}/status`: Authoritative status check.
   - `GET /api/billing/payment-config`: Gateway readiness info.
4. `frontend2/pricing.html`:
   - Bank QR modal `#modalBankQR` with VietQR image, bank details, 1-click copy buttons, countdown timer, and automated 2.5-second polling.
   - Auto-activation celebration screen upon payment confirmation.
5. `tools/validate_payment_config.py`:
   - Safe CLI validator reporting configuration presence without exposing secrets.
6. `tests/test_bank_qr_sepay.py`:
   - 14 automated synthetic test scenarios covering all edge cases.

---

## 7. Automated Test Suite Results

Test command executed:
```bash
python -m unittest tests/test_pricing_audit.py tests/test_vouchers.py tests/test_voucher_api.py tests/test_bank_qr_sepay.py
```

Result:
```
Ran 36 tests in 2.178s
OK (100% Pass)
```

Test scenarios covered:
- [x] Valid webhook and exact matching payment (`test_03`)
- [x] Invalid or missing signature/token authentication (`test_04`)
- [x] Incorrect recipient bank account number (`test_05`)
- [x] Missing or incorrect order reference (`test_06`)
- [x] Unknown order reference transaction (`test_07`)
- [x] Duplicate webhook delivery idempotency (`test_08`)
- [x] Replayed transaction protection (`test_09`)
- [x] Underpayment and overpayment rejection (`test_10`)
- [x] Expired order rejection (`test_11`)
- [x] Concurrent webhook delivery thread safety (`test_12`)
- [x] Frontend zero-trust: direct client cannot mark order paid (`test_13`)
- [x] Subscription grant failure atomic rollback (`test_14`)
- [x] Public checkout fail-closed default (`test_01`)
- [x] Valid checkout creates pending order with trusted pricing & VietQR (`test_02`)

---

## 8. Remaining Manual Steps for System Administrator

1. **Obtain Bank & SePay Credentials:**
   - Link your corporate Vietnamese bank account in SePay.
   - Generate your `PAYMENT_WEBHOOK_SECRET` token in SePay.
2. **Set Environment Variables on Server:**
   ```bash
   BANK_QR_BANK_ID="MB"
   BANK_QR_ACCOUNT_NUMBER="0123456789"
   BANK_QR_ACCOUNT_NAME="CONG TY TNHH GARI AI"
   PAYMENT_WEBHOOK_SECRET="your_actual_sepay_token"
   PAYMENT_PUBLIC_CHECKOUT_ENABLED=0
   ```
3. **Verify Configuration:**
   ```bash
   python tools/validate_payment_config.py
   ```
4. **Trigger Controlled Test Webhook:**
   Use the SePay simulator to send a synthetic webhook to `https://<domain>/api/billing/webhook/sepay` and confirm your test order transitions to `paid`.
5. **Enable Public Checkout:**
   Update `PAYMENT_PUBLIC_CHECKOUT_ENABLED=1` and reload the service.
