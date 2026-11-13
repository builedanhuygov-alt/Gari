with open('scratch/test_platform_expansion_suite.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''        data={
            "message": "Thuốc nào phun trị đốm lá cà chua an toàn?",
            "crop": "Tomato",
            "disease": predict_res.get("primary_disease", "Đốm lá")
        },'''

replacement = '''        data={
            "message": "Thuốc nào phun trị đốm lá cà chua an toàn?",
            "diagnosis_id": predict_res.get("diagnosis_id") or predict_res.get("id"),
            "crop": "Tomato",
            "disease": predict_res.get("primary_disease", "Đốm lá")
        },'''

if target in text:
    text = text.replace(target, replacement, 1)
    with open('scratch/test_platform_expansion_suite.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Updated test suite chat call')
else:
    print('Target not found')
