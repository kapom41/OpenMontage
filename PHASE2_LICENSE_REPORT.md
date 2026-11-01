# Phase 2 License Verification Report

**Date:** 2026-10-31  
**Sources accessed:** 2026-10-31

---

## 1. Core Production Tools

### 1.1 Remotion (Video Composition Framework)

| Aspect | Details |
|--------|---------|
| **Version** | 4.0.484 (current in package.json) |
| **License** | Source-available / Dual license |
| **Free License Eligibility** | Individuals, orgs ≤3 people, non-profits, evaluation |
| **Company License Required** | For-profit orgs >3 people |
| **Commercial Use** | ✅ Allowed under Free License for eligible entities |
| **Automation Use** | ✅ Allowed under Free License for eligible entities |
| **Company License Options** | • Remotion for Creators: $25/seat/month<br>• Remotion for Automators: $0.01/render, $100/mo minimum |
| **Source** | https://www.remotion.dev/license (accessed 2026-10-31) |

**Verdict for OpenMontage:** As an individual developer / small team project, **Free License applies**. Commercial use and automation are permitted.

---

### 1.2 Stable Diffusion 1.5 (Image Generation)

| Aspect | Details |
|--------|---------|
| **Model ID** | runwayml/stable-diffusion-v1-5 |
| **License** | OpenRAIL-M |
| **Commercial Use** | ✅ Allowed |
| **Attribution** | Not required for generated images |
| **Restrictions** | Cannot use for illegal/harmful content; cannot claim ownership of model |
| **Source** | https://huggingface.co/runwayml/stable-diffusion-v1-5 (accessed 2026-10-31) |

**Verdict:** ✅ **PRODUCTION READY** - Commercial use permitted.

---

### 1.3 CogVideoX-2B (Video Generation)

| Aspect | Details |
|--------|---------|
| **Model ID** | THUDM/CogVideoX-2b (Apache 2.0) |
| **License** | Apache 2.0 (model weights + code) |
| **Commercial Use** | ✅ Allowed with registration |
| **Registration Required** | Yes - https://open.bigmodel.cn/mla/form |
| **Usage Limit** | ≤1M service users/month (basic commercial license) |
| **Attribution** | Copyright notice required |
| **Source** | https://huggingface.co/THUDM/CogVideoX-2b (accessed 2026-10-31) |

**Important:** The CogVideoX-5B model has a **different, more restrictive license** (CogVideoX LICENSE). Only the 2B model is Apache 2.0.

**Verdict:** ✅ **USABLE** - Requires free registration for commercial use.

---

### 1.4 Wan 2.1 (Video Generation)

| Aspect | Details |
|--------|---------|
| **Model ID** | Wan-AI/Wan2.1-T2V-1.3B-Diffusers |
| **License** | Apache 2.0 |
| **Commercial Use** | ✅ Allowed |
| **Attribution** | Copyright notice required |
| **Restrictions** | No illegal/harmful content; no misinformation; no targeting vulnerable populations |
| **Source** | https://github.com/Wan-Video/Wan2.1 (accessed 2026-10-31) |

**Verdict:** ✅ **PRODUCTION READY** - Apache 2.0, commercial use permitted.

---

### 1.5 Piper TTS (Text-to-Speech)

| Aspect | Details |
|--------|---------|
| **Package** | piper-tts (PyPI) |
| **Original Repo** | rhasspy/piper (MIT License) |
| **Active Repo** | OHF-Voice/piper1-gpl (GPL-3.0) |
| **License Conflict** | MIT (frozen) vs GPL-3.0 (active) |
| **Piper Code** | MIT (rhasspy/piper) |
| **espeak-ng dependency** | GPL (dynamic linking) |
| **Voice Models** | Various (LibriTTS: CC BY, others vary) |
| **Commercial Use** | ✅ Allowed under MIT; GPL-3.0 requires source distribution if shipping binary |
| **Source** | https://github.com/rhasspy/piper (accessed 2026-10-31) |

**Critical:** The pipi-tts PyPI package resolves to the **MIT-licensed rhasspy/piper** (frozen). The active development is under GPL-3.0 at OHF-Voice/piper1-gpl.

**Verdict for OpenMontage:** Using `pip install piper-tts` → **MIT License applies** → ✅ Commercial use permitted, no source distribution required for SaaS/local use.

---

### 1.6 FFmpeg (Video Processing)

| Aspect | Details |
|--------|---------|
| **License** | LGPL v2.1+ (core), GPL v2+ (optional parts) |
| **Build Used** | Gyan.dev "essentials_build" (LGPL + GPL parts) |
| **Commercial Use** | ✅ Allowed |
| **Distribution Requirements** | • Dynamic linking to DLLs<br>• Provide FFmpeg source code<br>• No static linking of GPL parts (libx264, libx265)<br>• Mention FFmpeg in about box |
| **GPL Parts in Gyan Build** | libx264, libx265, various filters |
| **Source** | https://ffmpeg.org/legal.html (accessed 2026-10-31) |

**Verdict:** ✅ **USABLE** - Use dynamic linking, provide source, avoid static linking of GPL parts. Gyan build includes libx264/libx265 (GPL) - ensure dynamic linking.

---

## 2. Animation & Graphics Libraries

### 2.1 GSAP (Animation Library)

| Aspect | Details |
|--------|---------|
| **Version** | 3.15.0+ |
| **License** | Standard "No Charge" License (Webflow) |
| **Commercial Use** | ✅ **100% FREE** including all plugins |
| **Plugins Included Free** | SplitText, MorphSVG, DrawSVG, MotionPath, Flip, Draggable, Inertia, ScrollTrigger, ScrollSmoother, Observer, CustomEase, TextPlugin, etc. |
| **Restrictions** | Cannot build visual animation builder competing with Webflow |
| **Source** | https://gsap.com/community/standard-license/ (accessed 2026-10-31) |

**Verdict:** ✅ **PRODUCTION READY** - Fully free for commercial use.

---

### 2.2 Three.js (3D Graphics)

| Aspect | Details |
|--------|---------|
| **Version** | 0.187.0 (current npm) |
| **License** | MIT |
| **Commercial Use** | ✅ Allowed |
| **Attribution** | Copyright notice required |
| **Source** | https://github.com/mrdoob/three.js (accessed 2026-10-31) |

**Verdict:** ✅ **PRODUCTION READY** - MIT license, commercial use permitted.

---

### 2.3 Blender (3D Creation Suite)

| Aspect | Details |
|--------|---------|
| **Version** | 4.5 LTS (recommended) |
| **License** | GPL v3+ |
| **Commercial Use** | ✅ **Allowed** - "Your artwork is your sole property" |
| **Blender Code** | GPL - only applies if distributing modified Blender |
| **Python Scripts/Add-ons** | Must be GPL-compatible if distributed |
| **Rendered Output** | **Your property** - no restrictions |
| **Source** | https://www.blender.org/about/license/ (accessed 2026-10-31) |

**Verdict:** ✅ **PRODUCTION READY** - Rendered content is fully yours. Only Blender modifications trigger GPL.

---

## 3. Stock Video Sources

| Source | License | Commercial | Attribution | Notes |
|--------|---------|------------|-------------|-------|
| **Wikimedia Commons** | CC BY / CC BY-SA / Public Domain | ✅ | Required for CC BY/SA | Verify per-file |
| **NASA** | Public Domain (with caveats) | ✅ | "Courtesy NASA" recommended | No endorsement implied |
| **ESA** | CC BY-SA 3.0 IGO | ✅ | Required | Attribution + license link |
| **Mixkit** | Mixkit License | ✅ | Not required | Free commercial, no attribution |
| **Pexels** | Pexels License | ✅ | Not required | 200 req/hour free tier |
| **Pixabay** | Pixabay License | ✅ | Not required | Free tier available |

**Verdict:** ✅ **Multiple sources available** without API keys (Wikimedia, NASA, ESA, Mixkit).

---

## 4. Python Ecosystem

| Package | License | Commercial |
|---------|---------|------------|
| torch / torchvision | BSD-3-Clause | ✅ |
| diffusers | Apache 2.0 | ✅ |
| transformers | Apache 2.0 | ✅ |
| accelerate | Apache 2.0 | ✅ |
| safetensors | Apache 2.0 | ✅ |
| fastapi | MIT | ✅ |
| pydantic | MIT | ✅ |
| pillow | HPND (MIT-like) | ✅ |
| numpy / scipy | BSD-3-Clause | ✅ |
| requests | Apache 2.0 | ✅ |
| playwright | Apache 2.0 | ✅ |

---

## 5. License Compliance Checklist for OpenMontage

### 5.1 Must Do
- [ ] Include FFmpeg LGPL/GPL notices in distribution
- [ ] Provide FFmpeg source code (or link to exact version)
- [ ] Include Apache 2.0 notices for diffusers, transformers, Wan, CogVideoX
- [ ] Register CogVideoX for commercial use (if using)
- [ ] Verify per-asset licenses for stock footage used
- [ ] Include MIT/BSD notices for Python dependencies

### 5.2 Should Do
- [ ] Attribute NASA/ESA footage ("Courtesy NASA", "ESA/CC BY-SA 3.0 IGO")
- [ ] Include GSAP license notice (though not strictly required)
- [ ] Document voice model licenses used (Piper voices)

### 5.3 Not Required
- [ ] Remotion Free License registration (eligible as individual/small team)
- [ ] Piper TTS source distribution (using MIT-licensed PyPI package)
- [ ] Blender GPL compliance (output is your property)

---

## 6. Risk Assessment

| Risk | Likelihood | Impact | Mitigation |
|------|------------|--------|------------|
| CogVideoX commercial registration denied | Low | Medium | Use Wan 2.1 instead (Apache 2.0, no registration) |
| FFmpeg GPL static linking | Medium | High | Use dynamic linking (Gyan build uses DLLs) |
| Piper voice model license unclear | Low | Low | Use LibriTTS voices (CC BY) |
| Stock footage license change | Low | Medium | Cache license at download time |
| Remotion license change | Low | High | Pin version; monitor remotion.dev/license |

---

## 7. Summary

| Category | Status |
|----------|--------|
| **Video Composition (Remotion)** | ✅ Free License eligible |
| **Image Generation (SD 1.5)** | ✅ OpenRAIL-M |
| **Video Generation (Wan 2.1)** | ✅ Apache 2.0 |
| **Video Generation (CogVideoX-2B)** | ✅ Apache 2.0 + registration |
| **TTS (Piper)** | ✅ MIT (PyPI package) |
| **Video Processing (FFmpeg)** | ✅ LGPL (dynamic linking) |
| **Animation (GSAP)** | ✅ Free commercial |
| **3D Graphics (Three.js)** | ✅ MIT |
| **3D Creation (Blender)** | ✅ GPL (output unrestricted) |
| **Stock Footage** | ✅ Multiple free sources |

**Overall:** **All core technologies cleared for commercial production use** with standard open-source compliance practices.