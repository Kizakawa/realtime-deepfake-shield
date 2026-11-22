# Hồ Sơ Rà Soát Pháp Lý (Luật 91/2025/QH15), Đạo Đức & Chính Sách Google Play — Phase 0

Tài liệu này là **bảng kiểm chuẩn bị làm việc với luật sư, hội đồng đạo đức nghiên cứu và đội ngũ phát hành Google Play** trong **Phase 0 (Tuần 1–2)** theo yêu cầu của [SYSTEM_ARCHITECTURE.md](../architecture/SYSTEM_ARCHITECTURE.md) v2.0 và [THREAT_MODEL.md](../architecture/THREAT_MODEL.md).

> **Tuyên bố miễn trừ:** Tài liệu này mang tính chuẩn bị kỹ thuật — **không thay thế ý kiến tư vấn pháp lý chính thức của luật sư hành nghề tại Việt Nam**.

---

## 1. Rà soát Tuân thủ Luật Bảo vệ Dữ liệu Cá nhân số 91/2025/QH15 (Hiệu lực 01/01/2026)

### 1.1. Bối cảnh Pháp lý Cốt lõi
* **Luật số 91/2025/QH15** phân loại **dữ liệu sinh trắc học (giọng nói, khuôn mặt)** là **Dữ liệu cá nhân nhạy cảm**.
* Xử lý dữ liệu nhạy cảm yêu cầu **sự đồng ý rõ ràng, tự nguyện, có thông báo mục đích** của chủ thể dữ liệu và áp dụng biện pháp bảo vệ kỹ thuật nghiêm ngặt.

### 1.2. Danh sách Câu hỏi Cần Luật sư Thẩm định Trước Phase 1
1. **Chủ thể dữ liệu bên thứ ba (Người gọi đến):** Khi người cao tuổi cài app bảo vệ và chấp thuận điều khoản, người gọi ở đầu dây bên kia (kể cả người gọi bình thường không phải kẻ lừa đảo) *không trực tiếp ký đồng ý*. Việc xử lý **hoàn toàn cục bộ trong RAM trên thiết bị cá nhân của người nhận cuộc gọi, không ghi đĩa, không truyền ra ngoài, không trích xuất định danh sinh trắc học (chỉ tính điểm bất thường kỹ thuật rồi hủy ngay)** có thuộc phạm vi miễn trừ xử lý phục vụ mục đích cá nhân/gia đình hay cần thông báo cảnh báo cho đầu dây bên kia?
2. **Dữ liệu tin nhắn qua `NotificationListenerService`:** Văn bản tin nhắn xem trước trên máy người cao tuổi có chứa thông tin cá nhân của người gửi; việc phân loại hoàn toàn cục bộ (`PhoBERT-v2` on-device) và **không gửi nội dung tin nhắn sang máy Người giám hộ** (chỉ gửi mã loại cảnh báo như `CHAT_URGENT_TRANSFER_PATTERN`) có đáp ứng nguyên tắc giảm thiểu dữ liệu (*data minimization*)?
3. **Hồ sơ Đánh giá Tác động Xử lý Dữ liệu Cá nhân (DPIA):** Khi mở rộng thành sản phẩm thương mại hoặc thí điểm cộng đồng, dự án cần lập hồ sơ đánh giá tác động và chỉ định bộ phận/nhân sự bảo vệ dữ liệu cá nhân theo quy định nào của nghị định hướng dẫn Luật 91/2025/QH15?
4. **Ranh giới giữa Phòng thí nghiệm và Thương mại:** Ở chế độ nghiên cứu (thu 20–30 mẫu qua Zalo thật và thử nghiệm đóng vai), mẫu văn bản chấp thuận (*Informed Consent Form*) cần quy định thời hạn xóa dữ liệu sinh trắc học tối đa là bao nhiêu ngày?

### 1.3. Ràng buộc Kỹ thuật Bắt buộc đã khóa trong Kiến trúc v2
* **Cấm tuyệt đối** truyền raw audio hoặc raw video của người gọi lên cloud ở bản phát hành thực tế.
* `0 bytes` ghi âm/video thô lưu vào bộ nhớ trong (`Internal/External Storage`).
* Mặc định `transcript_included = false` trong mọi gói tin SOS gửi cho Người giám hộ.

---

## 2. Đạo đức Nghiên cứu & Phòng ngừa Lạm dụng Người Cao Tuổi (IRB / Ethics)

Trước khi thực hiện thử nghiệm thực địa với tình nguyện viên người cao tuổi (`>= 60 tuổi`) ở Phase 3, dự án phải hoàn thành các hạng mục sau:
1. **Phê duyệt Hội đồng Đạo đức Nghiên cứu (IRB / Hội đồng Khoa học):** Nộp đề cương thử nghiệm đóng vai (*Role-play Simulation*), tuyệt đối **không** tạo tình huống hù dọa thật (không giả mạo công an thật gây sốc tâm lý/tăng huyết áp cho người cao tuổi tham gia thử nghiệm).
2. **Chống Lạm dụng Quyền Giám hộ (*Elder Financial Abuse*):**
   * Người cao tuổi phải được giải thích rõ ràng bằng chữ cỡ lớn và giọng nói trước khi ghép đôi với Người giám hộ.
   * Cung cấp màn hình **Nhật ký Minh bạch (*Transparency Log*)** liệt kê mọi thông báo từng gửi cho con cái.
   * Khuyến nghị thiết lập **tối thiểu 2 Người giám hộ** (ví dụ 2 người con) để tránh độc quyền kiểm soát.
3. **An toàn Sinh mạng:** Danh sách trắng cứng cho các số khẩn cấp **`113`, `114`, `115`** — mọi lớp chặn/overlay đều tự động vô hiệu hóa ngay lập tức khi liên quan đến các đầu số này.

---

## 3. Ma trận Quyền Android & Chiến lược Duyệt Google Play

| Quyền Android | Trạng thái trong Kiến trúc v2 | Chính sách Google Play & Rủi ro | Biện pháp Tuân thủ & Phương án Thay thế |
| :--- | :--- | :--- | :--- |
| `SEND_SMS` | **ĐÃ LOẠI BỎ** | Bị cấm trừ *Default SMS Handler*; Android 15+ khóa cứng với app sideload | Thay bằng **FCM High-Priority + Server SMS Gateway Fallback + `ACTION_SENDTO` (`smsto:`)** mở sẵn tin nhắn cho người dùng bấm gửi |
| `BIND_NOTIFICATION_LISTENER_SERVICE` | **Sử dụng (Layer 0)** | Yêu cầu giải trình rõ mục đích cốt lõi (Core Functionality) và Chính sách quyền riêng tư | Chỉ lọc đúng package OTT/SMS liên quan; xử lý 100% cục bộ trong RAM; không gửi nội dung thông báo lên server |
| `PACKAGE_USAGE_STATS` | **Sử dụng (Point-of-Loss Guard)** | Quyền nhạy cảm, yêu cầu người dùng tự bật trong Settings & giải trình tính năng bảo vệ tài chính | Chỉ kích hoạt đọc foreground app khi đang có `SUSPICION_SESSION` hoạt động; không lưu lịch sử sử dụng ứng dụng |
| `SYSTEM_ALERT_WINDOW` | **Sử dụng (Cooling-Off / Verify UI)** | Được phép nhưng phải minh bạch, không chặn cứng nút điều hướng hệ thống vĩnh viễn | Hiển thị rõ mục đích cảnh báo lừa đảo; luôn có đường thoát an toàn (nhấn giữ 3s bỏ qua) và miễn trừ `113/114/115` |
| `FOREGROUND_SERVICE_MEDIA_PROJECTION` | **Có điều kiện (Tier 2–3)** | Từ Android 14+ bắt buộc khai báo loại dịch vụ nền rõ ràng và xin consent mỗi phiên | Chỉ bật khi người dùng chọn bảo vệ Video Call; kiểm tra rủi ro từ chối Play trong giai đoạn Internal Testing |
| `AccessibilityService` | **KHÔNG DÙNG ở MVP** | Rủi ro bị Google Play từ chối cực cao nếu không phải công cụ hỗ trợ khuyết tật | Tránh hoàn toàn bằng cách dùng `NotificationListenerService` + `UsageStatsManager` + `CallScreeningService` |
| `RECORD_AUDIO` | **Chỉ dùng ở Phase 0 Spike / Built-in WebRTC** | Android 10+ ép câm khi VoIP chạy (`isClientSilenced`); yêu cầu `FOREGROUND_SERVICE_MICROPHONE` | Nếu Phase 0 Spike xác nhận bị câm trên đa số máy → **gỡ bỏ hoàn toàn `RECORD_AUDIO`** khỏi Android MVP để tối giản quyền và tăng tỷ lệ duyệt Play |
