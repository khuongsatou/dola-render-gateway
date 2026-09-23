# Cẩm Nang Thiết Kế UI/UX & Animation (Chuẩn Graphite Tech & Apple HIG)
> *Đúc kết từ kiến trúc mã nguồn của dự án `mtips5s_motions` (Motion Studio Transfer Pipeline)*

---

## 1. Triết Lý & Bản Sắc Thị Giác: "Graphite Tech"

Hệ thống thiết kế của `mtips5s_motions` kết hợp 2 trường phái thiết kế hiện đại hàng đầu thế giới:
1. **Linear / Vercel Dark Mode**: Nền than chì sâu thẳm, viền hairline siêu mỏng, ánh sáng ambient mờ ảo và mực chữ tương phản cao.
2. **Apple Human Interface Guidelines (HIG)**: Độ cong góc bo mềm mại (squircle/continuous corners), độ nảy vật lý tự nhiên (Spring Physics), phản hồi xúc giác (Tactile Press) và các viên nang trạng thái (Status Capsules).

---

## 2. Hệ Thống Design Tokens & Bảng Màu

### 2.1. Nền Than Chì (Deep Charcoal Surfaces)
Thay vì dùng màu đen thuần túy `#000000` vốn dễ gây cảm giác "chết" và mỏi mắt, Graphite Tech sử dụng các sắc độ than chì có pha ánh xanh tím cực nhẹ:
```css
:root {
  --background: #0A0A0C;       /* Nền tổng thể trang */
  --surface:    #17171A;       /* Nền card con */
  --surface-2:  #1C1C21;       /* Nền thanh công cụ, popover */
  --foreground: #F7F8F8;       /* Mực sáng chính */
  
  --ink:        #F7F8F8;       /* Chữ chính, độ tương phản cao */
  --ink-2:      #8A8F98;       /* Chữ phụ, metadata */
  --ink-3:      #62666D;       /* Placeholder, label mờ */
  
  --line:       rgba(255, 255, 255, 0.08); /* Hairline siêu mảnh */
  --line-2:     rgba(255, 255, 255, 0.16); /* Viền hover / active */
}
```

### 2.2. Ánh Sáng Môi Trường (Dual Ambient Glows)
Hai nguồn sáng radial ở hai góc đối xứng tạo nên cảm giác không gian ba chiều sâu thẳm như trong phòng studio công nghệ cao:
```css
body {
  background:
    radial-gradient(55% 45% at 78% -8%, rgba(94, 106, 210, 0.13), transparent 62%),
    radial-gradient(45% 40% at 8% 108%, rgba(64, 143, 227, 0.07), transparent 60%),
    linear-gradient(180deg, #0B0B0E 0%, #09090B 100%);
  background-attachment: fixed;
}
```

### 2.3. Hiệu Ứng Gương Kính & Viền Phát Quang (Glassmorphism & Specular Edge)
Để card nổi bật trên nền tối mà không cần đổ bóng đen thô:
```css
.glass {
  background: rgba(20, 20, 23, 0.68);
  backdrop-filter: blur(28px) saturate(160%);
  -webkit-backdrop-filter: blur(28px) saturate(160%);
  border: 1px solid var(--line);
  /* Mép phản quang siêu nhẹ ở viền trên cùng */
  box-shadow: inset 0 1px 0 rgba(255, 255, 255, 0.06);
}
```

### 2.4. Đảo Ngược Thang Màu Xám (Inverted Neutral Scale)
Trong design system chuẩn dark-first:
- `--gray-50`: `#17171A` (surface tối)
- `--gray-100`: `#1C1C21`
- `--gray-200`: `#26262C`
- `--gray-300`: `#34343B`
- `--gray-400`: `#62666D`
- `--gray-500`: `#8A8F98`
- `--gray-700`: `#C9CDD1`
- `--gray-900`: `#F7F8F8` (chữ sáng nhất)
Nhờ vậy, khi chuyển đổi light/dark mode chỉ cần đổi bảng token mà không phải sửa class template HTML.

---

## 3. Vật Lý Chuyển Động & Micro-Interactions (Apple HIG)

### 3.1. Đường Cong Easing Chuẩn Apple (The Golden Spring Easing)
Mọi chuyển động trượt, mở drawer, co giãn kích thước đều dùng cubic bezier:
```css
:root {
  --spring: cubic-bezier(0.32, 0.72, 0, 1);
}
```
*Đặc tính*: Tăng tốc tức thì trong 30% thời gian đầu (mang lại cảm giác siêu nhạy), sau đó giảm tốc mềm mại tự nhiên trong 70% thời gian còn lại mà không bị giật cục.

### 3.2. Phản Hồi Xúc Giác Khi Bấm (Tactile Press Feedback)
Người dùng cảm nhận được chiều sâu khi click vào bất kỳ nút bấm hoặc tương tác nào:
```css
.press {
  transition: transform 0.15s ease-out;
}
.press:active {
  transform: scale(0.97);
}
```

### 3.3. Nguyên Tắc Vàng Cho Node Trên Canvas (Tuyệt Đối Không Scale Khi Hover)
> [!CAUTION]
> **Vấn đề chí mạng**: Trong các thư viện đồ thị canvas (Vue Flow, React Flow), nếu áp dụng `transform: scale(1.02)` trên thẻ node khi rê chuột, toạ độ thực tế của DOM Handles (chấm kết nối dây) sẽ bị xê dịch. Khi đó, các đường dây nối SVG (`bezier edges`) sẽ bị co giật hoặc lệch khỏi vị trí cắm.

**Giải pháp của `mtips5s_motions`**:
Giữ cố định kích thước node (ví dụ: `width: 240px`), không bao giờ dùng `scale()`. Thay vào đó, tạo cảm giác nổi bằng cách chuyển tiếp đa lớp `box-shadow` và `border-color`:
```css
.apl-node {
  width: 240px;
  background: var(--apl-node-bg);
  border-radius: 20px;
  border: 0.5px solid var(--apl-node-border);
  box-shadow: 0 1px 2px rgba(0,0,0,0.4), 0 16px 32px -8px rgba(0,0,0,0.55), inset 0 0.5px 0 rgba(255,255,255,0.06);
  transition: box-shadow 0.25s var(--spring),
              border-color 0.25s var(--spring);
}

.apl-node:hover {
  border-color: rgba(235, 236, 240, 0.28);
  box-shadow: 0 2px 4px rgba(0,0,0,0.45), 0 20px 44px -8px rgba(0,0,0,0.65), inset 0 0.5px 0 rgba(255,255,255,0.08);
}

/* Selected state: Vòng sáng đôi System Blue */
.apl-node.is-selected {
  border-color: rgba(94, 106, 210, 0.7);
  box-shadow:
    0 0 0 2px rgba(94, 106, 210, 0.55),
    0 0 0 6px rgba(94, 106, 210, 0.16),
    0 12px 32px rgba(94, 106, 210, 0.18);
}
```

---

## 4. Bộ Hoạt Họa Trạng Thái Thời Gian Thực (State Keyframes)

### 4.1. Quầng Hào Quang Khi Đang Chạy Tác Vụ (`apl-pulse`)
Node hoặc Task đang xử lý (GPU/Worker) sẽ phát ra quầng hào quang màu hổ phách lan tỏa nhịp nhàng:
```css
@keyframes apl-pulse {
  0%, 100% {
    box-shadow: 0 0 0 0 rgba(255, 149, 0, 0.18), 0 8px 24px rgba(255, 149, 0, 0.1);
  }
  50% {
    box-shadow: 0 0 0 8px rgba(255, 149, 0, 0), 0 8px 24px rgba(255, 149, 0, 0.15);
  }
}
.state-running {
  border-color: rgba(255, 149, 0, 0.5);
  animation: apl-pulse 1.4s ease-in-out infinite;
}
```

### 4.2. Nhịp Tim Trạng Thái (`apl-blink`)
Viên nang trạng thái (status capsule) ở góc dưới-phải:
```css
@keyframes apl-blink {
  0%, 100% { transform: scale(1); }
  50%      { transform: scale(1.15); }
}
.apl-status[data-state="running"] {
  background: #FF9500;
  animation: apl-blink 1s infinite;
}
```

### 4.3. Chấm Báo Chưa Lưu / Đang Poll (`apl-pulse-dot`)
```css
@keyframes apl-pulse-dot {
  0%, 100% { opacity: 1; }
  50%      { opacity: 0.4; }
}
.pulse-dot {
  width: 6px;
  height: 6px;
  border-radius: 50%;
  background: #F59E0B;
  animation: apl-pulse-dot 1.4s infinite;
}
```

---

## 5. Sàn Lưới 3D Perspective Kiểu Vercel (Canvas Backdrop)

Tạo cảm giác như đang đứng trên sàn diễn công nghệ ảo bằng CSS thuần với 2 lớp pseudo-elements:
```css
/* Lớp 1: Lưới 2D vuông mờ dần ra rìa */
.canvas-bg::before {
  content: "";
  position: absolute;
  inset: 0;
  pointer-events: none;
  background-image:
    linear-gradient(rgba(255, 255, 255, 0.07) 1px, transparent 1px),
    linear-gradient(90deg, rgba(255, 255, 255, 0.07) 1px, transparent 1px);
  background-size: 96px 96px;
  mask-image: radial-gradient(ellipse 85% 75% at 50% 38%, black 25%, transparent 78%);
  -webkit-mask-image: radial-gradient(ellipse 85% 75% at 50% 38%, black 25%, transparent 78%);
}

/* Lớp 2: Sàn lưới 3D nghiêng về chân trời */
.canvas-bg::after {
  content: "";
  position: absolute;
  left: -25%;
  right: -25%;
  bottom: -14%;
  height: 58%;
  pointer-events: none;
  background-image:
    linear-gradient(rgba(94, 106, 210, 0.10) 1px, transparent 1px),
    linear-gradient(90deg, rgba(94, 106, 210, 0.10) 1px, transparent 1px);
  background-size: 56px 56px;
  transform: perspective(620px) rotateX(63deg);
  transform-origin: center bottom;
  mask-image: linear-gradient(to top, rgba(0, 0, 0, 0.75), transparent 82%);
  -webkit-mask-image: linear-gradient(to top, rgba(0, 0, 0, 0.75), transparent 82%);
}
```

---

## 6. Trình Phát Video Tích Hợp Metadata & Đo FPS Tự Động

Trong `mtips5s_motions`, khung preview video tự động đọc metadata để hiển thị badge độ phân giải và tốc độ khung hình (fps) thực tế:
```javascript
function onVideoLoaded(event) {
  const vid = event.target;
  const w = vid.videoWidth;
  const h = vid.videoHeight;
  
  // Đo fps dựa trên MediaTrackCapabilities hoặc ước lượng requestVideoFrameCallback
  let fps = null;
  if ('requestVideoFrameCallback' in HTMLVideoElement.prototype) {
    let frameCount = 0;
    let startTime = null;
    function countFrame(now, metadata) {
      if (!startTime) startTime = now;
      frameCount++;
      if (frameCount > 20) {
        fps = Math.round((frameCount * 1000) / (now - startTime));
        renderVidMeta(w, h, fps);
        return;
      }
      vid.requestVideoFrameCallback(countFrame);
    }
    vid.requestVideoFrameCallback(countFrame);
  } else {
    renderVidMeta(w, h, null);
  }
}
```

---

## 7. Giải Pháp Tránh Xung Đột Stacking Context (`Teleport`)

Mọi thành phần trôi nổi:
- Dropdown Menu
- Toast Stack
- Modal Hộp Thoại
- Floating Context Toolbar

**Bắt buộc phải được gắn trực tiếp ra `document.body`** thay vì nằm trong container của Canvas hoặc Table:
- Trong Vue/Nuxt: Sử dụng `<Teleport to="body">`.
- Trong React: Sử dụng `ReactDOM.createPortal(element, document.body)`.
- Trong Vanilla JS: Gọi hàm tạo phần tử và `document.body.appendChild(modalEl)`.

Điều này đảm bảo không bao giờ bị các thuộc tính CSS như `overflow: hidden`, `transform: ...`, `backdrop-filter: ...` của component cha cắt cúp (clipping) hoặc kéo hạ z-index.
