# Android Phase 0 Validation Spike

Ứng dụng kiểm chứng thực địa 4 probe kỹ thuật trên các điện thoại Android thương mại (không root) trước khi lập trình Phase 1:

1. **Probe 1 (`AudioCaptureProbe`):** Đo `isClientSilenced()`, tỷ lệ mẫu bằng 0 (`zeroSampleRatio`) và âm lượng `rmsDb` khi Zalo, Messenger hoặc cuộc gọi PSTN đang giữ micro.
2. **Probe 2 (`ScreenCaptureProbe`):** Đo `MediaProjection` (`~3 FPS`) trong cuộc gọi video Zalo/Messenger để phát hiện `FLAG_SECURE` (`blackFrameRatio`) và mức suy giảm sắc nét Laplacian.
3. **Probe 3 (`ScamNotificationProbeService`):** Kiểm chứng đọc metadata ẩn danh từ thông báo Zalo/Messenger/SMS qua `NotificationListenerService`.
4. **Probe 4 (`PointOfLossProbe`):** Đo độ trễ (ms) khi phát hiện người dùng mở ứng dụng ngân hàng Việt Nam hoặc công cụ điều khiển từ xa (`AnyDesk`, `TeamViewer`, `RustDesk`).

## Cách Biên dịch & Chạy Thử

1. Mở thư mục `spikes/android-phase0-spike` bằng **Android Studio** (JDK 17, Android SDK 35).
2. Cắm điện thoại Android thật (bật USB Debugging) và nhấn **Run `app`**.
3. Thực hiện các bước kiểm thử và điền số liệu JSON từ nút **Copy JSON Matrix Report** vào [ANDROID_SPIKE_MATRIX.md](../../docs/phase0/ANDROID_SPIKE_MATRIX.md).

> **Tuân thủ Chính sách Play & Quyền riêng tư:** Project này **không** khai báo `SEND_SMS`, **không** dùng `AccessibilityService` và hoàn toàn **không ghi âm thanh hay ảnh chụp màn hình xuống bộ nhớ**.
