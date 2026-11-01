"""Local-only hardware inspection and explicit model compatibility decisions.

The registry deliberately does not download weights. A model becomes downloadable
only after the caller has recorded its source, licence, size, and compatibility.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import date
from pathlib import Path
import shutil
import subprocess
from typing import Any


@dataclass(frozen=True)
class ModelSpec:
    name: str
    tasks: tuple[str, ...]
    license: str
    download_url: str
    download_size_gb: float
    min_vram_mb: int
    min_ram_mb: int


MODELS = (
    ModelSpec("Piper voices", ("tts",), "MIT", "https://github.com/rhasspy/piper", 0.1, 0, 512),
    ModelSpec("Stable Diffusion 1.5", ("image",), "CreativeML Open RAIL-M", "https://huggingface.co/runwayml/stable-diffusion-v1-5", 4.0, 4000, 8000),
    ModelSpec("CogVideoX-2B", ("video",), "Apache-2.0", "https://huggingface.co/THUDM/CogVideoX-2b", 10.0, 6000, 16000),
    ModelSpec("Wan 2.1 1.3B", ("video",), "Apache-2.0", "https://huggingface.co/Wan-AI/Wan2.1-T2V-1.3B-Diffusers", 8.0, 8000, 16000),
    ModelSpec("LTX-2", ("video",), "LTX-2 Community", "https://huggingface.co/Lightricks/LTX-2", 12.0, 12000, 16000),
)


def _nvidia() -> tuple[str | None, int]:
    try:
        output = subprocess.check_output(
            ["nvidia-smi", "--query-gpu=name,memory.total", "--format=csv,noheader"],
            text=True, stderr=subprocess.DEVNULL, timeout=5,
        ).strip().splitlines()[0]
        name, memory = [part.strip() for part in output.split(",", 1)]
        return name, int(memory.split()[0])
    except Exception:
        return None, 0


def hardware_profile(workspace: Path) -> dict[str, Any]:
    gpu, vram = _nvidia()
    disk = shutil.disk_usage(workspace)
    try:
        import psutil
        ram_mb = int(psutil.virtual_memory().available / 1024 / 1024)
    except Exception:
        ram_mb = 0
    return {
        "gpu": gpu,
        "vram_mb": vram,
        "available_ram_mb": ram_mb,
        "available_disk_gb": round(disk.free / 1024 ** 3, 2),
        "ffmpeg_available": bool(shutil.which("ffmpeg")),
        "piper_available": bool(shutil.which("piper")),
        "last_verified": date.today().isoformat(),
    }


def model_registry(workspace: Path) -> list[dict[str, Any]]:
    hw = hardware_profile(workspace)
    records = []
    for spec in MODELS:
        reasons = []
        if spec.min_vram_mb > hw["vram_mb"]:
            reasons.append(f"requires {spec.min_vram_mb} MB VRAM; detected {hw['vram_mb']} MB")
        if hw["available_ram_mb"] and spec.min_ram_mb > hw["available_ram_mb"]:
            reasons.append(f"requires {spec.min_ram_mb} MB free RAM")
        if spec.download_size_gb + 5 > hw["available_disk_gb"]:
            reasons.append("insufficient free disk space with a 5 GB safety reserve")
        row = asdict(spec)
        row["compatibility_status"] = "compatible" if not reasons else "incompatible"
        row["compatibility_notes"] = reasons or ["hardware profile meets stated minimums; installation still requires explicit licence/source recording"]
        row["installation_status"] = "not_installed"
        row["last_verified"] = hw["last_verified"]
        records.append(row)
    return records
