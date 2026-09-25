"""Scriptwriter & Storyboard Planner for Blockbuster Studio."""
from __future__ import annotations

import os
import time
from typing import List, Optional
from .models import (
    CameraMotion,
    CharacterAnchor,
    LightingStyle,
    Scene,
    ShotType,
    StoryProject,
)


class ScriptWriter:
    """Creates structured multi-scene storyboards with cinematic pacing and prompts."""

    @staticmethod
    def get_preset_cyberpunk_escape() -> StoryProject:
        """Preset inspired by high-stakes sci-fi blockbuster breakdowns."""
        character = CharacterAnchor(
            name="Kaelen",
            gender="female",
            age="26",
            appearance="athletic Asian woman with sharp gaze, silver ear communicator, sleek bob haircut",
            wardrobe="matte black tactical exo-jacket with cyan luminescent seams, fingerless gloves",
            style_keywords="hyper-detailed cyberpunk realism, cinematic 35mm lens, sharp facial focus, 8K"
        )
        
        scenes = [
            Scene(
                scene_number=1,
                title="The Awakening in the Neon Rain",
                shot_type=ShotType.CLOSE_UP,
                camera_motion=CameraMotion.PUSH_IN,
                lighting=LightingStyle.NEON_CYBER,
                action="slowly opens her eyes, rain droplets trickling down her face, breathing heavily as neon signs flicker in her dark pupils",
                environment="rain-drenched narrow alleyway in Neo-Tokyo, steaming sewer grates, towering holographic billboards",
                duration=5,
                voiceover_text="They thought they erased me. But the code survived.",
                voice_name="Samantha",
                sound_fx_description="Heavy torrential rain, distant sirens, electronic hum"
            ),
            Scene(
                scene_number=2,
                title="The Pursuit Through the Alley",
                shot_type=ShotType.MEDIUM,
                camera_motion=CameraMotion.TRACKING_FORWARD,
                lighting=LightingStyle.NEON_CYBER,
                action="sprints forward with intense determination, leaping over metallic barricades while glancing back at searchlight beams",
                environment="cluttered cyberpunk market, neon signs in red and blue reflecting on wet asphalt",
                duration=5,
                voiceover_text="Three seconds to reach the mainframe. No turning back.",
                voice_name="Samantha",
                sound_fx_description="Fast heavy footsteps splashing on puddles, drone buzzing overhead"
            ),
            Scene(
                scene_number=3,
                title="The Quantum Core Overlook",
                shot_type=ShotType.WIDE,
                camera_motion=CameraMotion.PULL_BACK,
                lighting=LightingStyle.SCI_FI_CLEAN,
                action="stands at the edge of a high-tech skyscraper rooftop, holding a glowing cyan data-shard, wind whipping through her hair",
                environment="futuristic megalopolis vista under dark storm clouds, flying vehicles streaming across skyways",
                duration=5,
                voiceover_text="Now, the city belongs to the truth.",
                voice_name="Samantha",
                sound_fx_description="Deep cinematic bass drop, wind gusts, electronic chime"
            )
        ]

        # Build prompt for each scene
        for s in scenes:
            s.prompt = s.build_seedance_prompt(character)

        return StoryProject(
            project_id=f"proj_cyberpunk_{int(time.time())}",
            title="Protocol 09: Neon Escape",
            synopsis="A renegade agent awakens in a rainy neon metropolis to upload the truth before hunter drones catch her.",
            genre="Cyberpunk Action Thriller",
            character=character,
            scenes=scenes
        )

    @staticmethod
    def get_preset_vietnamese_legend() -> StoryProject:
        """Preset inspired by Vietnamese ancient warrior cinematic drama."""
        character = CharacterAnchor(
            name="An Linh",
            gender="female",
            age="24",
            appearance="fierce young Vietnamese warrior woman, focused dark brown eyes, long black hair braided with jade beads",
            wardrobe="traditional lacquered crimson and gold martial robes, embroidered phoenix motifs, silver dragon hairpin",
            style_keywords="ancient Vietnamese historical epic, cinematic photography, warm natural rim lighting, 8k masterpiece"
        )
        
        scenes = [
            Scene(
                scene_number=1,
                title="The Ancient Temple Awakening",
                shot_type=ShotType.CLOSE_UP,
                camera_motion=CameraMotion.PUSH_IN,
                lighting=LightingStyle.GOLDEN_HOUR,
                action="raises her head slowly, morning sunlight filtering through ancient banyan trees illuminating her warrior gaze",
                environment="ancient moss-covered stone temple courtyard in Ninh Binh, misty karst mountains in background",
                duration=5,
                voiceover_text="Ngàn năm sông núi, lời thề non sông không bao giờ phai.",
                voice_name="Linh",
                sound_fx_description="Gentle breeze rustling leaves, distant temple gong chime"
            ),
            Scene(
                scene_number=2,
                title="The River Battlefield",
                shot_type=ShotType.MEDIUM,
                camera_motion=CameraMotion.TRACKING_FORWARD,
                lighting=LightingStyle.GRITTY_DRAMA,
                action="draws a glowing ancestral bronze sword with swift grace, red silk banner billowing behind her in the battle mist",
                environment="wide misty riverbank with ancient wooden war boats floating under dramatic storm clouds",
                duration=5,
                voiceover_text="Thanh kiếm này khắc ghi danh dự của tiền nhân.",
                voice_name="Linh",
                sound_fx_description="Metallic sword unsheathing sound, thunder roll"
            ),
            Scene(
                scene_number=3,
                title="The Mountain Summit Triumph",
                shot_type=ShotType.WIDE,
                camera_motion=CameraMotion.PULL_BACK,
                lighting=LightingStyle.GOLDEN_HOUR,
                action="stands atop a magnificent limestone peak, looking out over the emerald valley as golden dawn breaks through clouds",
                environment="breathtaking panoramic limestone karst mountain peaks, lush rice fields glistening below in morning sun",
                duration=5,
                voiceover_text="Bình minh đã rạng trên quê hương.",
                voice_name="Linh",
                sound_fx_description="Epic cinematic crescendo, eagle cry in distance"
            )
        ]

        for s in scenes:
            s.prompt = s.build_seedance_prompt(character)

        return StoryProject(
            project_id=f"proj_legend_{int(time.time())}",
            title="Huyền Sử Núi Rồng (Dragon Mountain Epic)",
            synopsis="Nữ tướng An Linh thức tỉnh tại ngôi đền cổ và lĩnh mệnh bảo vệ giang sơn trên đỉnh núi thiêng.",
            genre="Vietnamese Historical Martial Epic",
            character=character,
            scenes=scenes
        )

    @staticmethod
    def get_preset_evolution() -> StoryProject:
        """Blockbuster project on EVOLUTION inspired by 4K Blockbuster Breakdown."""
        char_image = os.path.abspath("blockbuster_output/proj_evolution/assets/characters/character_sheet_3panel_aria.jpg")
        character = CharacterAnchor(
            name="Aria Vane",
            gender="female",
            age="27",
            appearance="athletic evolved human woman, sharp amber eyes, intricate glowing teal bioluminescent neural pathways running along her jawline and temple, braided dark hair",
            wardrobe="sleek matte carbon-nanofiber exo-suit with biomechanical spinal conduit, illuminated teal seam accents, tactical utility belt",
            style_keywords="masterpiece cinematic photorealism, documentary-grade film realism, sharp facial focus, 35mm anamorphic lens, 8K",
            image_path=char_image if os.path.exists(char_image) else None
        )

        scenes = [
            Scene(
                scene_number=1,
                title="The Primordial Awakening",
                shot_type=ShotType.CLOSE_UP,
                camera_motion=CameraMotion.PUSH_IN,
                lighting=LightingStyle.NEON_CYBER,
                action="slowly opens her piercing amber eyes in the deep abyss as bioluminescent neural circuits flare to life across her skin, reflecting off floating ocean particles",
                environment="ancient bioluminescent deep oceanic trench, glowing cyan hydrothermal vents, shimmering microscopic organisms drifting through dark water",
                duration=5,
                voiceover_text="Trước khi có ký ức, trước khi có ngôn từ, sự sống bắt đầu từ một tia lửa phản nghịch.",
                voice_name="Linh",
                sound_fx_description="Sub-bass deep ocean rumble, delicate bioluminescent chimes, fluid bubbles"
            ),
            Scene(
                scene_number=2,
                title="The Genesis Shard Catalyst",
                shot_type=ShotType.MEDIUM,
                camera_motion=CameraMotion.TRACKING_FORWARD,
                lighting=LightingStyle.SCI_FI_CLEAN,
                action="reaches forward with carbon-fiber gauntlet hand to grasp the glowing Genesis Shard, ancient fractal DNA spirals swirling inside the crystal matrix as her body adapts",
                environment="ancient volcanic obsidian cavern embedded with alien crystal formations, volumetric mist rolling across jagged stone floor",
                duration=5,
                voiceover_text="Chúng ta sinh ra không phải để mãi giam mình trong chiếc lồng hữu cơ chật hẹp.",
                voice_name="Linh",
                sound_fx_description="High-voltage energy hum, crystal resonance, swift aerodynamic movement"
            ),
            Scene(
                scene_number=3,
                title="The Ascent Through the Spire",
                shot_type=ShotType.WIDE,
                camera_motion=CameraMotion.CRANE_DOWN,
                lighting=LightingStyle.GOLDEN_HOUR,
                action="sprints along the narrow cliff ledge toward the colossal crystal spire, energy arcs rippling from her spine conduit as dawn breaks over the alien horizon",
                environment="breathtaking panoramic alien landscape of black basalt cliffs, towering crystalline monolith in background under a fiery cosmic nebula",
                duration=5,
                voiceover_text="Mỗi một lần tuyệt chủng, chỉ là gia tốc đẩy ta về phía bình minh kế tiếp.",
                voice_name="Linh",
                sound_fx_description="Epic cinematic orchestral swell, wind rushing past camera, thunderclap"
            ),
            Scene(
                scene_number=4,
                title="Cosmic Transcendence",
                shot_type=ShotType.WIDE,
                camera_motion=CameraMotion.PULL_BACK,
                lighting=LightingStyle.SCI_FI_CLEAN,
                action="stands at the pinnacle of the quantum spire holding the crystal aloft, as a column of celestial light erupts into the sky, her silhouette beginning to dissolve into pure luminous energy",
                environment="summit of the colossal quantum spire, swirling cosmic nebula in deep violet and gold, stars wheeling overhead",
                duration=5,
                voiceover_text="Và giờ đây, chúng ta hòa mình vào các vì sao.",
                voice_name="Linh",
                sound_fx_description="Monumental cinematic sub-bass drop, celestial choir, harmonic resonant ring"
            )
        ]

        for s in scenes:
            s.prompt = s.build_seedance_prompt(character)

        return StoryProject(
            project_id="proj_evolution",
            title="CHRONO-GENESIS: EVOLUTION BEYOND ORGANIC",
            synopsis="From the primordial oceanic abyss to the pinnacle of the quantum spire, Aria Vane unlocks the Genesis Shard to trigger the final transcendent leap of human evolution.",
            genre="Cinematic Sci-Fi Epic",
            character=character,
            scenes=scenes,
            output_dir="blockbuster_output/proj_evolution"
        )

    @staticmethod
    def get_preset_human_dawn() -> StoryProject:
        """Historical epic project on Primitive Human Evolution, Fire, and the First Level Up."""
        char_image = os.path.abspath("blockbuster_output/proj_human_dawn/assets/characters/character_sheet_3panel_kael.jpg")
        character = CharacterAnchor(
            name="Kael",
            gender="male",
            age="28",
            appearance="muscular primitive Homo sapiens hunter, sun-weathered bronze skin, piercing intelligent dark eyes, ash tribal markings on cheekbones, rugged facial stubble, wild dark hair tied back with rawhide",
            wardrobe="stitched deer-pelt loincloth, raw leather wrist wraps, predator tooth necklace, leather knife sheath",
            style_keywords="museum-grade documentary realism, photorealistic 35mm anamorphic film still, sharp facial focus, 8K",
            image_path=char_image if os.path.exists(char_image) else None
        )

        scenes = [
            Scene(
                scene_number=1,
                title="Hang Đá & Nỗi Sợ Dã Thú",
                shot_type=ShotType.CLOSE_UP,
                camera_motion=CameraMotion.PUSH_IN,
                lighting=LightingStyle.GRITTY_DRAMA,
                action="huddles shivering inside a dark limestone cave, hugging his knees tightly, breathing heavily while staring out into the pitch-black jungle storm where shadows of predatory beasts lurk outside",
                environment="primal tropical rainforest drenched in torrential rain, jagged cave mouth, thick misty gloom",
                duration=5,
                voiceover_text="Trước khi nhân loại viết nên lịch sử, chúng ta từng là sinh vật yếu ớt nhất trên hành tinh này. Suốt hàng trăm ngàn năm trong bóng tối rừng già, nỗi sợ là thứ duy nhất giữ tổ tiên ta sống sót.",
                voice_name="Linh",
                sound_fx_description="Heavy tropical rain on jungle leaves, distant thunder rumble, fearful breathing, low predator growl"
            ),
            Scene(
                scene_number=2,
                title="Cuộc Kiếm Tìm Tuyệt Vọng",
                shot_type=ShotType.MEDIUM,
                camera_motion=CameraMotion.TRACKING_FORWARD,
                lighting=LightingStyle.DESERT_HAZE,
                action="forages cautiously through wet mud and fallen leaves beneath ancient banyan roots, pausing to look up through the colossal canopy with a hungry, longing gaze",
                environment="primordial tropical rainforest, colossal ferns, winding mossy vines, thick morning mist rolling across the jungle floor",
                duration=5,
                voiceover_text="Mỗi buổi sớm thức dậy đều là một canh bạc sinh tử. Chúng ta bới tìm từng ngọn cỏ, rễ cây để chống lại cơn đói cồn cào, trong khi cái chết luôn rình rập sau từng bụi rậm.",
                voice_name="Linh",
                sound_fx_description="Barefoot squelching in mud, tropical jungle insect hums, hollow stomach rumble, breaking twigs"
            ),
            Scene(
                scene_number=3,
                title="Cú Sét Giáng & Lửa Bùng Cháy",
                shot_type=ShotType.WIDE,
                camera_motion=CameraMotion.PUSH_IN,
                lighting=LightingStyle.NEON_CYBER,
                action="a massive blinding bolt of lightning strikes a colossal ancient tree, splitting the trunk with explosive force, sparks and glowing embers showering the damp ground as roaring orange flames erupt into the pouring rain",
                environment="prehistoric tropical forest under dramatic dark purple storm clouds",
                duration=5,
                voiceover_text="Rồi một ngày, bầu trời gầm lên cơn thịnh nộ. Một tia sét xé toạc màn đêm, ban tặng ngọn lửa đầu tiên xua tan bóng lạnh.",
                voice_name="Linh",
                sound_fx_description="Deafening thunder strike, wood splintering crack, roaring fire eruption, howling storm wind"
            ),
            Scene(
                scene_number=4,
                title="Bắt Lấy Ngọn Lửa Thiêng",
                shot_type=ShotType.CLOSE_UP,
                camera_motion=CameraMotion.ORBIT_360,
                lighting=LightingStyle.GOLDEN_HOUR,
                action="kneels beside the burning tree trunk, extending a dry pine branch into the embers; bright orange flames burst onto the branch creating a blazing torch; he slowly stands upright, raising the torch high, his face illuminated by dancing golden flames",
                environment="steaming rainforest ground littered with wet leaves, glowing embers floating in the humid night air",
                duration=5,
                voiceover_text="Muông thú nhìn thấy lửa liền khiếp đảm tháo chạy. Chỉ có một sinh vật duy nhất dám dừng lại và bước tới gần. Bàn tay con người bắt lấy ngọn lửa thiêng, bóng đêm vĩnh cửu chính thức lùi bước.",
                voice_name="Linh",
                sound_fx_description="Crackling pine resin, sharp intake of awe, torch flames flapping in wind, predator retreating growl"
            ),
            Scene(
                scene_number=5,
                title="Bậc Thầy Ghè Đá & Chế Tác",
                shot_type=ShotType.MACRO,
                camera_motion=CameraMotion.STATIC_SUBTLE,
                lighting=LightingStyle.GOLDEN_HOUR,
                action="strikes a hard hammerstone against black obsidian flint, chipping away razor-sharp flakes with skilled precision; cut to him tightly lashing the sharp stone axe-head onto a hardwood branch with rawhide cords",
                environment="sunlit jungle clearing, colossal ferns, morning dew glistening on foliage",
                duration=5,
                voiceover_text="Nhưng lửa mới chỉ là sự khởi đầu. Chúng ta học cách ghè đẽo hòn đá vô tri, biến nó thành lưỡi rìu sắc bén, biến cành cây thành ngọn giáo săn. Trật tự tự nhiên bắt đầu đảo lộn.",
                voice_name="Linh",
                sound_fx_description="Sharp stone chipping clink, flaking obsidian, creaking rawhide sinew tension, axe swish"
            ),
            Scene(
                scene_number=6,
                title="Đảo Ngược Vị Thế: Thợ Săn Rừng Sâu",
                shot_type=ShotType.LOW_ANGLE,
                camera_motion=CameraMotion.TRACKING_FORWARD,
                lighting=LightingStyle.GOLDEN_HOUR,
                action="leads three athletic primitive hunters sprinting across a tropical riverbank, holding a raised obsidian spear ready to strike with lethal coordination and fierce hunter confidence",
                environment="wide tropical riverbed, ancient karst limestone peaks rising in mist, lush jungle foliage lining the banks",
                duration=5,
                voiceover_text="Kẻ từng là con mồi nay đã trở thành thợ săn. Bằng công cụ và trí tuệ tập thể, chúng ta chinh phục những cánh rừng rậm rạp nhất, không còn đơn độc trước thiên nhiên.",
                voice_name="Linh",
                sound_fx_description="Rhythmic thudding footsteps on river stones, primitive hunting calls, spear whistle through air, deep tribal drums"
            ),
            Scene(
                scene_number=7,
                title="Bộ Tộc Khởi Sinh & Tranh Khắc Đá",
                shot_type=ShotType.MEDIUM,
                camera_motion=CameraMotion.PAN_HORIZONTAL,
                lighting=LightingStyle.WARM_INTERIOR,
                action="women and elders gather around a large communal cooking fire sharing roasted meat, while in background a hunter uses charcoal to paint running deer and fire symbols on a smooth limestone cave wall",
                environment="prehistoric river valley settlement, timber shelters, lush jungle backdrop under deep twilight sky",
                duration=5,
                voiceover_text="Ngọn lửa gom những cá thể cô độc lại thành một bộ tộc. Chúng ta chia nhau miếng thịt chín, sưởi ấm cho nhau, và bắt đầu vẽ lên vách đá ước mơ của mình: Con người đã tồn tại nơi đây.",
                voice_name="Linh",
                sound_fx_description="Children soft babble, crackling firewood, charcoal scraping on limestone, distant river murmur"
            ),
            Scene(
                scene_number=8,
                title="Đỉnh Cao Vách Đá — BƯỚC LÊN CẤP VĨ ĐẠI",
                shot_type=ShotType.HIGH_ANGLE,
                camera_motion=CameraMotion.PULL_BACK,
                lighting=LightingStyle.GOLDEN_HOUR,
                action="stands victorious at the pinnacle of a colossal limestone cliff overhang, thrusting a blazing pine-torch triumphantly into the twilight sky, while across the immense river valley below, hundreds of campfires ignite like stars on Earth",
                environment="panoramic prehistoric river valley at sunset with fiery amber clouds, smoke plumes rising, transitioning toward cosmic starlight perspective",
                duration=5,
                voiceover_text="Từ một que củi bén lửa trong giông bão, đến những ngọn đuốc thắp sáng cả thung lũng... Hàng triệu năm tiến hóa chỉ chờ đợi khoảnh khắc này: Con người chính thức lên cấp, trở thành người làm chủ thế giới!",
                voice_name="Linh",
                sound_fx_description="Resonant animal-horn trumpet blast, thunderous tribal victory cheers, monumental cinematic orchestral crescendo"
            )
        ]

        for s in scenes:
            s.prompt = s.build_seedance_prompt(character)

        return StoryProject(
            project_id="proj_human_dawn",
            title="DAWN OF MAN: THE FIRST LEVEL UP",
            synopsis="Từ bóng tối sợ hãi nơi rừng sâu nhiệt đới, người tiền sử Kael thuần phục ngọn lửa, chế tác công cụ đá sắc bén và dẫn dắt bộ tộc thực hiện bước nhảy vọt 'lên cấp' vĩ đại nhất lịch sử nhân loại.",
            genre="Prehistoric Human Epic",
            character=character,
            scenes=scenes,
            output_dir="blockbuster_output/proj_human_dawn"
        )

    @classmethod
    def create_custom_storyboard(
        cls,
        title: str,
        synopsis: str,
        character_name: str,
        character_appearance: str,
        character_wardrobe: str,
        scene_actions: List[dict]
    ) -> StoryProject:
        """Builds a custom multi-scene storyboard project."""
        character = CharacterAnchor(
            name=character_name,
            appearance=character_appearance,
            wardrobe=character_wardrobe
        )
        
        scenes: List[Scene] = []
        for i, item in enumerate(scene_actions, 1):
            sc = Scene(
                scene_number=i,
                title=item.get("title", f"Scene {i}"),
                shot_type=item.get("shot_type", ShotType.MEDIUM),
                camera_motion=item.get("camera_motion", CameraMotion.PUSH_IN),
                lighting=item.get("lighting", LightingStyle.GOLDEN_HOUR),
                action=item.get("action", ""),
                environment=item.get("environment", ""),
                duration=item.get("duration", 5),
                voiceover_text=item.get("voiceover_text", ""),
                voice_name=item.get("voice_name", "Samantha"),
                sound_fx_description=item.get("sound_fx", "")
            )
            sc.prompt = sc.build_seedance_prompt(character)
            scenes.append(sc)

        return StoryProject(
            project_id=f"proj_{int(time.time())}",
            title=title,
            synopsis=synopsis,
            character=character,
            scenes=scenes
        )
