import sqlite3

def audit():
    conn = sqlite3.connect('database/disease_detector.db')
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%' ORDER BY name")
    tables = [r[0] for r in cursor.fetchall()]
    print(f"Total tables: {len(tables)}")
    
    total_rows = 0
    non_empty = []
    for t in tables:
        try:
            cnt = cursor.execute(f'SELECT count(*) FROM "{t}"').fetchone()[0]
            total_rows += cnt
            if cnt > 0:
                non_empty.append((t, cnt))
        except Exception as e:
            print(f"Error reading {t}: {e}")
            
    print(f"Total rows across all tables: {total_rows}")
    print(f"Tables with data ({len(non_empty)} tables):")
    for t, cnt in sorted(non_empty, key=lambda x: -x[1]):
        print(f"  - {t}: {cnt} rows")

if __name__ == '__main__':
    audit()

