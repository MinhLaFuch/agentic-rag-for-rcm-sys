# Demo UI cho Hệ Gợi ý Sản phẩm LLM Agent

Tài liệu hướng dẫn chạy demo UI với Gradio cho hệ gợi ý sản phẩm bằng LLM agent trên Amazon Reviews 2023.

## Cài đặt

### Cài Gradio

Gradio là thư viện tuỳ chọn cho demo UI. Cài bằng một trong hai cách:

**Cách 1: Cài trực tiếp**
```powershell
pip install gradio
```

**Cách 2: Cài qua pyproject.toml**
```powershell
pip install -e .[demo]
```

### Cài các dependency khác

Nếu chưa cài các dependency chính của project:
```powershell
pip install pyarrow pytest --break-system-packages
```

## Chạy Demo

### Chế độ Mock (không cần dữ liệu/LLM/mạng)

Dùng cho demo khi không có dữ liệu thật, không có mạng, hoặc LLM API key.

```powershell
$env:PYTHONPATH="."
python scripts/run_demo.py --mock
```

Server sẽ chạy tại `http://127.0.0.1:7860` (mặc định). Trình duyệt sẽ tự động mở.

### Chế độ thật (cần dữ liệu và LLM)

**Bước 1: Set LLM API key**
```powershell
$env:LLM_API_KEY="YOUR_API_KEY_HERE"
```

Thay `YOUR_API_KEY_HERE` bằng API key thật của bạn (không chia sẻ hoặc commit).

**Bước 2: Chạy demo**
```powershell
$env:PYTHONPATH="."
python scripts/run_demo.py --tag v1 --domain Video_Games
```

Các tùy chọn thêm:
- `--tag`: Data tag (mặc định: tag từ `run_tag.yaml`)
- `--domain`: Domain để load (có thể lặp lại, mặc định: tất cả)
- `--eval-on`: Split để load dữ liệu (`validation` hoặc `test`, mặc định: `validation`)
- `--host`: Host để chạy server (mặc định: `127.0.0.1`)
- `--port`: Port để chạy server (mặc định: `7860`)

**Ví dụ:**
```powershell
# Chạy với domain Video_Games và Toys_and_Games
python scripts/run_demo.py --tag v1 --domain Video_Games --domain Toys_and_Games

# Chạy với port khác
python scripts/run_demo.py --mock --port 8080
```

## Thời gian khởi động dự kiến

- **Chế độ mock**: < 1 giây (không tải dữ liệu)
- **Chế độ thật**: 
  - Tải corpus ~2.6 triệu item: 30-60 giây
  - Fit ItemKNN: 10-30 giây
  - Tổng cộng: khoảng 1-2 phút (tùy cấu hình máy)

*Lưu ý: Số liệu này được ước lượng, bạn nên đo thực tế trên máy của mình.*

## Kịch bản Demo (5 bước)

Dưới đây là 5 kịch bản demo để kiểm tra từng trạng thái của hệ thống:

### 1. Trạng thái "ok" - Gợi ý thành công

**Yêu cầu:** "Gợi ý 5 sản phẩm tương tự Video_Games::B00EXAMPLE"

**Công tắc:**
- Memory: Off
- Reflect: Off
- Mode: Planner (LLM)

**Kết quả mong đợi:**
- Status: ✅ Thành công
- Có danh sách item gợi ý (tên, domain, giá, rating, store)
- Trace hiển thị plan JSON và các step thực thi

### 2. Trạng thái "ask_user" - Cần thông tin thêm

**Yêu cầu:** "Gợi ý cho tôi sản phẩm hay."

**Công tắc:**
- Memory: Off
- Reflect: Off
- Mode: Planner (LLM)

**Kết quả mong đợi:**
- Status: ❓ Cần thông tin thêm
- Có câu hỏi lại (ví dụ: "Bạn muốn tìm sản phẩm thuộc danh mục nào?")
- Không có item gợi ý

### 3. Trạng thái "no_result" - Không có kết quả

**Yêu cầu:** "Gợi ý sản phẩm với giá âm" (hoặc yêu cầu không hợp lệ khác)

**Công tắc:**
- Memory: Off
- Reflect: Off
- Mode: Planner (LLM)

**Kết quả mong đợi:**
- Status: ⚠️ Không có kết quả
- Thông báo "Không tìm thấy sản phẩm phù hợp"
- Không có item gợi ý

### 4. Trạng thái "tool_error" - Lỗi hệ thống

**Yêu cầu:** (Chỉ có thể demo bằng mock mode)

**Công tắc:** (Mock mode tự xoay vòng qua các trạng thái)

**Cách demo:**
- Chạy với `--mock`
- Gửi request 4 lần liên tiếp
- Request thứ 4 sẽ trả trạng thái "tool_error"

**Kết quả mong đợi:**
- Status: ❌ Lỗi hệ thống
- Có thông báo lỗi rút gọn (không hiển thị stack trace)
- Không có item gợi ý

### 5. Chế độ Type1 (không LLM) - Gợi ý dựa trên lịch sử

**Yêu cầu:** Chọn user mẫu từ danh sách (ví dụ: warm:user123)

**Công tắc:**
- Memory: Off (không dùng)
- Reflect: Off
- Mode: Type1 (no LLM)

**Kết quả mong đợi:**
- Status: ✅ Thành công
- Có danh sách item tương tự với item cuối cùng trong lịch sử user
- Trace: None (Type1Agent không có trace chi tiết)

## Phương án dự phòng khi demo lỗi

### 1. Chuyển sang chế độ mock

Nếu gặp lỗi khi chạy chế độ thật (thiếu dữ liệu, LLM không available, mạng mất):

```powershell
# Dừng server hiện tại (Ctrl+C)
# Chạy lại với --mock
python scripts/run_demo.py --mock
```

Mock mode sẽ:
- Không cần dữ liệu thật
- Không cần LLM
- Không cần mạng
- Trả kết quả mẫu xoay vòng qua 4 trạng thái

### 2. Ảnh chụp màn hình / Video quay trước

**Chuẩn bị trước demo:**
1. Chạy demo với `--mock` để có kết quả ổn định
2. Chụp màn hình từng trạng thái (ok, ask_user, no_result, tool_error)
3. Lưu ảnh vào thư mục `docs/demo_screenshots/`

**Khi demo lỗi:**
- Hiển thị ảnh chụp màn hình/video đã quay
- Giải thích rằng đây là kết quả mong đợi

### 3. Dùng video quay sẵn

Quay video màn hình khi chạy demo thành công:
- Windows: Win+G để bật Game Bar và quay
- Lưu video vào `docs/demo_videos/`

Khi demo lỗi, phát video thay vì chạy live.

## Giới hạn đã biết

### Single-turn demo
- Hệ thống demo chỉ hỗ trợ single-turn (một request, một response)
- Nếu agent trả về `ask_user`, user cần gửi request mới với đầy đủ thông tin
- Không có lịch sử hội thoại giữa các request

### Chạy tuần tự
- UI chỉ xử lý request tuần tự (không xử lý song song)
- Nếu có nhiều user demo cùng lúc, cần queue hoặc chạy server riêng

### Chưa có xác thực
- Demo không có xác thực user
- Không lưu log chứa dữ liệu người dùng ra file ngoài đường dẫn cấu hình
- Không có session management

### Dữ liệu giới hạn
- LiveBackend giới hạn 10,000 item trong corpus để demo nhanh hơn
- Trong production, sẽ load toàn bộ ~2.6 triệu item

### Tầng Inference
- Demo hiện tại dùng adapter từ `PlanExecutor` (tầng agent cũ)
- Khi tầng `package.inference` hoàn thiện, chỉ cần đổi adapter
- Adapter Inference hiện tại là chỗ giữ chỗ (`NotImplementedError`)

## Xử lý lỗi phổ biến

### Lỗi "gradio not installed"
```
ERROR: gradio not installed
Please install with: pip install gradio
```

**Giải pháp:**
```powershell
pip install gradio
```

### Lỗi "LLM health check failed"
```
ERROR: LLM health check failed
```

**Nguyên nhân:**
- `configs/agent/llm.yaml` misconfigured
- `LLM_API_KEY` không được set
- Endpoint LLM không available

**Giải pháp:**
1. Kiểm tra `configs/agent/llm.yaml`
2. Set `LLM_API_KEY`:
   ```powershell
   $env:LLM_API_KEY="YOUR_KEY"
   ```
3. Hoặc chạy với `--mock`:
   ```powershell
   python scripts/run_demo.py --mock
   ```

### Lỗi "LIVEBACKEND INITIALIZATION FAILED"
```
ERROR: LIVEBACKEND INITIALIZATION FAILED
Reason: ...
```

**Nguyên nhân:**
- Dữ liệu chưa được xử lý (thư mục `resource/` không có file)
- Tag hoặc domain không đúng
- Mapping không có format `Domain::asin`

**Giải pháp:**
1. Kiểm tra dữ liệu đã được xử lý (xem `scripts/stage1_clean_domain.py`, `stage2_merge_filter.py`, `stage3_map_split.py`)
2. Kiểm tra tag và domain
3. Chạy với `--mock` để demo không cần dữ liệu

### Lỗi "Mapping has plain item ids"
```
RuntimeError: Mapping has plain item ids; need namespaced 'Domain::asin' ids
```

**Nguyên nhân:**
- Mapping cũ chưa chạy qua stage3 (chưa thêm prefix domain)

**Giải pháp:**
1. Chạy lại stage3: `python scripts/stage3_map_split.py`
2. Hoặc dùng tag có mapping mới

## Tài liệu liên quan

- `inference_contract.md` - Contract cho tầng Inference (khi hoàn thiện)
- `configs/agent/demo.yaml` - Config runtime limits cho demo
- `package/demo/` - Source code demo UI
