# 04. Nghiên cứu HCI cho Người Cao Tuổi, Ràng buộc Hệ Điều Hành & Hành lang Pháp lý

Tài liệu này tổng hợp các nghiên cứu tương tác người–máy (HCI), kịch bản lừa đảo thực tế tại Việt Nam, các giới hạn kỹ thuật của Android/iOS, chính sách Google Play và hành lang pháp lý về dữ liệu cá nhân tại Việt Nam nhằm đảm bảo hệ thống **chạy được trong thực tế**, **an toàn đạo đức** và **tuân thủ pháp luật**.

---

## 1. Nghiên cứu HCI, Thủ đoạn Thực tế tại Việt Nam & Bảo vệ Liên thế hệ

### Intergenerational Support for Deepfake Scams Targeting Older Adults
* **Nguồn / Năm:** arXiv:2508.11579 (2025)
* **Liên kết:** [https://arxiv.org/abs/2508.11579](https://arxiv.org/abs/2508.11579)
* **Bài toán & Đóng góp cốt lõi:** Khảo sát sâu các kịch bản lừa đảo mạo danh người thân bằng audio/video deepfake (*"grandparent scams"*) nhắm vào người lớn tuổi. Nghiên cứu khẳng định các mẹo nhận biết thủ công thất bại khi nạn nhân rơi vào hoảng loạn; **hỗ trợ liên thế hệ (Intergenerational Support)** — đưa con cái/người thân vào vòng phản hồi xác minh — là lá chắn hệ thống hiệu quả nhất.
* **Lưu ý Đạo đức (*Guardian Abuse / Elder Financial Exploitation*):** Nghiên cứu thực tế chỉ ra lạm dụng tài chính người cao tuổi không ít lần đến từ chính người thân trong gia đình. Do đó vai trò Người giám hộ bắt buộc phải theo nguyên tắc **Quyền tối thiểu (*Least-Privilege*)** — mặc định không gửi nội dung hội thoại, hỗ trợ đa người giám hộ và có *Transparency Log* để người cao tuổi tự kiểm soát.

### Thủ đoạn Lừa đảo Deepfake Thực tế tại Việt Nam (Cảnh báo Bộ Công an)
Theo cảnh báo liên tục của Bộ Công an và Cục An ninh mạng và phòng, chống tội phạm sử dụng công nghệ cao:
1. Kẻ gian chiếm đoạt tài khoản mạng xã hội hoặc thu thập video/ảnh công khai của người thân.
2. Thực hiện **cuộc gọi video deepfake cực ngắn (chỉ vài giây)** với **chất lượng mờ, nhòe, giật**, sau đó chủ động cúp máy lấy lý do *"sóng yếu, không nghe rõ"* để che lỗi giả mạo.
3. Ngay sau khi tạo được niềm tin giả ("vừa nhìn thấy mặt rồi"), kẻ gian **chuyển sang nhắn tin** viện cớ cấp cứu/gấp gáp để yêu cầu chuyển khoản vào tài khoản ngân hàng mang tên người lạ.
4. Với kịch bản giả danh công an/viện kiểm sát (thường không cần deepfake), kẻ gian dụ nạn nhân cài **file `.apk` dịch vụ công giả** hoặc phần mềm điều khiển từ xa (**AnyDesk, TeamViewer**).

→ **Hệ quả thiết kế:** Hệ thống không thể chỉ theo dõi trong một cuộc gọi dài mà bắt buộc phải có **Phiên nghi vấn xuyên kênh (cuộc gọi ngắn → tin nhắn → mở app ngân hàng / cài APK)** và đặt **Xác minh Ngoài kênh** (*Mật khẩu gia đình + Gọi lại số đã lưu*) lên hàng đầu.

### Tổng quan Nghiên cứu HCI / CHI / CSCW / SOUPS (2024–2026)
1. **Can thiệp đúng điểm mất tiền:** Ngoài cảnh báo trong lúc gọi/chat, cần tạo điểm dừng làm nguội (*Cooling-Off*) ngay trước thời điểm chuyển khoản.
2. **Đo báo động giả theo người dùng/tháng:** Vì lừa đảo có tần suất rất thấp (*low base rate*), mục tiêu phải đo theo **số lần báo Đỏ nhầm / người dùng / tháng** (`<= 0.5`), đi kèm *Family Trusted Allowlist* để tránh *Alarm Fatigue*.
3. **An toàn khi cảnh báo:** Không dùng nút `"TẮT MÁY NGAY"` (tránh làm lỡ cấp cứu thật; tuyệt đối không chặn `113/115/114`). Không phát giọng đọc TTS cảnh báo qua loa ngoài khi micro cuộc gọi đang mở (tránh kẻ gian nghe thấy để trấn an tiếp và tránh tự kích hoạt ASR).
4. **Phê duyệt Đạo đức & Giọng người cao tuổi:** Thử nghiệm thực địa với người cao tuổi cần hội đồng đạo đức phê duyệt; đồng thời bộ phát hiện audio có độ lệch sai số cao trên giọng người già (`arXiv:2606.04414`).

---

## 2. Phân tích Ràng buộc Hệ Điều Hành (Android & iOS) & Chính sách Google Play

### 2.1. Thực trạng Thu nhận Âm thanh & Hình ảnh trên Android 10+ (Không Root)
1. **Khóa `AudioPlaybackCapture` với cuộc gọi OTT:** Android 10 (API 29) chỉ cho phép `AudioPlaybackCapture` thu luồng `USAGE_MEDIA`, `USAGE_GAME`, `USAGE_UNKNOWN`. Zalo, Messenger, WhatsApp sử dụng **`USAGE_VOICE_COMMUNICATION`** và đặt chính sách chặn thu (`ALLOW_CAPTURE_BY_NONE`) → không thể đọc gói âm thanh nội bộ cuộc gọi OTT.
2. **Chính sách Thu âm Đồng thời (*Concurrent Audio Capture Policy* — Rào cản sống còn với Micro):**
   * Từ Android 10, `AudioSource.VOICE_COMMUNICATION` được đánh dấu là nguồn **nhạy cảm về quyền riêng tư (*privacy-sensitive*)** có độ ưu tiên cao nhất.
   * Khi Zalo, Messenger hoặc cuộc gọi di động đang giữ micro, ứng dụng thứ hai gọi `AudioRecord.startRecording()` (dù dùng `AudioSource.MIC` hay `DEFAULT`) sẽ **không văng lỗi, nhưng bị hệ điều hành đẩy về hoàn toàn buffer âm thanh câm (toàn số 0)**.
   * Ứng dụng bắt buộc phải đăng ký `AudioManager.AudioRecordingCallback` và kiểm tra **`AudioRecordingConfiguration.isClientSilenced()`** để biết luồng thu có bị câm hay không.
   * *Lưu ý thêm:* Không bao giờ đặt bộ khử tiếng vang (AEC) trước Engine phát hiện giọng giả, vì AEC sẽ xóa chính âm thanh phát ra từ loa ngoài (giọng của kẻ gian).
3. **Khóa `VOICE_CALL` cuộc gọi PSTN:** Bị khóa trên Android 9+ ở hầu hết máy chưa root.
4. **Bắt hình ảnh (`MediaProjection`):** Khả thi nhưng bắt buộc hộp thoại xin quyền từng phiên, khai báo `foregroundServiceType="mediaProjection"` (bắt buộc từ Android 14+) và hiện biểu tượng ghi màn hình.
5. **Tín hiệu Khả thi 100% trên Android không root:** `NotificationListenerService` (đọc tên người gọi & tin nhắn Zalo/Messenger), `CallScreeningService` (số lạ/quốc tế), `UsageStatsManager` (phát hiện mở app ngân hàng/ví điện tử/AnyDesk) và giám sát cài đặt gói (`ACTION_PACKAGE_ADDED`).

### 2.2. Ràng buộc Chính sách Google Play
* **`SEND_SMS`:** Bị Google Play cấm hoàn toàn trừ khi ứng dụng được đặt làm **Default SMS Handler**. Với app cài ngoài (sideload), Android 15+ khóa cứng dưới dạng *hard-restricted permission*. → Không dùng `SmsManager` gửi SMS ngầm; thay bằng **FCM High-Priority + Server SMS Gateway Fallback + `ACTION_SENDTO` (`smsto:`)** 1 chạm khi mất mạng.
* **Thông báo khẩn (DND):** FCM không tự vượt qua chế độ *Không làm phiền (Do Not Disturb)*; ứng dụng phía Người giám hộ phải tự hướng dẫn người dùng cấp quyền vượt DND cho kênh cảnh báo.
* **Các quyền nhạy cảm cần hồ sơ giải trình Play:** `SYSTEM_ALERT_WINDOW`, `MediaProjection`, `NotificationListenerService`, `PACKAGE_USAGE_STATS`, `Foreground Service (microphone/mediaProjection)`.

---

## 3. Hành lang Pháp lý Việt Nam: Luật Bảo vệ Dữ liệu Cá nhân 91/2025/QH15

* **Hiệu lực:** Luật số **91/2025/QH15** được Quốc hội thông qua ngày 26/06/2025, chính thức có hiệu lực từ **01/01/2026**.
* **Phân loại Sinh trắc học:** **Giọng nói và khuôn mặt** được xếp vào nhóm **Dữ liệu cá nhân nhạy cảm** — đòi hỏi sự đồng ý tường minh, tự nguyện của chủ thể dữ liệu và tiêu chuẩn bảo vệ kỹ thuật cao nhất (mức xử phạt vi phạm rất nặng, có thể tính theo tỷ lệ doanh thu kèm trách nhiệm dân sự/hình sự).
* **Tác động trực tiếp đến Kiến trúc:**
  * Người gọi bên kia (có thể là người vô tội) **không hề cấp đồng ý** cho việc truyền giọng nói hay hình ảnh khuôn mặt của họ lên đám mây của bên thứ ba.
  * **Bắt buộc:** Bản triển khai thực tế **không được gửi raw audio/video của người gọi lên cloud**; mọi xử lý sinh trắc học phải diễn ra cục bộ trong RAM và hủy tức thì. Chế độ Hybrid Cloud chỉ dùng trong nghiên cứu có văn bản đồng ý (*Informed Consent*) và bắt buộc **tham vấn luật sư** trước khi triển khai cộng đồng.

---

## 4. Ma trận Giải pháp Triển khai Thực tế (Cập nhật v2)

| Phương án thu nhận / bảo vệ | Nền tảng | Khả thi thực tế (Không Root) | Ghi chú triển khai trong v2 |
| :--- | :--- | :--- | :--- |
| **A. Layer 0 Metadata + Chat Context + Point-of-Loss Interception** *(NotificationListener + CallScreening + UsageStats)* | Android (10+) không root | **100% Khả thi**, chạy mượt trên máy RAM 3–4GB | **Nền tảng cốt lõi của Android MVP (v2)** — chặn đúng kịch bản gọi ngắn + nhắn tin + mở app ngân hàng/AnyDesk |
| **B. Desktop Companion / Built-in WebRTC Safe-Call** *(WASAPI Loopback / WebRTC RTP + Screen Capture)* | Windows / macOS / App gọi riêng | **100% Khả thi**, tín hiệu số sạch 100% | **Nền tảng chuẩn cho Nghiên cứu AI, Replay Harness & Demo đủ 3 Engine** |
| **C. Android `MediaProjection` Video Forensics** | Android Tier 2–3 (`>= 6GB RAM`) | **Khả thi** (cần duyệt quyền & kiểm soát nhiệt/FPS) | Bổ sung bằng chứng hình ảnh cho cuộc gọi video nghi vấn (2–5 FPS) |
| **D. Android Loa ngoài + Micro** | Android (10+) không root | **Rủi ro rất cao** (bị Android 10+ trả buffer 0 qua `isClientSilenced()`) | **Không mặc định sử dụng**; chỉ kiểm chứng trong **Phase 0 Spike** trên 3–4 hãng máy và tuyệt đối không đặt AEC trước Engine A |
| **E. Phần cứng Phụ trợ / Hợp tác OEM** | Thiết bị đặt cạnh / System Priv-app | Khả thi ở Phase mở rộng | Giải pháp dài hạn để có luồng audio độc lập ngoài sandbox Android |
