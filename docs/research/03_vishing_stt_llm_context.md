# 03. Nghiên cứu Phát hiện Vishing Thời gian thực (Streaming STT + SLM/LLM Ngữ cảnh)

Tài liệu này tổng hợp các nghiên cứu học thuật, kho mã nguồn GitHub và tài nguyên tiếng Việt cho **Nhánh Phân tích Ngữ cảnh Hội thoại (Engine C)** — lớp bảo vệ đặc biệt hiệu quả ngay cả khi kẻ gian không dùng deepfake (ví dụ: người thật gọi kịch bản lừa đảo giả danh công an, viện kiểm sát, ngân hàng).

---

## 1. Bài báo Học thuật Trọng tâm

### "It Warned Me Just at the Right Moment": Exploring LLM-based Real-time Detection of Phone Scams
* **Nguồn / Năm:** Zitong Shen et al. (Hong Kong Polytechnic University - PolyU), 2025 (CHI Extended Abstracts / arXiv)
* **Mã định danh:** `arXiv:2502.03964` — [https://arxiv.org/abs/2502.03964](https://arxiv.org/abs/2502.03964)
* **Bài toán & Đóng góp cốt lõi:** Nghiên cứu cơ chế LLM đánh giá cuộc gọi theo từng lượt thoại (*turn-by-turn*) theo thời gian thực. Chỉ ra bài toán đánh đổi sống còn: cảnh báo quá sớm khi mới nghe vài từ đơn lẻ (như "chuyển tiền", "công an") sẽ gây báo động giả, nhưng chờ hết cuộc gọi thì nạn nhân đã chuyển tiền xong. Nhóm tác giả đề xuất **trạng thái `UNCERTAIN`**, cho phép mô hình chủ động trì hoãn phán quyết và tiếp tục gom thêm ngữ cảnh cho đến khi đủ bằng chứng thao túng.
* **Ứng dụng vào Realtime Deepfake Shield:** Là cơ sở khoa học trực tiếp cho cơ chế trì hoãn giữ phiên nghi vấn (**`SUSPICION_SESSION`**) trong **Máy trạng thái xuyên kênh 5 mức** của kiến trúc v2.

### Combating Phone Scams with LLM-based Detection: Where Do We Stand?
* **Nguồn / Năm:** Zitong Shen et al., AAAI 2025 (Student Abstract)
* **Mã định danh:** `arXiv:2409.11643` — [https://arxiv.org/abs/2409.11643](https://arxiv.org/abs/2409.11643)
* **Bài toán & Đóng góp cốt lõi:** Đánh giá khả năng của các LLM trong việc nhận diện cấu trúc đối thoại giữa kẻ lừa đảo và nạn nhân (các pha xây dựng uy quyền, tạo nỗi sợ hãi, cô lập nạn nhân khỏi người thân và thúc ép giao dịch tài chính).
* **Ứng dụng vào Realtime Deepfake Shield:** Xây dựng bộ tiêu chí 5 trục thao túng tâm lý cho bộ phân loại ngữ cảnh tiếng Việt.

### ChunkFormer: Masked Chunking Conformer for Long-Form Speech Recognition
* **Nguồn / Năm:** khanhld et al., ICASSP 2025
* **Mã định danh:** `arXiv:2502.14673` — [https://arxiv.org/abs/2502.14673](https://arxiv.org/abs/2502.14673)
* **Mã nguồn:** [khanld/chunkformer](https://github.com/khanld/chunkformer)
* **Bài toán & Đóng góp cốt lõi:** Kiến trúc Conformer chia đoạn có mặt nạ (*Masked Chunking Conformer*) tối ưu hóa bộ nhớ GPU/CPU cực tốt cho nhận dạng tiếng nói luồng dài (*long-form streaming ASR*). Phiên bản `ChunkFormer-CTC-Large-Vie` được huấn luyện trên khoảng **3.000 giờ tiếng Việt**.
* **Ứng dụng vào Realtime Deepfake Shield:** Làm động cơ Streaming STT chính cho tiếng Việt trên máy chủ/Desktop (độ trễ thấp, xử lý cuộc gọi kéo dài hàng chục phút không tràn bộ nhớ).

---

## 2. Kho Mã Nguồn GitHub Tham Khảo

| Kho mã nguồn / Dự án | Kiến trúc / Công nghệ | Điểm nổi bật ứng dụng cho dự án |
| :--- | :--- | :--- |
| [abhishek-pandey7/Kavach-Realtime-Voice-Threat-Intelligence](https://github.com/abhishek-pandey7/Kavach-Realtime-Voice-Threat-Intelligence) | Streaming STT + Rolling-window LLM + TTS Warning | Cài đặt thực tế trạng thái `UNCERTAIN` và chấm điểm rủi ro trên cửa sổ trượt cho các cuộc gọi đa ngữ/pha trộn ngôn ngữ |
| [junhoeKu/Voice-Phishing-Detection](https://github.com/junhoeKu/Voice-Phishing-Detection) | Whisper + **SLM fine-tuned QLoRA 4-bit** + Overlapping Sliding Windows | Chứng minh dùng Mô hình Ngôn ngữ Nhỏ (SLM 4-bit) kết hợp cửa sổ trượt gối đầu giúp chạy nhẹ mà không mất mạch hội thoại dài |
| [satya-py/real_time_fraudcall_detection](https://github.com/satya-py/real_time_fraudcall_detection) | **Android (Kotlin)** + FastAPI + WebSockets + `whisper.cpp` | Full-stack mẫu xử lý luồng audio mỗi **cửa sổ trượt 4 giây**, trả về điểm rủi ro liên tục `0.0–1.0` và theo dõi giai đoạn cuộc gọi |
| [BYU-PCCL/scam-call-identification](https://github.com/BYU-PCCL/scam-call-identification) | Python, Docker, Whisper/STT, LLM NLP | Trích xuất đặc trưng hành vi gây áp lực thời gian và sự khẩn cấp trong hội thoại |
| *A Multimodal Framework for Voice Phishing Detection via Integrated Text and Speech Processing* (Dự án GitHub tham chiếu) | Whisper + BERT + Resemblyzer (Speaker Diarization) + CNN-BiLSTM | Minh họa công thức **hợp nhất có trọng số (Weighted Score Fusion)** giữa phân tích văn bản và phát hiện giọng tổng hợp |

---

## 3. Tài nguyên Tiếng Việt (ASR & Dữ liệu Kịch bản Lừa đảo)

### Nhận dạng Giọng nói Tiếng Việt (Vietnamese ASR)
1. **[khanld/chunkformer](https://github.com/khanld/chunkformer):** Nhẹ, chạy dạng chunk thời gian thực, hỗ trợ rất tốt hội thoại dài trên phần cứng giới hạn.
2. **[VinAIResearch/PhoWhisper](https://github.com/VinAIResearch/PhoWhisper):** Mô hình Whisper được VinAI tinh chỉnh trên **844 giờ dữ liệu tiếng Việt** đa vùng miền (tỷ lệ lỗi từ WER rất thấp). Có thể lượng tử hóa và chạy cục bộ qua `whisper.cpp` / `sherpa-onnx` cho biến thể nhẹ (`PhoWhisper-tiny` / `base` / `small`).

### Tập dữ liệu Kịch bản & Tin nhắn Lừa đảo Việt Nam
1. **[hoangvt2501/data_scam](https://github.com/hoangvt2501/data_scam):** Tập dữ liệu văn bản phân loại **~29 nhóm kịch bản lừa đảo phổ biến tại Việt Nam** (giả danh công an/viện kiểm sát, nâng cấp SIM, khóa tài khoản ngân hàng, tuyển cộng tác viên, người thân cấp cứu...).
2. **[trannguyenthaituan251209/vietnamese_sms_dataset](https://github.com/trannguyenthaituan251209/vietnamese_sms_dataset):** Tập dữ liệu văn bản spam/lừa đảo tiếng Việt đã được làm sạch thông tin định danh cá nhân (PII), tổng hợp có sự hỗ trợ từ cộng đồng **Chống Lừa Đảo**.

---

## 4. Kết luận Lựa chọn Công nghệ cho Dự án (Cập nhật v2)

Kiến trúc **Engine C (Unified Chat & Voice Context)** được mở rộng từ chỉ xử lý hội thoại sang **quét song song cả tin nhắn Zalo/Messenger/SMS và luồng thoại ASR** nhằm bao phủ kịch bản *"gọi video 3–5 giây rồi nhắn tin vay tiền"*:

1. **Đa nguồn đầu vào (Chat + Streaming ASR):**
   * *Kênh Chat (luôn khả dụng trên Android không root):* Đọc tin nhắn xem trước qua `NotificationListenerService` ngay khi đang mở `SUSPICION_SESSION`.
   * *Kênh Thoại (Desktop / WebRTC / thiết bị vượt Phase 0 Spike):* Dùng `ChunkFormer-CTC-Large-Vie` (Desktop/Server) hoặc `PhoWhisper-tiny` chạy qua `whisper.cpp` / `sherpa-onnx` + `Silero VAD`.
2. **Tầng Lọc Nhanh (Keyword & Pattern Pre-Filter):** Bộ quy tắc cụm từ nhạy cảm tiếng Việt (*"công an điều tra", "viện kiểm sát", "lệnh bắt giữ", "phong tỏa tài khoản", "chuyển tiền gấp", "đang cấp cứu", "tuyệt đối giữ bí mật", "mã OTP", "cài app dịch vụ công", "AnyDesk"*). Chỉ kích hoạt/ưu tiên phân tích sâu, không tự bật cảnh báo Đỏ.
3. **Bộ Phân loại Ngữ cảnh An toàn & Chống Prompt Injection:**
   * *Mặc định Mobile (Tier 1–2):* Dùng encoder nhẹ **`PhoBERT-v2` Multi-label** (RAM `< 300 MB`, miễn nhiễm prompt injection).
   * *Desktop / Tier 3 (SLM 4-bit `Qwen2.5-1.5B/3B` QLoRA):* Bọc dữ liệu đầu vào trong thẻ `<UNTRUSTED_INPUT>...</UNTRUSTED_INPUT>`, ép đầu ra bằng **Structured JSON Schema Constrained Decoding** và không cấp quyền tool-calling.
   * Phân loại **6 nhãn chiến thuật đặc thù Việt Nam**: `Authority_Impersonation`, `Relative_Emergency`, `Urgency_Fear`, `Secrecy_Isolation`, `Financial_Transfer`, và `Malicious_App_Install` (APK giả / AnyDesk / TeamViewer).
