# TÀI LIỆU TOÀN DIỆN VỀ DOLA RENDER GATEWAY

Tài liệu này tổng hợp toàn bộ thông tin kiến trúc, quy trình vận hành, hướng dẫn sử dụng và chi tiết kỹ thuật của hệ thống **Dola Render Gateway**.

---

## 📑 MỤC LỤC
1. [Giới thiệu tổng quan](#1-giới-thiệu-tổng-quan)
2. [Hướng dẫn cài đặt và sử dụng](#2-hướng-dẫn-cài-đặt-và-sử-dụng)
   - [Yêu cầu tiên quyết](#21-yêu-cầu-tiên-quyết)
   - [Cấu hình biến môi trường (.env)](#22-cấu-hình-biến-môi-trường-env)
   - [Thêm tài khoản Dola vào hệ thống](#23-thêm-tài-khoản-dola-vào-hệ-thống)
   - [Khởi chạy Server](#24-khởi-chạy-server)
   - [Quản lý qua Web Dashboard](#25-quản-lý-qua-web-dashboard)
   - [Gọi API sinh Video (Chuẩn OpenAI)](#26-gọi-api-sinh-video-chuẩn-openai)
3. [Quy trình hoạt động chi tiết (Workflow Pipeline)](#3-quy-trình-hoạt-động-chi-tiết-workflow-pipeline)
   - [Sơ đồ luồng xử lý](#31-sơ-đồ-luồng-xử-lý)
   - [Chi tiết 4 giai đoạn xử lý](#32-chi-tiết-4-giai-đoạn-xử-lý)
4. [Các thư viện sử dụng & Vai trò kỹ thuật](#4-các-thư-viện-sử-dụng--vai-trò-kỹ-thuật)
5. [Cơ chế tương tác với Web (DOM / XPath / Protocol Injection)](#5-cơ-chế-tương-tác-với-web-dom--xpath--protocol-injection)

---

## 1. Giới thiệu tổng quan

**Dola Render Gateway** là một hệ thống gateway biến dịch vụ sinh video AI của **Dola (dola.com)** thành một API chuẩn tương thích OpenAI (`/v1/videos/generations`, `/v1/videos/{id}`), đi kèm giao diện Web Dashboard trực quan để giám sát và quản trị pool tài khoản.

### Tính năng chính:
* **Chuẩn hóa API Video**: Cung cấp các endpoint tương tự chuẩn OpenAI, dễ dàng tích hợp vào các frontend hoặc hệ thống tự động hóa.
* **Mở rộng thời lượng & Tách Watermark**: Sử dụng Chromium Extension tùy biến (`extensions/dola30`) để mở khóa video độ dài **15s, 30s** và bóc tách luồng video gốc chất lượng cao không gắn logo watermark.
* **Browser Account Pool**: Quản lý nhiều tài khoản Google/Dola đồng thời, xoay vòng tài khoản tự động khi hết hạn mức ngày (quota), tự động quản lý cooldown và trạng thái khóa tài khoản.
* **Tự động vượt Captcha**: Tích hợp thuật toán thị giác máy tính OpenCV để phát hiện và tự động kéo thanh trượt giải Captcha của ByteDance.
* **Web Admin Dashboard**: Giao diện tại `/web` giúp quản lý tài khoản, xem hàng đợi tác vụ, tạo API key và theo dõi tỉ lệ thành công.

---

## 2. Hướng dẫn cài đặt và sử dụng

### 2.1. Yêu cầu tiên quyết
1. **Proxy (Bắt buộc)**:
   * Cần proxy có IP egress tại **Nhật Bản (JP)** hoặc **Hàn Quốc (KR)** do Dola hạn chế truy cập từ nhiều khu vực địa lý khác.
   * Hỗ trợ định dạng `http://ip:port`, `socks5://ip:port`.
2. **Tài khoản Dola / Google**:
   * Ít nhất 1 tài khoản Google (Email, Password và mã TOTP 2FA) hoặc cookie `sessionid`.
3. **Môi trường**:
   * Python 3.11+ (hiện đã có sẵn `.venv` tại thư mục gốc).

### 2.2. Cấu hình biến môi trường (`.env`)
Sao chép file mẫu:
```bash
cp .env.example .env
```

Thiết lập các giá trị trong `.env`:
```ini
# Host và Port chạy server
DOLA_HOST=0.0.0.0
DOLA_PORT=8000

# BẮT BUỘC: Proxy IP Nhật Bản hoặc Hàn Quốc
DOLA_PROXY=http://127.0.0.1:7890

# API Key cho client khi gọi API (để trống nếu chạy test local)
DOLA_API_KEYS=

# Mật khẩu trang quản trị Web Dashboard (để trống = không yêu cầu mật khẩu)
DOLA_ADMIN_KEY=

# Số lượng tác vụ render đồng thời tối đa
DOLA_MAX_CONCURRENCY=3

# Trình duyệt chạy ngầm (1 = headless ngầm, 0 = hiện cửa sổ trình duyệt)
DOLA_HEADLESS=1

# Chạy trình duyệt ở chế độ ẩn danh Incognito (1 = bật, 0 = tắt, mặc định: 0)
DOLA_INCOGNITO=0

# Timeout render video (giây)
DOLA_VIDEO_TIMEOUT=300
```

### 2.3. Thêm tài khoản Dola vào hệ thống

#### Cách 1: Tự động qua lệnh terminal (`add_account.py`)
Hỗ trợ đăng nhập tự động qua Google OAuth và vượt 2FA TOTP (thêm cờ `--incognito` nếu muốn chạy ẩn danh):
```bash
source .venv/bin/activate
python add_account.py acc1 "your_email@gmail.com----your_password----JBSWY3DPEHPK3PXP" [--incognito]
```
*(Trình duyệt sẽ tự mở, đăng nhập, lấy session và lưu vào `accounts/acc1`)*.

#### Cách 2: Nhập qua cookie (`cookies.txt`)
Copy cookie `sessionid` từ trình duyệt của bạn vào file `cookies.txt` (mỗi tài khoản một dòng).

#### Cách 3: Thêm qua giao diện Web Dashboard
Thêm trực tiếp thông qua nút Add Account trên giao diện quản trị `/web`.

### 2.4. Khởi chạy Server
```bash
# Cách 1: Chạy script có sẵn
./start_server.sh

# Cách 2: Chạy trực tiếp uvicorn
source .venv/bin/activate
uvicorn server:app --host 0.0.0.0 --port 8000 --reload
```

### 2.5. Quản lý qua Web Dashboard
Mở trình duyệt truy cập: **`http://localhost:8000/web`**
* **Accounts**: Quản lý trạng thái đăng nhập, điểm quota, bật/tắt tài khoản.
* **Tasks Queue**: Xem các video đang xếp hàng (`queued`), đang tạo (`processing`), hoàn thành hoặc thất bại.
* **API Keys**: Cấp phát và quản lý giới hạn cho từng bên gọi API.

### 2.6. Gọi API sinh Video (Chuẩn OpenAI)

#### Bước 1: Tạo tác vụ sinh video (`POST /v1/videos/generations`)
```bash
curl -X POST http://localhost:8000/v1/videos/generations \
  -H "Content-Type: application/json" \
  -d '{
    "prompt": "Cinematic shot of a cybernetic tiger running through neon streets, 4k",
    "ratio": "16:9",
    "duration": 10
  }'
```
* **Tham số**:
  * `prompt`: Mô tả video cần tạo.
  * `ratio`: Tỉ lệ khung hình (`16:9`, `9:16`, `1:1`, `4:3`, `3:4`).
  * `duration`: Thời lượng video (hỗ trợ `10`, `15`, hoặc `30` giây).
  * `reference_images`: Danh sách link ảnh tham chiếu (tùy chọn).
* **Kết quả trả về**:
```json
{
  "id": "task-uuid-xxxx",
  "status": "queued",
  "model": "seedance-2.0",
  "prompt": "Cinematic shot...",
  "video_url": null,
  "error": null
}
```

#### Bước 2: Kiểm tra trạng thái và nhận video (`GET /v1/videos/{id}`)
```bash
curl http://localhost:8000/v1/videos/task-uuid-xxxx
```
Khi render thành công:
```json
{
  "id": "task-uuid-xxxx",
  "status": "completed",
  "model": "seedance-2.0",
  "video_url": "http://localhost:8000/videos/xxxxxx.mp4"
}
```
Video được lưu trực tiếp tại thư mục local `downloads/`.

---

## 3. Quy trình hoạt động chi tiết (Workflow Pipeline)

### 3.1. Sơ đồ luồng xử lý

```
[Client / User]
       │
       ▼ (1. POST /v1/videos/generations)
 [FastAPI Server] ────────► [media.py]: Kiểm tra SSRF & Format ảnh tham chiếu
       │
       ▼ (2. Ghi task vào tasks.db với status="queued")
[Browser Pool Manager] ───► [pool_usage.db]: Kiểm tra Quota, Credit, Rate-limit, Lock
       │
       ▼ (3. Khởi chạy Context qua Proxy JP/KR + Nạp Extension dola30)
 [Patchright Engine]
       ├──► Điều hướng tới https://www.dola.com/chat
       ├──► Nhập Prompt, chọn Model, thiết lập Ratio & Duration (15s/30s)
       ├──► Bắt gặp Captcha kéo mảnh ghép?
       │        └──► [gap.py + OpenCV]: Canny Edge + Template Matching giải tự động
       └──► Gửi lệnh tạo video thành công
       │
       ▼ (4. Polling trạng thái ngầm qua In-page Fetch /im/chain/single)
 [Video Stream Extractor]
       └──► Trích xuất URL video gốc (Unwatermarked) ──► Tải về thư mục downloads/
       │
       ▼ (5. Cập nhật tasks.db status="completed")
[Client / User] ◄───────── GET /v1/videos/{id} nhận URL tải video
```

### 3.2. Chi tiết 4 giai đoạn xử lý

1. **Tiếp nhận & Kiểm duyệt an toàn (API Tier)**:
   * Nhận yêu cầu từ client, xác thực Bearer token / API key.
   * `media.py` tiến hành thẩm định an toàn đối với các URL ảnh tham chiếu: phân giải DNS và loại bỏ triệt để các địa chỉ IP nội bộ (`127.0.0.1`, `10.x`, `192.168.x`, link-local...) nhằm ngăn ngừa nguy cơ SSRF.
   * Lưu task vào SQLite (`tasks.db`) và kích hoạt worker chạy ngầm.

2. **Điều phối tài nguyên & Xoay vòng tài khoản (Pool Management Tier)**:
   * Giới hạn tải thông qua `asyncio.Semaphore`.
   * Mỗi tài khoản có một `asyncio.Lock` riêng, đảm bảo 1 tài khoản không bị gửi nhiều lệnh đồng thời gây crash giao diện.
   * Hệ thống tính toán quota còn lại trong ngày (mặc định 2 video/ngày/acc) và reset vào lúc 00:00 giờ Tokyo (`Asia/Tokyo`). Nếu tài khoản dính risk-control, hệ thống đưa vào trạng thái cooldown 30 phút và tự động chuyển sang tài khoản sẵn sàng tiếp theo.

3. **Tự động hóa trình duyệt & Vượt Captcha (Execution Tier)**:
   * Sử dụng `patchright` để khởi chạy Chromium với profile lưu sẵn tại `accounts/`.
   * Nhúng Extension `extensions/dola30` để hook dữ liệu skill-pack, mở khóa các nút chọn thời lượng dài 15s và 30s.
   * Khi gặp Captcha trượt (`bdcaptcha.html`), module `gap.py` trích xuất ảnh nền và ảnh puzzle, dùng thuật toán thị giác máy tính tìm tọa độ rãnh khuyết và điều khiển chuột kéo khớp vị trí.

4. **Polling giao thức ngầm & Xuất bản Media (Extraction & Storage Tier)**:
   * Không kiểm tra DOM liên tục mà thực thi script `POLL_JS` gọi trực tiếp API `/im/chain/single` bên trong ngữ cảnh tab.
   * Tìm kiếm link video không đóng dấu mờ (`unwatermarked url`).
   * Sử dụng `aiohttp` tải stream video về `downloads/` và cập nhật cơ sở dữ liệu để client truy cập.

---

## 4. Các thư viện sử dụng & Vai trò kỹ thuật

| Thư viện | Vai trò & Mục đích trong dự án |
| :--- | :--- |
| **`patchright`** | **Tự động hóa trình duyệt chống phát hiện (Anti-bot Bypass)**.<br>Bản fork đặc biệt của Playwright đã được vá các cờ bot-detection (`navigator.webdriver`, CDP leak, fingerprint). Dola chặn hầu hết các công cụ tự động hóa thông thường, nên `patchright` là cốt lõi để giữ phiên trình duyệt an toàn. |
| **`fastapi`** & **`uvicorn`** | **Web Framework & ASGI Server**.<br>Xây dựng hệ thống REST API tương thích chuẩn OpenAI, phục vụ các route quản trị Admin (`/api/admin/*`), Web Dashboard (`/web`) và phân phối file video tĩnh (`/videos`). |
| **`opencv-python-headless`** | **Thị giác máy tính (Computer Vision)**.<br>Chạy trên server không cần màn hình GUI. Dùng thuật toán **Canny Edge Detection** và **Template Matching (`cv2.matchTemplate`)** để phát hiện tọa độ khe khuyết trên Captcha trượt. |
| **`numpy`** | **Xử lý mảng số học**.<br>Chuyển đổi buffer byte nhị phân của ảnh Captcha thành ma trận điểm ảnh phục vụ việc tính toán trong OpenCV. |
| **`pillow` (PIL)** | **Kiểm định & Xử lý ảnh**.<br>Đọc metadata, kiểm tra tính hợp lệ và định dạng (JPEG, PNG, WEBP) của các ảnh tham chiếu trước khi tải lên. |
| **`aiohttp`** | **HTTP Client bất đồng bộ**.<br>Tải ảnh tham chiếu từ internet và stream video hoàn thiện từ CDN về máy chủ mà không làm nghẽn event loop. |
| **`pydantic`** | **Xác thực dữ liệu (Data Validation)**.<br>Kiểm tra tính hợp lệ của payload JSON mà client gửi lên (prompt, duration 10/15/30, aspect ratio). |
| **`python-dotenv`** | **Quản lý biến môi trường**.<br>Tự động nạp cấu hình từ `.env` hoặc `.env.local`. |
| **`sqlite3`** *(Chuẩn Python)* | **Cơ sở dữ liệu cục bộ**.<br>Lưu trữ nhiệm vụ (`tasks.db`), theo dõi quota, lịch sử rate-limit và credit của từng tài khoản (`pool_usage.db`). |
| **`hashlib` & `hmac`** *(Chuẩn Python)* | **Giải mã 2FA TOTP**.<br>Tự sinh mã Google Authenticator 6 số trong quá trình đăng nhập tự động ở file `add_account.py`. |

---

## 5. Cơ chế tương tác với Web (DOM / XPath / Protocol Injection)

Dự án tương tác với trang web Dola thông qua các kỹ thuật sau:

### 5.1. Có sử dụng XPath không?
* **KHÔNG sử dụng XPath**. Không có bất kỳ truy vấn XPath nào (`//div[...]`) trong mã nguồn.
* **Lý do**: XPath dễ bị hỏng khi hệ thống web thay đổi layout hoặc mã hash class động. Dự án ưu tiên CSS selector kết hợp Playwright Text Selector.

### 5.2. Các phương thức tương tác DOM & Trình duyệt cụ thể

1. **CSS Selector & Text Selector**:
   * Chọn phần tử nhập liệu: `input[type="file"]`, `#identifierId`, `input[name="Passwd"]`, `.captcha-slider-btn`, `textarea`, `[contenteditable="true"]`.
   * Chọn nút theo nhãn văn bản: `page.click("text=動画を作成")` (nút tạo video), `page.click("text=比率")`, `page.get_by_text("Dreamina Seedance 2.0高速")`, `page.click("text=10s")`.

2. **Chạy JavaScript trực tiếp trên DOM (`page.evaluate()`)**:
   * Dùng để kích hoạt sự kiện an toàn: `g.locator("#identifierNext").evaluate("e => e.click()")`.
   * Tìm và đóng popup xác nhận tuổi 18+:
     ```javascript
     const els = [...document.querySelectorAll('button, [role="button"], div, span')];
     const t = els.find(e => (e.textContent || '').trim() === 'OK');
     if (t) t.click();
     ```
   * Trích xuất thông tin ảnh Captcha: Lấy `document.images` để phân tích đường dẫn và kích thước tự nhiên của ảnh puzzle và ảnh nền.

3. **Thao tác Iframe DOM xuyên frame**:
   * Captcha ByteDance nằm trong iframe `bdcaptcha.html`. Code quét `page.frames` để tìm frame này, sau đó định vị phần tử trượt `.captcha-slider-btn` bên trong context của iframe.

4. **Mô phỏng chuột và bàn phím người thật (Human-like Simulation)**:
   * Nhập prompt: Sử dụng `page.keyboard.type(prompt, delay=100)` để gõ từng phím có độ trễ, tránh bị nhận diện là copy-paste bot.
   * Kéo trượt Captcha: Tính tọa độ từ `bounding_box()`, sau đó áp dụng hàm sinh quỹ đạo đường cong `_gen_track` tạo chuyển động rê chuột có độ lệch tự nhiên (`page.mouse.move()`, `page.mouse.down()`, `page.mouse.up()`).

5. **In-Page Fetch Protocol Injection (Kỹ thuật nổi bật)**:
   * Thay vì tương tác qua DOM để chờ video hoàn thành (dễ lỗi và phụ thuộc UI), worker inject script JavaScript trực tiếp gọi endpoint nội bộ `/im/chain/single` bằng `fetch()`.
   * Yêu cầu này tự động thừa hưởng toàn bộ Cookie, `sessionid`, `msToken`, `s_v_web_id` của tab đang mở, giúp trích xuất trạng thái và URL video gốc với độ tin cậy tuyệt đối.
