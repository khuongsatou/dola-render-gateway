# 🎬 Blockbuster Studio: AI Cinematic Production Pipeline

Xây dựng video điện ảnh đa cảnh (multi-scene blockbuster) với nhân vật nhất quán (Character Consistency Anchor), lồng tiếng (Voiceover/TTS), âm thanh môi trường điện ảnh (Atmospheric Soundscape) và dựng phim chuẩn Hollywood Cinemascope (2.39:1 @ 24fps) dựa trên phương pháp phân tích từ **Higgsfield 4K Blockbuster Breakdown**.

---

## 🌟 Quy trình 5 bước chuẩn điện ảnh (5-Step Production Pipeline)

```
[1. Script & Storyboard] ──► [2. Character Anchor] ──► [3. Seedance Render] ──► [4. Voiceover & Audio] ──► [5. Master Stitch]
  - 3-5 phân cảnh              - Khóa khuôn mặt/trang phục - Dola Seedance 2.0/2.5    - Voiceover AI (EN/VI)        - Khung hình 2.39:1
  - Cỡ cảnh (Shot type)        - Character Reference Card  - Reference image upload    - Sub-bass drone & Ambience   - Chuẩn phim 24fps
  - Chuyển động máy quay                                                               - Phụ đề (.srt)               - Master video
```

### 1. Lên ý tưởng & Kịch bản phân cảnh (Scriptwriting & Storyboard)
- Cấu trúc 3 đến 5 hồi kinh điển (Hook, Rising Tension, Climax / Twist, Resolution).
- Quy chuẩn hóa từng cú máy: Shot Type (Close-up, Medium, Wide), Camera Motion (Push-in, Orbit, Steadicam Tracking), Ánh sáng (Neon Cyber, Golden Hour, Chiaroscuro).

### 2. Cố định nhân vật (Character Consistency Anchor)
- Tạo thẻ định danh nhân vật (`CharacterAnchor`): khuôn mặt, độ tuổi, trang phục đặc trưng, phụ kiện bất biến.
- Tự động sinh Reference Anchor Card và truyền vào tham số `reference_image_paths` của Dola Seedance UI Automation (`input[type="file"]`), đảm bảo AI diffusion giữ nguyên khuôn mặt và style xuyên suốt mọi phân cảnh.

### 3. Render cảnh quay Seedance (Multi-scene Rendering)
- Tự động kết hợp `[Shot Type] + [Character Anchor] + [Scene Action] + [Environment & Lighting] + [Film Finish]` thành prompt Seedance chất lượng cao.
- Điều phối render qua Dola account (`vankhuong240_p185`), tự động fallback thông minh giữa `seedance_v2.5` và `seedance_v2.0`.

### 4. Xử lý Voiceover & Thiết kế âm thanh (Voice & Sound Design)
- Tạo giọng lồng tiếng tự nhiên bằng macOS Speech Engine / TTS (hỗ trợ Tiếng Anh như `Samantha`, `Daniel`, và Tiếng Việt như `Linh`).
- Tự động tổng hợp dải âm trầm điện ảnh (Cinematic Sub-bass 55Hz & Pink noise ambience) để video không bị khô ráp.
- Xuất file phụ đề chuẩn `.srt` khớp từng mili-giây với cảnh quay.

### 5. Dựng & Xuất bản Master Timeline (Cinematic Mastering & Stitching)
- Chuẩn hóa tốc độ khung hình chuẩn điện ảnh 24.0 fps.
- Thêm dải đen điện ảnh tỷ lệ Anamorphic Cinemascope **2.39:1**.
- Ghép nối đa cảnh liền mạch, hòa âm master và xuất ra video hoàn chỉnh 1080p/4K.

---

## 🚀 Hướng dẫn sử dụng CLI (`run_blockbuster.py`)

### 1. Xem trước kịch bản phân cảnh (`plan`)
```bash
./.venv/bin/python run_blockbuster.py --preset cyberpunk --mode plan
# Hoặc kịch bản cổ trang Việt Nam:
./.venv/bin/python run_blockbuster.py --preset vietnamese_legend --mode plan
```

### 2. Chuẩn bị Asset & Thẻ nhân vật & Audio lồng tiếng (`prepare`)
```bash
./.venv/bin/python run_blockbuster.py --preset cyberpunk --mode prepare
```
Lệnh này sẽ:
- Khóa diện mạo nhân vật và tạo ảnh Reference Card trong thư mục `blockbuster_output/.../character/`.
- Tạo file lồng tiếng từng cảnh (`scene_1_voice.mp3`, `scene_2_voice.mp3`, ...).
- Hòa âm tiếng nền điện ảnh và xuất phụ đề `.srt`.

### 3. Render các cảnh bằng Dola Seedance (`render`)
```bash
./.venv/bin/python run_blockbuster.py --preset cyberpunk --account vankhuong240_p185 --model seedance_v2.0 --mode render
```

### 4. Dựng phim thành Master hoàn chỉnh (`stitch`)
```bash
./.venv/bin/python run_blockbuster.py --project-file blockbuster_output/<project_id>/project.json --mode stitch
```

### 5. Chạy toàn bộ quy trình từ A - Z (`full`)
```bash
./.venv/bin/python run_blockbuster.py --preset cyberpunk --account vankhuong240_p185 --model seedance_v2.0 --mode full
```

---

## 📁 Cấu trúc thư mục Module

```
dola/
├── blockbuster_studio/
│   ├── __init__.py          # Export các API chính
│   ├── models.py            # Data classes: StoryProject, Scene, CharacterAnchor
│   ├── character.py         # Quản lý Reference Anchor Image & Prompt Tokens
│   ├── scriptwriter.py      # Kịch bản mẫu (Cyberpunk, Vietnamese Legend) & Custom Generator
│   ├── audio_engine.py      # Bộ tổng hợp lồng tiếng (TTS), Ambient Drone & Subtitles (.srt)
│   ├── video_stitcher.py    # Dựng phim ffmpeg: 24fps conform, 2.39:1 Cinemascope letterbox
│   └── studio.py            # Orchestrator điều phối từ A đến Z
└── run_blockbuster.py       # Công cụ CLI thân thiện cho người dùng
```
