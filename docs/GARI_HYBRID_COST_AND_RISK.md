# GARI AgriTech AI Platform — Capacity, Cost & Risk Analysis

**Document ID:** GARI-ANALYSIS-COST-RISK-2026-01  
**Project:** GARI AgriTech AI Platform  
**Target Infrastructure:** Vercel Hobby + Supabase Free Tier + Windows Self-Hosted Worker  
**Date:** 2026-11-11  
**Status:** DRAFT SPECIFICATION — APPROVED FOR REVIEW  

---

## 1. Provider Free-Tier Limits vs. GARI Expected Workload

To maintain a zero-cost infrastructure model, GARI operates within the official free tiers of Vercel and Supabase. The table below contrasts **verified provider limits** with **projected operational consumption**.

| Metric | Verified Provider Free Limit | GARI Projected Monthly Usage | Consumption Ratio | Headroom Status |
| :--- | :--- | :--- | :---: | :---: |
| **Vercel Bandwidth** | 100 GB / month | ~6.5 GB / month | 6.5% | **EXCELLENT** |
| **Vercel Serverless Invocations**| 100,000 requests / day | ~3,500 requests / day | 3.5% | **EXCELLENT** |
| **Vercel Function Duration** | Max 10s (default) / 15s (Hobby) | ~350ms – 600ms (Job enqueue) | < 6% | **SAFE (Zero Timeout Risk)**|
| **Supabase Database Storage** | 500 MB PostgreSQL | ~45 MB (Initial) to ~85 MB (Yr 1) | 17% | **SAFE** |
| **Supabase File Storage** | 1 GB Bucket storage | ~400 MB (With 30-day lifecycle) | 40% | **MANAGED** |
| **Supabase Storage Egress** | 2 GB / month | ~0.8 GB / month (Worker downloads) | 40% | **MANAGED** |
| **Supabase Monthly Active Users**| 50,000 MAU | 3,611 existing + ~500 new | 8.2% | **EXCELLENT** |
| **Supabase Realtime Connections**| 200 concurrent WebSockets | 15–40 concurrent peak | 20% | **SAFE** |
| **Windows Worker Compute** | Self-hosted hardware ($0) | 2–4 hours / day active runtime | N/A | **CONTROLLED** |

---

## 2. Storage & Database Capacity Sizing

### 2.1 PostgreSQL Database Sizing (500 MB Limit)
- **User Accounts & Profiles (3,611 users):**
  - Average row size in `public.profiles` + `auth.users` + `user_preferences`: ~1.5 KB.
  - Total: 3,611 × 1.5 KB ≈ **5.4 MB**.
- **Farm Hierarchy & Plots (1,200 farms, 3,500 plots):**
  - Average row size: ~1.2 KB.
  - Total: **5.6 MB**.
- **Cultivation Tasks & Activity Logs (15,000 records):**
  - Average row size: ~800 bytes.
  - Total: **12.0 MB**.
- **Diagnosis Job Queue & History (10,000 records):**
  - Average row size (including diagnostic result JSONB): ~2.5 KB.
  - Total: **25.0 MB**.
- **System Indexes & Overhead:** ~20.0 MB.
- **Estimated Total PostgreSQL Footprint:** **~68.0 MB** (13.6% of 500 MB quota).

### 2.2 Supabase Object Storage Sizing (1 GB Limit)
- **Raw Image Dimensions:** JPEG compressed to 1280×720 or 1080×1080 resolution.
- **Average Leaf Photo Size:** ~180 KB to 250 KB (Average: ~200 KB).
- **Daily Image Submissions:** ~30–50 images / day.
- **Monthly Image Accumulation:** 45 images/day × 30 days = 1,350 images/month.
- **Gross Monthly Image Volume:** 1,350 × 200 KB ≈ **270 MB / month**.
- **Storage Lifecycle Policy:**
  - Raw leaf images are retained in full resolution for **30 days**.
  - After 30 days, an automated edge cron purges or compresses older raw images, retaining diagnostic JSON vectors and small thumbnails (25 KB) in the database.
  - Under this policy, storage usage stabilizes permanently at **~350 MB to 450 MB**, well within the 1 GB free quota.

---

## 3. Windows Worker Processing Throughput & Duty Cycle

### 3.1 Inference Performance Profile
- **Benchmark Average (Pre-warmed):** 0.74 seconds per leaf image.
- **Image Download & Payload Writeback:** ~0.45 seconds over local broadband.
- **Total End-to-End Job Turnaround:** ~1.20 seconds per queued task.

### 3.2 Throughput Calculations Across Daily Host Schedules
| Windows PC Active Runtime | Total Available Seconds | Effective Hourly Throughput | Maximum Daily Jobs Processed |
| :---: | :---: | :---: | :---: |
| **1 Hour / Day** | 3,600 s | 3,000 jobs / hr | **3,000 diagnoses / day** |
| **2 Hours / Day** | 7,200 s | 3,000 jobs / hr | **6,000 diagnoses / day** |
| **4 Hours / Day** | 14,400 s | 3,000 jobs / hr | **12,000 diagnoses / day** |

> [!NOTE]
> **Queue Clearing Efficiency:**
> At an anticipated traffic volume of 50 to 150 diagnoses per day across the farmer community, **the Windows worker will clear the entire 24-hour backlog within 2 to 3 minutes of booting up!**

---

## 4. Key Operational Risks & Mitigation Strategies

```
+---------------------------------------------------------------------------------------------------------+
|                                    GARI RISK & MITIGATION MATRIX                                        |
+--------------------+----------------------------+----------+--------------------------------------------+
| Risk Description   | Failure Mechanism          | Severity | Automated Mitigation Strategy              |
+--------------------+----------------------------+----------+--------------------------------------------+
| Supabase 7-Day     | Free-tier Supabase         | MEDIUM   | Scheduled GitHub Actions Keep-Alive Cron   |
| Inactivity Pause   | projects pause after       |          | executes a lightweight query every 4 days: |
|                    | 7 days without queries.    |          | 'SELECT COUNT(*) FROM public.crops;'       |
+--------------------+----------------------------+----------+--------------------------------------------+
| Windows Worker     | Power outage, host PC      | MEDIUM   | Cloud queue buffers jobs indefinitely.     |
| Offline for Days   | fails to power on for      |          | Frontend displays clear queue status:      |
|                    | 48+ hours.                 |          | "Ảnh đang chờ xử lý khi trạm AI kích hoạt" |
+--------------------+----------------------------+----------+--------------------------------------------+
| Storage Quota      | Heavy photo uploads        | HIGH     | Automatic 30-day purge lifecycle for raw   |
| Exhaustion (>1 GB) | accumulate without purge.  |          | JPEGs. Diagnostic JSON history is kept.    |
+--------------------+----------------------------+----------+--------------------------------------------+
| Stalled Processing | Windows host crashes or    | LOW      | Heartbeat timeout (120s) resets stalled    |
| Lock               | sleeps during inference.   |          | jobs from 'processing' back to 'queued'.   |
+--------------------+----------------------------+----------+--------------------------------------------+
| Local Model Leak   | Local model files          | CRITICAL | Windows worker initiates outbound HTTPS    |
| or Host Intrusion  | exposed to internet.       |          | only. Zero inbound open ports. Zero PHP.   |
+--------------------+----------------------------+----------+--------------------------------------------+
```

---

## 5. Free-Tier vs. Verified Provider Boundary Summary

To ensure financial safety and avoid unexpected charges:

1. **Credit Card Billing Disabled:** Supabase and Vercel accounts remain on non-metered free tiers. Quota exhaustion results in controlled HTTP 429 / 503 responses rather than surprise billing.
2. **Zero Commercial API Dependencies:** The core diagnosis pipeline uses self-hosted PyTorch neural models rather than paid vision APIs (e.g. Google Cloud Vision or OpenAI Vision), ensuring that diagnosis processing costs remain strictly **$0.00**.
3. **Bandwidth Conservation:** Images are uploaded directly from the browser to Supabase Storage; image bytes never traverse Vercel Serverless Functions, keeping Vercel bandwidth consumption negligible.

