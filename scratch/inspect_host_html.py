import re

with open('frontend2/host.html', 'r', encoding='utf-8') as f:
    text = f.read()

tabs = re.findall(r'data-tab="([^"]+)"', text)
print("Tabs in host.html:", list(dict.fromkeys(tabs)))

# Look for tab buttons/navigation in host.html
nav_matches = re.findall(r'<button[^>]*class="[^"]*nav-item[^"]*"[^>]*>([\s\S]*?)</button>', text)
print(f"Nav buttons count: {len(nav_matches)}")
for btn in nav_matches[:10]:
    clean = re.sub(r'<[^>]+>', '', btn).strip()
    print(" - Nav button:", clean)
