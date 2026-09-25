import asyncio
import json
import os
import sys
import time
from pathlib import Path

from video_worker_ui import generate_video
from store import TaskStore

# Định nghĩa Prompt chi tiết cho các Scene theo giáo án mtips5s_cut_scene & shotlist blockbuster
SCENE_PROMPTS = {
    1: {
        "title": "Scene 1 - Hang Đá & Nỗi Sợ Dã Thú",
        "folder": "scene_01_hang_đá_nỗi_sợ_dã_thú",
        "prompt": (
            "Cinematic slow push-in: prehistoric dark limestone cave interior during a violent monsoon rainstorm at twilight. "
            "Outside the cave entrance, torrential rain lashes prehistoric tropical jungle canopy with jagged lightning illuminating rain streaks. "
            "Inside the cavern, a primitive hunter with sun-weathered bronze skin and dark hair tied back with rawhide sits shivering against cold rock. "
            "He breathes heavily, his chest heaving with deep tension, eyes hyper-vigilant scanning the dark jungle. "
            "Outside in the rainy mist, two predatory glowing amber eyes of a sabertooth cat briefly gleam before disappearing into shadows. "
            "Cinematic chiaroscuro lighting, 7000K cold slate blue ambience, wet rock reflections, 35mm anamorphic, shallow depth of field, 8K ultra-detailed."
        ),
        "target_file": "sc01_hang_da_noi_so_10s_dola.mp4"
    },
    2: {
        "title": "Scene 2 - Món Quà Từ Sấm Sét & Ngọn Lửa Khởi Nguyên",
        "folder": "scene_02_ngọn_lửa_khởi_nguyên",
        "prompt": (
            "Cinematic wide establishing shot with dynamic camera shake: a colossal prehistoric ancient banyan tree towering in a jungle clearing under torrential storm rain. "
            "Suddenly a blinding electric-cyan lightning bolt violently strikes the tree crown, exploding the wood in a massive shower of sparks and debris. "
            "Fierce golden-orange flames erupt instantly up the trunk, billowing thick black smoke against the storm clouds while primal sparks drift through the heavy rain. "
            "High-contrast lighting transition from 9000K electric blue lightning flash to 2200K roaring orange firelight, 35mm Panavision anamorphic, photorealistic 8K."
        ),
        "target_file": "sc02_ngon_lua_khoi_nguyen_10s_dola.mp4"
    },
    3: {
        "title": "Scene 3 - Cọ Xát Giáng Lửa Bùng Cháy",
        "folder": "scene_03_cọ_xát_giáng_lửa_bùng_cháy",
        "prompt": (
            "Cinematic medium tracking shot to close-up: primitive hunter kneeling near smoking charred debris in the rain. "
            "He holds a dry wooden branch with steady trembling hands, carefully touching the wood tip to a glowing orange ember inside burnt bark. "
            "White aromatic smoke curls upward, tiny sparks ignite the wood fibers, and a vibrant golden flame bursts to life crackling brightly. "
            "Warm 2200K radial firelight illuminates his awe-struck weathered face, eyes reflecting the dancing fire. 50mm macro cinema lens, photorealistic 8K."
        ),
        "target_file": "sc03_thuan_hoa_lua_10s_dola.mp4"
    }
}

async def render_scene(scene_num: int = 1, duration: int = 10, account: str = "cookrightvig_p596", model: str = "seedance_v2.0"):
    scene_data = SCENE_PROMPTS.get(scene_num)
    if not scene_data:
        print(f"Error: Scene {scene_num} not found in prompt pack.")
        return False

    print("=" * 60)
    print(f"🎬 BẮT ĐẦU RENDER {scene_data['title']} (DURATION: {duration}s)")
    print(f"Account: {account} | Model: {model} | Tỷ lệ: 16:9")
    print(f"Prompt:\n{scene_data['prompt']}")
    print("=" * 60)

    out_dir = Path(f"blockbuster_output/proj_human_dawn/scenes/{scene_data['folder']}/final_4k")
    out_dir.mkdir(parents=True, exist_ok=True)
    out_path = out_dir / scene_data["target_file"]

    start_time = time.time()
    try:
        result = await generate_video(
            account=account,
            prompt=scene_data["prompt"],
            ratio="16:9",
            duration=duration,
            model=model,
            timeout=600,
            reference_image_paths=None
        )
    except Exception as e:
        print(f"❌ Render thất bại: {e}")
        return False

    elapsed = time.time() - start_time
    print(f"✅ RENDER THÀNH CÔNG trong {elapsed:.1f}s!")
    print(json.dumps(result, ensure_ascii=False, indent=2))

    local_src = result.get("local_path")
    if local_src and os.path.exists(local_src):
        import shutil
        shutil.copy2(local_src, str(out_path))
        print(f"📁 Đã lưu video thành công vào: {out_path}")
        
        # Ghi vào asset manifest
        manifest_file = Path("blockbuster_output/proj_human_dawn/metadata/asset_manifest.jsonl")
        manifest_entry = {
            "asset_id": f"vid_scene_{scene_num:02d}_{duration}s",
            "type": "video_clip",
            "scene": scene_num,
            "duration": duration,
            "path": str(out_path),
            "created_at": time.time(),
            "status": "APPROVED",
            "provider": f"Dola {model}"
        }
        with open(manifest_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(manifest_entry, ensure_ascii=False) + "\n")
        print(f"📝 Đã cập nhật vào asset manifest.")

    return True

if __name__ == "__main__":
    target_scene = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    target_dur = int(sys.argv[2]) if len(sys.argv) > 2 else 10
    target_acc = sys.argv[3] if len(sys.argv) > 3 else "cookrightvig_p596"
    asyncio.run(render_scene(scene_num=target_scene, duration=target_dur, account=target_acc))
