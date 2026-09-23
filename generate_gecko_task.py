import asyncio
import json
import os
import sys
import time
from video_worker_ui import generate_video
from store import TaskStore

async def main():
    account = "vankhuong240_p185"
    ref_image = "/Users/apple/.gemini/antigravity/brain/3ccfaba1-56ac-4611-9cd2-54a20c17d8d1/.user_uploaded/media_1790098587693.png"
    
    prompt = (
        "A cute 3D cartoon green gecko standing on a school desk, short T-rex arms, huge white eyes with tiny pupils, "
        "long curling tail to the right, hind feet planted and never sliding. Vertical 9:16, locked camera with tiny handheld drift only, "
        "one continuous 8-second take, no text, no captions, no watermark, no logo. 0.0-2.0s frantic explaining: hunched body, "
        "anxious hip bounces, mouth wide open, long pink tongue hanging out, short arms flailing opposite with splayed fingers, "
        "head nodding and yawing while talking, tail wagging as overlapping follow-through. 2.0-5.0s desperate plead: chest rises, "
        "head tilts back, snout lifts to the ceiling, jaw opens to maximum, tongue flips upward, both short arms throw up together, "
        "hold the scream with tiny shakes and no locomotion. 5.0-5.7s embarrassed pause: energy collapses, mouth almost closes, "
        "arms drop, deadpan still eyes, one short hold, feet stay planted. 5.7-8.2s explode talking again: body snaps back into "
        "frantic bounce, mouth pops wide, tongue out, opposite arm flails, head shakes while explaining, tail lags behind. "
        "Keep the gecko as one connected character. No walking, no jumping off the desk, no flying, no extra characters, "
        "no camera cuts, no extra limbs, no disconnected head, no sliding feet, no morphing face."
    )
    
    ratio = "9:16"
    duration = 10
    model = "seedance_v2.0"
    
    print(f"=== KHỞI CHẠY TẠO VIDEO GECKO SEEDANCE ===", flush=True)
    print(f"Account: {account}", flush=True)
    print(f"Ảnh tham chiếu: {ref_image} (Tồn tại: {os.path.exists(ref_image)})", flush=True)
    print(f"Tỷ lệ: {ratio} (Dọc), Thời lượng: {duration}s, Model: {model}", flush=True)
    
    start_time = time.time()
    result = await generate_video(
        account=account,
        prompt=prompt,
        ratio=ratio,
        duration=duration,
        model=model,
        reference_image_paths=[ref_image]
    )
    
    elapsed = time.time() - start_time
    print(f"=== TẠO VIDEO THÀNH CÔNG trong {elapsed:.1f}s ===", flush=True)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    
    # Ghi nhận vào SQLite tasks.db để đồng bộ Dashboard
    try:
        store = TaskStore("tasks.db")
        task_id = "video_gecko_" + str(int(time.time()))
        store.create(
            task_id=task_id,
            model=model,
            prompt=prompt,
            ratio=ratio,
            duration=duration,
            reference_images=json.dumps([ref_image]),
            api_key_hash=None,
            api_key_name="Character Reference Runner",
        )
        video_url = f"http://127.0.0.1:8000/videos/{os.path.basename(result['local_path'])}"
        store.update(
            task_id,
            status="completed",
            video_url=video_url,
            account=account,
            started_at=start_time,
            finished_at=time.time(),
            conversation_id=result.get("conversation_id")
        )
        print("Đã lưu task vào tasks.db thành công!", flush=True)
    except Exception as e:
        print(f"Lỗi ghi tasks.db: {e}", flush=True)

if __name__ == "__main__":
    asyncio.run(main())
