"""Video Stitcher & Post-Production Master Assembler for Blockbuster Studio."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import List, Optional

from .models import Scene, StoryProject


class VideoStitcher:
    """Conforms, stitches, and masters multi-scene videos into a cinematic blockbuster film."""

    def __init__(self, ffmpeg_bin: str = "ffmpeg"):
        self.ffmpeg_bin = ffmpeg_bin

    def conform_scene_clip(
        self,
        scene: Scene,
        output_clip_path: str,
        target_width: int = 1920,
        target_height: int = 1080,
        apply_cinemascope: bool = True
    ) -> str:
        """Conforms a scene video: replaces audio, conforms to 24fps, and applies 2.39:1 letterbox."""
        if not scene.rendered_video_path or not os.path.exists(scene.rendered_video_path):
            raise FileNotFoundError(f"Scene {scene.scene_number} has no rendered video file.")

        os.makedirs(os.path.dirname(os.path.abspath(output_clip_path)), exist_ok=True)
        
        # Build video filter: scale to target, set 24fps, and optionally letterbox to 2.39:1
        # In 1920x1080, 2.39:1 height is ~804px, leaving top and bottom black bars (138px each)
        if apply_cinemascope:
            bar_height = int((target_height - (target_width / 2.39)) / 2)
            vf = (
                f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,"
                f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black,"
                f"drawbox=y=0:h={bar_height}:color=black:t=fill,"
                f"drawbox=y={target_height - bar_height}:h={bar_height}:color=black:t=fill,"
                f"fps=24"
            )
        else:
            vf = (
                f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,"
                f"pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2:black,"
                f"fps=24"
            )

        cmd = [
            self.ffmpeg_bin, "-y",
            "-i", scene.rendered_video_path
        ]

        if scene.rendered_audio_path and os.path.exists(scene.rendered_audio_path):
            cmd.extend(["-i", scene.rendered_audio_path])
            cmd.extend([
                "-vf", vf,
                "-map", "0:v:0",
                "-map", "1:a:0",
                "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-c:a", "aac", "-b:a", "192k",
                "-t", str(scene.duration),
                output_clip_path
            ])
        else:
            cmd.extend([
                "-vf", vf,
                "-c:v", "libx264", "-preset", "medium", "-crf", "18",
                "-c:a", "aac", "-b:a", "192k",
                "-t", str(scene.duration),
                output_clip_path
            ])

        print(f"[VideoStitcher] Conforming Scene {scene.scene_number} -> {output_clip_path}")
        subprocess.run(cmd, capture_output=True, check=True)
        return output_clip_path

    def assemble_project(
        self,
        project: StoryProject,
        output_master_path: Optional[str] = None,
        apply_cinemascope: bool = True
    ) -> str:
        """Stitches all scenes together into a final Master Video."""
        if not project.scenes:
            raise ValueError("No scenes in project to assemble.")

        out_dir = Path(project.output_dir)
        out_dir.mkdir(parents=True, exist_ok=True)
        
        master_path = output_master_path or str(out_dir / f"{project.project_id}_master.mp4")
        temp_dir = out_dir / "conformed_scenes"
        temp_dir.mkdir(exist_ok=True)

        conformed_clips = []
        for scene in sorted(project.scenes, key=lambda s: s.scene_number):
            if not scene.rendered_video_path or not os.path.exists(scene.rendered_video_path):
                print(f"[VideoStitcher] Warning: Scene {scene.scene_number} has not been rendered yet! Skipping.")
                continue
            clip_path = str(temp_dir / f"conformed_scene_{scene.scene_number}.mp4")
            self.conform_scene_clip(scene, clip_path, apply_cinemascope=apply_cinemascope)
            conformed_clips.append(clip_path)

        if not conformed_clips:
            raise RuntimeError("No conformed scene clips available to assemble.")

        # Create concat text file
        concat_txt = str(temp_dir / "concat_list.txt")
        with open(concat_txt, "w", encoding="utf-8") as f:
            for p in conformed_clips:
                f.write(f"file '{os.path.abspath(p)}'\n")

        # Concat demuxer
        cmd = [
            self.ffmpeg_bin, "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", concat_txt,
            "-c:v", "copy",
            "-c:a", "copy",
            master_path
        ]
        print(f"[VideoStitcher] Assembling {len(conformed_clips)} scene(s) into Master Video: {master_path}")
        subprocess.run(cmd, capture_output=True, check=True)

        project.master_video_path = os.path.abspath(master_path)
        return project.master_video_path
