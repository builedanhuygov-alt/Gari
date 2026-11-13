with open('frontend2/host.html', 'r', encoding='utf-8') as f:
    text = f.read()

box_marker = '<div id="aiTestResultBox"'
box_end = '</div>\n            \n            <div class="host-grid-4">'

# Extract aiTestResultBox
idx1 = text.find(box_marker)
if idx1 != -1:
    idx2 = text.find('</div>\n            \n            <div class="host-grid-4">', idx1)
    if idx2 == -1:
        idx2 = text.find('</div>\n            <div class="host-grid-4">', idx1)
    
    # Remove from tab-overview
    box_html = text[idx1:idx2+6]
    text = text[:idx1] + text[idx2+6:]

    # Place in tab-models
    models_target = '<div class="host-table-wrap">\n                <table class="host-table">\n                    <thead>\n                        <tr>\n                            <th>Mã Cây Trồng</th>'
    if models_target in text:
        text = text.replace(models_target, box_html + '\n\n            ' + models_target, 1)
        with open('frontend2/host.html', 'w', encoding='utf-8') as f:
            f.write(text)
        print("Moved aiTestResultBox into tab-models successfully!")
    else:
        print("models_target not found")
else:
    print("box_marker not found")
