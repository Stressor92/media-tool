# Design Decision: Upscaling Strategy

## Problem

The project needs to process heterogeneous legacy video sources ranging from DVD rips to Blu-ray/remux material while preserving quality, controlling file size, and staying compatible with different host machines.

The system therefore has to answer several questions:

- when should a file be upscaled vs merely re-encoded?
- how should quality be controlled?
- how can the same command run on machines with and without GPU encoders?

---

## Options Considered

### Option A — fixed one-size-fits-all ffmpeg command

**Pros**
- simple to understand
- minimal branching

**Cons**
- poor fit for mixed source quality
- hard to tune for different workloads
- no clean way to adapt to hardware capabilities

### Option B — fully ad hoc per-command flags everywhere

**Pros**
- maximum flexibility

**Cons**
- poor repeatability
- too much policy exposed at the CLI boundary
- hard to keep consistent across machines and workflows

### Option C — named profiles plus hardware detection (**chosen**)

**Pros**
- repeatable defaults with room for override
- portable across machines with different encoder support
- easy to document and reason about operationally

**Cons**
- more indirection than a single command
- profile sprawl must be managed carefully

---

## Chosen Solution

The current implementation uses:

- **named profiles** in `core.video.upscale_profiles`
- **opportunistic hardware detection** in `core.video.hardware_detector`
- **CRF-based H.265 encoding** as the main quality-control mechanism

### Why CRF-based H.265?

The code favors `libx265`/HEVC-compatible encoders because the target environment is media-library storage rather than broadcast mastering. CRF provides a better storage/quality trade-off than rigid bitrate targets for this use case.

### Why profiles?

Profiles such as `dvd`, `dvd-hq`, `dvd-fast`, `jellyfin`, `anime`, and `archive` encode project policy directly:

- default quality level
- speed/quality trade-off
- target resolution
- filter-chain strength
- crop/deinterlace behavior

### Why GPU fallback rather than GPU-only?

`HardwareDetector` first checks whether encoders are listed and then performs a real probe encode. If no validated hardware encoder is available, the code falls back to software.

This avoids making the pipeline brittle on machines without a usable GPU path.

---

## Trade-offs

| Decision | Benefit | Cost |
|---|---|---|
| HEVC over always using AVC | smaller library footprints for similar visual quality | slower software encodes and broader compatibility considerations |
| profile-based settings | repeatable operational behavior | more configuration surface to maintain |
| hardware opportunism | faster runs when GPUs are available | extra detection logic and fallback complexity |
| conservative crop heuristics | lower risk of content loss | may leave some black bars untrimmed |

---

## Future Considerations

If this subsystem evolves, likely areas are:

- making profile selection more explicit in higher-level workflows
- extending validation rules per source class
- documenting host-specific playback compatibility constraints

Any future change should preserve the current priorities: **batch safety, repeatability, and graceful fallback**.