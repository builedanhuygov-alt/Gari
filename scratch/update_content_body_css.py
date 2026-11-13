import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('frontend2/style.css', 'r', encoding='utf-8') as f:
    css = f.read()

target = '''.content-body {
        flex: 1;
        min-height: 0;
        min-width: 0;
    }'''

replacement = '''.content-body {
        flex: 1 0 auto;
        min-height: 0;
        min-width: 0;
        overflow-y: visible !important;
        overflow-x: visible;
    }'''

if target not in css:
    print("Error: target not found in style.css")
    sys.exit(1)

css = css.replace(target, replacement, 1)

with open('frontend2/style.css', 'w', encoding='utf-8') as f:
    f.write(css)

print("Successfully updated .content-body in frontend2/style.css!")
