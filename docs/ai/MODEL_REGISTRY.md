# GARI 3.0 — AI MODEL REGISTRY & MANIFEST

## 1. TỔNG QUAN TẬP MODEL HIỆN HỮU

Thư mục `D:\leaf-diseases-detector-main\models` hiện lưu trữ **51 checkpoints mô hình AI thực tế** phục vụ phân tích thị giác máy tính trong nông nghiệp:

### A. Phân loại Mô hình
1. **Model Kiểm định Đầu vào (`is_leaf` gate):**
   - Nhiệm vụ: Xác định ảnh tải lên có phải lá cây thật hay là ảnh ngoại lai (con người, xe cộ, đồ vật...).
   - Checkpoint: `models/gate/is_leaf_classifier.pth`
2. **Model Đa Cây trồng Tổng hợp (Multi-Crop Universal Classifiers):**
   - Kiến trúc: ConvNeXt Small / Base, MobileNetV4 Large.
   - Nhiệm vụ: Tự động nhận diện loài cây và phân loại bệnh khi người dùng không chọn trước cây trồng.
3. **Model Chuyên biệt theo Cây trồng (Crop-Specific Specialized Models):**
   - **Cà phê (Coffee):** Phát hiện Bệnh Gỉ sắt (*Hemileia vastatrix*), Thán thư lá, Nấm hồng, Đốm mắt cua.
   - **Hồ tiêu (Pepper):** Phát hiện Bệnh Chết nhanh (*Phytophthora capsici*), Chết chậm, Thán thư gié.
   - **Sầu riêng (Durian):** Phát hiện Xì mủ nứt thân (*Phytophthora palmivora*), Cháy lá chết ngọn (*Rhizoctonia solani*), Thán thư lá.
   - **Lúa nước (Rice):** Phát hiện Đạo ôn lá, Khô vằn, Vàng lùn xoắn lá, Bạc lá vi khuẩn.
   - **Cà chua (Tomato):** Phát hiện Mốc sương (*Phytophthora infestans*), Đốm lá vi khuẩn, Đốm mắt cua, Xoăn lá vàng virus.
   - **Ớt cay (Chili):** Phát hiện Thán thư quả/lá, Héo xanh vi khuẩn, Bọ trĩ đọt non.
   - **Ngô/Bắp (Corn):** Phát hiện Đốm lá lớn, Khô vằn, Rỉ sắt ngô, Sâu keo mùa thu.

---

## 2. QUẢN LÝ VÒNG ĐỜI MÔ HÌNH (MODEL LIFECYCLE MANAGEMENT)

- **Cơ chế nạp trước (Preloading):** Các mô hình hay dùng (Combined ConvNeXt + Crop phổ biến) được nạp sẵn vào RAM khi worker khởi động để loại bỏ Cold Start.
- **Giải phóng bộ nhớ (Auto Unload):** Các mô hình chuyên biệt ít gọi được nạp theo cơ chế On-Demand và tự động giải phóng sau thời gian nhàn rỗi (idle timeout) để tối ưu RAM cho máy trạm.
- **Độ tin cậy & Hiệu chuẩn (Confidence Calibration):** Ngưỡng tin cậy được thiết lập nghiêm ngặt: kết quả dưới 65% tự động cảnh báo người dùng chụp lại cận cảnh hoặc gửi vào quy trình thẩm định chuyên gia.
