"""Viral Pattern Agent — extracts structural patterns from successful videos.

Analyzes viral videos to identify winning formulas: hook types, narrative structures,
visual language, pacing, audio design, and retention techniques.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from lib.trend_intelligence import TrendIntelligenceAgent, TrendReport, ViralPattern


# 21 Hook Formulas from youtube-agent-skill (hooks.json)
HOOK_FORMULAS = [
    {
        "id": "the-statistic",
        "name": "The Statistic",
        "shape": "A number the viewer did not know, stated flat, then the consequence.",
        "example": "97% of the people who start a channel quit before video 30. Here is what the other 3% do differently.",
        "fails_when": "Dies if the number is vague or unverifiable. Say the source out loud.",
        "patterns": [r"\b\d+(\.\d+)?\s?%", r"\b\d+ (out of|in) \d+\b", r"\b\d{2,}(,\d{3})+\b"],
    },
    {
        "id": "someone-elses-result",
        "name": "Someone Else's Result",
        "shape": "A named person's outcome, then the mechanism.",
        "example": "This channel went from 400 subscribers to 200,000 in seven months on one format. I mapped it.",
        "fails_when": "Do not invent the number. If you cannot name the channel, use a different formula.",
        "patterns": [r"\bthis (channel|guy|creator|account)\b", r"\bwent from .* to\b", r"\bin (a|one|two|three|\d+) (week|month|year)s?\b"],
    },
    {
        "id": "the-mistake",
        "name": "The Mistake",
        "shape": "Name the error the viewer is probably making right now.",
        "example": "Your first 30 seconds are why nobody finishes your videos. It is not the topic.",
        "fails_when": "Only works if the mistake is common and the viewer can check it in one second.",
        "patterns": [r"\byou('re| are) (probably |still )?(doing|making)\b", r"\bthe (mistake|reason) (everyone|most people|nobody)\b", r"\bstop (doing )?\b"],
    },
    {
        "id": "contrarian-flip",
        "name": "Contrarian Flip",
        "shape": "State the accepted advice, then reject it.",
        "example": "Everyone says post daily. I posted once a week for a year and tripled the channel.",
        "fails_when": "Needs evidence in the next 15 seconds or it reads as contrarian for its own sake.",
        "patterns": [r"\beveryone (says|thinks|tells you)\b", r"\bis (actually )?wrong\b", r"\bnobody (tells|talks about)\b"],
    },
    {
        "id": "the-reveal",
        "name": "The Reveal",
        "shape": "Promise a specific thing will be shown, then show it.",
        "example": "I am going to show you the exact prompt, on screen, that wrote this video.",
        "fails_when": "You have to actually show it, early. A reveal at 8:00 is a retention cliff at 1:00.",
        "patterns": [r"\bI('m| am) going to show you\b", r"\bhere('s| is) (the|exactly)\b", r"\bon screen\b"],
    },
    {
        "id": "the-superlative",
        "name": "The Superlative",
        "shape": "The single best/worst/fastest of a category.",
        "example": "This is the fastest way to turn one long video into thirty Shorts.",
        "fails_when": "Superlatives are cheap. Earn it by naming what it beat.",
        "patterns": [r"\bthe (best|worst|fastest|easiest|only)\b", r"\bnumber one\b"],
    },
    {
        "id": "the-clock",
        "name": "The Clock",
        "shape": "Bound the payoff in time.",
        "example": "In the next six minutes you will have a working title, thumbnail and script for your next video.",
        "fails_when": "The clock has to be true. Overrun it and the next video's hook is not believed.",
        "patterns": [r"\bin (the next )?\d+ (seconds|minutes|hours)\b", r"\bby the end of this video\b", r"\bunder \d+\b"],
    },
    {
        "id": "i-tried-it",
        "name": "I Tried It",
        "shape": "First-person experiment with a stated cost.",
        "example": "I let an AI run my channel for 30 days. I did not touch the uploads.",
        "fails_when": "Needs a real cost - time, money, risk - or there is no stake.",
        "patterns": [r"\bI (tried|spent|tested|let|gave)\b", r"\bfor \d+ (days|weeks|months)\b", r"\bso you don'?t have to\b"],
    },
    {
        "id": "the-question",
        "name": "The Question",
        "shape": "Ask the exact question the viewer typed into search.",
        "example": "Why do your videos die at 30 seconds when the topic is fine?",
        "fails_when": "Must be the viewer's question, not yours. Pull it from your own comments.",
        "patterns": [r"^(why|how|what|when|should|can|do|does|is)\b", r"\?\s*$"],
    },
    {
        "id": "the-before-after",
        "name": "Before and After",
        "shape": "Two states, one cut between them.",
        "example": "This was my thumbnail. This is my thumbnail now. Same video, four times the click-through.",
        "fails_when": "Only works with a visual. Do not use it on a talking-head-only video.",
        "patterns": [r"\bbefore\b.*\bafter\b", r"\bthis was\b.*\bthis is\b", r"\bused to\b"],
    },
    {
        "id": "the-teardown",
        "name": "The Teardown",
        "shape": "Take a real thing apart in public.",
        "example": "I pulled the nine most-viewed AI videos of the month and broke down what the titles share.",
        "fails_when": "Name what you pulled and how many. A teardown of one example is an anecdote.",
        "patterns": [r"\b(broke|break|breaking) (it )?down\b", r"\bteardown\b", r"\banalys(ed|ed|is|e)\b", r"\bI pulled\b"],
    },
    {
        "id": "the-stack",
        "name": "The Stack",
        "shape": "Two named tools combined into one outcome.",
        "example": "Claude plus your YouTube Studio export gives you next week's upload schedule in one prompt.",
        "fails_when": "Both tools must be nameable and the outcome must need both.",
        "patterns": [r"\b\w+ (plus|\+) \w+\b", r"\bcombine\b", r"\btogether\b"],
    },
    {
        "id": "the-warning",
        "name": "The Warning",
        "shape": "A cost the viewer is about to pay.",
        "example": "Do not upload another video until you check this one setting.",
        "fails_when": "If the cost is small the hook is a lie. Reserve it.",
        "patterns": [r"\bdo not\b", r"\bdon'?t (upload|post|publish|start)\b", r"\bbefore you\b", r"\bstop\b"],
    },
    {
        "id": "the-list",
        "name": "The List",
        "shape": "A counted set, with the count in the first line.",
        "example": "Seven things I would do differently if I started a channel in 2026.",
        "fails_when": "The count must be exact and every item must be different in kind.",
        "patterns": [r"^\d+ \w+", r"\b(here are|these are) \d+\b"],
    },
    {
        "id": "the-receipt",
        "name": "The Receipt",
        "shape": "Show the artifact first, explain second.",
        "example": "This is the analytics page. This video did 40% of the channel's watch time. Here is why.",
        "fails_when": "Requires a real screenshot. A described receipt is not a receipt.",
        "patterns": [r"\bthis is (the|my)\b", r"\bscreenshot\b", r"\bproof\b", r"\breceipts?\b"],
    },
    {
        "id": "the-insider",
        "name": "The Insider",
        "shape": "Information from inside a system.",
        "example": "YouTube tells you which videos are underperforming. Almost nobody opens the report.",
        "fails_when": "Do not claim insider access you do not have.",
        "patterns": [r"\b(nobody|almost nobody|most people) (knows?|opens?|uses?)\b", r"\bhidden\b", r"\bburied\b"],
    },
    {
        "id": "the-impossible",
        "name": "The Impossible Claim",
        "shape": "State something that sounds untrue, then prove it.",
        "example": "You can write, title, thumbnail and schedule a week of videos without opening a single editor.",
        "fails_when": "The proof has to start within 20 seconds or it reads as clickbait.",
        "patterns": [r"\bwithout\b", r"\bnever\b", r"\bin one\b", r"\bzero\b"],
    },
    {
        "id": "the-comparison",
        "name": "The Comparison",
        "shape": "Two named options, one winner.",
        "example": "I wrote the same video three ways. One of them held 62% and the other two did not.",
        "fails_when": "Say the losing option out loud. A comparison with no loser is an advert.",
        "patterns": [r"\bvs\.?\b", r"\bversus\b", r"\bwhich (one )?(is|wins)\b", r"\bsame .* (three|two) ways\b"],
    },
    {
        "id": "the-origin",
        "name": "The Origin",
        "shape": "Where a result actually came from.",
        "example": "Every video on this channel starts in the same 12-line file. Here it is.",
        "fails_when": "Works once per channel. It is a reveal about you, and you only have one.",
        "patterns": [r"\bevery (video|post) .* starts\b", r"\bit all (starts|started)\b", r"\bthe (real )?reason\b"],
    },
    {
        "id": "the-deadline",
        "name": "The Deadline",
        "shape": "Something is changing on a date.",
        "example": "The old description format stops mattering this month. Here is what replaces it.",
        "fails_when": "Only use with a real, checkable date. This is the fastest formula to lose trust with.",
        "patterns": [r"\b(this|next) (week|month|year)\b", r"\bis changing\b", r"\bno longer\b", r"\bas of\b"],
    },
    {
        "id": "the-direct-address",
        "name": "The Direct Address",
        "shape": "Name the exact viewer in the first six words.",
        "example": "If you have under a thousand subscribers, this is the only video you need this week.",
        "fails_when": "Narrow beats broad. 'If you make videos' addresses nobody.",
        "patterns": [r"^if you\b", r"\bfor (anyone|everyone|people) who\b", r"\byou specifically\b"],
    },
]


# Scoring weights (from hookscore.py)
FILLER = {"basically", "actually", "literally", "just", "really", "very", "so", "kind", "sort", "like",
          "guys", "hey", "welcome", "today", "video", "subscribe", "channel"}
VAGUE = {"amazing", "incredible", "insane", "crazy", "huge", "massive", "game", "changer", "secret",
         "powerful", "ultimate", "best", "revolutionary", "mind", "blowing", "unbelievable"}
CONCRETE_RE = re.compile(r"\b(\d[\d,.]*\s?(%|k|m|x|s|m|h)?|\$\d|\d+\s?(second|minute|hour|day|week|month|year)s?)\b", re.I)
YOU_RE = re.compile(r"\b(you|your|you're|youre|yourself)\b", re.I)
STAKE_RE = re.compile(r"\b(lose|lost|wasting|waste|quit|fail|broke|cost|risk|before|stop|never|die|dying|dead)\b", re.I)
CURIOSITY_RE = re.compile(r"\b(why|how|what|which|until|before|but|nobody|almost|except|reason|actually)\b", re.I)


@dataclass
class ViralVideoPattern:
    """Structural pattern extracted from a viral video."""
    hook_type: str
    hook_formula_id: str
    hook_formula_name: str
    hook_score: int
    narrative_structure: str
    visual_style: str
    pacing: str
    audio_design: str
    caption_style: str
    retention_techniques: list[str]
    scene_transitions: list[str]
    platform: str
    source_url: str
    views: int
    channel_median_views: int
    multiple: float
    confidence: float
    analyzed_at: str


@dataclass
class ViralPatternReport:
    """Synthesized viral patterns for a topic."""
    topic: str
    patterns: list[ViralVideoPattern]
    top_hook_formulas: list[dict[str, Any]]
    top_structures: list[dict[str, Any]]
    visual_keywords: list[str]
    audio_keywords: list[str]
    retention_techniques: list[str]
    recommended_hooks: list[str]
    recommended_structures: list[str]
    generated_at: str
    cache_hit: bool


class HookScorer:
    """Scores hooks against 5 properties: Specificity, Address, Stakes, Curiosity, Brevity."""

    @staticmethod
    def words(text: str) -> list[str]:
        return re.findall(r"[a-z0-9'%$.]+", text.lower())

    @staticmethod
    def specificity(text: str) -> int:
        w = HookScorer.words(text)
        if not w:
            return 0
        nums = len(CONCRETE_RE.findall(text))
        vague = sum(1 for x in w if x in VAGUE)
        filler = sum(1 for x in w if x in FILLER)
        s = 34 + nums * 22 - vague * 16 - filler * 5
        s += min(18, 6 * sum(1 for x in text.split()[1:] if x[:1].isupper()))
        return max(0, min(100, s))

    @staticmethod
    def address(text: str) -> int:
        n = len(YOU_RE.findall(text))
        first = 30 if YOU_RE.search(" ".join(text.split()[:6])) else 0
        return max(0, min(100, 26 + n * 20 + first))

    @staticmethod
    def stakes(text: str) -> int:
        n = len(STAKE_RE.findall(text))
        return max(0, min(100, 22 + n * 26 + (14 if CONCRETE_RE.search(text) else 0)))

    @staticmethod
    def curiosity(text: str) -> int:
        n = len(CURIOSITY_RE.findall(text))
        q = 18 if text.strip().endswith("?") else 0
        closed = -18 if re.search(r"\b(because|so that|which means)\b", text, re.I) else 0
        return max(0, min(100, 24 + n * 17 + q + closed))

    @staticmethod
    def brevity(text: str) -> int:
        n = len(HookScorer.words(text))
        if n == 0:
            return 0
        if 9 <= n <= 24:
            return 100
        if n < 9:
            return max(30, 100 - (9 - n) * 11)
        return max(10, 100 - (n - 24) * 7)

    @classmethod
    def score(cls, hook: str) -> dict[str, Any]:
        parts = {
            "SPECIFICITY": cls.specificity(hook),
            "ADDRESS": cls.address(hook),
            "STAKES": cls.stakes(hook),
            "CURIOSITY": cls.curiosity(hook),
            "BREVITY": cls.brevity(hook),
        }
        vals = list(parts.values())
        verdict = round(0.6 * (sum(vals) / len(vals)) + 0.4 * min(vals))

        # Classify against formulas
        best_formula, hits = None, 0
        for f in HOOK_FORMULAS:
            n = sum(1 for p in f["patterns"] if re.search(p, hook, re.I))
            if n > hits:
                best_formula, hits = f, n

        return {
            "properties": parts,
            "verdict": verdict,
            "band": "STRONG" if verdict >= 72 else "WORKABLE" if verdict >= 55 else "WEAK",
            "formula": best_formula["name"] if best_formula else "Unclassified",
            "formula_id": best_formula["id"] if best_formula else "unknown",
            "matched_patterns": hits,
            "weakest": min(parts, key=parts.get),
        }


class ViralPatternAgent:
    """Extracts viral video patterns from trend intelligence and public sources."""

    def __init__(self, cache_dir: Path | None = None):
        self.trend_agent = TrendIntelligenceAgent(cache_dir)
        self.cache_dir = cache_dir or Path(".trend_cache")
        self.cache_dir.mkdir(exist_ok=True)
        self.hook_scorer = HookScorer()

    def analyze(self, topic: str, max_results: int = 20) -> ViralPatternReport:
        """Analyze viral patterns for a topic."""
        cache_file = self.cache_dir / f"viral_patterns_{self._slug(topic)}.json"

        if cache_file.exists():
            try:
                with open(cache_file, encoding="utf-8") as f:
                    cached = json.load(f)
                # Convert patterns dicts to ViralVideoPattern dataclasses
                if "patterns" in cached:
                    cached["patterns"] = [ViralVideoPattern(**p) if isinstance(p, dict) else p for p in cached["patterns"]]
                cached_report = ViralPatternReport(**cached)
                cached_report.cache_hit = True
                return cached_report
            except Exception:
                pass

        # Get trend report first
        trend_report = self.trend_agent.analyze(topic, max_results)

        # Extract viral patterns from trend data
        patterns = self._extract_viral_patterns(topic, trend_report)

        # Synthesize report
        report = self._synthesize_report(topic, patterns, trend_report)

        try:
            with open(cache_file, "w", encoding="utf-8") as f:
                json.dump(asdict(report), f, indent=2, ensure_ascii=False)
        except Exception:
            pass

        return report

    def _extract_viral_patterns(self, topic: str, trend_report: TrendReport) -> list[ViralVideoPattern]:
        """Extract detailed viral patterns from trend report."""
        patterns: list[ViralVideoPattern] = []

        for p in trend_report.patterns:
            # Handle both dataclass and dict (from cache)
            if isinstance(p, dict):
                hook_type = p.get("hook_type", "generic")
                structure = p.get("structure", "linear")
                visual_style = p.get("visual_style", "modern_cinematic")
                pacing = p.get("pacing", "medium")
                audio_design = p.get("audio_design", "music_plus_narration")
                caption_style = p.get("caption_style", "sentence")
                platform = p.get("platform", "unknown")
                source_url = p.get("source_url", "")
                confidence = p.get("confidence", 0.7)
            else:
                hook_type = p.hook_type
                structure = p.structure
                visual_style = p.visual_style
                pacing = p.pacing
                audio_design = p.audio_design
                caption_style = p.caption_style
                platform = p.platform
                source_url = p.source_url
                confidence = p.confidence

            # Score the hook type against formulas
            hook_text = hook_type.replace("_", " ")
            score_result = self.hook_scorer.score(hook_text)

            pattern = ViralVideoPattern(
                hook_type=hook_type,
                hook_formula_id=score_result["formula_id"],
                hook_formula_name=score_result["formula"],
                hook_score=score_result["verdict"],
                narrative_structure=structure,
                visual_style=visual_style,
                pacing=pacing,
                audio_design=audio_design,
                caption_style=caption_style,
                retention_techniques=self._infer_retention_techniques_from_dict({
                    "pacing": pacing,
                    "caption_style": caption_style,
                    "structure": structure,
                    "audio_design": audio_design,
                    "hook_type": hook_type,
                }),
                scene_transitions=self._infer_transitions_from_dict({
                    "structure": structure,
                    "visual_style": visual_style,
                    "pacing": pacing,
                }),
                platform=platform,
                source_url=source_url,
                views=0,
                channel_median_views=0,
                multiple=1.0,
                confidence=confidence,
                analyzed_at=datetime.now(timezone.utc).isoformat(),
            )
            patterns.append(pattern)

        # Add built-in high-confidence patterns for the topic
        builtin = self._get_builtin_viral_patterns(topic)
        patterns.extend(builtin)

        return patterns

    def _infer_retention_techniques(self, p: ViralPattern) -> list[str]:
        """Infer retention techniques from pattern metadata (dataclass version)."""
        return self._infer_retention_techniques_from_dict({
            "pacing": p.pacing,
            "caption_style": p.caption_style,
            "structure": p.structure,
            "audio_design": p.audio_design,
            "hook_type": p.hook_type,
        })

    def _infer_retention_techniques_from_dict(self, p: dict) -> list[str]:
        """Infer retention techniques from pattern metadata (dict version)."""
        techniques = []
        if p.get("pacing") == "fast":
            techniques.append("rapid_cuts")
        if "animated" in p.get("caption_style", ""):
            techniques.append("animated_captions")
        if p.get("structure") in ("reveal", "before_after", "comparison"):
            techniques.append("curiosity_gaps")
        if "tension" in p.get("audio_design", "") or "emotional" in p.get("audio_design", ""):
            techniques.append("audio_tension")
        if p.get("hook_type") in ("hook_reveal", "hook_question", "hook_curiosity"):
            techniques.append("strong_hook")
        return techniques

    def _infer_transitions(self, p: ViralPattern) -> list[str]:
        """Infer scene transition types from pattern (dataclass version)."""
        return self._infer_transitions_from_dict({
            "structure": p.structure,
            "visual_style": p.visual_style,
            "pacing": p.pacing,
        })

    def _infer_transitions_from_dict(self, p: dict) -> list[str]:
        """Infer scene transition types from pattern (dict version)."""
        transitions = ["cut"]
        if p.get("structure") == "chronological":
            transitions.append("match_cut")
        if p.get("structure") == "before_after":
            transitions.append("split_screen")
        if p.get("visual_style") in ("cinematic_modern", "cinematic_contrast"):
            transitions.extend(["whip_pan", "glitch"])
        if p.get("pacing") == "fast":
            transitions.append("jump_cut")
        return list(set(transitions))

    def _get_builtin_viral_patterns(self, topic: str) -> list[ViralVideoPattern]:
        """Return curated high-confidence viral patterns for topic categories."""
        topic_lower = topic.lower()
        patterns: list[ViralVideoPattern] = []

        # History/tech documentary patterns (e.g., Kodak)
        if any(w in topic_lower for w in ["history", "rise", "fall", "evolution", "origin", "koda", "technology", "invention", "company", "corporate"]):
            patterns.extend([
                ViralVideoPattern(
                    hook_type="hook_reveal", hook_formula_id="the-reveal", hook_formula_name="The Reveal",
                    hook_score=88, narrative_structure="reveal", visual_style="cinematic_historical",
                    pacing="medium", audio_design="orchestral_plus_narration", caption_style="sentence",
                    retention_techniques=["curiosity_gaps", "audio_tension", "strong_hook", "visual_reveal"],
                    scene_transitions=["match_cut", "whip_pan", "glitch"],
                    platform="builtin", source_url="", views=0, channel_median_views=0, multiple=1.0,
                    confidence=0.95, analyzed_at=datetime.now(timezone.utc).isoformat(),
                ),
                ViralVideoPattern(
                    hook_type="hook_transformation", hook_formula_id="the-before-after", hook_formula_name="Before and After",
                    hook_score=85, narrative_structure="before_after", visual_style="cinematic_contrast",
                    pacing="medium", audio_design="emotional_music_plus_narration", caption_style="sentence",
                    retention_techniques=["curiosity_gaps", "visual_reveal", "emotional_payoff"],
                    scene_transitions=["split_screen", "match_cut", "fade"],
                    platform="builtin", source_url="", views=0, channel_median_views=0, multiple=1.0,
                    confidence=0.9, analyzed_at=datetime.now(timezone.utc).isoformat(),
                ),
                ViralVideoPattern(
                    hook_type="hook_question", hook_formula_id="the-question", hook_formula_name="The Question",
                    hook_score=82, narrative_structure="investigation", visual_style="cinematic_modern",
                    pacing="fast", audio_design="tension_music_plus_narration", caption_style="animated_keywords",
                    retention_techniques=["curiosity_gaps", "rapid_cuts", "audio_tension"],
                    scene_transitions=["jump_cut", "whip_pan", "glitch"],
                    platform="builtin", source_url="", views=0, channel_median_views=0, multiple=1.0,
                    confidence=0.85, analyzed_at=datetime.now(timezone.utc).isoformat(),
                ),
            ])

        # Science/explanation patterns
        if any(w in topic_lower for w in ["how", "why", "works", "science", "physics", "technology", "engineering", "explained"]):
            patterns.extend([
                ViralVideoPattern(
                    hook_type="hook_curiosity", hook_formula_id="the-question", hook_formula_name="The Question",
                    hook_score=90, narrative_structure="problem_solution", visual_style="clean_educational",
                    pacing="medium", audio_design="clear_narration_plus_subtle_music", caption_style="word_by_word",
                    retention_techniques=["strong_hook", "visual_reveal", "clear_structure"],
                    scene_transitions=["cut", "fade", "zoom"],
                    platform="builtin", source_url="", views=0, channel_median_views=0, multiple=1.0,
                    confidence=0.9, analyzed_at=datetime.now(timezone.utc).isoformat(),
                ),
                ViralVideoPattern(
                    hook_type="hook_visual", hook_formula_id="the-reveal", hook_formula_name="The Reveal",
                    hook_score=85, narrative_structure="visual_journey", visual_style="animated_diagram",
                    pacing="fast", audio_design="upbeat_music_plus_narration", caption_style="animated",
                    retention_techniques=["visual_reveal", "animated_captions", "rapid_cuts"],
                    scene_transitions=["jump_cut", "zoom", "pan"],
                    platform="builtin", source_url="", views=0, channel_median_views=0, multiple=1.0,
                    confidence=0.85, analyzed_at=datetime.now(timezone.utc).isoformat(),
                ),
            ])

        # Story/personal patterns
        if any(w in topic_lower for w in ["story", "journey", "experience", "life", "career", "mistake", "lesson"]):
            patterns.extend([
                ViralVideoPattern(
                    hook_type="hook_personal", hook_formula_id="the-direct-address", hook_formula_name="The Direct Address",
                    hook_score=88, narrative_structure="narrative", visual_style="intimate_cinematic",
                    pacing="slow", audio_design="emotional_music_plus_voice", caption_style="sentence",
                    retention_techniques=["emotional_payoff", "strong_hook", "audio_tension"],
                    scene_transitions=["cut", "cross_dissolve", "slow_push"],
                    platform="builtin", source_url="", views=0, channel_median_views=0, multiple=1.0,
                    confidence=0.9, analyzed_at=datetime.now(timezone.utc).isoformat(),
                ),
            ])

        # Default fallback
        if not patterns:
            patterns.extend([
                ViralVideoPattern(
                    hook_type="hook_question", hook_formula_id="the-question", hook_formula_name="The Question",
                    hook_score=70, narrative_structure="linear", visual_style="modern_cinematic",
                    pacing="medium", audio_design="music_plus_narration", caption_style="sentence",
                    retention_techniques=["strong_hook"], scene_transitions=["cut"],
                    platform="builtin", source_url="", views=0, channel_median_views=0, multiple=1.0,
                    confidence=0.7, analyzed_at=datetime.now(timezone.utc).isoformat(),
                ),
            ])

        return patterns

    def _synthesize_report(
        self,
        topic: str,
        patterns: list[ViralVideoPattern],
        trend_report: TrendReport,
    ) -> ViralPatternReport:
        """Synthesize patterns into actionable recommendations."""
        if not patterns:
            patterns = self._get_builtin_viral_patterns(topic)

        # Count hook formula frequencies
        hook_counts: dict[str, int] = {}
        formula_details: dict[str, dict] = {}
        structure_counts: dict[str, int] = {}
        visual_keywords: set[str] = set()
        audio_keywords: set[str] = set()
        retention_techniques: set[str] = set()

        for p in patterns:
            fid = p.hook_formula_id
            hook_counts[fid] = hook_counts.get(fid, 0) + 1
            if fid not in formula_details:
                formula_details[fid] = {
                    "formula_id": fid,
                    "formula_name": p.hook_formula_name,
                    "avg_score": p.hook_score,
                    "count": 0,
                }
            formula_details[fid]["count"] += 1
            formula_details[fid]["avg_score"] = (formula_details[fid]["avg_score"] + p.hook_score) / 2

            structure_counts[p.narrative_structure] = structure_counts.get(p.narrative_structure, 0) + 1
            visual_keywords.update(p.visual_style.split(", "))
            audio_keywords.update(p.audio_design.split(", "))
            retention_techniques.update(p.retention_techniques)

        # Sort by frequency and score
        top_hooks = sorted(
            formula_details.values(),
            key=lambda x: (x["count"], x["avg_score"]),
            reverse=True
        )[:5]

        top_structures = sorted(
            [{"structure": k, "count": v} for k, v in structure_counts.items()],
            key=lambda x: -x["count"]
        )[:5]

        recommended_hooks = [h["formula_id"] for h in top_hooks]
        recommended_structures = [s["structure"] for s in top_structures]

        return ViralPatternReport(
            topic=topic,
            patterns=patterns,
            top_hook_formulas=top_hooks,
            top_structures=top_structures,
            visual_keywords=sorted(visual_keywords),
            audio_keywords=sorted(audio_keywords),
            retention_techniques=sorted(retention_techniques),
            recommended_hooks=recommended_hooks,
            recommended_structures=recommended_structures,
            generated_at=datetime.now(timezone.utc).isoformat(),
            cache_hit=False,
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
    parser = argparse.ArgumentParser(description="Viral Pattern Agent")
    parser.add_argument("topic")
    parser.add_argument("--max-results", type=int, default=20)
    args = parser.parse_args()

    agent = ViralPatternAgent()
    report = agent.analyze(args.topic, args.max_results)
    print(json.dumps(asdict(report), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())