import sys
sys.stdout.reconfigure(encoding='utf-8')

with open('frontend2/index.html', 'r', encoding='utf-8') as f:
    text = f.read()

# 1. Add scan beam inside preview-img-container
old_preview = '''<div class="preview-img-container">
                                        <img id="previewImgElement" src="" alt="Xem trước ảnh chẩn đoán" class="preview-img">
                                        <div class="reticle-corner top-left"></div>
                                        <div class="reticle-corner top-right"></div>
                                        <div class="reticle-corner bottom-left"></div>
                                        <div class="reticle-corner bottom-right"></div>
                                        <button type="button" class="btn-remove-preview" id="btnRemovePreview" title="Hủy ảnh">✕</button>
                                    </div>'''

new_preview = '''<div class="preview-img-container">
                                        <img id="previewImgElement" src="" alt="Xem trước ảnh chẩn đoán" class="preview-img">
                                        <div class="reticle-corner top-left"></div>
                                        <div class="reticle-corner top-right"></div>
                                        <div class="reticle-corner bottom-left"></div>
                                        <div class="reticle-corner bottom-right"></div>
                                        <div class="diag-scan-beam" id="diagScanBeam"></div>
                                        <button type="button" class="btn-remove-preview" id="btnRemovePreview" title="Hủy ảnh">✕</button>
                                    </div>'''

if old_preview not in text:
    print('Error: old_preview not found')
    sys.exit(1)

text = text.replace(old_preview, new_preview, 1)

# 2. Add scanBeam toggle in executeDiagnosis
old_exec_start = '''async function executeDiagnosis(file) {
            toast('Đang gửi hình ảnh lên mạng nơ-ron GARI AI...', 'info');

            const btnExecute = document.getElementById('btnExecuteDiagnose');
            if (btnExecute) {
                btnExecute.disabled = true;
                btnExecute.innerHTML = '<span>Đang quét...</span>';
            }'''

new_exec_start = '''async function executeDiagnosis(file) {
            toast('Đang gửi hình ảnh lên mạng nơ-ron GARI AI...', 'info');

            const btnExecute = document.getElementById('btnExecuteDiagnose');
            const scanBeam = document.getElementById('diagScanBeam');
            if (scanBeam) scanBeam.classList.add('scanning');

            if (btnExecute) {
                btnExecute.disabled = true;
                btnExecute.innerHTML = '<span>Đang quét...</span>';
            }'''

if old_exec_start not in text:
    print('Error: old_exec_start not found')
    sys.exit(1)

text = text.replace(old_exec_start, new_exec_start, 1)

# In finally block:
old_finally = '''} finally {
                if (btnExecute) {
                    btnExecute.disabled = false;'''

new_finally = '''} finally {
                if (scanBeam) scanBeam.classList.remove('scanning');
                if (btnExecute) {
                    btnExecute.disabled = false;'''

if old_finally not in text:
    print('Error: old_finally not found')
    sys.exit(1)

text = text.replace(old_finally, new_finally, 1)

with open('frontend2/index.html', 'w', encoding='utf-8') as f:
    f.write(text)

print('Successfully updated frontend2/index.html with scan beam and animation hooks!')
