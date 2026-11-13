import sys
import re

sys.stdout.reconfigure(encoding='utf-8')
with open('frontend2/farms.html', 'r', encoding='utf-8') as f:
    text = f.read()

calls = re.findall(r'(?:fetchJSON|fetch)\([\'"]([^\'"]+)[\'"]', text)
print('API calls in farms.html:', set(calls))

# Also search for template strings like `/api/farms/${...}`
template_calls = re.findall(r'`([^`]*\/api\/[^`]*)`', text)
print('Template API calls in farms.html:', set(template_calls))
