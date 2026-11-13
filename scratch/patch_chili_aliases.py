import sys

with open('gari_inference_engine.py', 'r', encoding='utf-8') as f:
    text = f.read()

target = '"aliases": ["chili", "chilli", "ớt", "ot", "pepper_bell", "pepper,_bell", "ớt cay", "ớt ngọt", "ớt chuông"]'
replacement = '"aliases": ["chili", "chilli", "ớt", "ot", "bell pepper", "bell_pepper", "pepper_bell", "pepper,_bell", "chili pepper", "ớt cay", "ớt ngọt", "ớt chuông"]'

if target in text:
    text = text.replace(target, replacement, 1)
    with open('gari_inference_engine.py', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Added bell pepper aliases to chili in gari_inference_engine.py")
else:
    print("Target not found")
