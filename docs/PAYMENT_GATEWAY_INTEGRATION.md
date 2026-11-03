# GARI AI LAB — Payment Gateway Integration & Webhook Guide

This document details the production integration of the payment gateway for **Personal (129,000 VND/month)** and **Business (299,000 VND/month)** plans.

---

## 1. Provider Selection & Architecture

- **Provider:** PayOS (`https://payos.vn`)
- **Payment Rails:** VietQR, Napas 24/7 bank transfers, and domestic cards.
- **Currency:** Vietnamese Dong (`VND`), integer representation.
- **Canonical Server-Side Pricing:**
  - **Personal:** `129,000 VND/month` (Single user, 100 diagnoses/day, VIP model access).
  - **Business:** `299,000 VND/month` (Organization-wide shared quota, 5 team members, B2B multi-tenant isolation).
- **Core Security Rule:** The client never specifies the price, currency, or subscription period. The backend strictly resolves the price from `gari_plans.py` during order creation.

```
[ Frontend: pricing.html ]
        |
        |  1. POST /api/billing/checkout { plan_id: "personal" } (Bearer JWT)
        v
[ Backend: api_server.py / gari_payment.py ]
        |  - Resolves canonical price (129,000 VND)
        |  - Checks organization role if Business
        |  - Generates integer orderCode & internal_payment_id
        |  - Requests payment link from PayOS API v2 (with HMAC-SHA256 signature)
        |  - Saves order as 'pending' in payment_orders
        v
[ PayOS Gateway (api-merchant.payos.vn) ]
        |
        |  Customer scans VietQR via Mobile Banking
        v
[ PayOS Webhook Delivery ]
        |
        |  2. POST /api/billing/webhook/payos (Raw JSON + HMAC-SHA256 signature)
        v
[ Backend Webhook Engine: gari_payment.py ]
        |  - Verifies HMAC-SHA256 signature using PAYOS_CHECKSUM_KEY
        |  - Checks timestamp replay-protection window
        |  - Checks durable idempotency in payment_webhook_events table
        |  - Verifies orderCode, amount, and currency
        |  - Atomic DB Transaction:
        |      * payment_orders: status = 'succeeded', paid_at = now
        |      * invoices: status = 'paid', payment_status = 'succeeded'
        |      * subscriptions: status = 'active', 30 days granted, supersedes older rows
        |      * payment_webhook_events: status = 'processed'
        v
[ User Entitlement Activated ]
```

---

## 2. Required Environment Variables

Configure these variables in `.env` (refer to `.env.example`):

```bash
# Payment Provider
PAYMENT_PROVIDER=payos
PAYMENT_ENVIRONMENT=sandbox # Set to 'production' for live merchant accounts

# PayOS API Credentials (from https://my.payos.vn)
PAYOS_CLIENT_ID=your_payos_client_id_here
PAYOS_API_KEY=your_payos_api_key_here
PAYOS_CHECKSUM_KEY=your_payos_checksum_key_here

# Customer Return & Cancel URLs
PAYMENT_RETURN_URL=https://app.gari.vn/frontend2/pricing.html?payment=success
PAYMENT_CANCEL_URL=https://app.gari.vn/frontend2/pricing.html?payment=cancel

# Replay Protection Window (seconds, default: 86400 / 24 hours)
PAYMENT_WEBHOOK_MAX_AGE_SECONDS=86400
```

> **Fail-Closed Protection:** If `PAYOS_CLIENT_ID`, `PAYOS_API_KEY`, or `PAYOS_CHECKSUM_KEY` are empty or set to default placeholders, `gari_payment.is_payment_configured()` returns `False`. The checkout endpoint returns `HTTP 400/503` with an honest message. No fake payment success is ever permitted.

---

## 3. Webhook Endpoint Configuration in PayOS Dashboard

1. Log in to the [PayOS Dashboard](https://my.payos.vn).
2. Navigate to **Kênh thanh toán / Cấu hình Webhook**.
3. Set the Webhook URL to:
   ```
   https://app.gari.vn/api/billing/webhook/payos
   ```
4. Copy the generated **Checksum Key** and store it in `PAYOS_CHECKSUM_KEY` in `.env`.
5. Trigger PayOS "Gửi thử nghiệm Webhook" to confirm connectivity.

---

## 4. Webhook Signature Verification Algorithm

PayOS signs the webhook payload using HMAC-SHA256 over alphabetically sorted key-value pairs:

```python
# 1. Sort all keys of payload['data'] alphabetically
sorted_keys = sorted(data.keys())

# 2. Exclude keys where value is None or empty string, format key=value
parts = [f"{k}={data[k]}" for k in sorted_keys if data.get(k) not in (None, "")]
sign_string = "&".join(parts)

# 3. Compute HMAC-SHA256 with CHECKSUM_KEY
expected_signature = hmac.new(
    checksum_key.encode("utf-8"),
    sign_string.encode("utf-8"),
    hashlib.sha256
).hexdigest()

# 4. Compare with constant-time comparison against timing attacks
is_valid = hmac.compare_digest(expected_signature.lower(), signature.lower())
```

Requests with missing, invalid, altered, or expired signatures are rejected immediately with `HTTP 400 Bad Request` prior to database queries.

---

## 5. Durable Idempotency & Concurrency Strategy

Webhook delivery is at-least-once. The same event may arrive multiple times or concurrently across multiple worker processes.

1. **Database-Level Unique Constraint:**
   `payment_webhook_events` enforces `UNIQUE(provider, event_id)` where `event_id` is `payos_{orderCode}_{reference}`.
2. **Duplicate Detection:**
   If a duplicate arrives, the unique constraint catches it. If the existing event is `processed`, the endpoint returns `200 OK` with `{"success": true, "duplicate": true}` without re-granting access.
3. **Atomic Transaction:**
   Updating order status, writing invoices, activating subscriptions, and marking event `processed` occur within a single database transaction under `_PAYMENT_LOCK` and SQLite WAL mode.
4. **Single Active Subscription Invariant:**
   Granting a new paid subscription automatically cancels/supersedes any previous active subscription for that user or organization.

---

## 6. How to Test Using Sandbox vs. Live Credentials

### Sandbox Testing
1. In PayOS dashboard, create a test channel in **Môi trường Thử nghiệm (Sandbox)**.
2. Set `PAYMENT_ENVIRONMENT=sandbox` in `.env`.
3. Use the PayOS testing QR app or transfer simulator to trigger mock transfers.
4. Run the automated test suite:
   ```bash
   python -m unittest tests/test_payment_gateway.py
   ```

### Switching to Live Production
1. Complete merchant business verification on PayOS (Đăng ký doanh nghiệp / Hộ kinh doanh).
2. Generate production API credentials on PayOS.
3. Update `.env`:
   - `PAYMENT_ENVIRONMENT=production`
   - Set live `PAYOS_CLIENT_ID`, `PAYOS_API_KEY`, `PAYOS_CHECKSUM_KEY`.
4. Register the production webhook URL on PayOS dashboard.
5. Perform a live 129,000 VND test payment using a real bank app, verify subscription activation, then initiate an admin refund if needed.

---

## 7. Known Limitations & Merchant Account Prerequisites

- **Business Registration:** Live VietQR payments via PayOS require a registered Vietnamese business entity or verified individual merchant account with a connected corporate/merchant bank account.
- **Distributed Lock at Scale:** The current SQLite WAL implementation uses in-process reentrant locking (`_PAYMENT_LOCK`) and database unique constraints. If scaling to a multi-instance Kubernetes cluster with multiple SQLite replicas, migrate to PostgreSQL or Redis-backed distributed locks.
