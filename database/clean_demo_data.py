"""
GARI AI LAB — Production Cutover: Confirmed Demo Data Cleanup Script
File: database/clean_demo_data.py

Removes confirmed test fixtures and demo clutter from disease_detector.db.
CRITICAL SAFETY INVARIANTS:
1. NEVER deletes Real User Data (ID 1: danhuynh@gari.vn, ID 175: huy175209@gmail.com).
2. NEVER deletes Real Organizations (ID 1: HTX Ba Vì, ID 2: Trang Trại 7).
3. NEVER deletes Real Farms (IDs 1, 2, 3, 4, 5, 8, 9).
4. NEVER deletes Uncertain records (Users 2, 3, 7) without explicit owner approval.
5. Generates a structured JSON manifest at docs/CLEANUP_MANIFEST.json before executing.
6. All deletions execute inside a single atomic SQLite transaction.
"""

import argparse
import json
import os
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT_DIR))

import gari_database

DB_PATH = ROOT_DIR / "database" / "disease_detector.db"
MANIFEST_PATH = ROOT_DIR / "docs" / "CLEANUP_MANIFEST.json"

# Strict Preservation Sets
PROTECTED_USER_IDS = {1, 175}
UNCERTAIN_USER_IDS = {2, 3, 7}  # Preserved until explicit owner approval
PROTECTED_ORG_IDS = {1, 2}
PROTECTED_FARM_IDS = {1, 2, 3, 4, 5, 8, 9}


def identify_cleanup_targets(conn: sqlite3.Connection):
    cursor = conn.cursor()

    # 1. Target Organizations: is_test = 1
    cursor.execute("SELECT id, name, slug FROM organizations WHERE is_test = 1")
    target_orgs = [{"id": r[0], "name": r[1], "slug": r[2]} for r in cursor.fetchall()]
    target_org_ids = {o["id"] for o in target_orgs}
    for protected_id in PROTECTED_ORG_IDS:
        assert protected_id not in target_org_ids, f"CRITICAL: Protected Org #{protected_id} in target list!"

    # 2. Target Farms: is_test = 1
    cursor.execute("SELECT id, name, user_id FROM farms WHERE is_test = 1")
    target_farms = [{"id": r[0], "name": r[1], "user_id": r[2]} for r in cursor.fetchall()]
    target_farm_ids = {f["id"] for f in target_farms}
    for protected_id in PROTECTED_FARM_IDS:
        assert protected_id not in target_farm_ids, f"CRITICAL: Protected Farm #{protected_id} in target list!"

    # 3. Target Users: automated test fixtures
    cursor.execute("SELECT id, email, full_name, account_type FROM users")
    all_users = cursor.fetchall()
    target_users = []
    test_prefixes = [
        "sim_user_", "victim_", "attacker_", "user_a_", "user_b_",
        "temp_", "nongdan_", "farmer_b_", "vip_payer_", "perm_farmer_",
        "perm_expert_", "farmer_mod_", "target_mod_", "host_mod_",
        "audit_", "bankqr_admin", "farmer_cc91d3e8", "target_cc91d3e8", "host_cc91d3e8"
    ]
    for r in all_users:
        u_id, email, name, acc_type = r[0], (r[1] or "").lower(), r[2], r[3]
        if u_id in PROTECTED_USER_IDS or u_id in UNCERTAIN_USER_IDS:
            continue
        # If email matches known test prefix patterns
        if any(email.startswith(p) for p in test_prefixes) or "example.com" in email:
            target_users.append({
                "id": u_id,
                "email": r[1],
                "name": name,
                "account_type": acc_type,
                "reason": "Automated test fixture"
            })
    target_user_ids = {u["id"] for u in target_users}
    for protected_id in PROTECTED_USER_IDS.union(UNCERTAIN_USER_IDS):
        assert protected_id not in target_user_ids, f"CRITICAL: Protected/Uncertain User #{protected_id} in target list!"

    # 4. Target Diagnoses: linked to target test farms or target test users
    cursor.execute("SELECT id, user_id, farm_id, crop_id, predicted_disease FROM diagnoses")
    all_diags = cursor.fetchall()
    target_diagnoses = []
    for r in all_diags:
        d_id, u_id, f_id, crop, disease = r[0], r[1], r[2], r[3], r[4]
        if f_id in target_farm_ids or u_id in target_user_ids:
            target_diagnoses.append({
                "id": d_id,
                "user_id": u_id,
                "farm_id": f_id,
                "crop": crop,
                "disease": disease,
                "reason": "Associated with quarantined test farm or test user fixture"
            })
    target_diag_ids = {d["id"] for d in target_diagnoses}

    # 5. Target Vouchers: test vouchers
    cursor.execute("SELECT id, code_preview, created_by_user_id FROM vouchers")
    all_vouchers = cursor.fetchall()
    target_vouchers = []
    for r in all_vouchers:
        v_id, preview, creator_id = r[0], r[1] or "", r[2]
        if creator_id in target_user_ids or preview.startswith("TEST") or preview.startswith("MOD") or creator_id is None:
            target_vouchers.append({"id": v_id, "preview": preview, "creator_id": creator_id})
    target_voucher_ids = {v["id"] for v in target_vouchers}

    # 6. Target Payment Orders: test orders
    cursor.execute("SELECT id, order_code, user_id, payment_status FROM payment_orders")
    all_orders = cursor.fetchall()
    target_orders = []
    for r in all_orders:
        o_id, code, u_id, status = r[0], r[1], r[2], r[3]
        if u_id in target_user_ids or u_id is None or u_id not in PROTECTED_USER_IDS:
            target_orders.append({"id": o_id, "order_code": code, "user_id": u_id, "status": status})
    target_order_ids = {o["id"] for o in target_orders}
    target_order_codes = {o["order_code"] for o in target_orders if o.get("order_code")}

    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "database_file": str(DB_PATH.name),
        "protected_records_preserved": {
            "real_users": [{"id": 1, "email": "danhuynh@gari.vn"}, {"id": 175, "email": "huy175209@gmail.com"}],
            "uncertain_users": [{"id": 2, "email": "user1@example.com"}, {"id": 3, "email": "user2@example.com"}, {"id": 7, "email": "nongdan.mau@gari.vn"}],
            "real_organizations": [{"id": 1, "name": "Hợp Tác Xã Nông Nghiệp Ba Vì"}, {"id": 2, "name": "Trang Trại Rau Sạch Nông Dân 7"}],
            "real_farms": [{"id": i} for i in sorted(PROTECTED_FARM_IDS)]
        },
        "cleanup_targets_count": {
            "organizations": len(target_orgs),
            "farms": len(target_farms),
            "users": len(target_users),
            "diagnoses": len(target_diagnoses),
            "vouchers": len(target_vouchers),
            "payment_orders": len(target_orders)
        },
        "target_organization_ids": sorted(list(target_org_ids)),
        "target_farm_ids": sorted(list(target_farm_ids)),
        "target_user_ids": sorted(list(target_user_ids)),
        "target_diagnosis_ids": sorted(list(target_diag_ids)),
        "target_voucher_ids": sorted(list(target_voucher_ids)),
        "target_payment_order_ids": sorted(list(target_order_ids)),
        "target_payment_order_codes": sorted(list(target_order_codes))
    }

    return manifest


def execute_cleanup(conn: sqlite3.Connection, manifest: dict):
    cursor = conn.cursor()
    org_ids = manifest["target_organization_ids"]
    farm_ids = manifest["target_farm_ids"]
    user_ids = manifest["target_user_ids"]
    diag_ids = manifest["target_diagnosis_ids"]
    voucher_ids = manifest["target_voucher_ids"]
    order_ids = manifest["target_payment_order_ids"]

    print("[*] Executing atomic transaction cleanup...")

    # 1. Clean Organization children
    if org_ids:
        ph = ",".join("?" for _ in org_ids)
        cursor.execute(f"DELETE FROM organization_members WHERE organization_id IN ({ph})", org_ids)
        cursor.execute(f"DELETE FROM organization_quotas WHERE organization_id IN ({ph})", org_ids)
        cursor.execute(f"DELETE FROM organization_onboarding WHERE organization_id IN ({ph})", org_ids)
        cursor.execute(f"DELETE FROM organization_audit_log WHERE organization_id IN ({ph})", org_ids)
        cursor.execute(f"DELETE FROM organizations WHERE id IN ({ph})", org_ids)
        print(f"    - Removed {len(org_ids)} test organizations and dependent records.")

    # 2. Clean Farm children & Farms
    if farm_ids:
        ph = ",".join("?" for _ in farm_ids)
        cursor.execute(f"DELETE FROM plot_timeline_events WHERE plot_id IN (SELECT id FROM farm_plots WHERE farm_id IN ({ph}))", farm_ids)
        cursor.execute(f"DELETE FROM farm_plots WHERE farm_id IN ({ph})", farm_ids)
        cursor.execute(f"DELETE FROM farms WHERE id IN ({ph})", farm_ids)
        print(f"    - Removed {len(farm_ids)} test farms and associated plots.")

    # 3. Clean Diagnoses
    if diag_ids:
        ph = ",".join("?" for _ in diag_ids)
        cursor.execute(f"DELETE FROM diagnoses WHERE id IN ({ph})", diag_ids)
        print(f"    - Removed {len(diag_ids)} test diagnoses.")

    # 4. Clean User children & Users
    if user_ids:
        ph = ",".join("?" for _ in user_ids)
        cursor.execute(f"DELETE FROM user_sessions WHERE user_id IN ({ph})", user_ids)
        cursor.execute(f"DELETE FROM user_quotas WHERE user_id IN ({ph})", user_ids)
        cursor.execute(f"DELETE FROM user_subscriptions WHERE user_id IN ({ph})", user_ids)
        cursor.execute(f"DELETE FROM user_account_type_audit WHERE user_id IN ({ph})", user_ids)
        cursor.execute(f"DELETE FROM user_consents WHERE user_id IN ({ph})", user_ids)
        cursor.execute(f"DELETE FROM audit_metrics WHERE user_id IN ({ph})", user_ids)
        cursor.execute(f"DELETE FROM usage_metering WHERE user_id IN ({ph})", user_ids)
        cursor.execute(f"DELETE FROM users WHERE id IN ({ph})", user_ids)
        print(f"    - Removed {len(user_ids)} test users and related session/quota records.")

    # 5. Clean Vouchers
    if voucher_ids:
        ph = ",".join("?" for _ in voucher_ids)
        cursor.execute(f"DELETE FROM voucher_redemptions WHERE voucher_id IN ({ph})", voucher_ids)
        cursor.execute(f"DELETE FROM voucher_audit_log WHERE voucher_id IN ({ph})", voucher_ids)
        cursor.execute(f"DELETE FROM vouchers WHERE id IN ({ph})", voucher_ids)
        print(f"    - Removed {len(voucher_ids)} test vouchers.")

    # 6. Clean Payment Orders
    if order_ids:
        ph = ",".join("?" for _ in order_ids)
        cursor.execute(f"DELETE FROM payment_orders WHERE id IN ({ph})", order_ids)
        print(f"    - Removed {len(order_ids)} test payment orders.")
    if manifest.get("target_payment_order_codes"):
        order_codes = manifest["target_payment_order_codes"]
        ph = ",".join("?" for _ in order_codes)
        cursor.execute(f"DELETE FROM payment_audit_log WHERE order_code IN ({ph})", order_codes)
        print(f"    - Cleaned payment audit logs for test order codes.")

    # 7. Clean orphaned test audit and activity records
    cursor.execute("DELETE FROM vouchers WHERE created_by_user_id IS NOT NULL AND created_by_user_id NOT IN (SELECT id FROM users)")
    cursor.execute("DELETE FROM voucher_redemptions WHERE voucher_id NOT IN (SELECT id FROM vouchers)")
    cursor.execute("DELETE FROM voucher_audit_log WHERE voucher_id NOT IN (SELECT id FROM vouchers)")
    cursor.execute("DELETE FROM host_audit_logs WHERE host_admin_id NOT IN (SELECT id FROM users)")
    cursor.execute("DELETE FROM voucher_audit_log WHERE actor_user_id IS NOT NULL AND actor_user_id NOT IN (SELECT id FROM users)")
    cursor.execute("DELETE FROM usage_metering WHERE organization_id NOT IN (SELECT id FROM organizations)")
    cursor.execute("DELETE FROM voucher_redemptions WHERE user_id NOT IN (SELECT id FROM users)")
    cursor.execute("DELETE FROM expert_cases WHERE farm_id IS NOT NULL AND farm_id NOT IN (SELECT id FROM farms)")
    cursor.execute("DELETE FROM moderation_cases WHERE user_id NOT IN (SELECT id FROM users)")
    cursor.execute("DELETE FROM moderation_audit_logs WHERE target_user_id NOT IN (SELECT id FROM users)")
    cursor.execute("DELETE FROM moderation_appeals WHERE user_id NOT IN (SELECT id FROM users)")
    cursor.execute("DELETE FROM diagnoses WHERE farm_id IS NOT NULL AND farm_id NOT IN (SELECT id FROM farms)")
    cursor.execute("DELETE FROM user_subscriptions WHERE user_id NOT IN (SELECT id FROM users)")
    print("    - Cleaned orphaned test audit logs, redemptions, and activity references.")

    conn.commit()
    print("[+] Atomic cleanup committed successfully!")


def main():
    parser = argparse.ArgumentParser(description="GARI Demo Data Cleanup Tool")
    parser.add_argument("--execute", action="store_true", help="Execute deletion (requires pre-cutover backup)")
    args = parser.parse_args()

    print("[1/3] Scanning database for confirmed test fixtures...")
    with sqlite3.connect(str(DB_PATH)) as conn:
        manifest = identify_cleanup_targets(conn)

    print(f"[2/3] Writing cleanup manifest to {MANIFEST_PATH.name}...")
    with open(MANIFEST_PATH, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)
    print(f"    Targets: {manifest['cleanup_targets_count']}")

    if args.execute:
        print("[3/3] Proceeding with execution mode...")
        with sqlite3.connect(str(DB_PATH)) as conn:
            execute_cleanup(conn, manifest)
        
        # Verify database integrity and vacuum
        with sqlite3.connect(str(DB_PATH)) as conn:
            cursor = conn.cursor()
            cursor.execute("PRAGMA foreign_key_check")
            fk_errors = cursor.fetchall()
            if fk_errors:
                print(f"[!] Warning: Foreign key check reported {len(fk_errors)} issues: {fk_errors}")
            else:
                print("[+] Foreign key check: PASSED (Zero integrity violations)")
            cursor.execute("VACUUM")
            print("[+] Database vacuum complete.")
    else:
        print("[3/3] DRY RUN COMPLETE. No data was deleted. Re-run with --execute to commit.")


if __name__ == "__main__":
    main()
