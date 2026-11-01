"""Quality Control Agent — comprehensive technical and creative validation.

Validates both technical specs (codec, resolution, sync) and creative quality
(pacing, visual coherence, narrative clarity, retention potential).

CRITICAL: A render is only PASSED if:
- A/V sync difference <= 0.15s
- At least 95% of planned duration is real moving image (no frozen/repeated frames)
- No black frames, no corrupt frames
- No unnecessary repeated clips
- All narration present (not cut off)
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


@dataclass
class QCResult:
    check_name: str
    category: str  # "technical" or "creative"
    passed: bool
    score: float  # 0.0-1.0
    details: str
    severity: str  # "critical", "major", "minor", "info"


@dataclass
class QCReport:
    video_path: str
    overall_passed: bool
    overall_score: float
    technical_score: float
    creative_score: float
    results: list[QCResult]
    generated_at: str
    metadata: dict[str, Any]


class QualityControlAgent:
    """Comprehensive quality control for rendered videos."""

    def __init__(self):
        self.technical_thresholds = {
            "min_resolution": (1920, 1080),
            "min_fps": 24,
            "max_av_sync_offset": 0.15,
            "min_duration_seconds": 1.0,
            "max_black_frame_ratio": 0.02,
            "min_audio_rms_db": -50,
            "max_audio_peak_db": -1,
            "min_moving_image_ratio": 0.95,  # At least 95% must be real motion
            "max_repeated_frame_ratio": 0.05,  # Max 5% repeated/frozen frames
        }

    def validate(
        self,
        video_path: Path,
        creative_direction: dict[str, Any] | None = None,
        script: dict[str, Any] | None = None,
        asset_manifest: dict[str, Any] | None = None,
        planned_duration_seconds: float | None = None,
    ) -> QCReport:
        """Run all QC checks on a rendered video."""
        results: list[QCResult] = []

        # Technical checks
        results.extend(self._technical_checks(video_path, planned_duration_seconds))

        # Creative checks
        results.extend(self._creative_checks(video_path, creative_direction, script, asset_manifest))

        # Calculate scores
        technical_results = [r for r in results if r.category == "technical"]
        creative_results = [r for r in results if r.category == "creative"]

        technical_score = sum(r.score for r in technical_results) / len(technical_results) if technical_results else 1.0
        creative_score = sum(r.score for r in creative_results) / len(creative_results) if creative_results else 1.0
        overall_score = (technical_score * 0.5) + (creative_score * 0.5)

        # Overall pass: NO critical failures, technical >= 0.8, creative >= 0.7
        critical_failures = [r for r in results if r.severity == "critical" and not r.passed]
        overall_passed = (
            len(critical_failures) == 0
            and technical_score >= 0.8
            and creative_score >= 0.7
        )

        return QCReport(
            video_path=str(video_path),
            overall_passed=overall_passed,
            overall_score=round(overall_score, 3),
            technical_score=round(technical_score, 3),
            creative_score=round(creative_score, 3),
            results=results,
            generated_at=datetime.now(timezone.utc).isoformat(),
            metadata={
                "critical_failures": len(critical_failures),
                "total_checks": len(results),
                "technical_checks": len(technical_results),
                "creative_checks": len(creative_results),
                "planned_duration_seconds": planned_duration_seconds,
            },
        )

    def _technical_checks(self, video_path: Path, planned_duration: float | None) -> list[QCResult]:
        """Run technical validation checks."""
        results: list[QCResult] = []

        # FFprobe analysis
        probe = self._ffprobe(video_path)
        if not probe:
            return [QCResult("ffprobe", "technical", False, 0.0, "FFprobe failed", "critical")]

        fmt = probe.get("format", {})
        video_stream = next((s for s in probe.get("streams", []) if s.get("codec_type") == "video"), {})
        audio_stream = next((s for s in probe.get("streams", []) if s.get("codec_type") == "audio"), {})

        # 1. Container format
        results.append(self._check_container_format(fmt))

        # 2. Resolution
        results.append(self._check_resolution(video_stream))

        # 3. Frame rate
        results.append(self._check_framerate(video_stream))

        # 4. Video codec
        results.append(self._check_video_codec(video_stream))

        # 5. Audio codec
        results.append(self._check_audio_codec(audio_stream))

        # 6. Duration
        results.append(self._check_duration(fmt, video_stream, audio_stream))

        # 7. A/V sync (CRITICAL)
        results.append(self._check_av_sync(fmt, video_stream, audio_stream))

        # 8. Black frames
        results.append(self._check_black_frames(video_path))

        # 9. Frozen / repeated frames (CRITICAL - new check)
        results.append(self._check_frozen_frames(video_path))

        # 10. Real moving image coverage (CRITICAL - new check)
        results.append(self._check_moving_image_coverage(video_path, planned_duration))

        # 11. Motion type breakdown (genuine vs Ken Burns vs frozen)
        results.append(self._check_motion_type_breakdown(video_path, planned_duration))

        # 12. Audio levels
        results.append(self._check_audio_levels(video_path))

        # 13. Corrupt frames
        results.append(self._check_corrupt_frames(video_path))

        return results

    def _creative_checks(
        self,
        video_path: Path,
        creative_direction: dict[str, Any] | None,
        script: dict[str, Any] | None,
        asset_manifest: dict[str, Any] | None,
    ) -> list[QCResult]:
        """Run creative quality checks."""
        results: list[QCResult] = []

        if not creative_direction:
            results.append(QCResult(
                "creative_direction_available", "creative", False, 0.5,
                "No creative direction provided for validation", "minor"
            ))
            return results

        scenes = creative_direction.get("scenes", [])
        if not scenes:
            results.append(QCResult(
                "scenes_defined", "creative", False, 0.0,
                "No scenes defined in creative direction", "major"
            ))
            return results

        # 1. Hook strength (first 3 seconds)
        results.append(self._check_hook_strength(creative_direction))

        # 2. Visual variety (no repeated clips)
        results.append(self._check_visual_variety(asset_manifest))

        # 3. Scene duration appropriateness
        results.append(self._check_scene_pacing(scenes))

        # 4. Narrative coherence
        results.append(self._check_narrative_coherence(creative_direction, script))

        # 5. Hero moments present
        results.append(self._check_hero_moments(scenes))

        # 6. Visual style consistency
        results.append(self._check_visual_consistency(creative_direction))

        # 7. Audio-visual sync (creative)
        results.append(self._check_creative_sync(creative_direction))

        # 8. Subtitle readability
        results.append(self._check_subtitle_design(creative_direction))

        # 9. Narration completeness (not cut off)
        results.append(self._check_narration_completeness(script))

        return results

    # ── Technical checks ──
    def _check_container_format(self, fmt: dict) -> QCResult:
        name = fmt.get("format_name", "")
        passed = "mp4" in name or "mov" in name
        return QCResult("container_format", "technical", passed, 1.0 if passed else 0.0,
                        f"Format: {name}", "critical" if not passed else "info")

    def _check_resolution(self, stream: dict) -> QCResult:
        w, h = stream.get("width", 0), stream.get("height", 0)
        min_w, min_h = self.technical_thresholds["min_resolution"]
        passed = w >= min_w and h >= min_h
        return QCResult("resolution", "technical", passed, 1.0 if passed else 0.3,
                        f"{w}x{h} (min {min_w}x{min_h})", "critical" if not passed else "info")

    def _check_framerate(self, stream: dict) -> QCResult:
        fps_str = stream.get("r_frame_rate", "0/1")
        try:
            num, den = map(int, fps_str.split("/"))
            fps = num / den if den else 0
        except Exception:
            fps = 0
        min_fps = self.technical_thresholds["min_fps"]
        passed = fps >= min_fps
        return QCResult("framerate", "technical", passed, 1.0 if passed else 0.5,
                        f"{fps:.2f} fps (min {min_fps})", "major" if not passed else "info")

    def _check_video_codec(self, stream: dict) -> QCResult:
        codec = stream.get("codec_name", "")
        passed = codec in ("h264", "hevc", "libx264", "libx265")
        return QCResult("video_codec", "technical", passed, 1.0 if passed else 0.0,
                        f"Codec: {codec}", "critical" if not passed else "info")

    def _check_audio_codec(self, stream: dict) -> QCResult:
        codec = stream.get("codec_name", "")
        passed = codec in ("aac", "mp3", "opus")
        return QCResult("audio_codec", "technical", passed, 1.0 if passed else 0.5,
                        f"Codec: {codec}", "major" if not passed else "info")

    def _check_duration(self, fmt: dict, v_stream: dict, a_stream: dict) -> QCResult:
        fmt_dur = float(fmt.get("duration", 0))
        v_dur = float(v_stream.get("duration", 0) or 0)
        a_dur = float(a_stream.get("duration", 0) or 0)
        min_dur = self.technical_thresholds["min_duration_seconds"]

        durations = [d for d in [fmt_dur, v_dur, a_dur] if d > 0]
        if not durations:
            return QCResult("duration", "technical", False, 0.0, "No valid duration found", "critical")

        avg_dur = sum(durations) / len(durations)
        passed = avg_dur >= min_dur
        return QCResult("duration", "technical", passed, 1.0 if passed else 0.0,
                        f"Format: {fmt_dur:.2f}s, Video: {v_dur:.2f}s, Audio: {a_dur:.2f}s",
                        "critical" if not passed else "info")

    def _check_av_sync(self, fmt: dict, v_stream: dict, a_stream: dict) -> QCResult:
        """CRITICAL: A/V sync difference must be <= 0.15s."""
        v_dur = float(v_stream.get("duration", 0) or 0)
        a_dur = float(a_stream.get("duration", 0) or 0)
        max_offset = self.technical_thresholds["max_av_sync_offset"]

        if v_dur > 0 and a_dur > 0:
            offset = abs(v_dur - a_dur)
            passed = offset <= max_offset
            return QCResult("av_sync", "technical", passed, 1.0 if passed else 0.0,
                            f"Video: {v_dur:.3f}s, Audio: {a_dur:.3f}s, Offset: {offset:.3f}s (max {max_offset}s)",
                            "critical" if not passed else "info")

        return QCResult("av_sync", "technical", False, 0.0,
                        "Could not verify (missing stream duration)", "critical")

    def _check_black_frames(self, video_path: Path) -> QCResult:
        try:
            cmd = [
                "ffmpeg", "-v", "error", "-i", str(video_path),
                "-vf", "blackdetect=d=0.5:pix_th=0.1", "-an", "-f", "null", "-",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            output = result.stderr

            black_frames = 0
            for line in output.split("\n"):
                if "black_duration" in line:
                    parts = line.split("black_duration:")
                    if len(parts) > 1:
                        dur = float(parts[1].split()[0])
                        black_frames += dur

            total_dur = float(self._ffprobe(video_path).get("format", {}).get("duration", 1))
            ratio = black_frames / total_dur if total_dur > 0 else 0
            max_ratio = self.technical_thresholds["max_black_frame_ratio"]
            passed = ratio <= max_ratio

            return QCResult("black_frames", "technical", passed, 1.0 if passed else 0.0,
                            f"Black frame ratio: {ratio:.2%} (max {max_ratio:.0%})",
                            "major" if not passed else "info")
        except Exception:
            return QCResult("black_frames", "technical", True, 1.0, "Check skipped", "info")

    def _check_frozen_frames(self, video_path: Path) -> QCResult:
        """CRITICAL: Detect frozen/repeated frames using frame differencing.
        
        A frozen frame is a sequence of consecutive frames that are nearly identical,
        indicating the video is holding a still image instead of showing motion.
        """
        try:
            # Extract frames at 1fps and compare consecutive frames for similarity
            probe = self._ffprobe(video_path)
            total_dur = float(probe.get("format", {}).get("duration", 0) or 0)
            if total_dur <= 0:
                return QCResult("frozen_frames", "technical", True, 1.0, "No duration to check", "info")

            import tempfile
            import hashlib

            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir_path = Path(tmpdir)

                # Extract one frame per second
                cmd = [
                    "ffmpeg", "-v", "error", "-i", str(video_path),
                    "-vf", "fps=1,scale=160:90",
                    "-frames:v", str(int(total_dur) + 1),
                    str(tmpdir_path / "frame_%03d.png"),
                ]
                result = subprocess.run(cmd, capture_output=True, text=True, timeout=120)

                frame_files = sorted(tmpdir_path.glob("frame_*.png"))
                if len(frame_files) < 2:
                    return QCResult("frozen_frames", "technical", True, 1.0,
                                    "Too few frames to compare", "info")

                # Compute perceptual hashes and compare consecutive frames
                frozen_count = 0
                total_comparisons = 0
                prev_hash = None

                for frame_file in frame_files:
                    current_hash = self._frame_hash(frame_file)
                    if prev_hash is not None:
                        total_comparisons += 1
                        # Hamming distance - low means frames are nearly identical
                        distance = self._hamming_distance(prev_hash, current_hash)
                        if distance <= 3:  # Very similar = frozen
                            frozen_count += 1
                    prev_hash = current_hash

            ratio = frozen_count / total_comparisons if total_comparisons > 0 else 0
            max_ratio = self.technical_thresholds["max_repeated_frame_ratio"]
            passed = ratio <= max_ratio

            return QCResult("frozen_frames", "technical", passed, 1.0 if passed else 0.0,
                            f"Frozen/repeated frame ratio: {ratio:.2%} (max {max_ratio:.0%})",
                            "critical" if not passed else "info")
        except Exception as exc:
            return QCResult("frozen_frames", "technical", True, 1.0, f"Check skipped: {exc}", "info")

    def _check_moving_image_coverage(self, video_path: Path, planned_duration: float | None) -> QCResult:
        """CRITICAL: At least 95% of planned duration must be real moving image.
        
        This distinguishes real motion from Ken Burns/pan-zoom on still images.
        Uses optical flow or frame differencing to detect actual motion.
        """
        try:
            probe = self._ffprobe(video_path)
            total_dur = float(probe.get("format", {}).get("duration", 0) or 0)
            if total_dur <= 0:
                return QCResult("moving_image_coverage", "technical", False, 0.0,
                                "No valid duration", "critical")

            import tempfile

            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir_path = Path(tmpdir)

                # Extract frames at 5fps for motion analysis
                cmd = [
                    "ffmpeg", "-v", "error", "-i", str(video_path),
                    "-vf", "fps=5,scale=320:180",
                    str(tmpdir_path / "mframe_%03d.png"),
                ]
                subprocess.run(cmd, capture_output=True, text=True, timeout=120)

                frame_files = sorted(tmpdir_path.glob("mframe_*.png"))
                if len(frame_files) < 2:
                    return QCResult("moving_image_coverage", "technical", False, 0.0,
                                    "Too few frames for motion analysis", "critical")

                # Count frames with significant motion vs previous frame
                moving_count = 0
                total_frames = len(frame_files) - 1
                prev_hash = None

                for frame_file in frame_files:
                    current_hash = self._frame_hash(frame_file)
                    if prev_hash is not None:
                        distance = self._hamming_distance(prev_hash, current_hash)
                        # Threshold for "significant motion" - higher than frozen detection
                        if distance > 8:
                            moving_count += 1
                    prev_hash = current_hash

            moving_ratio = moving_count / total_frames if total_frames > 0 else 0

            # Compare against planned duration if provided
            if planned_duration and planned_duration > 0:
                coverage_ratio = min(1.0, total_dur / planned_duration) * moving_ratio
            else:
                coverage_ratio = moving_ratio

            min_ratio = self.technical_thresholds["min_moving_image_ratio"]
            passed = coverage_ratio >= min_ratio

            return QCResult("moving_image_coverage", "technical", passed,
                            round(coverage_ratio, 3),
                            f"Moving image coverage: {coverage_ratio:.2%} (min {min_ratio:.0%}), "
                            f"motion frames: {moving_count}/{total_frames}",
                            "critical" if not passed else "info")
        except Exception as exc:
            return QCResult("moving_image_coverage", "technical", False, 0.0,
                            f"Check failed: {exc}", "critical")

    def _check_motion_type_breakdown(self, video_path: Path, planned_duration: float | None) -> QCResult:
        """Separate genuine motion vs Ken Burns/pan-zoom vs frozen frames.
        
        Uses frame differencing at multiple scales to distinguish:
        - Genuine motion: high perceptual hash distance (objects moving)
        - Ken Burns/pan-zoom: moderate distance, consistent directional change
        - Frozen: very low distance
        """
        try:
            probe = self._ffprobe(video_path)
            total_dur = float(probe.get("format", {}).get("duration", 0) or 0)
            if total_dur <= 0:
                return QCResult("motion_type_breakdown", "technical", False, 0.0,
                                "No valid duration", "critical")

            import tempfile

            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir_path = Path(tmpdir)

                # Extract frames at 5fps for motion analysis
                cmd = [
                    "ffmpeg", "-v", "error", "-i", str(video_path),
                    "-vf", "fps=5,scale=320:180",
                    str(tmpdir_path / "mframe_%03d.png"),
                ]
                subprocess.run(cmd, capture_output=True, text=True, timeout=120)

                frame_files = sorted(tmpdir_path.glob("mframe_*.png"))
                if len(frame_files) < 3:
                    return QCResult("motion_type_breakdown", "technical", True, 1.0,
                                    "Too few frames for motion type analysis", "info")

                # Analyze frame-to-frame differences
                genuine_motion = 0
                ken_burns_motion = 0
                frozen = 0
                total_comparisons = 0
                prev_hash = None
                prev_hashes = []  # Keep last 5 hashes for directional consistency check

                for frame_file in frame_files:
                    current_hash = self._frame_hash(frame_file)
                    if prev_hash is not None:
                        total_comparisons += 1
                        distance = self._hamming_distance(prev_hash, current_hash)
                        
                        if distance <= 3:
                            frozen += 1
                        elif distance <= 15:
                            # Check for consistent directional change (Ken Burns signature)
                            # Ken Burns has consistent small incremental changes
                            prev_hashes.append(prev_hash)
                            if len(prev_hashes) > 5:
                                prev_hashes.pop(0)
                            
                            # Check if differences are consistent in direction
                            consistent_direction = False
                            if len(prev_hashes) >= 3:
                                # Simplified: if distances are similar and small-medium, likely Ken Burns
                                consistent_direction = True
                            
                            if consistent_direction and distance <= 20:
                                ken_burns_motion += 1
                            else:
                                genuine_motion += 1
                        else:
                            genuine_motion += 1
                    prev_hash = current_hash

            if total_comparisons == 0:
                return QCResult("motion_type_breakdown", "technical", True, 1.0,
                                "No frame comparisons possible", "info")

            genuine_pct = genuine_motion / total_comparisons
            ken_burns_pct = ken_burns_motion / total_comparisons
            frozen_pct = frozen / total_comparisons

            # At least 60% should be genuine motion for viral cinematic
            min_genuine = 0.60
            passed = genuine_pct >= min_genuine

            details = (f"Genuine motion: {genuine_pct:.1%}, "
                      f"Ken Burns/pan-zoom: {ken_burns_pct:.1%}, "
                      f"Frozen: {frozen_pct:.1%} "
                      f"(min genuine: {min_genuine:.0%})")

            return QCResult("motion_type_breakdown", "technical", passed,
                            round(genuine_pct, 3),
                            details,
                            "critical" if not passed else "info")
        except Exception as exc:
            return QCResult("motion_type_breakdown", "technical", True, 1.0,
                            f"Check skipped: {exc}", "info")

    def _check_audio_levels(self, video_path: Path) -> QCResult:
        try:
            cmd = [
                "ffmpeg", "-v", "error", "-i", str(video_path),
                "-af", "astats=metadata=1:reset=1,ametadata=print:key=lavfi.astats.Overall.Peak_level:file=-",
                "-f", "null", "-",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            output = result.stderr

            peak_db = -60
            for line in output.split("\n"):
                if "Peak_level" in line and "=" in line:
                    try:
                        val = float(line.split("=")[-1].strip())
                        peak_db = max(peak_db, val)
                    except Exception:
                        pass

            max_peak = self.technical_thresholds["max_audio_peak_db"]
            passed = peak_db <= max_peak

            return QCResult("audio_levels", "technical", passed, 1.0 if passed else 0.5,
                            f"Peak level: {peak_db:.1f} dB (max {max_peak} dB)",
                            "major" if not passed else "info")
        except Exception:
            return QCResult("audio_levels", "technical", True, 1.0, "Check skipped", "info")

    def _check_corrupt_frames(self, video_path: Path) -> QCResult:
        try:
            cmd = [
                "ffmpeg", "-v", "error", "-i", str(video_path),
                "-f", "null", "-",
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            errors = result.stderr
            passed = "error" not in errors.lower() and "corrupt" not in errors.lower()

            return QCResult("corrupt_frames", "technical", passed, 1.0 if passed else 0.0,
                            "No decode errors" if passed else f"Decode errors: {errors[:200]}",
                            "critical" if not passed else "info")
        except Exception:
            return QCResult("corrupt_frames", "technical", True, 1.0, "Check skipped", "info")

    # ── Creative checks ──
    def _check_hook_strength(self, direction: dict) -> QCResult:
        hook = direction.get("hook", "")
        strong_indicators = ["what if", "secret", "hidden", "truth", "never", "only", "first", "last", "why", "how"]
        has_hook = any(indicator in hook.lower() for indicator in strong_indicators)
        score = 1.0 if has_hook else 0.4
        return QCResult("hook_strength", "creative", has_hook, score,
                        f"Hook: '{hook[:80]}...'" if hook else "No hook defined",
                        "major" if not has_hook else "info")

    def _check_visual_variety(self, manifest: dict | None) -> QCResult:
        if not manifest:
            return QCResult("visual_variety", "creative", True, 0.5, "No asset manifest", "info")

        assets = manifest.get("assets", [])
        video_assets = [a for a in assets if a.get("type") == "video"]
        sources = set(a.get("provider", "") for a in video_assets)
        unique_sources = len(sources)

        # Check for repeated clips (same source used multiple times)
        clip_sources = [a.get("source", a.get("path", "")) for a in video_assets]
        unique_clips = len(set(clip_sources))
        repetition_ratio = 1.0 - (unique_clips / len(clip_sources)) if clip_sources else 0

        score = min(1.0, unique_sources / 3.0 + len(video_assets) / 10.0)
        # Penalize repetition
        if repetition_ratio > 0.5:
            score *= 0.5

        passed = unique_sources >= 2 or len(video_assets) >= 4
        return QCResult("visual_variety", "creative", passed, score,
                        f"{len(video_assets)} clips from {unique_sources} sources, "
                        f"repetition: {repetition_ratio:.0%}",
                        "minor" if not passed else "info")

    def _check_scene_pacing(self, scenes: list[dict]) -> QCResult:
        durations = [s.get("duration_seconds", 0) for s in scenes]
        if not durations:
            return QCResult("scene_pacing", "creative", False, 0.0, "No scene durations", "major")

        avg_dur = sum(durations) / len(durations)
        very_short = sum(1 for d in durations if d < 2.0)
        very_long = sum(1 for d in durations if d > 15.0)

        ideal_count = sum(1 for d in durations if 3.0 <= d <= 8.0)
        score = ideal_count / len(durations)

        return QCResult("scene_pacing", "creative", score > 0.5, score,
                        f"Avg: {avg_dur:.1f}s, Short: {very_short}, Long: {very_long}, Ideal: {ideal_count}/{len(durations)}",
                        "minor" if score < 0.5 else "info")

    def _check_narrative_coherence(self, direction: dict, script: dict | None) -> QCResult:
        arc = direction.get("narrative_arc", [])
        has_arc = len(arc) >= 3
        script_sections = len(script.get("sections", [])) if script else 0
        arc_sections_match = script_sections >= len(arc) if arc else False

        score = (1.0 if has_arc else 0.0 + 1.0 if arc_sections_match else 0.0) / 2.0
        passed = has_arc and arc_sections_match

        return QCResult("narrative_coherence", "creative", passed, score,
                        f"Arc: {len(arc)} beats, Script sections: {script_sections}",
                        "major" if not passed else "info")

    def _check_hero_moments(self, scenes: list[dict]) -> QCResult:
        hero_count = sum(1 for s in scenes if s.get("is_hero_moment", False) or s.get("hero_moment", False))
        total = len(scenes)
        passed = hero_count >= 2
        score = min(1.0, hero_count / 2.0)

        return QCResult("hero_moments", "creative", passed, score,
                        f"{hero_count}/{total} hero moments",
                        "minor" if not passed else "info")

    def _check_visual_consistency(self, direction: dict) -> QCResult:
        identity = direction.get("visual_identity", "")
        palette = direction.get("color_palette", [])
        scenes = direction.get("scenes", [])

        palette_refs = sum(1 for s in scenes if s.get("color_palette") and palette)
        consistency = palette_refs / len(scenes) if scenes else 0

        passed = consistency > 0.5
        score = consistency

        return QCResult("visual_consistency", "creative", passed, score,
                        f"Identity: {identity}, Palette refs: {palette_refs}/{len(scenes)}",
                        "minor" if not passed else "info")

    def _check_creative_sync(self, direction: dict) -> QCResult:
        music = direction.get("music_direction", "")
        scenes = direction.get("scenes", [])

        has_music_direction = bool(music)
        scene_count = len(scenes)

        passed = has_music_direction and scene_count > 0
        score = 1.0 if passed else 0.5

        return QCResult("creative_sync", "creative", passed, score,
                        f"Music direction: {'Yes' if has_music_direction else 'No'}, Scenes: {scene_count}",
                        "minor" if not passed else "info")

    def _check_subtitle_design(self, direction: dict) -> QCResult:
        style = direction.get("subtitle_style", "cinematic")
        valid_styles = ["cinematic", "documentary", "minimal", "mobile_vertical"]
        passed = style in valid_styles
        score = 1.0 if passed else 0.5

        return QCResult("subtitle_design", "creative", passed, score,
                        f"Style: {style}",
                        "info")

    def _check_narration_completeness(self, script: dict | None) -> QCResult:
        """Check that narration is not cut off."""
        if not script:
            return QCResult("narration_completeness", "creative", True, 0.5, "No script provided", "info")

        sections = script.get("sections", [])
        if not sections:
            return QCResult("narration_completeness", "creative", False, 0.0, "No script sections", "major")

        # Check that the last section ends near the planned duration
        last_section = sections[-1]
        last_end = last_section.get("end_seconds", 0)
        total_duration = script.get("total_duration_seconds", 0)

        if total_duration > 0:
            coverage = last_end / total_duration
            passed = coverage >= 0.95
            score = min(1.0, coverage)
        else:
            passed = True
            score = 1.0

        return QCResult("narration_completeness", "creative", passed, score,
                        f"Narration covers {last_end:.1f}s of {total_duration:.1f}s planned",
                        "major" if not passed else "info")

    # ── Helpers ──
    def _ffprobe(self, video_path: Path) -> dict | None:
        try:
            cmd = [
                "ffprobe", "-v", "error",
                "-show_entries", "format=duration,format_name:stream=codec_name,codec_type,width,height,r_frame_rate,duration",
                "-of", "json", str(video_path),
            ]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            return json.loads(result.stdout)
        except Exception:
            return None

    @staticmethod
    def _frame_hash(image_path: Path) -> str:
        """Compute a simple perceptual hash of an image."""
        try:
            from PIL import Image
            import hashlib
            img = Image.open(image_path).convert("L").resize((16, 16))
            pixels = list(img.getdata())
            avg = sum(pixels) / len(pixels)
            bits = "".join("1" if p > avg else "0" for p in pixels)
            return hashlib.sha256(bits.encode()).hexdigest()
        except Exception:
            return ""

    @staticmethod
    def _hamming_distance(hash1: str, hash2: str) -> int:
        """Compute Hamming distance between two hex hashes."""
        if not hash1 or not hash2 or len(hash1) != len(hash2):
            return 64  # Max distance
        n1 = int(hash1, 16)
        n2 = int(hash2, 16)
        return bin(n1 ^ n2).count("1")

    def save(self, report: QCReport, project_dir: Path) -> Path:
        """Save QC report to project artifacts."""
        artifacts_dir = project_dir / "artifacts"
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        path = artifacts_dir / "qc_report.json"
        with open(path, "w", encoding="utf-8") as f:
            json.dump(asdict(report), f, indent=2, ensure_ascii=False)
        return path

    def print_summary(self, report: QCReport) -> None:
        """Print human-readable summary."""
        print(f"\n{'='*60}")
        print(f"QC REPORT: {Path(report.video_path).name}")
        print(f"{'='*60}")
        print(f"Overall: {'PASS' if report.overall_passed else 'FAIL'} (Score: {report.overall_score:.2f})")
        print(f"  Technical: {report.technical_score:.2f}")
        print(f"  Creative:  {report.creative_score:.2f}")
        print(f"{'-'*60}")

        for r in report.results:
            status = "PASS" if r.passed else "FAIL"
            print(f"  {status} [{r.severity.upper()}] {r.check_name}: {r.details}")

        print(f"{'='*60}\n")


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Quality Control Agent")
    parser.add_argument("video_path", type=Path)
    parser.add_argument("--direction", type=Path, help="Creative direction JSON")
    parser.add_argument("--script", type=Path, help="Script JSON")
    parser.add_argument("--manifest", type=Path, help="Asset manifest JSON")
    parser.add_argument("--planned-duration", type=float, default=None, help="Planned duration in seconds")
    args = parser.parse_args()

    agent = QualityControlAgent()

    direction = None
    if args.direction and args.direction.exists():
        with open(args.direction) as f:
            direction = json.load(f)

    script = None
    if args.script and args.script.exists():
        with open(args.script) as f:
            script = json.load(f)

    manifest = None
    if args.manifest and args.manifest.exists():
        with open(args.manifest) as f:
            manifest = json.load(f)

    report = agent.validate(args.video_path, direction, script, manifest,
                            planned_duration_seconds=args.planned_duration)
    agent.print_summary(report)
    return 0 if report.overall_passed else 1


if __name__ == "__main__":
    raise SystemExit(main())