with open("frontend2/host.html", "r", encoding="utf-8") as f:
    text = f.read()

target = """<div class="host-brand-title">
                    GARI Host Server Admin Console
                    <span class="host-pill host-pill-active" id="serverStatePill">Hệ thống sẵn sàng</span>
                </div>"""

replacement = """<h1 class="host-brand-title" style="margin:0; font-size:16px;">
                    GARI Host Server Admin Console
                    <span class="host-pill host-pill-active" id="serverStatePill">Hệ thống sẵn sàng</span>
                </h1>"""

if target in text:
    text = text.replace(target, replacement, 1)
    with open("frontend2/host.html", "w", encoding="utf-8") as f:
        f.write(text)
    print("Replaced in host.html successfully")
else:
    # Check with CRLF
    target_crlf = target.replace("\n", "\r\n")
    replacement_crlf = replacement.replace("\n", "\r\n")
    if target_crlf in text:
        text = text.replace(target_crlf, replacement_crlf, 1)
        with open("frontend2/host.html", "w", encoding="utf-8") as f:
            f.write(text)
        print("Replaced CRLF in host.html successfully")
    else:
        print("Target not found in host.html")
