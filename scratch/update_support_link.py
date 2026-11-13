with open('frontend2/support.html', 'r', encoding='utf-8') as f:
    text = f.read()

target = '''                        <div class="card">
                            <h4 style="font-size:13.5px; font-weight:700; color:var(--text-main); margin-bottom:6px;">Quy trình tư vấn bệnh học</h4>
                            <p style="font-size:12px; color:var(--text-secondary); line-height:1.4;">
                                Mọi hồ sơ gửi đi sẽ được chuyển tới bác sĩ cây trồng thuộc viện nghiên cứu nông nghiệp đối tác. Kết quả kiểm tra mẫu vi sinh và phác đồ phun phòng sinh học sẽ được cập nhật trực tiếp tại đây.
                            </p>
                        </div>'''

addition = '''

                        <div class="card" style="border-color:rgba(16,185,129,0.3); background:rgba(16,185,129,0.04);">
                            <div style="display:flex; gap:10px; align-items:center; margin-bottom:6px;">
                                <span style="font-size:20px;">👨‍🔬</span>
                                <h4 style="font-size:13.5px; font-weight:700; color:var(--primary); margin:0;">Bạn là Kỹ sư / Chuyên gia Nông nghiệp?</h4>
                            </div>
                            <p style="font-size:12px; color:var(--text-secondary); line-height:1.4; margin-bottom:12px;">
                                Tham gia Mạng lưới Chuyên gia GARI để nhận các ca tư vấn thực địa, kê đơn thuốc và hỗ trợ kỹ thuật số cho hàng ngàn bà con nông dân.
                            </p>
                            <a href="/frontend2/expert-portal.html" class="btn btn-outline" style="width:100%; text-align:center; display:block; text-decoration:none; font-size:12.5px;">
                                Truy cập Cổng Chuyên Gia & Ứng Tuyển &rarr;
                            </a>
                        </div>'''

normalized = text.replace('\r\n', '\n')
if target in normalized:
    normalized = normalized.replace(target, target + addition, 1)
    with open('frontend2/support.html', 'w', encoding='utf-8') as f:
        f.write(normalized)
    print('Updated support.html successfully!')
else:
    print('Target not found in support.html')
