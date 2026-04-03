# Design Decision: Upscaling Profiles and Hardware Selection

## Context

Video processing must run across machines with different acceleration capabilities and varying source quality tiers (DVD-like vs Blu-ray-like).

## Decision

Use profile-driven encoding settings combined with runtime hardware detection.

Implementation anchors:

- `upscale_profiles` defines policy bundles
- `hardware_detector` selects available acceleration mode
- `encoder_profile_builder` generates ffmpeg args from profile + hardware

## Rationale

- Keeps high-level workflow logic stable
- Avoids hardcoding one encoder path
- Enables graceful fallback to software encode

## Consequences

Positive:

- Better portability across hosts
- Cleaner separation between policy and execution
- Easier tuning by editing profile definitions

Negative:

- More moving parts to debug
- Profile defaults may not fit all content types equally

## Alternatives Considered

- Single static ffmpeg command template
- Manual per-machine config only

These were rejected due to poor portability and maintenance overhead.
