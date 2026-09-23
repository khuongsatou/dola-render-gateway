# Hướng dẫn Cài đặt & Sử dụng Jev Ultrafast với Dola.com

Hệ thống browser agent siêu tốc **Jev Ultrafast** (từ `browser-use/jev-ultrafast`) đã được cài đặt và tích hợp trực tiếp với **dola.com**.

---

## 1. Cấu trúc sau khi cài đặt

- `jev-ultrafast/`: Thư mục mã nguồn của Jev Ultrafast agent.
- `jev-ultrafast/.env`: File cấu hình API keys và target URL `dola.com`.
- `jev-ultrafast/examples/dola.py`: Script chạy agent tự động trên dola.com.
- `run_jev_dola.sh`: Script phím tắt chạy automation dola từ thư mục gốc.
- `run_jev_ui.sh`: Script phím tắt mở Web Inspector giao diện trực quan tại `http://127.0.0.1:8766`.

---

## 2. Cấu hình API Keys (`jev-ultrafast/.env`)

Trước khi chạy agent, mở file `jev-ultrafast/.env` và điền 2 API key:

```env
# 1. TypeSafe API Key (Model Jev chọn element / action siêu tốc)
# Đăng ký tại: https://docs.typesafe.ai
TYPESAFE_API_KEY=your_typesafe_api_key_here
TYPESAFE_MODEL=jev-latest

# 2. Text Model API Key (Dùng để sinh nội dung khi nhập text vào input)
# Hỗ trợ bất kỳ endpoint chuẩn OpenAI nào (OpenRouter, DeepSeek, OpenAI, Gemini)
TEXT_MODEL_API_KEY=your_text_model_api_key_here
TEXT_MODEL_BASE_URL=https://openrouter.ai/api/v1
TEXT_MODEL=inception/mercury-2.5
TEXT_MODEL_REASONING=none

# 3. URL mục tiêu Dola
DOLA_URL=https://www.dola.com/chat

# 4. Cổng chạy giao diện Inspector
TYPESAFE_DEMO_PORT=8766
```

> **Gợi ý Text Model:**
> Nếu dùng DeepSeek: `TEXT_MODEL_BASE_URL=https://api.deepseek.com/v1`, `TEXT_MODEL=deepseek-chat`
> Nếu dùng OpenRouter: `TEXT_MODEL_BASE_URL=https://openrouter.ai/api/v1`, `TEXT_MODEL=inception/mercury-2.5`

---

## 3. Cách chạy

### Cách 1: Giao diện Web Inspector trực quan (Khuyên dùng khi test)

Chạy lệnh:
```bash
./run_jev_ui.sh
# Hoặc: cd jev-ultrafast && uv run jev
```
1. Mở trình duyệt tại: **http://127.0.0.1:8766**
2. Chọn scenario: **Dola (dola.com) · AI Video**
3. Bấm **Start demo** -> **Run automatically** (hoặc chọn **Choose next** để xem từng bước phán đoán của model).
4. Khi Chrome bật thông báo *"Allow remote debugging?"*, bấm **Allow**.

---

### Cách 2: Chạy dòng lệnh tự động (CLI)

Chạy với prompt tạo video:
```bash
./run_jev_dola.sh --prompt "Cyberpunk street with flying cars in rainy night"
```

Hoặc đặt goal tùy chỉnh:
```bash
./run_jev_dola.sh --goal "Vào dola.com/chat, nhấn 動画を作成, nhập prompt tạo video và gửi đi"
```

Các tham số bổ sung:
- `--keep-open`: Giữ nguyên tab trình duyệt sau khi hoàn thành.
- `--screenshots`: Chụp ảnh từng bước lưu vào thư mục `artifacts/dola/`.
- `--url`: Đổi URL nếu muốn (mặc định: `https://www.dola.com/chat`).
