#!/usr/bin/env python3
"""CLI Runner for Blockbuster Studio.

Usage examples:
  # 1. Preview storyboard & generate all assets (Voice, Anchor card, Subtitles) without rendering:
  ./.venv/bin/python run_blockbuster.py --preset cyberpunk --mode prepare

  # 2. Dry-run asset preparation and test mastering using existing clips:
  ./.venv/bin/python run_blockbuster.py --preset vietnamese_legend --mode prepare

  # 3. Full End-to-End Blockbuster Production (Assets -> Dola Render -> 4K Cinemascope Stitch):
  ./.venv/bin/python run_blockbuster.py --preset cyberpunk --account vankhuong240_p185 --mode full

  # 4. Custom Storyboard from JSON:
  ./.venv/bin/python run_blockbuster.py --project-file my_project.json --mode full
"""

import argparse
import asyncio
import os
import sys

from blockbuster_studio import BlockbusterStudio, ScriptWriter, StoryProject


def parse_args():
    parser = argparse.ArgumentParser(description="Blockbuster Studio Cinematic Production Engine")
    parser.add_argument(
        "--preset",
        choices=["cyberpunk", "vietnamese_legend", "evolution", "human_dawn"],
        default="human_dawn",
        help="Use a built-in blockbuster preset storyboard",
    )
    parser.add_argument(
        "--project-file",
        type=str,
        default=None,
        help="Path to custom storyboard project JSON file",
    )
    parser.add_argument(
        "--account",
        type=str,
        default="vankhuong240_p185",
        help="Dola account username for Seedance rendering",
    )
    parser.add_argument(
        "--model",
        choices=["seedance_v2.0", "seedance_v2.5"],
        default="seedance_v2.0",
        help="Seedance model (default: seedance_v2.0 for fast reliable generation)",
    )
    parser.add_argument(
        "--mode",
        choices=["plan", "prepare", "render", "stitch", "full"],
        default="prepare",
        help=(
            "Execution mode: "
            "'plan' (print script & prompts), "
            "'prepare' (generate anchor card, voiceover, srt), "
            "'render' (render scenes via Dola), "
            "'stitch' (assemble rendered clips into master movie), "
            "'full' (run entire pipeline end-to-end)"
        ),
    )
    parser.add_argument(
        "--no-cinemascope",
        action="store_true",
        help="Disable 2.39:1 Cinemascope anamorphic letterboxing bars",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="blockbuster_output",
        help="Root directory for output assets and renders",
    )
    return parser.parse_args()


async def main():
    args = parse_args()
    studio = BlockbusterStudio(output_root=args.output_dir)

    # 1. Load or Generate Project
    if args.project_file and os.path.exists(args.project_file):
        print(f"📖 Loading custom project from {args.project_file}...")
        project = StoryProject.load_json(args.project_file)
    else:
        if args.preset == "vietnamese_legend":
            project = ScriptWriter.get_preset_vietnamese_legend()
        elif args.preset == "evolution":
            project = ScriptWriter.get_preset_evolution()
        elif args.preset == "human_dawn":
            project = ScriptWriter.get_preset_human_dawn()
        else:
            project = ScriptWriter.get_preset_cyberpunk_escape()

    # 2. Execution Modes
    if args.mode == "plan":
        print("\n=======================================================")
        print(f"🎬 STORYBOARD: {project.title}")
        print(f"Genre: {project.genre}")
        print(f"Synopsis: {project.synopsis}")
        print("-------------------------------------------------------")
        print(f"👤 Character Anchor: {project.character.name}")
        print(f"   Appearance: {project.character.appearance}")
        print(f"   Wardrobe: {project.character.wardrobe}")
        print("-------------------------------------------------------")
        for s in project.scenes:
            print(f"\n[Scene {s.scene_number}] {s.title} ({s.duration}s)")
            print(f"   Shot Type: {s.shot_type.value}")
            print(f"   Camera: {s.camera_motion.value}")
            print(f"   Lighting: {s.lighting.value}")
            print(f"   Voiceover: \"{s.voiceover_text}\" (Voice: {s.voice_name})")
            print(f"   Seedance Prompt:\n   {s.prompt}")
        print("=======================================================\n")
        return

    if args.mode == "prepare":
        studio.prepare_assets(project)
        print(f"💡 Assets ready in: {project.output_dir}")
        print(f"   To render on Dola, run with: --mode render or --mode full --account {args.account}")
        return

    if args.mode == "render":
        studio.prepare_assets(project)
        await studio.render_all_scenes(project, account=args.account, preferred_model=args.model)
        return

    if args.mode == "stitch":
        master_path = studio.assemble_master(
            project, apply_cinemascope=not args.no_cinemascope
        )
        print(f"🎉 Master Video Ready: {master_path}")
        return

    if args.mode == "full":
        master_path = await studio.run_full_production(
            project=project,
            account=args.account,
            preferred_model=args.model,
            apply_cinemascope=not args.no_cinemascope,
        )
        print(f"\n🎉 ALL STEPS COMPLETED!")
        print(f"Master Blockbuster Video: {master_path}")


if __name__ == "__main__":
    asyncio.run(main())
