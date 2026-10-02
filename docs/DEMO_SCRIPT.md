# Kịch Bản Demo Trực Tiếp 3 Phút (3-Minute Live Demo Script)

## Dự Án: TMA Enterprise Voice Agent — Full-Duplex Speech-to-Speech PoC

> **Thời lượng chuẩn:** Đúng 3 phút 00 giây  
> **Người thực hiện:** Trình diễn viên (Presenter) & Người vận hành kỹ thuật (Technical Operator)  
> **Mục tiêu:** Thuyết phục hội đồng thẩm định TMA Solutions về tốc độ phản hồi siêu nhanh (< 500ms), độ tự nhiên tiếng Việt, khả năng ngắt lời tức thời (Barge-in < 50ms) và gọi công cụ doanh nghiệp thời gian thực.  
> **Địa chỉ demo:** `http://localhost:8000/web`

---

## Bảng Phân Bổ Thời Lượng & Mục Tiêu Trình Diễn

```
0:00 ──────── 0:30 ───────────────── 1:30 ───────────── 2:15 ────────────── 3:00 (Phút)
  │ MÀN 1: MỞ ĐẦU     │ MÀN 2: ĐỐI ĐÁP TIẾNG VIỆT │ MÀN 3: BARGE-IN │ MÀN 4: TOOLING & EXPORT │
  │ Giới thiệu & HUD  │ Tốc độ TTFA P50 ~406ms    │ Chen ngang cướp lời│ Gọi hàm & Xuất WAV     │
```

| Màn | Thời gian | Nội dung trình diễn | Chỉ số kỹ thuật cần đạt (KPI) |
| :---: | :---: | :--- | :--- |
| **Màn 1** | **0:00 - 0:30** | Mở đầu, khởi động Web Studio & Giới thiệu Kiến trúc Native S2S | Kết nối WebSocket `/ws/live`, Visualizer hoạt động |
| **Màn 2** | **0:30 - 1:30** | Đàm thoại tiếng Việt tự nhiên & Quan sát Telemetry Latency HUD | TTFA: ~400ms, Phát âm tự nhiên, chuẩn dấu thanh |
| **Màn 3** | **1:30 - 2:15** | Kiểm thử ngắt lời chen ngang tức thì (Barge-in Interruption) | Loa client im bặt < 50ms, triệt tiêu audio queue |
| **Màn 4** | **2:15 - 3:00** | Ra lệnh thoại gọi Tool (Giờ & Phòng họp) + Tải file ghi âm WAV | Badge tool hiện ~15ms, xuất tệp WAV 16kHz tải về |

---

## Chuẩn Bị Trước Giờ G (Pre-Demo Checklist - 2 phút trước khi bắt đầu)

1. **Khởi chạy Server:**
   ```bash
   cd /home/intern-tdkhuong/Desktop/Voice_Agent_TMA
   ./scripts/start_server.sh
   ```
2. **Kiểm tra trình duyệt:** Mở Chrome/Edge tại `http://localhost:8000/web`.
3. **Cấu hình âm thanh:** Đặt âm lượng loa máy tính ở mức 70%. Đảm bảo micro đã được cấp quyền truy cập.
4. **Kiểm tra trạng thái:** Đảm bảo thanh trạng thái ghi nhận: `Transport: Connected` hoặc `Ready`.

---

## Chi Tiết Kịch Bản Từng Giây

### 🎬 MÀN 1: MỞ ĐẦU VÀ GIỚI THIỆU KIẾN TRÚC (0:00 - 0:30)

* **0:00 - 0:15 (Lời thoại dẫn dắt):**
  > *"Kính chào quý anh chị hội đồng thẩm định TMA Solutions. Hôm nay, đội ngũ R&D xin trân trọng giới thiệu PoC Trợ lý Giọng nói Doanh nghiệp Song công Toàn phần - Full-Duplex Voice Agent. Hệ thống hoàn toàn không sử dụng mô hình tuần tự ASR-LLM-TTS truyền thống vốn mất từ 2 đến 3 giây độ trễ, mà chạy trực tiếp trên mô hình âm thanh gốc Gemini Multimodal Live API kết hợp Google ADK."*

* **0:15 - 0:30 (Thao tác màn hình):**
  * Presenter click vào nút **`Start Call`** (màu xanh). Nút chuyển sang trạng thái kết nối thành công.
  * Chỉ chuột vào thanh **Live PCM 16kHz Spectrum Visualizer** và màn hình **Real-time Latency & Barge-in Monitor (HUD)**:
  > *"Như anh chị thấy trên màn hình Studio, hệ thống đã thiết lập kết nối WebSocket nhị phân trực tiếp 16kHz PCM. Màn hình HUD phía dưới sẽ đo lường minh bạch từng mili-giây độ trễ cho mỗi lượt nói."*

---

### 🎬 MÀN 2: ĐÀM THOẠI TIẾNG VIỆT TỰ NHIÊN & ĐO ĐỘ TRỄ (0:30 - 1:30)

* **0:30 - 0:45 (Lượt nói 1 - Chào hỏi và giới thiệu):**
  * **Presenter nói vào mic:**
    > *"Xin chào bạn! Bạn có thể giới thiệu ngắn gọn về thế mạnh của TMA Solutions được không?"*
  * **Hành vi hệ thống:**
    * Sóng âm dao động trên Visualizer.
    * Giao diện Live Transcript hiện ngay chữ của User.
    * Trong vòng **~400ms**, Trợ lý AI cất giọng phản hồi qua loa.
  * **Trợ lý AI trả lời (giọng ấm, rõ ràng):**
    > *"Dạ xin chào anh! TMA Solutions là tập đoàn công nghệ hàng đầu Việt Nam với hơn 26 năm kinh nghiệm, cung cấp các giải pháp phần mềm chuyên sâu cho khách hàng tại 30 quốc gia trong các lĩnh vực Viễn thông, Tài chính và Trí tuệ Nhân tạo ạ!"*
  * **Presenter chỉ vào HUD:**
    > *"Anh chị có thể thấy trên màn hình: Server TTFA chỉ mất đúng 412ms, và tổng thời gian E2E chưa tới nửa giây. Âm điệu tiếng Việt hoàn toàn tự nhiên, chuẩn dấu hỏi ngã và phát âm chính xác tên riêng TMA Solutions."*

* **0:45 - 1:15 (Lượt nói 2 - Câu hỏi tình huống kỹ thuật):**
  * **Presenter hỏi:**
    > *"Hệ thống Full-Duplex này mang lại lợi ích gì khác biệt so với các chatbot thoại thông thường?"*
  * **Trợ lý AI trả lời:**
    > *"Dạ, điểm khác biệt lớn nhất là khả năng song công hai chiều: em có thể vừa nghe vừa nói đồng thời, loại bỏ cảm giác chờ đợi như dùng bộ đàm, và đặc biệt anh có thể ngắt lời em bất kỳ lúc nào nếu em nói dài dòng ạ!"*

* **1:15 - 1:30 (Chuyển tiếp tự nhiên sang Màn 3):**
  * Presenter cười thân thiện và hướng về phía hội đồng:
  > *"Và sau đây, tôi xin thử nghiệm ngay tính năng ngắt lời cướp mic - một trong những bài toán hóc búa nhất của công nghệ Voice AI."*

---

### 🎬 MÀN 3: THỬ NGHIỆM NGẮT LỜI CHEN NGANG (BARGE-IN CUTOFF) (1:30 - 2:15)

* **1:30 - 1:45 (Tạo tình huống để AI nói một câu rất dài):**
  * **Presenter nói vào mic:**
    > *"Bạn hãy kể chi tiết cho tôi nghe về lịch sử phát triển của ngành trí tuệ nhân tạo từ năm 1950 đến nay."*
  * **Trợ lý AI bắt đầu thao thao bất tuyệt:**
    > *"Dạ vâng! Lịch sử AI bắt đầu từ mùa hè năm 1956 tại hội nghị Dartmouth College huyền thoại, nơi thuật ngữ Artificial Intelligence lần đầu tiên được John McCarthy đặt tên. Sau đó, vào những năm 1960..."*

* **1:45 - 1:55 (Hành động cướp lời quyết liệt):**
  * **Presenter lập tức nói lớn chen ngang:**
    > *"Đợi một chút, dừng lại đi! Đừng kể lịch sử nữa, hãy chuyển sang việc khác!"*
  * **Hành vi hệ thống (Quan sát trực tiếp):**
    * **Loa ngoài ngắt tiếng ngay tức khắc!** Không có bất kỳ âm thanh dư thừa nào bị phát tiếp.
    * Ô **Barge-in Reaction** trên màn hình HUD nhảy số: **`42 ms`** (Target < 250ms hiển thị màu xanh lá cây).
    * Hàng đợi âm thanh phía client được dọn sạch hoàn toàn qua hàm `reset_audio_queue()`.
  
* **1:55 - 2:15 (Giải thích kỹ thuật):**
  * **Trợ lý AI ngoan ngoãn đáp:**
    > *"Dạ em xin lỗi ạ! Em đã dừng lại rồi, anh cần em hỗ trợ việc gì tiếp theo ạ?"*
  * **Presenter nhấn mạnh:**
    > *"Như quý anh chị vừa chứng kiến, chỉ mất chưa đầy 50ms kể từ khi tôi cất giọng, bộ đệm âm thanh của loa đã bị triệt tiêu hoàn toàn. Đặc biệt, tôi đang sử dụng trực tiếp loa ngoài của laptop mà hệ thống không hề bị vọng âm hay tự ngắt sai, nhờ vào bộ lọc bảo vệ GraceGuard độc quyền mà đội ngũ đã phát triển."*

---

### 🎬 MÀN 4: GỌI CÔNG CỤ THỜI GIAN THỰC & XUẤT TỆP GHI ÂM (2:15 - 3:00)

* **2:15 - 2:25 (Bật tính năng Ghi âm phiên thoại):**
  * Presenter click vào nút **`Record Session`** trên giao diện. Nút nhấp nháy chấm đỏ: `Recording...`.
  > *"Tôi vừa bấm ghi âm trực tiếp toàn bộ luồng âm thanh song công cả hai chiều trên trình duyệt."*

* **2:25 - 2:40 (Thử nghiệm Mid-Speech Tooling - Tra cứu giờ):**
  * **Presenter nói vào mic:**
    > *"Bây giờ chính xác là mấy giờ rồi bạn?"*
  * **Hành vi hệ thống:**
    * Huy hiệu **`Tool Activity Badge`** trên khung phụ đề bật sáng nhấp nháy: ⚙️ *"AI đang tra cứu dữ liệu..."*.
    * Hàm `get_current_time()` thực thi trong vòng **9ms**.
  * **Trợ lý AI trả lời chuẩn xác:**
    > *"Dạ, hiện tại đồng hồ hệ thống đang là 15 giờ 22 phút ngày 2 tháng 10 năm 2026 ạ!"*

* **2:40 - 2:50 (Thử nghiệm Mid-Speech Tooling - Đặt phòng họp):**
  * **Presenter hỏi tiếp:**
    > *"Kiểm tra giúp tôi phòng Lab A có đang trống không?"*
  * **Hành vi hệ thống:**
    * Badge hiện gọi `check_meeting_room({"room_name": "Lab A"})`.
  * **Trợ lý AI giải đáp:**
    > *"Dạ, phòng họp Lab A hiện tại đang hoàn toàn trống và sẵn sàng sử dụng ạ!"*

* **2:50 - 3:00 (Kết thúc & Xuất file WAV):**
  * Presenter click nút dừng ghi âm, sau đó nhấn nút biểu tượng tải về **`Export Recording (.wav)`**.
  * Trình duyệt lập tức tải xuống tệp âm thanh định dạng `tma_voice_session_<timestamp>.wav`.
  * **Presenter chốt hạ ấn tượng:**
    > *"Toàn bộ tệp ghi âm 16kHz chuẩn RIFF WAV đã được xuất trực tiếp trên máy khách. Toàn bộ 80/80 test tự động đều đã vượt qua 100%. PoC Voice Agent của TMA Solutions đã sẵn sàng cho giai đoạn thí điểm tiếp theo. Xin trân trọng cảm ơn hội đồng đã lắng nghe!"*

---

## Phương Án Dự Phòng Sự Cố (Contingency Fallback Plans)

| Sự cố bất ngờ | Nguyên nhân có thể | Hành động xử lý ngay lập tức của Presenter |
| :--- | :--- | :--- |
| **Mất kết nối WebSocket** | Rớt mạng hoặc chạm nhầm cáp | Bấm nút **`Reconnect`** (mũi tên xoay vòng) ngay cạnh nút ghi âm. Hệ thống sẽ tự khôi phục trong 1 giây. |
| **Trình duyệt không nhận mic** | Trình duyệt chưa cấp quyền | Click biểu tượng ổ khóa cạnh URL $\rightarrow$ Cho phép Micro $\rightarrow$ F5 tải lại trang. |
| **Bị dội âm khi mở loa quá lớn** | Âm lượng phòng họp vọng mạnh | Giảm âm lượng loa laptop xuống 50% hoặc chuyển sang cắm tai nghe có dây. |
| **Hỏi tiếng Anh thay vì tiếng Việt** | Hội đồng muốn thử ngoại ngữ | Đặt câu hỏi tự nhiên bằng tiếng Anh: *"Can you check the meeting room 101 for me?"*, AI sẽ tự nhận dạng và trả lời tiếng Anh mượt mà. |

---

**© 2026 TMA Solutions — R&D Voice AI Engineering Team.**
