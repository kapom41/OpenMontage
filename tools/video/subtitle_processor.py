"""Modern Subtitle & Typography System — clean, professional, mobile-readable.

Replaces the old garish subtitle style with modern cinematic standards.
"""

from __future__ import annotations

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

# Modern subtitle style presets
SUBTITLE_PRESETS = {
    "cinematic": {
        "font": "Inter, Helvetica Neue, Arial, sans-serif",
        "font_size": 20,
        "primary_color": "&HFFFFFF",
        "outline_color": "&H000000",
        "outline_width": 1.5,
        "shadow_offset": 1,
        "shadow_color": "&H00000080",
        "margin_v": 70,
        "alignment": 2,  # Bottom center
        "max_chars_per_line": 42,
        "max_lines": 2,
        "line_spacing": 1.2,
        "fade_in_ms": 150,
        "fade_out_ms": 150,
        "emphasis_color": "&HFFFF00",  # Yellow for key words
        "emphasis_bold": True,
    },
    "documentary": {
        "font": "Georgia, Times New Roman, serif",
        "font_size": 18,
        "primary_color": "&HE0E0E0",
        "outline_color": "&H1A1A1A",
        "outline_width": 1,
        "shadow_offset": 1,
        "shadow_color": "&H00000060",
        "margin_v": 80,
        "alignment": 2,
        "max_chars_per_line": 45,
        "max_lines": 2,
        "line_spacing": 1.3,
        "fade_in_ms": 200,
        "fade_out_ms": 200,
        "emphasis_color": "&HC8C8FF",
        "emphasis_bold": True,
    },
    "minimal": {
        "font": "Inter, -apple-system, BlinkMacSystemFont, sans-serif",
        "font_size": 16,
        "primary_color": "&HFFFFFF",
        "outline_color": "&H000000",
        "outline_width": 1,
        "shadow_offset": 0,
        "shadow_color": "&H00000000",
        "margin_v": 60,
        "alignment": 2,
        "max_chars_per_line": 50,
        "max_lines": 1,
        "line_spacing": 1.0,
        "fade_in_ms": 100,
        "fade_out_ms": 100,
        "emphasis_color": "&H00FFFF",
        "emphasis_bold": False,
    },
    "mobile_vertical": {
        "font": "Inter, Helvetica Neue, Arial, sans-serif",
        "font_size": 24,
        "primary_color": "&HFFFFFF",
        "outline_color": "&H000000",
        "outline_width": 2,
        "shadow_offset": 2,
        "shadow_color": "&H000000AA",
        "margin_v": 140,
        "alignment": 2,
        "max_chars_per_line": 28,
        "max_lines": 2,
        "line_spacing": 1.2,
        "fade_in_ms": 100,
        "fade_out_ms": 100,
        "emphasis_color": "&HFFFF00",
        "emphasis_bold": True,
    },
    "modern_mobile": {
        "font": "Inter, Helvetica Neue, Arial, sans-serif",
        "font_size": 18,
        "primary_color": "&HFFFFFF",
        "outline_color": "&H000000",
        "outline_width": 1.5,
        "shadow_offset": 1,
        "shadow_color": "&H00000099",
        "margin_v": 80,
        "alignment": 2,
        "max_chars_per_line": 38,
        "max_lines": 2,
        "line_spacing": 1.15,
        "fade_in_ms": 120,
        "fade_out_ms": 120,
        "emphasis_color": "&HFFFF00",
        "emphasis_bold": True,
    },
}


@dataclass
class SubtitleStyle:
    font: str
    font_size: int
    primary_color: str
    outline_color: str
    outline_width: float
    shadow_offset: int
    shadow_color: str
    margin_v: int
    alignment: int
    max_chars_per_line: int
    max_lines: int
    line_spacing: float
    fade_in_ms: int
    fade_out_ms: int
    emphasis_color: str
    emphasis_bold: bool

    @classmethod
    def from_preset(cls, preset_name: str) -> "SubtitleStyle":
        preset = SUBTITLE_PRESETS.get(preset_name, SUBTITLE_PRESETS["cinematic"])
        return cls(**preset)

    def to_ass_style(self) -> str:
        """Convert to ASS style string for FFmpeg subtitles filter."""
        parts = [
            f"Fontname={self.font.split(',')[0].strip()}",
            f"Fontsize={self.font_size}",
            f"PrimaryColour={self.primary_color}",
            f"OutlineColour={self.outline_color}",
            f"Outline={self.outline_width}",
            f"Shadow={self.shadow_offset}",
            f"BackColour={self.shadow_color}",
            f"MarginV={self.margin_v}",
            f"Alignment={self.alignment}",
            f"Spacing={int((self.line_spacing - 1) * 100)}",
        ]
        if self.emphasis_bold:
            parts.append("Bold=1")
        return ",".join(parts)


class SubtitleProcessor:
    """Processes scripts into modern, well-formatted subtitles."""

    def __init__(self, style: SubtitleStyle | str = "cinematic"):
        if isinstance(style, str):
            self.style = SubtitleStyle.from_preset(style)
        else:
            self.style = style

    def process_script(self, script_sections: list[dict[str, Any]]) -> str:
        """Convert script sections to SRT with modern formatting."""
        srt_entries = []

        for section in script_sections:
            text = section.get("text", "")
            start = section.get("start_seconds", 0)
            end = section.get("end_seconds", 0)
            emphasis_words = section.get("delivery_cues", {}).get("emphasis_words", [])

            # Split into subtitle chunks
            chunks = self._split_into_chunks(text, emphasis_words)

            if not chunks:
                continue

            # Distribute time across chunks
            chunk_duration = (end - start) / len(chunks)

            for i, chunk in enumerate(chunks):
                chunk_start = start + i * chunk_duration
                chunk_end = start + (i + 1) * chunk_duration

                # Apply emphasis formatting
                formatted = self._apply_emphasis(chunk, emphasis_words)

                srt_entries.append(self._format_srt_entry(
                    len(srt_entries) + 1,
                    chunk_start,
                    chunk_end,
                    formatted,
                ))

        return "\n\n".join(srt_entries)

    def _split_into_chunks(self, text: str, emphasis_words: list[str]) -> list[str]:
        """Split text into subtitle-friendly chunks."""
        # Split by sentences first
        sentences = re.split(r'(?<=[.!?])\s+', text.strip())

        chunks = []
        current_chunk = ""
        current_length = 0

        for sentence in sentences:
            sentence = sentence.strip()
            if not sentence:
                continue

            # If sentence fits in one chunk, add it
            if current_length + len(sentence) <= self.style.max_chars_per_line:
                if current_chunk:
                    current_chunk += " " + sentence
                else:
                    current_chunk = sentence
                current_length = len(current_chunk)
            else:
                # Save current chunk and start new
                if current_chunk:
                    chunks.append(current_chunk)
                current_chunk = sentence
                current_length = len(sentence)

        if current_chunk:
            chunks.append(current_chunk)

        # If still too long, hard-split by words
        final_chunks = []
        for chunk in chunks:
            if len(chunk) <= self.style.max_chars_per_line:
                final_chunks.append(chunk)
            else:
                words = chunk.split()
                temp = ""
                for word in words:
                    if len(temp) + len(word) + 1 <= self.style.max_chars_per_line:
                        temp = temp + " " + word if temp else word
                    else:
                        if temp:
                            final_chunks.append(temp)
                        temp = word
                if temp:
                    final_chunks.append(temp)

        return final_chunks[:self.style.max_lines * 3]  # Safety limit

    def _apply_emphasis(self, text: str, emphasis_words: list[str]) -> str:
        """Apply ASS formatting to emphasis words."""
        if not emphasis_words:
            return text

        result = text
        for word in emphasis_words:
            escaped = re.escape(word)
            # ASS inline formatting: {\c&HFFFF00&\b1}word{\c&HFFFFFF&\b0}
            # Use raw strings to avoid regex escape interpretation
            fmt_start = r"{\c" + self.style.emphasis_color + r"\b1}"
            fmt_end = r"{\c" + self.style.primary_color + r"\b0}"
            result = re.sub(
                rf"\b({escaped})\b",
                lambda m: fmt_start + m.group(1) + fmt_end,
                result,
                flags=re.IGNORECASE,
            )
        return result

    def _format_srt_entry(self, index: int, start: float, end: float, text: str) -> str:
        """Format single SRT entry."""
        def fmt_time(seconds: float) -> str:
            ms = int(round(seconds * 1000))
            h, ms = divmod(ms, 3_600_000)
            m, ms = divmod(ms, 60_000)
            s, ms = divmod(ms, 1000)
            return f"{h:02}:{m:02}:{s:02},{ms:03}"

        return f"{index}\n{fmt_time(start)} --> {fmt_time(end)}\n{text}"

    def generate_ass_header(self) -> str:
        """Generate ASS header for direct ASS file creation."""
        return f"""[Script Info]
Title: Generated Subtitles
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.709
PlayResX: 1920
PlayResY: 1080

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{self.style.to_ass_style()}

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
"""


def create_subtitle_style(preset: str = "cinematic", **overrides) -> SubtitleStyle:
    """Factory function to create subtitle style with optional overrides."""
    style = SubtitleStyle.from_preset(preset)
    for key, value in overrides.items():
        if hasattr(style, key):
            setattr(style, key, value)
    return style


def generate_subtitles_from_script(
    script_path: Path,
    output_path: Path,
    style: str | SubtitleStyle = "cinematic",
) -> Path:
    """Convenience function to generate subtitles from script artifact."""
    with open(script_path, encoding="utf-8") as f:
        script = json.load(f)

    processor = SubtitleProcessor(style)
    srt_content = processor.process_script(script.get("sections", []))

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(srt_content, encoding="utf-8")
    return output_path


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Modern Subtitle Generator")
    parser.add_argument("--script", required=True, help="Path to script.json")
    parser.add_argument("--output", required=True, help="Output .srt path")
    parser.add_argument("--style", default="cinematic", choices=list(SUBTITLE_PRESETS.keys()))
    parser.add_argument("--font-size", type=int)
    parser.add_argument("--margin-v", type=int)
    args = parser.parse_args()

    overrides = {}
    if args.font_size:
        overrides["font_size"] = args.font_size
    if args.margin_v:
        overrides["margin_v"] = args.margin_v

    style = create_subtitle_style(args.style, **overrides)
    generate_subtitles_from_script(Path(args.script), Path(args.output), style)
    print(f"Subtitles generated: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())