"""Creative Director Agent — transforms topics into cinematic visual narratives.

Decides the visual language, scene architecture, and storytelling approach
for maximum viewer retention and emotional impact.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.trend_intelligence import TrendIntelligenceAgent, TrendReport


@dataclass
class SceneConcept:
    id: str
    narrative_beat: str
    visual_concept: str
    shot_description: str
    camera_movement: str
    lighting: str
    color_palette: str
    duration_seconds: float
    transition_in: str
    transition_out: str
    is_hero_moment: bool
    ai_generation_prompt: str
    archive_fallback_query: str
    visual_reference: str
    rationale: str


@dataclass
class CreativeDirection:
    title: str
    core_concept: str
    hook: str
    narrative_arc: list[str]
    visual_identity: str
    color_palette: list[str]
    scenes: list[SceneConcept]
    music_direction: str
    sound_design_notes: str
    subtitle_style: str
    target_duration: float
    aspect_ratio: str
    generated_at: str


class CreativeDirectorAgent:
    """Creates cinematic creative direction from topic + trend intelligence."""

    NARRATIVE_ARCS = {
        "chronological": ["establish", "context", "conflict", "climax", "resolution"],
        "reveal": ["mystery", "clues", "investigation", "revelation", "implication"],
        "before_after": ["before_state", "catalyst", "transformation", "after_state", "meaning"],
        "problem_solution": ["problem", "attempts", "breakthrough", "solution", "impact"],
        "narrative": ["inciting_incident", "rising_action", "climax", "falling_action", "resolution"],
        "comparison": ["subject_a", "subject_b", "contrast", "synthesis", "verdict"],
        "investigation": ["question", "evidence_1", "evidence_2", "twist", "conclusion"],
    }

    VISUAL_IDENTITIES = {
        "cinematic_historical": {
            "description": "Rich, textured look with film grain, vintage lenses, warm tones",
            "palette": ["#8B4513", "#CD853F", "#DEB887", "#2F1B14", "#FFD700"],
            "lighting": "golden_hour, tungsten_warm, volumetric",
            "camera": "slow dolly, orbital, rack focus",
        },
        "cinematic_modern": {
            "description": "Clean, high-contrast, anamorphic feel, cool/warm separation",
            "palette": ["#0D1117", "#161B22", "#58A6FF", "#F78166", "#FFFFFF"],
            "lighting": "rim_lit, neon, mixed, volumetric",
            "camera": "dynamic tracking, whip pan, dolly_in",
        },
        "cinematic_contrast": {
            "description": "Stark before/after visual separation, split lighting",
            "palette": ["#1A1A2E", "#16213E", "#E94560", "#0F3460", "#FFFFFF"],
            "lighting": "low_key vs high_key, silhouette, dramatic",
            "camera": "static vs handheld, matched cuts",
        },
        "clean_educational": {
            "description": "Bright, clear, diagram-friendly, minimal distractions",
            "palette": ["#FFFFFF", "#F0F0F0", "#2563EB", "#10B981", "#1E293B"],
            "lighting": "high_key, overcast_soft, even",
            "camera": "static, slow zoom, top-down for diagrams",
        },
        "animated_diagram": {
            "description": "Motion graphics, kinetic typography, 3D diagrams",
            "palette": ["#0F172A", "#1E293B", "#38BDF8", "#FACC15", "#22D3EE"],
            "lighting": "studio, clean, rim highlights",
            "camera": "virtual camera, smooth orbits, focus pulls",
        },
        "intimate_cinematic": {
            "description": "Close, personal, shallow DOF, emotional lighting",
            "palette": ["#1C1917", "#292524", "#F5E6D3", "#D6D3D1", "#78716C"],
            "lighting": "natural, window_light, golden_hour, soft",
            "camera": "handheld, close_up, slow push_in",
        },
    }

    def __init__(self):
        self.trend_agent = TrendIntelligenceAgent()
        self._viral_pattern_agent = None
        self._memory_agent = None

    @property
    def viral_pattern_agent(self):
        if self._viral_pattern_agent is None:
            from lib.viral_pattern import ViralPatternAgent
            self._viral_pattern_agent = ViralPatternAgent()
        return self._viral_pattern_agent

    @property
    def memory_agent(self):
        if self._memory_agent is None:
            from lib.creative_memory import CreativeMemoryAgent
            self._memory_agent = CreativeMemoryAgent()
        return self._memory_agent

    def create_direction(
        self,
        title: str,
        idea: str,
        trend_report: TrendReport,
        duration_seconds: float = 45.0,
        aspect_ratio: str = "16:9",
    ) -> CreativeDirection:
        """Generate full creative direction with viral patterns and memory."""

        # Get viral pattern analysis
        viral_report = self.viral_pattern_agent.analyze(title + " " + idea)

        # Get creative memory recommendations
        memory_recs = self.memory_agent.get_recommendations(title + " " + idea)

        # Select best structure from viral patterns (preferred) or trends
        structure = viral_report.recommended_structures[0] if viral_report.recommended_structures else (
            trend_report.recommended_structures[0] if trend_report.recommended_structures else "chronological"
        )
        narrative_beats = self.NARRATIVE_ARCS.get(structure, self.NARRATIVE_ARCS["chronological"])

        # Select visual identity from viral patterns or memory
        visual_identity = viral_report.top_hook_formulas[0]["formula_id"].replace("hook_", "") if viral_report.top_hook_formulas else ""
        if visual_identity not in self.VISUAL_IDENTITIES:
            visual_identity = self._select_visual_identity(trend_report, idea)
        # Override with memory recommendation if strong
        if memory_recs.get("recommended_visual_identities"):
            mem_vid = memory_recs["recommended_visual_identities"][0][0]
            if mem_vid in self.VISUAL_IDENTITIES:
                visual_identity = mem_vid

        identity_config = self.VISUAL_IDENTITIES.get(visual_identity, self.VISUAL_IDENTITIES["cinematic_modern"])

        # Generate hook from viral pattern recommendation
        recommended_hook = viral_report.recommended_hooks[0] if viral_report.recommended_hooks else (
            trend_report.recommended_hooks[0] if trend_report.recommended_hooks else "hook_question"
        )
        hook = self._craft_hook(title, idea, recommended_hook)

        # Build narrative arc
        narrative_arc = self._build_narrative_arc(idea, narrative_beats)

        # Create scenes with viral retention techniques
        scenes = self._create_scenes(
            title, idea, narrative_beats, identity_config, duration_seconds, viral_report
        )

        # Music & sound design
        music_direction = self._design_music(viral_report, visual_identity)
        sound_design = self._design_sound(viral_report, scenes)

        # Subtitle style from viral patterns or memory
        subtitle_style = viral_report.top_hook_formulas[0]["formula_id"].replace("hook_", "cinematic") if viral_report.top_hook_formulas else "cinematic"
        if memory_recs.get("recommended_subtitle_styles"):
            mem_style = memory_recs["recommended_subtitle_styles"][0][0]
            if mem_style in ["cinematic", "documentary", "minimal", "mobile_vertical"]:
                subtitle_style = mem_style
        elif memory_recs.get("recommended_subtitle_styles"):
            subtitle_style = "cinematic"

        return CreativeDirection(
            title=title,
            core_concept=self._craft_core_concept(idea, structure),
            hook=hook,
            narrative_arc=narrative_arc,
            visual_identity=visual_identity,
            color_palette=identity_config["palette"],
            scenes=scenes,
            music_direction=music_direction,
            sound_design_notes=sound_design,
            subtitle_style=subtitle_style,
            target_duration=duration_seconds,
            aspect_ratio=aspect_ratio,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def _select_visual_identity(self, trend_report: TrendReport, idea: str) -> str:
        """Select the best visual identity for the topic."""
        idea_lower = idea.lower()

        if any(w in idea_lower for w in ["history", "rise", "fall", "evolution", "origin", "koda", "19", "20th", "archive", "historical"]):
            return "cinematic_historical"
        elif any(w in idea_lower for w in ["vs", "versus", "compare", "comparison", "battle"]):
            return "cinematic_contrast"
        elif any(w in idea_lower for w in ["how", "works", "science", "technology", "engineering", "explained"]):
            return "animated_diagram"
        elif any(w in idea_lower for w in ["story", "journey", "personal", "experience", "life"]):
            return "intimate_cinematic"
        elif any(w in idea_lower for w in ["tutorial", "guide", "learn", "teach"]):
            return "clean_educational"
        else:
            return "cinematic_modern"

    def _craft_hook(self, title: str, idea: str, recommended_hook: str) -> str:
        """Craft a compelling opening hook."""
        hooks = {
            "hook_question": f"What if everything you knew about {title.split(':')[0]} was wrong?",
            "hook_reveal": f"The {title.split(':')[0]} secret that changed everything — hidden for decades.",
            "hook_curiosity": f"In 1975, an engineer built the future. His company buried it.",
            "hook_transformation": f"From dominant giant to cautionary tale — the {title.split(':')[0]} story.",
            "hook_personal": f"I discovered why {title.split(':')[0]} really failed. It wasn't what you think.",
            "hook_visual": f"Watch this single moment that killed an empire.",
            "generic": f"The untold story of {title.split(':')[0]}.",
        }
        return hooks.get(recommended_hook, hooks["hook_curiosity"])

    def _craft_core_concept(self, idea: str, structure: str) -> str:
        """Create the core creative concept statement."""
        return f"A {structure} visual narrative exploring: {idea}. Cinematic, evidence-driven, emotionally resonant."

    def _build_narrative_arc(self, idea: str, beats: list[str]) -> list[str]:
        """Flesh out narrative beats with topic-specific content."""
        arc = []
        for beat in beats:
            if beat == "establish":
                arc.append(f"Establish the world of {idea} — the dominance, the scale")
            elif beat == "context":
                arc.append(f"Context: how {idea} became the standard everyone trusted")
            elif beat == "conflict":
                arc.append(f"The disruption: the moment the paradigm shifted")
            elif beat == "climax":
                arc.append(f"The critical choice: adapt or deny — the turning point")
            elif beat == "resolution":
                arc.append(f"The aftermath: what remains and what we learn")
            elif beat == "mystery":
                arc.append(f"A puzzling disappearance: the prototype that vanished")
            elif beat == "clues":
                arc.append(f"Following the breadcrumbs: internal memos, forgotten labs")
            elif beat == "investigation":
                arc.append(f"Digging deeper: the engineers who knew the truth")
            elif beat == "revelation":
                arc.append(f"The smoking gun: the meeting where the future was rejected")
            elif beat == "implication":
                arc.append(f"What this means for every company facing disruption today")
            elif beat == "before_state":
                arc.append(f"Before: total market control, infinite resources")
            elif beat == "catalyst":
                arc.append(f"The catalyst: a 0.01 megapixel prototype in a lab")
            elif beat == "transformation":
                arc.append(f"The transformation: digital eats film, the world changes")
            elif beat == "after_state":
                arc.append(f"After: bankruptcy, the brand sold, the lesson learned")
            elif beat == "meaning":
                arc.append(f"The meaning: innovation isn't invention — it's courage to cannibalize yourself")
            elif beat == "problem":
                arc.append(f"The problem: {idea} — a giant blind to its own obsolescence")
            elif beat == "attempts":
                arc.append(f"Failed attempts: half-measures, acquisitions, rebrands")
            elif beat == "breakthrough":
                arc.append(f"The breakthrough they had but didn't ship")
            elif beat == "solution":
                arc.append(f"The solution that could have saved them")
            elif beat == "impact":
                arc.append(f"The impact: a case study in corporate inertia")
            else:
                arc.append(beat.replace("_", " ").capitalize())
        return arc

    def _create_scenes(
        self,
        title: str,
        idea: str,
        narrative_beats: list[str],
        identity_config: dict[str, Any],
        duration_seconds: float,
        viral_report: ViralPatternReport,
    ) -> list[SceneConcept]:
        """Create detailed scene concepts with viral retention techniques."""
        scenes: list[SceneConcept] = []
        num_scenes = len(narrative_beats)
        base_duration = duration_seconds / num_scenes

        # Get retention techniques from viral patterns
        retention_techniques = viral_report.retention_techniques if hasattr(viral_report, 'retention_techniques') else []

        # Kodak-specific scene concepts (will generalize later)
        kodak_scenes = [
            {
                "beat": "establish",
                "visual": "1975 Kodak lab — engineer Steve Sasson holding the first digital camera prototype, size of a toaster, 0.01 megapixels. Cinematic close-up on the crude CCD sensor.",
                "shot": "Extreme close-up on the prototype camera, pull back to reveal lab environment. Anamorphic lens, shallow DOF.",
                "camera": "macro_to_medium_dolly_out",
                "lighting": "tungsten_warm, volumetric_dust_motes",
                "palette": "warm_amber_teal",
                "transition_in": "fade_from_black",
                "transition_out": "match_cut_to_modern",
                "hero": True,
                "prompt": "Cinematic 1975 Kodak research laboratory, engineer Steve Sasson holding world's first digital camera prototype (toaster-sized, 0.01MP), dramatic tungsten lighting with volumetric dust motes, anamorphic lens flare, shallow depth of field, 35mm film grain, warm amber and teal color grading, photorealistic, 8k",
                "archive": "Kodak digital camera prototype 1975 Steve Sasson",
                "reference": "https://commons.wikimedia.org/wiki/File:First_digital_camera_1975.jpg",
            },
            {
                "beat": "context",
                "visual": "Kodak Park Rochester at peak — massive film coating machines, miles of emulsion, 145,000 employees. Aerial establishing shot, golden hour.",
                "shot": "Wide establishing aerial, slow dolly in. Show scale of film empire.",
                "camera": "aerial_dolly_in",
                "lighting": "golden_hour, epic_scale",
                "palette": "golden_kodak_yellow",
                "transition_in": "match_cut_from_prototype",
                "transition_out": "whip_pan_to_disruption",
                "hero": True,
                "prompt": "Aerial view of Kodak Park Rochester 1980s at peak, massive industrial film coating complex, golden hour sunlight, 145000 employees, miles of emulsion coating machines, cinematic wide establishing shot, Kodak yellow and gold color palette, epic scale, photorealistic, 8k",
                "archive": "Kodak Park Rochester aerial 1980s",
                "reference": "https://commons.wikimedia.org/wiki/File:Kodak_Park_Rochester.jpg",
            },
            {
                "beat": "conflict",
                "visual": "1989 — first consumer digital cameras hit market. Split screen: film grain vs pixel grid. The moment digital crossed 'good enough'.",
                "shot": "Split screen transition: left side 35mm film texture, right side early digital noise. Matching camera move.",
                "camera": "static_split_screen",
                "lighting": "contrast_low_key_vs_high_key",
                "palette": "film_warm_vs_digital_cool",
                "transition_in": "whip_pan_from_empire",
                "transition_out": "digital_glitch_transition",
                "hero": False,
                "prompt": "Split screen visual metaphor: left side rich 35mm film grain texture with warm cinematic tones, right side early 1990s digital camera pixel grid with cool blue noise, perfect vertical split with matching camera movement, dramatic contrast between analog warmth and digital coldness, photorealistic textures, 8k",
                "archive": "first consumer digital camera 1990",
                "reference": "https://commons.wikimedia.org/wiki/File:First_consumer_digital_camera.jpg",
            },
            {
                "beat": "climax",
                "visual": "1995 boardroom — executives reject digital pivot. 'Film margins are 70%. Digital is 5%.' The fatal decision. Tight on faces, tense silence.",
                "shot": "Intimate boardroom, close-ups on conflicted faces. Rack focus from presenter to skeptical CEO. Silence as sound design.",
                "camera": "rack_focus, slow_push_in",
                "lighting": "low_key, rim_lit, tense",
                "palette": "cool_corporate_blue",
                "transition_in": "glitch_from_digital",
                "transition_out": "slow_fade_to_consequence",
                "hero": True,
                "prompt": "Cinematic 1995 corporate boardroom, tense executives in suits, tight close-ups on conflicted faces, rack focus from digital camera prototype on table to skeptical CEO, low-key dramatic lighting with rim highlights, cool corporate blue color palette, heavy atmosphere of denial, photorealistic, 8k",
                "archive": "Kodak boardroom 1990s",
                "reference": "",
            },
            {
                "beat": "resolution",
                "visual": "2012 — Chapter 11 bankruptcy filing. Final shot: Kodak logo fading on abandoned factory. Then: modern smartphone camera — their invention in everyone's pocket.",
                "shot": "Slow zoom out from bankruptcy document to abandoned factory, match cut to modern smartphone camera close-up. Full circle.",
                "camera": "zoom_out_match_cut",
                "lighting": "overcast_soft, then bright_clean",
                "palette": "desaturated_then_vibrant",
                "transition_in": "fade_from_boardroom",
                "transition_out": "end_hold",
                "hero": True,
                "prompt": "Cinematic sequence: 2012 Kodak Chapter 11 bankruptcy document, slow zoom out to abandoned Rochester factory with overcast sky, match cut to modern smartphone camera module in bright clean light, vibrant colors, the 0.01MP prototype evolved into billions of pockets, poetic visual irony, photorealistic, 8k",
                "archive": "Kodak bankruptcy 2012 abandoned factory",
                "reference": "https://commons.wikimedia.org/wiki/File:Kodak_headquarters_Rochester.jpg",
            },
        ]

        # Get transition recommendations from viral patterns
        viral_transitions = viral_report.patterns[0].scene_transitions if viral_report.patterns else ["cut"]

        # Map narrative beats to kodak scenes or generate generic
        for i, beat in enumerate(narrative_beats):
            transition_in = viral_transitions[i % len(viral_transitions)] if i > 0 else "fade_from_black"
            transition_out = viral_transitions[(i + 1) % len(viral_transitions)] if i < num_scenes - 1 else "end_hold"

            if i < len(kodak_scenes) and "koda" in idea.lower():
                sc = kodak_scenes[i]
                # Override transitions with viral recommendations
                if i > 0:
                    sc["transition_in"] = transition_in
                if i < num_scenes - 1:
                    sc["transition_out"] = transition_out

                scenes.append(SceneConcept(
                    id=f"scene_{i+1:02d}",
                    narrative_beat=beat,
                    visual_concept=sc["visual"],
                    shot_description=sc["shot"],
                    camera_movement=sc["camera"],
                    lighting=sc["lighting"],
                    color_palette=sc["palette"],
                    duration_seconds=base_duration,
                    transition_in=sc["transition_in"],
                    transition_out=sc["transition_out"],
                    is_hero_moment=sc["hero"],
                    ai_generation_prompt=sc["prompt"],
                    archive_fallback_query=sc["archive"],
                    visual_reference=sc["reference"],
                    rationale=f"Serves {beat} beat in {viral_report.recommended_structures[0] if viral_report.recommended_structures else 'chronological'} structure. Retention: {', '.join(retention_techniques)}",
                ))
            else:
                # Generic scene generation with viral transitions
                scenes.append(SceneConcept(
                    id=f"scene_{i+1:02d}",
                    narrative_beat=beat,
                    visual_concept=f"Visual representation of {beat} for: {idea}",
                    shot_description=f"Cinematic shot supporting {beat}",
                    camera_movement=identity_config["camera"],
                    lighting=identity_config["lighting"],
                    color_palette=", ".join(identity_config["palette"][:3]),
                    duration_seconds=base_duration,
                    transition_in=transition_in,
                    transition_out=transition_out,
                    is_hero_moment=i in (0, num_scenes - 1),
                    ai_generation_prompt=f"Cinematic {identity_config['description']}, {beat} visual for: {idea}, {identity_config['lighting']}, {identity_config['camera']}, 8k photorealistic",
                    archive_fallback_query=f"{idea} {beat} footage",
                    visual_reference="",
                    rationale=f"Generic {beat} beat. Retention: {', '.join(retention_techniques)}",
                ))

        return scenes

    def _design_music(self, viral_report: ViralPatternReport, visual_identity: str) -> str:
        """Design music direction based on viral patterns."""
        base = "Original cinematic score"
        if "historical" in visual_identity:
            base += " — orchestral with period-appropriate motifs, evolving from warm analog to cold digital textures"
        elif "modern" in visual_identity:
            base += " — hybrid electronic/orchestral, tension-building, modern documentary style"
        elif "contrast" in visual_identity:
            base += " — dual themes: warm analog melody vs cold digital synth, merging at climax"
        elif "educational" in visual_identity or "diagram" in visual_identity:
            base += " — minimal, rhythmic, unobtrusive, supports clarity"
        elif "intimate" in visual_identity:
            base += " — solo piano/cello, sparse, emotional, breathing with narration"

        audio_kws = viral_report.audio_keywords if hasattr(viral_report, 'audio_keywords') else []
        if "tension_music" in " ".join(audio_kws):
            base += "; rising tension cues at reveals"
        if "emotional_music" in " ".join(audio_kws):
            base += "; emotional swell at resolution"

        return base

    def _design_sound(self, viral_report: ViralPatternReport, scenes: list[SceneConcept]) -> str:
        """Design sound effects and ambience based on viral patterns."""
        retention_techniques = viral_report.retention_techniques if hasattr(viral_report, 'retention_techniques') else []
        notes = [
            "Subtle ambient layers per scene (lab hum, factory roar, boardroom silence, factory wind)",
            "Transition SFX: film projector whir (analog), digital glitch (digital), page turn (documents)",
            "Hero moments: impact hit on key revelations",
            "Music ducked -18dB under narration, -6dB in pauses",
        ]
        if "audio_tension" in retention_techniques:
            notes.append("Rising tension drones before reveals, sudden silence at key moments")
        if "curiosity_gaps" in retention_techniques:
            notes.append("Audio question marks: pitch rise on rhetorical questions")
        return "; ".join(notes)

    def _select_subtitle_style(self, trend_report: TrendReport) -> str:
        """Select modern subtitle style."""
        patterns = trend_report.patterns if hasattr(trend_report, 'patterns') else trend_report.get('patterns', [])
        caption_styles = [p.caption_style if hasattr(p, 'caption_style') else p.get('caption_style', 'sentence') for p in patterns if (p.caption_style if hasattr(p, 'caption_style') else p.get('caption_style', 'sentence')) != "sentence"]
        if caption_styles:
            style = max(set(caption_styles), key=caption_styles.count)
            # Map legacy styles to modern presets
            style_map = {
                "sentence": "modern_mobile",
                "word_by_word": "modern_mobile",
                "animated_keywords": "modern_mobile",
                "animated": "modern_mobile",
            }
            return style_map.get(style, "modern_mobile")
        return "modern_mobile"  # Clean, mobile-readable default

    def save(self, direction: CreativeDirection, project_dir: Path) -> Path:
        """Save creative direction to project artifacts."""
        artifacts_dir = project_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        path = artifacts_dir / "creative_direction.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(direction), f, indent=2, ensure_ascii=False)
        return path


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Creative Director Agent")
    parser.add_argument("title")
    parser.add_argument("idea")
    parser.add_argument("--duration", type=float, default=45)
    parser.add_argument("--aspect", default="16:9")
    args = parser.parse_args()

    agent = CreativeDirectorAgent()
    trend_report = agent.trend_agent.analyze(args.title + " " + args.idea)
    direction = agent.create_direction(args.title, args.idea, trend_report, args.duration, args.aspect)
    print(json.dumps(asdict(direction), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())