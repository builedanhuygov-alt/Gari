with open('frontend2/predict.html', 'r', encoding='utf-8') as f:
    text = f.read()

target = """                                <div class="report-section">
                                    <span class="report-label">Nguyên nhân có thể:</span>
                                    <ul class="report-list" id="repCausesList"></ul>
                                </div>"""

replacement = """                                <div class="report-section">
                                    <span class="report-label">Nguyên nhân có thể:</span>
                                    <ul class="report-list" id="repCausesList"></ul>
                                </div>

                                <div class="report-section" id="repRecommendationsSection">
                                    <span class="report-label" style="color:var(--primary); font-weight:700;">🌱 Khuyến nghị xử lý & Lập lịch canh tác tức thì:</span>
                                    <ul class="report-list" id="repRecommendationsList"></ul>
                                </div>"""

target_crlf = target.replace('\n', '\r\n')
replacement_crlf = replacement.replace('\n', '\r\n')

if target_crlf in text:
    text = text.replace(target_crlf, replacement_crlf, 1)
    with open('frontend2/predict.html', 'w', encoding='utf-8') as f:
        f.write(text)
    print("SUCCESS: repRecommendationsList added (CRLF)")
elif target in text:
    text = text.replace(target, replacement, 1)
    with open('frontend2/predict.html', 'w', encoding='utf-8') as f:
        f.write(text)
    print("SUCCESS: repRecommendationsList added (LF)")
else:
    print("FAILED: Target not found")
