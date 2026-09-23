import asyncio
import json
import os
import time
from video_worker_ui import resume_video
from store import TaskStore

async def resume():
    account = "vankhuong240_p185"
    conv_id = "38418042663557905"
    print(f"=== ĐANG LẤY VIDEO TỪ CONVERSATION {conv_id} ===", flush=True)
    res = await resume_video(account, conv_id, timeout=900)
    print("=== TẢI VIDEO THÀNH CÔNG ===", flush=True)
    print(json.dumps(res, indent=2, ensure_ascii=False), flush=True)
    
    # Save to tasks.db
    store = TaskStore("tasks.db")
    task_id = "video_gecko_ref_" + conv_id
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
    store.create(
        task_id=task_id,
        model="seedance-2.0",
        prompt=prompt,
        ratio="9:16",
        duration=10,
        reference_images=json.dumps(["/Users/apple/.gemini/antigravity/brain/3ccfaba1-56ac-4611-9cd2-54a20c17d8d1/.user_uploaded/media_1790098587693.png"]),
        api_key_hash=None,
        api_key_name="Character Reference Runner",
    )
    video_url = f"http://127.0.0.1:8000/videos/{os.path.basename(res['local_path'])}"
    store.update(
        task_id,
        status="completed",
        video_url=video_url,
        account=account,
        started_at=time.time() - 600,
        finished_at=time.time(),
        conversation_id=conv_id
    )
    print(f"Recorded into tasks.db as {task_id}", flush=True)

if __name__ == "__main__":
    asyncio.run(resume())
