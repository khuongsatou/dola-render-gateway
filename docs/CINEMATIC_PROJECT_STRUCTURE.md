# 🎬 Cấu Trúc Dự Án & Quy Chuẩn Chuẩn Bị Asset Chuẩn Điện Ảnh (Cinematic Project Structure & Asset Vault Standard)

> **Tài liệu tham chiếu chuẩn** được trích xuất và hệ thống hóa từ kho lưu trữ sản xuất thực tế:  
> `/Users/apple/Downloads/mtips5s_artifact_vault/4k-blockbuster-breakdown` (Dự án bom tấn 4K của *Adil in the Wild / Higgsfield* với hơn 8.900 asset).

---

## 1. Sơ đồ Cấu Trúc Thư Mục Chuẩn (Production Folder Hierarchy)

```
project_vault/ (hoặc blockbuster_output/<project_id>/)
│
├── 📂 metadata/                                    # Quản trị toàn bộ dữ liệu & thông số kỹ thuật
│   ├── project.json                               # Kịch bản tổng, thông số các cảnh, đạo cụ, nhân vật
│   ├── folder_map.json                            # Ánh xạ thư mục ID sang đường dẫn thực tế
│   └── asset_manifest.jsonl                       # Kiểm soát mã băm sha256, kích thước, model, prompt
│
├── 📂 assets/                                      # TRỤ CỘT ASSET ĐẦU VÀO (Input Anchors)
│   │
│   ├── 📂 characters/                             # Cố định nhân vật & diện mạo
│   │   ├── character_sheet_3panel.png             # THẺ VÀNG: 3 khung hình (Front Close-up, Full Front, Full Back)
│   │   ├── headshots/                             # Các góc biểu cảm (giận dữ, ngạc nhiên, tập trung)
│   │   └── turnarounds/                           # Góc quay 360 độ (nếu cần)
│   │
│   ├── 📂 props/                                  # Đạo cụ then chốt (Hero Props)
│   │   ├── prop_sheet_item1.png                   # Thẻ đạo cụ 4 góc chụp (ví dụ: vũ khí, bản đồ, la bàn)
│   │   └── prop_sheet_item2.png                   # Đạo cụ phụ (ví dụ: hộp báu vật, kính thiên văn)
│   │
│   └── 📂 locations/                              # Bối cảnh không gian & khí quyển (Master Environments)
│       ├── location_establishing_master.png       # Khung cảnh toàn cảnh khóa bảng màu và nguồn sáng
│       └── location_details/                      # Chi tiết mặt sàn, texture tường, cây cối, khói sương
│
├── 📂 scenes/                                      # QUY TRÌNH SẢN XUẤT THEO PHÂN CẢNH (Scene Pipelines)
│   │
│   ├── 📂 scene_01_<slug_name>/                   # Ví dụ: scene_01_hook_awakening
│   │   ├── 📂 drafts_1080p/                       # Thử nghiệm góc máy, chuyển động, pacing (tốc độ nhanh)
│   │   │   ├── beat_01/                           # Từng nhịp diễn xuất nhỏ trong cảnh
│   │   │   ├── beat_02/
│   │   │   └── selected/                          # Các bản nháp ưng ý nhất được chọn lọc
│   │   └── 📂 final_4k/                           # Render chất lượng cao nhất cho các shot trong selected/
│   │       └── sc01_shot01_final.mp4
│   │
│   ├── 📂 scene_02_<slug_name>/                   # Ví dụ: scene_02_tension_pursuit
│   │   ├── drafts_1080p/
│   │   └── final_4k/
│   │
│   └── 📂 scene_03_<slug_name>/                   # Ví dụ: scene_03_climax_reveal
│       ├── drafts_1080p/
│       └── final_4k/
│
└── 📂 timeline_master/                             # HẬU KỲ & XUẤT BẢN HOÀN CHỈNH (Master Post-Production)
    ├── 📂 voiceovers/                             # Audio lồng tiếng AI từng cảnh (.mp3 / .wav)
    ├── 📂 foley_ambience/                         # Tiếng nền môi trường, sub-bass drone, SFX
    ├── 📂 subtitles/                              # File phụ đề chuẩn thời gian (.srt)
    └── 🎞️ master_blockbuster_2.39_4k.mp4           # Video phim hoàn chỉnh chuẩn 24fps Cinemascope
```

---

## 2. Quy Chuẩn 4 Trụ Cột Chuẩn Bị Asset (The 4 Asset Pillars)

### 👤 Trụ cột 1: Thẻ Nhân Vật 3 Khung Hình (3-Panel Character Sheet)
- **Tỷ lệ & Kích thước**: Khung ngang 16:9 (tối ưu từ `2048x1152` đến `5504x3072`).
- **Phông nền & Ánh sáng**: Nền xám/trắng trung tính (*neutral cool light-grey seamless studio backdrop*), ánh sáng tán xạ mềm (*soft diffuse broad softbox*), không bóng đổ gắt.
- **Bố cục 3 khung hình từ trái qua phải**:
  1. **Khung trái (Frontal Close-up)**: Chụp cận mặt góc chính diện, khóa hình học xương hàm, khoảng cách hai mắt, sống mũi, khóe môi, biểu cảm điềm tĩnh. Vành nón hoặc tóc không được che khuất trán/mắt.
  2. **Khung giữa (Full-Body Front)**: Toàn thân từ đỉnh đầu đến mũi giày, hai tay thả lỏng tự nhiên, khóa tỷ lệ cơ thể và trang phục phía trước.
  3. **Khung phải (Full-Body Back)**: Toàn thân nhìn từ phía sau cùng tỷ lệ với khung giữa, khóa chi tiết ba lô, thắt lưng, kiểu tóc phía sau và gót giày.
- **Quy tắc pha trộn 2 ảnh (Dual-Reference Prompting)**:
  - `Image 1`: Khóa tuyệt đối đặc điểm khuôn mặt (*Identity/Face geometry lock*).
  - `Image 2`: Khóa trang phục, vũ khí, phụ kiện và kiểu tóc (*Wardrobe & Gear lock*).

---

### 🗡️ Trụ cột 2: Thẻ Đạo Cụ Điện Ảnh (Hero Prop Sheet)
- Tách riêng từng món đồ nhân vật sẽ tương tác (dao găm, kính viễn vọng, bình thuốc, cổ vật).
- **Trình bày**: 4 ô ngang (*4 equally-sized frames in a horizontal row*) thể hiện:
  - Góc toàn cảnh 3/4.
  - Cận cảnh chất liệu (kim loại xước, da thuộc, ngọc cổ...).
  - Trạng thái khi đóng / mở hoặc trong bao / rút ra.
- **Mục đích**: Ngăn hiện tượng AI "bịa" hình dáng hoặc làm méo vật thể khi nhân vật cầm nắm trong video.

---

### 🌴 Trụ cột 3: Bối Cảnh Không Gian Gốc (Location Master)
- Tạo ảnh góc cực rộng (*Colossal panoramic master shot*).
- **Yếu tố bắt buộc phải xác lập**:
  - Hướng nguồn sáng chính (*Key light direction*) và ánh sáng ven (*Rim light*).
  - Tầng khí quyển (*Atmospheric volumetric haze, mist, dust particles*).
  - Bảng màu chủ đạo (*Color palette: ấm áp golden hour, lạnh neon cyan hay âm u chiaroscuro*).
- **Mục đích**: Khi nạp cùng lúc `Character Sheet` + `Location Master` vào Image-to-Video, nhân vật lập tức thừa hưởng đúng ánh sáng và màu sắc của thế giới đó.

---

### ⏱️ Trụ cột 4: Quy Trình Render Phân Tầng (Tiered Prototyping)
- **Giai đoạn 1 - 1080p Drafts**:
  - Render nhanh nhiều take (lần thử) cho từng nhịp (*Beats*) với Seedance.
  - Đánh giá chuyển động máy quay (*Camera motion*), diễn xuất (*Acting/Emotion*), tốc độ (*Pacing*).
- **Giai đoạn 2 - Tuyển chọn (`selected/`)**:
  - Đưa 1 hoặc 2 take xuất sắc nhất vào thư mục `selected/`.
- **Giai đoạn 3 - 4K Master**:
  - Chỉ render bản độ phân giải cao nhất cho các shot trong `selected/`, giúp tiết kiệm quota điểm và thời gian chờ đợi.
- **Giai đoạn 4 - Timeline Stitching**:
  - Hòa âm giọng đọc AI + âm thanh môi trường + dải đen tỉ lệ vàng điện ảnh **2.39:1 Cinemascope** ở tốc độ **24.0 fps**.

---

## 3. Mẫu Prompt Chuẩn Cho Từng Trụ Cột Asset

### Mẫu 1: Prompt Tạo Thẻ Nhân Vật 3 Khung Hình (3-Panel Character Sheet)
```text
Generate a NEW three-panel character reference sheet from TWO reference images. 
Image 1 defines the FACE and identity ONLY. 
Image 2 defines the wardrobe, gear, hat and hairstyle. 
Combine them: the exact face from Image 1 wearing the full look and hair from Image 2. 
A real photograph, documentary-grade realism, 8k resolution. 
Three panels side by side in one horizontal row with thin divider lines, 16:9 horizontal sheet.

- Left, FRONTAL CLOSE-UP: head and shoulders, head square to camera, full front view, nose centered, eyes straight down the lens, neutral calm clever expression. Face geometry, bone structure, eyes, lips locked to Image 1. Forehead, brows and eyes fully visible and clearly lit.
- Center, FULL-BODY FRONT: full figure head to boots, facing camera straight on, weight balanced, arms relaxed, both hands visible, full costume details visible.
- Right, FULL-BODY BACK: full figure head to boots, back to camera, showing the back of the outfit, hairstyle, backpack and belt accessories.

Both full-body panels at identical scale with feet aligned on the same ground line.
Lighting and background: neutral cool light-grey seamless studio backdrop, soft even flat diffuse light, no harsh directional shadows.
```

### Mẫu 2: Prompt Tạo Thẻ Đạo Cụ (Hero Prop Sheet)
```text
Professional film production prop reference sheet, isolating only the [PROP NAME]. 
Four equally-sized frames in a single horizontal row, neutral warm grey background, soft even studio lighting, no harsh shadows, subtle contact shadow under the object.
Frame 1: 3/4 perspective hero angle showing entire length and silhouette.
Frame 2: Extreme close-up macro texture showing material details, worn leather, weathered brass and patina.
Frame 3: Front orthographic view.
Frame 4: The object in functional position / unsheathed state.
Photorealistic, cinematic asset breakdown sheet, 8K.
```

### Mẫu 3: Prompt Tạo Bối Cảnh Gốc (Location Master)
```text
Cinematic establishing master environment shot of [SETTING NAME]. 
Extreme wide panoramic angle, breathtaking depth of scale. 
Atmosphere & Lighting: [LIGHTING STYLE, e.g. misty morning sunbeams piercing through dense canopy, volumetric god rays, atmospheric haze].
Color palette: [COLOR SPECIFICATION, e.g. rich emerald greens, deep earthy tones, warm amber highlights].
Hyper-detailed textures, photorealistic 35mm anamorphic film still, masterpiece composition, 8K.
```
