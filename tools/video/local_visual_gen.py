"""Local AI Visual Generation Tool -- image and video generation using local models.

Supports:
- Stable Diffusion 1.5 (images) via diffusers
- CogVideoX-2B / Wan 2.1 / LTX-2 (video) via diffusers
- Fallback: Ken Burns / parallax animation from still images
- Hardware-aware model selection (VRAM/RAM checks)
"""

# -*- coding: utf-8 -*-
from __future__ import annotations

import json
import os
import shutil
import subprocess
import time
import requests
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Optional

try:
    from PIL import Image, ImageDraw, ImageFont
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from lib.local_model_manager import LocalModelManager, LOCAL_MODELS
from tools.base_tool import (
    BaseTool,
    Determinism,
    ExecutionMode,
    ResourceProfile,
    RetryPolicy,
    ResumeSupport,
    ToolResult,
    ToolStability,
    ToolTier,
)


@dataclass
class GenerationRequest:
    prompt: str
    negative_prompt: str = ""
    width: int = 1920
    height: int = 1080
    num_inference_steps: int = 20
    guidance_scale: float = 7.5
    seed: int = -1
    model: str = "auto"


@dataclass
class GenerationResult:
    success: bool
    output_path: str = ""
    model_used: str = ""
    generation_time_seconds: float = 0
    error: str = ""
    metadata: dict[str, Any] | None = None


class LocalVisualGenTool(BaseTool):
    """Local AI visual generation -- images and video from text prompts."""

    name = "local_visual_gen"
    version = "0.1.0"
    tier = ToolTier.CORE
    capability = "video_generation"
    provider = "local"
    stability = ToolStability.EXPERIMENTAL
    execution_mode = ExecutionMode.SYNC
    determinism = Determinism.DETERMINISTIC

    dependencies = ["cmd:ffmpeg", "python:diffusers", "python:torch", "python:accelerate"]
    install_instructions = "pip install diffusers accelerate transformers safetensors torch torchvision --index-url https://download.pytorch.org/whl/cu121"
    agent_skills = ["comfyui", "flux-best-practices"]

    capabilities = [
        "text_to_image",
        "text_to_video",
        "image_to_video",
        "ken_burns_animation",
        "parallax_animation",
    ]

    input_schema = {
        "type": "object",
        "required": ["operation"],
        "properties": {
            "operation": {
                "type": "string",
                "enum": ["text_to_image", "text_to_video", "image_to_video", "ken_burns", "parallax", "doctor"],
                "description": "Generation operation",
            },
            "prompt": {"type": "string", "description": "Positive prompt"},
            "negative_prompt": {"type": "string", "default": ""},
            "image_path": {"type": "string", "description": "Input image for img2vid/ken_burns/parallax"},
            "output_path": {"type": "string", "description": "Output file path"},
            "width": {"type": "integer", "default": 1920},
            "height": {"type": "integer", "default": 1080},
            "num_frames": {"type": "integer", "default": 48},
            "fps": {"type": "integer", "default": 24},
            "num_inference_steps": {"type": "integer", "default": 20},
            "guidance_scale": {"type": "number", "default": 7.5},
            "seed": {"type": "integer", "default": -1},
            "model": {"type": "string", "default": "auto", "description": "Model to use: auto, sdxl, sd15, cogvideox, wan, ltx"},
            "duration_seconds": {"type": "number", "default": 5.0, "description": "For ken_burns/parallax"},
            "motion_scale": {"type": "number", "default": 1.0, "description": "Motion intensity for video models"},
        },
    }

    resource_profile = ResourceProfile(
        cpu_cores=4, ram_mb=8192, vram_mb=6000, disk_mb=15000, network_required=False
    )

    retry_policy = RetryPolicy(max_retries=1, retryable_errors=["OOM", "CUDA out of memory"])
    resume_support = ResumeSupport.FROM_START
    idempotency_key_fields = ["operation", "prompt", "seed", "model"]
    side_effects = ["writes image/video file to output_path"]

    def __init__(self):
        super().__init__()
        self._pipe_cache: dict[str, Any] = {}
        self._device = self._get_device()
        self._model_manager = LocalModelManager()
        self._available_models = self._model_manager.available_models
        self._vram_mb = self._model_manager.vram_mb
        self._ram_mb = self._model_manager.ram_mb

        # Log capabilities at startup
        hw_profile = self._model_manager.get_hardware_profile()
        print(f"[LocalVisualGen] Hardware: {hw_profile['gpu_vram_mb']}MB VRAM, {hw_profile['system_ram_mb']}MB RAM")
        can_video, video_msg = self._model_manager.can_run_video_generation()
        if not can_video:
            print(f"[LocalVisualGen] WARNING: {video_msg}")
        else:
            print(f"[LocalVisualGen] Video generation: {video_msg}")

    def _get_device(self) -> str:
        try:
            import torch
            if torch.cuda.is_available():
                return "cuda"
        except Exception:
            pass
        return "cpu"

    def _get_vram_mb(self) -> int:
        return self._vram_mb

    def _select_model(self, operation: str, requested: str) -> tuple[str, str]:
        """Select best available model for operation using LocalModelManager."""
        vram = self._vram_mb

        if requested != "auto" and requested in self._available_models and self._available_models[requested]:
            # Find the model spec
            for key, spec in LOCAL_MODELS.items():
                if spec.model_id.endswith(requested) or key == requested:
                    if spec.vram_required_mb <= vram:
                        return key, spec.model_id
                    else:
                        print(f"[LocalVisualGen] WARNING: Requested model {requested} needs {spec.vram_required_mb}MB VRAM, only {vram}MB available")
                        break

        # Use model manager recommendations
        task_map = {
            "text_to_image": "text_to_image",
            "text_to_video": "text_to_video",
            "image_to_video": "image_to_video",
            "ken_burns": "text_to_image",  # Ken Burns uses image model
            "parallax": "text_to_image",
        }
        task = task_map.get(operation, "text_to_image")
        
        best_spec = self._model_manager.select_best_model(task, prefer_quality=False)
        if best_spec and best_spec.vram_required_mb <= vram:
            # Find the key for this spec
            for key, spec in LOCAL_MODELS.items():
                if spec.model_id == best_spec.model_id:
                    print(f"[LocalVisualGen] Selected model: {spec.name} ({spec.vram_required_mb}MB VRAM, {spec.speed_rating})")
                    return key, spec.model_id

        # Fallback to sd15 + ken burns if available
        if self._available_models.get("sd15") and vram >= 3500:
            return "sd15+kenburns", "runwayml/stable-diffusion-v1-5"

        # Ultimate fallback - no model fits
        return "none", ""

    def _load_image_pipe(self, model_id: str):
        """Load Stable Diffusion pipeline."""
        if model_id in self._pipe_cache:
            return self._pipe_cache[model_id]

        try:
            from diffusers import StableDiffusionPipeline, StableDiffusionXLPipeline
            import torch

            if "xl" in model_id.lower():
                pipe = StableDiffusionXLPipeline.from_pretrained(
                    model_id,
                    torch_dtype=torch.float16 if self._device == "cuda" else torch.float32,
                    use_safetensors=True,
                    variant="fp16" if self._device == "cuda" else None,
                )
            else:
                pipe = StableDiffusionPipeline.from_pretrained(
                    model_id,
                    torch_dtype=torch.float16 if self._device == "cuda" else torch.float32,
                    use_safetensors=True,
                )

            pipe = pipe.to(self._device)
            if self._device == "cuda":
                pipe.enable_attention_slicing()
                pipe.enable_vae_slicing()
                # pipe.enable_model_cpu_offload()  # Sequential offload for low VRAM

            self._pipe_cache[model_id] = pipe
            return pipe
        except Exception as e:
            raise RuntimeError(f"Failed to load image pipeline {model_id}: {e}")

    def _load_video_pipe(self, model_id: str):
        """Load video generation pipeline."""
        if model_id in self._pipe_cache:
            return self._pipe_cache[model_id]

        try:
            import torch
            from diffusers import CogVideoXPipeline, WanPipeline, LTXPipeline

            if "cogvideo" in model_id.lower():
                pipe = CogVideoXPipeline.from_pretrained(
                    model_id,
                    torch_dtype=torch.float16,
                    use_safetensors=True,
                )
            elif "wan" in model_id.lower():
                pipe = WanPipeline.from_pretrained(
                    model_id,
                    torch_dtype=torch.float16,
                    use_safetensors=True,
                )
            elif "ltx" in model_id.lower():
                pipe = LTXPipeline.from_pretrained(
                    model_id,
                    torch_dtype=torch.float16,
                    use_safetensors=True,
                )
            else:
                raise ValueError(f"Unknown video model: {model_id}")

            pipe = pipe.to(self._device)
            if self._device == "cuda":
                pipe.enable_attention_slicing()
                pipe.enable_vae_slicing()

            self._pipe_cache[model_id] = pipe
            return pipe
        except Exception as e:
            raise RuntimeError(f"Failed to load video pipeline {model_id}: {e}")

    def execute(self, inputs: dict[str, Any]) -> ToolResult:
        operation = inputs["operation"]
        start = time.time()

        try:
            if operation == "doctor":
                return self._doctor()
            elif operation == "text_to_image":
                result = self._text_to_image(inputs)
            elif operation == "text_to_video":
                result = self._text_to_video(inputs)
            elif operation == "image_to_video":
                result = self._image_to_video(inputs)
            elif operation == "ken_burns":
                result = self._ken_burns(inputs)
            elif operation == "parallax":
                result = self._parallax(inputs)
            else:
                return ToolResult(success=False, error=f"Unknown operation: {operation}")

            result.duration_seconds = round(time.time() - start, 2)
            return result
        except Exception as e:
            return ToolResult(success=False, error=str(e), duration_seconds=round(time.time() - start, 2))

    def _doctor(self) -> ToolResult:
        """Health check with detailed capability report."""
        hw_profile = self._model_manager.get_hardware_profile()
        recs = hw_profile["recommended_models"]
        issues = []

        if self._device == "cpu":
            issues.append("CUDA not available -- generation will be very slow")

        if self._get_vram_mb() < 4000:
            issues.append(f"Low VRAM ({self._get_vram_mb()} MB) -- only SD1.5 image gen feasible")

        available = [k for k, v in self._available_models.items() if v]
        if not available:
            issues.append("No local models found. Run model download first.")

        # Add capability summary
        capability_summary = {
            "hardware": hw_profile,
            "text_to_image": [m["name"] for m in recs.get("text_to_image", [])],
            "text_to_video": [m["name"] for m in recs.get("text_to_video", [])],
            "image_to_video": [m["name"] for m in recs.get("image_to_video", [])],
            "not_recommended": [m["name"] for m in recs.get("not_recommended", [])[:5]],
        }

        can_video, video_msg = self._model_manager.can_run_video_generation()
        capability_summary["video_generation_possible"] = can_video
        capability_summary["video_message"] = video_msg

        return ToolResult(
            success=len(issues) == 0,
            data=capability_summary,
            error="; ".join(issues) if issues else None,
        )

    def _text_to_image(self, inputs: dict[str, Any]) -> ToolResult:
        prompt = inputs["prompt"]
        negative = inputs.get("negative_prompt", "")
        width = inputs.get("width", 1920)
        height = inputs.get("height", 1080)
        steps = inputs.get("num_inference_steps", 20)
        guidance = inputs.get("guidance_scale", 7.5)
        seed = inputs.get("seed", -1)
        output_path = Path(inputs["output_path"])
        model_name = inputs.get("model", "auto")

        model_key, model_id = self._select_model("text_to_image", model_name)
        if model_key == "none":
            # Try PIL placeholder as last resort
            print("[LocalVisualGen] No image model available, trying PIL placeholder...")
            return self._generate_placeholder_image(inputs)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            import torch
            pipe = self._load_image_pipe(model_id)

            generator = torch.Generator(device=self._device)
            if seed >= 0:
                generator.manual_seed(seed)
            else:
                generator.seed()

            with torch.inference_mode():
                image = pipe(
                    prompt=prompt,
                    negative_prompt=negative,
                    width=width,
                    height=height,
                    num_inference_steps=steps,
                    guidance_scale=guidance,
                    generator=generator,
                ).images[0]

            image.save(output_path)

            return ToolResult(
                success=True,
                data=GenerationResult(
                    success=True,
                    output_path=str(output_path),
                    model_used=model_key,
                    generation_time_seconds=0,
                    metadata={"prompt": prompt, "width": width, "height": height},
                ).__dict__,
                artifacts=[str(output_path)],
            )
        except Exception as e:
            # Try PIL placeholder as fallback
            print(f"[LocalVisualGen] Image generation failed: {e}, trying PIL placeholder...")
            return self._generate_placeholder_image(inputs)

    def _text_to_video(self, inputs: dict[str, Any]) -> ToolResult:
        prompt = inputs["prompt"]
        negative = inputs.get("negative_prompt", "")
        width = inputs.get("width", 1920)
        height = inputs.get("height", 1080)
        num_frames = inputs.get("num_frames", 48)
        fps = inputs.get("fps", 24)
        steps = inputs.get("num_inference_steps", 20)
        guidance = inputs.get("guidance_scale", 7.5)
        seed = inputs.get("seed", -1)
        output_path = Path(inputs["output_path"])
        model_name = inputs.get("model", "auto")
        motion_scale = inputs.get("motion_scale", 1.0)

        model_key, model_id = self._select_model("text_to_video", model_name)

        if model_key == "sd15+kenburns" or model_key == "none":
            # Try stock video first (CPU-only, no PyTorch needed)
            print("[LocalVisualGen] No video model available, trying stock video...")
            stock_result = self._search_and_download_stock_video(inputs)
            if stock_result.success:
                return stock_result
            # Fallback: generate image + ken burns
            return self._fallback_ken_burns(inputs)

        output_path.parent.mkdir(parents=True, exist_ok=True)

        try:
            import torch
            pipe = self._load_video_pipe(model_id)

            generator = torch.Generator(device=self._device)
            if seed >= 0:
                generator.manual_seed(seed)
            else:
                generator.seed()

            with torch.inference_mode():
                video_frames = pipe(
                    prompt=prompt,
                    negative_prompt=negative,
                    width=width,
                    height=height,
                    num_frames=num_frames,
                    num_inference_steps=steps,
                    guidance_scale=guidance,
                    generator=generator,
                ).frames[0]

            # Export frames to video
            self._frames_to_video(frames, output_path, fps)

            return ToolResult(
                success=True,
                data=GenerationResult(
                    success=True,
                    output_path=str(output_path),
                    model_used=model_key,
                    generation_time_seconds=0,
                    metadata={"prompt": prompt, "frames": num_frames, "fps": fps},
                ).__dict__,
                artifacts=[str(output_path)],
            )
        except Exception as e:
            # Try stock video before Ken Burns
            print(f"[LocalVisualGen] Video generation failed: {e}, trying stock video...")
            stock_result = self._search_and_download_stock_video(inputs)
            if stock_result.success:
                return stock_result
            # Final fallback to Ken Burns
            print(f"[LocalVisualGen] Stock video failed, falling back to Ken Burns: {e}")
            return self._fallback_ken_burns(inputs)

    def _image_to_video(self, inputs: dict[str, Any]) -> ToolResult:
        """Image-to-video using video pipeline or fallback to stock video then ken burns."""
        image_path = Path(inputs["image_path"])
        if not image_path.exists():
            return ToolResult(success=False, error=f"Input image not found: {image_path}")

        # Try video model first
        model_key, model_id = self._select_model("image_to_video", inputs.get("model", "auto"))

        if model_key not in ("sd15+kenburns", "none"):
            # Use video pipeline img2vid
            return self._video_img2vid(inputs, model_id, model_key)

        # Try stock video based on prompt
        print("[LocalVisualGen] No video model available, trying stock video for img2vid...")
        stock_result = self._search_and_download_stock_video(inputs)
        if stock_result.success:
            return stock_result

        # Fallback to ken burns
        return self._ken_burns(inputs)

    def _video_img2vid(self, inputs: dict[str, Any], model_id: str, model_key: str) -> ToolResult:
        """Image-to-video with video pipeline."""
        try:
            import torch
            from PIL import Image
            pipe = self._load_video_pipe(model_id)

            image = Image.open(inputs["image_path"]).convert("RGB")
            image = image.resize((inputs.get("width", 1920), inputs.get("height", 1080)))

            generator = torch.Generator(device=self._device)
            seed = inputs.get("seed", -1)
            if seed >= 0:
                generator.manual_seed(seed)
            else:
                generator.seed()

            with torch.inference_mode():
                video_frames = pipe(
                    image=image,
                    prompt=inputs.get("prompt", ""),
                    negative_prompt=inputs.get("negative_prompt", ""),
                    num_frames=inputs.get("num_frames", 48),
                    num_inference_steps=inputs.get("num_inference_steps", 20),
                    guidance_scale=inputs.get("guidance_scale", 7.5),
                    generator=generator,
                ).frames[0]

            output_path = Path(inputs["output_path"])
            output_path.parent.mkdir(parents=True, exist_ok=True)
            self._frames_to_video(video_frames, output_path, inputs.get("fps", 24))

            return ToolResult(
                success=True,
                data=GenerationResult(
                    success=True,
                    output_path=str(output_path),
                    model_used=model_key,
                    generation_time_seconds=0,
                ).__dict__,
                artifacts=[str(output_path)],
            )
        except Exception as e:
            # Fallback to ken burns
            return self._ken_burns(inputs)


    def _ken_burns(self, inputs: dict[str, Any]) -> ToolResult:
            """Ken Burns animation from still image using FFmpeg."""
            image_path = Path(inputs["image_path"])
            output_path = Path(inputs["output_path"])
            duration = inputs.get("duration_seconds", 5.0)
            width = inputs.get("width", 1920)
            height = inputs.get("height", 1080)

            if not image_path.exists():
                return ToolResult(success=False, error=f"Input image not found: {image_path}")

            output_path.parent.mkdir(parents=True, exist_ok=True)

            # Ken Burns: slow zoom + pan using zoompan filter with simple expression
            zoom_factor = 1.15
            # zoompan z expression: zoom goes from 1.0 to zoom_factor over duration
            # zoompan z='1.0 + (zoom_factor-1.0)*t/duration'
            zoom_expr = f"1.0+{zoom_factor-1.0}*t/{duration}"

            # Build filter chain
            vf = (
                f"scale={width*zoom_factor}:{height*zoom_factor}:force_original_aspect_ratio=increase,"
                f"crop={width}:{height},"
                f"zoompan=z='{zoom_expr}':"
                f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':"
                f"d={int(duration*30)}:s={width}x{height},"
                f"fps=30"
            )

            cmd = [
                "ffmpeg", "-y",
                "-loop", "1",
                "-i", str(image_path),
                "-vf", vf,
                "-c:v", "libx264",
                "-crf", "23",
                "-preset", "medium",
                "-pix_fmt", "yuv420p",
                "-t", str(duration),
                str(output_path),
            ]

            try:
                self.run_command(cmd)
                if not output_path.exists():
                    return ToolResult(success=False, error="Ken Burns output not created")

                return ToolResult(
                    success=True,
                    data=GenerationResult(
                        success=True,
                        output_path=str(output_path),
                        model_used="ffmpeg_ken_burns",
                        generation_time_seconds=0,
                    ).__dict__,
                    artifacts=[str(output_path)],
                )
            except Exception as e:
                return ToolResult(success=False, error=f"Ken Burns failed: {e}")

    def _parallax(self, inputs: dict[str, Any]) -> ToolResult:
        """Parallax animation from still image (depth-based)."""
        # Simplified: use FFmpeg with displacement map
        # For true parallax, would need depth map generation
        return self._ken_burns(inputs)  # Fallback for now
    # 
    def _fallback_ken_burns(self, inputs: dict[str, Any]) -> ToolResult:
        """Generate image first, then ken burns."""
        # Generate base image
        temp_image = Path(inputs["output_path"]).with_suffix(".png")
        img_inputs = dict(inputs)
        img_inputs["operation"] = "text_to_image"
        img_inputs["output_path"] = str(temp_image)
        img_result = self._text_to_image(img_inputs)
    # 
        if not img_result.success:
            return img_result
    # 
        # Then ken burns
        kb_inputs = dict(inputs)
        kb_inputs["operation"] = "ken_burns"
        kb_inputs["image_path"] = str(temp_image)
        return self._ken_burns(kb_inputs)
    # 
    #     def _generate_placeholder_image(self, inputs: dict[str, Any]) -> ToolResult:
    #         """Generate a simple placeholder image using PIL (no PyTorch needed)."""
    #         if not PIL_AVAILABLE:
    #             return ToolResult(success=False, error="PIL not available for placeholder generation")
    #         
    #         prompt = inputs.get("prompt", "OpenMontage Video")
    #         width = inputs.get("width", 1920)
    #         height = inputs.get("height", 1080)
    #         output_path = Path(inputs["output_path"])
    #         
    #         output_path.parent.mkdir(parents=True, exist_ok=True)
    #         
    #         try:
    #             # Create a gradient background
    #             img = Image.new('RGB', (width, height), color=(20, 30, 50))
    #             draw = ImageDraw.Draw(img)
    #             
    #             # Create a subtle gradient
    #             for y in range(height):
    #                 r = int(20 + (y / height) * 30)
    #                 g = int(30 + (y / height) * 20)
    #                 b = int(50 + (y / height) * 40)
    #                 draw.line([(0, y), (width, y)], fill=(r, g, b))
    #             
    #             # Add prompt text
    #             try:
    #                 font = ImageFont.load_default()
    #             except:
    #                 font = None
    #             
    #             # Wrap text
    #             text_lines = []
    #             words = inputs.get("prompt", "OpenMontage").split()
    #             line = ""
    #             for word in words:
    #                 test_line = line + " " + word if line else word
    #                 if font:
    #                     bbox = draw.textbbox((0, 0), test_line, font=font)
    #                     w = bbox[2] - bbox[0]
    #                 else:
    #                     w = len(test_line) * 8
    #                 if w > width - 100:
    #                     text_lines.append(line)
    #                     line = word
    #                 else:
    #                     line = test_line
    #             if line:
    #                 text_lines.append(line)
    #             
    #             # Draw text centered
    #             y_start = height // 2 - (len(text_lines) * 20)
    #             for i, line in enumerate(text_lines):
    #                 if font:
    #                     bbox = draw.textbbox((0, 0), line, font=font)
    #                     text_w = bbox[2] - bbox[0]
    #                     text_h = bbox[3] - bbox[1]
    #                 else:
    #                     text_w = len(line) * 8
    #                     text_h = 16
    #                 x = (width - text_w) // 2
    #                 y = y_start + i * (text_h + 10)
    #                 # Draw shadow
    #                 draw.text((x+2, y+2), line, fill=(0, 0, 0, 128), font=font)
    #                 # Draw text
    #                 draw.text((x, y), line, fill=(255, 255, 255, 230), font=font)
    #             
    #             # Add OpenMontage watermark
    #             if font:
    #                 draw.text((width-150, height-40), "OpenMontage", fill=(255, 255, 255, 100), font=font)
    #             
    #             output_path.parent.mkdir(parents=True, exist_ok=True)
    #             img.save(output_path)
    #             
    #             return ToolResult(
    #                 success=True,
    #                 data=GenerationResult(
    #                     success=True,
    #                     output_path=str(output_path),
    #                     model_used="placeholder_pil",
    #                     generation_time_seconds=0,
    #                     metadata={"prompt": inputs.get("prompt", ""), "width": width, "height": height},
    #                 ).__dict__,
    #                 artifacts=[str(output_path)],
    #             )
    #         except Exception as e:
    #             return ToolResult(success=False, error=f"Placeholder generation failed: {e}")
    # 
    #     def _search_and_download_stock_video(self, inputs: dict[str, Any]) -> ToolResult:
    #         """Search and download stock video from free sources (CPU-only, no PyTorch required)."""
    #         import requests
    #         import tempfile
    #         import shutil
    #         
    #         prompt = inputs.get("prompt", "")
    #         duration = inputs.get("duration_seconds", 5.0)
    #         width = inputs.get("width", 1920)
    #         height = inputs.get("height", 1080)
    #         output_path = Path(inputs["output_path"])
    #         
    #         # Search queries derived from prompt (limited to 8)
    #         search_terms = self._extract_search_terms(prompt)
    #         
    #         # Try stock sources in order of preference for cinematic content (max 5 sources)
    #         sources = [
    #             ("wikimedia", "tools.video.stock_sources.wikimedia", "WikimediaSource"),
    #             ("nasa", "tools.video.stock_sources.nasa", "NASASource"),
    #             ("esa", "tools.video.stock_sources.esa", "ESASource"),
    #             ("jaxa", "tools.video.stock_sources.jaxa", "JAXASource"),
    #             ("pexels", "tools.video.stock_sources.pexels", "PexelsSource"),
    #         ]
    #         
    #         from tools.video.stock_sources.base import SearchFilters
    #         
    #         for source_name, module_path, class_name in sources[:5]:  # Max 5 sources
    #             try:
    #                 module = __import__(module_path, fromlist=[class_name])
    #                 source_class = getattr(module, class_name)
    #                 source = source_class()
    #                 
    #                 if not source.is_available():
    #                     continue
    #                 
    #                 # Limit search terms per source (max 3)
    #                 for term in search_terms[:3]:
    #                     filters = SearchFilters(kind="video", per_page=5)  # Max 5 results
    #                     results = source.search(term, filters)
    #                     
    #                     if results:
    #                         # Pick the best result (max 3 results per search)
    #                         for result in results[:3]:
    #                             if result.duration and result.duration >= duration * 0.5:
    #                                 # Download the video
    #                                 downloaded = self._download_and_process_stock(
    #                                     result, duration, width, height, output_path
    #                                 )
    #                                 if downloaded.success:
    #                                     downloaded.data["source"] = source_name
    #                                     downloaded.data["source_url"] = result.source_url
    #                                     downloaded.data["license"] = result.license
    #                                     downloaded.data["search_term"] = term
    #                                     print(f"[LocalVisualGen] Stock video from {source_name}: {term}")
    #                                     return downloaded
    #             except Exception as e:
    #                 print(f"[LocalVisualGen] Stock source {source_name} failed: {e}")
    #                 continue
    #         
    #         return ToolResult(success=False, error="No suitable stock video found")
    # 
    #     def _extract_search_terms(self, prompt: str) -> list[str]:
    #         """Extract key visual search terms from prompt."""
    #         # Remove common prompt filler words
    #         stop_words = {"cinematic", "photorealistic", "8k", "4k", "high quality", "detailed", 
    #                     "lighting", "camera", "shot", "angle", "view", "scene", "visual",
    #                       "style", "look", "feel", "mood", "atmosphere", "tone", "color"}
    #         
    #         words = prompt.lower().split()
    #         # Keep meaningful words, filter stop words
    #         terms = [w for w in words if w not in stop_words and len(w) > 3]
    #         
    #         # Build search terms - try most specific first
    #         search_terms = []
    #         if len(terms) >= 2:
    #             search_terms.append(" ".join(terms[:3]))
    #             search_terms.append(" ".join(terms[:2]))
    #         search_terms.extend(terms[:3])
    #         
    #         # Add specific topic-related terms if relevant (limited to 3 per category)
    #         prompt_lower = prompt.lower()
    #         if "koda" in prompt_lower or "film" in prompt_lower:
    #             search_terms.extend(["Kodak camera", "film camera", "vintage camera"])
    #         if "digital" in prompt_lower or "camera" in prompt_lower:
    #             search_terms.extend(["digital camera", "camera prototype"])
    #         if "factory" in prompt_lower or "industrial" in prompt_lower:
    #             search_terms.extend(["film factory", "industrial manufacturing"])
    #         if "bankrupt" in prompt_lower or "abandoned" in prompt_lower:
    #             search_terms.extend(["abandoned factory", "urban decay"])
    #             
    #         # Deduplicate and limit to max 8 search terms
    #         return list(dict.fromkeys(search_terms))[:8]
    # 
    #     def _download_and_process_stock(
    #         self, 
    #         candidate, 
    #         target_duration: float, 
    #         target_width: int, 
    #         target_height: int, 
    #         output_path: Path
    #     ) -> ToolResult:
    #         """Download stock video and process to target specs using FFmpeg."""
    #         import requests
    #         import tempfile
    #         
    #         download_url = candidate.download_url
    #         if not download_url:
    #             return ToolResult(success=False, error="No download URL")
    #         
    #         output_path.parent.mkdir(parents=True, exist_ok=True)
    #         
    #         try:
    #             with tempfile.TemporaryDirectory() as tmpdir:
    #                 tmpdir_path = Path(tmpdir)
    #                 temp_video = tmpdir_path / "stock_raw.mp4"
    #                 
    #                 # Download with progress
    #                 print(f"[LocalVisualGen] Downloading stock video: {download_url}")
    #                 response = requests.get(download_url, stream=True, timeout=120)
    #                 response.raise_for_status()
    #                 
    #                 with open(temp_video, "wb") as f:
    #                     for chunk in response.iter_content(chunk_size=8192):
    #                         f.write(chunk)
    #                 
    #                 if not temp_video.exists() or temp_video.stat().st_size == 0:
    #                     return ToolResult(success=False, error="Download failed or empty file")
    #                 
    #                 # Probe source video
    #                 probe_cmd = [
    #                     "ffprobe", "-v", "error", "-select_streams", "v:0",
    #                     "-show_entries", "stream=width,height,duration,avg_frame_rate",
    #                     "-of", "json", str(temp_video)
    #                 ]
    #                 import subprocess, json
    #                 probe_result = subprocess.run(probe_cmd, capture_output=True, text=True, timeout=30)
    #                 if probe_result.returncode != 0:
    #                     return ToolResult(success=False, error="FFprobe failed on downloaded video")
    #                 
    #                 probe_data = json.loads(probe_result.stdout)
    #                 stream = probe_data.get("streams", [{}])[0]
    #                 src_w = stream.get("width", 1920)
    #                 src_h = stream.get("height", 1080)
    #                 src_duration = float(stream.get("duration", 0))
    #                 src_fps_str = stream.get("avg_frame_rate", "30/1")
    #                 src_fps = eval(src_fps_str) if "/" in src_fps_str else 30
    #                 
    #                 if src_duration <= 0:
    #                     return ToolResult(success=False, error="Invalid source duration")
    #                 
    #                 # Calculate processing: crop to target aspect, scale to target resolution, trim/loop to target duration
    #                 target_aspect = target_width / target_height
    #                 src_aspect = src_w / src_h
    #                 
    #                 # Build FFmpeg filter chain
    #                 filters = []
    #                 
    #                 # Crop to target aspect ratio (center crop)
    #                 if abs(src_aspect - target_aspect) > 0.02:
    #                     if src_aspect > target_aspect:
    #                         # Source wider - crop sides
    #                         crop_h = src_h
    #                         crop_w = int(crop_h * target_aspect)
    #                         x_offset = (src_w - crop_w) // 2
    #                         filters.append(f"crop={crop_w}:{crop_h}:{x_offset}:0")
    #                     else:
    #                         # Source taller - crop top/bottom
    #                         crop_w = src_w
    #                         crop_h = int(crop_w / target_aspect)
    #                         y_offset = (src_h - crop_h) // 2
    #                         filters.append(f"crop={crop_w}:{crop_h}:0:{y_offset}")
    #                 
    #                 # Scale to target resolution
    #                 filters.append(f"scale={target_width}:{target_height}:force_original_aspect_ratio=decrease,pad={target_width}:{target_height}:(ow-iw)/2:(oh-ih)/2")
    #                 
    #                 # Set fps to 30
    #                 filters.append("fps=30")
    #                 
    #                 # Duration handling: if source is longer, trim; if shorter, loop
    #                 if src_duration >= target_duration:
    #                     # Trim from center (more interesting part)
    #                     start_time = max(0, (src_duration - target_duration) / 2)
    #                     trim_filter = f"trim=start={start_time}:duration={target_duration},setpts=PTS-STARTPTS"
    #                     filters.append(trim_filter)
    #                 else:
    #                     # Loop to extend
    #                     loops_needed = int(target_duration / src_duration) + 1
    #                     loop_filter = f"loop=loop={loops_needed}:size={int(src_fps * src_duration)}:start=0"
    #                     filters.append(loop_filter)
    #                     # Then trim to exact duration
    #                     filters.append(f"trim=duration={target_duration},setpts=PTS-STARTPTS")
    #                 
    #                 filter_chain = ",".join(filters)
    #                 
    #                 cmd = [
    #                     "ffmpeg", "-y",
    #                     "-i", str(temp_video),
    #                     "-vf", filter_chain,
    #                     "-c:v", "libx264",
    #                     "-crf", "23",
    #                     "-preset", "medium",
    #                     "-pix_fmt", "yuv420p",
    #                     "-an",  # No audio from stock (we add narration separately)
    #                     "-t", str(target_duration),
    #                     str(output_path)
    #                 ]
    #                 
    #                 import subprocess
    #                 result = subprocess.run(cmd, capture_output=True, text=True, timeout=180)
    #                 
    #                 if result.returncode != 0:
    #                     return ToolResult(success=False, error=f"FFmpeg processing failed: {result.stderr[-500:]}")
    #                 
    #                 if not output_path.exists() or output_path.stat().st_size == 0:
    #                     return ToolResult(success=False, error="Processed video not created")
    #                 
    #                 # Verify output
    #                 verify_cmd = [
    #                     "ffprobe", "-v", "error", "-select_streams", "v:0",
    #                     "-show_entries", "stream=width,height,duration",
    #                     "-of", "json", str(output_path)
    #                 ]
    #                 verify_result = subprocess.run(verify_cmd, capture_output=True, text=True, timeout=30)
    #                 if verify_result.returncode == 0:
    #                     verify_data = json.loads(verify_result.stdout)
    #                     stream = verify_data.get("streams", [{}])[0]
    #                     out_w = stream.get("width", 0)
    #                     out_h = stream.get("height", 0)
    #                     out_dur = float(stream.get("duration", 0))
    #                     
    #                     if out_w == target_width and out_h == target_height and abs(out_dur - target_duration) < 0.5:
    #                         return ToolResult(
    #                             success=True,
    #                             data=GenerationResult(
    #                                 success=True,
    #                                 output_path=str(output_path),
    #                                 model_used=f"stock_video",
    #                                 generation_time_seconds=0,
    #                                 metadata={
    #                                     "source": "stock",
    #                                     "duration": out_dur,
    #                                     "width": out_w,
    #                                     "height": out_h
    #                                 }
    #                             ).__dict__,
    #                             artifacts=[str(output_path)],
    #                         )
    #                 
    #                 return ToolResult(success=True, 
    #                     data=GenerationResult(success=True, output_path=str(output_path), model_used="stock_video").__dict__,
    #                     artifacts=[str(output_path)])
    #                 
    #         except Exception as e:
    #             return ToolResult(success=False, error=f"Stock video processing failed: {e}")
    # 
    def _fallback_ken_burns(self, inputs: dict[str, Any]) -> ToolResult:
        """Generate image first, then ken burns."""
        # Generate base image
        temp_image = Path(inputs["output_path"]).with_suffix(".png")
        img_inputs = dict(inputs)
        img_inputs["operation"] = "text_to_image"
        img_inputs["output_path"] = str(temp_image)
        img_result = self._text_to_image(img_inputs)
    # 
        if not img_result.success:
            return img_result
    # 
        # Then ken burns
        kb_inputs = dict(inputs)
        kb_inputs["operation"] = "ken_burns"
        kb_inputs["image_path"] = str(temp_image)
        return self._ken_burns(kb_inputs)
    # 
    #     def _frames_to_video(self, frames: list, output_path: Path, fps: int):
    #         """Save frames as video using FFmpeg."""
    #         import tempfile
    #         import os
    # 
    #         with tempfile.TemporaryDirectory() as tmpdir:
    #             tmpdir_path = Path(tmpdir)
    #             for i, frame in enumerate(frames):
    #                 frame.save(tmpdir_path / f"frame_{i:05d}.png")
    # 
    #             cmd = [
    #                 "ffmpeg", "-y",
    #                 "-framerate", str(fps),
    #                 "-i", str(tmpdir_path / "frame_%05d.png"),
    #                 "-c:v", "libx264",
    #                 "-crf", "23",
    #                 "-preset", "medium",
    #                 "-pix_fmt", "yuv420p",
    #                 str(output_path),
    #             ]
    #             self.run_command(cmd)
    # 
    # 
    # def main() -> int:
    #     import argparse
    #     parser = argparse.ArgumentParser(description="Local Visual Generation Tool")
    #     parser.add_argument("operation", choices=["text_to_image", "text_to_video", "image_to_video", "ken_burns", "parallax", "doctor"])
    #     parser.add_argument("--prompt", default="")
    #     parser.add_argument("--negative-prompt", default="")
    #     parser.add_argument("--image-path", default="")
    #     parser.add_argument("--output-path", required=True)
    #     parser.add_argument("--width", type=int, default=1920)
    #     parser.add_argument("--height", type=int, default=1080)
    #     parser.add_argument("--num-frames", type=int, default=48)
    #     parser.add_argument("--fps", type=int, default=24)
    #     parser.add_argument("--steps", type=int, default=20)
    #     parser.add_argument("--guidance", type=float, default=7.5)
    #     parser.add_argument("--seed", type=int, default=-1)
    #     parser.add_argument("--model", default="auto")
    #     parser.add_argument("--duration", type=float, default=5.0)
    #     parser.add_argument("--motion-scale", type=float, default=1.0)
    #     args = parser.parse_args()
    # 
    #     tool = LocalVisualGenTool()
    #     result = tool.execute(vars(args))
    #     print(json.dumps({"success": result.success, "data": result.data, "error": result.error}, indent=2))
    #     return 0 if result.success else 1
    # 
    # 
    # if __name__ == "__main__":
    #     raise SystemExit(main())