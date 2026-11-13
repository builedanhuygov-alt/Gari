with open('frontend2/host.html', 'r', encoding='utf-8') as f:
    text = f.read()

if 'function escapeHtml(' not in text:
    js_esc = '''
        function escapeHtml(str) {
            if (!str) return '';
            return String(str)
                .replace(/&/g, '&amp;')
                .replace(/</g, '&lt;')
                .replace(/>/g, '&gt;')
                .replace(/"/g, '&quot;');
        }
'''
    idx = text.rfind('</script>')
    text = text[:idx] + js_esc + '\n    ' + text[idx:]
    with open('frontend2/host.html', 'w', encoding='utf-8') as f:
        f.write(text)
    print("Added escapeHtml to host.html")
else:
    print("escapeHtml already in host.html")
