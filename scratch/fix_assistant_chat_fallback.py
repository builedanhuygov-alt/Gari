with open('api_server.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = """    diag_id = payload.get("diagnosis_id")
    if not diag_id:
        raise HTTPException(status_code=400, detail="Thiếu diagnosis_id cho phiên giải thích bệnh học.")"""

replacement = """    diag_id = payload.get("diagnosis_id")
    if not diag_id:
        with gari_database.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT id FROM leaf_diagnoses WHERE user_id = ? ORDER BY id DESC LIMIT 1", (user_id,))
            row = cursor.fetchone()
            if row:
                diag_id = row["id"]
            else:
                diag_id = 1"""

if target in text:
    text = text.replace(target, replacement, 1)
    with open('api_server.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Updated assistant_chat_message with graceful fallback')
else:
    print('Target not found')
