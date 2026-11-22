# Kho Tài Liệu Nghiên Cứu & Tham Chiếu Công Nghệ

Thư mục này lưu trữ toàn bộ bài báo khoa học, chuẩn đánh giá (benchmarks), tập dữ liệu (datasets) và kho mã nguồn mở GitHub phục vụ trực tiếp cho dự án **"Lá chắn Chống Lừa đảo Deepfake & Giọng nói AI Thời gian thực cho Người cao tuổi"** (*Realtime Deepfake Shield*).

---

## 1. Bối cảnh & Khoảng trống Nghiên cứu (Research Gap)

Hiện nay trên thị trường đã có một số giải pháp chống lừa đảo và nhận diện deepfake của các tập đoàn lớn, tuy nhiên đều tồn tại giới hạn khiến chúng **chưa giải quyết được bài toán thực tế của người cao tuổi Việt Nam** khi bị tấn công qua Zalo, Messenger, Viber hoặc cuộc gọi VoIP/di động giả danh:

| Giải pháp thương mại | Cơ chế cốt lõi | Điểm mạnh | Hạn chế / Khoảng trống |
| :--- | :--- | :--- | :--- |
| **Google Android** *(Scam Detection & Fake Call Detection)* | On-device **Gemini Nano** phân tích nội dung cuộc gọi + bắt tay số qua **RCS** (*digital handshake*) | Chạy trực tiếp trên thiết bị, bảo vệ quyền riêng tư, cảnh báo âm thanh/rung tức thì | Đóng mã nguồn, khóa chặt trong ứng dụng *Phone by Google*; không bảo vệ cuộc gọi OTT (Zalo, Messenger); chưa tối ưu cho tiếng Việt & kịch bản lừa đảo đặc thù tại Việt Nam |
| **Honor AI** *(Deepfake & Voice Cloning Detection)* | Phân tích biểu cảm, ánh sáng, kết cấu khuôn mặt và phổ giọng nói trong ~3 giây | Độ trễ thấp, tích hợp sâu ở tầng hệ điều hành cho cả video & audio call | Độc quyền trên thiết bị phần cứng Honor (MagicOS); không thể cài đặt lên điện thoại phổ thông của đa số người lớn tuổi |
| **Intel FakeCatcher & McAfee Deepfake Detector** | Intel FakeCatcher dùng **rPPG** (nhịp mạch dưới da) trên OpenVINO/Xeon; McAfee chạy trên NPU của Intel AI PC | Độ chính xác cao trên phần cứng Intel chuyên dụng | Hướng tới máy tính PC/trình duyệt, chưa phải giải pháp bảo vệ cuộc gọi di động cho người cao tuổi |

**Khoảng trống dự án hướng tới lấp đầy (Cập nhật v2):**
1. **Bảo vệ xuyên kênh khớp kịch bản Việt Nam:** Liên kết chuỗi tấn công thực tế (*cuộc gọi video deepfake 3–5 giây mờ/giật → tin nhắn vay tiền → mở app ngân hàng / cài AnyDesk hoặc APK dịch vụ công giả*) kết hợp **Xác minh Ngoài kênh** và **Chặn tại Điểm mất tiền**.
2. **Bảo vệ liên thế hệ theo quyền tối thiểu (*Least-Privilege Intergenerational Support*):** Gửi cảnh báo SOS hợp chuẩn Google Play cho người thân nhưng mặc định không chia sẻ nội dung hội thoại riêng tư, chống lạm dụng quyền giám hộ và chống bị kẻ gian dụ tắt app.
3. **Thích ứng thực địa & Tuân thủ Pháp lý:** Giải quyết rào cản *Concurrent Audio Capture* trên Android 10+, nén VoIP Zalo/Messenger và tuân thủ **Luật Bảo vệ dữ liệu cá nhân số 91/2025/QH15** (hiệu lực 01/01/2026).

---

## 2. Mục lục Tài liệu Nghiên cứu Chi tiết

1. **[01_audio_deepfake_detection.md](./01_audio_deepfake_detection.md)** — Phát hiện giọng nói tổng hợp (TTS), nhân bản giọng nói (Voice Clone), Neural Audio Codec (`CodecFake`, `ASVspoof 5`, `VoiceWukong`), dữ liệu tiếng Việt (`VSASV`, `VietPrism`) và các mô hình `AASIST`, `RawNet2`, `XLSR/Wav2Vec 2.0`.
2. **[02_video_faceswap_detection.md](./02_video_faceswap_detection.md)** — Phân tích hạn chế của đo chớp mắt (`Blink/EAR`), suy hao nén của `MobileNetV2 + SRM`, phạm vi áp dụng đúng của `Lip-Sync` (clip dựng sẵn vài giây), `rPPG` và giới hạn của `Active Probing / GOTCHA` trước mặt nạ che khuất của Deep-Live-Cam/FaceFusion.
3. **[03_vishing_stt_llm_context.md](./03_vishing_stt_llm_context.md)** — Kiến trúc phân tích hội thoại & tin nhắn lừa đảo thời gian thực (`ChunkFormer`, `PhoWhisper`, `PhoBERT-v2` / SLM QLoRA 4-bit, trạng thái `UNCERTAIN`) và bộ dữ liệu kịch bản lừa đảo tiếng Việt.
4. **[04_elderly_hci_and_os_constraints.md](./04_elderly_hci_and_os_constraints.md)** — Nghiên cứu HCI bảo vệ liên thế hệ, kịch bản lừa đảo thực tế theo cảnh báo Bộ Công an, rào cản Android 10+ *Concurrent Audio Capture* (`isClientSilenced`), chính sách `SEND_SMS` Google Play và **Luật Bảo vệ dữ liệu cá nhân 91/2025/QH15**.

→ Bộ tài liệu kiến trúc & an ninh hoàn chỉnh được trình bày tại:
* **[SYSTEM_ARCHITECTURE.md](../architecture/SYSTEM_ARCHITECTURE.md)** (v2.0)
* **[DESIGN_REVIEW_v1.md](../architecture/DESIGN_REVIEW_v1.md)** (Nhật ký rà soát 14 lỗ hổng v1 → v2)
* **[THREAT_MODEL.md](../architecture/THREAT_MODEL.md)** (Mô hình mối đe dọa & 8 kịch bản tấn công trọng yếu)

---

## 3. Quy ước & Mẫu Ghi chú Bài báo Mới (Paper Note Template)

Khi bổ sung bài báo hoặc kho mã nguồn mới vào các tệp `01_`–`04_`, sử dụng cấu trúc thống nhất dưới đây để dễ tra cứu và đối chiếu vào kiến trúc:

```markdown
### [Tên Bài báo / Dự án]
* **Nguồn / Năm / Mã định danh:** (Ví dụ: arXiv:XXXX.XXXXX, IEEE/ACM/USENIX, GitHub)
* **Liên kết:** [URL gốc]
* **Bài toán & Đóng góp cốt lõi:** Tóm tắt vấn đề giải quyết và phương pháp kỹ thuật chính.
* **Hạn chế / Lưu ý thực nghiệm:** Các điều kiện làm giảm hiệu năng (nén VoIP, độ trễ, phần cứng, ngôn ngữ...).
* **Ứng dụng vào Realtime Deepfake Shield:** Thành phần nào trong hệ thống sẽ kế thừa trực tiếp kỹ thuật/mã nguồn này.
```
