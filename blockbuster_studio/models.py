"""Data models for Blockbuster Studio pipeline."""
from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, List, Optional


class ShotType(str, Enum):
    EXTREME_WIDE = "Extreme Wide Shot (Establishing)"
    WIDE = "Wide Shot (Full Body)"
    MEDIUM = "Medium Cinematic Shot (Waist Up)"
    CLOSE_UP = "Dramatic Close-Up (Face/Emotion)"
    MACRO = "Macro Detail Shot"
    LOW_ANGLE = "Low-Angle Hero Shot"
    HIGH_ANGLE = "High-Angle Overhead Bird's Eye Shot"


class CameraMotion(str, Enum):
    PUSH_IN = "Slow Cinematic Push In"
    PULL_BACK = "Dramatic Pull Back Reveal"
    ORBIT_360 = "Dynamic 360-degree Orbit"
    TRACKING_FORWARD = "Steadicam Tracking Forward"
    PAN_HORIZONTAL = "Smooth Horizontal Pan"
    CRANE_DOWN = "Crane Boom Down Shot"
    STATIC_SUBTLE = "Handheld Subtle Drift"


class LightingStyle(str, Enum):
    GOLDEN_HOUR = "Golden hour warm sunbeams with volumetric dust"
    NEON_CYBER = "High-contrast neon cyan and magenta rim lighting with reflective puddles"
    GRITTY_DRAMA = "Moody chiaroscuro low-key cinematic shadows"
    DESERT_HAZE = "Scorching atmospheric heat distortion and deep amber haze"
    SCI_FI_CLEAN = "Sterile cold fluorescent lights, blue anamorphics and metallic reflections"
    WARM_INTERIOR = "Intimate candlelit amber glow with soft shadows"


@dataclass
class CharacterAnchor:
    """Persistent character anchor ensuring visual consistency across all scenes."""
    name: str
    gender: str = "female"
    age: str = "mid-20s"
    appearance: str = "Asian young woman, sharp expressive dark brown eyes, sleek shoulder-length black hair"
    wardrobe: str = "futuristic black tactical jacket with high collar, carbon fiber accents, silver minimalist pendant"
    style_keywords: str = "photorealistic, sharp facial focus, 8k resolution, cinematic 35mm film photography"
    image_path: Optional[str] = None

    def to_prompt_fragment(self) -> str:
        """Returns the consistent character description fragment to append into scene prompts."""
        return (
            f"{self.name}, {self.age} {self.gender}, {self.appearance}, wearing {self.wardrobe}. "
            f"{self.style_keywords}"
        )


@dataclass
class Scene:
    """Individual scene / shot specification."""
    scene_number: int
    title: str
    shot_type: ShotType = ShotType.MEDIUM
    camera_motion: CameraMotion = CameraMotion.PUSH_IN
    lighting: LightingStyle = LightingStyle.GOLDEN_HOUR
    action: str = ""
    environment: str = ""
    prompt: str = ""
    duration: int = 5  # Dola Seedance standard: 5s, 10s, 15s, 30s
    ratio: str = "16:9"
    model: str = "seedance_v2.0"  # seedance_v2.0 or seedance_v2.5
    
    # Audio elements
    voiceover_text: str = ""
    voice_name: str = "Samantha"  # macOS say voice: Samantha, Daniel, Karen, Linh (vi)
    sound_fx_description: str = ""
    
    # Render outputs
    rendered_video_path: Optional[str] = None
    rendered_audio_path: Optional[str] = None
    status: str = "pending"  # pending, rendering, completed, failed

    def build_seedance_prompt(self, character: Optional[CharacterAnchor] = None) -> str:
        """Constructs a high-impact Seedance cinematic prompt."""
        parts = []
        # Shot & camera
        parts.append(f"{self.shot_type.value}, {self.camera_motion.value}.")
        
        # Character anchor
        if character:
            parts.append(character.to_prompt_fragment())
            
        # Action & emotion
        if self.action:
            parts.append(f"Action: {self.action}.")
            
        # Environment & lighting
        if self.environment:
            parts.append(f"Setting: {self.environment}.")
        parts.append(f"Lighting & Atmosphere: {self.lighting.value}.")
        
        # Cinematic finish
        parts.append(
            "Cinematic composition, depth of field, anamorphic lens flare, "
            "color graded, motion blur, masterpiece 4K film still."
        )
        return " ".join(parts)


@dataclass
class StoryProject:
    """Master project containing narrative script, character anchor, and all scenes."""
    project_id: str
    title: str
    synopsis: str
    genre: str = "Cinematic Sci-Fi / Drama"
    character: CharacterAnchor = field(default_factory=lambda: CharacterAnchor(name="Protagonist"))
    scenes: List[Scene] = field(default_factory=list)
    output_dir: str = "blockbuster_output"
    music_track_path: Optional[str] = None
    master_video_path: Optional[str] = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> StoryProject:
        char_data = data.get("character", {})
        character = CharacterAnchor(**char_data)
        
        scenes_data = data.get("scenes", [])
        scenes = []
        for s in scenes_data:
            s_copy = dict(s)
            if "shot_type" in s_copy and isinstance(s_copy["shot_type"], str):
                try:
                    s_copy["shot_type"] = ShotType(s_copy["shot_type"])
                except ValueError:
                    s_copy["shot_type"] = ShotType.MEDIUM
            if "camera_motion" in s_copy and isinstance(s_copy["camera_motion"], str):
                try:
                    s_copy["camera_motion"] = CameraMotion(s_copy["camera_motion"])
                except ValueError:
                    s_copy["camera_motion"] = CameraMotion.PUSH_IN
            if "lighting" in s_copy and isinstance(s_copy["lighting"], str):
                try:
                    s_copy["lighting"] = LightingStyle(s_copy["lighting"])
                except ValueError:
                    s_copy["lighting"] = LightingStyle.GOLDEN_HOUR
            scenes.append(Scene(**s_copy))
            
        return cls(
            project_id=data["project_id"],
            title=data["title"],
            synopsis=data.get("synopsis", ""),
            genre=data.get("genre", "Cinematic Drama"),
            character=character,
            scenes=scenes,
            output_dir=data.get("output_dir", "blockbuster_output"),
            music_track_path=data.get("music_track_path"),
            master_video_path=data.get("master_video_path")
        )

    def save_json(self, file_path: str) -> None:
        p = Path(file_path)
        p.parent.mkdir(parents=True, exist_ok=True)
        with open(p, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, indent=2, ensure_ascii=False)

    @classmethod
    def load_json(cls, file_path: str) -> StoryProject:
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return cls.from_dict(data)
