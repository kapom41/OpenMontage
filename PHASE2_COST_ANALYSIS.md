# Phase 2 Cost Analysis Report

**Date:** 2026-10-31  
**Currency:** USD  
**Assumption:** Individual developer / small team (≤3 people)

---

## 1. Tool & Model Cost Comparison

### 1.1 Core Production Stack

| Tool / Model | License Cost | API Cost | Local Hardware | Commercial Use | Total Monthly |
|--------------|--------------|----------|----------------|----------------|---------------|
| **Remotion** | Free (Free License) | $0 | CPU/GPU | ✅ | **$0** |
| **Stable Diffusion 1.5** | OpenRAIL-M | $0 | RTX 3050 4GB | ✅ | **$0** |
| **Wan 2.1 1.3B** | Apache 2.0 | $0 | RTX 3050 4GB (Q4) | ✅ | **$0** |
| **CogVideoX-2B** | Apache 2.0 + reg | $0 | RTX 3050 4GB (Q4) | ✅* | **$0** |
| **Piper TTS** | MIT | $0 | CPU only | ✅ | **$0** |
| **FFmpeg** | LGPL | $0 | CPU only | ✅ | **$0** |
| **GSAP** | Free | $0 | Browser/Node | ✅ | **$0** |
| **Three.js** | MIT | $0 | Browser/Node | ✅ | **$0** |
| **Blender** | GPL v3 | $0 | CPU/GPU | ✅ | **$0** |
| **Python deps** | Various (MIT/Apache/BSD) | $0 | - | ✅ | **$0** |

*Requires free registration at open.bigmodel.cn

**Core Stack Monthly Cost: $0**

---

### 1.2 Stock Footage Sources

| Source | Free Tier | Paid Tier | Commercial | Attribution |
|--------|-----------|-----------|------------|-------------|
| **Wikimedia Commons** | Unlimited | N/A | ✅ | CC BY/SA |
| **NASA** | Unlimited | N/A | ✅ | Recommended |
| **ESA** | Unlimited | N/A | ✅ | Required |
| **Mixkit** | Unlimited | N/A | ✅ | Not required |
| **Pexels** | 200 req/hour | $199/mo (API) | ✅ | Not required |
| **Pixabay** | 200 req/hour | $199/mo (API) | ✅ | Not required |
| **Videvo** | Limited | $12/mo | ✅ | Varies |
| **Coverr** | Requires auth | N/A | ✅ | Varies |

**Stock Footage Monthly Cost: $0** (using free sources)

---

### 1.3 Cloud/Optional Services

| Service | Free Tier | Paid Tier | When Needed |
|---------|-----------|-----------|-------------|
| **YouTube Data API** | 100 uploads/day | Quota extension (audit) | >100 videos/day |
| **YouTube Analytics API** | Included | N/A | Analytics access |
| **HuggingFace Hub** | Unlimited | Pro $9/mo | Private models, faster downloads |
| **Google Cloud (vertex AI)** | $300 credit | Pay-per-use | Cloud GPU fallback |
| **RunPod / Vast.ai** | N/A | ~$0.50-2.00/hr | Cloud GPU for large models |
| **Replicate / Fal.ai** | N/A | Per-generation | AI video without local GPU |

**Optional Cloud Monthly: $0-50** (only if local GPU insufficient)

---

## 2. Hardware Cost Analysis

### 2.1 Current Hardware (Already Owned)

| Component | Spec | Market Value | Notes |
|-----------|------|--------------|-------|
| **GPU** | RTX 3050 Laptop 4GB VRAM | ~$200-300 | Minimum for SD 1.5 |
| **RAM** | 16GB DDR4/5 | ~$50-80 | Sufficient |
| **Storage** | 512GB-1TB NVMe | ~$50-100 | 20GB+ for models |
| **CPU** | Intel i5/i7 or AMD Ryzen 5/7 | ~$200-400 | Adequate |

**Sunk Cost: ~$500-880** (already owned)

---

### 2.2 Hardware Upgrade Paths (If Needed)

| Upgrade | Cost | Benefit | ROI |
|---------|------|---------|-----|
| **RTX 3060 12GB (desktop)** | ~$300-350 | Runs SDXL, FLUX, CogVideoX native | High |
| **RTX 4060 8GB (laptop)** | ~$800-1000 (new laptop) | Better video gen, 8GB VRAM | Medium |
| **RTX 4070 12GB (desktop)** | ~$550-600 | Runs all local models comfortably | High |
| **64GB RAM** | ~$150-200 | Larger models, more concurrent | Low |
| **2TB NVMe** | ~$120-180 | More model cache | Low |

**Recommendation:** Stay with RTX 3050 4GB. Use quantized models (GGUF Q4) and stock footage. Upgrade only if production volume justifies it.

---

## 3. Per-Video Production Cost

### 3.1 Cinematic Documentary (Stock + Ken Burns)

| Duration | Local Compute | Stock Footage | TTS | Total |
|----------|---------------|---------------|-----|-------|
| 60s | $0.02 (electricity) | $0 | $0 | **$0.02** |
| 5 min | $0.10 | $0 | $0 | **$0.10** |
| 20 min | $0.40 | $0 | $0 | **$0.40** |

### 3.2 Animated Documentary (Character + Remotion)

| Duration | Local Compute | Remotion | TTS | Total |
|----------|---------------|----------|-----|-------|
| 60s | $0.05 | $0 | $0 | **$0.05** |
| 5 min | $0.25 | $0 | $0 | **$0.25** |
| 20 min | $1.00 | $0 | $0 | **$1.00** |

### 3.3 Hybrid with AI Video Generation (Local)

| Duration | Local Compute | AI Video Gen | TTS | Total |
|----------|---------------|--------------|-----|-------|
| 60s | $0.10 | $0.15 | $0 | **$0.25** |
| 5 min | $0.50 | $0.75 | $0 | **$1.25** |
| 20 min | $2.00 | $3.00 | $0 | **$5.00** |

### 3.4 Hybrid with Cloud AI Video (RunPod RTX 4090 ~$0.79/hr)

| Duration | Cloud GPU Time | Cost/hr | Total |
|----------|----------------|---------|-------|
| 60s (12 clips × 5s) | ~10 min | $0.79 | **$0.13** |
| 5 min (60 clips) | ~50 min | $0.79 | **$0.66** |
| 20 min (240 clips) | ~3.5 hr | $0.79 | **$2.77** |

---

## 4. YouTube Publishing Costs

| Item | Cost | Frequency |
|------|------|-----------|
| YouTube Data API | Free (100 uploads/day) | Daily |
| Thumbnail design | $0 (DIY with Remotion/GSAP) | Per video |
| Channel verification | Free (phone) | One-time |
| YouTube Premium (for bg music) | $13.99/mo | Optional |

**Publishing Monthly: $0** (API free tier sufficient for daily uploads)

---

## 5. Annual Cost Projection

### Scenario A: Cinematic Only (20 videos/month, 5 min avg)

| Category | Monthly | Annual |
|----------|---------|--------|
| Electricity | $2.00 | $24 |
| Storage (model cache) | $0 | $0 |
| Stock footage | $0 | $0 |
| YouTube API | $0 | $0 |
| **Total** | **$2.00** | **$24** |

### Scenario B: Animated (10 videos/month, 5 min avg)

| Category | Monthly | Annual |
|----------|---------|--------|
| Electricity | $5.00 | $60 |
| Remotion license | $0 | $0 |
| **Total** | **$5.00** | **$60** |

### Scenario C: Hybrid with Cloud AI (5 videos/month, 10 min avg)

| Category | Monthly | Annual |
|----------|---------|--------|
| Electricity | $3.00 | $36 |
| Cloud GPU (RunPod) | $15.00 | $180 |
| **Total** | **$18.00** | **$216** |

---

## 6. Cost Comparison: Build vs Buy

| Approach | Setup Cost | Monthly | Per Video (10 min) | Annual (20 videos) |
|----------|------------|---------|-------------------|-------------------|
| **OpenMontage (Local)** | $0 (owned HW) | $2-5 | $0.10-1.00 | $24-60 |
| **OpenMontage + Cloud GPU** | $0 | $15-30 | $0.50-3.00 | $180-360 |
| **HeyGen / Synthesia** | $0 | $29-89 | $3-15 | $348-1068 |
| **Runway Gen-3** | $0 | $15-95 | $5-20 | $600-2400 |
| **Traditional Production** | $5000+ | N/A | $500-5000 | $10,000-100,000 |
| **Freelance Animator** | N/A | N/A | $500-2000 | $10,000-40,000 |

**OpenMontage Local is 100-1000x cheaper than alternatives.**

---

## 7. Break-Even Analysis

### vs HeyGen ($29/mo Creator plan)

| Metric | OpenMontage | HeyGen |
|--------|-------------|--------|
| Monthly cost | $2-5 | $29 |
| Annual savings | - | **$288-324** |
| Break-even | Immediate | N/A |

### vs Freelance ($500/video)

| Videos/year | OpenMontage | Freelance | Savings |
|-------------|-------------|-----------|---------|
| 12 | $24-60 | $6,000 | **$5,940-5,976** |
| 24 | $24-60 | $12,000 | **$11,940-11,976** |
| 52 | $24-60 | $26,000 | **$25,940-25,976** |

---

## 8. Cost Optimization Strategies

1. **Use quantized models (GGUF Q4)** - 50% VRAM reduction, minimal quality loss
2. **Cache all model downloads** - Avoid re-downloading (HuggingFace cache)
3. **Batch Remotion renders** - Reuse bundle cache, render multiple videos sequentially
4. **Use stock footage first** - Only generate AI video for shots unavailable in stock
5. **Ken Burns over AI video** - 100x faster, zero VRAM, acceptable for many shots
6. **Remotion Free License** - No cost for individuals/small teams
7. **Piper TTS local** - No per-character API costs (vs ElevenLabs $0.18/1000 chars)

---

## 9. Hidden Costs to Monitor

| Cost | Trigger | Estimate |
|------|---------|----------|
| **Storage growth** | Model cache + outputs | ~50GB/year → $10/year (NVMe) |
| **Electricity** | Heavy GPU usage | $2-10/month |
| **Hardware depreciation** | GPU wear | ~$50/year |
| **Time investment** | Learning curve | 40-80 hours initial |
| **Maintenance** | Dependency updates | 5-10 hours/month |

---

## 10. Summary

| Metric | Value |
|--------|-------|
| **Core Stack Monthly Cost** | **$0** |
| **Per Video (5 min cinematic)** | **$0.10** |
| **Per Video (5 min animated)** | **$0.25** |
| **Per Video (10 min hybrid cloud)** | **$0.66** |
| **Annual (20 videos cinematic)** | **$24** |
| **Annual (20 videos animated)** | **$60** |
| **vs HeyGen (annual)** | **Save $288+** |
| **vs Freelance (annual, 20 videos)** | **Save $10,000+** |

**Conclusion:** OpenMontage running locally on existing RTX 3050 hardware is **extremely cost-effective**. The entire production stack runs at near-zero marginal cost, with only electricity and minimal hardware depreciation as ongoing expenses.