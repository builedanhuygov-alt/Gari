with open('frontend2/farms.html', 'r', encoding='utf-8') as f:
    text = f.read()

target = """                    <div style="margin-top:14px; padding-top:10px; border-top:1px solid var(--border); display:flex; gap:6px; justify-content:space-between; align-items:center;">
                        <a href="/frontend2/predict.html?farm_id=${f.id}" class="btn btn-primary btn-sm" style="flex:1;">
                            Chẩn đoán lô
                        </a>
                        <button type="button" class="btn btn-secondary btn-sm" onclick="window.viewPlots(${f.id})" title="Quản lý lô canh tác">
                            Lô (${f.plots ? f.plots.length : 'Lô'})
                        </button>
                        <button type="button" class="btn btn-ghost btn-sm" onclick="window.editFarm(${f.id})" title="Chỉnh sửa nông trại">
                            Sửa
                        </button>
                        <button type="button" class="btn btn-ghost btn-sm" onclick="window.removeFarm(${f.id})" style="color:var(--danger);" title="Xóa nông trại">
                            Xóa
                        </button>
                    </div>"""

replacement = """                    <div style="margin-top:14px; padding-top:10px; border-top:1px solid var(--border); display:flex; gap:6px; justify-content:space-between; align-items:center; flex-wrap:wrap;">
                        <a href="/frontend2/predict.html?farm_id=${f.id}" class="btn btn-primary btn-sm" style="flex:1; min-width:85px;">
                            Chẩn đoán
                        </a>
                        <a href="/api/farms/${f.id}/export-season-report" target="_blank" class="btn btn-secondary btn-sm" title="Xuất Báo cáo Mùa vụ & Nhật ký VietGAP" style="display:inline-flex; align-items:center; gap:4px;">
                            📄 VietGAP
                        </a>
                        <button type="button" class="btn btn-secondary btn-sm" onclick="window.viewPlots(${f.id})" title="Quản lý lô canh tác">
                            Lô (${f.plots ? f.plots.length : '0'})
                        </button>
                        <button type="button" class="btn btn-ghost btn-sm" onclick="window.editFarm(${f.id})" title="Chỉnh sửa nông trại">
                            Sửa
                        </button>
                        <button type="button" class="btn btn-ghost btn-sm" onclick="window.removeFarm(${f.id})" style="color:var(--danger);" title="Xóa nông trại">
                            Xóa
                        </button>
                    </div>"""

target_crlf = target.replace('\n', '\r\n')
replacement_crlf = replacement.replace('\n', '\r\n')

if target_crlf in text:
    text = text.replace(target_crlf, replacement_crlf, 1)
    with open('frontend2/farms.html', 'w', encoding='utf-8') as f:
        f.write(text)
    print("SUCCESS: farms.html updated with CRLF")
elif target in text:
    text = text.replace(target, replacement, 1)
    with open('frontend2/farms.html', 'w', encoding='utf-8') as f:
        f.write(text)
    print("SUCCESS: farms.html updated with LF")
else:
    print("FAILED: target not found")
