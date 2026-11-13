import sqlite3
import json
import sys

sys.stdout.reconfigure(encoding="utf-8")
conn = sqlite3.connect("database/disease_detector.db")
conn.row_factory = sqlite3.Row

test_org_query = """
SELECT id, name, slug, owner_id FROM organizations 
WHERE name LIKE '%Test%' 
   OR name LIKE '%Cô Đơn%'
   OR name LIKE '%cô đơn%'
   OR slug LIKE '%co-don%'
   OR slug LIKE '%cô-đơn%'
   OR slug LIKE 'test-%'
   OR slug LIKE 'audit-%'
   OR slug LIKE 'payment-%'
   OR (name LIKE '%Nông Dân 7%' AND id > 2)
"""

test_orgs = [dict(r) for r in conn.execute(test_org_query)]
print(f"TEST ORGS COUNT: {len(test_orgs)}")
for o in test_orgs:
    print(f"  [TEST] ID={o['id']}: {o['name']} ({o['slug']}) - owner_id={o['owner_id']}")

real_org_query = f"""
SELECT id, name, slug, owner_id FROM organizations 
WHERE id NOT IN ({test_org_query.replace('SELECT id, name, slug, owner_id', 'SELECT id')})
"""
print("\n--- FARMS CHECK ---")
test_farm_query = """
SELECT id, user_id, name, province, primary_crop FROM farms
WHERE name LIKE '%17934%'
   OR name LIKE '%(Đã cập nhật)%'
   OR name LIKE 'Test %'
"""
test_farms = [dict(r) for r in conn.execute(test_farm_query)]
print(f"TEST FARMS COUNT: {len(test_farms)}")
for f in test_farms:
    print(f"  [TEST FARM] ID={f['id']}: {f['name']} - user_id={f['user_id']}")

real_farm_query = f"""
SELECT id, user_id, name, province, primary_crop FROM farms
WHERE id NOT IN ({test_farm_query.replace('SELECT id, user_id, name, province, primary_crop', 'SELECT id')})
"""
real_farms = [dict(r) for r in conn.execute(real_farm_query)]
print(f"\nREAL FARMS COUNT: {len(real_farms)}")
for f in real_farms:
    print(f"  [REAL FARM] ID={f['id']}: {f['name']} ({f['province']}) - user_id={f['user_id']}")

