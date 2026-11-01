"""Retention Agent — analyzes audience retention to find leaks and recommend fixes.

Based on youtube-agent-skill's yt-retention: reads YouTube Studio CSV exports,
identifies hook leaks, cliffs, and slides, maps to transcript for actionable fixes.
"""

from __future__ import annotations

import csv
import json
import re
import statistics
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from lib.script_writer import Script, ScriptSection


@dataclass
class RetentionPoint:
    """Single point on the retention curve."""
    position: float  # seconds or percentage
    percentage: float  # viewers remaining


@dataclass
class RetentionLeak:
    """A detected leak in retention."""
    type: str  # "hook_leak", "cliff", "slide"
    position_seconds: float
    position_percentage: float
    severity: float  # percentage points lost
    description: str
    transcript_context: str = ""
    fix_recommendation: str = ""


@dataclass
class RetentionReport:
    """Complete retention analysis report."""
    video_duration_seconds: float
    start_retention: float
    end_retention: float
    hook_leak_percentage: float
    hook_leak_verdict: str  # "healthy", "leaking", "severe"
    cliffs: list[RetentionLeak]
    slide_rate: float  # percentage points per unit time
    slide_verdict: str  # "flat", "moderate", "steep"
    total_leaks: int
    biggest_leak: Optional[RetentionLeak]
    primary_fix: str
    secondary_fixes: list[str]
    analyzed_at: str


class RetentionAgent:
    """Analyzes YouTube audience retention data to find where viewers leave."""

    def __init__(self):
        pass

    def analyze(
        self,
        retention_csv: Path,
        transcript_path: Optional[Path] = None,
        video_duration: Optional[float] = None,
    ) -> RetentionReport:
        """Analyze retention CSV and optionally map to transcript."""
        rows = self._load_csv(retention_csv)
        if len(rows) < 8:
            raise ValueError("Could not read at least 8 data points from CSV")

        # Determine if axis is percentage or seconds
        xs = [r[0] for r in rows]
        ys = [r[1] for r in rows]
        pct_axis = max(xs) <= 100.5

        # Get duration
        duration = video_duration
        if pct_axis and not duration:
            # Try to infer from transcript or use last point
            duration = 600  # default 10 min

        def at_seconds(x: float) -> float:
            if pct_axis and duration:
                return x / 100.0 * duration
            return x

        start = ys[0] or 100.0

        # HOOK LEAK: first 30 seconds (or 10% if percentage axis)
        cutoff = 30.0 if not pct_axis else (30.0 / duration * 100 if duration else 10.0)
        hook_end = min((y for x, y in rows if x <= cutoff), default=start)
        hook_leak = start - hook_end

        if hook_leak < 25:
            hook_verdict = "healthy"
        elif hook_leak < 40:
            hook_verdict = "leaking"
        else:
            hook_verdict = "severe"

        # CLIFFS: single steep drops
        drops = []
        for i in range(1, len(rows)):
            d = ys[i - 1] - ys[i]
            span = xs[i] - xs[i - 1] or 1
            drops.append((d / span, xs[i - 1], xs[i], d))

        drops.sort(reverse=True)
        cliffs = []
        for _, a1, b1, d in drops[:5]:
            if d > 0.8:  # threshold for cliff
                cliffs.append(RetentionLeak(
                    type="cliff",
                    position_seconds=round(at_seconds(a1), 1),
                    position_percentage=round(a1, 2),
                    severity=round(d, 2),
                    description=f"Drop of {d:.1f}% between {a1:.1f} and {b1:.1f}",
                    fix_recommendation=self._cliff_fix(d, a1, b1),
                ))

        # SLIDE: steady bleed across middle
        mid_drops = [d for d, x0, _, _ in drops if x0 > cutoff]
        slide = sum(mid_drops) / len(mid_drops) if mid_drops else 0

        if slide < 0.1:
            slide_verdict = "flat"
        elif slide < 0.3:
            slide_verdict = "moderate"
        else:
            slide_verdict = "steep"

        # Map cliffs to transcript if provided
        transcript_cues = []
        if transcript_path and transcript_path.exists():
            transcript_cues = self._load_transcript(transcript_path)
            for cliff in cliffs:
                if cliff.position_seconds is not None:
                    t = cliff.position_seconds
                    near = [q[2] for q in transcript_cues if q[0] <= t + 4 and q[1] >= t - 4]
                    cliff.transcript_context = " ".join(near)[:140]

        # Determine biggest leak
        all_leaks = cliffs[:]
        if hook_verdict != "healthy":
            all_leaks.insert(0, RetentionLeak(
                type="hook_leak",
                position_seconds=0,
                position_percentage=0,
                severity=hook_leak,
                description=f"Hook leak: {hook_leak:.1f}% lost in first 30s",
                fix_recommendation="Fix the first 15 seconds of script. Hook must confirm title, open curiosity gap, prove payoff.",
            ))

        if slide_verdict != "flat":
            all_leaks.append(RetentionLeak(
                type="slide",
                position_seconds=cutoff if not pct_axis else at_seconds(cutoff),
                position_percentage=cutoff,
                severity=slide,
                description=f"Slide: {slide:.3f}% per unit across middle",
                fix_recommendation="Cut the middle. A flat slide is pacing, not content. Remove filler, tighten transitions.",
            ))

        biggest = max(all_leaks, key=lambda l: l.severity) if all_leaks else None

        # Primary fix
        if biggest and biggest.type == "hook_leak":
            primary = "Rewrite the hook. The first 15 seconds are the only thing that matters here."
        elif biggest and biggest.type == "cliff":
            primary = f"Fix the cliff at {biggest.position_seconds:.0f}s: {biggest.transcript_context or 'add signposting / remove topic jump / shorten sponsor'}"
        else:
            primary = "Cut the middle. Pacing is the issue, not content."

        # Secondary fixes
        secondary = []
        if hook_verdict != "healthy":
            secondary.append("Hook leak: confirm title promise in first sentence, open uncloseable question, show artifact early")
        for c in cliffs[:2]:
            secondary.append(f"Cliff at {c.position_seconds:.0f}s: {c.fix_recommendation}")
        if slide_verdict != "flat":
            secondary.append("Slide: remove filler sections, add pattern interrupts, tighten edit to 3-5s per beat")

        return RetentionReport(
            video_duration_seconds=duration or 0,
            start_retention=start,
            end_retention=ys[-1],
            hook_leak_percentage=round(hook_leak, 2),
            hook_leak_verdict=hook_verdict,
            cliffs=cliffs,
            slide_rate=round(slide, 3),
            slide_verdict=slide_verdict,
            total_leaks=len(all_leaks),
            biggest_leak=biggest,
            primary_fix=primary,
            secondary_fixes=secondary,
            analyzed_at=datetime.now(timezone.utc).isoformat(),
        )

    def _load_csv(self, path: Path) -> list[tuple[float, float]]:
        """Load retention CSV with flexible parsing."""
        rows = []
        with open(path, newline="", encoding="utf-8-sig", errors="replace") as f:
            for r in csv.reader(f):
                nums = []
                for c in r:
                    c = c.strip().replace("%", "").replace(",", "")
                    try:
                        nums.append(float(c))
                    except ValueError:
                        nums.append(None)
                vals = [n for n in nums if n is not None]
                if len(vals) >= 2:
                    rows.append((vals[0], vals[1]))
        return rows

    def _load_transcript(self, path: Path) -> list[tuple[float, float, str]]:
        """Load SRT/VTT/JSON transcript as (start, end, text) cues."""
        cues = []
        if path.suffix.lower() == ".json":
            import json
            data = json.loads(path.read_text(encoding="utf-8"))
            segs = data.get("segments", data if isinstance(data, list) else [])
            for s in segs:
                cues.append((float(s.get("start", 0)), float(s.get("end", 0)), (s.get("text") or "").strip()))
        else:
            raw = path.read_text(encoding="utf-8", errors="replace")
            cur = None
            for line in raw.splitlines():
                m = re.match(r"\s*(\d[\d:.,]+)\s*-->\s*(\d[\d:.,]+)", line)
                if m:
                    cur = [self._parse_ts(m.group(1)), self._parse_ts(m.group(2)), []]
                    cues.append(cur)
                elif cur is not None and line.strip() and not line.strip().isdigit():
                    cur[2].append(line.strip())
            cues = [(a, b, " ".join(t)) for a, b, t in cues if t]
        return cues

    def _parse_ts(self, s: str) -> float:
        s = s.strip().replace(",", ".")
        p = s.split(":")
        return int(p[0]) * 3600 + int(p[1]) * 60 + float(p[2]) if len(p) == 3 else int(p[0]) * 60 + float(p[1])

    def _cliff_fix(self, drop: float, start: float, end: float) -> str:
        """Recommend fix for a cliff."""
        if drop > 5:
            return "Major topic jump or sponsor read. Add signposting: 'Now I'll show you...' or move sponsor to end."
        if drop > 2:
            return "Pacing issue. Cut filler, tighten transition, add visual change at this moment."
        return "Minor dip. Check for filler words, repeated phrases, or audio glitch."

    def predict_retention(self, script: Script, creative_direction: dict) -> dict[str, Any]:
        """Predict retention curve from script structure (pre-production)."""
        # Analyze script for retention risk factors
        risks = []
        sections = script.sections

        # Hook risk
        hook_section = next((s for s in sections if s.id == "s_hook"), None)
        if hook_section:
            hook_text = hook_section.text
            if len(hook_text.split()) > 30:
                risks.append({"type": "hook_length", "severity": "high", "detail": "Hook exceeds 3 seconds at measured pace"})
            if not any(w in hook_text.lower() for w in ["you", "your", "why", "how", "what", "secret", "hidden"]):
                risks.append({"type": "hook_weak", "severity": "high", "detail": "Hook lacks direct address or curiosity gap"})

        # Section pacing
        for i, sec in enumerate(sections):
            duration = sec.end_seconds - sec.start_seconds
            words = len(sec.text.split())
            wps = words / duration if duration > 0 else 0
            if wps > 3.5:
                risks.append({"type": "too_fast", "severity": "medium", "section": sec.id, "detail": f"{wps:.1f} wps - too fast for comprehension"})
            if wps < 2.0:
                risks.append({"type": "too_slow", "severity": "medium", "section": sec.id, "detail": f"{wps:.1f} wps - risks slide"})

        # Long sections without visual change
        for i, sec in enumerate(sections):
            duration = sec.end_seconds - sec.start_seconds
            if duration > 15:
                risks.append({"type": "long_section", "severity": "medium", "section": sec.id, "detail": f"{duration:.0f}s without scene change"})

        # Predicted curve shape
        predicted_start = 100
        predicted_hook_loss = 15 if not any(r["type"] == "hook_weak" for r in risks) else 35
        predicted_slide = 0.1 if not any(r["type"] in ("too_slow", "long_section") for r in risks) else 0.25

        return {
            "predicted_hook_retention": round(predicted_start - predicted_hook_loss, 1),
            "predicted_slide_rate": predicted_slide,
            "predicted_end_retention": round(max(20, predicted_start - predicted_hook_loss - predicted_slide * 10), 1),
            "risk_factors": risks,
            "recommendations": [
                "Keep hook under 3 seconds (45 words at measured pace)",
                "Add visual change every 5-8 seconds",
                "Vary pacing: measured for explanation, brisk for transitions",
                "End each section with a forward hook to next section",
            ],
        }

    def save(self, report: RetentionReport, project_dir: Path) -> Path:
        """Save retention report to project artifacts."""
        artifacts_dir = project_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        path = artifacts_dir / "retention_report.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(report), f, indent=2, ensure_ascii=False)
        return path


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Retention Agent")
    parser.add_argument("retention_csv", type=Path)
    parser.add_argument("--transcript", type=Path, default=None)
    parser.add_argument("--duration", type=float, default=None)
    args = parser.parse_args()

    agent = RetentionAgent()
    report = agent.analyze(args.retention_csv, args.transcript, args.duration)
    print(json.dumps(asdict(report), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())