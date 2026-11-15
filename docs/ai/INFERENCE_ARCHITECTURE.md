# GARI 3.0 — AI INFERENCE ARCHITECTURE & ROUTING

## 1. MÔ HÌNH SUY LUẬN LAI (HYBRID INFERENCE PIPELINE)

```
[Client Upload Ảnh Lá Cây]
            │
            ▼ (POST /api/predict)
[Vercel Serverless Gateway: api/[...path].js]
            │
            ├─ Kiểm tra Hạn mức (Quota Check: Tối đa 5 lượt/ngày đối với Free/Trial)
            │
            ▼ (Proxy Request qua Cloudflare Tunnel)
[Primary: Windows Local AI Worker (api_server.py)]
            │
            ├─ 1. Tiền xử lý ảnh (Resize 224x224, Normalize ImageNet)
            ├─ 2. Gatekeeper: Kiểm tra is_leaf (Loại bỏ ảnh không phải lá)
            ├─ 3. Chạy Inference Model PyTorch / ONNX
            ├─ 4. Tạo bản đồ nhiệt trực quan hóa Grad-CAM (Target layer visualization)
            └─ 5. Chuẩn hóa kết quả JSON (Bệnh, Tên khoa học, Độ tin cậy, Phác đồ xử lý IPM)
```

---

## 2. QUY TẮC DỰ PHÒNG THẤT BẠI (FAILOVER & CIRCUIT BREAKER)

1. **Ưu tiên Hàng đầu (Primary Inference):** Mọi request mặc định chuyển đến máy chủ Windows AI Worker cục bộ với sức mạnh phần cứng đầy đủ và thời gian xử lý nhanh.
2. **Tiêu chí Kích hoạt Fallback:** Chỉ khi kết nối đến Primary Worker gặp lỗi mạng hệ thống (Network Connection Refused, 502, Gateway Timeout > 25 giây) thì Inference Router mới chuyển hướng sang Cloud Worker.
3. **Không Fallback khi Lỗi Dữ liệu:** Các lỗi xuất phát từ phía người dùng (ảnh hỏng, định dạng không hỗ trợ, ảnh không phải lá cây) bị từ chối ngay lập tức tại tầng kiểm định, không kích hoạt fallback để tránh lãng phí tài nguyên.
