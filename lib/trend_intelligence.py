"""Trend Intelligence Agent — discovers viral video patterns from public sources.

Uses only free/public methods: YouTube RSS, HTML scraping, no API keys required.
Focuses on structural patterns (hooks, pacing, visual language) not content copying.
"""

from __future__ import annotations

import json
import re
import subprocess
import time
from dataclasses import asdict, dataclass
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

try:
    import requests
    REQUESTS_AVAILABLE = True
except ImportError:
    REQUESTS_AVAILABLE = False


TREND_CACHE_DIR = Path(".trend_cache")
TREND_CACHE_DIR.mkdir(exist_ok=True)

VIRAL_KEYWORDS = [
    "how it works", "secret", "hidden", "nobody talks about", "truth about",
    "why you", "stop doing", "start doing", "game changer", "mind blown",
    "revealed", "exposed", "untold story", "real reason", "mistake",
    "before after", "transformation", "evolution", "history of", "origin of",
    "forgotten", "lost", "abandoned", "failed", "survived", "comeback",
    "rise and fall", "turning point", "moment that changed", "never knew",
    "shocking", "unbelievable", "incredible", "amazing", "fascinating",
]


@dataclass
class ViralPattern:
    hook_type: str
    structure: str
    visual_style: str
    pacing: str
    audio_design: str
    caption_style: str
    platform: str
    source_url: str
    observed_at: str
    confidence: float = 0.7
    # Real data tracking
    source_type: str = "estimated"  # "real_youtube", "real_archive", "estimated"
    view_count: int = 0
    channel_subscribers: int = 0
    engagement_rate: float = 0.0
    published_at: str = ""
    data_fetched_at: str = ""

    def is_real_data(self) -> bool:
        """Check if this pattern is based on real measured data."""
        return self.source_type in ("real_youtube", "real_archive")


@dataclass
class TrendReport:
    topic: str
    patterns: list[ViralPattern]
    recommended_hooks: list[str]
    recommended_structures: list[str]
    visual_keywords: list[str]
    audio_keywords: list[str]
    generated_at: str
    cache_hit: bool
    # Real data summary
    real_data_count: int = 0
    estimated_data_count: int = 0


class TrendIntelligenceAgent:
    """Discovers viral video patterns for a given topic using free public sources."""

    def __init__(self, cache_dir: Path | None = None):
        self.cache_dir = cache_dir or TREND_CACHE_DIR
        self.cache_dir.mkdir(exist_ok=True)
        self.warnings: list[str] = []

    def analyze(self, topic: str, max_results: int = 20) -> TrendReport:
        """Analyze viral patterns for a topic."""
        cache_file = self.cache_dir / f"{self._slug(topic)}.json"

        if cache_file.exists():
            try:
                with open(cache_file, encoding="utf-8") as f:
                    cached = json.load(f)
                cached_report = TrendReport(**cached)
                cached_report.cache_hit = True
                return cached_report
            except Exception:
                pass

        patterns = self._discover_patterns(topic, max_results)
        report = self._synthesize_report(topic, patterns)

        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(asdict(report), f, indent=2, ensure_ascii=False)
        except Exception:
            pass

        return report

    def _discover_patterns(self, topic: str, max_results: int) -> list[ViralPattern]:
        """Discover patterns from multiple free sources."""
        patterns: list[ViralPattern] = []

        # Source 1: YouTube search via RSS (no API key)
        yt_patterns = self._search_youtube_rss(topic, max_results // 2)
        patterns.extend(yt_patterns)

        # Source 2: Archive.org for historical viral content
        archive_patterns = self._search_archive_org(topic, max_results // 4)
        patterns.extend(archive_patterns)

        # Source 3: Built-in pattern library (curated from public analysis)
        builtin_patterns = self._get_builtin_patterns(topic)
        patterns.extend(builtin_patterns)

        return patterns

    def _search_youtube_rss(self, topic: str, max_results: int) -> list[ViralPattern]:
        """Search YouTube via RSS feeds (public, no API key)."""
        if not REQUESTS_AVAILABLE:
            return []

        patterns: list[ViralPattern] = []
        try:
            # Use invidious instance or RSS
            query = topic.replace(" ", "+")
            url = f"https://yewtu.be/api/v1/search?q={query}&sort_by=view_count"
            resp = requests.get(url, timeout=15)
            if resp.status_code != 200:
                return []

            data = resp.json()
            for item in data[:max_results]:
                title = item.get("title", "").lower()
                desc = item.get("description", "").lower()
                view_count = item.get("view_count", 0) or 0
                channel = item.get("author", "")
                channel_subs = item.get("author_subscriber_count", 0) or 0
                published = item.get("published", "")
                video_url = item.get("url", "")

                pattern = self._analyze_metadata(title, desc, "youtube", video_url)
                if pattern:
                    # Mark as real YouTube data
                    pattern.source_type = "real_youtube"
                    pattern.view_count = view_count
                    pattern.channel_subscribers = channel_subs
                    pattern.published_at = published
                    pattern.data_fetched_at = datetime.now(timezone.utc).isoformat()
                    # Calculate engagement rate
                    if channel_subs > 0:
                        pattern.engagement_rate = view_count / channel_subs
                    # Normalize view count by channel size
                    if channel_subs > 1000:
                        pattern.confidence = min(0.9, 0.5 + (view_count / max(channel_subs, 1000)) * 0.4)
                    patterns.append(pattern)

        except Exception as e:
            self.warnings.append(f"YouTube RSS search failed: {e}")

        return patterns

    def _search_archive_org(self, topic: str, max_results: int) -> list[ViralPattern]:
        """Search Internet Archive for viral content patterns."""
        if not REQUESTS_AVAILABLE:
            return []

        patterns: list[ViralPattern] = []
        try:
            query = topic.replace(" ", "%20")
            url = f"https://archive.org/advancedsearch.php?q={query}&fl=identifier,title,description,mediatype&rows={max_results}&output=json"
            resp = requests.get(url, timeout=15)
            if resp.status_code != 200:
                return []

            data = resp.json()
            for doc in data.get("response", {}).get("docs", []):
                title = doc.get("title", "").lower()
                desc = doc.get("description", "")
                if isinstance(desc, list):
                    desc = " ".join(desc)
                desc = desc.lower()
                identifier = doc.get("identifier", "")

                pattern = self._analyze_metadata(title, desc, "archive_org", f"https://archive.org/details/{identifier}")
                if pattern:
                    # Mark as real Archive.org data
                    pattern.source_type = "real_archive"
                    pattern.view_count = doc.get("downloads", 0) or 0
                    pattern.published_at = doc.get("date", "")
                    pattern.data_fetched_at = datetime.now(timezone.utc).isoformat()
                    pattern.confidence = 0.8
                    patterns.append(pattern)

        except Exception as e:
            self.warnings.append(f"Archive.org search failed: {e}")

        return patterns

    def _analyze_metadata(self, title: str, description: str, platform: str, url: str) -> ViralPattern | None:
        """Analyze video metadata for viral patterns."""
        text = f"{title} {description}"

        # Detect hook type
        hook_type = "generic"
        for kw in VIRAL_KEYWORDS:
            if kw in text:
                hook_type = kw.replace(" ", "_")
                break

        # Detect structure
        structure = "linear"
        if any(w in text for w in ["before", "after", "then", "now", "evolution", "history"]):
            structure = "chronological"
        elif any(w in text for w in ["secret", "hidden", "revealed", "truth"]):
            structure = "reveal"
        elif any(w in text for w in ["vs", "versus", "compare", "comparison"]):
            structure = "comparison"
        elif any(w in text for w in ["how to", "tutorial", "guide", "step"]):
            structure = "tutorial"
        elif any(w in text for w in ["story", "journey", "experience"]):
            structure = "narrative"

        # Detect visual style keywords
        visual_keywords = []
        for kw in ["cinematic", "documentary", "animation", "3d", "vfx", "motion graphics",
                   "kinetic", "typography", "archive", "footage", "b-roll", "drone", "timelapse"]:
            if kw in text:
                visual_keywords.append(kw)
        visual_style = ", ".join(visual_keywords) if visual_keywords == ["documentary"] else "modern_cinematic"

        # Detect pacing
        pacing = "medium"
        if any(w in text for w in ["fast", "quick", "speed", "rapid"]):
            pacing = "fast"
        elif any(w in text for w in ["slow", "deep", "detailed", "long"]):
            pacing = "slow"

        # Audio design
        audio_keywords = []
        for kw in ["music", "soundtrack", "narration", "voiceover", "sound design", "sfx", "effects", "ambient"]:
            if kw in text:
                audio_keywords.append(kw)
        audio_design = ", ".join(audio_keywords) if audio_keywords else "music_plus_narration"

        # Caption style
        caption_style = "sentence"
        if any(w in text for w in ["word by word", "karaoke", "highlight"]):
            caption_style = "word-by-word"
        elif any(w in text for w in ["dynamic", "animated", "moving"]):
            caption_style = "animated"

        return ViralPattern(
            hook_type=hook_type,
            structure=structure,
            visual_style=visual_style,
            pacing=pacing,
            audio_design=audio_design,
            caption_style=caption_style,
            platform=platform,
            source_url=url,
            observed_at=datetime.now(timezone.utc).isoformat(),
            confidence=0.7,
        )

    def _get_builtin_patterns(self, topic: str) -> list[ViralPattern]:
        """Return curated viral patterns based on topic category."""
        topic_lower = topic.lower()
        patterns: list[ViralPattern] = []

        # History/tech documentary patterns
        if any(w in topic_lower for w in ["history", "rise", "fall", "evolution", "origin", "koda", "technology", "invention", "company"]):
            patterns.extend([
                ViralPattern("hook_question", "chronological", "cinematic_historical", "medium", "orchestral_plus_narration", "sentence", "builtin", "", datetime.now(timezone.utc).isoformat(), 0.9, "estimated"),
                ViralPattern("hook_reveal", "reveal", "cinematic_modern", "fast", "tension_music_plus_narration", "animated_keywords", "builtin", "", datetime.now(timezone.utc).isoformat(), 0.85, "estimated"),
                ViralPattern("hook_transformation", "before_after", "cinematic_contrast", "medium", "emotional_music_plus_narration", "sentence", "builtin", "", datetime.now(timezone.utc).isoformat(), 0.85, "estimated"),
            ])

        # Science/explanation patterns
        if any(w in topic_lower for w in ["how", "why", "works", "science", "physics", "technology", "engineering"]):
            patterns.extend([
                ViralPattern("hook_curiosity", "problem_solution", "clean_educational", "medium", "clear_narration_plus_subtle_music", "word_by_word", "builtin", "", datetime.now(timezone.utc).isoformat(), 0.9, "estimated"),
                ViralPattern("hook_visual", "visual_journey", "animated_diagram", "fast", "upbeat_music_plus_narration", "animated", "builtin", "", datetime.now(timezone.utc).isoformat(), 0.85, "estimated"),
            ])

        # Story/personal patterns
        if any(w in topic_lower for w in ["story", "journey", "experience", "life", "career", "mistake", "lesson"]):
            patterns.extend([
                ViralPattern("hook_personal", "narrative", "intimate_cinematic", "slow", "emotional_music_plus_voice", "sentence", "builtin", "", datetime.now(timezone.utc).isoformat(), 0.9, "estimated"),
            ])

        # Default fallback patterns
        if not patterns:
            patterns.extend([
                ViralPattern("hook_question", "linear", "modern_cinematic", "medium", "music_plus_narration", "sentence", "builtin", "", datetime.now(timezone.utc).isoformat(), 0.7, "estimated"),
                ViralPattern("hook_curiosity", "problem_solution", "clean_visual", "medium", "narration_plus_subtle_music", "sentence", "builtin", "", datetime.now(timezone.utc).isoformat(), 0.7, "estimated"),
            ])

        return patterns

    def _synthesize_report(self, topic: str, patterns: list[ViralPattern]) -> TrendReport:
        """Synthesize patterns into actionable recommendations."""
        if not patterns:
            patterns = self._get_builtin_patterns(topic)

        # Count real vs estimated data
        real_count = sum(1 for p in patterns if p.is_real_data())
        estimated_count = len(patterns) - real_count

        # Count pattern frequencies
        hook_counts: dict[str, int] = {}
        structure_counts: dict[str, int] = {}
        visual_keywords: set[str] = set()
        audio_keywords: set[str] = set()

        for p in patterns:
            hook_counts[p.hook_type] = hook_counts.get(p.hook_type, 0) + 1
            structure_counts[p.structure] = structure_counts.get(p.structure, 0) + 1
            visual_keywords.update(p.visual_style.split(", "))
            audio_keywords.update(p.audio_design.split(", "))

        # Sort by frequency
        recommended_hooks = sorted(hook_counts.keys(), key=lambda k: -hook_counts[k])[:5]
        recommended_structures = sorted(structure_counts.keys(), key=lambda k: -structure_counts[k])[:5]

        return TrendReport(
            topic=topic,
            patterns=patterns,
            recommended_hooks=recommended_hooks,
            recommended_structures=recommended_structures,
            visual_keywords=sorted(visual_keywords),
            audio_keywords=sorted(audio_keywords),
            generated_at=datetime.now(timezone.utc).isoformat(),
            cache_hit=False,
            real_data_count=real_count,
            estimated_data_count=estimated_count,
        )

    @staticmethod
    def _slug(value: str) -> str:
        """Generate a short, deterministic cache key from a topic.
        
        Format: <short-slug>-<hash8> (max ~24 chars)
        """
        import hashlib
        slug_part = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:16]
        hash_part = hashlib.sha256(value.encode()).hexdigest()[:8]
        return f"{slug_part}-{hash_part}" if slug_part else f"untitled-{hash_part}"


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Trend Intelligence Agent")
    parser.add_argument("topic")
    parser.add_argument("--max-results", type=int, default=20)
    args = parser.parse_args()

    agent = TrendIntelligenceAgent()
    report = agent.analyze(args.topic, args.max_results)
    print(json.dumps(asdict(report), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())