"""Character consistency anchor manager for Blockbuster Studio."""
from __future__ import annotations

import os
from pathlib import Path
from typing import Optional
from PIL import Image, ImageDraw, ImageFont

from .models import CharacterAnchor


class CharacterManager:
    """Manages character identity, visual reference asset, and prompt consistency tokens."""

    def __init__(self, anchor: CharacterAnchor):
        self.anchor = anchor

    def ensure_reference_image(self, target_dir: str) -> str:
        """Verifies or generates a high-quality character reference anchor card image."""
        if self.anchor.image_path and os.path.exists(self.anchor.image_path):
            return os.path.abspath(self.anchor.image_path)

        os.makedirs(target_dir, exist_ok=True)
        fallback_path = os.path.join(target_dir, f"anchor_{self.anchor.name.lower().replace(' ', '_')}.png")
        
        if not os.path.exists(fallback_path):
            self._generate_anchor_card(fallback_path)
            
        self.anchor.image_path = os.path.abspath(fallback_path)
        return self.anchor.image_path

    def _generate_anchor_card(self, output_path: str) -> None:
        """Creates an authentic 16:9 3-Panel Character Sheet (Frontal Close-Up, Full Front, Full Back)."""
        width, height = 1920, 1080
        # Neutral cool light-grey seamless studio backdrop (RGB 42, 45, 52)
        img = Image.new("RGB", (width, height), color=(38, 41, 48))
        draw = ImageDraw.Draw(img)

        # Panel dividers
        panel_w = width // 3
        draw.line([(panel_w, 40), (panel_w, height - 40)], fill=(75, 82, 98), width=2)
        draw.line([(panel_w * 2, 40), (panel_w * 2, height - 40)], fill=(75, 82, 98), width=2)

        # Panel 1: FRONTAL CLOSE-UP (Left)
        p1_cx = panel_w // 2
        p1_cy = height // 2 - 20
        # Head silhouette
        draw.ellipse([p1_cx - 130, p1_cy - 180, p1_cx + 130, p1_cy + 110], fill=(62, 68, 82), outline=(120, 150, 210), width=3)
        draw.ellipse([p1_cx - 210, p1_cy + 100, p1_cx + 210, p1_cy + 420], fill=(48, 54, 66))
        draw.text((p1_cx, 60), "PANEL 1: FRONTAL CLOSE-UP", fill=(140, 185, 255), anchor="mm")
        draw.text((p1_cx, 95), "Identity & Face Geometry Lock", fill=(190, 200, 220), anchor="mm")

        # Panel 2: FULL-BODY FRONT (Center)
        p2_cx = panel_w + panel_w // 2
        # Head & full body
        draw.ellipse([p2_cx - 50, 180, p2_cx + 50, 290], fill=(62, 68, 82), outline=(120, 150, 210), width=2)
        # Torso & legs
        draw.rectangle([p2_cx - 90, 290, p2_cx + 90, 600], fill=(52, 58, 72))
        draw.rectangle([p2_cx - 85, 600, p2_cx - 15, 930], fill=(44, 50, 62))
        draw.rectangle([p2_cx + 15, 600, p2_cx + 85, 930], fill=(44, 50, 62))
        # Ground shadow line
        draw.ellipse([p2_cx - 140, 930, p2_cx + 140, 955], fill=(24, 26, 32))
        draw.text((p2_cx, 60), "PANEL 2: FULL-BODY FRONT", fill=(140, 185, 255), anchor="mm")
        draw.text((p2_cx, 95), "Wardrobe & Gear Lock", fill=(190, 200, 220), anchor="mm")

        # Panel 3: FULL-BODY BACK (Right)
        p3_cx = panel_w * 2 + panel_w // 2
        # Head & backpack silhouette
        draw.ellipse([p3_cx - 50, 180, p3_cx + 50, 290], fill=(56, 62, 74), outline=(100, 130, 180), width=2)
        # Backpack feature
        draw.rectangle([p3_cx - 80, 310, p3_cx + 80, 560], fill=(68, 55, 45), outline=(130, 100, 80), width=2)
        draw.rectangle([p3_cx - 90, 290, p3_cx + 90, 600], outline=(60, 66, 80), width=1)
        draw.rectangle([p3_cx - 85, 600, p3_cx - 15, 930], fill=(44, 50, 62))
        draw.rectangle([p3_cx + 15, 600, p3_cx + 85, 930], fill=(44, 50, 62))
        # Ground shadow line aligned
        draw.ellipse([p3_cx - 140, 930, p3_cx + 140, 955], fill=(24, 26, 32))
        draw.text((p3_cx, 60), "PANEL 3: FULL-BODY BACK", fill=(140, 185, 255), anchor="mm")
        draw.text((p3_cx, 95), "Backpack & Turnaround Lock", fill=(190, 200, 220), anchor="mm")

        # Master Bottom Header
        draw.rectangle([40, height - 75, width - 40, height - 25], fill=(28, 30, 36), outline=(65, 72, 88), width=1)
        meta_label = f"CHARACTER ANCHOR: {self.anchor.name.upper()} | {self.anchor.age} {self.anchor.gender.upper()} | {self.anchor.appearance[:70]}..."
        draw.text((width // 2, height - 50), meta_label, fill=(230, 235, 245), anchor="mm")

        img.save(output_path, "PNG")
        print(f"[CharacterManager] Generated 3-Panel Reference Sheet (16:9): {output_path}")

    def get_reference_image_paths(self) -> list[str]:
        """Returns the list of reference image paths for Dola upload."""
        if self.anchor.image_path and os.path.exists(self.anchor.image_path):
            return [os.path.abspath(self.anchor.image_path)]
        return []
