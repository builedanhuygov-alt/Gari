import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('frontend2/app.js', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''    if (backdrop && sidebar) {
        backdrop.onclick = () => {
            sidebar.classList.remove('drawer-open');
            backdrop.classList.remove('show');
        };
    }'''

replacement = '''    if (backdrop && sidebar) {
        backdrop.onclick = () => {
            sidebar.classList.remove('drawer-open');
            backdrop.classList.remove('show');
        };
    }

    // Close mobile drawer when clicking navigation link
    if (sidebar) {
        sidebar.querySelectorAll('.nav-link').forEach(link => {
            link.addEventListener('click', () => {
                if (window.innerWidth <= 1024) {
                    sidebar.classList.remove('drawer-open');
                    if (backdrop) backdrop.classList.remove('show');
                }
            });
        });
    }'''

if target not in text:
    print("Error: target not found in app.js")
    sys.exit(1)

text = text.replace(target, replacement, 1)

with open('frontend2/app.js', 'w', encoding='utf-8') as f:
    f.write(text)

print("Successfully updated frontend2/app.js with mobile drawer link auto-close!")
