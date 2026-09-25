import asyncio
import json
import os
import sys
import time
from video_worker_ui import generate_video
from store import TaskStore

async def main():
    account = "vankhuong240_p185"
    prompt = (
        "cinematic close-up of a young Asian woman wearing a black hoodie and a dark head covering, "
        "standing beside a traditional outdoor barbecue grill. She slowly adjusts the cloth on her head with both hands "
        "while smoke rises around her. Cut to detailed macro shots of juicy pieces of grilled meat on metal skewers "
        "over glowing charcoal, sizzling and releasing thick aromatic smoke. Close-up of the meat being grilled over "
        "intense open flames, golden-orange firelight reflecting on the food, realistic smoke and heat distortion. "
        "Ultra-realistic food cinematography, cinematic lighting, shallow depth of field, dramatic warm tones, "
        "highly detailed textures, natural movement, realistic fire and smoke physics, 4K, 8K, professional DSLR camera, "
        "macro lens, smooth camera movement, photorealistic, immersive atmosphere."
    )
    
    ratio = "16:9"
    duration = 5
    model = "seedance_v2.5"
    
    print(f"=== KHỞI CHẠY TẠO VIDEO SEEDANCE 2.5 ===", flush=True)
    print(f"Nguồn prompt: https://youmind.com/vi-VN/video-prompts/bbq-food-cinematography-macro-11164", flush=True)
    print(f"Account: {account}", flush=True)
    print(f"Tỷ lệ: {ratio}, Thời lượng: {duration}s, Model: {model}", flush=True)
    print(f"Prompt:\n{prompt}\n", flush=True)
    
    start_time = time.time()
    try:
        result = await generate_video(
            account=account,
            prompt=prompt,
            ratio=ratio,
            duration=duration,
            model=model,
            timeout=300
        )
    except Exception as e:
        print(f"Lỗi khi dùng model {model}: {e}. Thử fallback về seedance_v2.0...", flush=True)
        model = "seedance_v2.0"
        result = await generate_video(
            account=account,
            prompt=prompt,
            ratio=ratio,
            duration=duration,
            model=model,
            timeout=300
        )
    
    elapsed = time.time() - start_time
    print(f"=== TẠO VIDEO THÀNH CÔNG trong {elapsed:.1f}s ===", flush=True)
    print(json.dumps(result, ensure_ascii=False, indent=2), flush=True)
    
    try:
        store = TaskStore("tasks.db")
        task_id = "video_seedance_" + str(int(time.time()))
        store.create(
            task_id=task_id,
            model=model,
            prompt=prompt,
            ratio=ratio,
            duration=duration,
            reference_images=None,
            api_key_hash=None,
            api_key_name="Seedance YouMind Runner",
        )
        video_url = f"/videos/{os.path.basename(result['local_path'])}"
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
