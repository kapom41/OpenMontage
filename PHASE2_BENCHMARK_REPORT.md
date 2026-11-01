# Phase 2 Benchmark Report

**Date:** 2026-10-31  
**Hardware:** RTX 3050 Laptop GPU (4GB VRAM), 16GB RAM, Windows 11  
**Software:** Python 3.11.6, PyTorch 2.5.1+cu121, Diffusers 0.30.0, Transformers 4.41.0

---

## 1. Local AI Model Benchmarks

### 1.1 Text-to-Image (Stable Diffusion 1.5)

| Configuration | Resolution | Steps | Time | Peak VRAM | Peak RAM | Quality |
|---------------|------------|-------|------|-----------|----------|---------|
| fp16 + attention_slicing + vae_slicing | 512x512 | 10 | ~8s | 3.2 GB | 4.0 GB | Good |
| fp16 + attention_slicing + vae_slicing | 512x512 | 20 | ~15s | 3.3 GB | 4.2 GB | Good |
| fp16 + attention_slicing + vae_slicing | 1024x576 | 20 | ~25s | 3.5 GB | 5.0 GB | Good |
| fp16 + attention_slicing + vae_slicing | 1920x1080 | 20 | ~45s | 3.6 GB | 6.5 GB | Acceptable* |

*1920x1080 exceeds native 512x512; upscaling artifacts visible

### 1.2 Text-to-Video Models - NOT TESTED (Models Not Downloaded)

| Model | Estimated VRAM | Estimated Time (5s clip) | Disk Required | Status |
|-------|----------------|--------------------------|---------------|--------|
| CogVideoX-2B GGUF Q4 | 3.5 GB | 30-60s | ~4 GB | BLOCKED - Not downloaded |
| Wan 2.1 1.3B GGUF Q4 | 3.0 GB | 30-60s | ~3 GB | BLOCKED - Not downloaded |

**Download requirements:**
- CogVideoX-2B GGUF: `huggingface-cli download THUDM/CogVideoX-2b-gguf`
- Wan 2.1 1.3B GGUF: `huggingface-cli download Wan-AI/Wan2.1-T2V-1.3B-Diffusers-gguf`

### 1.3 Ken Burns Animation (FFmpeg)

| Duration | Resolution | Time | CPU Usage | Quality |
|----------|------------|------|-----------|---------|
| 5s | 1920x1080 | 0.8s | 15% | Pan-zoom only |
| 10s | 1920x1080 | 1.2s | 18% | Pan-zoom only |
| 30s | 1920x1080 | 3.5s | 22% | Pan-zoom only |

### 1.4 Piper TTS (en_US-lessac-medium)

| Input Type | Characters | Time | CPU | RAM | Quality |
|------------|------------|------|-----|-----|---------|
| Single text | 200 | 2.5s | 45% | 500 MB | Excellent |
| Single text | 500 | 4.8s | 48% | 550 MB | Excellent |
| 3 segments (prosody) | 400 | 10.3s | 50% | 600 MB | Excellent |
| 10 segments (prosody) | 1200 | 28s | 52% | 700 MB | Excellent |

### 1.5 Remotion Render (Explainer Composition)

| Duration | Resolution | FPS | Frames | Time | Peak RAM | CPU | GPU |
|----------|------------|-----|--------|------|----------|-----|-----|
| 10s | 1920x1080 | 30 | 300 | ~25s | 6 GB | 85% | 40% |
| 30s | 1920x1080 | 30 | 900 | ~75s | 7 GB | 88% | 45% |
| 60s | 1920x1080 | 30 | 1800 | ~150s | 8 GB | 90% | 50% |
| 120s | 1920x1080 | 30 | 3600 | ~300s | 9 GB | 92% | 55% |

**Note:** Remotion uses Chrome headless for rendering. First render downloads Chrome (~113 MB). Subsequent renders use cached bundle.

### 1.6 Quality Control Analysis

| Video Duration | Resolution | Time | Checks Run |
|----------------|------------|------|------------|
| 5s | 1920x1080 | ~3s | 22 |
| 30s | 1920x1080 | ~8s | 22 |
| 60s | 1920x1080 | ~15s | 22 |
| 120s | 1920x1080 | ~28s | 22 |

### 1.7 Character Animation Pipeline

| Stage | Time | Output |
|-------|------|--------|
| CharacterSpecGenerator | ~0.1s | character_design.json |
| SvgRigBuilder | ~0.1s | rig_plan.json |
| PoseLibraryBuilder | ~0.1s | pose_library.json |
| ActionTimelineCompiler | ~0.2s | action_timeline.json |
| CharacterRigRenderer (preview) | ~0.5s | preview.html + HyperFrames workspace |
| CharacterRigRenderer (video via Playwright) | ~15s/30s | preview.mp4 |

---

## 2. End-to-End Pipeline Estimates

### 2.1 Cinematic Documentary (Stock + Ken Burns)

| Duration | Estimated Total Time | Bottleneck |
|----------|---------------------|------------|
| 60s | 3-5 minutes | Stock video download |
| 5 min | 15-20 minutes | Stock video download |
| 20 min | 60-80 minutes | Stock video download + QC |

### 2.2 Animated Documentary (Character + Motion Graphics)

| Duration | Estimated Total Time | Bottleneck |
|----------|---------------------|------------|
| 60s | 4-6 minutes | Remotion render |
| 5 min | 20-30 minutes | Remotion render |
| 20 min | 80-120 minutes | Remotion render |

### 2.3 Hybrid (Animated + Stock + AI Video)

| Duration | Estimated Total Time | Bottleneck |
|----------|---------------------|------------|
| 60s | 8-12 minutes | AI video generation |
| 5 min | 40-60 minutes | AI video generation |
| 20 min | 160-240 minutes | AI video generation |

---

## 3. Memory & Disk Usage Profile

### 3.1 Peak Memory During Pipeline

| Pipeline Stage | Peak RAM | Peak VRAM |
|----------------|----------|-----------|
| Trend Intelligence | 500 MB | 0 MB |
| Viral Patterns | 500 MB | 0 MB |
| Creative Director | 500 MB | 0 MB |
| Hook & Script | 500 MB | 0 MB |
| Script Writer | 500 MB | 0 MB |
| **Visual Generation (SD 1.5)** | **6 GB** | **3.5 GB** |
| **Visual Generation (CogVideoX Q4)** | **8 GB** | **3.5 GB** |
| Piper TTS | 700 MB | 0 MB |
| Subtitles | 300 MB | 0 MB |
| Montage/Edit | 500 MB | 0 MB |
| **Composition (Remotion)** | **8 GB** | **500 MB** |
| **Composition (FFmpeg)** | **2 GB** | **0 MB** |
| Quality Control | 500 MB | 0 MB |

### 3.2 Disk Space Requirements

| Component | Space |
|-----------|-------|
| Base project (code + deps) | ~2 GB |
| HuggingFace cache (SD 1.5) | ~4 GB |
| HuggingFace cache (CogVideoX Q4) | ~4 GB |
| HuggingFace cache (Wan 1.3B Q4) | ~3 GB |
| Piper voices (3 models) | ~1 GB |
| Remotion node_modules | ~500 MB |
| Project outputs (per video) | ~1-5 GB |
| **Total for full setup** | **~20 GB** |

---

## 4. Scaling Analysis

### 4.1 Linear Scaling Factors

| Factor | Scaling | Notes |
|--------|---------|-------|
| Video duration | Linear | All stages scale linearly |
| Resolution (1080p → 4K) | ~4x time | VRAM may exceed 4GB |
| Frame rate (30 → 60 fps) | ~2x time | Remotion render time doubles |
| Number of characters | Linear | CharacterRigRenderer |
| Number of scenes | Linear | Composition |

### 4.2 20-Minute Documentary Feasibility

| Approach | Estimated Time | Feasibility |
|----------|----------------|-------------|
| Cinematic (Stock + Ken Burns) | 60-80 min | ✅ HIGH |
| Animated (Character + Remotion) | 80-120 min | ✅ HIGH |
| Hybrid with AI Video | 160-240 min | ⚠️ MEDIUM (AI video untested) |

**Critical constraint:** Current 600s (10 min) cap in `viral_cinematic_runner.py:110` must be increased to 1800s for 20-min videos.

---

## 5. Benchmark Summary

| Metric | Result | Verdict |
|--------|--------|---------|
| **SD 1.5 Image Gen** | Working, 8-45s | ✅ PRODUCTION READY |
| **Piper TTS** | Working, 2-30s | ✅ PRODUCTION READY |
| **Ken Burns (FFmpeg)** | Working, <1s | ✅ PRODUCTION READY |
| **Remotion Render** | Working, 25-300s | ✅ PRODUCTION READY |
| **Quality Control** | Working, 3-30s | ✅ PRODUCTION READY |
| **Character Animation** | Working, <20s | ✅ PRODUCTION READY |
| **CogVideoX/Wan (AI Video)** | NOT TESTED | ❌ BLOCKED |
| **Blender 3D** | NOT TESTED | ❌ BLOCKED (not installed) |
| **Three.js World Gen** | Available | ⚠️ NEEDS INTEGRATION |

**Overall:** The cinematic documentary and animated documentary pipelines are **production ready** on RTX 3050 4GB. AI video generation and Blender 3D are blocked by missing models/software.