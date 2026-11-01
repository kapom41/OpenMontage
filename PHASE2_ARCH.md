# Phase 2 Architecture Proposal

**Date:** 2026-10-31  
**Status:** Based on validated benchmarks and license research

---

## 1. Recommended Production Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    MASTER ORCHESTRATOR                           │
│  Single Prompt → Full Production → YouTube Ready                │
└─────────────────────────────────────────────────────────────────┘
                              │
        ┌─────────────────────┼─────────────────────┐
        ▼                     ▼                     ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│  RESEARCH     │     │  CREATIVE     │     │  YOUTUBE      │
│  AGENT (NEW)  │     │  DIRECTOR     │     │  STRATEGY     │
│               │     │  (ENHANCED)   │     │  (NEW)        │
└───────────────┘     └───────────────┘     └───────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              ANIMATION DIRECTOR (NEW)                            │
│  Script → Scene Visual Plan → Asset Assignment                  │
└─────────────────────────────────────────────────────────────────┘
        │                     │                     │
        ▼                     ▼                     ▼
┌───────────────┐     ┌───────────────┐     ┌───────────────┐
│ CHARACTER     │     │ MOTION        │     │ 3D / ENV      │
│ ANIMATION     │     │ GRAPHICS      │     │ (ThreeJS/     │
│ (SVG/GSAP)    │     │ (Remotion)    │     │  Blender)     │
└───────────────┘     └───────────────┘     └───────────────┘
        │                     │                     │
        └─────────────────────┼─────────────────────┘
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│              COMPOSITION ENGINE                                  │
│  HyperFrames (primary) / Remotion (motion graphics) /           │
│  FFmpeg (video concat + Ken Burns fallback)                     │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  QC → MONETIZATION SAFETY → LICENSE CHECK → USER APPROVAL       │
│  → YOUTUBE PUBLISHER → ANALYTICS → CREATIVE MEMORY              │
└─────────────────────────────────────────────────────────────────┘
```

---

## 2. Technology Decisions

| Layer | Choice | Rationale |
|-------|--------|-----------|
| **2D Characters** | SVG + GSAP + HyperFrames | Zero VRAM, deterministic, editable, exports to HyperFrames |
| **Motion Graphics** | Remotion components | Already built (charts, stat cards, callouts, text cards) |
| **3D Environments** | ThreeJSWorld (procedural) + Blender (hero assets) | ThreeJS for web-exportable scenes; Blender for production quality |
| **AI Video Gen** | Wan 2.1 1.3B GGUF Q4 (optional) | Only model fitting 4GB VRAM; deferred as enhancement |
| **TTS** | Piper TTS (local) | MIT license, prosody control, zero API cost |
| **Composition** | HyperFrames primary | HTML/CSS/GSAP runtime, frame-accurate, deterministic |
| **Fallback Video** | FFmpeg Ken Burns | CPU-only, <1s per clip, production ready |

---

## 3. New Agents to Implement

| Agent | Purpose | Priority |
|-------|---------|----------|
| `ResearchAgent` | Fact-checking, source citation, claim verification | HIGH |
| `AnimationDirector` | Script → scene visual mapping, asset type selection | HIGH |
| `MonetizationSafetyAgent` | YouTube policy compliance, risk scoring | HIGH |
| `LicenseManager` | Per-asset license tracking, validation | HIGH |
| `YouTubePublisher` | OAuth, resumable upload, metadata, Analytics | HIGH |
| `CharacterConsistencyEngine` | Cross-scene character ID, rigging, expressions | MEDIUM |
| `VideoReferenceAgent` | Reference video analysis → production blueprint | MEDIUM |

---

## 4. Integration Points

| Existing Component | Integration |
|-------------------|-------------|
| `ViralCinematicRunner` | Wrap as `CinematicPipeline` class; add `AnimatedPipeline` |
| `CharacterRigRenderer` | Connect to AnimationDirector output |
| `Remotion components` | Use for all motion graphics (charts, stats, callouts) |
| `Stock video sources` | Enable Wikimedia/NASA/ESA/Mixkit (uncomment in local_visual_gen) |
| `CreativeMemory` | Feed Analytics data back to CreativeDirector |
| `QualityControl` | Add animation-specific checks (character consistency, motion type) |

---

## 5. Phase 3+ Development Roadmap

### Phase 3: Core Animated Pipeline (Week 1-2)
- [ ] Implement `AnimationDirector` agent
- [ ] Connect `CharacterRigRenderer` to pipeline
- [ ] Wire Remotion motion graphics into composition
- [ ] Enable stock video sources
- [ ] Fix hardcoded Kodak content in creative_director.py + script_writer.py
- [ ] Increase duration cap to 1800s (30 min)

### Phase 4: Safety & Compliance (Week 2-3)
- [ ] Implement `MonetizationSafetyAgent`
- [ ] Implement `LicenseManager`
- [ ] Implement `ResearchAgent`
- [ ] Add monetization checks to QC pipeline

### Phase 5: Publishing & Learning (Week 3-4)
- [ ] Implement `YouTubePublisher` with OAuth
- [ ] Add YouTube Analytics integration
- [ ] Implement `MasterProductionOrchestrator` (single prompt entry)
- [ ] Connect CreativeMemory feedback loop

### Phase 6: Enhancement (Optional)
- [ ] Download/test Wan 2.1 1.3B GGUF Q4
- [ ] Install Blender 4.5 LTS
- [ ] Implement `VideoReferenceAgent`
- [ ] Implement `CharacterConsistencyEngine`

---

## 6. Key Technical Fixes Needed

| Issue | File | Fix |
|-------|------|-----|
| Hardcoded Kodak content | `creative_director.py:302-373`, `script_writer.py:228-237` | Remove conditional; use generic templates |
| 600s duration cap | `viral_cinematic_runner.py:110` | Change to 1800s |
| Stock video commented | `local_visual_gen.py:698-951` | Uncomment + integrate |
| Remotion bundle | `remotion-composer/` | Already installed; verify production render |

---

## 7. Production Modes

| Mode | Description | Status |
|------|-------------|--------|
| **Cinematic** | Stock footage + Ken Burns + narration | ✅ Working |
| **Animated** | SVG chars + Remotion graphics + TTS | ⚠️ Components ready, needs wiring |
| **Hybrid** | Both above + AI video generation | ❌ AI video blocked (models not downloaded) |

---

## 8. Cost Summary

| Scenario | Monthly Cost | Annual (20 videos) |
|----------|--------------|-------------------|
| Cinematic only | ~$2 | ~$24 |
| Animated | ~$5 | ~$60 |
| Hybrid (cloud AI) | ~$18 | ~$216 |

**All core stack: $0/month** (local hardware, open source licenses)

---

## 9. Acceptance Criteria for Phase 3

- [ ] Single prompt → 60s animated documentary with character
- [ ] Character appears in ≥3 scenes with consistent appearance
- [ ] Motion graphics (charts, stats) render via Remotion
- [ ] QC passes (technical + creative)
- [ ] Monetization safety report generated
- [ ] License manifest complete
- [ ] YouTube upload tested (private)
- [ ] Analytics webhook registered

---

**Next Step:** Begin Phase 3 with `AnimationDirector` implementation and Kodak content removal.