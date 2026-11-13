with open('frontend2/predict.html', 'r', encoding='utf-8') as f:
    for idx, line in enumerate(f):
        for w in ['<body', '<header', 'doctor-hero', 'predict-grid', 'form-card', 'result-card', 'sidebar']:
            if w in line:
                print(f'{idx+1}: {line.strip()[:100]}')
                break
