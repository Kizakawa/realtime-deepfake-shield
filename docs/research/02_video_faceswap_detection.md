# 02. Nghiên cứu Phát hiện Face-Swap & Liveness trong Video Call (Computer Vision)

Tài liệu này tổng hợp các nghiên cứu học thuật, phân tích giới hạn kỹ thuật và kho mã nguồn mở GitHub cho **Nhánh Thị giác Máy tính (Engine B)** của hệ thống *Realtime Deepfake Shield*.

---

## 1. Cảnh báo Học thuật: Giới hạn của "Nhịp chớp mắt" (Blink Rate / EAR)

Trong các bài báo thế hệ đầu như ***In Ictu Oculi***, việc không chớp mắt tự nhiên từng là dấu hiệu vàng để nhận biết video deepfake (do tập dữ liệu mặt tĩnh thiếu ảnh nhắm mắt). Tuy nhiên, **các khảo sát giai đoạn 2024–2026 trên arXiv khẳng định phương pháp đo nhịp chớp mắt không còn đủ để làm trụ cột phát hiện Face-Swap thời gian thực**:

1. **Công cụ Face-Swap live sao chép trực tiếp biểu cảm:** Các phần mềm ghép mặt thời gian thực hiện nay (như *DeepFaceLive*, *FaceFusion*) ánh xạ trực tiếp điểm mốc khuôn mặt (*facial landmarks*) của kẻ lừa đảo sang khuôn mặt nạn nhân. Khi kẻ lừa đảo chớp mắt tự nhiên trước webcam, khuôn mặt giả cũng chớp mắt đồng bộ.
2. **Suy hao tín hiệu do nén Video Call:** Zalo, Messenger, WhatsApp sử dụng thuật toán nén luồng thời gian thực mạnh (giảm bitrate, hạ FPS khi mạng yếu), làm mờ ranh giới ghép mặt (*blending boundaries*) và xóa nhòa các vi chuyển động ở vùng mắt.
3. **Sụp đổ tổng quát hóa (Generalization Collapse):** Các mô hình thụ động chỉ học dấu vết của bộ dữ liệu offline cũ (như *FaceForensics++*) có thể tụt `40–50% AUC` khi gặp bộ sinh hình ảnh trực tiếp mới.

**Kết luận thiết kế:** MediaPipe Face Mesh + OpenCV EAR (*Eye Aspect Ratio*) **chỉ được giữ lại như một tín hiệu phụ trợ siêu nhẹ** (kiểm tra bất thường cấu trúc mắt hoặc nhắm/mở bất khả thi), tuyệt đối **không** dùng làm bộ quyết định chính.

---

## 2. Bài báo & Hướng tiếp cận SOTA cho Video Call Thời gian thực

### Dual-Stream Spatial + Forensic Noise (MobileNetV2 + SRM)
* **Kho mã nguồn tham khảo:** [shovan-mondal/Deepfake-detection](https://github.com/shovan-mondal/Deepfake-detection)
* **Bài toán & Đóng góp cốt lõi:** Kết hợp hai luồng song song: luồng ảnh RGB qua mạng **MobileNetV2** siêu nhẹ và luồng **bộ lọc nhiễu pháp y SRM (*Steganalysis Rich Model*)** chuyên tách nhiễu tần số cao ở viền ghép khuôn mặt. Mô hình sau khi lượng tử hóa xuất ra tệp **TFLite chỉ khoảng 4.3 MB**, chạy mượt mà trên thiết bị di động.
* **Hạn chế thực nghiệm (*Domain Shift*):** Khi khung hình video bị nén mạnh bởi Zalo/Messenger và trải qua bước chụp màn hình + co giãn kích thước (`MediaProjection`), **phần lớn nhiễu tần số cao mà bộ lọc SRM dựa vào sẽ bị xóa sạch**. Bắt buộc phải thu bộ dữ liệu mẫu trực tiếp qua cuộc gọi Zalo/Messenger thật để đo mức suy giảm (Phase 0 Spike) và fine-tune lại.
* **Ứng dụng vào Realtime Deepfake Shield:** Là bộ phát hiện khung hình thụ động phụ trợ (Engine B1) chạy trên Android Tier 2–3 (`>= 6GB RAM`) hoặc Desktop.

### Audio-Visual Temporal Synchronization (LipForensics & Cross-Modal Attention)
* **Nguồn / Benchmark:** Có mặt trong [SCLBD/DeepfakeBench](https://github.com/SCLBD/DeepfakeBench) và các hội nghị IEEE/ACM 2024–2026.
* **Bài toán & Đóng góp cốt lõi:** Đối chiếu sự đồng bộ theo thời gian giữa âm vị tiếng nói (*phoneme*) và chuyển động khẩu hình (*viseme*) bằng *Cross-Modal Attention* / *Contrastive Sync Loss*.
* **Giới hạn kỹ thuật quan trọng (Cập nhật v2):** Lip-Sync **không bắt được kịch bản face-swap trực tiếp kèm đổi giọng trực tiếp**, vì miệng hiển thị vẫn thừa hưởng chuyển động thật của kẻ gian và bộ chuyển giọng live giữ nguyên nhịp nói. Tuy nhiên, nó **hữu ích để bắt các đoạn video dựng sẵn / lồng tiếng ghép khẩu hình phát lại trong 3–10 giây** — khớp với kịch bản gọi chớp nhoáng phổ biến tại Việt Nam.
* **Ứng dụng vào Realtime Deepfake Shield:** Định vị nhánh **Engine B2** tập trung phát hiện clip dựng sẵn / lồng tiếng trong các cuộc gọi ngắn trên nền tảng có đủ cả luồng hình và tiếng sạch.

### GOTCHA: Real-Time Video Deepfake Detection via Challenge-Response
* **Nguồn / Năm:** arXiv:2210.06186 (2022) — được kế thừa trong các khảo sát 2024–2026.
* **Liên kết:** [https://arxiv.org/abs/2210.06186](https://arxiv.org/abs/2210.06186)
* **Bài toán & Đóng góp cốt lõi:** Đề xuất cơ chế **thử thách – phản hồi (Active Probing / Challenge-Response)** như yêu cầu xoay nghiêng mặt nhanh, đưa tay che ngang mặt (*occlusion*), hoặc đổi biểu cảm đột ngột để gây áp lực lên pipeline sinh khuôn mặt thời gian thực.
* **Giới hạn thực nghiệm (Cập nhật v2):**
  1. Các công cụ phổ biến hiện nay như **Deep-Live-Cam** và **FaceFusion** đã tích hợp mặt nạ che khuất (*occlusion mask* / *mouth mask* dùng MediaPipe hoặc CelebAMask-HQ) để tách bàn tay đặt chồng lên mặt ghép, khiến phép thử vẫy tay **không còn là đòn đánh chí mạng tuyệt đối**.
  2. Bắt một người cao tuổi đang trong trạng thái hoảng loạn phải tự điều khiển bài kiểm tra kỹ thuật là **quá tải nhận thức**.
* **Ứng dụng vào Realtime Deepfake Shield:** Hạ bậc thành **tín hiệu tùy chọn phụ trợ (Engine B4)**; thay tuyến phòng thủ chính bằng **Xác minh Ngoài kênh** (*Mật khẩu gia đình + Tạm dừng, gọi lại số đã lưu*).

### Detection of Real-time DeepFakes in Video Conferencing with Active Probing and Corneal Reflection
* **Nguồn / Năm:** arXiv:2210.14153 (2022)
* **Liên kết:** [https://arxiv.org/abs/2210.14153](https://arxiv.org/abs/2210.14153)
* **Bài toán & Đóng góp cốt lõi:** Kết hợp thử thách chủ động với phân tích **phản xạ giác mạc (Corneal Reflection)** — phát hiện ánh sáng đổi màu trên màn hình không phản chiếu đồng nhất trên mắt của ảnh/video giả.
* **Hạn chế thực nghiệm:** Yêu cầu độ phân giải vùng mắt tương đối cao; dễ mất tín hiệu khi gọi video qua mạng 3G/4G bị nén mạnh.

### rPPG (Remote Photoplethysmography) — Phát hiện Nhịp mạch Sinh học
* **Nguồn / Năm:** Nguyên lý cốt lõi của **Intel FakeCatcher**; nghiên cứu mở mới nhất: *"Do deepfakes have a heartbeat? Detecting deepfake videos using remote photoplethysmography"* (Viện Pháp y Hà Lan - NFI, *Forensic Science International: Reports*, 2026).
* **Bài toán & Đóng góp cốt lõi:** Trích xuất biến thiên màu sắc RGB cực nhỏ do máu lưu thông dưới da vùng trán và hai bên má (tạo thành sóng mạch BVP - *Blood Volume Pulse*). Video deepfake thường không tái tạo được nhịp tim sinh học nhất quán trên các vùng da.
* **Hạn chế thực nghiệm:** Rất nhạy cảm với thuật toán nén video bitrate thấp (Zalo/Messenger) và ánh sáng yếu trong phòng người lớn tuổi. Phù hợp làm tín hiệu bổ trợ khi video đạt chất lượng HD/ổn định trên Desktop.

---

## 3. Kho Mã Nguồn GitHub Tham Khảo

| Kho mã nguồn (GitHub) | Ngôn ngữ / Stack | Mục đích tham khảo cho dự án |
| :--- | :--- | :--- |
| [SCLBD/DeepfakeBench](https://github.com/SCLBD/DeepfakeBench) | PyTorch | Bộ nền tảng benchmark chuẩn hóa để đánh giá và so sánh hàng chục detector SOTA |
| [shovan-mondal/Deepfake-detection](https://github.com/shovan-mondal/Deepfake-detection) | TensorFlow / TFLite (~4.3MB) | Mô hình nhẹ 2 nhánh `MobileNetV2 + SRM` rất phù hợp cho Edge/Android |
| [sreenathyadavk/HiddenLayer](https://github.com/sreenathyadavk/HiddenLayer) | Android Kotlin, Jetpack Compose, TFLite, CameraX/MediaProjection | Kiến trúc tham chiếu app Android chạy phát hiện deepfake hoàn toàn offline |
| [adit9852/Deepfake-Detector](https://github.com/adit9852/Deepfake-Detector) | Python / Android, EfficientNetV2, RawNet, ONNX | Tham khảo kiến trúc đa phương thức kết hợp hình ảnh + âm thanh xuất ONNX |
| [NetherlandsForensicInstitute/rppg-deepfake-detection](https://github.com/NetherlandsForensicInstitute/rppg-deepfake-detection) | Python, rPPG, LSTM | Pipeline mã nguồn mở từ Viện Pháp y Hà Lan (2026) |
| [AI-Advanced-Vision-Forensics-Lab/rPPG-TalkingFace-Detector](https://github.com/AI-Advanced-Vision-Forensics-Lab/rPPG-TalkingFace-Detector) | RhythmFormer + 1D Classifier | Tham khảo phát hiện talking-face qua tín hiệu nhịp mạch |
| [arifdag/rppg-deepfake-detector](https://github.com/arifdag/rppg-deepfake-detector) | EfficientNet + POS rPPG + 3D CNN/Transformer | Tham khảo cách hợp nhất đặc trưng không gian và sinh lý học |
| [olekacak/Face-Recognition](https://github.com/olekacak/Face-Recognition) | Python, OpenCV, MediaPipe | Kiểm tra liveness kết hợp blink, biểu cảm và LBP texture |
| [Pushtogithub23/Eye-Blink-Detection-using-MediaPipe-and-OpenCV](https://github.com/Pushtogithub23/Eye-Blink-Detection-using-MediaPipe-and-OpenCV) | Python, MediaPipe FaceMesh, OpenCV | Đo chỉ số EAR thời gian thực từ 468 điểm mốc khuôn mặt |
| [shakirsadiq6/Blink_Detection_Python](https://github.com/shakirsadiq6/Blink_Detection_Python) | OpenCV, MediaPipe FaceMesh | Đếm nhịp chớp mắt cơ bản trên luồng video |
| [SakshiAher-Codes/Detection-of-Face-Swap-based-Deep-Fake-Videos](https://github.com/SakshiAher-Codes/Detection-of-Face-Swap-based-Deep-Fake-Videos) | Python, CNN-LSTM, OpenCV | Tham khảo mô hình chuỗi thời gian CNN-LSTM trên khung hình mặt |

---

## 4. Kết luận Lựa chọn Công nghệ cho Dự án (Cập nhật v2)

Kiến trúc **Engine B (Video)** đóng vai trò **nguồn bằng chứng bổ trợ có điều kiện** (không làm điểm tựa duy nhất), được hiệu chỉnh theo đúng kịch bản lừa đảo thực tế tại Việt Nam:

1. **Tầng Tiền xử lý (MediaPipe BlazeFace + Face Mesh):** Chạy ở tần suất thích ứng `2–5 FPS` trên Android Tier 2–3 (`>= 6GB RAM`) hoặc Desktop, cắt vùng mặt (ROI `224x224`) kèm kiểm soát nhiệt độ/FPS để không làm giật cuộc gọi Zalo.
2. **Tín hiệu Hành vi Cuộc gọi Ngắn & Mờ (`ShortGlitchyCall`):** Thay vì bỏ qua nhánh video khi chất lượng kém, tổ hợp *tài khoản lạ + cuộc gọi `< 15 giây` + hình mờ/giật + cúp máy đột ngột* được chuyển thành tín hiệu **tăng rủi ro** mở Phiên nghi vấn xuyên kênh.
3. **Nhánh Thụ động có Fine-tune Thực địa:**
   * **Engine B1 (`MobileNetV2 + SRM`):** Fine-tune trên dữ liệu chụp màn hình thật qua Zalo/Messenger để bù suy hao nén.
   * **Engine B2 (`Clip-Targeted Lip-Sync`):** Tập trung phát hiện đoạn video dựng sẵn / ghép khẩu hình phát lại trong vài giây đầu.
4. **Phòng tuyến chính là Xác minh Ngoài kênh:** *Mật khẩu gia đình + Tạm dừng, gọi lại số đã lưu*; *Active Probing* (vẫy tay ngang mặt) chỉ giữ lại ở mức gợi ý tùy chọn phụ trợ.
