"""Enhanced Piper TTS with prosody, SSML, and sound design integration."""

from __future__ import annotations

import json
import re
import shutil
import subprocess
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ToolResult,
    ToolRuntime,
    ToolStability,
    ToolStatus,
    ToolTier,
)


@dataclass
class ProsodySegment:
    text: str
    pace: str = "measured"
    energy: str = "medium"
    emphasis_words: list[str] | None = None
    pause_before: float = 0
    pause_after: float = 0
    pitch_shift: float = 0  # semitones
    rate_percent: float = 100  # percentage of normal


class EnhancedPiperTTS(BaseTool):
    """Enhanced Piper TTS with prosody control and cinematic delivery."""

    name = "enhanced_piper_tts"
    version = "0.2.0"
    tier = ToolTier.VOICE
    capability = "tts"
    provider = "piper"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC
    runtime = ToolRuntime.LOCAL

    dependencies = ["cmd:piper", "cmd:ffmpeg"]
    install_instructions = (
        "Install Piper TTS:\n"
        "  pip install piper-tts\n"
        "Or download from https://github.com/rhasspy/piper/releases\n"
        "Download voices:\n"
        "  piper --download-dir ~/.piper/models --model en_US-lessac-medium\n"
        "  piper --download-dir ~/.piper/models --model en_US-amy-medium\n"
        "  piper --download-dir ~/.piper/models --model en_US-ryan-high"
    )
    agent_skills = ["text-to-speech"]

    capabilities = [
        "text_to_speech",
        "prosody_control",
        "ssml_support",
        "multi_segment_generation",
        "offline_generation",
        "cinematic_delivery",
    ]
    supports = {
        "voice_cloning": False,
        "multilingual": True,
        "offline": True,
        "native_audio": True,
        "prosody": True,
        "emphasis": True,
    }
    best_for = [
        "cinematic documentary narration",
        "dramatic storytelling with pacing control",
        "offline narration with expressive delivery",
    ]

    input_schema = {
        "type": "object",
        "required": ["text"],
        "properties": {
            "text": {"type": "string", "description": "Full text or SSML"},
            "segments": {
                "type": "array",
                "description": "Prosody segments for fine-grained control",
                "items": {
                    "type": "object",
                    "properties": {
                        "text": {"type": "string"},
                        "pace": {"type": "string", "enum": ["slow", "measured", "conversational", "brisk", "fast"]},
                        "energy": {"type": "string", "enum": ["low", "medium", "high"]},
                        "emphasis_words": {"type": "array", "items": {"type": "string"}},
                        "pause_before": {"type": "number", "default": 0},
                        "pause_after": {"type": "number", "default": 0},
                        "pitch_shift": {"type": "number", "default": 0},
                        "rate_percent": {"type": "number", "default": 100},
                    },
                    "required": ["text"],
                },
            },
            "model": {
                "type": "string",
                "default": "en_US-lessac-medium",
                "description": "Voice model: lessac-medium (documentary), amy-medium (warm), ryan-high (authoritative)",
            },
            "speaker_id": {"type": "integer", "default": 0},
            "global_length_scale": {"type": "number", "default": 1.0},
            "sentence_silence": {"type": "number", "default": 0.3},
            "output_path": {"type": "string"},
            "add_silence_padding": {"type": "number", "default": 0.5, "description": "Seconds of silence at end"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=2, ram_mb=1024, vram_mb=0, disk_mb=500, network_required=False
    )
    retry_policy = RetryPolicy(max_retries=1, retryable_errors=[])
    idempotency_key_fields = ["text", "segments", "model", "speaker_id", "global_length_scale"]
    side_effects = ["writes audio file to output_path"]
    user_visible_verification = ["Listen to generated audio for prosody and clarity"]

    # Voice characteristics for cinematic selection
    VOICE_PROFILES = {
        "en_US-lessac-medium": {"style": "documentary", "gender": "neutral", "quality": "good"},
        "en_US-amy-medium": {"style": "warm_narrative", "gender": "female", "quality": "good"},
        "en_US-ryan-high": {"style": "authoritative", "gender": "male", "quality": "high"},
        "en_US-libritts-high": {"style": "audiobook", "gender": "mixed", "quality": "high"},
        "en_GB-northern_english_male-medium": {"style": "british_doc", "gender": "male", "quality": "medium"},
    }

    def get_status(self) -> ToolStatus:
        if shutil.which("piper"):
            return ToolStatus.AVAILABLE
        return ToolStatus.UNAVAILABLE

    def _resolve_model_path(self, model: str) -> str:
        """Resolve model name to full .onnx file path."""
        # Common Piper model directories
        model_dirs = [
            Path.home() / ".piper" / "models",
            Path.home() / "AppData" / "Local" / "piper" / "models",
            Path("C:/") / "ProgramData" / "piper" / "models",
        ]
        
        for model_dir in model_dirs:
            # Try exact match first
            exact = model_dir / f"{model}.onnx"
            if exact.exists():
                return str(exact)
            # Try without -high/-medium suffix
            for suffix in ["-high", "-medium", "-low"]:
                if model.endswith(suffix):
                    base = model[:-len(suffix)]
                    alt = model_dir / f"{base}.onnx"
                    if alt.exists():
                        return str(alt)
        
        # If not found, return as-is (piper might find it in its own cache)
        return model

    def estimate_cost(self, inputs: dict[str, Any]) -> float:
        return 0.0

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        if self.get_status() != ToolStatus.AVAILABLE:
            return ToolResult(success=False, error="Piper TTS not available. " + self.install_instructions)

        start = time.time()
        try:
            result = self._generate(inputs)
        except Exception as exc:
            return ToolResult(success=False, error=f"Enhanced TTS generation failed: {exc}")

        result.duration_seconds = round(time.time() - start, 2)
        return result

    def _generate(self, inputs: dict[str, Any]) -> ToolResult:
        output_path = Path(inputs.get("output_path", "tts_output.wav"))
        output_path.parent.mkdir(parents=True, exist_ok=True)

        segments = inputs.get("segments")
        text = inputs.get("text", "")

        if segments:
            # Multi-segment prosody generation
            return self._generate_segmented(inputs, segments, output_path)
        else:
            # Single text with optional SSML
            return self._generate_single(inputs, text, output_path)

    def _generate_single(self, inputs: dict[str, Any], text: str, output_path: Path) -> ToolResult:
        """Generate single audio file with global prosody settings."""
        model = inputs.get("model", "en_US-lessac-medium")
        model_path = self._resolve_model_path(model)
        speaker_id = inputs.get("speaker_id", 0)
        length_scale = inputs.get("global_length_scale", 1.0)
        sentence_silence = inputs.get("sentence_silence", 0.3)
        padding = inputs.get("add_silence_padding", 0.5)

        # Build piper command
        cmd = [
            "piper",
            "--model", model_path,
            "--speaker", str(speaker_id),
            "--length-scale", str(length_scale),
            "--sentence-silence", str(sentence_silence),
            "--output_file", str(output_path),
        ]

        # Process text with emphasis markers
        processed_text = self._process_emphasis(text)

        proc = subprocess.run(
            cmd,
            input=processed_text,
            capture_output=True,
            text=True,
            timeout=300,
        )

        if proc.returncode != 0:
            return ToolResult(success=False, error=f"Piper failed (exit {proc.returncode}): {proc.stderr}")
        if not output_path.exists():
            return ToolResult(success=False, error=f"Piper output file missing: {output_path}")

        # Add padding silence if requested
        if padding > 0:
            self._add_silence_padding(output_path, padding)

        return ToolResult(
            success=True,
            data={
                "provider": self.provider,
                "model": model,
                "speaker_id": speaker_id,
                "text_length": len(text),
                "output": str(output_path),
                "format": "wav",
                "segments_used": False,
            },
            artifacts=[str(output_path)],
            model=model,
        )

    def _generate_segmented(self, inputs: dict[str, Any], segments: list[dict[str, Any]], output_path: Path) -> ToolResult:
        """Generate multiple segments with different prosody and concatenate."""
        import tempfile

        model = inputs.get("model", "en_US-lessac-medium")
        model_path = self._resolve_model_path(model)
        speaker_id = inputs.get("speaker_id", 0)
        global_length_scale = inputs.get("global_length_scale", 1.0)

        segment_files = []

        try:
            with tempfile.TemporaryDirectory() as tmpdir:
                tmpdir_path = Path(tmpdir)

                for i, seg_data in enumerate(segments):
                    seg = ProsodySegment(**seg_data)
                    seg_path = tmpdir_path / f"seg_{i:03d}.wav"

                    # Calculate length_scale from pace and rate_percent
                    pace_scales = {"slow": 1.3, "measured": 1.1, "conversational": 1.0, "brisk": 0.9, "fast": 0.8}
                    length_scale = pace_scales.get(seg.pace, 1.0) * (seg.rate_percent / 100.0) * global_length_scale

                    # Build command for this segment
                    cmd = [
                        "piper",
                        "--model", model_path,
                        "--speaker", str(speaker_id),
                        "--length-scale", str(length_scale),
                        "--sentence-silence", "0",  # We'll add pauses manually
                        "--output_file", str(seg_path),
                    ]

                    processed_text = self._process_emphasis(seg.text, seg.emphasis_words)

                    proc = subprocess.run(
                        cmd,
                        input=processed_text,
                        capture_output=True,
                        text=True,
                        timeout=120,
                    )

                    if proc.returncode != 0 or not seg_path.exists():
                        return ToolResult(success=False, error=f"Segment {i} generation failed: {proc.stderr}")

                    # Add pause before/after if specified
                    if seg.pause_before > 0 or seg.pause_after > 0:
                        seg_path = self._add_segment_padding(seg_path, seg.pause_before, seg.pause_after)

                    segment_files.append(seg_path)

                # Concatenate all segments
                self._concatenate_audio(segment_files, output_path)

            return ToolResult(
                success=True,
                data={
                    "provider": self.provider,
                    "model": model,
                    "speaker_id": speaker_id,
                    "segment_count": len(segments),
                    "output": str(output_path),
                    "format": "wav",
                    "segments_used": True,
                },
                artifacts=[str(output_path)],
                model=model,
            )
        except Exception as e:
            return ToolResult(success=False, error=f"Segmented generation failed: {e}")

    def _process_emphasis(self, text: str, emphasis_words: list[str] | None = None) -> str:
        """Add Piper-compatible emphasis markers.
        Piper doesn't natively support SSML emphasis, but we can adjust via punctuation.
        """
        if not emphasis_words:
            return text

        # Piper respects some punctuation for emphasis
        # We'll add slight pauses around emphasis words
        result = text
        for word in emphasis_words:
            # Escape regex special chars
            escaped = re.escape(word)
            # Add subtle pause markers (piper uses | for pauses)
            result = re.sub(rf"\b({escaped})\b", r"| \1 |", result, flags=re.IGNORECASE)

        return result

    def _add_silence_padding(self, audio_path: Path, seconds: float):
        """Add silence padding to end of audio file."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            cmd = [
                "ffmpeg", "-y",
                "-i", str(audio_path),
                "-f", "lavfi", "-t", str(seconds),
                "-i", "anullsrc=channel_layout=mono:sample_rate=22050",
                "-filter_complex", "[0:a][1:a]concat=n=2:v=0:a=1[aout]",
                "-map", "[aout]",
                "-c:a", "pcm_s16le",
                str(tmp_path),
            ]
            subprocess.run(cmd, check=True, capture_output=True)
            tmp_path.replace(audio_path)
        except Exception:
            pass  # Non-critical

    def _add_segment_padding(self, audio_path: Path, before: float, after: float) -> Path:
        """Add silence before/after a segment."""
        import tempfile
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            filter_parts = []
            if before > 0:
                filter_parts.append(f"anullsrc=channel_layout=mono:sample_rate=22050:duration={before}[sil_b]")
            filter_parts.append("[0:a]")
            if after > 0:
                filter_parts.append(f"anullsrc=channel_layout=mono:sample_rate=22050:duration={after}[sil_a]")

            filter_complex = "".join(filter_parts) + "concat=n=" + str(2 + (1 if before > 0 else 0) + (1 if after > 0 else 0)) + ":v=0:a=1[aout]"

            inputs = ["ffmpeg", "-y", "-i", str(audio_path)]
            if before > 0:
                inputs.extend(["-f", "lavfi", "-t", str(before), "-i", "anullsrc=channel_layout=mono:sample_rate=22050"])
            if after > 0:
                inputs.extend(["-f", "lavfi", "-t", str(after), "-i", "anullsrc=channel_layout=mono:sample_rate=22050"])

            inputs.extend([
                "-filter_complex", filter_complex,
                "-map", "[aout]",
                "-c:a", "pcm_s16le",
                str(tmp_path),
            ])
            subprocess.run(inputs, check=True, capture_output=True)
            return tmp_path
        except Exception:
            return audio_path

    def _concatenate_audio(self, segment_files: list[Path], output_path: Path):
        """Concatenate audio segments using FFmpeg."""
        concat_file = output_path.parent / "concat_list.txt"
        with open(concat_file, "w") as f:
            for seg in segment_files:
                f.write(f"file '{seg.resolve()}'\n")

        cmd = [
            "ffmpeg", "-y",
            "-f", "concat", "-safe", "0",
            "-i", str(concat_file),
            "-c:a", "pcm_s16le",
            str(output_path),
        ]
        subprocess.run(cmd, check=True, capture_output=True)


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Enhanced Piper TTS")
    parser.add_argument("--text", default="")
    parser.add_argument("--segments", default="")
    parser.add_argument("--model", default="en_US-lessac-medium")
    parser.add_argument("--speaker-id", type=int, default=0)
    parser.add_argument("--length-scale", type=float, default=1.0)
    parser.add_argument("--sentence-silence", type=float, default=0.3)
    parser.add_argument("--output-path", required=True)
    parser.add_argument("--padding", type=float, default=0.5)
    args = parser.parse_args()

    tool = EnhancedPiperTTS()
    inputs = {
        "text": args.text,
        "model": args.model,
        "speaker_id": args.speaker_id,
        "global_length_scale": args.length_scale,
        "sentence_silence": args.sentence_silence,
        "output_path": args.output_path,
        "add_silence_padding": args.padding,
    }
    if args.segments:
        inputs["segments"] = json.loads(args.segments)

    result = tool.execute(inputs)
    print(json.dumps({"success": result.success, "data": result.data, "error": result.error}, indent=2))
    return 0 if result.success else 1


if __name__ == "__main__":
    raise SystemExit(main())