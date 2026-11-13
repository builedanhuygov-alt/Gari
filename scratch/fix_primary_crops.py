with open('frontend2/predict.html', 'r', encoding='utf-8') as f:
    text = f.read()

target = 'primary_crops,'
replacement = 'primary_crops: primary_crops ? primary_crops.split(",").map(s => s.trim()).filter(Boolean) : ["coffee", "pepper"],'
if target in text:
    text = text.replace(target, replacement, 1)
    with open('frontend2/predict.html', 'w', encoding='utf-8') as f:
        f.write(text)
    print("SUCCESS: Updated primary_crops to array in predict.html")
else:
    print("Target not found")
