with open('frontend2/predict.html', 'r', encoding='utf-8') as f:
    text = f.read()

target = """                const actions = (ag.immediate_low_risk_actions && ag.immediate_low_risk_actions.length) ? ag.immediate_low_risk_actions : (data.recommendations || [
                    'Kiểm tra thêm các lá xung quanh cây trồng.',
                    'Theo dõi sự thay đổi của vết bệnh sau 2-3 ngày.',
                    'Giữ khu vực trồng thông thoáng, tránh tưới đẫm vào chiều muộn.'
                ]);"""

replacement = """                const actions = (ag.immediate_low_risk_actions && ag.immediate_low_risk_actions.length)
                    ? ag.immediate_low_risk_actions
                    : ((data.recommendations && data.recommendations.length) ? data.recommendations : [
                        'Kiểm tra thêm các lá xung quanh cây trồng.',
                        'Theo dõi sự thay đổi của vết bệnh sau 2-3 ngày.',
                        'Giữ khu vực trồng thông thoáng, tránh tưới đẫm vào chiều muộn.'
                    ]);"""

target_crlf = target.replace('\n', '\r\n')
replacement_crlf = replacement.replace('\n', '\r\n')

if target_crlf in text:
    text = text.replace(target_crlf, replacement_crlf, 1)
    with open('frontend2/predict.html', 'w', encoding='utf-8') as f:
        f.write(text)
    print("SUCCESS: predict.html updated with CRLF")
elif target in text:
    text = text.replace(target, replacement, 1)
    with open('frontend2/predict.html', 'w', encoding='utf-8') as f:
        f.write(text)
    print("SUCCESS: predict.html updated with LF")
else:
    print("FAILED: Target not found")
