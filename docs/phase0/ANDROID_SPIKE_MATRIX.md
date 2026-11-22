# Ma Trận Kiểm Chứng Thực Địa Android — Phase 0 Validation Spike (Tuần 1–2)

**Mục đích:** Trả lời dứt khoát bằng số liệu thực nghiệm trên điện thoại Android thương mại (không root) trước khi quyết định đầu tư lập trình sản phẩm cho Phase 1:
1. Khi Zalo, Messenger hoặc cuộc gọi PSTN đang hoạt động, app thứ ba gọi `AudioRecord` có bị Android 10+ ép câm (`isClientSilenced == true` / buffer toàn số 0) hay không?
2. `NotificationListenerService` lấy được chính xác những trường dữ liệu nào từ Zalo (`com.zing.zalo`) và Messenger (`com.facebook.orca`)?
3. `MediaProjection` chụp khung hình cuộc gọi video Zalo/Messenger ở `2–5 FPS` có làm giật cuộc gọi hay bị màn hình đen (`FLAG_SECURE`) không?
4. `UsageStatsManager` phát hiện người cao tuổi mở app ngân hàng (`VCB`, `BIDV`, `MB`, `MoMo`...) hoặc `AnyDesk` với độ trễ bao nhiêu mili-giây?

**Ứng dụng thử nghiệm:** [spikes/android-phase0-spike/](../../spikes/android-phase0-spike/README.md)

---

## 1. Quy trình Chạy Thử nghiệm (Test Protocol)

### Chuẩn bị Thiết bị
Chọn tối thiểu **3–4 hãng máy phổ biến với người cao tuổi tại Việt Nam**:
* **Máy 1:** Samsung Galaxy A-series (One UI, Android 13–15, RAM 4–6 GB)
* **Máy 2:** Xiaomi / Redmi (HyperOS / MIUI, Android 13–14, RAM 4–6 GB)
* **Máy 3:** Oppo / Realme (ColorOS, Android 13–14, RAM 4–6 GB)
* **Máy 4 (Tham chiếu chuẩn AOSP):** Google Pixel hoặc máy chạy Android 14–15 thuần

### Các bước thực hiện cho mỗi máy
1. Mở project `spikes/android-phase0-spike` trong **Android Studio (JDK 17, compileSdk 35)** và cài trực tiếp qua cáp USB (`adb install`).
2. Cấp lần lượt 4 quyền kiểm thử trong giao diện app:
   * `RECORD_AUDIO` (cho **Probe 1: Concurrent Audio**)
   * `MediaProjection` qua hộp thoại hệ thống (cho **Probe 2: Video Screen Capture**)
   * `NotificationListenerService` trong *Cài đặt → Truy cập thông báo* (cho **Probe 3: Layer 0**)
   * `PACKAGE_USAGE_STATS` trong *Cài đặt → Truy cập dữ liệu sử dụng* (cho **Probe 4: Point-of-Loss**)
3. **Kịch bản A (Concurrent Audio):** Bật Probe 1, sau đó nhận lần lượt (a) cuộc gọi thoại Zalo, (b) cuộc gọi video Zalo bật loa ngoài, (c) cuộc gọi video Messenger, (d) cuộc gọi di động PSTN bật loa ngoài. Đọc trực tiếp chỉ số `isClientSilenced`, `zeroSampleRatio`, và `rmsDb`.
4. **Kịch bản B (Notification Layer 0):** Dùng tài khoản phụ đặt tên trùng với 1 liên hệ giả lập trong Allowlist (ví dụ `"Con trai Minh"`), thực hiện gọi Zalo 5 giây rồi cúp máy và nhắn `"Sóng yếu quá mẹ chuyển gấp 20 triệu vào STK này"`. Kiểm tra log đã ẩn danh xem có trích xuất được `senderName` và `textPreview` không.
5. **Kịch bản C (MediaProjection Video):** Bật Probe 2 ở `3 FPS` trong cuộc gọi video Zalo/Messenger, ghi nhận khung hình có bị đen (`blackFrameRatio`) hay không, độ nét Laplacian trung bình và cảm nhận độ mượt cuộc gọi.
6. **Kịch bản D (Point-of-Loss):** Mở app ngân hàng (VCB/MoMo) và app `AnyDesk`; ghi lại độ trễ phát hiện (`detectionLatencyMs`) và kiểm tra khi bật chế độ tiết kiệm pin của MIUI/ColorOS/One UI.

---

## 2. Bảng Ghi Nhận Kết Quả Thực Nghiệm (Điền sau khi chạy trên máy thật)

### 2.1. Probe 1 — Thu âm Đồng thời (`AudioRecord` + `isClientSilenced`)

| Thiết bị / ROM / Android | Kênh gọi | `isClientSilenced` | `zeroSampleRatio` (%) | `rmsDb` (dBFS) | Kết luận (Thu được tiếng đầu dây bên kia?) |
| :--- | :--- | :---: | :---: | :---: | :--- |
| Samsung Galaxy A... (One UI / Android ...) | Zalo Voice (Loa ngoài) | *Chờ đo* | *Chờ đo* | *Chờ đo* | *PASS / FAIL* |
| Samsung Galaxy A... | Zalo Video (Loa ngoài) | *Chờ đo* | *Chờ đo* | *Chờ đo* | *PASS / FAIL* |
| Samsung Galaxy A... | Messenger Video | *Chờ đo* | *Chờ đo* | *Chờ đo* | *PASS / FAIL* |
| Samsung Galaxy A... | PSTN Call (Loa ngoài) | *Chờ đo* | *Chờ đo* | *Chờ đo* | *PASS / FAIL* |
| Xiaomi / Redmi (HyperOS / Android ...) | Zalo Video (Loa ngoài) | *Chờ đo* | *Chờ đo* | *Chờ đo* | *PASS / FAIL* |
| Oppo / Realme (ColorOS / Android ...) | Zalo Video (Loa ngoài) | *Chờ đo* | *Chờ đo* | *Chờ đo* | *PASS / FAIL* |
| Pixel / AOSP (Android 14–15) | Zalo Video (Loa ngoài) | *Chờ đo* | *Chờ đo* | *Chờ đo* | *PASS / FAIL* |

### 2.2. Probe 2, 3, 4 — `MediaProjection`, `NotificationListener` & `UsageStats`

| Thiết bị / ROM | Zalo `NotificationListener` (Tên gọi + Tin nhắn?) | Messenger `NotificationListener` (Tên gọi + Tin nhắn?) | `MediaProjection` Zalo/Messenger (Bị `FLAG_SECURE` đen hình? FPS thực?) | `UsageStats` phát hiện App Ngân hàng / AnyDesk (Độ trễ ms) | Ghi chú hành vi kill background (MIUI/ColorOS/OneUI) |
| :--- | :---: | :---: | :---: | :---: | :--- |
| Samsung Galaxy A... | *Chờ đo* | *Chờ đo* | *Chờ đo* | *Chờ đo* | *Chờ đo* |
| Xiaomi / Redmi | *Chờ đo* | *Chờ đo* | *Chờ đo* | *Chờ đo* | *Chờ đo* |
| Oppo / Realme | *Chờ đo* | *Chờ đo* | *Chờ đo* | *Chờ đo* | *Chờ đo* |
| Pixel / AOSP | *Chờ đo* | *Chờ đo* | *Chờ đo* | *Chờ đo* | *Chờ đo* |

---

## 3. Tiêu chí Cổng Quyết định (Go / No-Go Gate cho Phase 1)

* **Cổng Audio Android:** Nếu `>= 50%` thiết bị thử nghiệm báo `isClientSilenced == true` hoặc `zeroSampleRatio > 95%` → **CHỐT CHÍNH THỨC** không xây Engine A trên micro Android không root; Android MVP tập trung hoàn toàn vào **Layer 0 + Chat Engine C + MediaProjection Video (Tier 2–3) + Point-of-Loss Guard**.
* **Cổng Layer 0 & Point-of-Loss:** Bắt buộc đạt tỷ lệ phát hiện `>= 95%` tên/tin nhắn Zalo & Messenger (khi bật xem trước thông báo) và độ trễ phát hiện mở app ngân hàng `< 1000 ms` trước khi triển khai Phase 1 Track B.
* **Cổng Video `MediaProjection`:** Nếu Zalo/Messenger bật `FLAG_SECURE` trả khung hình đen trên bản mới nhất → ghi nhận giới hạn và chuyển nhánh Video sang Desktop Companion / Built-in WebRTC Safe-Call.
