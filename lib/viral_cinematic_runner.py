"""Viral Cinematic Runner — end-to-end AI video production pipeline.

Integrates: Trend Intelligence → Viral Patterns → Creative Director → Hook & Script →
Title & Thumbnail → Script Writer → Visual Generation → Enhanced TTS →
Subtitle Processor → Cinematic Montage → Compose → QC → Retention Analysis → Creative Memory
"""

from __future__ import annotations

import argparse
import json
import re
import shutil
import subprocess
import time
from dataclasses import asdict, is_dataclass
from pathlib import Path
from typing import Any

from lib.checkpoint import init_project, write_checkpoint
from lib.events import emit_event
from lib.local_model_registry import hardware_profile, model_registry
from lib.local_model_manager import LocalModelManager
from lib.paths import PROJECTS_DIR, REPO_ROOT, safe_artifact_path
from schemas.artifacts import validate_artifact
from tools.tool_registry import registry

from lib.trend_intelligence import TrendIntelligenceAgent
from lib.viral_pattern import ViralPatternAgent
from lib.creative_director import CreativeDirectorAgent
from lib.hook_script import HookScriptAgent
from lib.title_thumbnail import TitleThumbnailAgent
from lib.script_writer import ScriptWriterAgent
from lib.quality_control import QualityControlAgent
from lib.retention_agent import RetentionAgent
from lib.creative_memory import CreativeMemoryAgent
from tools.video.subtitle_processor import generate_subtitles_from_script, SubtitleStyle
from tools.video.local_visual_gen import LocalVisualGenTool
from tools.audio.enhanced_piper_tts import EnhancedPiperTTS


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
    import hashlib
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
        audio = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), {})
        fps_str = video.get("r_frame_rate", "0/1")
        try:
            num, den = map(int, fps_str.split("/"))
            fps = round(num / den, 2) if den else 0
        except Exception:
            fps = 0
        return {
            "duration_seconds": round(float(data.get("format", {}).get("duration", 0)), 3),
            "format": data.get("format", {}).get("format_name", "unknown"),
            "resolution": f"{video.get('width', 0)}x{video.get('height', 0)}",
            "video_codec": video.get("codec_name", "unknown"),
            "audio_codec": audio.get("codec_name", "unknown"),
            "fps": fps,
        }
    except Exception as exc:
        return {"duration_seconds": 0, "format": "unknown", "resolution": "0x0", "video_codec": "unknown", "audio_codec": "unknown", "probe_error": str(exc)}


class ViralCinematicRunner:
    """Orchestrates the full viral cinematic production pipeline."""

    def __init__(
        self,
        title: str,
        idea: str,
        *,
        language: str = "en",
        duration_seconds: float = 45,
        aspect_ratio: str = "16:9",
        visual_style: str = "cinematic",
        reuse_project_id: str | None = None,
        max_retries: int = 2,
    ):
        self.title = title.strip()
        self.idea = idea.strip()
        self.language = language
        self.duration_seconds = max(20.0, min(float(duration_seconds), 600.0))
        self.aspect_ratio = aspect_ratio
        self.visual_style = visual_style
        self.reuse_project_id = reuse_project_id
        self.max_retries = max_retries
        self.project_id = _slug(self.title)
        self.project_dir: Path | None = None
        self.warnings: list[str] = []

        # Initialize local model manager for honest capability reporting
        self.model_manager = LocalModelManager()
        hw_profile = self.model_manager.get_hardware_profile()
        self.warnings.append(f"Hardware: {hw_profile['gpu_vram_mb']}MB VRAM, {hw_profile['system_ram_mb']}MB RAM")
        
        # Check video generation capability
        can_video, video_msg = self.model_manager.can_run_video_generation()
        if not can_video:
            self.warnings.append(f"VIDEO GENERATION LIMITATION: {video_msg}. Using Ken Burns fallback.")
        else:
            self.warnings.append(f"VIDEO GENERATION: {video_msg}")

        # Initialize agents
        self.trend_agent = TrendIntelligenceAgent()
        self.viral_pattern_agent = ViralPatternAgent()
        self.creative_director = CreativeDirectorAgent()
        self.hook_script_agent = HookScriptAgent()
        self.title_thumbnail_agent = TitleThumbnailAgent()
        self.script_writer = ScriptWriterAgent()
        self.qc_agent = QualityControlAgent()
        self.retention_agent = RetentionAgent()
        self.memory_agent = CreativeMemoryAgent()
        self.visual_gen = LocalVisualGenTool()
        self.tts = EnhancedPiperTTS()
        self.subtitle_processor = None  # Created after script

    def _artifact(self, name: str, payload: Any) -> Path:
        # Convert dataclasses to dicts
        if is_dataclass(payload):
            payload = asdict(payload)
        elif hasattr(payload, '__dict__') and not isinstance(payload, dict):
            payload = payload.__dict__

        validate_artifact(name, payload)
        assert self.project_dir is not None
        # Use safe path for Windows long path support
        path = safe_artifact_path(self.project_id, name)
        _write_json(path, payload)
        return path

    def _checkpoint(self, stage: str, name: str, payload: Any, *, metadata: dict[str, Any] | None = None) -> None:
        # Convert dataclasses to dicts
        if is_dataclass(payload):
            payload = asdict(payload)
        elif hasattr(payload, '__dict__') and not isinstance(payload, dict):
            payload = payload.__dict__

        assert self.project_dir is not None
        write_checkpoint(PROJECTS_DIR, self.project_id, stage, "completed", {name: payload},
                         pipeline_type="viral-cinematic", checkpoint_policy="auto_noncreative",
                         metadata=metadata or {})

    def run(self) -> dict[str, Any]:
        if not self.title or not self.idea:
            raise ValueError("A title and idea are both required.")

        self.project_dir = init_project(self.project_id, title=self.title, pipeline_type="viral-cinematic")
        emit_event(self.project_dir, {"event": "start", "tool": "ProductionDirector", "stage": "trends"})

        # Write hardware/model info
        _write_json(self.project_dir / "artifacts" / "hardware_profile.json", hardware_profile(REPO_ROOT))
        _write_json(self.project_dir / "artifacts" / "model_registry.json", {"models": model_registry(REPO_ROOT)})

        # Stage 1: Trend Intelligence
        emit_event(self.project_dir, {"event": "stage", "stage": "trends", "status": "started"})
        trend_report = self.trend_agent.analyze(self.title + " " + self.idea)
        self._artifact("trend_report", trend_report)
        self._checkpoint("trends", "trend_report", trend_report)
        emit_event(self.project_dir, {"event": "stage", "stage": "trends", "status": "completed"})

        # Stage 2: Viral Pattern Analysis
        emit_event(self.project_dir, {"event": "stage", "stage": "viral_patterns", "status": "started"})
        viral_report = self.viral_pattern_agent.analyze(self.title + " " + self.idea)
        self._artifact("viral_pattern_report", viral_report)
        self._checkpoint("viral_patterns", "viral_pattern_report", viral_report)
        emit_event(self.project_dir, {"event": "stage", "stage": "viral_patterns", "status": "completed"})

        # Stage 3: Creative Direction
        emit_event(self.project_dir, {"event": "stage", "stage": "creative_direction", "status": "started"})
        creative_direction = self.creative_director.create_direction(
            self.title, self.idea, trend_report,
            duration_seconds=self.duration_seconds,
            aspect_ratio=self.aspect_ratio,
        )
        self.creative_director.save(creative_direction, self.project_dir)
        self._artifact("creative_direction", creative_direction)
        self._checkpoint("creative_direction", "creative_direction", creative_direction)
        emit_event(self.project_dir, {"event": "stage", "stage": "creative_direction", "status": "completed"})

        # Stage 4: Hook & Script Generation (with scoring)
        emit_event(self.project_dir, {"event": "stage", "stage": "hook_script", "status": "started"})
        hook_script_result = self.hook_script_agent.generate(creative_direction, self.language)
        self.hook_script_agent.save(hook_script_result, self.project_dir)
        self._artifact("hook_script_result", hook_script_result)
        self._checkpoint("hook_script", "hook_script_result", hook_script_result)
        emit_event(self.project_dir, {"event": "stage", "stage": "hook_script", "status": "completed"})

        # Stage 5: Title & Thumbnail (as one unit)
        emit_event(self.project_dir, {"event": "stage", "stage": "title_thumbnail", "status": "started"})
        title_thumbnail_result = self.title_thumbnail_agent.generate(
            creative_direction, hook_script_result.winning_hook.text
        )
        self.title_thumbnail_agent.save(title_thumbnail_result, self.project_dir)
        self._artifact("title_thumbnail_result", title_thumbnail_result)
        self._checkpoint("title_thumbnail", "title_thumbnail_result", title_thumbnail_result)
        emit_event(self.project_dir, {"event": "stage", "stage": "title_thumbnail", "status": "completed"})

        # Update creative direction with winning hook
        creative_direction.hook = hook_script_result.winning_hook.text

        # Stage 6: Script Writing (using winning hook)
        emit_event(self.project_dir, {"event": "stage", "stage": "script", "status": "started"})
        script = self.script_writer.write_script(creative_direction, self.language)
        self.script_writer.save(script, self.project_dir)
        self._artifact("script", script)
        self._checkpoint("script", "script", script)
        emit_event(self.project_dir, {"event": "stage", "stage": "script", "status": "completed"})

        # Stage 7: Scene Plan
        emit_event(self.project_dir, {"event": "stage", "stage": "scene_plan", "status": "started"})
        scene_plan = self._create_scene_plan(creative_direction, script)
        self._artifact("scene_plan", scene_plan)
        self._checkpoint("scene_plan", "scene_plan", scene_plan)
        emit_event(self.project_dir, {"event": "stage", "stage": "scene_plan", "status": "completed"})

        # Stage 8: Visual Generation (with retries)
        emit_event(self.project_dir, {"event": "stage", "stage": "visual_generation", "status": "started"})
        assets = self._generate_visuals_with_retry(creative_direction, scene_plan)
        self._artifact("asset_manifest", assets)
        self._checkpoint("visual_generation", "asset_manifest", assets)
        emit_event(self.project_dir, {"event": "stage", "stage": "visual_generation", "status": "completed"})

        # Stage 8: Narration (Enhanced TTS) - MUST come before scene plan to get duration
        emit_event(self.project_dir, {"event": "stage", "stage": "narration", "status": "started"})
        narration_asset = self._generate_narration(script)
        if narration_asset:
            assets["assets"].append(narration_asset)
            self._artifact("asset_manifest", assets)
        self._checkpoint("narration", "asset_manifest", assets)
        emit_event(self.project_dir, {"event": "stage", "stage": "narration", "status": "completed"})

        # Store narration duration for scene planning
        narration_duration = narration_asset.get("duration_seconds", self.duration_seconds) if narration_asset else self.duration_seconds

        # Stage 10: Subtitle Generation
        emit_event(self.project_dir, {"event": "stage", "stage": "subtitles", "status": "started"})
        subtitle_path = self._generate_subtitles(script, creative_direction)
        self._checkpoint("subtitles", "subtitles", {"path": str(subtitle_path)})
        emit_event(self.project_dir, {"event": "stage", "stage": "subtitles", "status": "completed"})

        # Stage 11: Scene Plan (now after narration to match duration)
        emit_event(self.project_dir, {"event": "stage", "stage": "scene_plan", "status": "started"})
        scene_plan = self._create_scene_plan(creative_direction, script, narration_duration)
        self._artifact("scene_plan", scene_plan)
        self._checkpoint("scene_plan", "scene_plan", scene_plan)
        emit_event(self.project_dir, {"event": "stage", "stage": "scene_plan", "status": "completed"})

        # Stage 12: Cinematic Montage
        emit_event(self.project_dir, {"event": "stage", "stage": "montage", "status": "started"})
        edit_decisions = self._create_edit_decisions(creative_direction, assets, scene_plan, script, subtitle_path)
        self._artifact("edit_decisions", edit_decisions)
        self._checkpoint("montage", "edit_decisions", edit_decisions)
        emit_event(self.project_dir, {"event": "stage", "stage": "montage", "status": "completed"})

        # Stage 12: Compose/Render
        emit_event(self.project_dir, {"event": "stage", "stage": "compose", "status": "started"})
        render_report = self._compose(edit_decisions, assets, subtitle_path)
        self._artifact("render_report", render_report)
        self._checkpoint("compose", "render_report", render_report)
        emit_event(self.project_dir, {"event": "stage", "stage": "compose", "status": "completed"})

        # Stage 13: Quality Control (with auto-retry on failure)
        emit_event(self.project_dir, {"event": "stage", "stage": "quality_control", "status": "started"})
        qc_report = self._quality_control_with_retry(render_report, creative_direction, script, assets)
        self._artifact("qc_report", qc_report)
        self._checkpoint("quality_control", "qc_report", qc_report)
        emit_event(self.project_dir, {"event": "stage", "stage": "quality_control", "status": "completed"})

        # Stage 14: Retention Analysis (predictive)
        emit_event(self.project_dir, {"event": "stage", "stage": "retention_analysis", "status": "started"})
        retention_report = self.retention_agent.predict_retention(script, creative_direction.__dict__ if hasattr(creative_direction, '__dict__') else creative_direction)
        self._artifact("retention_report", retention_report)
        self._checkpoint("retention_analysis", "retention_report", retention_report)
        emit_event(self.project_dir, {"event": "stage", "stage": "retention_analysis", "status": "completed"})

        # Stage 15: Creative Memory (record production)
        emit_event(self.project_dir, {"event": "stage", "stage": "creative_memory", "status": "started"})
        self.memory_agent.record_production(
            project_id=self.project_id,
            title=self.title,
            topic=self.idea,
            direction=creative_direction,
            script=script,
            qc_report=qc_report,
            asset_manifest=assets,
            edit_decisions=edit_decisions,
        )
        self._checkpoint("creative_memory", "memory_update", {"recorded": True})
        emit_event(self.project_dir, {"event": "stage", "stage": "creative_memory", "status": "completed"})

        emit_event(self.project_dir, {"event": "finish", "tool": "ExportAgent", "stage": "compose"})

        return {
            "project_id": self.project_id,
            "project_dir": str(self.project_dir),
            "render_report": render_report,
            "qc_report": asdict(qc_report) if is_dataclass(qc_report) else qc_report,
            "retention_report": retention_report,
            "hook_script_result": asdict(hook_script_result) if hasattr(hook_script_result, '__dict__') else hook_script_result,
            "title_thumbnail_result": asdict(title_thumbnail_result) if hasattr(title_thumbnail_result, '__dict__') else title_thumbnail_result,
            "viral_pattern_report": asdict(viral_report) if hasattr(viral_report, '__dict__') else viral_report,
            "warnings": self.warnings,
        }

    def _create_scene_plan(self, direction: Any, script: Any, narration_duration: float = None) -> dict[str, Any]:
        """Create scene plan from creative direction, matching narration duration."""
        target_duration = narration_duration if narration_duration else self.duration_seconds
        scenes = []
        current_time = 0.0
        num_scenes = len(direction.scenes)
        for i, scene in enumerate(direction.scenes):
            duration = scene.duration_seconds if scene.duration_seconds > 0 else (target_duration / num_scenes)
            scenes.append({
                "id": scene.id,
                "type": "generated" if scene.ai_generation_prompt else "broll",
                "description": scene.visual_concept,
                "start_seconds": round(current_time, 2),
                "end_seconds": round(current_time + duration, 2),
                "script_section_id": f"s_{i+1}",
                "framing": scene.shot_description.split(",")[0] if scene.shot_description else "wide",
                "movement": scene.camera_movement,
                "transition_in": scene.transition_in,
                "transition_out": scene.transition_out,
                "shot_intent": scene.rationale,
                "narrative_role": scene.narrative_beat,
                "information_role": "Support the narrated beat with cinematic visuals.",
                "hero_moment": scene.is_hero_moment,
                "required_assets": [{
                    "type": "video",
                    "description": scene.visual_concept,
                    "source": "generate",
                }],
                "cinematic_metadata": {
                    "color_grade": self._infer_color_grade(scene),
                    "film_grain": False,
                    "vignette": None,
                    "dynamic_zoom": {"factor": 1.08} if duration > 5 else None,
                    "target_aspect": self.aspect_ratio,
                },
            })
            current_time += duration

        return {
            "version": "1.0",
            "style_playbook": self.visual_style,
            "scenes": scenes,
            "metadata": {
                "agent": "CreativeDirectorAgent",
                "total_duration_seconds": target_duration,
                "visual_policy": "AI-generated cinematic visuals first; licensed footage as fallback",
                "aspect_ratio": self.aspect_ratio,
            }
        }

    def _infer_color_grade(self, scene: Any) -> str:
        """Infer color grade from scene concept."""
        concept = scene.visual_concept.lower() if scene.visual_concept else ""
        palette = scene.color_palette.lower() if scene.color_palette else ""

        if "warm" in concept or "nostalgia" in concept or "golden" in concept or "amber" in palette:
            return "warm_nostalgia"
        elif "cold" in concept or "tech" in concept or "digital" in concept or "blue" in palette:
            return "cold_tech"
        elif "vintage" in concept or "historical" in concept or "film" in concept or "sepia" in palette:
            return "vintage_film"
        elif "drama" in concept or "tension" in concept or "dark" in concept:
            return "cinematic_drama"
        elif "contrast" in concept or "split" in concept or "before" in concept or "after" in concept:
            return "teal_orange"
        else:
            return "teal_orange"  # Default viral look

    def _generate_visuals(self, direction: Any, scene_plan: dict[str, Any]) -> dict[str, Any]:
        """Generate visuals for each scene using local AI models."""
        assert self.project_dir is not None

        assets_dir = self.project_dir / "assets" / "video" / "generated"
        assets_dir.mkdir(parents=True, exist_ok=True)

        assets_list = []
        provenance = []

        for i, scene in enumerate(scene_plan.get("scenes", [])):
            scene_id = scene["id"]
            cinematic_meta = scene.get("cinematic_metadata", {})

            # Try AI video generation first
            video_path = None
            generation_method = "ai_video"

            if scene.get("required_assets", [{}])[0].get("source") == "generate":
                prompt = scene.get("visual_concept", "")
                # Get the AI generation prompt from creative direction
                creative_scenes = direction.scenes if hasattr(direction, 'scenes') else []
                if i < len(creative_scenes):
                    prompt = creative_scenes[i].ai_generation_prompt or prompt

                if prompt:
                    output_file = assets_dir / f"{scene_id}_ai.mp4"
                    try:
                        result = self.visual_gen.execute({
                            "operation": "text_to_video",
                            "prompt": prompt,
                            "negative_prompt": "blurry, low quality, distorted, ugly, watermark, text, logo, watermark",
                            "width": 1920 if self.aspect_ratio == "16:9" else 1080,
                            "height": 1080 if self.aspect_ratio == "16:9" else 1920,
                            "num_frames": int(scene.get("duration_seconds", 5) * 24),
                            "fps": 24,
                            "num_inference_steps": 20,
                            "guidance_scale": 7.5,
                            "seed": -1,
                            "model": "auto",
                            "output_path": str(output_file),
                        })
                        if result.success and output_file.exists():
                            video_path = output_file
                        else:
                            self.warnings.append(f"AI video generation failed for {scene_id}: {result.error}")
                            generation_method = "ken_burns_fallback"
                    except Exception as e:
                        self.warnings.append(f"AI video generation error for {scene_id}: {e}")
                        generation_method = "ken_burns_fallback"

            # Fallback: Ken Burns on generated image
            if not video_path:
                # Generate base image first
                prompt = scene.get("visual_concept", "")
                creative_scenes = direction.scenes if hasattr(direction, 'scenes') else []
                if i < len(creative_scenes):
                    prompt = creative_scenes[i].ai_generation_prompt or prompt

                if prompt:
                    img_file = assets_dir / f"{scene_id}_base.png"
                    vid_file = assets_dir / f"{scene_id}_kb.mp4"
                    try:
                        img_result = self.visual_gen.execute({
                            "operation": "text_to_image",
                            "prompt": prompt,
                            "negative_prompt": "blurry, low quality, distorted, ugly, watermark, text, logo",
                            "width": 1920 if self.aspect_ratio == "16:9" else 1080,
                            "height": 1080 if self.aspect_ratio == "16:9" else 1920,
                            "num_inference_steps": 25,
                            "guidance_scale": 7.5,
                            "seed": -1,
                            "model": "auto",
                            "output_path": str(img_file),
                        })
                        if img_result.success and img_file.exists():
                            # Ken Burns animation
                            kb_result = self.visual_gen.execute({
                                "operation": "ken_burns",
                                "image_path": str(img_file),
                                "output_path": str(vid_file),
                                "duration_seconds": scene.get("duration_seconds", 5),
                                "width": 1920 if self.aspect_ratio == "16:9" else 1080,
                                "height": 1080 if self.aspect_ratio == "16:9" else 1920,
                            })
                            if kb_result.success and vid_file.exists():
                                video_path = vid_file
                                generation_method = "ken_burns"
                    except Exception as e:
                        self.warnings.append(f"Ken Burns fallback failed for {scene_id}: {e}")

            if video_path and video_path.exists():
                media = _probe(video_path)
                asset_id = f"video_{len(assets_list)+1:03d}"
                rel_path = str(video_path.relative_to(self.project_dir)).replace("\\", "/")
                assets_list.append({
                    "id": asset_id,
                    "type": "video",
                    "path": rel_path,
                    "source_tool": f"local_visual_gen_{generation_method}",
                    "scene_id": scene_id,
                    "cost_usd": 0,
                    "duration_seconds": media.get("duration_seconds", scene.get("duration_seconds", 5)),
                    "resolution": media.get("resolution", "1920x1080"),
                    "format": media.get("format", "mp4"),
                    "provider": "local_ai",
                    "license": "local_generated",
                    "original_url": "",
                    "generation_method": generation_method,
                    "cinematic_metadata": cinematic_meta,
                })
                provenance.append({
                    "asset_id": asset_id,
                    "original_source_url": "local_ai_generation",
                    "direct_download_url": "local_ai_generation",
                    "creator": "OpenMontage Local AI",
                    "license": "local_generated",
                    "download_date": time.strftime("%Y-%m-%d"),
                    "sha256": _sha256(video_path),
                    "modified": False,
                    "attribution": f"Generated by OpenMontage local AI ({generation_method})",
                })

        # Write attribution file
        attribution = self.project_dir / "ATTRIBUTIONS.md"
        attribution.write_text("# Asset attributions\n\n" + "\n".join(
            f"- {r['attribution']}" for r in provenance
        ), encoding="utf-8")

        # Fallback: reuse existing Kodak project assets if no AI-generated assets
        if not assets_list and self.reuse_project_id:
            self._reuse_existing_assets(assets_list, provenance)

        return {
            "version": "1.0",
            "assets": assets_list,
            "total_cost_usd": 0,
            "metadata": {
                "agent": "VisualGenerationAgent + NarrationAgent",
                "provenance": provenance,
                "attribution_document": "ATTRIBUTIONS.md",
                "unfilled_scenes": [],
                "music": "Will be generated or sourced locally",
                "model_registry": "artifacts/model_registry.json",
            }
        }

    def _reuse_existing_assets(self, assets_list: list[dict], provenance: list[dict]) -> None:
        """Reuse verified assets from an existing Kodak project when AI generation is unavailable."""
        assert self.project_dir is not None
        import shutil
        import hashlib

        source = PROJECTS_DIR / _slug(self.reuse_project_id)
        manifest_path = source / "artifacts" / "asset_manifest.json"
        if not manifest_path.is_file():
            self.warnings.append(f"Reuse project {self.reuse_project_id!r} has no asset manifest.")
            return

        try:
            original = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            self.warnings.append(f"Reuse project {self.reuse_project_id!r} has unreadable asset manifest.")
            return

        scenes_needed = len(scene_plan.get("scenes", [])) if hasattr(self, '_scene_plan') else 4
        video_assets = [a for a in original.get("assets", []) if a.get("type") == "video"]

        for i, record in enumerate(video_assets[:scenes_needed]):
            origin_path = source / str(record.get("path", ""))
            if not origin_path.is_file():
                continue

            dest_dir = self.project_dir / "assets" / "video" / "reused"
            dest_dir.mkdir(parents=True, exist_ok=True)
            dest_path = dest_dir / origin_path.name
            shutil.copy2(origin_path, dest_path)

            media = _probe(dest_path)
            if media.get("duration_seconds", 0) <= 0:
                continue

            asset_id = f"reused_video_{len(assets_list)+1:03d}"
            rel_path = str(dest_path.relative_to(self.project_dir)).replace("\\", "/")
            assets_list.append({
                "id": asset_id,
                "type": "video",
                "path": rel_path,
                "source_tool": "project_asset_cache",
                "scene_id": f"scene_{i+1:02d}",
                "cost_usd": 0,
                "duration_seconds": media["duration_seconds"],
                "resolution": media["resolution"],
                "format": media["format"],
                "provider": record.get("provider", "Wikimedia Commons"),
                "license": record.get("license"),
                "original_url": record.get("source_url") or record.get("original_url", ""),
                "generation_method": "reused_from_existing_project",
                "cinematic_metadata": {},
            })
            provenance.append({
                "asset_id": asset_id,
                "original_source_url": record.get("source_url") or record.get("original_url", ""),
                "direct_download_url": record.get("download_url", "not recorded"),
                "creator": record.get("creator", "unknown"),
                "license": record.get("license"),
                "download_date": record.get("download_date") or time.strftime("%Y-%m-%d"),
                "sha256": hashlib.sha256(dest_path.read_bytes()).hexdigest(),
                "modified": False,
                "attribution": f"Reused from {self.reuse_project_id}: {record.get('creator', 'Unknown')}, {record.get('license', 'unknown')}",
            })

    def _generate_narration(self, script: Any) -> dict[str, Any] | None:
        """Generate narration with enhanced prosody."""
        assert self.project_dir is not None

        audio_dir = self.project_dir / "assets" / "audio"
        audio_dir.mkdir(parents=True, exist_ok=True)
        output_path = audio_dir / "narration.wav"

        # Build prosody segments from script
        segments = []
        for section in script.sections:
            cues = section.delivery_cues
            segments.append({
                "text": section.text,
                "pace": cues.get("pace", "measured"),
                "energy": cues.get("energy", "medium"),
                "emphasis_words": cues.get("emphasis_words", []),
                "pause_before": cues.get("pause_before_seconds", 0.3),
                "pause_after": cues.get("pause_after_seconds", 0.5),
            })

        result = self.tts.execute({
            "segments": segments,
            "model": "en_US-lessac-medium",
            "speaker_id": 0,
            "global_length_scale": 1.0,
            "output_path": str(output_path),
            "add_silence_padding": 1.0,
        })

        if result.success and output_path.exists():
            media = _probe(output_path)
            return {
                "id": "narration_001",
                "type": "narration",
                "path": str(output_path.relative_to(self.project_dir)).replace("\\", "/"),
                "source_tool": "enhanced_piper_tts",
                "scene_id": "narration",
                "cost_usd": 0,
                "duration_seconds": media.get("duration_seconds", 0),
                "format": media.get("format", "wav"),
                "generation_summary": "Enhanced Piper TTS with prosody control",
                "voice_model": "en_US-lessac-medium",
            }

        self.warnings.append(f"Enhanced TTS failed: {result.error}")

        # Fallback: reuse narration from existing project
        if self.reuse_project_id:
            reused = self._reuse_existing_narration()
            if reused:
                return reused

        return None

    def _reuse_existing_narration(self) -> dict[str, Any] | None:
        """Reuse narration from existing Kodak project when TTS unavailable."""
        import shutil
        import hashlib

        source = PROJECTS_DIR / _slug(self.reuse_project_id)
        manifest_path = source / "artifacts" / "asset_manifest.json"
        if not manifest_path.is_file():
            return None

        try:
            original = json.loads(manifest_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            return None

        # Find narration asset
        for record in original.get("assets", []):
            if record.get("type") == "narration":
                origin_path = source / str(record.get("path", ""))
                if not origin_path.is_file():
                    continue

                dest_dir = self.project_dir / "assets" / "audio"
                dest_dir.mkdir(parents=True, exist_ok=True)
                dest_path = dest_dir / "narration_reused.wav"
                shutil.copy2(origin_path, dest_path)

                media = _probe(dest_path)
                if media.get("duration_seconds", 0) <= 0:
                    continue

                return {
                    "id": "narration_001",
                    "type": "narration",
                    "path": str(dest_path.relative_to(self.project_dir)).replace("\\", "/"),
                    "source_tool": "project_asset_cache",
                    "scene_id": "narration",
                    "cost_usd": 0,
                    "duration_seconds": media["duration_seconds"],
                    "format": media["format"],
                    "generation_summary": f"Reused narration from {self.reuse_project_id}",
                    "voice_model": "reused",
                }

        return None

    def _generate_subtitles(self, script: Any, direction: Any) -> Path:
        """Generate modern subtitles from script."""
        assert self.project_dir is not None
        subtitle_path = self.project_dir / "assets" / "subtitles.srt"

        # Determine subtitle style from creative direction
        style_name = direction.subtitle_style if hasattr(direction, 'subtitle_style') else "cinematic"

        generate_subtitles_from_script(
            script_path=self.project_dir / "artifacts" / "script.json",
            output_path=subtitle_path,
            style=style_name,
        )

        return subtitle_path

    def _create_edit_decisions(
        self,
        direction: Any,
        assets: dict[str, Any],
        scene_plan: dict[str, Any],
        script: Any,
        subtitle_path: Path,
    ) -> dict[str, Any]:
        """Create edit decisions with cinematic transitions."""
        video_assets = [a for a in assets["assets"] if a["type"] == "video"]

        cuts = []
        for i, scene in enumerate(scene_plan.get("scenes", [])):
            asset = video_assets[i] if i < len(video_assets) else video_assets[-1] if video_assets else None

            if not asset:
                continue

            start = scene.get("start_seconds", 0)
            end = scene.get("end_seconds", 0)
            duration = end - start

            cinematic_meta = scene.get("cinematic_metadata", {})

            cuts.append({
                "id": f"cut_{scene['id']}",
                "source": str((self.project_dir / asset["path"]).resolve()),
                "in_seconds": 0,
                "out_seconds": duration,
                "transition_in": scene.get("transition_in", "fade"),
                "transition_out": scene.get("transition_out", "dissolve"),
                "transition_duration": 0.5,
                "speed": 1.0,
                "color_grade": cinematic_meta.get("color_grade"),
                "film_grain": cinematic_meta.get("film_grain", False),
                "vignette": cinematic_meta.get("vignette"),
                "dynamic_zoom": cinematic_meta.get("dynamic_zoom"),
                "target_aspect": cinematic_meta.get("target_aspect", self.aspect_ratio),
                "reason": scene.get("shot_intent", "Cinematic visual generated by AI"),
            })

        # Audio configuration
        narration = next((a for a in assets["assets"] if a["type"] == "narration"), None)

        return {
            "version": "1.0",
            "cuts": cuts,
            "render_runtime": "ffmpeg",
            "renderer_family": "viral-cinematic",
            "audio": {
                "narration": {
                    "segments": [{"asset_id": "narration_001", "start_seconds": 0}] if narration else []
                },
                "music": {"volume": 0.15},  # Subtle background music
            },
            "subtitles": {
                "enabled": True,
                "style": direction.subtitle_style if hasattr(direction, 'subtitle_style') else "cinematic",
                "source": str(subtitle_path),
                "position": "bottom-center",
                "max_words_per_line": 12,
            },
            "metadata": {
                "agent": "ViralCinematicEditor",
                "visual_style": self.visual_style,
                "aspect_ratio": self.aspect_ratio,
            }
        }

    def _compose(self, edit: dict[str, Any], assets: dict[str, Any], subtitle_path: Path) -> dict[str, Any]:
        """Render final video using video_compose."""
        assert self.project_dir is not None

        output = self.project_dir / "renders" / "final.mp4"
        narration = next((a for a in assets["assets"] if a["type"] == "narration"), None)

        registry.discover()
        composer = registry.get("video_compose")

        result = composer.execute({
            "operation": "compose",
            "edit_decisions": edit,
            "output_path": str(output),
            "audio_path": str(self.project_dir / narration["path"]) if narration else None,
            "subtitle_path": str(subtitle_path),
            "codec": "libx264",
            "crf": 20,  # Higher quality for cinematic
            "preset": "slow",
        }) if composer else None

        if not result or not result.success or not output.is_file():
            self.warnings.append(f"FFmpeg composition failed: {getattr(result, 'error', 'video_compose unavailable')}")
            return {"version": "1.0", "outputs": [], "render_time_seconds": 0, "warnings": self.warnings, "status": "failed"}

        media = _probe(output)
        return {
            "version": "1.0",
            "outputs": [{
                "path": "renders/final.mp4",
                "format": "mp4",
                "codec": media["video_codec"],
                "audio_codec": media["audio_codec"],
                "resolution": media["resolution"],
                "fps": media["fps"],
                "duration_seconds": media["duration_seconds"],
                "file_size_bytes": output.stat().st_size,
                "platform_target": "youtube" if self.aspect_ratio == "16:9" else "shorts",
            }],
            "render_time_seconds": result.duration_seconds or 0,
            "warnings": self.warnings,
            "verification_notes": ["FFprobe completed after export."],
            "render_grammar": "viral-cinematic",
            "metadata": {"agent": "QualityControlAgent + ExportAgent", "ffprobe": media, "status": "rendered"},
        }

    def _quality_control(
        self,
        render_report: dict[str, Any],
        creative_direction: Any,
        script: Any,
        assets: dict[str, Any],
    ) -> Any:
        """Run comprehensive QC on rendered video."""
        assert self.project_dir is not None

        output = self.project_dir / "renders" / "final.mp4"
        if not output.exists():
            # Return a proper QCReport dataclass for failed renders
            from lib.quality_control import QCReport, QCResult
            return QCReport(
                video_path=str(output),
                overall_passed=False,
                overall_score=0.0,
                technical_score=0.0,
                creative_score=0.0,
                results=[
                    QCResult("render_output", "technical", False, 0.0,
                             "No output file produced", "critical"),
                ],
                generated_at=time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
                metadata={"error": "No output file", "render_report": render_report},
            )

        qc_report = self.qc_agent.validate(
            output,
            creative_direction=asdict(creative_direction) if is_dataclass(creative_direction) else creative_direction,
            script=asdict(script) if is_dataclass(script) else script,
            asset_manifest=assets,
        )
        self.qc_agent.save(qc_report, self.project_dir)
        self.qc_agent.print_summary(qc_report)

        return qc_report

    def _generate_visuals_with_retry(self, direction: Any, scene_plan: dict[str, Any]) -> dict[str, Any]:
        """Generate visuals with retry logic for failed generations."""
        last_assets = None
        for attempt in range(self.max_retries + 1):
            if attempt > 0:
                self.warnings.append(f"Visual generation retry attempt {attempt}/{self.max_retries}")
                emit_event(self.project_dir, {"event": "retry", "stage": "visual_generation", "attempt": attempt})
            assets = self._generate_visuals(direction, scene_plan)
            if assets.get("assets"):
                return assets
            last_assets = assets
        # If all retries failed, return what we have (may be empty)
        self.warnings.append(f"Visual generation failed after {self.max_retries} retries")
        return last_assets or {"version": "1.0", "assets": [], "total_cost_usd": 0, "metadata": {}}

    def _quality_control_with_retry(
        self,
        render_report: dict[str, Any],
        creative_direction: Any,
        script: Any,
        assets: dict[str, Any],
    ) -> Any:
        """Run QC with auto-retry on critical failures (max 2 retries)."""
        for attempt in range(self.max_retries + 1):
            if attempt > 0:
                self.warnings.append(f"QC retry attempt {attempt}/{self.max_retries} - re-rendering")
                emit_event(self.project_dir, {"event": "retry", "stage": "quality_control", "attempt": attempt})
                # Re-render
                edit_decisions_path = self.project_dir / "artifacts" / "edit_decisions.json"
                if edit_decisions_path.exists():
                    import json
                    with open(edit_decisions_path) as f:
                        edit_decisions = json.load(f)
                    subtitle_path = self.project_dir / "assets" / "subtitles.srt"
                    render_report = self._compose(edit_decisions, assets, subtitle_path)

            qc_report = self._quality_control(render_report, creative_direction, script, assets)

            # Check if critical failures exist
            critical_failures = [r for r in qc_report.results if r.severity == "critical" and not r.passed]
            if not critical_failures:
                return qc_report

            self.warnings.append(f"QC failed with {len(critical_failures)} critical failures: " +
                               ", ".join(r.check_name for r in critical_failures))

        self.warnings.append(f"QC failed after {self.max_retries} retries. Last report returned.")
        return qc_report


def main() -> int:
    parser = argparse.ArgumentParser(description="Run viral cinematic production pipeline.")
    parser.add_argument("title")
    parser.add_argument("idea")
    parser.add_argument("--language", default="en")
    parser.add_argument("--duration", type=float, default=45)
    parser.add_argument("--aspect", default="16:9", choices=["16:9", "9:16"])
    parser.add_argument("--style", default="cinematic")
    parser.add_argument("--reuse-project", help="Reuse assets from existing project")
    args = parser.parse_args()

    print(json.dumps(
        ViralCinematicRunner(
            args.title, args.idea,
            language=args.language,
            duration_seconds=args.duration,
            aspect_ratio=args.aspect,
            visual_style=args.style,
            reuse_project_id=args.reuse_project,
        ).run(),
        indent=2, ensure_ascii=False
    ))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())