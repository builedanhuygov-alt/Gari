// Demo prediction results - fixed predictions for testing
export const DEMO_PREDICTIONS = {
    'tomato_early_blight': {
        success: true,
        prediction: {
            prediction: 'Bệnh cháy lá sớm cà chua (Early Blight)',
            confidence: 0.92,
            originalPrediction: 'Bệnh cháy lá sớm cà chua',
            source: 'Gari AI Lab v3.0 - Demo Mode',
            crop: 'Cà chua',
            cropType: 'Cà chua',
            isHealthy: false,
            symptoms: [
                'Đốm tròn với các vành tay đàn rõ (3-10mm)',
                'Viền lá bị cháy nâu đỏ',
                'Tâm đốm có vòng nâu vàng',
                'Lá héo, vàng, rụng',
                'Bắt đầu từ lá dưới cùng'
            ],
            treatment: [
                'Phun Chlorothalonil 72% SC 2ml/lít',
                'Phun Mancozeb 80% WP 3g/lít',
                'Cắt bỏ lá bệnh ngay',
                'Phun từ sớm, tiếp tục 7 ngày/lần'
            ],
            prevention: [
                'Tránh tưới lên lá, tưới gốc',
                'Hạn chế độ ẩm, tăng thông gió',
                'Bón phân khoáng cân đối'
            ],
            causes: 'Nấm Alternaria solani',
            severity: 'CAO',
            riskLevel: 4,
            economicImpact: 'Có thể mất 40-100% vụ',
            processingTime: 1250,
            modelInfo: {
                name: 'AI Crop Classification + Disease Detection v3.0',
                version: '3.0.0',
                modelsUsed: 2,
                totalModels: 2
            },
            detailedAnalysisReport: {
                summaryAnalysis: 'Cà chua bị bệnh cháy lá sớm với mức độ cao, cần xử lý ngay',
                diseaseProgression: 'Bệnh sẽ lan rộng từ lá dưới lên trên trong 7-14 ngày nếu không điều trị',
                treatmentStrategy: 'Bắt đầu phun fungicide từ sớm, lặp lại 7 ngày/lần',
                economicRecommendation: 'Ưu tiên cao - mất 40-100% sản lượng nếu không kiểm soát',
                riskAssessment: 'Rủi ro rất cao trong điều kiện ẩm ướt'
            },
            detailedAnalysisFormatted: `
╔════════════════════════════════════════════════════════════════╗
║         PHÂN TÍCH CHI TIẾT BỆNH CÀ CHUA                       ║
╚════════════════════════════════════════════════════════════════╝

📊 CHẨN ĐOÁN: Bệnh cháy lá sớm cà chua (Early Blight)
   Độ tin cậy: 92% | Mức độ nghiêm trọng: CAO

🔍 TRIỆU CHỨNG:
   • Đốm tròn với vành tay đàn rõ (3-10mm)
   • Viền lá bị cháy nâu đỏ, tâm xám
   • Vòng nâu vàng quanh đốm bệnh
   • Lá héo, vàng từ từ rồi rụng
   • Bắt đầu từ lá dưới cùng

🧬 NGUYÊN NHÂN: Nấm Alternaria solani
   Điều kiện thuận lợi:
   • Độ ẩm cao >70%
   • Mưa lớn kéo dài
   • Nhiệt độ 20-25°C lý tưởng
   • Tưới nước lên lá

📈 DỰ PHÓNG:
   • 7-14 ngày: Bệnh lan rộng từ lá dưới lên
   • Mất 30-50% năng suất nếu không điều trị
   • Có thể mất toàn bộ vụ (40-100%) nếu bỏ qua

💊 ĐIỀU TRỊ NGAY:
   1. Phun Chlorothalonil 72% SC 2ml/lít
   2. Phun Mancozeb 80% WP 3g/lít  
   3. Cắt bỏ lá bệnh ngay
   4. Lặp lại 7 ngày/lần cho đến khi bệnh kiểm soát

🛡️ PHÒNG NGỪA:
   • Tránh tưới lên lá, tưới gốc
   • Hạn chế độ ẩm, tăng thông gió
   • Bón phân NPK cân đối
   • Thu dọn lá bệnh ngay

⚠️ RỦI RO: RẤT CAO - Cần xử lý tức thì
      `
        },
        imageInfo: {
            filename: 'tomato_early_blight.jpg',
            size: 245000,
            contentType: 'image/jpeg'
        },
        timestamp: new Date().toISOString()
    },

    'coffee_leaf_rust': {
        success: true,
        prediction: {
            prediction: 'Bệnh rôi lá cà phê (Leaf Rust)',
            confidence: 0.88,
            originalPrediction: 'Bệnh rôi lá cà phê',
            source: 'Gari AI Lab v3.0 - Demo Mode',
            crop: 'Cà phê',
            cropType: 'Cà phê',
            isHealthy: false,
            symptoms: [
                'Vệ màu nâu đỏ trên mặt dưới lá',
                'Lá vàng từ từ',
                'Có bột nâu dưới lá',
                'Lá rơi sớm'
            ],
            treatment: [
                'Phun Sulfur 80% WP 2-3g/lít',
                'Phun Myclobutanil 10% WP 1-2g/lít',
                'Cắt bỏ lá bệnh ngay'
            ],
            prevention: [
                'Tỉa cây thưa để thông gió',
                'Tránh tưới lên lá',
                'Thu dọn lá bệnh'
            ],
            causes: 'Nấm Hemileia vastatrix',
            severity: 'RẤT CAO',
            riskLevel: 5,
            economicImpact: 'Mất 50-90% sản lượng',
            processingTime: 1180,
            modelInfo: {
                name: 'AI Crop Classification + Disease Detection v3.0',
                version: '3.0.0',
                modelsUsed: 2,
                totalModels: 2
            },
            detailedAnalysisFormatted: `
╔════════════════════════════════════════════════════════════════╗
║         PHÂN TÍCH CHI TIẾT BỆNH CÀ PHÊ                        ║
╚════════════════════════════════════════════════════════════════╝

📊 CHẨN ĐOÁN: Bệnh rôi lá cà phê (Leaf Rust)
   Độ tin cậy: 88% | Mức độ nghiêm trọng: RẤT CAO ⚠️

🔍 TRIỆU CHỨNG:
   • Vệ màu nâu đỏ trên mặt dưới lá
   • Bột nâu (sporangia) dưới lá
   • Lá vàng từ từ rồi rụng
   • Mất nhiều lá, cành trần

🧬 NGUYÊN NHÂN: Nấm Hemileia vastatrix
   Điều kiện thuận lợi:
   • Độ ẩm cao 90%+
   • Nhiệt độ 20-24°C
   • Cây trồng dày đặc
   • Thông gió kém

📈 ĐÂY LÀ BỆNH NGUY HIỂM NHẤT CÀ PHÊ:
   • Mất 50-90% sản lượng
   • Có thể hủy hoại cả vùng canh tác
   • Cần kiểm soát tức thì

💊 ĐIỀU TRỊ KHẨN CẤP:
   1. Phun Sulfur 80% WP 2-3g/lít (tuần 1)
   2. Phun Myclobutanil 10% WP 1-2g/lít (tuần 2)
   3. Cắt bỏ toàn bộ lá bệnh
   4. Phun lặp lại 10-14 ngày/lần

🛡️ PHÒNG NGỪA DỮ:
   • Tỉa cây thưa (30-40% ánh sáng)
   • Tránh tưới lên lá, tưới gốc
   • Thu dọc lá bệnh ngay
   • Vệ sinh dụng cụ

⚠️ RỦI RO: CỰC KỲGGGHIỂM TRỌNG
      `
        },
        imageInfo: {
            filename: 'coffee_leaf_rust.jpg',
            size: 280000,
            contentType: 'image/jpeg'
        },
        timestamp: new Date().toISOString()
    },

    'durian_fruit_rot': {
        success: true,
        prediction: {
            prediction: 'Bệnh thối quả sầu riêng (Fruit Rot)',
            confidence: 0.85,
            originalPrediction: 'Bệnh thối quả sầu riêng',
            source: 'Gari AI Lab v3.0 - Demo Mode',
            crop: 'Sầu riêng',
            cropType: 'Sầu riêng',
            isHealthy: false,
            symptoms: [
                'Quả bị mềm, chảy nước',
                'Mùi lạ hôi thúi',
                'Nấm phát triển trên bề mặt',
                'Quả khô cháy'
            ],
            treatment: [
                'Phun fungicide từ sớm',
                'Cắt bỏ quả bệnh ngay'
            ],
            prevention: [
                'Tránh tưới lên quả',
                'Hạn chế độ ẩm',
                'Thu dọn lá rơi'
            ],
            causes: 'Nấm Phytophthora, Fusarium, Botryodiplodia',
            severity: 'CAO',
            riskLevel: 4,
            economicImpact: 'Mất 30-50% sản lượng quả',
            processingTime: 1320,
            detailedAnalysisFormatted: `
╔════════════════════════════════════════════════════════════════╗
║        PHÂN TÍCH CHI TIẾT BỆNH SẦU RIÊNG                      ║
╚════════════════════════════════════════════════════════════════╝

📊 CHẨN ĐOÁN: Bệnh thối quả sầu riêng (Fruit Rot)
   Độ tin cậy: 85% | Mức độ nghiêm trọng: CAO

🔍 TRIỆU CHỨNG:
   • Quả bị mềm, nước chảy ra
   • Mùi lạ, hôi thúi
   • Nấm phát triển trên bề mặt
   • Quả khô cháy phần ngoài

🧬 NGUYÊN NHÂN: 
   • Nấm Phytophthora palmivora
   • Nấm Fusarium
   • Nấm Botryodiplodia

📈 TÌNH HÌNH:
   • Mất 30-50% sản lượng quả
   • Quả không thể bán
   • Cần xử lý ngay

💊 ĐIỀU TRỊ:
   1. Cắt bỏ quả bệnh ngay
   2. Phun fungicide từ sớm
   3. Cơ bản hóa vườn

🛡️ PHÒNG NGỪA:
   • Tránh tưới lên quả
   • Hạn chế độ ẩm
   • Thu dọn lá rơi

⚠️ RỦI RO: CAO - Tác động kinh tế lớn
      `
        },
        imageInfo: {
            filename: 'durian_fruit_rot.jpg',
            size: 310000,
            contentType: 'image/jpeg'
        },
        timestamp: new Date().toISOString()
    },

    'healthy_leaf': {
        success: true,
        prediction: {
            prediction: 'Lá khỏe mạnh (Healthy Leaf)',
            confidence: 0.95,
            originalPrediction: 'Lá khỏe mạnh',
            source: 'Gari AI Lab v3.0 - Demo Mode',
            crop: 'Không xác định',
            cropType: 'Unknown',
            isHealthy: true,
            symptoms: ['Lá xanh tươi đều', 'Không có đốm hay vệ bệnh', 'Bề mặt lá bóng mịn'],
            treatment: ['Tiếp tục chăm sóc bình thường'],
            prevention: ['Duy trì tình trạng hiện tại', 'Kiểm tra định kỳ'],
            causes: 'Cây khỏe mạnh',
            severity: 'KHÔNG',
            riskLevel: 0,
            economicImpact: 'Không có tác động âm tính',
            processingTime: 890,
            detailedAnalysisFormatted: `
╔════════════════════════════════════════════════════════════════╗
║           CÂY KHỎE MẠNH - KHÔNG CÓ BỆNH                       ║
╚════════════════════════════════════════════════════════════════╝

✅ CHẨN ĐOÁN: Lá khỏe mạnh
   Độ tin cậy: 95% | Mức độ: LÀNH LẶNG

🔍 TÌNH TRẠNG:
   • Lá xanh tươi đều
   • Không có đốm hay vệ bệnh
   • Bề mặt lá bóng mịn
   • Phát triển bình thường

✨ KHUYẾN CÁO:
   • Tiếp tục chăm sóc bình thường
   • Kiểm tra định kỳ
   • Duy trì dinh dưỡng tốt
   • Tưới nước thích hợp

🛡️ PHÒNG NGỪA:
   • Bón phân NPK cân đối
   • Hạn chế độ ẩm thừa
   • Thu dọn cỏ dại
   • Kiểm tra côn trùng

✅ KHÔNG CÓ RỦI RO - Cây đang rất khỏe!
      `
        },
        imageInfo: {
            filename: 'healthy_leaf.jpg',
            size: 185000,
            contentType: 'image/jpeg'
        },
        timestamp: new Date().toISOString()
    }
};

// Get demo prediction by type
export const getDemoPrediction = (type: string = 'default') => {
    const demoType = type.toLowerCase() || 'tomato_early_blight';
    return DEMO_PREDICTIONS[demoType as keyof typeof DEMO_PREDICTIONS] || DEMO_PREDICTIONS['tomato_early_blight'];
};

export default DEMO_PREDICTIONS;
