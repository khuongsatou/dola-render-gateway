"""Blockbuster Studio Pipeline Orchestrator with Professional Vault Hierarchy."""
from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import shutil
import time
from pathlib import Path
from typing import Optional

from .audio_engine import AudioEngine
from .character import CharacterManager
from .models import Scene, StoryProject
from .video_stitcher import VideoStitcher

try:
    from video_worker_ui import generate_video
    from store import TaskStore
except ImportError:
    generate_video = None
    TaskStore = None


def slugify(text: str) -> str:
    """Converts a string into a clean filesystem slug."""
    text = re.sub(r"[^\w\s-]", "", text).strip().lower()
    return re.sub(r"[-\s]+", "_", text)


class BlockbusterStudio:
    """End-to-End Orchestrator for Multi-Scene Blockbuster Film Production.
    
    Adheres strictly to the 4K Blockbuster Breakdown Vault Standard:
    - metadata/
    - assets/ (characters, props, locations)
    - scenes/ (drafts_1080p, final_4k)
    - timeline_master/ (voiceovers, subtitles, master.mp4)
    """

    def __init__(self, output_root: str = "blockbuster_output"):
        self.output_root = output_root
        self.audio_engine = AudioEngine()
        self.stitcher = VideoStitcher()

    def _init_vault_directories(self, project: StoryProject) -> dict[str, str]:
        """Creates the full professional vault directory tree."""
        proj_dir = os.path.join(self.output_root, project.project_id)
        dirs = {
            "root": proj_dir,
            "metadata": os.path.join(proj_dir, "metadata"),
            "assets_chars": os.path.join(proj_dir, "assets", "characters"),
            "assets_props": os.path.join(proj_dir, "assets", "props"),
            "assets_locs": os.path.join(proj_dir, "assets", "locations"),
            "scenes": os.path.join(proj_dir, "scenes"),
            "timeline": os.path.join(proj_dir, "timeline_master"),
            "voiceovers": os.path.join(proj_dir, "timeline_master", "voiceovers"),
            "subtitles": os.path.join(proj_dir, "timeline_master", "subtitles"),
        }
        for d in dirs.values():
            os.makedirs(d, exist_ok=True)
            
        # Create scene subfolders
        for scene in project.scenes:
            slug = slugify(scene.title or f"scene_{scene.scene_number}")
            scene_dir = os.path.join(dirs["scenes"], f"scene_{scene.scene_number:02d}_{slug}")
            os.makedirs(os.path.join(scene_dir, "drafts_1080p"), exist_ok=True)
            os.makedirs(os.path.join(scene_dir, "final_4k"), exist_ok=True)
            dirs[f"scene_{scene.scene_number}"] = scene_dir
            
        project.output_dir = proj_dir
        return dirs

    def _record_asset_manifest(self, metadata_dir: str, asset_record: dict) -> None:
        """Appends an asset entry to asset_manifest.jsonl."""
        manifest_path = os.path.join(metadata_dir, "asset_manifest.jsonl")
        with open(manifest_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(asset_record, ensure_ascii=False) + "\n")

    def prepare_assets(self, project: StoryProject) -> dict[str, str]:
        """Step 1 & Step 2: Prepare character anchor, voiceover audio, and project structure."""
        dirs = self._init_vault_directories(project)
        meta_dir = dirs["metadata"]

        print(f"\n=======================================================")
        print(f"🎬 BLOCKBUSTER STUDIO: PREPARING PRODUCTION ASSETS")
        print(f"Project: {project.title} ({project.genre})")
        print(f"Vault Directory: {dirs['root']}")
        print(f"=======================================================")

        # 1. Anchor Character Consistency (3-Panel Sheet)
        char_mgr = CharacterManager(project.character)
        anchor_img = char_mgr.ensure_reference_image(dirs["assets_chars"])
        print(f"👤 Character Anchor Locked: {project.character.name}")
        print(f"   Anchor Image (3-Panel Sheet): {anchor_img}")

        # Compute hash and record anchor to asset manifest
        try:
            with open(anchor_img, "rb") as f:
                sha = hashlib.sha256(f.read()).hexdigest()
            self._record_asset_manifest(meta_dir, {
                "id": f"anchor_{slugify(project.character.name)}",
                "folder_path": "assets/characters",
                "local_path": anchor_img,
                "sha256": sha,
                "type": "character_sheet_3panel",
                "created_at": time.time()
            })
        except Exception:
            pass

        # 2. Build Seedance Prompts & Generate Voiceovers
        for scene in project.scenes:
            if not scene.prompt:
                scene.prompt = scene.build_seedance_prompt(project.character)
            
            # Generate voiceover audio track for scene
            audio_path = self.audio_engine.prepare_scene_audio(scene, dirs["voiceovers"])
            scene.rendered_audio_path = audio_path
            print(f"🔊 Scene {scene.scene_number} Audio Ready: '{scene.voiceover_text or 'Atmospheric Drone'}' -> {audio_path}")

        # 3. Generate Subtitles
        srt_path = os.path.join(dirs["subtitles"], f"{project.project_id}_subtitles.srt")
        self.audio_engine.generate_subtitles_srt(project.scenes, srt_path)

        # 4. Save metadata
        project.save_json(os.path.join(meta_dir, "project.json"))
        
        # Save folder map
        with open(os.path.join(meta_dir, "folder_map.json"), "w", encoding="utf-8") as f:
            json.dump({k: os.path.relpath(v, dirs["root"]) for k, v in dirs.items()}, f, indent=2)

        print(f"✅ Assets preparation complete. Metadata saved to {meta_dir}/project.json\n")
        return dirs

    async def render_scene(
        self,
        project: StoryProject,
        scene: Scene,
        account: str,
        preferred_model: str = "seedance_v2.0"
    ) -> str:
        """Step 3: Render individual scene using Dola Seedance with Character Anchor."""
        if generate_video is None:
            raise RuntimeError("video_worker_ui is not available in current environment.")

        dirs = self._init_vault_directories(project)
        slug = slugify(scene.title or f"scene_{scene.scene_number}")
        scene_dir = dirs.get(f"scene_{scene.scene_number}", dirs["scenes"])
        final_dir = os.path.join(scene_dir, "final_4k")

        print(f"\n🎥 [Rendering Scene {scene.scene_number}/{len(project.scenes)}] {scene.title}")
        print(f"   Shot: {scene.shot_type.value} | Camera: {scene.camera_motion.value}")
        print(f"   Prompt: {scene.prompt[:120]}...")

        char_mgr = CharacterManager(project.character)
        ref_images = char_mgr.get_reference_image_paths()
        if ref_images:
            print(f"   Using Reference Anchor: {ref_images[0]}")

        model = preferred_model
        start_time = time.time()
        scene.status = "rendering"

        try:
            result = await generate_video(
                account=account,
                prompt=scene.prompt,
                ratio=scene.ratio,
                duration=scene.duration,
                model=model,
                timeout=300,
                reference_image_paths=ref_images if ref_images else None
            )
        except Exception as e:
            if model != "seedance_v2.0":
                print(f"⚠️ Model {model} failed ({e}), falling back to seedance_v2.0...")
                model = "seedance_v2.0"
                result = await generate_video(
                    account=account,
                    prompt=scene.prompt,
                    ratio=scene.ratio,
                    duration=scene.duration,
                    model=model,
                    timeout=300,
                    reference_image_paths=ref_images if ref_images else None
                )
            else:
                scene.status = "failed"
                raise e

        local_path = result.get("local_path")
        if not local_path or not os.path.exists(local_path):
            raise FileNotFoundError(f"Generated video not found at {local_path}")

        # Copy/move into scene's final_4k vault folder
        dest_filename = f"sc{scene.scene_number:02d}_{slug}_final.mp4"
        dest_path = os.path.join(final_dir, dest_filename)
        shutil.copy2(local_path, dest_path)

        scene.rendered_video_path = os.path.abspath(dest_path)
        scene.status = "completed"
        scene.model = model
        print(f"✅ Scene {scene.scene_number} stored in vault: {scene.rendered_video_path} ({time.time() - start_time:.1f}s)")

        # Record to metadata asset manifest
        try:
            with open(dest_path, "rb") as f:
                sha = hashlib.sha256(f.read()).hexdigest()
            self._record_asset_manifest(dirs["metadata"], {
                "id": f"video_sc{scene.scene_number:02d}",
                "folder_path": f"scenes/scene_{scene.scene_number:02d}_{slug}/final_4k",
                "local_path": dest_path,
                "sha256": sha,
                "model": model,
                "prompt": scene.prompt,
                "created_at": time.time()
            })
        except Exception:
            pass

        # Update local task store if available
        if TaskStore:
            try:
                store = TaskStore("tasks.db")
                task_id = f"blockbuster_{project.project_id}_sc{scene.scene_number}"
                store.create(
                    task_id=task_id,
                    model=model,
                    prompt=scene.prompt,
                    ratio=scene.ratio,
                    duration=scene.duration,
                    reference_images=ref_images,
                    api_key_hash=None,
                    api_key_name="Blockbuster Studio",
                )
                store.update(
                    task_id,
                    status="completed",
                    video_url=f"/videos/{os.path.basename(dest_path)}",
                    account=account,
                    started_at=start_time,
                    finished_at=time.time(),
                    conversation_id=result.get("conversation_id")
                )
            except Exception as e:
                print(f"Notice: tasks.db update skipped: {e}")

        # Save updated project json
        project.save_json(os.path.join(dirs["metadata"], "project.json"))
        return scene.rendered_video_path

    async def render_all_scenes(
        self,
        project: StoryProject,
        account: str,
        preferred_model: str = "seedance_v2.0"
    ) -> None:
        """Renders all scenes in sequence."""
        for scene in project.scenes:
            if scene.status == "completed" and scene.rendered_video_path and os.path.exists(scene.rendered_video_path):
                print(f"⏩ Scene {scene.scene_number} already rendered: {scene.rendered_video_path}")
                continue
            await self.render_scene(project, scene, account=account, preferred_model=preferred_model)

    def assemble_master(self, project: StoryProject, apply_cinemascope: bool = True) -> str:
        """Step 5: Conforms all clips, synchronizes audio, and stitches final master movie."""
        print(f"\n🎞️ =======================================================")
        print(f"🎬 MASTERING & STITCHING FINAL BLOCKBUSTER TIMELINE")
        print(f"=======================================================")
        dirs = self._init_vault_directories(project)
        master_output_path = os.path.join(dirs["timeline"], f"{project.project_id}_master_2.39_4k.mp4")

        master_path = self.stitcher.assemble_project(
            project=project,
            output_master_path=master_output_path,
            apply_cinemascope=apply_cinemascope
        )
        print(f"\n🏆 PRODUCTION COMPLETE!")
        print(f"Master Video Output: {master_path}")
        project.master_video_path = master_path
        project.save_json(os.path.join(dirs["metadata"], "project.json"))
        return master_path

    async def run_full_production(
        self,
        project: StoryProject,
        account: str,
        preferred_model: str = "seedance_v2.0",
        apply_cinemascope: bool = True
    ) -> str:
        """Executes the entire end-to-end blockbuster film pipeline."""
        self.prepare_assets(project)
        await self.render_all_scenes(project, account=account, preferred_model=preferred_model)
        return self.assemble_master(project, apply_cinemascope=apply_cinemascope)
