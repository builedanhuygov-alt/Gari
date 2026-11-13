with open('api_server.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = 'SELECT id FROM leaf_diagnoses WHERE user_id = ? ORDER BY id DESC LIMIT 1'
replacement = 'SELECT id FROM diagnoses WHERE user_id = ? ORDER BY id DESC LIMIT 1'

if target in text:
    text = text.replace(target, replacement, 1)
    with open('api_server.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Updated diagnoses table name in api_server.py')
else:
    print('Target not found')
