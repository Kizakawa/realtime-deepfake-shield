# Android Shield MVP (Phase 1 Track B — v2.0)

Ứng dụng Android bảo vệ người cao tuổi được xây dựng theo đúng kiến trúc v2.0 trong [SYSTEM_ARCHITECTURE.md](../../docs/architecture/SYSTEM_ARCHITECTURE.md) và kết quả rà soát pháp lý/Google Play trong [LEGAL_AND_PLAY_COMPLIANCE.md](../../docs/phase0/LEGAL_AND_PLAY_COMPLIANCE.md).

## Đặc điểm Kiến trúc Cốt lõi
* **Tuân thủ Chính sách Google Play & Android 10+:** Không yêu cầu quyền gửi SMS nền, không dùng dịch vụ trợ năng, và không giả định thu âm micro VoIP.
* **Lớp 0 (`ShieldCallScreeningService` + `ShieldNotificationListenerService`):** Miễn trừ cứng `113/114/115` và danh bạ gia đình tin cậy (*Family Allowlist*); phát hiện mạo danh tên người thân và đọc tin nhắn xem trước hoàn toàn trong RAM.
* **Chặn Điểm mất tiền (`PointOfLossMonitorService` + `PackageSideloadReceiver`):** Chỉ chạy theo dõi `UsageStatsManager` khi đang có phiên nghi vấn; kích hoạt ngay màn hình làm nguội **30 giây** (`CoolingOffOverlayActivity`) khi mở app ngân hàng Việt Nam hoặc cài `AnyDesk`/APK nguồn lạ.
* **Xác minh Ngoài kênh & Quyền tối thiểu:** Nút hành động chính **`TẠM DỪNG — GỌI LẠI SỐ ĐÃ LƯU`**, gửi gói tin SOS không kèm transcript sang `shield_backend`, định kỳ gửi `AntiTamperHeartbeatWorker` và hiển thị **Transparency Log** cho người cao tuổi.

## Cách Mở & Chạy thử với Backend Local
1. Chạy backend FastAPI trên máy tính:
   ```powershell
   $env:PYTHONPATH="src"
   py -3.12 -m uvicorn shield_backend.app:create_app --factory --host 127.0.0.1 --port 8000
   ```
2. Nối cổng USB sang điện thoại Android thật:
   ```powershell
   adb reverse tcp:8000 tcp:8000
   ```
3. Mở thư mục `apps/android-shield-mvp` bằng **Android Studio** (JDK 17, compileSdk 35) và nhấn **Run `app`**.
