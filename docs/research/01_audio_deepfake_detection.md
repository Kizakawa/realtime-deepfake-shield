# 01. Nghiên cứu Phát hiện Deepfake Giọng nói & Voice Clone (Audio Anti-Spoofing)

Tài liệu này tổng hợp các công trình khoa học, bộ chuẩn đánh giá (benchmarks), tập dữ liệu tiếng Việt và kho mã nguồn GitHub cho **Nhánh Phân tích Âm thanh (Engine A)** của hệ thống *Realtime Deepfake Shield*.

---

## 1. Bài báo Khoa học & Benchmarks Quốc tế

### AASIST (Audio Anti-Spoofing using Integrated Spectro-Temporal Graph Attention Networks)
* **Nguồn / Năm:** Naver Corporation — CLOVA AI Lab (ICASSP 2022)
* **Mã nguồn chính thức:** [clovaai/aasist](https://github.com/clovaai/aasist)
* **Bài toán & Đóng góp cốt lõi:** Kết hợp đồng thời biểu diễn dạng sóng thô (raw waveform qua bộ lọc SincNet) và đặc trưng phổ thời gian–tần số (spectro-temporal) bằng mạng đồ thị chú ý (*Graph Attention Network*). Khắc phục nhược điểm bỏ sót pha tín hiệu của các mô hình CNN thuần túy trên ảnh Spectrogram.
* **Ứng dụng vào Realtime Deepfake Shield:** Là mô hình xương sống (backbone) cho cả cấu hình gọn nhẹ trên thiết bị (biến thể `AASIST-L` xuất sang ONNX INT8) và cấu hình kết hợp tự giám sát (`XLSR + AASIST`).

### SSL Anti-Spoofing (Wav2Vec 2.0 / XLSR + RawBoost)
* **Nguồn / Năm:** Hemlata Tak et al. (Speaker Odyssey Workshop)
* **Mã nguồn chính thức:** [TakHemlata/SSL_Anti-spoofing](https://github.com/TakHemlata/SSL_Anti-spoofing)
* **Bài toán & Đóng góp cốt lõi:** Sử dụng mô hình học tự giám sát đa ngôn ngữ (`Wav2Vec 2.0 / XLSR`) làm bộ trích xuất đặc trưng đầu vào (front-end) kết hợp với back-end `AASIST` và kỹ thuật tăng cường dữ liệu **RawBoost** (mô phỏng nhiễu truyền dẫn và méo tín hiệu). Đạt hiệu năng SOTA trên các bộ *ASVspoof 2021 LA (Logical Access)* và *DF (Deepfake)*.
* **Hạn chế / Lưu ý thực nghiệm:** Mô hình XLSR gốc có kích thước lớn, tốn tài nguyên tính toán hơn khi chạy hoàn toàn trên smartphone tầm trung.
* **Ứng dụng vào Realtime Deepfake Shield:** Dùng làm mô hình chính cho **Chế độ Hybrid Edge-Cloud** và làm mô hình giáo viên (teacher) để tinh chỉnh (fine-tune) trên dữ liệu tiếng Việt đa vùng miền.

### ASVspoof 5 (2024–2026)
* **Nguồn / Năm:** ASVspoof Challenge Series (2024–2026)
* **Bài toán & Đóng góp cốt lõi:** Chuyển dịch từ dữ liệu phòng thu sạch sang **dữ liệu thu thập cộng đồng (crowdsourced)** từ khoảng 2.000 người nói trong điều kiện âm học nhiễu thực tế. Lần đầu tiên đưa vào các đòn **tấn công đối kháng (adversarial attacks)** kết hợp với các bộ mã hóa/giải mã âm thanh nơ-ron (DNN-based audio codecs), TTS và Voice Conversion hiện đại.
* **Ứng dụng vào Realtime Deepfake Shield:** Định hướng quy trình huấn luyện tăng cường (data augmentation) mô phỏng nhiễu môi trường và kênh truyền điện thoại/VoIP thực tế.

### VoiceWukong: Benchmarking Deepfake Voice Detection
* **Nguồn / Năm:** arXiv (09/2024) / USENIX Security
* **Bài toán & Đóng góp cốt lõi:** Bộ benchmark song ngữ (Anh–Trung) quy mô lớn gồm hơn **400.000 mẫu giọng giả** từ **19 công cụ thương mại** và **15 công cụ mã nguồn mở**, trải dài qua 38 biến thể và 6 loại biến dạng thực tế (nén bitrate, chèn nhiễu, lỗi truyền dẫn).
* **Hạn chế / Phát hiện quan trọng:**
  * Các mô hình phát hiện SOTA tụt hiệu năng nghiêm trọng khi gặp điều kiện thực tế (EER tốt nhất cũng rơi vào khoảng `13.5%` đến hơn `20%`).
  * Các mô hình ngôn ngữ lớn đa phương thức âm thanh (Audio LLMs như *Qwen2-Audio*) gần như **không có khả năng tự phát hiện** giọng deepfake.
* **Ứng dụng vào Realtime Deepfake Shield:** Khẳng định **không thể dùng chung LLM đa phương thức để đoán giọng giả**; bắt buộc phải tách riêng nhánh chuyên sâu xử lý tín hiệu âm học (Engine A) và phải kiểm thử qua nén VoIP.

### CodecFake & CodecFake+ (2024–2025)
* **Nguồn / Năm:** arXiv (giữa 2024 – đầu 2025)
* **Bài toán & Đóng góp cốt lõi:** Các mô hình Audio Language Models (ALMs) và bộ sinh tiếng nói mới sử dụng **Neural Audio Codecs** (như *EnCodec, SoundStream, DAC*) để sinh âm thanh trực tiếp từ các token rời rạc, thay cho vocoder truyền thống. Điều này khiến các detector cũ (chỉ tìm dấu vết vocoder) bị mù hoàn toàn. Nghiên cứu đề xuất bộ dữ liệu *Codec-Resynthesized Speech (CoRS)* làm dữ liệu huấn luyện thay thế.
* **Ứng dụng vào Realtime Deepfake Shield:** Bổ sung mẫu âm thanh tái tổng hợp qua các Neural Audio Codec vào tập huấn luyện fine-tune của Engine A để chống các công cụ clone giọng thế hệ mới.

### Real-Time Audio Streaming Detection
* **Nguồn / Năm:** arXiv:2403.11778 (2024)
* **Liên kết:** [https://arxiv.org/abs/2403.11778](https://arxiv.org/abs/2403.11778)
* **Bài toán & Đóng góp cốt lõi:** Giải quyết bài toán phát hiện audio deepfake trên **luồng phát trực tiếp (streaming)** trong điều kiện bị ràng buộc nghiêm ngặt về **độ trễ thấp (low-latency)** và nén truyền dẫn đặc trưng của các nền tảng VoIP / Video Call.
* **Ứng dụng vào Realtime Deepfake Shield:** Tham khảo cơ chế cắt cửa sổ trượt (sliding window ~3–4 giây, bước nhảy 1 giây) và đánh giá suy giảm độ tin cậy khi luồng mạng bị nén mạnh.

### Bridging the Age Gap: Towards Detecting Neural Audio Codec Synthesized Elderly Speech Deepfake
* **Nguồn / Năm:** arXiv:2606.04414 (2026)
* **Liên kết:** [https://arxiv.org/abs/2606.04414](https://arxiv.org/abs/2606.04414)
* **Bài toán & Đóng góp cốt lõi:** Nghiên cứu chứng minh các mô hình phát hiện giọng giả chính thống bị suy giảm hiệu năng nghiêm trọng khi đánh giá trên **giọng nói của người cao tuổi** (tỷ lệ lỗi có thể tăng gấp đôi do đặc trưng thanh quản lão hóa, độ rung/khàn tự nhiên dễ bị nhầm với nhiễu tổng hợp). Nhóm tác giả đề xuất kiến trúc kết hợp mô hình nền tảng đa phương thức (như *BONSAI*) để thu hẹp khoảng cách độ tuổi.
* **Ứng dụng vào Realtime Deepfake Shield:** Cảnh báo quan trọng cho kịch bản kẻ gian giả giọng ông/bà, vợ/chồng lớn tuổi hoặc đồng nghiệp về hưu gọi cho nạn nhân. Tập kiểm thử và hiệu chỉnh ngưỡng (threshold calibration) của dự án **bắt buộc phải bao gồm mẫu giọng người cao tuổi thật**.

---

## 2. Tài nguyên & Nghiên cứu Tiếng Việt

### VSASV (Vietnamese Spoofing-Aware Speaker Verification)
* **Nguồn / Tổ chức:** Cộng đồng **VLSP** ([https://vlsp.org.vn/](https://vlsp.org.vn/))
* **Quy mô & Đặc điểm:** Tập dữ liệu tiếng Việt quy mô lớn gồm hơn **174.000 mẫu giả mạo (spoofed)** và **164.000 mẫu thật (bona fide)** từ **1.382 người nói**, bao gồm các kỹ thuật TTS và Voice Conversion hiện đại. Phục vụ bài toán xác thực người nói có nhận biết giả mạo (Spoofing-Aware Speaker Verification).
* **Ứng dụng:** Tập dữ liệu nền tảng quan trọng nhất để huấn luyện và benchmark Engine A cho tiếng Việt.

### VietPrism
* **Nguồn / Năm:** arXiv / Cộng đồng nghiên cứu tiếng Việt
* **Quy mô & Đặc điểm:** Tập dữ liệu đa miền quy mô lớn gồm khoảng **99,3 giờ giọng nói thật** từ hàng nghìn video thực tế và hơn **3,1 giờ giọng nói giả mạo** có điều kiện qua nhiều hệ thống tổng hợp khác nhau. Đặc biệt thiết kế để kiểm thử khả năng chống chịu trước **đa vùng miền tiếng Việt (Bắc/Trung/Nam)** và hiện tượng **pha trộn ngôn ngữ (code-switching)**.
* **Ứng dụng:** Kiểm thử chéo khả năng tổng quát hóa (cross-domain generalization) của Engine A với các phương ngữ Việt Nam.

### Nghiên cứu Phát hiện Giả mạo Giọng nói Tiếng Việt bằng Frame-Level MHSA
* **Nguồn / Tổ chức:** Nhóm nghiên cứu **HuSTek Lab (Đại học Bách Khoa Hà Nội - HUST)**, công bố tại ICASSP.
* **Ý tưởng cốt lõi:** Vì nhiễu nhân tạo trong các đoạn giọng nói tổng hợp hoặc cuộc gọi vishing ngắn thường chỉ xuất hiện ở những vùng thời gian rất nhỏ, việc sử dụng **Multi-Head Self-Attention (MHSA) ở mức khung hình (frame-level)** cho kết quả vượt trội so với bộ phân loại gộp toàn bộ câu (utterance-level pooling).
* **Ứng dụng:** Tham khảo thiết kế lớp pooling/attention ở đầu ra cho các đoạn audio ngắn (3–4 giây) trong cuộc gọi lừa đảo.

---

## 3. Kho Mã Nguồn GitHub Tham Khảo

| Kho mã nguồn (GitHub) | Kiến trúc / Công nghệ | Mục đích tham khảo cho dự án |
| :--- | :--- | :--- |
| [clovaai/aasist](https://github.com/clovaai/aasist) | PyTorch, SincNet + Spectro-Temporal Graph Attention | Mã nguồn gốc chuẩn nhất để train/export `AASIST` & `AASIST-L` |
| [TakHemlata/SSL_Anti-spoofing](https://github.com/TakHemlata/SSL_Anti-spoofing) | Wav2Vec 2.0 / XLSR + AASIST + RawBoost | Fine-tune mô hình đa ngôn ngữ sang tiếng Việt (VSASV/VietPrism) |
| [media-sec-lab/Audio-Deepfake-Detection](https://github.com/media-sec-lab/Audio-Deepfake-Detection) | Danh mục tổng hợp bài báo, đặc trưng (LFCC, CQT, Spectrogram), hàm mất mát | Nguồn tra cứu nhanh các phương pháp tiền xử lý và benchmark mới |
| [mlvanguards/DeepFakeDetector_edge](https://github.com/mlvanguards/DeepFakeDetector_edge) | Android, PyTorch Mobile / TFLite, Mel/MFCC/LFCC | Tham khảo pipeline trích xuất đặc trưng và chạy suy luận trên thiết bị di động |
| [Ashutosh-1001/audio-deepfake-detection-rawnet2](https://github.com/Ashutosh-1001/audio-deepfake-detection-rawnet2) | RawNet2 trên ASVspoof 2019/2021 | So sánh baseline dạng sóng thô RawNet2 với AASIST |
| [raza-haider-zaidi/audio-deepfake-detection-fyp](https://github.com/raza-haider-zaidi/audio-deepfake-detection-fyp) | AASIST xuất sang ONNX / tối ưu hóa CPU/GPU streaming | Tham khảo cách đóng gói mô hình sang ONNX chạy thời gian thực |
| [imsoumya18/audio_deepfake_detector](https://github.com/imsoumya18/audio_deepfake_detector) | RawNet2 + Light CNN (Spectrogram) + FastAPI | Tham khảo API server thử nghiệm nhanh |

---

## 4. Kết luận Lựa chọn Công nghệ cho Dự án

| Phương án | Độ chính xác thực địa (VoIP + Tiếng Việt) | Tốc độ / Kích thước | Quyết định kiến trúc |
| :--- | :--- | :--- | :--- |
| **CNN thuần trên Mel-Spectrogram** | Trung bình (dễ hỏng trước CodecFake và nén VoIP) | Rất nhanh (~10–20ms) | Không dùng làm mô hình độc lập |
| **RawNet2** | Khá trên dữ liệu sạch, dễ overfit nếu thiếu RawBoost | Trung bình | Dùng để đối chứng baseline |
| **`AASIST-L` (ONNX INT8)** | Tốt khi được fine-tune kèm giả lập VoIP + CodecFake | Nhẹ (~nhỏ gọn cho CPU di động) | **Chọn cho cấu hình On-Device (Edge)** |
| **`XLSR-Wav2Vec2 + AASIST` (Fine-tuned VSASV)** | Rất cao, bắt tốt đặc trưng đa vùng miền và nhiễu nén | Nặng (cần GPU/NPU hoặc server) | **Chọn cho cấu hình Hybrid Cloud (MVP)** |

**Quy tắc bắt buộc khi huấn luyện Engine A:** Mọi dữ liệu huấn luyện (*VSASV*, *VietPrism*, dữ liệu tự thu) đều phải đi qua tầng mô phỏng kênh truyền thực tế: giảm mẫu xuống `8kHz/16kHz`, nén qua các codec cuộc gọi (**Opus, AMR-NB, G.711**), trộn nhiễu môi trường gia đình (**RawBoost**), và bổ sung mẫu **CodecFake** + **giọng người cao tuổi thật**.
