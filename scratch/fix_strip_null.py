with open('gari_database.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = """            user_id,
            data.get("full_name", "").strip(),
            data.get("email", "").strip(),
            data.get("phone", "").strip(),
            data.get("institution", "").strip(),
            data.get("degree", "").strip(),
            data.get("specialization", "").strip(),
            primary_crops_json,
            regions_json,
            data.get("bio", "").strip(),
            data.get("certificate_url", "").strip()"""

replacement = """            user_id,
            (data.get("full_name") or "").strip(),
            (data.get("email") or "").strip(),
            (data.get("phone") or "").strip(),
            (data.get("institution") or "").strip(),
            (data.get("degree") or "").strip(),
            (data.get("specialization") or "").strip(),
            primary_crops_json,
            regions_json,
            (data.get("bio") or "").strip(),
            (data.get("certificate_url") or "").strip()"""

if target in text:
    text = text.replace(target, replacement, 1)
    with open('gari_database.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Fixed strip null safety in gari_database.py')
else:
    print('Target not found')
