with open('scratch/test_platform_expansion_suite.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''    dummy_img = Image.new("RGB", (224, 224), color=(34, 139, 34))
    buf = io.BytesIO()
    dummy_img.save(buf, format="JPEG")
    leaf_bytes = buf.getvalue()'''

replacement = '''    if os.path.exists("test_leaf.jpg"):
        with open("test_leaf.jpg", "rb") as f:
            leaf_bytes = f.read()
    elif os.path.exists("tests/fixtures/test_leaf.jpg"):
        with open("tests/fixtures/test_leaf.jpg", "rb") as f:
            leaf_bytes = f.read()
    else:
        dummy_img = Image.new("RGB", (224, 224), color=(34, 139, 34))
        buf = io.BytesIO()
        dummy_img.save(buf, format="JPEG")
        leaf_bytes = buf.getvalue()'''

if target in text:
    text = text.replace(target, replacement, 1)
    with open('scratch/test_platform_expansion_suite.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print('Updated test suite to use real leaf fixture')
else:
    print('Target not found')
