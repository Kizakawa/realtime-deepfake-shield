# Desktop Phase 0 Spike — Replay Harness & Công cụ Đo Suy giảm VoIP

Thư mục này cung cấp bộ công cụ chạy trực tiếp trên máy tính Windows (không cần GPU rời) để thực hiện các phép kiểm chứng Phase 0 theo [SYSTEM_ARCHITECTURE.md](../../docs/architecture/SYSTEM_ARCHITECTURE.md) v2.0.

## 1. Chạy Offline Replay Evaluation Harness (10 kịch bản Việt Nam)
```powershell
py -3.12 spikes\desktop-phase0-spike\run_replay_benchmark.py
```
Kiểm tra:
* 5 kịch bản tấn công (`T1` gọi 5s mờ + nhắn tin + mở app ngân hàng; `T2` giả công an + AnyDesk; `T3` hạ chất lượng video; `T5` Prompt Injection; `T6` Audio Deepfake Desktop).
* 4 kịch bản lành tính (con trai thật chuyển tiền mua thuốc, con gái thật rớt mạng, shipper gọi 12s, mở ngân hàng sau khi hết TTL 60 phút).
* 1 kịch bản cấp cứu `115`.

## 2. Chạy Kiểm thử Đo Suy giảm Tín hiệu Audio/Video (CPU Self-Test)
```powershell
py -3.12 spikes\desktop-phase0-spike\measure_degradation.py --self-test
```
Hoặc đo trực tiếp giữa 2 tệp thu được qua cuộc gọi Zalo thật:
```powershell
py -3.12 spikes\desktop-phase0-spike\measure_degradation.py `
  --clean-wav path\to\clean.wav --degraded-wav path\to\zalo_recorded.wav `
  --clean-img path\to\clean.png --degraded-img path\to\zalo_screen.png
```

## 3. Thu mẫu Phòng thí nghiệm trên Desktop (Windows WASAPI Loopback)
Cài thêm gói tùy chọn desktop (`pip install -e .[desktop]` hoặc `pip install pyaudiowpatch`), sau đó chạy:
```powershell
# Chế độ mặc định Zero-Retention (chỉ in chỉ số, không lưu đĩa)
py -3.12 spikes\desktop-phase0-spike\capture_desktop_lab.py --duration 5

# Chỉ lưu mẫu nghiên cứu vào data/consented_lab/ (đã git-ignore) khi có đồng ý bằng văn bản
py -3.12 spikes\desktop-phase0-spike\capture_desktop_lab.py --duration 8 --sample-id zalo_test_01 --i-have-written-consent
```
