with open('frontend2/predict.html', 'r', encoding='utf-8') as f:
    text = f.read()

target = """            if (btnModePro) {
                btnModePro.onclick = () => {
                    currentDiagnosisMode = 'auto_pro';
                    resetModeButtons();
                    btnModePro.classList.add('active');
                    btnModePro.style.borderColor = '#f59e0b';
                    btnModePro.style.background = 'rgba(245,158,11,0.1)';
                    btnModePro.style.color = '#d97706';

                    manualCropGroup.style.display = 'none';
                                        modeExplanation.innerHTML = 'Chế độ Pro: Kiểm định lá cây -> Nhận diện loài thực vật bằng mô hình Pro <strong>Model tong 2 (ViT GBIF 14,829 loài)</strong> -> Tự động chuyển đến mô hình bệnh học tương ứng.';
                };
            }"""

replacement = """            if (btnModePro) {
                btnModePro.onclick = () => {
                    const isVip = (activeUser && activeUser.subscription && activeUser.subscription.is_vip) || (currentQuotaData && currentQuotaData.is_vip);
                    if (!isVip) {
                        window.openProUpgradeModal('Tính năng Tự động Pro (Model ViT GBIF 14,829 loài) yêu cầu tài khoản nâng cấp gói Pro. Vui lòng nâng cấp gói để mở khóa.');
                        return;
                    }
                    currentDiagnosisMode = 'auto_pro';
                    resetModeButtons();
                    btnModePro.classList.add('active');
                    btnModePro.style.borderColor = '#f59e0b';
                    btnModePro.style.background = 'rgba(245,158,11,0.1)';
                    btnModePro.style.color = '#d97706';

                    manualCropGroup.style.display = 'none';
                    modeExplanation.innerHTML = 'Chế độ Pro: Kiểm định lá cây -> Nhận diện loài thực vật bằng mô hình Pro <strong>Model tong 2 (ViT GBIF 14,829 loài)</strong> -> Tự động chuyển đến mô hình bệnh học tương ứng.';
                };
            }"""

if target in text:
    text = text.replace(target, replacement, 1)
    with open('frontend2/predict.html', 'w', encoding='utf-8') as f:
        f.write(text)
    print("SUCCESS: Gated btnModePro click with Pro entitlement check")
else:
    print("Target not found, checking with normalize whitespace")
    # match by index
    idx = text.find("if (btnModePro) {")
    end_idx = text.find("fileInput.addEventListener('change'", idx)
    if idx != -1 and end_idx != -1:
        text = text[:idx] + replacement + "\n\n            " + text[end_idx:]
        with open('frontend2/predict.html', 'w', encoding='utf-8') as f:
            f.write(text)
        print("SUCCESS: Gated btnModePro by index")
