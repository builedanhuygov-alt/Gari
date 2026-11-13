import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('frontend2/community.html', 'r', encoding='utf-8') as f:
    text = f.read()

print("--- Header & Aside ---")
idx_aside = text.find('<aside')
print(text[idx_aside-50:idx_aside+250])

print("--- Script Tag Area ---")
idx_script = text.find('<script src="/static/frontend2/app.js')
print(text[idx_script:idx_script+500])
