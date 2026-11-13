import sqlite3

conn = sqlite3.connect("database/staging_disease_detector.db")
cur = conn.cursor()

cur.execute("SELECT id, user_id FROM diagnoses LIMIT 5;")
rows = cur.fetchall()
print("Diagnoses rows:", rows)

cur.execute("PRAGMA table_info(diagnostic_triage_records);")
print("diagnostic_triage_records cols:", cur.fetchall())

try:
    cur.execute("""
        INSERT INTO diagnostic_triage_records (
            diagnosis_id, user_id, triage_state, urgency_level, explanation_vi, explanation_en
        ) VALUES (?, ?, 'NORMAL', 'low', 'test vi', 'test en')
    """, (rows[0][0], rows[0][1]))
    conn.commit()
    print("Insert succeeded! Lastrowid:", cur.lastrowid)
except Exception as e:
    print("Insert failed:", e)

conn.close()

