"""Title & Thumbnail Agent — designs title and thumbnail as ONE pairing.

Linting for truncation, duplication, vagueness. Generates 10 titles, ranks them,
writes thumbnail brief for the winner. Based on youtube-agent-skill's yt-package.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.creative_director import CreativeDirection
from lib.viral_pattern import HOOK_FORMULAS


# Title linting constants (from title.py)
DESKTOP_LIMIT = 60
MOBILE_LIMIT = 40
HARD_LIMIT = 100

VAGUE_WORDS = {
    "amazing", "incredible", "insane", "crazy", "huge", "massive", "ultimate",
    "best", "powerful", "secret", "revolutionary", "mindblowing", "epic",
    "perfect", "complete", "everything", "game", "changer", "unbelievable",
}

STOP_WORDS = {
    "the", "a", "an", "of", "for", "to", "in", "on", "and", "or", "is", "are",
    "with", "your", "you", "my", "i", "this", "that", "it", "how", "what", "why",
}


@dataclass
class TitleOption:
    """A single title option with linting results."""
    title: str
    thumbnail_text: str
    score: int
    chars: int
    issues: list[dict[str, str]]
    good: list[str]
    desktop_truncated: bool
    mobile_truncated: bool


@dataclass
class ThumbnailBrief:
    """Thumbnail design brief for the winning title."""
    title: str
    thumbnail_text: str
    expression: str
    framing: str
    background_action: str
    color_scheme: list[str]
    contrast_notes: str
    font_style: str
    text_position: str


@dataclass
class TitleThumbnailResult:
    """Complete result: ranked titles + thumbnail brief for winner."""
    title_options: list[TitleOption]
    winner: TitleOption
    thumbnail_brief: ThumbnailBrief
    generated_at: str


class TitleThumbnailAgent:
    """Designs title + thumbnail as one unit, linted together."""

    def __init__(self):
        pass

    def generate(
        self,
        direction: CreativeDirection,
        script_hook: str = "",
        num_titles: int = 10,
    ) -> TitleThumbnailResult:
        """Generate and lint title+thumbnail pairs."""

        # Generate title candidates
        title_candidates = self._generate_titles(direction, script_hook, num_titles)

        # Generate thumbnail text candidates (different from titles)
        thumb_candidates = self._generate_thumbnail_texts(direction, script_hook, num_titles)

        # Pair and lint each
        title_options = []
        for i, title in enumerate(title_candidates):
            thumb = thumb_candidates[i] if i < len(thumb_candidates) else ""
            result = self._lint_pair(title, thumb)
            title_options.append(TitleOption(**result))

        # Sort by score
        title_options.sort(key=lambda t: -t.score)

        winner = title_options[0]
        thumbnail_brief = self._create_thumbnail_brief(winner, direction)

        return TitleThumbnailResult(
            title_options=title_options,
            winner=winner,
            thumbnail_brief=thumbnail_brief,
            generated_at=datetime.now(timezone.utc).isoformat(),
        )

    def _generate_titles(
        self,
        direction: CreativeDirection,
        script_hook: str,
        num_titles: int,
    ) -> list[str]:
        """Generate title candidates using hook formulas and creative direction."""
        topic = direction.title.split(":")[0] if ":" in direction.title else direction.title
        hook = script_hook or direction.hook
        core = direction.core_concept

        templates = [
            # Question-based
            f"Why {topic} Failed: The Real Reason Nobody Talks About",
            f"What If Everything You Knew About {topic} Was Wrong?",
            f"How {topic} Invented the Future — And Lost It",

            # Statistic-based
            "97% of Market Leaders Make This Mistake. {topic} Did Too.",
            "{topic}: From 145,000 Employees to Bankruptcy in 17 Years",
            "The 0.01 Megapixel Camera That Changed Everything",

            # Reveal-based
            "The {topic} Secret They Buried for 20 Years",
            "I Found the Meeting Where {topic} Killed Their Own Future",
            "The Prototype {topic} Hid in a Drawer Since 1975",

            # Contrarian
            "Everyone Says {topic} Failed at Digital. The Truth Is Opposite.",
            "{topic} Didn't Miss the Future. They Invented It — Then Buried It.",

            # List/Count
            "7 Decisions That Killed {topic}",
            "3 Moments {topic} Could Have Saved Themselves",

            # Direct address
            "If You Run a Company, This Is the Only {topic} Lesson You Need",
        ]

        # Fill templates
        titles = []
        for t in templates:
            titles.append(t.format(topic=topic))

        # Add hook-derived titles
        if hook:
            hook_clean = hook.rstrip(".?!")
            if len(hook_clean) < 80:
                titles.append(hook_clean)

        # Add formula-inspired titles
        formula_titles = [
            f"The {topic} Teardown: What the Archives Reveal",
            f"{topic} vs. The Future: A Case Study in Corporate Inertia",
            f"The Origin of {topic}'s Downfall: One Meeting in 1995",
        ]
        titles.extend(formula_titles)

        # Ensure uniqueness and limit
        unique = list(dict.fromkeys(titles))
        return unique[:num_titles]

    def _generate_thumbnail_texts(
        self,
        direction: CreativeDirection,
        script_hook: str,
        num_thumbs: int,
    ) -> list[str]:
        """Generate thumbnail text candidates (3 words max, different from title)."""
        topic = direction.title.split(":")[0] if ":" in direction.title else direction.title

        # Thumbnail text must NOT repeat title words, must be visual
        thumb_concepts = [
            "1975 Prototype Revealed",
            "145K → Bankruptcy",
            "The 0.01MP Camera",
            "They Buried This",
            "Film vs Digital",
            "The Fatal Meeting",
            "Invented Then Ignored",
            "Your Pocket Has It",
            "Kodak's Fatal Error",
            "The Camera That Changed History",
        ]

        # Add visual concepts from direction
        for scene in direction.scenes:
            if scene.is_hero_moment:
                # Extract key visual elements
                concept = scene.visual_concept[:40]
                if len(concept.split()) <= 4:
                    thumb_concepts.append(concept)

        unique = list(dict.fromkeys(thumb_concepts))
        return unique[:num_thumbs]

    def _lint_pair(self, title: str, thumbnail_text: str) -> dict[str, Any]:
        """Lint title + thumbnail as a pair."""
        t = title.strip()
        n = len(t)
        issues, good = [], []

        # Length checks
        if n > HARD_LIMIT:
            issues.append({"code": "length", "message": f"{n} characters - YouTube's hard limit is {HARD_LIMIT}"})
        elif n > DESKTOP_LIMIT:
            issues.append({"code": "length", "message": f"{n} characters - desktop search cuts near {DESKTOP_LIMIT}"})
        else:
            good.append(f"{n} characters, inside the {DESKTOP_LIMIT}-character desktop cut")

        # Mobile truncation
        desktop_truncated = n > DESKTOP_LIMIT
        mobile_truncated = n > MOBILE_LIMIT
        if mobile_truncated:
            head = t[:MOBILE_LIMIT].rsplit(" ", 1)[0]
            issues.append({"code": "mobile", "message": f'A mobile feed shows about "{head}..." - check the subject survives'})

        # All-caps words
        caps = [w for w in t.split() if len(w) > 2 and w.isupper()]
        if len(caps) > 2:
            issues.append({"code": "shouting", "message": f"{len(caps)} all-caps words - two is the ceiling before it reads as spam"})
        elif caps:
            good.append(f"{len(caps)} all-caps word for emphasis")

        # Vague words
        words_list = re.findall(r"[a-z0-9']+", t.lower())
        vague_found = [w for w in words_list if w in VAGUE_WORDS]
        if vague_found:
            issues.append({"code": "vague", "message": f"{', '.join(sorted(set(vague_found)))} - swap for a number, a name or a date"})

        # Numbers/dates/names
        nums = re.findall(r"\d[\d,.]*%?", t)
        if nums:
            good.append(f"carries a concrete figure ({', '.join(nums[:3])})")
        else:
            issues.append({"code": "no-number", "message": "no number, date or name - the most reliable single fix"})

        # Question in title
        if t.endswith("?"):
            good.append("open question in the title")

        # Front-loaded subject
        front = [w for w in words_list[:3] if w not in STOP_WORDS]
        if not front:
            issues.append({"code": "front-load", "message": "the first three words are all filler - move the subject forward"})

        # Thumbnail duplication check
        if thumbnail_text:
            tw = set(re.findall(r"[a-z0-9']+", t.lower())) - STOP_WORDS
            hw = set(re.findall(r"[a-z0-9']+", thumbnail_text.lower())) - STOP_WORDS
            shared = tw & hw
            if shared:
                issues.append({"code": "duplicate", "message": f"thumbnail repeats the title on {', '.join(sorted(shared))} - the thumbnail should say what the title does not"})
            else:
                good.append("thumbnail and title carry different words")

            # Thumbnail word count
            thumb_words = len(re.findall(r"[a-z0-9']+", thumbnail_text.lower()))
            if thumb_words > 4:
                issues.append({"code": "thumb-length", "message": f"{thumb_words} words on the thumbnail - three is the ceiling at feed size"})

        # Score: 100 - 14*issues + 4*good
        score = max(0, min(100, 100 - 14 * len(issues) + 4 * len(good)))

        return {
            "title": t,
            "thumbnail_text": thumbnail_text,
            "score": score,
            "chars": n,
            "issues": issues,
            "good": good,
            "desktop_truncated": desktop_truncated,
            "mobile_truncated": mobile_truncated,
        }

    def _create_thumbnail_brief(self, winner: TitleOption, direction: CreativeDirection) -> ThumbnailBrief:
        """Create detailed thumbnail design brief for the winner."""
        topic = direction.title.split(":")[0] if ":" in direction.title else direction.title
        visual_id = direction.visual_identity

        # Expression based on visual identity
        expressions = {
            "cinematic_historical": "determined engineer holding prototype, warm light in eyes",
            "cinematic_modern": "split screen: film grain vs pixel grid, intense focus",
            "cinematic_contrast": "half face in warm light, half in cold blue, decision moment",
            "clean_educational": "clean diagram overlay on face, pointing to key insight",
            "animated_diagram": "3D camera model exploding into components",
            "intimate_cinematic": "close up, thoughtful gaze at old photograph",
        }

        # Framing
        framings = {
            "cinematic_historical": "medium close-up, anamorphic, shallow DOF, prototype in foreground",
            "cinematic_modern": "split screen vertical, matched camera movement both sides",
            "cinematic_contrast": "half-and-half lighting split down center of face",
            "clean_educational": "centered, top-down on diagram, hands entering frame",
            "animated_diagram": "virtual camera orbiting 3D model, wireframe overlay",
            "intimate_cinematic": "extreme close-up, eye level, window light catchlights",
        }

        # Background action
        backgrounds = {
            "cinematic_historical": "1975 Kodak lab, volumetric dust, coating machines blurred",
            "cinematic_modern": "abstract data visualization, particle flow representing digital disruption",
            "cinematic_contrast": "left: film coating machine; right: server farm, both motion blurred",
            "clean_educational": "clean white studio, subtle grid lines, animated waveform",
            "animated_diagram": "dark void, neon wireframe camera assembling",
            "intimate_cinematic": "desk with bankruptcy docs, soft bokeh, personal artifacts",
        }

        # Color scheme from direction
        color_scheme = direction.color_palette

        # Contrast notes
        contrast_notes = (
            "High contrast at feed size: subject face/eyes must pop against background. "
            "Thumbnail text (max 3 words) in bold yellow/white with black stroke. "
            "Test at 160x90px — if not readable, increase text size or contrast."
        )

        return ThumbnailBrief(
            title=winner.title,
            thumbnail_text=winner.thumbnail_text,
            expression=expressions.get(visual_id, "engaged, authoritative, direct eye contact"),
            framing=framings.get(visual_id, "cinematic medium shot, rule of thirds"),
            background_action=backgrounds.get(visual_id, "cinematic environment supporting narrative"),
            color_scheme=color_scheme,
            contrast_notes=contrast_notes,
            font_style="Bold sans-serif (Inter/Helvetica), all caps, tracking +10",
            text_position="Lower third, centered, safe margins for YouTube UI overlay",
        )

    def save(self, result: TitleThumbnailResult, project_dir: Path) -> Path:
        """Save title+thumbnail result to project artifacts."""
        artifacts_dir = project_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        path = artifacts_dir / "title_thumbnail.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(result), f, indent=2, ensure_ascii=False)
        return path


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Title & Thumbnail Agent")
    parser.add_argument("--direction", required=True, help="Path to creative_direction.json")
    parser.add_argument("--hook", default="", help="Script hook text")
    parser.add_argument("--titles", type=int, default=10)
    args = parser.parse_args()

    with open(args.direction, encoding="utf-8") as f:
        direction_data = json.load(f)

    from lib.creative_director import CreativeDirection, SceneConcept
    direction = CreativeDirection(**direction_data)

    agent = TitleThumbnailAgent()
    result = agent.generate(direction, args.hook, args.titles)
    print(json.dumps(asdict(result), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())