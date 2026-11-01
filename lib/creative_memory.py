"""Creative Memory Agent — learns from every production to improve future ones.

Stores: hooks used + scores, script structures, scene durations, visual types,
subtitle styles, edit pacing, QC results, user feedback, actual YouTube performance.

Separates predictions from real performance data.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from lib.creative_director import CreativeDirection
from lib.script_writer import Script
from lib.quality_control import QCReport


@dataclass
class ProductionRecord:
    """Complete record of one production."""
    project_id: str
    title: str
    topic: str
    created_at: str
    # Hook & Script
    hook_used: str
    hook_formula: str
    hook_score: int
    hook_band: str
    script_structure: list[str]
    script_duration_seconds: float
    # Visual
    visual_identity: str
    scene_count: int
    scene_durations: list[float]
    visual_types: list[str]  # "ai_video", "ken_burns", "stock", "reused"
    generation_methods: list[str]
    # Audio
    narration_duration: float
    tts_model: str
    music_style: str
    # Subtitles
    subtitle_style: str
    # Edit
    edit_pacing_avg: float
    transition_types: list[str]
    cut_count: int
    # QC
    qc_overall_passed: bool
    qc_overall_score: float
    qc_technical_score: float
    qc_creative_score: float
    qc_critical_failures: int
    moving_image_ratio: float
    av_sync_offset: float
    # User feedback (post-production)
    user_rating: Optional[int] = None  # 1-5
    user_liked: Optional[list[str]] = None
    user_disliked: Optional[list[str]] = None
    # Real YouTube performance (post-publish)
    youtube_views: Optional[int] = None
    youtube_ctr: Optional[float] = None
    youtube_avg_view_duration: Optional[float] = None
    youtube_retention_at_30s: Optional[float] = None
    youtube_retention_at_50pct: Optional[float] = None
    youtube_retention_at_100pct: Optional[float] = None
    performance_fetched_at: Optional[str] = None


class CreativeMemoryAgent:
    """Persists and queries production history for continuous improvement."""

    def __init__(self, db_path: Path | None = None):
        self.db_path = db_path or Path("creative_memory.db")
        self._init_db()

    def _init_db(self):
        """Initialize SQLite database with schema."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS productions (
                project_id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                topic TEXT NOT NULL,
                created_at TEXT NOT NULL,
                -- Hook & Script
                hook_used TEXT,
                hook_formula TEXT,
                hook_score INTEGER,
                hook_band TEXT,
                script_structure TEXT,  -- JSON array
                script_duration_seconds REAL,
                -- Visual
                visual_identity TEXT,
                scene_count INTEGER,
                scene_durations TEXT,  -- JSON array
                visual_types TEXT,  -- JSON array
                generation_methods TEXT,  -- JSON array
                -- Audio
                narration_duration REAL,
                tts_model TEXT,
                music_style TEXT,
                -- Subtitles
                subtitle_style TEXT,
                -- Edit
                edit_pacing_avg REAL,
                transition_types TEXT,  -- JSON array
                cut_count INTEGER,
                -- QC
                qc_overall_passed INTEGER,
                qc_overall_score REAL,
                qc_technical_score REAL,
                qc_creative_score REAL,
                qc_critical_failures INTEGER,
                moving_image_ratio REAL,
                av_sync_offset REAL,
                -- User feedback
                user_rating INTEGER,
                user_liked TEXT,  -- JSON array
                user_disliked TEXT,  -- JSON array
                -- Real YouTube performance
                youtube_views INTEGER,
                youtube_ctr REAL,
                youtube_avg_view_duration REAL,
                youtube_retention_at_30s REAL,
                youtube_retention_at_50pct REAL,
                youtube_retention_at_100pct REAL,
                performance_fetched_at TEXT
            )
        """)
        conn.commit()
        conn.close()

    def record_production(
        self,
        project_id: str,
        title: str,
        topic: str,
        direction: CreativeDirection,
        script: Script,
        qc_report: QCReport,
        asset_manifest: dict,
        edit_decisions: dict,
        user_feedback: dict | None = None,
    ) -> None:
        """Record a completed production."""
        # Extract hook info
        hook_section = next((s for s in script.sections if s.id == "s_hook"), None)
        hook_used = hook_section.text if hook_section else direction.hook
        hook_score = 0
        hook_formula = ""
        hook_band = ""

        # Visual types
        assets = asset_manifest.get("assets", [])
        visual_types = [a.get("type", "") for a in assets if a.get("type") == "video"]
        generation_methods = [a.get("generation_method", a.get("provider", "")) for a in assets if a.get("type") == "video"]

        # Scene durations
        scenes = direction.scenes
        scene_durations = [s.duration_seconds for s in scenes]

        # Edit pacing
        cuts = edit_decisions.get("cuts", [])
        cut_durations = [c["out_seconds"] - c["in_seconds"] for c in cuts]
        edit_pacing_avg = sum(cut_durations) / len(cut_durations) if cut_durations else 0
        transition_types = list(set(c.get("transition_in", "cut") for c in cuts))

        # QC metrics
        moving_image_ratio = 0.0
        av_sync_offset = 0.0
        for r in qc_report.results:
            if r.check_name == "moving_image_coverage":
                moving_image_ratio = r.score
            elif r.check_name == "av_sync":
                av_sync_offset = float(r.details.split("Offset: ")[-1].split("s")[0]) if "Offset:" in r.details else 0

        record = ProductionRecord(
            project_id=project_id,
            title=title,
            topic=topic,
            created_at=datetime.now(timezone.utc).isoformat(),
            hook_used=hook_used,
            hook_formula=hook_formula,  # Would need to store from hook_script result
            hook_score=hook_score,
            hook_band=hook_band,
            script_structure=direction.narrative_arc,
            script_duration_seconds=script.total_duration_seconds,
            visual_identity=direction.visual_identity,
            scene_count=len(scenes),
            scene_durations=scene_durations,
            visual_types=visual_types,
            generation_methods=generation_methods,
            narration_duration=sum(a.get("duration_seconds", 0) for a in assets if a.get("type") == "narration"),
            tts_model=next((a.get("voice_model", "") for a in assets if a.get("type") == "narration"), ""),
            music_style=direction.music_direction,
            subtitle_style=direction.subtitle_style,
            edit_pacing_avg=edit_pacing_avg,
            transition_types=transition_types,
            cut_count=len(cuts),
            qc_overall_passed=qc_report.overall_passed,
            qc_overall_score=qc_report.overall_score,
            qc_technical_score=qc_report.technical_score,
            qc_creative_score=qc_report.creative_score,
            qc_critical_failures=len([r for r in qc_report.results if r.severity == "critical" and not r.passed]),
            moving_image_ratio=moving_image_ratio,
            av_sync_offset=av_sync_offset,
            user_rating=user_feedback.get("rating") if user_feedback else None,
            user_liked=user_feedback.get("liked") if user_feedback else None,
            user_disliked=user_feedback.get("disliked") if user_feedback else None,
        )

        conn = sqlite3.connect(self.db_path)
        # Check table schema and adjust if needed
        cursor = conn.execute("PRAGMA table_info(productions)")
        columns = [row[1] for row in cursor.fetchall()]
        expected_columns = 39
        if len(columns) != expected_columns:
            # Recreate table with correct schema
            conn.execute("DROP TABLE IF EXISTS productions")
            self._init_db()
            conn = sqlite3.connect(self.db_path)
        
        values = (
            record.project_id, record.title, record.topic, record.created_at,
            record.hook_used, record.hook_formula, record.hook_score, record.hook_band,
            json.dumps(record.script_structure), record.script_duration_seconds,
            record.visual_identity, record.scene_count,
            json.dumps(record.scene_durations), json.dumps(record.visual_types),
            json.dumps(record.generation_methods),
            record.narration_duration, record.tts_model, record.music_style,
            record.subtitle_style,
            record.edit_pacing_avg, json.dumps(record.transition_types), record.cut_count,
            int(record.qc_overall_passed), record.qc_overall_score, record.qc_technical_score,
            record.qc_creative_score, record.qc_critical_failures,
            record.moving_image_ratio, record.av_sync_offset,
            record.user_rating, json.dumps(record.user_liked or []), json.dumps(record.user_disliked or []),
            record.youtube_views, record.youtube_ctr, record.youtube_avg_view_duration,
            record.youtube_retention_at_30s, record.youtube_retention_at_50pct,
            record.youtube_retention_at_100pct, record.performance_fetched_at,
        )
        sql = """
            INSERT OR REPLACE INTO productions VALUES (
                ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?
            )
        """
        conn.execute(sql, values)
        conn.commit()
        conn.close()

    def update_youtube_performance(
        self,
        project_id: str,
        views: int,
        ctr: float,
        avg_view_duration: float,
        retention_30s: float,
        retention_50pct: float,
        retention_100pct: float,
    ) -> None:
        """Update record with real YouTube performance data."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            UPDATE productions SET
                youtube_views = ?, youtube_ctr = ?, youtube_avg_view_duration = ?,
                youtube_retention_at_30s = ?, youtube_retention_at_50pct = ?,
                youtube_retention_at_100pct = ?, performance_fetched_at = ?
            WHERE project_id = ?
        """, (views, ctr, avg_view_duration, retention_30s, retention_50pct,
              retention_100pct, datetime.now(timezone.utc).isoformat(), project_id))
        conn.commit()
        conn.close()

    def update_user_feedback(
        self,
        project_id: str,
        rating: int,
        liked: list[str],
        disliked: list[str],
    ) -> None:
        """Update record with user feedback."""
        conn = sqlite3.connect(self.db_path)
        conn.execute("""
            UPDATE productions SET
                user_rating = ?, user_liked = ?, user_disliked = ?
            WHERE project_id = ?
        """, (rating, json.dumps(liked), json.dumps(disliked), project_id))
        conn.commit()
        conn.close()

    def get_recommendations(self, topic: str, limit: int = 5) -> dict[str, Any]:
        """Get recommendations based on similar past productions."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row

        # Find similar topics (simple keyword match)
        topic_keywords = set(topic.lower().split())
        cursor = conn.execute("SELECT * FROM productions")
        all_records = [dict(row) for row in cursor.fetchall()]

        # Score similarity
        scored = []
        for r in all_records:
            record_keywords = set(r["topic"].lower().split())
            overlap = len(topic_keywords & record_keywords)
            if overlap > 0:
                scored.append((overlap, r))

        scored.sort(key=lambda x: -x[0])
        similar = [r for _, r in scored[:limit]]

        if not similar:
            return self._get_global_recommendations(limit)

        # Aggregate recommendations
        hook_formulas = {}
        structures = {}
        visual_ids = {}
        subtitle_styles = {}
        pacing = []
        qc_scores = []

        for r in similar:
            if r["hook_formula"]:
                hook_formulas[r["hook_formula"]] = hook_formulas.get(r["hook_formula"], 0) + 1
            for s in json.loads(r["script_structure"] or "[]"):
                structures[s] = structures.get(s, 0) + 1
            visual_ids[r["visual_identity"]] = visual_ids.get(r["visual_identity"], 0) + 1
            subtitle_styles[r["subtitle_style"]] = subtitle_styles.get(r["subtitle_style"], 0) + 1
            pacing.append(r["edit_pacing_avg"])
            qc_scores.append(r["qc_overall_score"])

        # YouTube performance correlation
        perf_records = [r for r in similar if r["youtube_views"] is not None]
        perf_correlation = {}
        if perf_records:
            top_perf = max(perf_records, key=lambda x: x["youtube_retention_at_30s"] or 0)
            perf_correlation = {
                "best_hook_formula": top_perf["hook_formula"],
                "best_structure": json.loads(top_perf["script_structure"] or "[]")[0] if json.loads(top_perf["script_structure"] or "[]") else "",
                "best_visual_identity": top_perf["visual_identity"],
                "retention_30s": top_perf["youtube_retention_at_30s"],
            }

        return {
            "based_on_productions": len(similar),
            "recommended_hook_formulas": sorted(hook_formulas.items(), key=lambda x: -x[1])[:3],
            "recommended_structures": sorted(structures.items(), key=lambda x: -x[1])[:3],
            "recommended_visual_identities": sorted(visual_ids.items(), key=lambda x: -x[1])[:3],
            "recommended_subtitle_styles": sorted(subtitle_styles.items(), key=lambda x: -x[1])[:3],
            "avg_edit_pacing": round(sum(pacing) / len(pacing), 1) if pacing else 5.0,
            "avg_qc_score": round(sum(qc_scores) / len(qc_scores), 3) if qc_scores else 0.8,
            "performance_correlation": perf_correlation,
            "note": "Predictions based on past productions. Real YouTube performance (when available) carries more weight.",
        }

    def _get_global_recommendations(self, limit: int) -> dict[str, Any]:
        """Global recommendations when no similar topics exist."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM productions WHERE qc_overall_passed = 1")
        passed = [dict(row) for row in cursor.fetchall()]

        if not passed:
            return {"note": "No successful productions recorded yet. Run a few first."}

        # Aggregate from all passed
        hook_formulas = {}
        structures = {}
        visual_ids = {}
        for r in passed:
            if r["hook_formula"]:
                hook_formulas[r["hook_formula"]] = hook_formulas.get(r["hook_formula"], 0) + 1
            for s in json.loads(r["script_structure"] or "[]"):
                structures[s] = structures.get(s, 0) + 1
            visual_ids[r["visual_identity"]] = visual_ids.get(r["visual_identity"], 0) + 1

        return {
            "based_on_productions": len(passed),
            "recommended_hook_formulas": sorted(hook_formulas.items(), key=lambda x: -x[1])[:3],
            "recommended_structures": sorted(structures.items(), key=lambda x: -x[1])[:3],
            "recommended_visual_identities": sorted(visual_ids.items(), key=lambda x: -x[1])[:3],
            "note": "Global recommendations from all successful productions.",
        }

    def get_hook_performance(self) -> list[dict]:
        """Get hook formula performance stats."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT hook_formula, hook_score, hook_band, qc_overall_score FROM productions WHERE hook_formula != ''")
        rows = [dict(row) for row in cursor.fetchall()]

        by_formula = {}
        for r in rows:
            f = r["hook_formula"]
            if f not in by_formula:
                by_formula[f] = {"scores": [], "bands": [], "qc_scores": []}
            by_formula[f]["scores"].append(r["hook_score"])
            by_formula[f]["bands"].append(r["hook_band"])
            by_formula[f]["qc_scores"].append(r["qc_overall_score"])

        result = []
        for f, data in by_formula.items():
            result.append({
                "formula": f,
                "count": len(data["scores"]),
                "avg_hook_score": round(sum(data["scores"]) / len(data["scores"]), 1),
                "band_distribution": {b: data["bands"].count(b) for b in set(data["bands"])},
                "avg_qc_score": round(sum(data["qc_scores"]) / len(data["qc_scores"]), 3),
            })
        result.sort(key=lambda x: -x["avg_hook_score"])
        return result

    def export_learning_report(self, output_path: Path) -> Path:
        """Export full learning report as JSON."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        cursor = conn.execute("SELECT * FROM productions ORDER BY created_at DESC")
        records = [dict(row) for row in cursor.fetchall()]

        # Parse JSON fields
        for r in records:
            for field in ["script_structure", "scene_durations", "visual_types", "generation_methods", "transition_types", "user_liked", "user_disliked"]:
                if r[field]:
                    try:
                        r[field] = json.loads(r[field])
                    except:
                        pass

        report = {
            "total_productions": len(records),
            "passed_qc": sum(1 for r in records if r["qc_overall_passed"]),
            "with_user_feedback": sum(1 for r in records if r["user_rating"] is not None),
            "with_youtube_performance": sum(1 for r in records if r["youtube_views"] is not None),
            "hook_performance": self.get_hook_performance(),
            "productions": records,
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }

        output_path.write_text(json.dumps(report, indent=2, ensure_ascii=False), encoding="utf-8")
        return output_path


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Creative Memory Agent")
    parser.add_argument("--db", type=Path, default=Path("creative_memory.db"))
    subparsers = parser.add_subparsers(dest="command")

    subparsers.add_parser("recommend", help="Get recommendations for topic").add_argument("topic")
    subparsers.add_parser("hooks", help="Show hook formula performance")
    subparsers.add_parser("export", help="Export learning report").add_argument("output", type=Path)

    args = parser.parse_args()
    agent = CreativeMemoryAgent(args.db)

    if args.command == "recommend":
        print(json.dumps(agent.get_recommendations(args.topic), indent=2))
    elif args.command == "hooks":
        print(json.dumps(agent.get_hook_performance(), indent=2))
    elif args.command == "export":
        agent.export_learning_report(args.output)
        print(f"Exported to {args.output}")
    else:
        parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())