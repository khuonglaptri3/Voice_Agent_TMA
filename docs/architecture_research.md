# Kiến Trúc Dự Án Hợp Nhất Cho Hệ Thống Trí Tuệ Nhân Tạo Tác Tử Và Tác Tử Thoại Thời Gian Thực

## Phân Tích Cơ Sở Kiến Trúc Đa Tầng Và Mẫu Hình Tích Hợp Hệ Thống

Sự phát triển nhanh chóng của các mô hình ngôn ngữ lớn (LLM) và mô hình ngôn ngữ nhỏ (SLM) đã thúc đẩy ranh giới của các hệ thống hội thoại tự động vượt ra khỏi phạm vi văn bản truyền thống để tiến tới các giao diện tương tác giọng nói trực tiếp                                                                                        . Các hệ thống chatbot cổ điển phần lớn vận hành theo mô hình yêu cầu - phản hồi tuần tự trên nền giao thức HTTP REST hoặc cơ chế dòng văn bản Server-Sent Events (SSE)                                                                                        . Trong mô hình này, hệ thống ưu tiên chiều sâu suy luận đa chặng thông qua các chuỗi ReAct, phân rã mục tiêu và tự phản biện với dung sai trễ chấp nhận được từ 2 đến 10 giây                                                                                        . Ngược lại, tác tử thoại thời gian thực (Voice Agent) bị giới hạn bởi các tiêu chuẩn khắt khe về mặt âm học và tâm lý học nhận thức, đòi hỏi khoảng thời gian trễ từ khi người dùng dứt lời đến khi âm thanh đầu tiên phát ra (Time to First Audio Frame - TTFA) phải nằm dưới ngưỡng 800 mili-giây để duy trì cảm giác đối thoại tự nhiên của con người                                                                                        .

Sự khác biệt căn bản về ngân sách độ trễ và hình thức dữ liệu dẫn đến sự phân hóa sâu sắc trong kiến trúc xử lý                                                                                        . Voice Agent không thể xử lý dữ liệu theo từng khối văn bản hoàn chỉnh mà bắt buộc phải tổ chức theo mô hình đường ống dòng dữ liệu phân khung (Frame-based Streaming Pipeline) trên nền tảng WebRTC hoặc WebSocket hai chiều                                                                                        . Mỗi khung âm thanh 16kHz PCM nhận được phải trải qua quá trình tiền xử lý tín hiệu âm học (Digital Signal Processing - DSP), phân đoạn giọng nói (Voice Activity Detection - VAD), nhận dạng giọng nói (STT), định tuyến ngữ nghĩa, kích hoạt suy luận LLM theo luồng token, chia tách câu và tổng hợp giọng nói (TTS) chuyển tiếp ngược lại người dùng mà không làm gián đoạn luồng đàm thoại                                                                                        . Hơn nữa, Voice Agent đòi hỏi khả năng xử lý ngắt lời lập tức (Barge-in / Interruption handling): khi người dùng cất lời trong lúc hệ thống đang phát âm thanh, toàn bộ đường ống sinh văn bản và bộ đệm âm thanh phải được thu hồi ngay lập tức để chuyển sang trạng thái lắng nghe                                                                                        .

Để dung hòa hai mô hình này trong một hệ thống phần mềm cấp doanh nghiệp, kiến trúc phần mềm phải áp dụng nghiêm ngặt các nguyên lý Kiến trúc Sạch (Clean Architecture)                                                                                        . Bằng cách tách biệt tuyệt đối giữa tầng nghiệp vụ cốt lõi (Domain Core), tầng điều phối kịch bản (Application Orchestration) và tầng điều hợp hạ tầng kỹ thuật (Infrastructure Adapters), hệ thống có khả năng vận hành song song hai cơ chế: chế độ đàm thoại sâu nhiều bước dành cho Chatbot và chế độ phản hồi siêu trễ thấp cho Voice Agent mà không làm trùng lặp logic nghiệp vụ hay gây phụ thuộc cứng vào bất kỳ nhà cung cấp dịch vụ mô hình nào                                                                                        .

| Tiêu chí kỹ thuật                   | Hệ thống Chatbot Văn bản (Text Agent)                         | Tác tử Thoại Thời gian thực (Voice Agent)                         | Kiến trúc Hợp nhất Đa phương thức                                |
| --------------------------------------- | ----------------------------------------------------------------- | ---------------------------------------------------------------------- | ------------------------------------------------------------------------ |
| **Giao thức mạng chủ đạo**   | HTTP/2, REST, Server-Sent Events, WebSocket                       | WebRTC (RTP/SRTP), SIP, Telephony Media Streams                        | Đa giao thức thích ứng (WebRTC Transport + HTTP/WS Gateway)          |
| **Cấu trúc luồng dữ liệu**   | Khối văn bản tĩnh hoặc chuỗi token văn bản rời rạc      | Dòng khung âm thanh nhị phân (Audio Frames 10-20ms)                | Khung dữ liệu định kiểu (Typed Frames: Audio, Text, Marker, Signal) |
| **Ngân sách trễ mục tiêu**   | 1.500ms – 8.000ms (ưu tiên độ sâu suy luận)                | 400ms – 800ms (ưu tiên thời gian phản hồi âm thanh)             | Phân bổ động theo kênh đầu vào (Voice < 600ms, Chat linh hoạt)  |
| **Cơ chế ngắt tương tác**   | Hủy tác vụ bất đồng bộ phía máy khách (AbortController) | Ngắt VAD thời gian thực, dọn sạch hàng đợi phát âm thanh     | Quản trị vòng đời ngắt tập trung qua tín hiệu điều phối FSM  |
| **Mô hình thực thi công cụ** | JSON Schema Function Calling tiêu chuẩn đa lượt              | Ký hiệu hành động dòng (Streaming Action Markers) / RPC nhẹ     | Bộ điều hợp kép: Streaming Markers cho Voice, MCP cho Agent         |
| **Cơ chế quản lý bộ nhớ**   | Tải toàn bộ lịch sử hội thoại vào cửa sổ ngữ cảnh     | Bộ nhớ phân tầng: Trích xuất thực thể ngầm + Cửa sổ trượt | Phân cấp 5 tầng (Working, Buffer, Episodic, Vector, Graph)            |

   

## Đặc Tả Kỹ Thuật Bảy Phân Tầng Chức Năng Cốt Lõi

Khung kiến trúc hệ thống hợp nhất được thiết kế xoay quanh bảy phân tầng độc lập, giao tiếp với nhau qua các giao diện hợp đồng trừu tượng (Ports and Adapters) nhằm triệt tiêu sự phụ thuộc chéo và cho phép mở rộng linh hoạt                                                                                        .

### Phân Tầng Cổng Kết Nối Và Xử Lý Tín Hiệu Đầu Vào

Tầng cổng kết nối chịu trách nhiệm tiếp nhận, chuyển đổi và kiểm soát mọi luồng tín hiệu từ môi trường bên ngoài trước khi chuyển giao vào hệ thống suy luận                                                                                        . Đối với kênh tương tác âm thanh, hệ thống thiết lập các bộ chuyển đổi giao vận WebRTC chuyên biệt, phối hợp cùng các thư viện thời gian thực để thu nhận dòng âm thanh chuẩn 16kHz PCM đơn kênh                                                                                        .

Quá trình xử lý tín hiệu âm học (Acoustic DSP) bắt đầu bằng bộ triệt tiêu tiếng vọng âm học (AEC), loại bỏ triệt để tín hiệu phát ra từ loa của chính thiết bị lọt trở lại micro                                                                                        . Tín hiệu sau đó được đưa qua bộ lọc nhiễu phổ ứng dụng học sâu nhằm loại bỏ tạp âm nền công nghiệp, tiếng quạt hoặc âm thanh sinh hoạt                                                                                        . Mô hình Silero VAD đánh giá xác suất tiếng người trên từng khung tín hiệu; khi kết hợp với bộ phát hiện điểm dừng lời (Turn Detector), hệ thống đo đạc chính xác ranh giới kết thúc câu thoại của người dùng                                                                                        . Để ngăn chặn hiện tượng kích hoạt sai bởi tiếng thở hoặc âm thanh va đập, tín hiệu âm thanh phải thỏa mãn bộ tiêu chuẩn kiểm định cơ học: thời lượng tối thiểu ≥0,4s, năng lượng căn bậc hai trung bình bình phương (RMS) ≥0,0015, và tỷ lệ khung chứa giọng nói ≥7%                                                                                        .

Âm thanh hợp lệ lập tức được giải mã qua các bộ điều hợp nhận dạng giọng nói (STT Adapters), hỗ trợ chuyển đổi linh hoạt giữa các mô hình tự host như Whisper.cpp CUDA hoặc Parakeet CTC cho tiếng Việt, và các dịch vụ đám mây tốc độ cao như Deepgram Nova                                                                                        . Sau khi văn bản được hình thành, bộ định tuyến ngữ nghĩa (Semantic Router) phân tích các từ khóa và thực thể ban đầu để xác định ý định và ngôn ngữ đàm thoại                                                                                        . Tại chốt chặn cuối cùng của tầng này, mô-đun khử định danh cá nhân (PII Anonymizer) sử dụng các biểu thức chính quy và mô hình nhận diện thực thể để che giấu mã khóa bảo mật, mật khẩu, số điện thoại và tên riêng trước khi ghi nhận vào nhật ký hệ thống                                                                                        . Đồng thời, thuật toán giới hạn tần suất cửa sổ trượt (Sliding Window Rate Limiter) và cơ chế cấp vé truy cập một lần (One-shot Ticket) được áp dụng nhằm bảo vệ các điểm cuối dữ liệu nhạy cảm khỏi nguy cơ bị rà quét bất hợp pháp                                                                                        .

### Phân Tầng Suy Luận Cốt Lõi Và Điều Phối Tiến Trình

Trọng tâm điều khiển của hệ thống nằm ở động cơ suy luận và bộ điều phối tiến trình                                                                                        . Lớp trừu tượng hóa mô hình nền tảng cung cấp một giao diện đồng nhất để tương tác với cả các mô hình cục bộ tối ưu hóa độ trễ thông qua vLLM/llama.cpp lẫn các mô hình đám mây hiệu năng cao                                                                                        .

Để đảm bảo cuộc hội thoại diễn ra kỷ luật và tránh tình trạng mô hình lạc đề, hệ thống áp dụng máy trạng thái tuần hoàn (Cyclic Finite State Machine) để quản trị hai vòng lặp riêng biệt: vòng lặp lượt nói (Turn Loop FSM) và máy trạng thái nghiệp vụ (Dialog FSM)                                                                                        . Vòng lặp lượt nói điều khiển quá trình luân chuyển từ lắng nghe, kích hoạt VAD, tiếp nhận văn bản STT, sinh phản hồi token, phân tách câu cho tới phát âm thanh TTS                                                                                        . Trong khi đó, máy trạng thái nghiệp vụ kiểm soát việc thu thập các trường thông tin trong các quy trình có cấu trúc (chẳng hạn như đăng ký lịch hẹn hoặc đặt phòng họp) theo cơ chế lập kế hoạch đối thoại hai giai đoạn                                                                                        . Thay vì sử dụng chuỗi lập luận ReAct tốn nhiều vòng phản hồi mạng gây trễ âm thanh, hệ thống gom nhóm các trường thông tin còn thiếu để hỏi trong một lượt duy nhất ở giai đoạn đầu, sau đó chuyển sang giai đoạn xác nhận và chốt hành động                                                                                        .

Đặc biệt, tầng này tích hợp vòng lặp tự phản hồi (Reflection Loop) thông qua cơ chế tự đánh giá vòng kín STT (STT Loopback Self-Evaluation)                                                                                        . Âm thanh tổng hợp từ TTS được đưa ngược trở lại bộ giải mã STT; chuỗi văn bản nhận dạng được đối chiếu với văn bản gốc từ LLM bằng giải thuật so khớp chuỗi nhằm phát hiện hiện tượng suy giảm chất lượng âm thanh hoặc phát âm sai từ mượn                                                                                        . Ngoài ra, bộ ngữ cảnh hóa truy vấn ngắn tự động phân tích câu hỏi giản lược của người dùng dựa trên lượt phản hồi trước đó để tái tạo một câu truy vấn đầy đủ ngữ nghĩa cho các bước tiếp theo                                                                                        .

### Phân Tầng Quản Trị Bộ Nhớ Phân Cấp

Một kiến trúc tác tử mạnh mẽ đòi hỏi cơ chế quản trị bộ nhớ đa tầng nhằm duy trì tính liền mạch của ngữ cảnh mà không làm quá tải giới hạn token của mô hình nền tảng                                                                                        . Hệ thống thiết lập cấu trúc bộ nhớ gồm năm phân tầng rõ rệt:

Khối ngữ cảnh làm việc tức thời (Working Context) lưu trữ các thực thể định danh cốt lõi và dữ liệu trạng thái hiện tại của phiên                                                                                        . Cơ chế cập nhật bất đồng bộ (`extract_async`) đóng vai trò sống còn trong việc triệt tiêu độ trễ: một tiến trình chạy ngầm được kích hoạt để gọi mô hình ngôn ngữ bóc tách thực thể ngay khi người dùng nói xong, chạy song song với quá trình phát âm thanh TTS tới tai người nghe, đưa thời gian trễ thực tế đối với người dùng về mức 0 mili-giây                                                                                        . Khối bộ đệm thông điệp (Message Buffer) duy trì một cửa sổ trượt lưu giữ 10 tin nhắn gần nhất (tương ứng với 5 lượt trao đổi đầy đủ), sử dụng giải thuật cắt tỉa theo cặp nguyên tử để bảo toàn cấu trúc luân phiên người dùng - trợ lý                                                                                        .

Khối bộ nhớ tái hiện (Recall Storage) lưu trữ các phiên làm việc trong quá khứ và trạng thái giao dịch dưới dạng nhật ký nối tiếp trên SQLite hoặc cơ sở dữ liệu có cấu trúc thời gian                                                                                        . Khối bộ nhớ ngữ nghĩa vĩnh cửu (Archival Vector Memory) đóng gói toàn bộ kho tri thức chuyên sâu của doanh nghiệp dưới dạng chỉ mục không gian vector (FAISS hoặc Qdrant) phục vụ việc tra cứu mờ các tài liệu dài                                                                                        . Cuối cùng, bộ quản trị cửa sổ ngữ cảnh sắp xếp các thành phần thông tin theo cấu trúc tối ưu: đặt phần System Prompt tĩnh lên đầu để khai thác tính năng lưu đệm tiền tố (Prompt Caching), giúp giảm thiểu chi phí xử lý và cắt giảm thời gian sinh token đầu tiên (TTFT), tiếp nối bởi khối Working Context, các đoạn tài liệu RAG, bộ đệm thông điệp và câu hỏi hiện tại                                                                                        .

### Phân Tầng Tri Thức Và Truy Xuất Chuyên Sâu

Nhằm giải quyết triệt để rủi ro ảo giác và cung cấp câu trả lời có căn cứ xác thực, tầng tri thức triển khai đường ống truy xuất lai (Advanced Hybrid RAG) kết hợp biểu diễn đồ thị (GraphRAG)                                                                                        .

Quá trình truy xuất bắt đầu bằng việc quét đồng thời hai không gian dữ liệu: không gian ngữ nghĩa dày đặc (Dense Vector) sử dụng mô hình nhúng đa ngôn ngữ trên chỉ mục FAISS, và không gian từ khóa thưa thớt (Sparse Keyword) sử dụng thuật toán BM25Okapi                                                                                        . Danh sách kết quả từ hai nguồn được chuẩn hóa và hợp nhất bằng giải thuật Xếp hạng Tương hỗ (Reciprocal Rank Fusion - RRF) theo công thức toán học:

RRF_Score(d)=m∈M∑k+rm(d)1

với hằng số làm mịn k=60, trong đó rm(d) là thứ hạng của tài liệu d trong phương pháp xếp hạng m∈{Dense,Sparse}                                                                                        . Điểm số này tiếp tục được điều chỉnh bằng hệ số khuếch đại ý định (Intent Boost=+0,25) cho các tài liệu thuộc trang chuyên môn đích, và trừ điểm phạt (Penalty=−0,08) đối với các tệp PDF quét thô nhằm ưu tiên nội dung cấu trúc cao                                                                                        .

Các đoạn tài liệu nằm trong nhóm đầu sau bước RRF được đưa qua mô hình Cross-Encoder để tiến hành tái xếp hạng sâu (Reranking)                                                                                        . Cross-Encoder đánh giá trực tiếp mối tương quan đồng thời giữa câu truy vấn và văn bản mục tiêu, khắc phục sự suy giảm thông tin ngữ nghĩa vốn là nhược điểm của các kiến trúc Bi-Encoder truyền thống                                                                                        . Đồng thời, phân tầng này tích hợp mô-đun đồ thị tri thức (GraphRAG) dựa trên KùzuDB hoặc Neo4j                                                                                        . Khi phát hiện các thực thể có mối liên kết phức tạp, động cơ duyệt đồ thị sẽ trích xuất các bộ ba quan hệ (Triplets) trong bán kính hai bước nhảy quanh thực thể, cung cấp cấu trúc ngữ nghĩa liên kết chéo cho các câu hỏi đòi hỏi tư duy suy luận đa chặng                                                                                        .

### Phân Tầng Giao Thức Công Cụ Và Hành Động Ngoại Vi

Khả năng tác động đến môi trường bên ngoài của tác tử được thiết lập dựa trên hai giao thức riêng biệt nhằm thích ứng với các yêu cầu vận hành khác nhau                                                                                        .

Trong môi trường tương tác thoại trực tiếp, việc gọi hàm theo định dạng JSON hai chiều truyền thống tạo ra độ trễ mạng lớn và làm ngắt quãng luồng âm thanh                                                                                        . Để khắc phục, hệ thống triển khai cơ chế ký hiệu hành động dòng (Streaming Action Markers)                                                                                        . Trong quá trình sinh phản hồi, LLM chèn trực tiếp các đoạn mã ngắn có cấu trúc như `BOOKING_SUBMIT: name=... | phone=...` vào luồng token                                                                                        . Trình phân tích ký hiệu sẽ lọc bỏ các chuỗi này trước khi đưa văn bản vào bộ đọc TTS (tránh việc đọc mã lệnh kỹ thuật thành tiếng), đồng thời kích hoạt các tác vụ phi đồng bộ ngầm để gửi yêu cầu đến các API đích                                                                                        .

Đối với các tác vụ trong môi trường Chatbot văn bản hoặc các công cụ phân tích phức tạp, hệ thống tuân thủ toàn diện giao thức bối cảnh mô hình (Model Context Protocol - MCP) do Anthropic chuẩn hóa                                                                                        . Agent đóng vai trò là một MCP Host, duy trì các kết nối Client tới các MCP Server chuyên biệt (quản lý lịch biểu, cơ sở dữ liệu CRM, hệ thống tệp) thông qua cơ chế giao tiếp liên tiến trình (Stdio) hoặc luồng HTTP SSE                                                                                        . Đối với các hành động yêu cầu thực thi mã lệnh tùy biến hoặc truy cập tài nguyên bảo mật cao, hệ thống phân phối tác vụ vào môi trường cô lập MicroVM (Firecracker) hoặc Docker Sandbox có giới hạn tài nguyên nghiêm ngặt nhằm triệt tiêu nguy cơ tấn công leo thang đặc quyền                                                                                        .

### Phân Tầng Kiểm Định An Toàn Và Hàng Rào Bảo Vệ

Tầng kiểm định bảo đảm toàn bộ dữ liệu đầu vào và đầu ra đều thỏa mãn các tiêu chuẩn nghiêm ngặt về an toàn, tính chân thực và sự tương thích phần cứng                                                                                        .

Bộ xác thực ảo giác âm thanh (ASR Hallucination Verifier) là chốt chặn đặc thù cho Voice Agent                                                                                        . Do các mô hình STT như Whisper thường sinh ra các chuỗi văn bản ảo giác (ví dụ: các đoạn phụ đề video lặp đi lặp lại) khi nhận tín hiệu im lặng hoặc tạp âm kéo dài, hệ thống áp dụng danh sách đen các mẫu câu ảo giác kết hợp tính toán tỷ lệ từ vựng duy nhất theo công thức:

Unique_Ratio=∣Tokenstotal∣∣Tokensunique∣

Nếu chuỗi văn bản nhận dạng có Unique_Ratio<0,40 hoặc xuất hiện hiện tượng lặp từ bốn lần liên tiếp, dữ liệu sẽ bị loại bỏ ngay lập tức                                                                                        . Để bảo vệ bộ thu âm khỏi hiện tượng vòng lặp dội âm do chính loa phát ra, hệ thống áp dụng khóa đệm an toàn sau TTS (Post-TTS Grace Guard) với khoảng thời gian khóa micro từ 0,5 đến 1,0 giây sau khi âm thanh kết thúc                                                                                        .

Dữ liệu đầu ra trước khi gửi sang TTS phải đi qua bộ lọc làm sạch văn bản để gỡ bỏ hoàn toàn các định dạng Markdown, ký hiệu code block, và đường dẫn URL thô nhằm bảo đảm phát âm mượt mà                                                                                        . Ngoài ra, bộ kiểm tra ngôn ngữ nghiêm ngặt (Language Strictness Guard) quét qua 30 bảng mã Unicode để xác định tỷ lệ ký tự ngoại lai; nếu mô hình phản hồi sai ngôn ngữ chỉ định, nội dung sẽ bị thay thế bằng một phát ngôn lịch thiệp yêu cầu lặp lại câu hỏi                                                                                        . Mọi dữ liệu trích xuất có cấu trúc gửi sang hệ thống lưu trữ đều phải vượt qua bộ kiểm định cấu trúc Pydantic nghiêm ngặt, đảm bảo tính toàn vẹn của kiểu dữ liệu và định dạng nghiệp vụ                                                                                        .

### Phân Tầng Đo Lường Vận Hành Và Khả Năng Quan Sát

Sự ổn định của một hệ thống trí tuệ nhân tạo quy mô lớn phụ thuộc vào năng lực giám sát và đánh giá liên tục trong quá trình vận hành                                                                                        . Tầng đo lường vận hành tích hợp chuẩn truy vết phân tán OpenTelemetry kết hợp cùng các công cụ giám sát chuyên biệt                                                                                        .

Một bộ đệm vòng (Ring Buffer) an toàn luồng được triển khai để ghi nhận chi tiết độ trễ từng phần nghìn giây của toàn bộ các giai đoạn trong chu trình: từ xử lý DSP, phát hiện VAD, nhận dạng STT, định tuyến ý định, truy xuất RAG, độ trễ token đầu tiên của LLM cho tới dòng âm thanh TTS                                                                                        . Toàn bộ dữ liệu này được cung cấp thông qua API quản trị phục vụ việc hiển thị trên bảng điều khiển vận hành theo thời gian thực                                                                                        .

Hệ thống theo dõi chi phí (Token Cost Accounting) ghi nhận chi tiết mức tiêu thụ token đầu vào, token đầu ra và tỷ lệ trúng bộ đệm tiền tố (Cache Hit Rate) của từng phiên tương tác để giám sát ngân sách hạ tầng                                                                                        . Song song với đó, toàn bộ lịch sử đàm thoại được lưu trữ vào cơ sở dữ liệu kiểm toán có gắn nhãn thời gian                                                                                        . Bộ phân tích độ lệch dữ liệu ngữ âm định kỳ quét nhật ký này để phát hiện hiện tượng nhận dạng sai các từ viết tắt chuyên ngành, từ đó hỗ trợ các kỹ sư cập nhật quy tắc chuẩn hóa văn bản trước khi đưa vào mô hình nhận dạng                                                                                        . Hệ thống kiểm thử tự động sử dụng môi trường mô phỏng hai tác tử (Two-bot Simulation Harness) để chạy các kịch bản đối kháng tự động, liên tục đánh giá khả năng duy trì ngữ cảnh và phản xạ ngắt lời của Voice Agent trong quy trình tích hợp liên tục (CI/CD)                                                                                        .

## Thiết Kế Cấu Trúc Thư Mục Dự Án Hoàn Chỉnh

Cấu trúc cây thư mục dưới đây tích hợp đầy đủ mọi mô-đun của cả Chatbot Agent và Real-time Voice Agent, tuân thủ nguyên lý tách biệt mối quan tâm và cấu trúc tầng sạch                                                                                        :

* `enterprise_agent/` - Thư mục gốc quản trị toàn bộ dự án

  * `.github/` - Tự động hóa tích hợp và phân phối mã nguồn (CI/CD)

    * `workflows/` - Định nghĩa quy trình kiểm thử và triển khai

      * `ci_pipeline.yaml` - Kiểm tra định dạng Ruff, kiểm tra kiểu tĩnh Mypy, và chạy Unit Tests
      * `eval_simulation.yaml` - Chạy kiểm thử tự động mô phỏng đàm thoại hai bot (Two-bot Simulation)
  * `config/` - Cấu hình tập trung toàn hệ thống

    * `__init__.py` - Khởi tạo gói cấu hình
    * `settings.py` - Quản lý biến môi trường an toàn dựa trên Pydantic BaseSettings
    * `models.yaml` - Danh mục cấu hình mô hình LLM, SLM, STT, TTS và Embeddings
    * `audio_params.yaml` - Tham số âm học: tần số 16kHz, kích thước khung, ngưỡng năng lượng VAD
    * `guardrails_rules.yaml` - Bộ quy tắc chặn từ khóa nhạy cảm, ngưỡng lặp từ và ràng buộc ngôn ngữ
    * `logging_config.yaml` - Cấu hình định dạng nhật ký có cấu trúc theo chuẩn JSON
  * `data/` - Quản lý tài nguyên dữ liệu và chỉ mục cục bộ

    * `knowledge_base/` - Kho tài liệu nghiệp vụ phục vụ nạp dữ liệu RAG

      * `raw_documents/` - Tài liệu nguồn chưa qua xử lý (PDF, Markdown, DOCX)
      * `processed/` - Các đoạn văn bản đã được bóc tách và phân mảnh ngữ nghĩa
    * `indices/` - Lưu trữ các tệp chỉ mục tìm kiếm tĩnh

      * `faiss/` - Tệp tin chỉ mục vector `index.faiss` và tệp thuộc tính `meta.json`
      * `bm25/` - Dữ liệu tần suất từ khóa BM25 đã tuần tự hóa
      * `graph/` - Cơ sở dữ liệu đồ thị cục bộ nhúng (KùzuDB database storage)
    * `storage/` - Lưu trữ trạng thái phiên và kiểm toán vận hành

      * `conversations.db` - SQLite lưu trữ phiên, người dùng và nhật ký hội thoại
      * `bookings_audit.jsonl` - Tệp ghi tuần tự các sự kiện thực thi tác vụ đặt lịch
  * `deploy/` - Cấu hình đóng gói container và triển khai hạ tầng

    * `docker/` - Dockerfiles tối ưu hóa cho các môi trường chạy khác nhau

      * `Dockerfile.voice` - Container chuyên biệt cho Voice Agent Pipeline (hỗ trợ CUDA, WebRTC)
      * `Dockerfile.api` - Container gọn nhẹ phục vụ giao diện REST API và Chatbot văn bản
    * `docker-compose.yaml` - Điều phối hạ tầng cục bộ (Redis, Qdrant, Neo4j, Voice App)
    * `k8s/` - Cấu hình Kubernetes triển khai quy mô lớn kèm HPA theo dõi tải GPU
  * `src/` - Toàn bộ mã nguồn ứng dụng (Clean Architecture)

    * `core/` - Tầng miền nghiệp vụ (Domain Core - Không phụ thuộc công nghệ ngoài)

      * `__init__.py`
      * `entities/` - Định nghĩa các thực thể dữ liệu cốt lõi

        * `message.py` - Cấu trúc thông điệp đa phương thức (`UserMessage`, `AssistantMessage`)
        * `audio_frame.py` - Cấu trúc dữ liệu nhị phân khung âm thanh (`AudioFrame`)
        * `session.py` - Thực thể trạng thái phiên làm việc (`SessionContext`)
        * `user_profile.py` - Thực thể người dùng và các thuộc tính nhận diện cốt lõi
      * `interfaces/` - Cổng giao diện trừu tượng định nghĩa các hợp đồng nghiệp vụ

        * `llm.py` - Hợp đồng trừu tượng cho nhà cung cấp mô hình ngôn ngữ (`BaseLLMProvider`)
        * `stt.py` - Hợp đồng trừu tượng cho bộ nhận dạng tiếng nói (`BaseSTTService`)
        * `tts.py` - Hợp đồng trừu tượng cho bộ tổng hợp giọng nói (`BaseTTSService`)
        * `vad.py` - Hợp đồng trừu tượng cho bộ nhận diện kích hoạt giọng nói (`BaseVADDetector`)
        * `memory.py` - Hợp đồng trừu tượng cho hệ thống lưu trữ bộ nhớ (`BaseMemoryStore`)
        * `retriever.py` - Hợp đồng trừu tượng cho động cơ truy xuất tri thức (`BaseRetriever`)
        * `tool.py` - Hợp đồng trừu tượng cho công cụ thực thi (`BaseTool`)
      * `exceptions.py` - Hệ thống phân cấp các ngoại lệ miền nghiệp vụ chuẩn
      * `constants.py` - Các định số và hằng số kiến trúc sử dụng xuyên suốt
    * `gateway/` - Tầng 1: Cổng giao tiếp và xử lý tín hiệu đầu vào đa phương thức

      * `__init__.py`
      * `transports/` - Lớp giao vận mạng thời gian thực

        * `base.py` - Lớp cơ sở cho các cơ chế giao vận dữ liệu
        * `webrtc_transport.py` - Bộ điều hợp kết nối WebRTC độ trễ cực thấp (LiveKit RTC / FastRTC)
        * `websocket_transport.py` - Giao vận WebSocket hai chiều cho âm thanh và văn bản
        * `fastapi_transport.py` - Giao vận REST API phục vụ Chatbot văn bản truyền thống
      * `audio/` - Đường ống xử lý tín hiệu âm học kỹ thuật số (DSP)

        * `dsp_pipeline.py` - Điều phối tuần tự các bước xử lý âm học
        * `aec.py` - Xử lý triệt tiêu tiếng vọng âm học (Acoustic Echo Cancellation)
        * `noise_filter.py` - Lọc tạp âm nền bằng thuật toán học sâu (RNNoise / DeepFilterNet)
        * `resampler.py` - Chuẩn hóa tần số lấy mẫu về 16.000 Hz đơn kênh
      * `vad/` - Phân đoạn và nhận diện giọng nói

        * `silero_vad.py` - Điều hợp mô hình Silero VAD chạy trên ONNX Runtime
        * `turn_detector.py` - Giải thuật phát hiện điểm kết thúc câu nói dựa trên khoảng lặng
      * `stt/` - Triển khai các bộ điều hợp nhận dạng giọng nói

        * `whisper_cpp_adapter.py` - Tích hợp Whisper.cpp tăng tốc GPU cục bộ
        * `parakeet_adapter.py` - Tích hợp NeMo Parakeet CTC cho tiếng Việt độ trễ thấp
        * `cloud_stt_adapter.py` - Tích hợp các nhà cung cấp STT đám mây (Deepgram, AssemblyAI)
      * `routing/` - Định tuyến ngữ nghĩa đầu vào

        * `semantic_router.py` - Định tuyến ý định dựa trên nhúng vector và phân loại token sớm
        * `language_router.py` - Nhận diện ngôn ngữ tức thời và hoán đổi đường ống xử lý
      * `security/` - An toàn dữ liệu cổng vào

        * `pii_anonymizer.py` - Làm mờ thông tin cá nhân và khóa bí mật trước khi lưu vết
        * `rate_limiter.py` - Giới hạn tần suất cửa sổ trượt và quản lý vé truy cập một lần
    * `orchestration/` - Tầng 2: Động cơ suy luận, điều phối và máy trạng thái

      * `__init__.py`
      * `engine/` - Bộ điều phối chu trình hội thoại

        * `turn_orchestrator.py` - Điều phối chu trình một lượt thoại âm thanh thời gian thực
        * `chat_orchestrator.py` - Điều phối quy trình đàm thoại văn bản đa chặng cho Chatbot
      * `state_machine/` - Quản lý trạng thái và quy trình tương tác

        * `cyclic_turn_fsm.py` - Máy trạng thái hữu hạn kiểm soát các bước trong một lượt nói
        * `dialog_fsm.py` - Máy trạng thái quản lý quy trình nghiệp vụ thu thập dữ liệu nhiều bước
      * `planning/` - Động cơ lập kế hoạch nhiệm vụ

        * `dialogue_planner.py` - Lập kế hoạch đối thoại hai giai đoạn tối ưu trễ cho Voice
        * `react_planner.py` - Động cơ suy luận ReAct / Plan-and-Solve dành cho Text Agent
      * `reflection/` - Vòng lặp tự kiểm tra và điều chỉnh

        * `loopback_evaluator.py` - Đánh giá chất lượng âm học khép kín qua STT Loopback
        * `query_contextualizer.py` - Tái cấu trúc câu hỏi ngắn dựa trên ngữ cảnh lượt trước
    * `memory/` - Tầng 3: Quản trị bộ nhớ phân tầng

      * `__init__.py`
      * `working/` - Bộ nhớ ngữ cảnh làm việc tức thời

        * `session_state.py` - Cấu trúc lưu trữ thực thể và sự thật cốt lõi (`SessionStateMemory`)
        * `async_extractor.py` - Trình trích xuất thực thể chạy ngầm phi đồng bộ khi TTS đang phát
      * `buffer/` - Bộ đệm hội thoại

        * `sliding_window.py` - Cửa sổ trượt lưu giữ 10 thông điệp gần nhất theo cặp nguyên tử
      * `episodic/` - Bộ nhớ sự kiện và lịch sử tương tác

        * `sqlite_store.py` - Lưu trữ lịch sử đàm thoại và sự kiện quá khứ trên SQLite
        * `temporal_graph.py` - Quản lý tính hợp lệ của các sự kiện theo dòng thời gian
      * `archival/` - Bộ nhớ ngữ nghĩa vĩnh cửu

        * `vector_store.py` - Điều hợp lưu trữ vector dài hạn trên FAISS hoặc Qdrant
      * `context/` - Lắp ráp cửa sổ ngữ cảnh cho LLM

        * `context_builder.py` - Định dạng tiền tố tối ưu Prompt Caching và chèn dữ liệu RAG
        * `token_budget.py` - Quản lý giới hạn token và cắt tỉa thông minh
    * `knowledge/` - Tầng 4: Tầng tri thức, RAG nâng cao và GraphRAG

      * `__init__.py`
      * `ingestion/` - Đường ống nạp và xử lý tài liệu ngoại tuyến

        * `document_loader.py` - Trích xuất văn bản từ tài liệu thô đa định dạng
        * `semantic_chunker.py` - Phân mảnh tài liệu theo cấu trúc ngữ nghĩa hoàn chỉnh
        * `embedder.py` - Mã hóa đoạn văn bản thành vector nhúng đa ngôn ngữ
      * `retrieval/` - Động cơ tìm kiếm lai

        * `dense_search.py` - Tìm kiếm tương đồng vector Cosine trên FAISS
        * `sparse_search.py` - Tìm kiếm tần suất từ khóa bằng thuật toán BM25Okapi
        * `hybrid_fusion.py` - Hợp nhất bảng xếp hạng qua Reciprocal Rank Fusion (RRF)
      * `reranking/` - Bộ tái xếp hạng sâu

        * `cross_encoder.py` - Tái chấm điểm top ứng viên bằng mô hình Cross-Encoder
      * `graph/` - Đồ thị tri thức (Knowledge Graph)

        * `graph_store.py` - Trình kết nối cơ sở dữ liệu đồ thị KùzuDB / Neo4j
        * `entity_extractor.py` - Trích xuất các thực thể và mối quan hệ bộ ba
        * `graph_traversal.py` - Truy vấn đa chặng đồ thị tri thức bổ sung ngữ cảnh
    * `tools/` - Tầng 5: Giao thức công cụ, MCP và môi trường thực thi

      * `__init__.py`
      * `markers/` - Cơ chế ký hiệu hành động dòng cho Voice

        * `marker_parser.py` - Nhận diện và bóc tách các ký hiệu hành động trong luồng token
        * `marker_dispatcher.py` - Chuyển tiếp tác vụ bóc tách tới worker chạy ngầm
      * `mcp/` - Chuẩn công nghiệp Model Context Protocol (Anthropic MCP)

        * `client.py` - MCP Client kết nối tới các MCP Server công cụ ngoại vi
        * `server.py` - MCP Server nội bộ phơi bày các năng lực nghiệp vụ của Agent
        * `protocol_types.py` - Định nghĩa cấu trúc thông điệp JSON-RPC chuẩn MCP
      * `internal/` - Các công cụ nghiệp vụ tích hợp sẵn

        * `calendar_tool.py` - Công cụ tra cứu lịch biểu và đặt phòng họp
        * `crm_tool.py` - Công cụ truy xuất và cập nhật hồ sơ khách hàng
      * `sandbox/` - Môi trường cô lập an toàn

        * `container_runner.py` - Thực thi mã lệnh an toàn trong MicroVM hoặc Docker cô lập
    * `guardrails/` - Tầng 6: Hàng rào an toàn và bộ lọc kiểm định

      * `__init__.py`
      * `hallucination/` - Kiểm soát và ngăn chặn ảo giác

        * `speech_hallucination_filter.py` - Lọc câu ảo giác đặc thù của STT và phạt lặp từ
        * `fact_aligner.py` - Đối soát thông tin câu trả lời với tài liệu nguồn RAG
      * `schemas/` - Lớp xác thực cấu trúc Pydantic

        * `booking_schema.py` - Kiểm định dữ liệu đặt lịch hẹn và số điện thoại
        * `entity_schema.py` - Kiểm định dữ liệu trích xuất thực thể người dùng
      * `output_filters/` - Tinh chỉnh nội dung đầu ra

        * `tts_text_cleaner.py` - Gỡ bỏ Markdown và URL chuẩn bị văn bản cho bộ đọc âm thanh
        * `language_strictness_guard.py` - Quét 30 bảng mã Unicode chặn phát ngôn sai thứ tiếng
        * `grace_guard.py` - Quản lý khoảng thời gian trễ khóa micro sau khi dứt lời phát
    * `observability/` - Tầng 7: Khả năng quan sát, đo lường và kiểm toán

      * `__init__.py`
      * `tracing/` - Truy vết phân tán

        * `pipeline_tracer.py` - Ghi nhận thời gian trễ từng chặng vào bộ đệm vòng (Ring Buffer)
        * `otel_instrumentation.py` - Xuất vết thực thi chuẩn OpenTelemetry ra Jaeger/Langfuse
      * `metrics/` - Kế toán chi phí và hiệu năng

        * `cost_tracker.py` - Theo dõi lượng token tiêu thụ và quy đổi chi phí vận hành
        * `latency_collector.py` - Thu thập và tính toán các phân vị độ trễ (P50, P95, P99)
      * `monitoring/` - Giám sát trôi dữ liệu và nhật ký

        * `conversation_logger.py` - Ghi nhận lịch sử tương tác có kiểm toán vào SQLite
        * `phonetic_drift_detector.py` - Phân tích tần suất nghe nhầm ngữ âm ASR định kỳ
    * `serving/` - Tầng giao diện ứng dụng và điểm khởi chạy

      * `__init__.py`
      * `api/` - Các điểm cuối giao tiếp HTTP REST

        * `v1/` - Phiên bản hóa API

          * `chat_routes.py` - Tuyến API cho Chatbot văn bản và luồng SSE streaming
          * `session_routes.py` - Tuyến API quản lý vòng đời phiên làm việc
          * `admin_routes.py` - Tuyến API truy xuất dữ liệu vết giám sát và thống kê
      * `realtime/` - Xử lý phiên tương tác thoại thời gian thực

        * `voice_handler.py` - Tiếp nhận sự kiện WebRTC và điều phối vòng lặp âm thanh
        * `sentence_splitter.py` - Bộ phân tách câu dòng chuyển tiếp văn bản sang TTS
      * `main.py` - Điểm khởi chạy chính của ứng dụng (FastAPI Server / LiveKit Worker)
  * `scripts/` - Kịch bản phụ trợ vận hành và bảo trì

    * `build_knowledge_base.py` - Kịch bản nạp tài liệu, tạo vector và xuất chỉ mục BM25
    * `sync_graph_triplets.py` - Kịch bản trích xuất quan hệ thực thể vào Graph Database
    * `run_benchmark.py` - Kịch bản đo lường chuẩn hóa độ trễ và độ chuẩn xác
  * `tests/` - Bộ kiểm thử tự động toàn diện

    * `conftest.py` - Thiết lập Pytest Fixtures chung và môi trường giả lập
    * `unit/` - Kiểm thử đơn vị logic độc lập

      * `test_dsp_pipeline.py` - Kiểm thử chuỗi lọc nhiễu và chuyển đổi tần số âm thanh
      * `test_vad.py` - Kiểm thử độ nhạy phát hiện giọng nói
      * `test_hybrid_rag.py` - Kiểm thử giải thuật RRF và bộ tái xếp hạng Cross-Encoder
      * `test_guardrails.py` - Kiểm thử bộ lọc ảo giác ASR và bảng mã ngôn ngữ Unicode
    * `integration/` - Kiểm thử tích hợp giữa các thành phần

      * `test_mcp_client.py` - Kiểm thử kết nối và gọi công cụ qua giao thức MCP
      * `test_memory_lifecycle.py` - Kiểm thử trích xuất thực thể ngầm và lưu trữ phân tầng
    * `e2e/` - Kiểm thử toàn trình và kịch bản mô phỏng

      * `test_chat_pipeline.py` - Kiểm thử toàn trình luồng Chatbot văn bản qua REST/SSE
      * `test_voice_turn_loop.py` - Kiểm thử toàn trình một lượt thoại qua WebRTC
      * `test_interruption_barge_in.py` - Kiểm thử khả năng ngắt lời và thu hồi hàng đợi âm thanh
  * `.env.example` - Tệp mẫu khai báo biến môi trường chuẩn
  * `pyproject.toml` - Quản lý cấu hình gói và các thư viện phụ thuộc
  * `README.md` - Hướng dẫn thiết lập môi trường và vận hành hệ thống

| Gói thư mục / Mô-đun   | Tầng kiến trúc   | Vai trò kỹ thuật chính                                                                      | Công nghệ / Gói triển khai          |
| --------------------------- | ------------------- | ----------------------------------------------------------------------------------------------- | --------------------------------------- |
| `src/core/`               | Domain Core         | Định nghĩa thực thể, kiểu dữ liệu chuẩn và các giao diện trừu tượng              | Python dataclasses, ABC, Typing         |
| `src/gateway/audio/`      | Tầng 1: Gateway    | Triệt tiêu tiếng vọng (AEC), lọc nhiễu phổ và chuyển đổi định dạng âm thanh      | SpeexDSP, WebRTC APM, RNNoise           |
| `src/gateway/vad/`        | Tầng 1: Gateway    | Phân đoạn âm thanh có tiếng người và nhận diện ranh giới kết thúc câu nói       | Silero VAD v5 (ONNX Runtime)            |
| `src/gateway/stt/`        | Tầng 1: Gateway    | Nhận dạng âm thanh thành văn bản tối ưu hóa theo ngôn ngữ                            | Whisper.cpp CUDA, NeMo Parakeet         |
| `src/gateway/transports/` | Tầng 1: Gateway    | Duy trì kết nối mạng thời gian thực hai chiều giữa thiết bị và máy chủ             | LiveKit WebRTC SDK, FastAPI WebSockets  |
| `src/orchestration/`      | Tầng 2: Reasoning  | Quản lý máy trạng thái vòng lặp lượt nói, kế hoạch đối thoại và tự đánh giá | Transitions FSM, Asyncio Orchestration  |
| `src/memory/`             | Tầng 3: Memory     | Bộ nhớ phân cấp 5 tầng: Working, Buffer, Episodic, Vector, Caching                         | SQLite, FAISS, In-memory Pydantic       |
| `src/knowledge/`          | Tầng 4: Knowledge  | Truy xuất lai kết hợp Dense-Sparse qua RRF, Cross-Encoder và GraphRAG                       | FAISS, Rank-BM25, KùzuDB, CrossEncoder |
| `src/tools/markers/`      | Tầng 5: Tools      | Bóc tách cờ lệnh hành động từ dòng token văn bản phục vụ Voice                     | Regex Streaming Scanner, Task Queue     |
| `src/tools/mcp/`          | Tầng 5: Tools      | Tương tác máy khách - máy chủ công cụ chuẩn Model Context Protocol                    | Model Context Protocol SDK, JSON-RPC    |
| `src/guardrails/`         | Tầng 6: Guardrails | Chặn ảo giác STT, khóa đệm sau loa, kiểm tra Unicode và xác thực dữ liệu            | Pydantic v2, Regex Script Filter        |
| `src/observability/`      | Tầng 7: Operations | Truy vết phân tán, tính toán chi phí token và giám sát độ trôi ngữ âm             | OpenTelemetry, Prometheus, Langfuse     |
| `src/serving/`            | Application Shell   | Phơi bày các điểm cuối API REST và điều phối luồng âm thanh WebRTC                  | FastAPI, Uvicorn, LiveKit Worker        |

   

## Cơ Chế Điều Phối Đột Phá Và Động Lực Học Luồng Dữ Liệu Thời Gian Thực

Hiệu năng thực tế của một hệ thống hội thoại phụ thuộc vào sự phân định rõ ràng giữa đường dẫn xử lý trực tiếp chịu ràng buộc thời gian nghiêm ngặt (Hot Conversational Path) và đường dẫn xử lý ngầm không gây nghẽn (Cold Background Path)                                                                                        .

Đường dẫn hội thoại trực tiếp của Voice Agent bắt đầu khi các gói tin âm thanh 20ms truyền qua kênh truyền WebRTC UDP đến `WebRTCTransport`                                                                                        . Gói tin lập tức đi qua chuỗi DSP để triệt tiêu tiếng vọng của loa hệ thống và làm sạch tạp âm môi trường                                                                                        . `SileroVAD` tính toán xác suất giọng nói trên từng khung; khi xác suất vượt ngưỡng liên tục trong hơn 400ms và theo sau bởi một khoảng lặng kéo dài trên 500ms, `TurnDetector` xác nhận người dùng đã kết thúc câu thoại                                                                                        . Khối âm thanh này được chuyển tới `WhisperCppSTT` để giải mã thành văn bản trong vòng chưa đầy 150ms                                                                                        . Văn bản nhận dạng lập tức đi qua `ASRHallucinationFilter` để loại bỏ ảo giác lặp từ, sau đó `SemanticRouter` phân loại ý định                                                                                        .

Nếu câu thoại yêu cầu truy vấn tri thức nghiệp vụ, `HybridFusionRetriever` quét đồng thời trên chỉ mục vector FAISS và chỉ mục từ khóa BM25, hợp nhất kết quả bằng thuật toán RRF trong vòng 80ms, tiếp nối bởi mô hình `CrossEncoder` chấm điểm lại top 5 tài liệu trong vòng 50ms                                                                                        . `ContextBuilder` tiến hành ghép nối khối System Prompt cố định đã được lưu đệm sẵn cùng dữ liệu tài liệu và gửi yêu cầu sinh phản hồi dạng dòng tới LLM                                                                                        . Ngay khi LLM sinh ra những token đầu tiên và `SentenceSplitter` phát hiện ranh giới câu hợp lý (dấu phẩy, dấu chấm), đoạn văn bản ngắn này lập tức được gửi sang `BaseTTSService` để tổng hợp thành âm thanh                                                                                        . Gói âm thanh đầu tiên được truyền ngược về loa người dùng qua WebRTC trong khi mô hình ngôn ngữ vẫn đang tiếp tục sinh phần nội dung tiếp theo                                                                                        .

| Giai đoạn xử lý trong đường dẫn                  | Ngân sách trễ tối đa (Target Budget) | Kỹ thuật tối ưu hóa then chốt                                                   |
| -------------------------------------------------------- | ----------------------------------------- | ------------------------------------------------------------------------------------- |
| **Thu nhận âm thanh & Tiền xử lý DSP**        | 30ms – 50ms                              | Xử lý khung trượt 10-20ms trên bộ nhớ đệm chia sẻ C++                       |
| **Nhận diện giọng nói (VAD & STT)**            | 120ms – 200ms                            | Silero VAD lượng tử hóa ONNX, Whisper.cpp chạy CUDA bán chính xác             |
| **Định tuyến & Truy xuất lai RAG**             | 80ms – 150ms                             | Quét FAISS trong bộ nhớ RAM, phân hạng song song qua BM25 và RRF                |
| **LLM Time-to-First-Token (TTFT)**                 | 100ms – 200ms                            | Sử dụng Prompt Caching tiền tố, tối ưu hóa kích thước cửa sổ ngữ cảnh   |
| **Phân tách câu & Khởi tạo âm thanh TTS**    | 80ms – 120ms                             | Cắt câu linh hoạt, dịch chuyển dòng token trực tiếp sang động cơ TTS       |
| **Tổng độ trễ toàn trình (End-to-End TTFA)** | **410ms – 720ms**                  | **Đảm bảo hội thoại tự nhiên theo thời gian thực (< 800ms)** [cite: 6] |

   

Song song với quá trình người dùng lắng nghe máy đọc (thường kéo dài từ 2 đến 6 giây), hệ thống kích hoạt đường dẫn xử lý ngầm hoàn toàn bất đồng bộ                                                                                        . Cặp thông điệp hỏi - đáp vừa phát sinh được đưa vào `SlidingWindowBuffer`                                                                                        . Đồng thời, tiến trình `AsyncEntityExtractor` sử dụng một mô hình ngôn ngữ nhỏ chạy ngầm để bóc tách các dữ liệu nhân thân (họ tên, thời gian cuộc hẹn, dịch vụ quan tâm) và cập nhật trực tiếp vào đối tượng `SessionStateMemory`                                                                                        . Toàn bộ dữ liệu trích xuất được xác thực bởi `PydanticSchemaValidator` trước khi ghi lưu vào cơ sở dữ liệu `conversations.db`                                                                                        . Do việc trích xuất và cập nhật này diễn ra trong lúc tai người nghe đang bận tiếp nhận âm thanh, thời gian trễ của bước xử lý tri thức chuyên sâu này hoàn toàn vô hình đối với người dùng                                                                                        .

Trong trường hợp người dùng chủ động cất lời ngắt quãng (Barge-in) khi hệ thống đang phát âm thanh, `SileroVAD` trên kênh thu âm phát hiện năng lượng tiếng người mới có thời lượng vượt quá 200ms                                                                                        . Hệ thống lập tức kích hoạt sự kiện ngắt lời, phát tín hiệu hủy bỏ tác vụ bất đồng bộ (Cancellation Token) tới LLM để ngừng sinh token, đồng thời gửi chỉ thị tới bộ điều khiển WebRTC yêu cầu xả sạch toàn bộ hàng đợi gói tin âm thanh chưa kịp phát trên thiết bị đầu cuối                                                                                        . Hệ thống thiết lập lại trạng thái của máy trạng thái tuần hoàn về `LISTENING`, sẵn sàng tiếp nhận lượt thoại mới một cách liền mạch mà không để lại bất kỳ dữ liệu rác nào trong bộ nhớ đệm                                                                                        .

## Ma Trận Ánh Xạ Thành Phần Hệ Thống Và Khuyến Nghị Triển Khai

Bảng ma trận kỹ thuật dưới đây tổng hợp mối liên kết trực tiếp giữa các thành phần kiến trúc lý thuyết, tệp mã nguồn tương ứng trong dự án và các thư viện hạ tầng được chỉ định thực thi:

| Phân tầng lý thuyết | Thành phần chức năng                     | Vị trí tệp tin trong cấu trúc dự án                      | Lớp / Hàm xử lý chính    | Thư viện & Công nghệ lựa chọn     |
| ----------------------- | -------------------------------------------- | --------------------------------------------------------------- | ----------------------------- | --------------------------------------- |
| **1. Gateway**    | Giao vận WebRTC thời gian thực            | `src/gateway/transports/webrtc_transport.py`                  | `WebRTCTransport`           | LiveKit Agents RTC / FastRTC / aiortc   |
|                         | Triệt tiêu tiếng vọng âm học (AEC)     | `src/gateway/audio/aec.py`                                    | `AcousticEchoCanceller`     | WebRTC AudioProcessingModule (APM)      |
|                         | Lọc nhiễu âm thanh học sâu              | `src/gateway/audio/noise_filter.py`                           | `NeuralNoiseFilter`         | RNNoise / DeepFilterNet3                |
|                         | Phân đoạn kích hoạt tiếng người      | `src/gateway/vad/silero_vad.py`                               | `SileroVADDetector`         | Silero VAD v5 (ONNX Runtime Execution)  |
|                         | Nhận diện giọng nói STT đa ngữ         | `src/gateway/stt/whisper_cpp_adapter.py`                      | `WhisperCppSTT`             | Whisper.cpp (CUDA C++ Bindings)         |
|                         | Định tuyến ý định ngữ nghĩa sớm     | `src/gateway/routing/semantic_router.py`                      | `SemanticRouter`            | MiniLM Cosine Router + Intent Regex     |
|                         | Khử thông tin định danh (PII)            | `src/gateway/security/pii_anonymizer.py`                      | `PIIAnonymizer`             | Microsoft Presidio / Regex Redaction    |
|                         | Giới hạn tần suất cửa sổ trượt       | `src/gateway/security/rate_limiter.py`                        | `SlidingWindowLimiter`      | In-memory Sliding Window / Redis        |
| **2. Reasoning**  | Trừu tượng hóa mô hình nền tảng      | `src/core/interfaces/llm.py`                                  | `BaseLLMProvider`           | OpenAI API / vLLM (Qwen/Gemma)          |
|                         | Máy trạng thái tuần hoàn lượt nói    | `src/orchestration/state_machine/cyclic_turn_fsm.py`          | `CyclicTurnFSM`             | Asyncio FSM State Controller            |
|                         | Kế hoạch đối thoại hai giai đoạn      | `src/orchestration/planning/dialogue_planner.py`              | `TwoPhaseDialogPlanner`     | 2-Phase Field Collection Dialog Pattern |
|                         | Tự đánh giá khép kín STT Loopback      | `src/orchestration/reflection/loopback_evaluator.py`          | `LoopbackEvaluator`         | Levenshtein Distance / SequenceMatcher  |
| **3. Memory**     | Ngữ cảnh làm việc cốt lõi              | `src/memory/working/session_state.py`                         | `SessionStateMemory`        | Pydantic Dataclass In-memory State      |
|                         | Trích xuất thực thể phi đồng bộ       | `src/memory/working/async_extractor.py`                       | `AsyncEntityExtractor`      | Background Asyncio Task Worker          |
|                         | Cửa sổ trượt bộ đệm thông điệp     | `src/memory/buffer/sliding_window.py`                         | `SlidingWindowBuffer`       | Atomic-pair Rolling Message Queue       |
|                         | Lưu trữ sự kiện và lịch sử phiên     | `src/memory/episodic/sqlite_store.py`                         | `SQLiteEpisodicStore`       | SQLite3 với chỉ mục thời gian       |
|                         | Chỉ mục tri thức vector vĩnh cửu        | `src/memory/archival/vector_store.py`                         | `VectorStoreAdapter`        | FAISS (IndexFlatIP) / Qdrant            |
|                         | Tối ưu hóa tiền tố Prompt Cache         | `src/memory/context/context_builder.py`                       | `ContextBuilder`            | Static Prefix Caching Layout            |
| **4. Knowledge**  | Hợp nhất truy xuất lai RRF                | `src/knowledge/retrieval/hybrid_fusion.py`                    | `HybridFusionRetriever`     | Reciprocal Rank Fusion (k=60)           |
|                         | Tìm kiếm từ khóa truyền thống          | `src/knowledge/retrieval/sparse_search.py`                    | `BM25Retriever`             | Rank-BM25 (BM25Okapi)                   |
|                         | Tái xếp hạng sâu Cross-Encoder           | `src/knowledge/reranking/cross_encoder.py`                    | `CrossEncoderReranker`      | sentence-transformers CrossEncoder      |
|                         | Duyệt đồ thị tri thức đa chặng        | `src/knowledge/graph/graph_traversal.py`                      | `GraphTraversalEngine`      | KùzuDB Embedded Graph Database         |
| **5. Tools**      | Quét cờ hành động trực tiếp           | `src/tools/markers/marker_parser.py`                          | `ActionMarkerParser`        | Regex Streaming Token Scanner           |
|                         | Máy khách Model Context Protocol           | `src/tools/mcp/client.py`                                     | `MCPClientManager`          | MCP Official Python SDK (Stdio/SSE)     |
|                         | Máy chủ cung cấp công cụ MCP            | `src/tools/mcp/server.py`                                     | `MCPServerEndpoint`         | FastMCP Server Implementation           |
|                         | Hộp cát thực thi cách ly an toàn        | `src/tools/sandbox/container_runner.py`                       | `ContainerSandbox`          | Docker SDK / Firecracker MicroVM        |
| **6. Guardrails** | Bộ lọc ảo giác nhận dạng ASR           | `src/guardrails/hallucination/speech_hallucination_filter.py` | `ASRHallucinationFilter`    | Vocabulary Unique Ratio Checker         |
|                         | Khóa bảo vệ dội âm sau khi phát        | `src/guardrails/output_filters/grace_guard.py`                | `GraceGuardManager`         | Lockout Timing Window (0.5s - 1.0s)     |
|                         | Xác thực lược đồ dữ liệu nghiệp vụ | `src/guardrails/schemas/booking_schema.py`                    | `VisitorBookingSchema`      | Pydantic v2 Core Validation             |
|                         | Bộ lọc thứ tiếng Unicode                 | `src/guardrails/output_filters/language_strictness_guard.py`  | `LanguageStrictnessGuard`   | Unicode Script Property Analysis        |
|                         | Làm sạch văn bản cho bộ đọc âm       | `src/guardrails/output_filters/tts_text_cleaner.py`           | `TTSTextCleaner`            | Regex Markdown/URL Stripper             |
| **7. Operations** | Ghi vết độ trễ phân đoạn vòng        | `src/observability/tracing/pipeline_tracer.py`                | `PipelineTracer`            | Thread-safe Circular Ring Buffer        |
|                         | Xuất vết chuẩn OpenTelemetry              | `src/observability/tracing/otel_instrumentation.py`           | `OTelManager`               | OpenTelemetry Tracing SDK               |
|                         | Theo dõi chi phí và số lượng token     | `src/observability/metrics/cost_tracker.py`                   | `TokenCostAccounting`       | Pricing Matrix Token Accounting         |
|                         | Giám sát độ trôi nhận dạng âm vị    | `src/observability/monitoring/phonetic_drift_detector.py`     | `PhoneticDriftDetector`     | SQLite Audit Logs Aggregator            |
|                         | Kịch bản mô phỏng kiểm thử hai bot     | `tests/e2e/test_voice_turn_loop.py`                           | `VoiceAgentSimulationSuite` | Pytest Audio Mock Environment           |

   

Kiến trúc hợp nhất này cung cấp một nền tảng vững chắc để chuyển giao các giải pháp trí tuệ nhân tạo từ giai đoạn thử nghiệm sang vận hành thực tế ở quy mô lớn                                                                                        . Bằng việc cô lập hoàn toàn các ràng buộc kỹ thuật của kênh truyền âm thanh (WebRTC, DSP, VAD) vào tầng Gateway, logic nghiệp vụ của hệ thống được bảo toàn tính toàn vẹn và có thể tái sử dụng tối đa cho cả hai hình thái Chatbot văn bản và Voice Agent tương tác trực tiếp                                                                                        .

Để đảm bảo hiệu quả khi bắt đầu hiện thực hóa kiến trúc trên, các nhóm kỹ sư nên ưu tiên xây dựng hoàn thiện tầng cốt lõi miền nghiệp vụ (`src/core/`) và máy trạng thái vòng lặp lượt nói cơ bản trước                                                                                        . Sau khi các chỉ số về độ trễ âm thanh toàn trình (TTFA < 800ms) và khả năng xử lý ngắt lời được kiểm chứng thành công trong môi trường kiểm thử mô phỏng hai tác tử, việc mở rộng thêm các năng lực chuyên sâu như GraphRAG hay giao thức Model Context Protocol có thể được tiến hành tuần tự mà không làm ảnh hưởng đến tính ổn định của hệ thống đang vận hành                                                                                        .
