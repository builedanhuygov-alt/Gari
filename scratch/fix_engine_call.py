with open('api_server.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = 'result = engine.predict(dummy_img, top_k=3, crop_filter="Tomato")'
replacement = 'result = engine.predict(dummy_img, top_k=3, crop_id="tomato")'

if target in text:
    text = text.replace(target, replacement, 1)
    with open('api_server.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Replaced successfully in api_server.py')
else:
    print('Target not found')
