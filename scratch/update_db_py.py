with open('gari_database.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Update migration in init_db
old_diag_mig = '''            ("monitoring_notes", "TEXT"),
            ("consent_store_image", "BOOLEAN DEFAULT 0")
        ]:'''
new_diag_mig = '''            ("monitoring_notes", "TEXT"),
            ("consent_store_image", "BOOLEAN DEFAULT 0"),
            ("growth_stage", "TEXT"),
            ("user_symptoms", "TEXT"),
            ("field_conditions", "TEXT"),
            ("image_references_json", "TEXT")
        ]:'''

if old_diag_mig in content:
    content = content.replace(old_diag_mig, new_diag_mig, 1)
    print("Updated diag migrations")
else:
    print("Diag migrations target not found")

old_chat_mig = '''        # Create Sprint 4 indexes'''
new_chat_mig = '''        # Migrate chat_history columns if missing
        chat_cols = [r[1] for r in cursor.execute("PRAGMA table_info(chat_history)").fetchall()]
        if "actions_json" not in chat_cols:
            try:
                cursor.execute("ALTER TABLE chat_history ADD COLUMN actions_json TEXT;")
            except Exception:
                pass

        # Create Sprint 4 indexes'''

if old_chat_mig in content:
    content = content.replace(old_chat_mig, new_chat_mig, 1)
    print("Updated chat migrations")
else:
    print("Chat migrations target not found")

# 2. Update save_diagnosis SQL
old_insert = 'attention_path, overlay_path, regions_json\n            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n        """, ('

new_insert = 'attention_path, overlay_path, regions_json,\n                growth_stage, user_symptoms, field_conditions, image_references_json\n            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)\n        """, ('

if old_insert in content:
    content = content.replace(old_insert, new_insert, 1)
    print("Updated insert query")
else:
    print("Insert query target not found")

old_params = 'json.dumps(regions_data) if isinstance(regions_data, (list, dict)) else str(regions_data)\n        ))'

new_params = 'json.dumps(regions_data) if isinstance(regions_data, (list, dict)) else str(regions_data),\n            data.get("growth_stage"),\n            data.get("user_symptoms"),\n            data.get("field_conditions"),\n            json.dumps(data.get("image_references", [])) if isinstance(data.get("image_references"), (list, dict)) else data.get("image_references_json")\n        ))'

if old_params in content:
    content = content.replace(old_params, new_params, 1)
    print("Updated insert params")
else:
    print("Insert params target not found")

with open('gari_database.py', 'w', encoding='utf-8', newline='') as f:
    f.write(content)
print("Done updating gari_database.py")
