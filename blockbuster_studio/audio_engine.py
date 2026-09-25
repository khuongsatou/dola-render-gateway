"""Cinematic Audio Engine for voiceover synthesis and sound mastering."""
from __future__ import annotations

import os
import subprocess
from pathlib import Path
from typing import Optional, List
from .models import Scene


class AudioEngine:
    """Manages character voice generation and cinematic soundscape mixing."""

    def __init__(self, ffmpeg_bin: str = "ffmpeg"):
        self.ffmpeg_bin = ffmpeg_bin

    def generate_voiceover(self, text: str, output_path: str, voice_name: str = "Samantha", speed_rate: int = 175) -> str:
        """Synthesizes high-fidelity voice audio using macOS speech engine or ffmpeg fallback."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        temp_aiff = output_path.replace(".mp3", ".aiff").replace(".aac", ".aiff")
        
        # Check if macOS 'say' command is available
        has_say = subprocess.run(["which", "say"], capture_output=True).returncode == 0
        if has_say and text.strip():
            cmd = ["say", "-v", voice_name, "-r", str(speed_rate), "-o", temp_aiff, text]
            res = subprocess.run(cmd, capture_output=True)
            if res.returncode == 0 and os.path.exists(temp_aiff):
                # Convert AIFF to MP3 via ffmpeg
                conv_cmd = [
                    self.ffmpeg_bin, "-y", "-i", temp_aiff,
                    "-ac", "2", "-ar", "44100", "-b:a", "192k",
                    output_path
                ]
                subprocess.run(conv_cmd, capture_output=True, check=True)
                if os.path.exists(temp_aiff) and temp_aiff != output_path:
                    os.remove(temp_aiff)
                print(f"[AudioEngine] Synthesized voiceover ({voice_name}): {output_path}")
                return output_path

        # Fallback: Generate subtle clean silent/tone audio if say fails or no text
        self.generate_cinematic_ambience(output_path, duration=5.0)
        return output_path

    def generate_cinematic_ambience(self, output_path: str, duration: float = 5.0) -> str:
        """Generates a deep, subtle cinematic sub-bass drone and atmospheric texture using ffmpeg."""
        os.makedirs(os.path.dirname(os.path.abspath(output_path)), exist_ok=True)
        cmd = [
            self.ffmpeg_bin, "-y",
            "-f", "lavfi", "-i", f"sine=frequency=55:duration={duration}",
            "-f", "lavfi", "-i", f"anoisesrc=duration={duration}:color=pink:amplitude=0.03",
            "-filter_complex",
            f"[1:a]lowpass=f=400[noise];[0:a][noise]amix=inputs=2:duration=first,afade=t=in:ss=0:d=0.5,afade=t=out:st={max(0.1, duration-0.5)}:d=0.5[out]",
            "-map", "[out]", "-ac", "2", "-ar", "44100", "-b:a", "192k",
            output_path
        ]
        subprocess.run(cmd, capture_output=True, check=True)
        print(f"[AudioEngine] Generated atmospheric drone ({duration}s): {output_path}")
        return output_path

    def prepare_scene_audio(self, scene: Scene, output_dir: str) -> str:
        """Creates combined voiceover + subtle sound bed for a specific scene."""
        os.makedirs(output_dir, exist_ok=True)
        target_path = os.path.join(output_dir, f"scene_{scene.scene_number}_audio.mp3")
        
        if scene.voiceover_text:
            voice_path = os.path.join(output_dir, f"scene_{scene.scene_number}_voice.mp3")
            self.generate_voiceover(scene.voiceover_text, voice_path, voice_name=scene.voice_name)
            
            # Mix voiceover with subtle background ambience timed to scene duration
            ambient_path = os.path.join(output_dir, f"scene_{scene.scene_number}_ambience.mp3")
            self.generate_cinematic_ambience(ambient_path, duration=float(scene.duration))
            
            # Combine voice + ambience
            cmd = [
                self.ffmpeg_bin, "-y",
                "-i", voice_path,
                "-i", ambient_path,
                "-filter_complex",
                "[0:a]volume=1.3[v];[1:a]volume=0.35[bg];[v][bg]amix=inputs=2:duration=first:dropout_transition=2[out]",
                "-map", "[out]",
                "-t", str(scene.duration),
                target_path
            ]
            subprocess.run(cmd, capture_output=True)
            if not os.path.exists(target_path):
                # If amix failed, use voice_path directly
                os.rename(voice_path, target_path)
        else:
            self.generate_cinematic_ambience(target_path, duration=float(scene.duration))

        scene.rendered_audio_path = target_path
        return target_path

    def generate_subtitles_srt(self, scenes: List[Scene], output_srt: str) -> str:
        """Generates standard SRT subtitle file matching scene timestamps."""
        os.makedirs(os.path.dirname(os.path.abspath(output_srt)), exist_ok=True)
        current_time = 0.0
        lines = []

        for i, s in enumerate(scenes, 1):
            if not s.voiceover_text:
                current_time += s.duration
                continue
                
            start_s = current_time + 0.3
            end_s = current_time + min(s.duration - 0.2, 4.5)
            
            def fmt_time(seconds: float) -> str:
                h = int(seconds // 3600)
                m = int((seconds % 3600) // 60)
                sec = int(seconds % 60)
                ms = int((seconds - int(seconds)) * 1000)
                return f"{h:02d}:{m:02d}:{sec:02d},{ms:03d}"

            lines.append(f"{i}")
            lines.append(f"{fmt_time(start_s)} --> {fmt_time(end_s)}")
            lines.append(f"{s.voiceover_text}\n")
            current_time += s.duration

        with open(output_srt, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
            
        print(f"[AudioEngine] Generated subtitle file: {output_srt}")
        return output_srt
