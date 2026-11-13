with open('gari_database.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = """        cursor.execute(\"\"\"
            INSERT INTO expert_case_messages (case_id, sender_user_id, sender_role, sender_name, message, attachments_json, is_internal_note)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        \"\"\", (case_id, sender_user_id, sender_role, sender_name, message.strip(), att_json, 1 if is_internal_note else 0))

        # Update case status if expert replied"""

replacement = """        cursor.execute(\"\"\"
            INSERT INTO expert_case_messages (case_id, sender_user_id, sender_role, sender_name, message, attachments_json, is_internal_note)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        \"\"\", (case_id, sender_user_id, sender_role, sender_name, message.strip(), att_json, 1 if is_internal_note else 0))
        msg_id = cursor.lastrowid

        # Update case status if expert replied"""

if target in text:
    text = text.replace(target, replacement, 1)
    with open('gari_database.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Fixed msg_id capture in gari_database.py")
else:
    print("Target not found in gari_database.py")
