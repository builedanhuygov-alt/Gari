# GARI — CLOUD INFRASTRUCTURE COST ANALYSIS & GUARDRAILS
**Document ID:** `GARI_INFRASTRUCTURE_COST_REPORT.md`  
**Version:** 1.0.0 | **Author:** GARI Cloud Architecture & FinOps  
**Date:** 2026-11-10  

---

## 1. Executive Summary

GARI AgriTech AI Lab has designed its production cloud topology to operate at **$0.00 / month (0 VND)** using the permanently free allotments of Oracle Cloud Infrastructure (OCI Always Free), Let's Encrypt ACME SSL, and Vercel Hobby tier.

This report documents the exact resource consumption, free tier entitlement headroom, and strict operational guardrails enforced to prevent inadvertent billing.

---

## 2. Resource Allocation & Cost Ledger

| Infrastructure Component | Free Tier Provider | Specification / Tier | GARI Consumption | Free Tier Limit | Monthly Cost |
| :--- | :--- | :--- | :---: | :---: | :---: |
| **Compute (Backend & AI)**| Oracle Cloud (OCI) | `VM.Standard.A1.Flex` (Ampere A1 ARM64) | **2 OCPU / 12 GB RAM** | 4 OCPU / 24 GB RAM | **$0.00** |
| **Boot & State Storage** | Oracle Cloud (OCI) | Block Volume (High Performance NVMe) | **100 GB** | 200 GB (Tenancy Total)| **$0.00** |
| **Public IPv4 Address** | Oracle Cloud (OCI) | Reserved / Ephemeral Public IP | **1 IPv4 Address** | 1 Reserved + Ephemeral | **$0.00** |
| **Network Egress (Out)** | Oracle Cloud (OCI) | Internet Outbound Bandwidth | **~10–25 GB / month** | 10,000 GB (10 TB) | **$0.00** |
| **Ingress Bandwidth** | Oracle Cloud (OCI) | Internet Inbound Traffic | **~15–30 GB / month** | Unlimited Free | **$0.00** |
| **SSL / TLS Encryption** | Let's Encrypt ACME | Automated X.509 RSA/ECDSA | **1 Domain (Wildcard/SAN)**| Unlimited Free | **$0.00** |
| **Frontend Web Hosting** | Vercel | Production CDN (`frontend2/`) | **~50,000 reqs/mo** | 100 GB Bandwidth | **$0.00** |
| **Database Engine** | Self-Hosted | SQLite WAL on Host Storage | **9.5 MB DB + Backups** | Included in 100 GB disk| **$0.00** |
| **Total Monthly Cost** | — | — | — | — | **$0.00 / mo** |

---

## 3. Capacity Headroom Analysis

```mermaid
xychart-beta
    title "Oracle Cloud Always Free Resource Headroom"
    x-axis ["OCPU Cores", "RAM (GB)", "Boot Storage (GB)", "Egress (TB)"]
    y-axis "Percentage Used (%)" 0 --> 100
    bar [50, 50, 50, 0.2]
```

- **OCPU Capacity:** 2 OCPU used out of 4 OCPU free quota (50% headroom remaining).
- **RAM Capacity:** 12 GB allocated out of 24 GB free quota (50% headroom remaining).
- **Boot Storage:** 100 GB allocated out of 200 GB free quota (100 GB available for snapshots or secondary instances).
- **Network Egress:** < 25 GB consumed against a 10,000 GB (10 TB) monthly allotment (< 0.25% used).

---

## 4. Cost Guardrails & Anti-Billing Policy

To guarantee that GARI never incurs surprise cloud invoices, the following guardrails are strictly observed:

### Guardrail 1: Strictly Use "Always Free Eligible" Compute Shapes
- Only select `VM.Standard.A1.Flex` (Ampere A1).
- **Never** provision x86 Intel/AMD shapes (such as `VM.Standard3.Flex` or `VM.Standard.E4.Flex`) which consume paid credits after trial expiration.

### Guardrail 2: Boot Volume Size Cap
- The total boot volume across all instances in the OCI compartment must **not exceed 200 GB**.
- GARI instance is provisioned at **100 GB**, leaving 100 GB buffer.

### Guardrail 3: Zero Paid Managed Services
- GARI uses self-hosted SQLite WAL and Nginx rather than paid OCI Autonomous Database, OCI Load Balancer ($0.015/hr), or OCI Container Engine for Kubernetes (OKE).
- Ingress and reverse proxying are terminated directly on the VM via Nginx inside Docker.

### Guardrail 4: Automated Retention Pruning
- `deploy/oracle/backup_sqlite.py` automatically prunes backups older than 7 days (daily), 4 weeks (weekly), and 3 months (monthly).
- Backup files consume < 150 MB total disk space, completely eliminating disk-filling risks.

---

## 5. Summary & Verdict

The GARI production infrastructure is **100% cost-optimized at zero USD / zero VND per month**. It delivers robust agricultural AI capabilities, high availability, and automated data protection without requiring ongoing operational subscriptions.

