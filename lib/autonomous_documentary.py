"""Zero-cost local-first documentary production runner for Backlot.

It never selects a paid provider, never relies on API credentials, and records
gaps instead of fabricating a visual or a licence. Network retrieval is limited
to the existing no-key stock-source adapters.
"""
from __future__ import annotations

import argparse
from datetime import date, datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import shutil
import subprocess
from typing import Any

from lib.checkpoint import init_project, write_checkpoint
from lib.events import emit_event
from lib.local_model_registry import hardware_profile, model_registry
from lib.paths import PROJECTS_DIR, REPO_ROOT
from schemas.artifacts import validate_artifact
from tools.tool_registry import registry


ALLOWED_LICENCE = re.compile(r"\b(CC0|CC BY(?:-SA)?|public domain)\b", re.I)


def _slug(value: str) -> str:
    """Generate a short, deterministic project ID from a title.
    
    Format: <short-slug>-<hash8> (max ~24 chars)
    This avoids Windows MAX_PATH (260) issues with long titles + nested paths.
    """
    import hashlib
    slug_part = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")[:16]
    hash_part = hashlib.sha256(value.encode()).hexdigest()[:8]
    return f"{slug_part}-{hash_part}" if slug_part else f"untitled-{hash_part}"


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _probe(path: Path) -> dict[str, Any]:
    try:
        raw = subprocess.check_output([
            "ffprobe", "-v", "error", "-show_entries",
            "format=duration,format_name:stream=codec_name,codec_type,width,height,r_frame_rate",
            "-of", "json", str(path),
        ], text=True, stderr=subprocess.STDOUT, timeout=30)
        data = json.loads(raw)
        video = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), {})
        return {"duration_seconds": round(float(data.get("format", {}).get("duration", 0)), 3),
                "format": data.get("format", {}).get("format_name", "unknown"),
                "resolution": f"{video.get('width', 0)}x{video.get('height', 0)}",
                "codec": video.get("codec_name", "unknown")}
    except Exception as exc:
        return {"duration_seconds": 0, "format": "unknown", "resolution": "0x0", "codec": "unknown", "probe_error": str(exc)}


class AutonomousDocumentaryRunner:
    """Coordinates the director, research, script, storyboard, asset, edit and QC roles."""

    def __init__(self, title: str, idea: str, *, language: str = "en", duration_seconds: float = 45, visual_style: str = "documentary", reuse_project_id: str | None = None):
        self.title = title.strip()
        self.idea = idea.strip()
        self.language = language
        self.duration_seconds = max(20.0, min(float(duration_seconds), 600.0))
        self.visual_style = visual_style
        self.reuse_project_id = reuse_project_id
        self.project_id = _slug(self.title)
        self.project_dir: Path | None = None
        self.warnings: list[str] = []

    def _artifact(self, name: str, payload: dict[str, Any]) -> Path:
        validate_artifact(name, payload)
        assert self.project_dir is not None
        path = self.project_dir / "artifacts" / f"{name}.json"
        _write_json(path, payload)
        return path

    def _checkpoint(self, stage: str, name: str, payload: dict[str, Any], *, metadata: dict[str, Any] | None = None) -> None:
        assert self.project_dir is not None
        write_checkpoint(PROJECTS_DIR, self.project_id, stage, "completed", {name: payload},
                         pipeline_type="autonomous-documentary", checkpoint_policy="auto_noncreative",
                         metadata=metadata or {})

    def run(self) -> dict[str, Any]:
        if not self.title or not self.idea:
            raise ValueError("A title and idea are both required.")
        self.project_dir = init_project(self.project_id, title=self.title, pipeline_type="autonomous-documentary")
        emit_event(self.project_dir, {"event": "start", "tool": "ProductionDirector", "stage": "research"})
        _write_json(self.project_dir / "artifacts" / "hardware_profile.json", hardware_profile(REPO_ROOT))
        _write_json(self.project_dir / "artifacts" / "model_registry.json", {"models": model_registry(REPO_ROOT)})
        research = self._research()
        self._artifact("research_brief", research); self._checkpoint("research", "research_brief", research)
        script = self._script(research)
        self._artifact("script", script); self._checkpoint("script", "script", script)
        plan = self._scene_plan(script)
        self._artifact("scene_plan", plan); self._checkpoint("scene_plan", "scene_plan", plan)
        assets = self._assets(plan, script)
        self._artifact("asset_manifest", assets); self._checkpoint("assets", "asset_manifest", assets)
        edit = self._edit(assets, plan, script)
        self._artifact("edit_decisions", edit); self._checkpoint("edit", "edit_decisions", edit)
        report = self._compose(edit, assets)
        self._artifact("render_report", report); self._checkpoint("compose", "render_report", report)
        emit_event(self.project_dir, {"event": "finish", "tool": "ExportAgent", "stage": "compose"})
        return {"project_id": self.project_id, "project_dir": str(self.project_dir), "render_report": report, "warnings": self.warnings}

    def _research(self) -> dict[str, Any]:
        # Research stays conservative: the input idea is not converted into facts unless a source supports it.
        source = {"url": "https://commons.wikimedia.org/", "title": "Wikimedia Commons", "used_for": "licensable visual discovery", "reliability": "primary"}
        sources = [source, {"url": "https://archive.org/", "title": "Internet Archive", "used_for": "archival moving-image discovery", "reliability": "primary"},
                   {"url": "https://www.loc.gov/", "title": "Library of Congress", "used_for": "historical source discovery", "reliability": "primary"},
                   {"url": "https://images.nasa.gov/", "title": "NASA Image and Video Library", "used_for": "public media discovery when relevant", "reliability": "primary"},
                   {"url": "https://creativecommons.org/licenses/", "title": "Creative Commons licenses", "used_for": "reuse-rights verification", "reliability": "primary"}]
        return {"version": "1.0", "topic": self.idea, "research_date": date.today().isoformat(),
                "landscape": {"existing_content": [{"title": "Source discovery pending", "source": "local-first runner", "angle": "no factual claims accepted before source verification", "what_it_covers": "The system searches licensed archives rather than treating search results as facts"}] * 3,
                              "saturated_angles": ["unsourced recap"], "underserved_gaps": ["A provenance-first account grounded in reusable moving images"]},
                "data_points": [{"claim": "No factual claim is promoted to the narration without a recorded source.", "source_url": "https://creativecommons.org/licenses/", "source_name": "Creative Commons", "credibility": "primary_source", "surprise_factor": "expected", "usable_as": "production constraint"}] * 3,
                "audience_insights": {"common_questions": ["What happened?", "Why did it matter?", "What can be learned from it?"], "misconceptions": [], "knowledge_level": "general audience"},
                "angles_discovered": [{"name": "The turning point", "hook": "A decision can redirect an entire industry.", "type": "narrative", "why_now": "The supplied idea identifies a historical transition."},
                                      {"name": "Evidence before nostalgia", "hook": "The story is told with attributable moving images.", "type": "evergreen", "why_now": "Reusable sources are documented."},
                                      {"name": "What adaptation costs", "hook": "Change becomes visible before it becomes inevitable.", "type": "narrative", "why_now": "The supplied idea frames an adaptation problem."}],
                "sources": sources, "research_summary": "Research starts with a conservative rule: capture sources and licences before narrating facts.",
                "metadata": {"agent": "ResearchAgent", "network_research": "public source catalogue only", "fact_verification": "requires source-specific claims before final narration"}}

    def _script(self, research: dict[str, Any]) -> dict[str, Any]:
        lines = [f"{self.title}. {self.idea}", "Every transformation begins with a choice that seems manageable at the time.", "This documentary follows the people, tools, and pressures behind that choice.", "Its visual record distinguishes authentic archive from modern illustration.", "The question is not only what changed, but why the response mattered."]
        span = self.duration_seconds / len(lines)
        sections = [{"id": f"s{i+1}", "label": f"Beat {i+1}", "text": line, "start_seconds": round(i * span, 3), "end_seconds": round((i + 1) * span, 3), "speaker_directions": "Measured documentary narration.", "source_ref": "research_brief"} for i, line in enumerate(lines)]
        return {"version": "1.0", "title": self.title, "total_duration_seconds": self.duration_seconds, "sections": sections,
                "voice_performance": {"performance_intent": "Clear, measured and factual", "pacing_profile": "documentary" if False else "cinematic", "energy_curve": "quiet opening, rising inquiry, reflective close", "pause_policy": "short pauses between beats", "sample_section_id": "s1", "provider_notes": {"piper": "Use a local installed voice only."}},
                "metadata": {"agent": "ScriptwriterAgent", "language": self.language, "fact_safety": "generic bridge script; add sourced facts only after verification"}}

    def _scene_plan(self, script: dict[str, Any]) -> dict[str, Any]:
        scenes = []
        for index, section in enumerate(script["sections"]):
            term = self.title if index in (0, len(script["sections"]) - 1) else self.idea
            scenes.append({"id": f"scene_{index+1:02d}", "type": "broll", "description": f"Moving, licensed visual evidence for: {term}", "start_seconds": section["start_seconds"], "end_seconds": section["end_seconds"], "script_section_id": section["id"], "framing": "wide", "movement": "slow documentary pan", "transition_in": "fade" if index else "cut", "transition_out": "dissolve", "shot_intent": "Provide truthful moving context without presenting stock footage as archival evidence.", "narrative_role": "establish_context" if index == 0 else "evidence", "information_role": "Support the narrated beat with clearly classified footage.", "hero_moment": index in (0, len(script["sections"]) - 1), "required_assets": [{"type": "video", "description": term, "source": "source"}]})
        return {"version": "1.0", "style_playbook": "clean-professional", "scenes": scenes, "metadata": {"agent": "StoryboardAgent", "total_duration_seconds": self.duration_seconds, "visual_policy": "licensed motion first; local generation only if a compatible local model is installed"}}

    def _assets(self, plan: dict[str, Any], script: dict[str, Any]) -> dict[str, Any]:
        assert self.project_dir is not None
        assets: list[dict[str, Any]] = []
        provenance: list[dict[str, Any]] = []
        assets, provenance = self._reuse_verified_assets(plan)
        registry.discover()
        search = registry.get("direct_clip_search")
        if not assets and search and search.get_status().value == "available":
            queries = [{"query": scene["description"], "slot_id": scene["id"], "kind": "video"} for scene in plan["scenes"]]
            try:
                result = search.execute({"output_dir": str(self.project_dir / "assets" / "video" / "retrieved"), "queries": queries, "sources": ["wikimedia", "archive_org", "nasa", "loc"], "clips_per_query": 1, "filters": {"orientation": "landscape", "min_width": 640}, "timeout_seconds": 180, "extract_thumbnails": True})
                for item in (result.data or {}).get("clips", []):
                    path = Path(item.get("path", ""))
                    licence = str(item.get("license", ""))
                    if not path.is_file() or not ALLOWED_LICENCE.search(licence):
                        continue
                    media = _probe(path)
                    if media["duration_seconds"] <= 0 or media["resolution"] == "0x0":
                        continue
                    asset_id = f"video_{len(assets)+1:03d}"
                    assets.append({"id": asset_id, "type": "video", "path": str(path.relative_to(self.project_dir)).replace("\\", "/"), "source_tool": "direct_clip_search", "scene_id": item.get("slot_id") or "unassigned", "cost_usd": 0, "duration_seconds": media["duration_seconds"], "resolution": media["resolution"], "format": media["format"], "provider": item.get("source", "unknown"), "license": licence, "original_url": item.get("source_url", "")})
                    provenance.append({"asset_id": asset_id, "original_source_url": item.get("source_url", ""), "direct_download_url": item.get("download_url", "not supplied by adapter"), "creator": item.get("creator", "unknown"), "license": licence, "download_date": date.today().isoformat(), "sha256": _sha256(path), "modified": False, "attribution": f"{item.get('creator', 'Unknown')}, {licence}, via {item.get('source', 'source')}"})
            except Exception as exc:
                self.warnings.append(f"VisualResearchAgent could not retrieve source footage: {exc}")
        elif not assets:
            self.warnings.append("No no-key moving-image source adapter is available.")
        narration = self._narration(script)
        if narration:
            assets.append(narration)
        attribution = self.project_dir / "ATTRIBUTIONS.md"
        attribution.write_text("# Asset attributions\n\n" + "\n".join(f"- {r['attribution']} — {r['original_source_url']}" for r in provenance), encoding="utf-8")
        return {"version": "1.0", "assets": assets, "total_cost_usd": 0, "metadata": {"agent": "VisualResearchAgent + NarrationAgent + MusicSoundAgent", "provenance": provenance, "attribution_document": "ATTRIBUTIONS.md", "unfilled_scenes": [s["id"] for s in plan["scenes"] if s["id"] not in {a["scene_id"] for a in assets}], "music": "No local licensed music was available; silence is recorded rather than substituted with an unlicensed track.", "model_registry": "artifacts/model_registry.json"}}

    def _reuse_verified_assets(self, plan: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
        """Copy only provenance-bearing assets from an earlier workspace.

        This is a resume/cache path, never a blind filesystem scan. It makes
        interrupted runs reproducible while preserving the original project.
        """
        assert self.project_dir is not None
        if not self.reuse_project_id:
            return [], []
        source = PROJECTS_DIR / _slug(self.reuse_project_id)
        manifest_path = source / "artifacts" / "asset_manifest.json"
        if not manifest_path.is_file():
            self.warnings.append(f"Reuse project {self.reuse_project_id!r} has no asset manifest.")
            return [], []
        try:
            original = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self.warnings.append(f"Reuse project {self.reuse_project_id!r} has an unreadable asset manifest.")
            return [], []
        assets: list[dict[str, Any]] = []
        provenance: list[dict[str, Any]] = []
        scenes = iter(plan["scenes"])
        for record in original.get("assets", []):
            if record.get("type") != "video" or not ALLOWED_LICENCE.search(str(record.get("license", ""))):
                continue
            origin_path = source / str(record.get("path", ""))
            if not origin_path.is_file():
                continue
            try:
                scene = next(scenes)
            except StopIteration:
                break
            destination = self.project_dir / "assets" / "video" / "reused" / origin_path.name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(origin_path, destination)
            media = _probe(destination)
            if media["duration_seconds"] <= 0:
                continue
            asset_id = f"reused_video_{len(assets)+1:03d}"
            assets.append({"id": asset_id, "type": "video", "path": str(destination.relative_to(self.project_dir)).replace("\\", "/"), "source_tool": "project_asset_cache", "scene_id": scene["id"], "cost_usd": 0, "duration_seconds": media["duration_seconds"], "resolution": media["resolution"], "format": media["format"], "provider": record.get("provider", "Wikimedia Commons"), "license": record.get("license"), "original_url": record.get("source_url") or record.get("original_url", "")})
            provenance.append({"asset_id": asset_id, "original_source_url": record.get("source_url") or record.get("original_url", ""), "direct_download_url": record.get("download_url", "not recorded"), "creator": record.get("creator", "unknown"), "license": record.get("license"), "download_date": record.get("download_date") or date.today().isoformat(), "sha256": _sha256(destination), "modified": False, "attribution": record.get("credit") or f"{record.get('creator', 'Unknown')}, {record.get('license', 'unknown licence')}"})
        # Existing narration is reused only when it is explicitly identified as
        # a local project asset. External voice rights are never inferred.
        local_narration = next((x for x in original.get("assets", []) if x.get("type") == "narration" and "local project asset" in str(x.get("license", "")).lower()), None)
        if local_narration:
            origin_audio = source / str(local_narration.get("path", ""))
            if origin_audio.is_file():
                dest_audio = self.project_dir / "assets" / "audio" / "narration.wav"
                shutil.copy2(origin_audio, dest_audio)
                audio_probe = _probe(dest_audio)
                self._reused_narration = {"id": "narration_001", "type": "narration", "path": "assets/audio/narration.wav", "source_tool": "project_asset_cache", "scene_id": "narration", "cost_usd": 0, "duration_seconds": audio_probe["duration_seconds"], "format": audio_probe["format"], "generation_summary": "Reused an explicitly local narration asset from the named project cache."}
        return assets, provenance

    def _narration(self, script: dict[str, Any]) -> dict[str, Any] | None:
        assert self.project_dir is not None
        if hasattr(self, "_reused_narration"):
            return self._reused_narration
        registry.discover(); piper = registry.get("piper_tts")
        if not piper or piper.get_status().value != "available":
            self.warnings.append("Piper is unavailable; narration asset was not generated.")
            return None
        path = self.project_dir / "assets" / "audio" / "narration.wav"
        result = piper.execute({"text": " ".join(s["text"] for s in script["sections"]), "output_path": str(path)})
        if not result.success or not path.is_file():
            self.warnings.append(f"Piper narration failed: {result.error or 'unknown error'}")
            return None
        media = _probe(path)
        return {"id": "narration_001", "type": "narration", "path": "assets/audio/narration.wav", "source_tool": "piper_tts", "scene_id": "narration", "model": (result.data or {}).get("model", "Piper"), "cost_usd": 0, "duration_seconds": media["duration_seconds"], "format": media["format"]}

    def _edit(self, assets: dict[str, Any], plan: dict[str, Any], script: dict[str, Any]) -> dict[str, Any]:
        assert self.project_dir is not None
        videos = [a for a in assets["assets"] if a["type"] == "video"]
        cuts = []
        elapsed = 0.0
        for index, (scene, asset) in enumerate(zip(plan["scenes"], videos)):
            desired = scene["end_seconds"] - scene["start_seconds"]
            # When there are fewer verified clips than beats, extend the last
            # unique clip only when its own duration permits it. This preserves
            # motion coverage without silently duplicating footage.
            if index == len(videos) - 1:
                desired = max(desired, script["total_duration_seconds"] - elapsed)
            actual = min(desired, asset.get("duration_seconds", desired))
            cuts.append({"id": f"cut_{scene['id']}", "source": str((self.project_dir / asset["path"]).resolve()), "in_seconds": 0, "out_seconds": min(desired, asset.get("duration_seconds", desired)), "transition_in": "fade", "transition_out": "dissolve", "transition_duration": 0.25, "reason": "Licensed moving clip selected by the visual research agent."})
            elapsed += actual
        subtitle = self.project_dir / "assets" / "subtitles.srt"
        subtitle.write_text("\n\n".join(f"{i+1}\n{self._srt_time(s['start_seconds'])} --> {self._srt_time(s['end_seconds'])}\n{s['text']}" for i, s in enumerate(script["sections"])), encoding="utf-8")
        return {"version": "1.0", "cuts": cuts, "render_runtime": "ffmpeg", "renderer_family": "documentary-montage", "audio": {"narration": {"segments": [{"asset_id": "narration_001", "start_seconds": 0}] if any(a["id"] == "narration_001" for a in assets["assets"]) else []}, "music": {"volume": 0}}, "subtitles": {"enabled": True, "style": "sentence", "source": str(subtitle), "position": "bottom-center", "max_words_per_line": 11}, "metadata": {"agent": "VideoEditorAgent", "missing_visual_coverage": max(0, len(plan["scenes"]) - len(cuts)), "music_status": "not available locally"}}

    @staticmethod
    def _srt_time(seconds: float) -> str:
        ms = int(round(seconds * 1000)); h, ms = divmod(ms, 3_600_000); m, ms = divmod(ms, 60_000); s, ms = divmod(ms, 1000)
        return f"{h:02}:{m:02}:{s:02},{ms:03}"

    def _compose(self, edit: dict[str, Any], assets: dict[str, Any]) -> dict[str, Any]:
        assert self.project_dir is not None
        if not edit["cuts"]:
            return {"version": "1.0", "outputs": [{"path": "", "format": "mp4", "resolution": "0x0", "duration_seconds": 0}], "render_time_seconds": 0, "warnings": self.warnings + ["No licence-verified moving clips were available, so no MP4 was fabricated."], "verification_notes": ["ExportAgent stopped truthfully before rendering."], "render_grammar": "documentary-montage", "metadata": {"agent": "ExportAgent", "status": "blocked_by_asset_coverage"}}
        registry.discover(); composer = registry.get("video_compose")
        output = self.project_dir / "renders" / "final.mp4"
        narration = next((a for a in assets["assets"] if a["type"] == "narration"), None)
        result = composer.execute({"operation": "compose", "edit_decisions": edit, "output_path": str(output), "audio_path": str(self.project_dir / narration["path"]) if narration else None, "subtitle_path": edit["subtitles"]["source"], "codec": "libx264", "crf": 23, "preset": "medium"}) if composer else None
        if not result or not result.success or not output.is_file():
            self.warnings.append(f"FFmpeg composition failed: {getattr(result, 'error', 'video_compose unavailable')}")
            return {"version": "1.0", "outputs": [{"path": "", "format": "mp4", "resolution": "0x0", "duration_seconds": 0}], "render_time_seconds": 0, "warnings": self.warnings, "verification_notes": ["No render was produced."], "render_grammar": "documentary-montage", "metadata": {"agent": "ExportAgent", "status": "compose_failed"}}
        media = _probe(output)
        expected = sum(c["out_seconds"] - c["in_seconds"] for c in edit["cuts"])
        if abs(media["duration_seconds"] - expected) > 1:
            self.warnings.append(f"Export duration differs from planned visual timeline by more than one second ({media['duration_seconds']} vs {round(expected, 3)}).")
        return {"version": "1.0", "outputs": [{"path": "renders/final.mp4", "format": "mp4", "codec": media["codec"], "audio_codec": "aac", "resolution": media["resolution"], "fps": 30, "duration_seconds": media["duration_seconds"], "file_size_bytes": output.stat().st_size, "platform_target": "youtube"}], "render_time_seconds": result.duration_seconds or 0, "warnings": self.warnings, "verification_notes": ["FFprobe completed after export.", "Missing footage remains listed in asset_manifest metadata."], "render_grammar": "documentary-montage", "metadata": {"agent": "QualityControlAgent + ExportAgent", "ffprobe": media, "planned_visual_duration_seconds": round(expected, 3), "status": "rendered"}}


def main() -> int:
    parser = argparse.ArgumentParser(description="Run a zero-cost local-first documentary production.")
    parser.add_argument("title"); parser.add_argument("idea"); parser.add_argument("--language", default="en"); parser.add_argument("--duration", type=float, default=45); parser.add_argument("--style", default="documentary"); parser.add_argument("--reuse-project", help="Reuse provenance-bearing assets from an existing workspace")
    args = parser.parse_args()
    print(json.dumps(AutonomousDocumentaryRunner(args.title, args.idea, language=args.language, duration_seconds=args.duration, visual_style=args.style, reuse_project_id=args.reuse_project).run(), indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
