with open("frontend2/predict.html", "r", encoding="utf-8") as f:
    text = f.read()

target = """            if (isLeafMode) {
                setupSaaSShell('leaf_check', 'Kiểm tra sức khỏe lá');
                document.title = 'Kiểm tra sức khỏe lá • Bác Sĩ Cây Trồng AI';
                const headlineEl = document.querySelector('.doctor-headline');
                if (headlineEl) headlineEl.textContent = 'Kiểm tra sức khỏe lá';
            } else {"""

replacement = """            if (isLeafMode) {
                setupSaaSShell('leaf_check', 'Kiểm tra sức khỏe lá');
                document.title = 'Kiểm tra sức khỏe lá • Bác Sĩ Cây Trồng AI';
                const headlineEl = document.querySelector('.doctor-headline');
                if (headlineEl) headlineEl.textContent = 'Kiểm tra sức khỏe lá';
                const h1El = document.querySelector('h1.page-head-title') || document.querySelector('h1');
                if (h1El) h1El.textContent = 'Kiểm tra sức khỏe lá';
            } else {"""

if target in text:
    text = text.replace(target, replacement, 1)
    with open("frontend2/predict.html", "w", encoding="utf-8") as f:
        f.write(text)
    print("Updated predict.html successfully")
else:
    target_crlf = target.replace("\n", "\r\n")
    replacement_crlf = replacement.replace("\n", "\r\n")
    if target_crlf in text:
        text = text.replace(target_crlf, replacement_crlf, 1)
        with open("frontend2/predict.html", "w", encoding="utf-8") as f:
            f.write(text)
        print("Updated CRLF predict.html successfully")
    else:
        print("Target not found in predict.html")
