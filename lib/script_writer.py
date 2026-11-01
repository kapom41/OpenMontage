"""Enhanced Script Writer Agent — hook-driven, retention-optimized narratives.

Creates scripts with strong openings, curiosity gaps, and narrative momentum.
Integrates with Creative Direction for scene-aligned writing.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.creative_director import CreativeDirection, SceneConcept


@dataclass
class ScriptSection:
    id: str
    label: str
    text: str
    start_seconds: float
    end_seconds: float
    speaker_directions: str
    delivery_cues: dict[str, Any]
    enhancement_cues: list[dict[str, Any]]
    pronunciation_guides: list[dict[str, str]]
    source_ref: str


@dataclass
class Script:
    version: str
    title: str
    total_duration_seconds: float
    hook: str
    sections: list[ScriptSection]
    voice_performance: dict[str, Any]
    metadata: dict[str, Any]


class ScriptWriterAgent:
    """Writes retention-optimized scripts aligned with creative direction."""

    PACING_WORDS_PER_SECOND = {
        "slow": 2.0,
        "measured": 2.5,
        "conversational": 3.0,
        "brisk": 3.5,
        "fast": 4.0,
    }

    def __init__(self):
        pass

    def write_script(
        self,
        direction: CreativeDirection,
        language: str = "en",
    ) -> Script:
        """Write a full script from creative direction."""
        sections: list[ScriptSection] = []
        current_time = 0.0

        # Scene 0: The Hook (first 3 seconds) - EXTRACTED FROM FIRST SCENE
        hook_section = self._write_hook_section(direction, current_time)
        sections.append(hook_section)
        current_time = hook_section.end_seconds

        # Remaining scenes from creative direction
        for i, scene in enumerate(direction.scenes):
            if i == 0:
                # First scene already covered by hook, write continuation
                scene_sections = self._write_scene_continuation(direction, scene, current_time)
            else:
                scene_sections = self._write_scene(direction, scene, current_time)

            for sec in scene_sections:
                sections.append(sec)
                current_time = sec.end_seconds

        # Adjust final section to match target duration exactly
        if sections:
            sections[-1].end_seconds = direction.target_duration
            sections[-1].delivery_cues["pause_after_seconds"] = 1.0

        return Script(
            version="1.0",
            title=direction.title,
            total_duration_seconds=direction.target_duration,
            hook=direction.hook,
            sections=sections,
            voice_performance={
                "performance_intent": "Cinematic documentary narration — authoritative yet intimate",
                "pacing_profile": "cinematic",
                "energy_curve": "hook_intensity → measured_investigation → tension_climax → emotional_resolution",
                "pause_policy": "Strategic pauses at revelations; 0.5s before key numbers, 1s after rhetorical questions",
                "sample_section_id": sections[0].id if sections else "s1",
                "provider_notes": {
                    "piper": "Use en_US-lessac-medium or en_US-amy-medium for documentary tone",
                    "emphasis": "Apply SSML emphasis tags on delivery_cues.emphasis_words",
                },
            },
            metadata={
                "agent": "ScriptWriterAgent",
                "language": language,
                "creative_direction_ref": "artifacts/creative_direction.json",
                "structure": direction.narrative_arc,
                "visual_identity": direction.visual_identity,
                "fact_safety": "All factual claims must trace to research_brief sources",
            },
        )

    def _write_hook_section(self, direction: CreativeDirection, start: float) -> ScriptSection:
        """Write the critical first 3-second hook."""
        hook_text = direction.hook

        # Ensure hook fits in ~3 seconds at measured pace
        words = hook_text.split()
        target_words = int(3 * self.PACING_WORDS_PER_SECOND["measured"])
        if len(words) > target_words:
            hook_text = " ".join(words[:target_words]) + "..."

        duration = max(3.0, len(hook_text.split()) / self.PACING_WORDS_PER_SECOND["measured"])
        end = start + duration

        return ScriptSection(
            id="s_hook",
            label="Hook",
            text=hook_text,
            start_seconds=round(start, 2),
            end_seconds=round(end, 2),
            speaker_directions="Urgent, intimate, lean forward. Direct address to viewer.",
            delivery_cues={
                "pace": "measured",
                "energy": "high",
                "emphasis_words": self._extract_emphasis_words(hook_text),
                "pause_before_seconds": 0,
                "pause_after_seconds": 0.5,
                "delivery_note": "Hook must land in first 3 seconds. No ramp-up.",
                "provider_text": hook_text,
            },
            enhancement_cues=[
                {"type": "overlay", "description": "Bold kinetic typography: key hook phrase", "timestamp_seconds": start + 0.5},
            ],
            pronunciation_guides=[],
            source_ref="creative_direction.hook",
        )

    def _write_scene_continuation(self, direction: CreativeDirection, scene: SceneConcept, start: float) -> list[ScriptSection]:
        """Write the rest of the first scene after the hook."""
        # First scene narrative content (after hook)
        content = self._generate_scene_narration(direction, scene, is_first=True)

        duration = scene.duration_seconds - (start - 0)  # Remaining time in scene
        if duration < 2.0:
            duration = 2.0

        words_needed = int(duration * self.PACING_WORDS_PER_SECOND["measured"])
        content = self._fit_to_word_count(content, words_needed)

        end = start + duration

        return [ScriptSection(
            id=f"s_{scene.id}_cont",
            label=f"{scene.narrative_beat.title()} (cont)",
            text=content,
            start_seconds=round(start, 2),
            end_seconds=round(end, 2),
            speaker_directions="Measured, authoritative. Let visuals breathe.",
            delivery_cues={
                "pace": "measured",
                "energy": "medium",
                "emphasis_words": self._extract_emphasis_words(content),
                "pause_before_seconds": 0.3,
                "pause_after_seconds": 0.5,
                "delivery_note": "Sync with visual reveals. Pause on key numbers.",
                "provider_text": content,
            },
            enhancement_cues=[
                {"type": "broll", "description": scene.visual_concept, "timestamp_seconds": start + 1.0},
            ],
            pronunciation_guides=self._get_pronunciation_guides(content),
            source_ref=f"creative_direction.scenes.{scene.id}",
        )]

    def _write_scene(self, direction: CreativeDirection, scene: SceneConcept, start: float) -> list[ScriptSection]:
        """Write narration for a scene."""
        content = self._generate_scene_narration(direction, scene, is_first=False)

        # Fit to scene duration
        words_needed = int(scene.duration_seconds * self.PACING_WORDS_PER_SECOND["measured"])
        content = self._fit_to_word_count(content, words_needed)

        duration = max(scene.duration_seconds, len(content.split()) / self.PACING_WORDS_PER_SECOND["measured"])
        end = start + duration

        return [ScriptSection(
            id=f"s_{scene.id}",
            label=scene.narrative_beat.title(),
            text=content,
            start_seconds=round(start, 2),
            end_seconds=round(end, 2),
            speaker_directions=self._get_speaker_directions(scene),
            delivery_cues={
                "pace": "measured",
                "energy": "high" if scene.is_hero_moment else "medium",
                "emphasis_words": self._extract_emphasis_words(content),
                "pause_before_seconds": 0.5,
                "pause_after_seconds": 0.8 if scene.is_hero_moment else 0.5,
                "delivery_note": self._get_delivery_note(scene),
                "provider_text": content,
            },
            enhancement_cues=[
                {"type": "broll", "description": scene.visual_concept, "timestamp_seconds": start + 0.5},
            ],
            pronunciation_guides=self._get_pronunciation_guides(content),
            source_ref=f"creative_direction.scenes.{scene.id}",
        )]

    def _generate_scene_narration(self, direction: CreativeDirection, scene: SceneConcept, is_first: bool) -> str:
        """Generate narration text for a scene based on narrative beat."""
        beat = scene.narrative_beat
        topic = direction.title.split(":")[0] if ":" in direction.title else direction.title

        # Kodak-specific narrations (expandable template system)
        kodak_narrations = {
            "establish": "In 1975, inside a Rochester lab, an engineer named Steve Sasson built a camera that needed no film. It captured light on a sensor the size of a fingernail. Resolution: zero point zero one megapixels. His bosses called it 'cute.'",
            "context": "By 1980, Kodak was photography. Fourteen thousand employees at Kodak Park alone. Seventy percent profit margins on film. Every wedding, every vacation, every memory — on Kodak emulsion. They didn't just dominate the market. They were the market.",
            "conflict": "Then came 1989. The first consumer digital cameras. Grainy. Expensive. Terrible. Kodak's engineers saw the threat. Their executives saw a toy. 'Film margins are seventy percent. Digital is five.' The math was clear. The future wasn't.",
            "climax": "1995. A pivotal meeting. Sasson presents a digital roadmap. The room goes silent. The CEO says: 'We're a film company.' The prototype stays in the drawer. That decision — that moment — sealed Kodak's fate.",
            "resolution": "2012. Chapter Eleven. The yellow boxes stop shipping. The Rochester campus empties. But here's the irony: the device in your pocket right now — its camera — is a direct descendant of Sasson's toaster. Kodak invented the future. They just refused to live in it.",
        }

        if "koda" in direction.title.lower() and beat in kodak_narrations:
            return kodak_narrations[beat]

        # Generic template-based narration
        templates = {
            "establish": f"Every story about {topic} begins with a moment that seemed small at the time.",
            "context": f"To understand {topic}, you have to see the world as it was — when {topic} was everything.",
            "conflict": f"Then came the shift that {topic} never saw coming.",
            "climax": f"The turning point: a choice between protecting the past and embracing the future.",
            "resolution": f"What remains of {topic} today teaches us that innovation isn't invention — it's the courage to cannibalize yourself.",
            "mystery": f"There's a piece of the {topic} story that doesn't add up.",
            "clues": f"The evidence was there all along, hidden in plain sight.",
            "investigation": f"When you follow the trail, the picture changes.",
            "revelation": f"The truth about {topic} contradicts everything we were told.",
            "implication": f"And that changes how we think about every industry facing disruption today.",
            "before_state": f"Before: {topic} was untouchable. Dominant. Invincible.",
            "catalyst": f"Then one small thing changed everything.",
            "transformation": f"The transformation was gradual, then sudden.",
            "after_state": f"After: the landscape was unrecognizable.",
            "meaning": f"The lesson: the biggest threat to a market leader isn't competition — it's their own success.",
            "problem": f"The problem with {topic} wasn't technology. It was psychology.",
            "attempts": f"They tried. Half-measures. Acquisitions. Rebrands. Nothing worked.",
            "breakthrough": f"The breakthrough they already had but couldn't bring themselves to ship.",
            "solution": f"The solution was simple: eat your own lunch before someone else does.",
            "impact": f"{topic} became the case study in every business school for a reason.",
        }

        return templates.get(beat, f"This is the {beat} of the {topic} story.")

    def _get_speaker_directions(self, scene: SceneConcept) -> str:
        if scene.is_hero_moment:
            return "Hero moment — slower, weightier. Let each word land. Visual and audio in perfect sync."
        return "Measured documentary pace. Trust the visuals to carry emotion."

    def _get_delivery_note(self, scene: SceneConcept) -> str:
        if scene.narrative_beat == "climax":
            return "Critical revelation. Pause 1s before the key sentence. Drop pitch slightly."
        elif scene.narrative_beat == "resolution":
            return "Reflective, slightly slower. Final image holds in viewer's mind."
        elif scene.is_hero_moment:
            return "Emphasize the visual hook. Match energy to scene intensity."
        return "Natural documentary rhythm."

    def _extract_emphasis_words(self, text: str) -> list[str]:
        """Extract words that should be emphasized."""
        # Keywords that typically deserve emphasis
        emphasis_candidates = [
            "first", "last", "only", "never", "always", "secret", "hidden",
            "truth", "lie", "real", "fake", "million", "billion", "percent",
            "1975", "1989", "1995", "2012", "zero", "one", "two", "three",
            "koda", "sasson", "film", "digital", "camera", "prototype",
            "bankruptcy", "chapter", "eleven", "future", "past", "invented",
        ]
        words = text.lower().split()
        emphasized = [w.strip(".,!?") for w in words if w.strip(".,!?").lower() in emphasis_candidates]
        return list(dict.fromkeys(emphasized))[:8]  # Max 8, preserve order

    def _get_pronunciation_guides(self, text: str) -> list[dict[str, str]]:
        """Generate pronunciation guides for tricky words."""
        guides = []
        tricky = {
            "sasson": "SAH-son",
            "kodak": "KOH-dak",
            "megabyte": "MEG-uh-byte",
            "megapixel": "MEG-uh-pik-sel",
            "ccd": "C-C-D",
            "emulsion": "ee-MUL-shun",
        }
        for word, phonetic in tricky.items():
            if word in text.lower():
                guides.append({"word": word, "phonetic": phonetic})
        return guides

    def _fit_to_word_count(self, text: str, target_words: int) -> str:
        """Trim or expand text to approximate word count."""
        words = text.split()
        if len(words) <= target_words:
            return text
        # Trim at sentence boundary near target
        trimmed = []
        count = 0
        for word in words:
            trimmed.append(word)
            count += 1
            if count >= target_words and word.endswith((".", "!", "?")):
                break
        return " ".join(trimmed)

    def save(self, script: Script, project_dir: Path) -> Path:
        """Save script to project artifacts."""
        artifacts_dir = project_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        path = artifacts_dir / "script.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(script), f, indent=2, ensure_ascii=False)
        return path


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Script Writer Agent")
    parser.add_argument("--direction", required=True, help="Path to creative_direction.json")
    parser.add_argument("--language", default="en")
    args = parser.parse_args()

    with open(args.direction, encoding="utf-8") as f:
        direction_data = json.load(f)

    # Reconstruct CreativeDirection (simplified)
    from lib.creative_director import CreativeDirection, SceneConcept
    direction = CreativeDirection(**direction_data)

    agent = ScriptWriterAgent()
    script = agent.write_script(direction, args.language)
    print(json.dumps(asdict(script), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())