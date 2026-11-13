with open('gari_database.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = """        conn.commit()
        msg_id = cursor.lastrowid
        cursor.execute("SELECT * FROM expert_case_messages WHERE id = ?", (msg_id,))"""

replacement = """        conn.commit()
        cursor.execute("SELECT * FROM expert_case_messages WHERE id = ?", (msg_id,))"""

if target in text:
    text = text.replace(target, replacement, 1)
    with open('gari_database.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Deleted duplicate cursor.lastrowid successfully.")
else:
    print("Target not found.")
