# Realtime Deepfake Shield

**Lá chắn Chống Lừa đảo Deepfake & Giả mạo Đa kênh Thời gian thực cho Người cao tuổi**

Dự án nghiên cứu và phát triển hệ thống bảo vệ đa tầng cho người cao tuổi trước tội phạm công nghệ cao tại Việt Nam, kết hợp **Lớp 0 Thông tin người gọi & Tin nhắn**, **Theo dõi Phiên nghi vấn xuyên kênh**, **3 Động cơ Bằng chứng AI có điều kiện (Audio / Video / Context)**, **Xác minh Ngoài kênh**, **Chặn tại Điểm mất tiền** (app ngân hàng, `AnyDesk`, APK giả) và **Cảnh báo SOS liên thế hệ theo quyền tối thiểu**.

---

## Cấu trúc Thư mục Dự án (Hiện tại: Kiến trúc v2.0 + Phase 0 + Phase 1 MVP)

```text
realtime-deepfake-shield/
├── .gitignore                                       # Chặn commit raw audio/video/biometric PII
├── pyproject.toml                                   # Cấu hình gói shield_core, backend, desktop, pytest
├── README.md
├── docs/
│   ├── research/                                    # Nghiên cứu học thuật, GitHub SOTA, kịch bản VN & Luật 91/2025
│   ├── architecture/
│   │   ├── SYSTEM_ARCHITECTURE.md                   # Bản thiết kế kiến trúc hệ thống v2.0 (6 tầng)
│   │   ├── DESIGN_REVIEW_v1.md                      # Nhật ký rà soát 14 lỗ hổng v1 (P0/P1/P2) -> sửa đổi v2
│   │   └── THREAT_MODEL.md                          # Mô hình mối đe dọa, ranh giới tin cậy & 8 kịch bản tấn công
│   └── phase0/
│       ├── ANDROID_SPIKE_MATRIX.md                  # Ma trận kiểm chứng 3-4 máy Android thật
│       └── LEGAL_AND_PLAY_COMPLIANCE.md             # Hồ sơ Luật 91/2025/QH15, IRB & Google Play
├── src/
│   ├── shield_core/                                 # Core v2 Engine: Layer 0, Context, Calibrated Noisy-OR, Replay Harness
│   ├── shield_backend/                              # Phase 1 Track A: FastAPI SOS Quyền tối thiểu, Anti-Tamper & Remote Config
│   └── shield_desktop/                              # Phase 1 Track A: ONNX Runtime Adapters (Audio/Video/SLM) & Desktop Runner
├── spikes/
│   ├── android-phase0-spike/                        # Dự án Android kiểm chứng 4 probe OS thực địa
│   └── desktop-phase0-spike/                        # Offline Replay Benchmark (10 kịch bản VN), Đo suy giảm & Lab Capture
├── apps/
│   └── android-shield-mvp/                          # Phase 1 Track B: Ứng dụng Android Shield MVP (Kotlin + Compose)
└── tests/                                           # Bộ kiểm thử tự động pytest (Phase 0 + Phase 1)
```

---

## Tài liệu Cốt lõi

* **Kiến trúc Hệ thống & An ninh (v2.0):**
  * [SYSTEM_ARCHITECTURE.md](./docs/architecture/SYSTEM_ARCHITECTURE.md) — Kiến trúc 6 tầng v2.0, Calibrated Noisy-OR Fusion, Point-of-Loss Guard, Device Tiering, MLOps và lộ trình.
  * [DESIGN_REVIEW_v1.md](./docs/architecture/DESIGN_REVIEW_v1.md) — Phân tích chi tiết 14 lỗ hổng của v1 và cách v2 giải quyết.
  * [THREAT_MODEL.md](./docs/architecture/THREAT_MODEL.md) — Ranh giới tin cậy, hồ sơ kẻ tấn công (`A1`–`A4`) và ma trận 8 kịch bản tấn công (`T1`–`T8`).
* **Hồ sơ Phase 0 Validation Spike:**
  * [ANDROID_SPIKE_MATRIX.md](./docs/phase0/ANDROID_SPIKE_MATRIX.md) & [LEGAL_AND_PLAY_COMPLIANCE.md](./docs/phase0/LEGAL_AND_PLAY_COMPLIANCE.md)
* **Tổng hợp Nghiên cứu & Tài nguyên Mở:** [docs/research/README.md](./docs/research/README.md)
  * [01. Phát hiện Deepfake Giọng nói & Voice Clone](./docs/research/01_audio_deepfake_detection.md)
  * [02. Phát hiện Face-Swap & Liveness trong Video Call](./docs/research/02_video_faceswap_detection.md)
  * [03. Phát hiện Vishing & Chat Lừa đảo Thời gian thực](./docs/research/03_vishing_stt_llm_context.md)
  * [04. HCI Người cao tuổi, Ràng buộc OS, Play Policy & Luật 91/2025](./docs/research/04_elderly_hci_and_os_constraints.md)

---

## Chạy Kiểm thử & Khởi chạy Phase 0 + Phase 1 MVP

1. **Chạy toàn bộ Unit & Integration Tests (`pytest`):**
```powershell
py -3.12 -m pytest -v
```

2. **Chạy Offline Replay Benchmark (10 kịch bản Việt Nam):**
```powershell
py -3.12 spikes\desktop-phase0-spike\run_replay_benchmark.py
```

3. **Chạy Mô phỏng End-to-End Desktop Runner → FastAPI SOS Backend:**
```powershell
$env:PYTHONPATH="src"
py -3.12 -m shield_desktop.desktop_runner --simulate-t1
```

4. **Khởi chạy FastAPI SOS & Remote Config Backend (Local Server):**
```powershell
$env:PYTHONPATH="src"
py -3.12 -m uvicorn shield_backend.app:create_app --factory --host 127.0.0.1 --port 8000
```

5. **Mở Ứng dụng Android (trên Android Studio — JDK 17, compileSdk 35):**
   * Phase 0 Probe: [`spikes/android-phase0-spike`](./spikes/android-phase0-spike/README.md)
   * Phase 1 Shield MVP: [`apps/android-shield-mvp`](./apps/android-shield-mvp/README.md)
