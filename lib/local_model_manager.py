"""Local Model Manager — realistic model selection for RTX 3050 4GB VRAM / 16GB RAM.

Provides honest assessment of what models can actually run on the hardware.
No fake claims about models that don't fit.
"""

from __future__ import annotations

import json
import subprocess
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


@dataclass
class ModelSpec:
    """Specification for a local AI model."""
    name: str
    model_id: str
    task: str  # "text_to_image", "text_to_video", "image_to_video"
    vram_required_mb: int
    ram_required_mb: int
    disk_required_mb: int
    quantized: bool = False
    quantization: str = ""  # "GGUF", "AWQ", "GPTQ", etc.
    backend: str = "diffusers"  # "diffusers", "llama.cpp", "transformers"
    speed_rating: str = "slow"  # "fast", "medium", "slow"
    quality_rating: str = "good"  # "excellent", "good", "acceptable"
    notes: str = ""


# Honest model specifications for RTX 3050 4GB VRAM
LOCAL_MODELS = {
    # Image Generation - WORKS on RTX 3050 4GB
    "sd15": ModelSpec(
        name="Stable Diffusion 1.5",
        model_id="runwayml/stable-diffusion-v1-5",
        task="text_to_image",
        vram_required_mb=3500,
        ram_required_mb=4000,
        disk_required_mb=4000,
        quantized=False,
        backend="diffusers",
        speed_rating="medium",
        quality_rating="good",
        notes="Base SD 1.5. Use fp16 + attention_slicing + vae_slicing. 512x512 native, can upscale."
    ),
    "sd15_quantized": ModelSpec(
        name="SD 1.5 (GGUF Q4)",
        model_id="runwayml/stable-diffusion-v1-5-gguf",
        task="text_to_image",
        vram_required_mb=2000,
        ram_required_mb=3000,
        disk_required_mb=2000,
        quantized=True,
        quantization="GGUF Q4_K_M",
        backend="diffusers",
        speed_rating="fast",
        quality_rating="acceptable",
        notes="Quantized version. Faster, lower VRAM. Use with GGUF-compatible loader."
    ),
    "sdxl": ModelSpec(
        name="SDXL Base 1.0",
        model_id="stabilityai/stable-diffusion-xl-base-1.0",
        task="text_to_image",
        vram_required_mb=6000,
        ram_required_mb=8000,
        disk_required_mb=7000,
        quantized=False,
        backend="diffusers",
        speed_rating="slow",
        quality_rating="excellent",
        notes="WILL NOT FIT on 4GB VRAM without CPU offload. Only viable with sequential CPU offload (very slow)."
    ),
    "sdxl_quantized": ModelSpec(
        name="SDXL (GGUF Q4)",
        model_id="stabilityai/stable-diffusion-xl-base-1.0-gguf",
        task="text_to_image",
        vram_required_mb=3500,
        ram_required_mb=6000,
        disk_required_mb=4000,
        quantized=True,
        quantization="GGUF Q4_K_M",
        backend="diffusers",
        speed_rating="medium",
        quality_rating="good",
        notes="Quantized SDXL. May fit on 4GB with attention slicing. Use GGUF loader."
    ),
    "flux_schnell": ModelSpec(
        name="FLUX.1 Schnell",
        model_id="black-forest-labs/FLUX.1-schnell",
        task="text_to_image",
        vram_required_mb=8000,
        ram_required_mb=12000,
        disk_required_mb=12000,
        quantized=False,
        backend="diffusers",
        speed_rating="slow",
        quality_rating="excellent",
        notes="WILL NOT FIT on 4GB VRAM. Requires 8GB+ or heavy CPU offload."
    ),
    "flux_schnell_quantized": ModelSpec(
        name="FLUX.1 Schnell (GGUF Q4)",
        model_id="black-forest-labs/FLUX.1-schnell-gguf",
        task="text_to_image",
        vram_required_mb=4500,
        ram_required_mb=8000,
        disk_required_mb=6000,
        quantized=True,
        quantization="GGUF Q4_K_M",
        backend="diffusers",
        speed_rating="medium",
        quality_rating="good",
        notes="Quantized FLUX. May barely fit on 4GB with optimizations. Marginal."
    ),

    # Video Generation - MOSTLY DO NOT WORK on RTX 3050 4GB
    "cogvideox_2b": ModelSpec(
        name="CogVideoX-2B",
        model_id="THUDM/CogVideoX-2b",
        task="text_to_video",
        vram_required_mb=6000,
        ram_required_mb=8000,
        disk_required_mb=8000,
        quantized=False,
        backend="diffusers",
        speed_rating="slow",
        quality_rating="good",
        notes="WILL NOT FIT on 4GB VRAM. Requires 6GB+ VRAM minimum."
    ),
    "cogvideox_2b_quantized": ModelSpec(
        name="CogVideoX-2B (GGUF Q4)",
        model_id="THUDM/CogVideoX-2b-gguf",
        task="text_to_video",
        vram_required_mb=3500,
        ram_required_mb=6000,
        disk_required_mb=4000,
        quantized=True,
        quantization="GGUF Q4_K_M",
        backend="diffusers",
        speed_rating="medium",
        quality_rating="acceptable",
        notes="Quantized CogVideoX. May fit on 4GB with attention/VAE slicing. Marginal."
    ),
    "wan_2_1_1_3b": ModelSpec(
        name="Wan 2.1 T2V 1.3B",
        model_id="Wan-AI/Wan2.1-T2V-1.3B-Diffusers",
        task="text_to_video",
        vram_required_mb=5000,
        ram_required_mb=8000,
        disk_required_mb=6000,
        quantized=False,
        backend="diffusers",
        speed_rating="slow",
        quality_rating="good",
        notes="WILL NOT FIT on 4GB VRAM. Requires 5GB+ VRAM."
    ),
    "wan_2_1_1_3b_quantized": ModelSpec(
        name="Wan 2.1 1.3B (GGUF Q4)",
        model_id="Wan-AI/Wan2.1-T2V-1.3B-Diffusers-gguf",
        task="text_to_video",
        vram_required_mb=3000,
        ram_required_mb=5000,
        disk_required_mb=3000,
        quantized=True,
        quantization="GGUF Q4_K_M",
        backend="diffusers",
        speed_rating="medium",
        quality_rating="acceptable",
        notes="Quantized Wan 1.3B. Best chance for local video on 4GB. Use with diffusers + slicing."
    ),
    "ltx_2": ModelSpec(
        name="LTX-2",
        model_id="Lightricks/LTX-2",
        task="text_to_video",
        vram_required_mb=10000,
        ram_required_mb=16000,
        disk_required_mb=12000,
        quantized=False,
        backend="diffusers",
        speed_rating="slow",
        quality_rating="excellent",
        notes="WILL NOT FIT on 4GB VRAM. Requires 10GB+ VRAM."
    ),
    "ltx_2_quantized": ModelSpec(
        name="LTX-2 (GGUF Q4)",
        model_id="Lightricks/LTX-2-gguf",
        task="text_to_video",
        vram_required_mb=6000,
        ram_required_mb=10000,
        disk_required_mb=7000,
        quantized=True,
        quantization="GGUF Q4_K_M",
        backend="diffusers",
        speed_rating="slow",
        quality_rating="good",
        notes="Quantized LTX. Still needs 6GB+ VRAM. Won't fit on 4GB."
    ),

    # Image-to-Video
    "stable_video_diffusion": ModelSpec(
        name="Stable Video Diffusion",
        model_id="stabilityai/stable-video-diffusion-img2vid-xt",
        task="image_to_video",
        vram_required_mb=5000,
        ram_required_mb=8000,
        disk_required_mb=5000,
        quantized=False,
        backend="diffusers",
        speed_rating="slow",
        quality_rating="good",
        notes="WILL NOT FIT on 4GB VRAM. Requires 5GB+ VRAM."
    ),
}


class LocalModelManager:
    """Manages local AI model selection based on actual hardware capabilities."""

    def __init__(self, vram_mb: int = None, ram_mb: int = None):
        self.vram_mb = vram_mb or self._detect_vram()
        self.ram_mb = ram_mb or self._detect_ram()
        self.available_models = self._detect_installed_models()

    def _detect_vram(self) -> int:
        """Detect GPU VRAM in MB."""
        try:
            import torch
            if torch.cuda.is_available():
                return torch.cuda.get_device_properties(0).total_memory // (1024 * 1024)
        except Exception:
            pass
        try:
            result = subprocess.run(
                ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
                capture_output=True, text=True, timeout=10
            )
            if result.returncode == 0:
                return int(result.stdout.strip().split("\n")[0])
        except Exception:
            pass
        return 0

    def _detect_ram(self) -> int:
        """Detect system RAM in MB."""
        try:
            import psutil
            return psutil.virtual_memory().total // (1024 * 1024)
        except Exception:
            pass
        return 16384  # Default assumption

    def _detect_installed_models(self) -> dict[str, bool]:
        """Check which models are actually installed in HuggingFace cache."""
        cache_dir = Path.home() / ".cache" / "huggingface" / "hub"
        installed = {}
        for key, spec in LOCAL_MODELS.items():
            # Check for model directory (handles both regular and quantized)
            model_path = cache_dir / f"models--{spec.model_id.replace('/', '--')}"
            installed[key] = model_path.exists()
        return installed

    def get_hardware_profile(self) -> dict[str, Any]:
        """Get complete hardware profile."""
        return {
            "gpu_vram_mb": self.vram_mb,
            "system_ram_mb": self.ram_mb,
            "cuda_available": self.vram_mb > 0,
            "models_installed": self.available_models,
            "recommended_models": self.get_recommendations(),
        }

    def get_recommendations(self) -> dict[str, list[dict]]:
        """Get model recommendations by task based on actual hardware."""
        recommendations = {
            "text_to_image": [],
            "text_to_video": [],
            "image_to_video": [],
            "not_recommended": [],
        }

        for key, spec in LOCAL_MODELS.items():
            fits_vram = spec.vram_required_mb <= self.vram_mb
            fits_ram = spec.ram_required_mb <= self.ram_mb
            fits = fits_vram and fits_ram

            info = {
                "key": key,
                "name": spec.name,
                "model_id": spec.model_id,
                "vram_required_mb": spec.vram_required_mb,
                "ram_required_mb": spec.ram_required_mb,
                "disk_required_mb": spec.disk_required_mb,
                "quantized": spec.quantized,
                "quantization": spec.quantization,
                "speed_rating": spec.speed_rating,
                "quality_rating": spec.quality_rating,
                "notes": spec.notes,
                "fits_hardware": fits,
                "installed": self.available_models.get(key, False),
            }

            if fits:
                recommendations[spec.task].append(info)
            else:
                recommendations["not_recommended"].append(info)

        # Sort by VRAM efficiency (lowest VRAM first for fitting models)
        for task in ["text_to_image", "text_to_video", "image_to_video"]:
            recommendations[task].sort(key=lambda x: x["vram_required_mb"])

        return recommendations

    def select_best_model(self, task: str, prefer_quality: bool = False) -> ModelSpec | None:
        """Select the best available model for a task."""
        recs = self.get_recommendations()
        candidates = recs.get(task, [])

        if not candidates:
            return None

        if prefer_quality:
            # Sort by quality rating, then speed
            quality_order = {"excellent": 3, "good": 2, "acceptable": 1}
            candidates.sort(key=lambda x: (-quality_order.get(x["quality_rating"], 0), x["speed_rating"]))
        else:
            # Sort by VRAM efficiency (lowest VRAM first)
            candidates.sort(key=lambda x: x["vram_required_mb"])

        best_key = candidates[0]["key"]
        return LOCAL_MODELS[best_key]

    def can_run_video_generation(self) -> tuple[bool, str]:
        """Check if ANY video generation model can run."""
        recs = self.get_recommendations()
        video_models = recs.get("text_to_video", []) + recs.get("image_to_video", [])
        
        if not video_models:
            return False, "No video generation models fit in 4GB VRAM. Use Ken Burns fallback."
        
        best = video_models[0]
        if best["fits_hardware"]:
            return True, f"Can run {best['name']} ({best['vram_required_mb']}MB VRAM)"
        else:
            return False, f"Best video model ({best['name']}) needs {best['vram_required_mb']}MB VRAM, only {self.vram_mb}MB available"

    def print_report(self) -> None:
        """Print a human-readable model capability report."""
        profile = self.get_hardware_profile()
        print("=" * 70)
        print(f"LOCAL MODEL CAPABILITY REPORT")
        print(f"=" * 70)
        print(f"GPU VRAM: {profile['gpu_vram_mb']} MB")
        print(f"System RAM: {profile['system_ram_mb']} MB")
        print(f"CUDA Available: {profile['cuda_available']}")
        print(f"")

        for task in ["text_to_image", "text_to_video", "image_to_video"]:
            recs = profile["recommended_models"].get(task, [])
            print(f"{task.upper().replace('_', ' ')}:")
            if recs:
                for m in recs:
                    status = "✓ INSTALLED" if m["installed"] else "○ NOT INSTALLED"
                    print(f"  {status} | {m['name']} ({m['model_id']})")
                    print(f"       VRAM: {m['vram_required_mb']}MB | RAM: {m['ram_required_mb']}MB | "
                          f"Speed: {m['speed_rating']} | Quality: {m['quality_rating']}")
                    if m["quantized"]:
                        print(f"       Quantized: {m['quantization']}")
                    print(f"       Notes: {m['notes']}")
            else:
                print(f"  ✗ NO MODELS FIT IN {self.vram_mb}MB VRAM")
            print(f"")

        # Show what won't fit
        not_rec = profile["recommended_models"].get("not_recommended", [])
        if not_rec:
            print(f"MODELS THAT WON'T FIT ON THIS HARDWARE:")
            for m in not_rec[:5]:  # Show top 5
                print(f"  ✗ {m['name']} - needs {m['vram_required_mb']}MB VRAM (have {self.vram_mb}MB)")
                print(f"       {m['notes']}")
        print(f"=" * 70)


def main() -> int:
    import argparse
    parser = argparse.ArgumentParser(description="Local Model Manager for RTX 3050 4GB")
    parser.add_argument("--vram", type=int, help="Override VRAM in MB")
    parser.add_argument("--ram", type=int, help="Override RAM in MB")
    parser.add_argument("--task", choices=["text_to_image", "text_to_video", "image_to_video"], 
                       help="Select best model for task")
    parser.add_argument("--prefer-quality", action="store_true", help="Prefer quality over speed")
    parser.add_argument("--list", action="store_true", help="List all model specs")
    args = parser.parse_args()

    manager = LocalModelManager(vram_mb=args.vram, ram_mb=args.ram)

    if args.list:
        for key, spec in LOCAL_MODELS.items():
            print(f"{key}: {spec.name} ({spec.task}) - VRAM: {spec.vram_required_mb}MB")
        return 0

    if args.task:
        best = manager.select_best_model(args.task, prefer_quality=args.prefer_quality)
        if best:
            print(f"Best for {args.task}: {best.name} ({best.model_id})")
            print(f"  VRAM: {best.vram_required_mb}MB, RAM: {best.ram_required_mb}MB")
            print(f"  Quantized: {best.quantized} ({best.quantization})")
            print(f"  Speed: {best.speed_rating}, Quality: {best.quality_rating}")
        else:
            print(f"No model fits for {args.task} on this hardware")
        return 0

    manager.print_report()

    # Video generation check
    can_run, msg = manager.can_run_video_generation()
    print(f"\nVIDEO GENERATION: {'✓ YES' if can_run else '✗ NO'}")
    print(f"  {msg}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())