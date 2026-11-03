"""
GARI AI LAB — Centralized Vietnamese Localization Engine
Generates:
1. localization/crop_vi.json
2. localization/disease_vi.json
3. localization/symptom_vi.json
4. localization/recommendation_vi.json
"""

import json
from pathlib import Path

LOC_DIR = Path("D:/leaf-diseases-detector-main/localization")
LOC_DIR.mkdir(parents=True, exist_ok=True)

# 1. Crops Localization (crop_vi.json)
CROPS_VI = {
    "Apple": {
        "name_vi": "Cà chua",
        "name_vi": "Táo tây",
        "common_name": "Cây táo tây",
        "scientific_name": "Malus domestica",
        "family": "Họ Hoa hồng (Rosaceae)"
    },
    "Apricot": {
        "name_vi": "Mơ tây",
        "common_name": "Cây mơ tây",
        "scientific_name": "Prunus armeniaca",
        "family": "Họ Hoa hồng (Rosaceae)"
    },
    "Banana": {
        "name_vi": "Chuối",
        "common_name": "Cây chuối",
        "scientific_name": "Musa acuminata",
        "family": "Họ Chuối (Musaceae)"
    },
    "Betel": {
        "name_vi": "Trầu không",
        "common_name": "Cây trầu không",
        "scientific_name": "Piper betle",
        "family": "Họ Hồ tiêu (Piperaceae)"
    },
    "Bitter_gourd": {
        "name_vi": "Mướp đắng (Khổ qua)",
        "common_name": "Cây mướp đắng",
        "scientific_name": "Momordica charantia",
        "family": "Họ Bầu bí (Cucurbitaceae)"
    },
    "Black_Pepper": {
        "name_vi": "Hồ tiêu",
        "common_name": "Cây hồ tiêu",
        "scientific_name": "Piper nigrum",
        "family": "Họ Hồ tiêu (Piperaceae)"
    },
    "Blueberry": {
        "name_vi": "Việt quất",
        "common_name": "Cây việt quất",
        "scientific_name": "Vaccinium corymbosum",
        "family": "Họ Thạch nam (Ericaceae)"
    },
    "Bottle_gourd": {
        "name_vi": "Bầu sao (Bầu nậm)",
        "common_name": "Cây bầu",
        "scientific_name": "Lagenaria siceraria",
        "family": "Họ Bầu bí (Cucurbitaceae)"
    },
    "Brinjal": {
        "name_vi": "Cà tím",
        "common_name": "Cây cà tím",
        "scientific_name": "Solanum melongena",
        "family": "Họ Cà (Solanaceae)"
    },
    "Cashew": {
        "name_vi": "Điều (Đào lộn hột)",
        "common_name": "Cây điều",
        "scientific_name": "Anacardium occidentale",
        "family": "Họ Đào lộn hột (Anacardiaceae)"
    },
    "Cassava": {
        "name_vi": "Sắn (Khoai mì)",
        "common_name": "Cây sắn",
        "scientific_name": "Manihot esculenta",
        "family": "Họ Đại kích (Euphorbiaceae)"
    },
    "Cherry": {
        "name_vi": "Anh đào (Cherry)",
        "common_name": "Cây anh đào",
        "scientific_name": "Prunus avium",
        "family": "Họ Hoa hồng (Rosaceae)"
    },
    "Chrysanthemum": {
        "name_vi": "Hoa cúc",
        "common_name": "Cây hoa cúc",
        "scientific_name": "Chrysanthemum morifolium",
        "family": "Họ Cúc (Asteraceae)"
    },
    "Citrus": {
        "name_vi": "Cây có múi (Cam, Chanh, Bưởi)",
        "common_name": "Cây có múi",
        "scientific_name": "Citrus spp.",
        "family": "Họ Cửu lý hương (Rutaceae)"
    },
    "Coconut": {
        "name_vi": "Dừa",
        "common_name": "Cây dừa",
        "scientific_name": "Cocos nucifera",
        "family": "Họ Cau (Arecaceae)"
    },
    "Coffee": {
        "name_vi": "Cà phê",
        "common_name": "Cây cà phê",
        "scientific_name": "Coffea canephora / Coffea arabica",
        "family": "Họ Cà phê (Rubiaceae)"
    },
    "Corn": {
        "name_vi": "Ngô (Bắp)",
        "common_name": "Cây ngô",
        "scientific_name": "Zea mays",
        "family": "Họ Hòa thảo (Poaceae)"
    },
    "Cucumber": {
        "name_vi": "Dưa chuột (Dưa leo)",
        "common_name": "Cây dưa chuột",
        "scientific_name": "Cucumis sativus",
        "family": "Họ Bầu bí (Cucurbitaceae)"
    },
    "Cucurbit": {
        "name_vi": "Họ bầu bí (Bí ngô, Dưa)",
        "common_name": "Cây họ bầu bí",
        "scientific_name": "Cucurbita spp.",
        "family": "Họ Bầu bí (Cucurbitaceae)"
    },
    "Custard_apple": {
        "name_vi": "Mãng cầu ta (Na)",
        "common_name": "Cây na",
        "scientific_name": "Annona squamosa",
        "family": "Họ Na (Annonaceae)"
    },
    "Fig": {
        "name_vi": "Quả sung (Vả tây)",
        "common_name": "Cây sung tây",
        "scientific_name": "Ficus carica",
        "family": "Họ Dâu tằm (Moraceae)"
    },
    "Grape": {
        "name_vi": "Nho",
        "common_name": "Cây nho",
        "scientific_name": "Vitis vinifera",
        "family": "Họ Nho (Vitaceae)"
    },
    "Guava": {
        "name_vi": "Ổi",
        "common_name": "Cây ổi",
        "scientific_name": "Psidium guajava",
        "family": "Họ Đào kim nương (Myrtaceae)"
    },
    "Loquat": {
        "name_vi": "Sơn tra (Tỳ bà)",
        "common_name": "Cây tỳ bà",
        "scientific_name": "Eriobotrya japonica",
        "family": "Họ Hoa hồng (Rosaceae)"
    },
    "Maize": {
        "name_vi": "Ngô (Bắp)",
        "common_name": "Cây ngô",
        "scientific_name": "Zea mays",
        "family": "Họ Hòa thảo (Poaceae)"
    },
    "Mango": {
        "name_vi": "Xoài",
        "common_name": "Cây xoài",
        "scientific_name": "Mangifera indica",
        "family": "Họ Đào lộn hột (Anacardiaceae)"
    },
    "Mulberry": {
        "name_vi": "Dâu tằm",
        "common_name": "Cây dâu tằm",
        "scientific_name": "Morus alba",
        "family": "Họ Dâu tằm (Moraceae)"
    },
    "okra": {
        "name_vi": "Đậu bắp",
        "common_name": "Cây đậu bắp",
        "scientific_name": "Abelmoschus esculentus",
        "family": "Họ Cẩm quỳ (Malvaceae)"
    },
    "Orange": {
        "name_vi": "Cam",
        "common_name": "Cây cam",
        "scientific_name": "Citrus sinensis",
        "family": "Họ Cửu lý hương (Rutaceae)"
    },
    "Papaya": {
        "name_vi": "Đu đủ",
        "common_name": "Cây đu đủ",
        "scientific_name": "Carica papaya",
        "family": "Họ Đu đủ (Caricaceae)"
    },
    "Peach": {
        "name_vi": "Đào",
        "common_name": "Cây đào",
        "scientific_name": "Prunus persica",
        "family": "Họ Hoa hồng (Rosaceae)"
    },
    "Pear": {
        "name_vi": "Lê",
        "common_name": "Cây lê",
        "scientific_name": "Pyrus communis",
        "family": "Họ Hoa hồng (Rosaceae)"
    },
    "Pepper": {
        "name_vi": "Ớt ngọt (Ớt chuông)",
        "common_name": "Cây ớt ngọt",
        "scientific_name": "Capsicum annuum",
        "family": "Họ Cà (Solanaceae)"
    },
    "pomrgranet": {
        "name_vi": "Lựu",
        "common_name": "Cây lựu",
        "scientific_name": "Punica granatum",
        "family": "Họ Thạch lựu (Lythraceae)"
    },
    "Potato": {
        "name_vi": "Khoai tây",
        "common_name": "Cây khoai tây",
        "scientific_name": "Solanum tuberosum",
        "family": "Họ Cà (Solanaceae)"
    },
    "Raspberry": {
        "name_vi": "Mâm xôi",
        "common_name": "Cây mâm xôi",
        "scientific_name": "Rubus idaeus",
        "family": "Họ Hoa hồng (Rosaceae)"
    },
    "Rice": {
        "name_vi": "Lúa nước",
        "common_name": "Cây lúa",
        "scientific_name": "Oryza sativa",
        "family": "Họ Hòa thảo (Poaceae)"
    },
    "Ridge_gourd": {
        "name_vi": "Mướp khía",
        "common_name": "Cây mướp khía",
        "scientific_name": "Luffa acutangula",
        "family": "Họ Bầu bí (Cucurbitaceae)"
    },
    "Rose": {
        "name_vi": "Hoa hồng",
        "common_name": "Cây hoa hồng",
        "scientific_name": "Rosa spp.",
        "family": "Họ Hoa hồng (Rosaceae)"
    },
    "Snake_gourd": {
        "name_vi": "Mướp rắn",
        "common_name": "Cây mướp rắn",
        "scientific_name": "Trichosanthes cucumerina",
        "family": "Họ Bầu bí (Cucurbitaceae)"
    },
    "Soybean": {
        "name_vi": "Đậu nành (Đậu tương)",
        "common_name": "Cây đậu tương",
        "scientific_name": "Glycine max",
        "family": "Họ Đậu (Fabaceae)"
    },
    "Squash": {
        "name_vi": "Bí ngô (Bí đỏ)",
        "common_name": "Cây bí đỏ",
        "scientific_name": "Cucurbita pepo",
        "family": "Họ Bầu bí (Cucurbitaceae)"
    },
    "Strawberry": {
        "name_vi": "Dâu tây",
        "common_name": "Cây dâu tây",
        "scientific_name": "Fragaria × ananassa",
        "family": "Họ Hoa hồng (Rosaceae)"
    },
    "Sugarcane": {
        "name_vi": "Mía",
        "common_name": "Cây mía",
        "scientific_name": "Saccharum officinarum",
        "family": "Họ Hòa thảo (Poaceae)"
    },
    "Tea": {
        "name_vi": "Chè (Trà)",
        "common_name": "Cây chè",
        "scientific_name": "Camellia sinensis",
        "family": "Họ Chè (Theaceae)"
    },
    "Tomato": {
        "name_vi": "Cà chua",
        "common_name": "Cây cà chua",
        "scientific_name": "Solanum lycopersicum",
        "family": "Họ Cà (Solanaceae)"
    },
    "Walnut": {
        "name_vi": "Óc chó",
        "common_name": "Cây óc chó",
        "scientific_name": "Juglans regia",
        "family": "Họ Óc chó (Juglandaceae)"
    },
    "Watermelon": {
        "name_vi": "Dưa hấu",
        "common_name": "Cây dưa hấu",
        "scientific_name": "Citrullus lanatus",
        "family": "Họ Bầu bí (Cucurbitaceae)"
    }
}

# 2. Diseases Localization (disease_vi.json)
DISEASES_VI = {
    # Common Patterns across crops
    "healthy": "Lá khỏe mạnh, không phát hiện dấu hiệu bệnh",
    "Healthy": "Lá khỏe mạnh, không phát hiện dấu hiệu bệnh",
    
    # Tomato
    "Bacterial_spot": "Bệnh đốm vi khuẩn",
    "Early_blight": "Bệnh cháy lá sớm (Đốm vòng)",
    "Late_blight": "Bệnh mốc sương (Đốm muộn)",
    "Leaf_Mold": "Bệnh mốc lá (Đốm nhung)",
    "Septoria_leaf_spot": "Bệnh đốm lá Septoria",
    "Spider_mites_Two_spotted_spider_mite": "Nhện đỏ hại lá (Nhện hai đốm)",
    "Spider_mites Two-spotted_spider_mite": "Nhện đỏ hại lá (Nhện hai đốm)",
    "Target_Spot": "Bệnh đốm mục tiêu (Đốm mắt cua)",
    "Tomato_YellowLeaf__Curl_Virus": "Bệnh xoăn vàng lá virus",
    "Tomato_Yellow_Leaf_Curl_Virus": "Bệnh xoăn vàng lá virus",
    "Tomato_mosaic_virus": "Bệnh khảm lá virus",
    "Fusarium_wilt": "Bệnh héo rũ Fusarium",
    "verticillium_wilt": "Bệnh héo rũ Verticillium",
    "leaf_miner": "Sâu vẽ bùa hại lá",

    # Potato
    "Potato___Early_blight": "Bệnh cháy lá sớm khoai tây",
    "Potato___Late_blight": "Bệnh mốc sương khoai tây",
    "Potato___healthy": "Lá khoai tây khỏe mạnh",

    # Pepper (Bell pepper)
    "Pepper,_bell___Bacterial_spot": "Bệnh đốm vi khuẩn trên ớt ngọt",
    "Pepper,_bell___healthy": "Lá ớt ngọt khỏe mạnh",

    # Corn / Maize
    "Common_rust": "Bệnh rỉ sắt ngô",
    "Common_rust_": "Bệnh rỉ sắt ngô",
    "Gray_leaf_spot": "Bệnh đốm xám lá ngô",
    "Cercospora_leaf_spot Gray_leaf_spot": "Bệnh đốm lá Cercospora / Đốm xám ngô",
    "Northern_leaf_blight": "Bệnh cháy lá lớn ngô (Đốm lá lớn)",
    "Northern_Leaf_Blight": "Bệnh cháy lá lớn ngô (Đốm lá lớn)",
    "Streak_virus": "Bệnh sọc lá ngô do virus",
    "Lethal_necrosis": "Bệnh hoại tử ngô nguy hiểm",
    "Smut": "Bệnh than đen ngô",

    # Rice
    "Bacterial_blight": "Bệnh bạc lá lúa (Cháy bìa lá vi khuẩn)",
    "Bacterial_leaf_streak": "Bệnh sọc trong vi khuẩn",
    "Blast": "Bệnh đạo ôn lá",
    "Brown_spot": "Bệnh đốm nâu hại lúa",
    "Sheath_blight": "Bệnh khô vằn",
    "Tungro": "Bệnh vàng lụi Tungro virus",
    "Leaf_scald": "Bệnh bỏng lá lúa",
    "Narrow_brown_leaf_spot": "Bệnh đốm nâu hẹp",

    # Apple
    "Apple_scab": "Bệnh vảy nến táo",
    "Black_rot": "Bệnh thối đen táo",
    "Cedar_apple_rust": "Bệnh rỉ sắt táo tuyết tùng",

    # Grape
    "Esca_(Black_Measles)": "Bệnh sởi đen (Esca) trên nho",
    "Leaf_blight_(Isariopsis_Leaf_Spot)": "Bệnh đốm mắt chim / Cháy lá nho",
    "Powdery_mildew": "Bệnh phấn trắng",
    "Downy_mildew": "Bệnh sương mai",
    "Anthracnose": "Bệnh thán thư",

    # Citrus / Orange
    "Haunglongbing_(Citrus_greening)": "Bệnh vàng lá gân xanh (Huanglongbing)",
    "Canker": "Bệnh loét cam quýt (Vi khuẩn)",
    "Black_spot": "Bệnh đốm đen cam quýt",

    # Coffee
    "Rust": "Bệnh rỉ sắt cà phê",
    "Leaf_miner": "Sâu vẽ bùa cà phê",
    "Red_spider_mite": "Nhện đỏ hại cà phê",
    "Cercospora_brown_eye_spot": "Bệnh đốm mắt cua (Cercospora)",

    # Strawberry
    "Leaf_scorch": "Bệnh cháy xém lá dâu tây",

    # Squash
    "Squash___Powdery_mildew": "Bệnh phấn trắng trên bí đỏ",

    # Generic
    "Mosaic_virus": "Bệnh virus khảm lá",
    "Nutrient_deficiency": "Triệu chứng thiếu hụt dinh dưỡng",
    "Blight": "Bệnh cháy lá",
}

# 3. Symptoms Localization (symptom_vi.json)
SYMPTOMS_VI = {
    "Bacterial_spot": {
        "summary": "Xuất hiện các đốm nhỏ 1-3mm, màu nâu sẫm hoặc đen, mép có quầng vàng nhạt úng nước.",
        "details": [
            "Đốm nhỏ hình tròn hoặc góc cạnh, phân bố rải rác trên bề mặt phiến lá.",
            "Trong điều kiện ẩm ướt, đốm có biểu hiện sũng nước, mặt dưới có thể hơi bóng.",
            "Các đốm liên kết lại làm lá cháy khô và rụng sớm từ tầng lá dưới lên."
        ]
    },
    "Early_blight": {
        "summary": "Vết bệnh đặc trưng bởi các vòng tròn đồng tâm hình đĩa bia, màu nâu đen, bắt đầu từ lá già.",
        "details": [
            "Vết đốm nâu đen có các vân tròn đồng tâm rõ rệt (dạng bia bắn target-spot).",
            "Mép vết bệnh có quầng vàng hẹp bao quanh, mô lá xung quanh dần chuyển vàng.",
            "Xuất hiện đầu tiên trên tầng lá sát mặt đất do bào tử nấm từ đất bắn lên."
        ]
    },
    "Late_blight": {
        "summary": "Vết thâm úng nước màu xanh xám loang nhanh, mặt dưới có lớp mốc trắng mỏng như sương.",
        "details": [
            "Vết bệnh ban đầu úng nước màu xanh tái, sau chuyển sang thâm nâu đen cháy xém.",
            "Lan nhanh khắp phiến lá trong điều kiện thời tiết lạnh ẩm hoặc sau đợt mưa kéo dài.",
            "Sáng sớm hoặc khi độ ẩm cao, quan sát thấy lớp tơ nấm trắng mỏng ở viền vết bệnh mặt dưới lá."
        ]
    },
    "Powdery_mildew": {
        "summary": "Bề mặt lá phủ lớp phấn trắng xám như rắc bột mì, làm lá khô cong queo.",
        "details": [
            "Lớp phấn trắng xuất hiện ở mặt trên lá, lan nhanh tạo thành mảng lớn.",
            "Lá bị nhiễm mất khả năng quang hợp, chuyển sang vàng nâu, giòn và rụng sớm.",
            "Thường phát triển mạnh khi trời hanh khô xen kẽ sương mù ban đêm."
        ]
    },
    "Downy_mildew": {
        "summary": "Mặt trên lá xuất hiện các vệt vàng góc cạnh giới hạn bởi gân lá, mặt dưới có lớp mốc tím xám.",
        "details": [
            "Vệt vàng hình đa giác bị chặn bởi các gân phụ của lá.",
            "Mặt dưới phiến lá mọc lớp mốc mịn màu tím nhạt hoặc xám tro khi trời ẩm.",
            "Lá chuyển nâu khô giòn từ giữa phiến lá lan ra mép."
        ]
    },
    "Healthy": {
        "summary": "Phiến lá xanh đều, mặt phẳng mịn, không có vết đốm hay biến dạng.",
        "details": [
            "Màu sắc diệp lục tươi tốt, đồng nhất trên toàn bộ phiến lá.",
            "Gân lá và mép lá phát triển bình thường, không có dấu vết chích hút hay nấm bệnh."
        ]
    },
    "Default": {
        "summary": "Có dấu hiệu tổn thương hoặc đổi màu bất thường trên phiến lá cây trồng.",
        "details": [
            "Xuất hiện đốm đổi màu hoặc tổn thương mô tế bào diệp lục trên mặt lá.",
            "Cần theo dõi sự lây lan sang các lá lân cận."
        ]
    }
}

# 4. Recommendations Localization (recommendation_vi.json)
RECOMMENDATIONS_VI = {
    "Bacterial_spot": {
        "action": "Cách ly tàn dư, tránh tưới phun mưa trên tán lá, ưu tiên chế phẩm sinh học hoặc gốc đồng.",
        "steps": [
            "Tưới nước trực tiếp vào gốc vào buổi sáng, tuyệt đối không tưới phun mưa làm ướt tán lá vào chiều tối.",
            "Tỉa bỏ các lá bị đốm nặng và gom vào túi nilon đem tiêu hủy xa vườn, khử trùng kéo cắt.",
            "Khi bệnh chớm xuất hiện, sử dụng chế phẩm vi sinh đối kháng Bacillus subtilis hoặc dung dịch gốc đồng (Copper hydroxide) theo nồng độ hướng dẫn."
        ],
        "caution": "Hạn chế lạm dụng kháng sinh nông nghiệp để phòng ngừa vi khuẩn kháng thuốc."
    },
    "Early_blight": {
        "action": "Tỉa lá già sát gốc, phủ bạt giữ ẩm ngăn bào tử từ đất, bón cân đối dinh dưỡng.",
        "steps": [
            "Vệ sinh sạch cỏ dại, tỉa bỏ tầng lá chân sát mặt đất để gốc cây luôn thông thoáng và khô ráo.",
            "Phủ rơm rạ sạch hoặc màng phủ nông nghiệp quanh gốc để ngăn giọt mưa bắn đất mang mầm bệnh lên lá dưới.",
            "Bón phân cân đối N-P-K, tăng cường Kali và Canxi-Bo để làm dày vách tế bào lá, giảm bón thừa đạm."
        ],
        "caution": "Luân canh cây trồng khác họ ít nhất 2 năm để làm đứt chu kỳ sống của nấm Alternaria trong đất."
    },
    "Late_blight": {
        "action": "Ngừng tưới nước ngay lập tức, cách ly khẩn cấp ổ bệnh, xử lý bằng hoạt chất chuyên biệt.",
        "steps": [
            "Ngừng mọi hình thức tưới nước trên tán lá; kiểm tra độ thoát nước của luống trong mùa mưa lạnh.",
            "Cắt bỏ và tiêu hủy toàn bộ các lá và quả bị thâm úng, không ủ làm phân hữu cơ.",
            "Khi thời tiết lạnh ẩm kéo dài, phun phòng ngừa bằng các hoạt chất đặc trị mốc sương như Metalaxyl, Cymoxanil hoặc Dimethomorph theo đúng khuyến cáo BVTV."
        ],
        "caution": "Bệnh mốc sương lây lan cực nhanh theo gió và nước, cần can thiệp xử lý ngay trong 24-48 giờ đầu."
    },
    "Powdery_mildew": {
        "action": "Tạo độ thông thoáng cho giàn/tán, phun phòng chế phẩm sinh học hoặc lưu huỳnh dạng bột/nước.",
        "steps": [
            "Tỉa bớt cành nhánh rậm rạp để ánh nắng chiếu sâu vào trong tán cây.",
            "Sử dụng dầu khoáng nông nghiệp hoặc chế phẩm nấm đối kháng Trichoderma phun đều 2 mặt lá.",
            "Có thể sử dụng các chế phẩm chứa hoạt chất Azoxystrobin hoặc gốc lưu huỳnh hữu cơ khi bệnh bùng phát."
        ],
        "caution": "Tránh phun lưu huỳnh khi nhiệt độ ngoài trời vượt quá 32°C để tránh gây cháy lá non."
    },
    "Downy_mildew": {
        "action": "Giảm độ ẩm vườn, nhổ bỏ cây bệnh nặng, phun phòng bằng gốc đồng hoặc hoạt chất diệt noãn nấm.",
        "steps": [
            "Giảm mật độ trồng, làm giàn vững chắc và dọn sạch lá khô tàn dư dưới gốc.",
            "Tưới tiêu hợp lý, tránh để nước tù đọng qua đêm trong rãnh luống.",
            "Phun luân phiên Mancozeb, Fosetyl-aluminium hoặc Metalaxyl khi quan sát thấy vết vàng góc cạnh đầu tiên."
        ],
        "caution": "Nấm sương mai dễ kháng thuốc, bắt buộc phải luân phiên các nhóm hoạt chất có cơ chế tác động khác nhau."
    },
    "Healthy": {
        "action": "Duy trì chế độ chăm sóc hiện tại, bổ sung dinh dưỡng hữu cơ và nấm đối kháng định kỳ.",
        "steps": [
            "Tiếp tục tưới nước hợp lý theo nhu cầu độ ẩm của từng giai đoạn sinh trưởng.",
            "Bổ sung phân hữu cơ hoai mục ủ Trichoderma vào gốc để tăng sức đề kháng tự nhiên cho bộ rễ.",
            "Kiểm tra bẫy dính vàng định kỳ để giám sát côn trùng truyền virus (bọ trĩ, rầy mềm, bọ phấn trắng)."
        ],
        "caution": "Không cần sử dụng thuốc BVTV hóa học khi lá cây đang ở trạng thái khỏe mạnh."
    },
    "Default": {
        "action": "Theo dõi sát diễn biến vết bệnh, giữ vườn thông thoáng và tham khảo ý kiến cán bộ khuyến nông.",
        "steps": [
            "Chụp thêm ảnh theo dõi sau 2-3 ngày để đánh giá tốc độ lan rộng của đốm tổn thương.",
            "Tạm thời ngưng bón phân đạm lá, tăng cường phân bón hữu cơ và vi lượng cân đối.",
            "Trao đổi trực tiếp với cán bộ nông nghiệp địa phương nếu xuất hiện lây lan trên diện rộng."
        ],
        "caution": "Không tự ý phối trộn nhiều loại thuốc BVTV khi chưa xác định chính xác tác nhân gây hại."
    }
}

# Write files
with open(LOC_DIR / "crop_vi.json", "w", encoding="utf-8") as f:
    json.dump(CROPS_VI, f, indent=2, ensure_ascii=False)

with open(LOC_DIR / "disease_vi.json", "w", encoding="utf-8") as f:
    json.dump(DISEASES_VI, f, indent=2, ensure_ascii=False)

with open(LOC_DIR / "symptom_vi.json", "w", encoding="utf-8") as f:
    json.dump(SYMPTOMS_VI, f, indent=2, ensure_ascii=False)

with open(LOC_DIR / "recommendation_vi.json", "w", encoding="utf-8") as f:
    json.dump(RECOMMENDATIONS_VI, f, indent=2, ensure_ascii=False)

print(f"Created 4 centralized Vietnamese localization files in {LOC_DIR}:")
print(f"  - crop_vi.json ({len(CROPS_VI)} crops)")
print(f"  - disease_vi.json ({len(DISEASES_VI)} diseases)")
print(f"  - symptom_vi.json ({len(SYMPTOMS_VI)} symptom profiles)")
print(f"  - recommendation_vi.json ({len(RECOMMENDATIONS_VI)} recommendation protocols)")
