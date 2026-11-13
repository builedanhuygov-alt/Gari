import sqlite3
import os
import glob

def audit_p3():
    conn = sqlite3.connect('database/disease_detector.db')
    cursor = conn.cursor()
    tables = [r[0] for r in cursor.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()]
    print(f"Total tables: {len(tables)}")
    
    keywords = ['farm', 'plot', 'gis', 'map', 'weather', 'satellite', 'risk', 'twin', 'alert', 'sensor', 'geo']
    matched = [t for t in tables if any(k in t.lower() for k in keywords)]
    print("\nMatched existing tables:")
    for t in sorted(matched):
        cols = [c[1] for c in cursor.execute(f"PRAGMA table_info({t})").fetchall()]
        print(f"  - {t}: {', '.join(cols[:8])}{' ...' if len(cols) > 8 else ''}")

    print("\nSearching api_server.py and other files for endpoints...")
    with open('api_server.py', 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()
    
    endpoints = []
    for line in content.split('\n'):
        if line.strip().startswith('@app.') or line.strip().startswith('@router.'):
            endpoints.append(line.strip())
    
    p3_endpoints = [ep for ep in endpoints if any(k in ep.lower() for k in keywords)]
    print(f"Total endpoints in api_server.py: {len(endpoints)}")
    print("Relevant P3-adjacent endpoints:")
    for ep in p3_endpoints:
        print(f"  {ep}")

if __name__ == '__main__':
    audit_p3()

