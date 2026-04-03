"""
Hardware Encoder Support for media-tool (NVENC/AMF/QSV)

This documentation describes the new hardware encoding features added to media-tool's upscale system.

======================================================================
OVERVIEW
======================================================================

The upscale system now automatically detects and uses GPU hardware encoders when available:
- NVENC (NVIDIA GPUs) — fastest
- AMF (AMD GPUs)
- QSV (Intel Arc GPUs)
- Software fallback (libx265) — always available

Benefits:
- 4-10× faster encoding than software libx265
- Transparent automatic detection
- Automatic fallback if GPU encoding fails
- Zero configuration required for typical users
- Full control via CLI flags and config files for power users

======================================================================
QUICK START
======================================================================

1. DETECT YOUR HARDWARE

   media-tool upscale detect

   Output example:
   ┌────────────────┬─────────────────────┬──────────────────────┐
   │ Encoder        │ Status              │ Notes                │
   ├────────────────┼─────────────────────┼──────────────────────┤
   │ NVENC          │ ✓ available         │ NVIDIA GPU           │
   │ AMF            │ ✗ not found         │ AMD GPU              │
   │ QSV            │ ✗ not found         │ Intel GPU            │
   │ libx265        │ ✓ available         │ CPU fallback         │
   └────────────────┴─────────────────────┴──────────────────────┘

   Selected encoder: nvenc (hevc_nvenc)
   Detection time:   1.2 ms

   ✓ Hardware acceleration available!


2. UPSCALE A SINGLE FILE (AUTOMATIC GPU)

   media-tool upscale single movie.mkv --profile dvd-hq

   This automatically uses NVENC (or AMF/QSV if available) for fastest encoding.


3. LIST PROFILES AND ENCODING SPEEDS

   media-tool upscale profiles

   Shows which GPU encoder each profile will use and estimated speeds.


======================================================================
CONFIGURATION
======================================================================

In media-tool.toml:

[upscale]
encoder = "auto"              # "auto" | "nvenc" | "amf" | "qsv" | "software"
hw_fallback_on_error = true   # Retry with CPU if GPU fails
nvenc_max_vram_mb = 0         # 0 = unlimited (recommended)
nvenc_max_sessions = 2        # Consumer GPUs: max 3; use 2 to be safe
hw_probe_timeout_sec = 10     # Timeout for hardware detection

======================================================================
CLI FLAGS
======================================================================

media-tool upscale single|batch

  --encoder [auto|nvenc|amf|qsv|software]
      Which encoder to use. Default: "auto" (best available).
      Examples:
        media-tool upscale single movie.mkv --encoder nvenc
        media-tool upscale batch . --encoder software  # Force CPU

  --no-hw
      Disable hardware encoding completely.
      Examples:
        media-tool upscale single movie.mkv --no-hw

  --no-hw-fallback
      Don't automatically fall back to software if GPU encoding fails.
      The encode will fail instead if hardware fails.

Examples combining flags:

  # Force NVENC GPU encoding:
  media-tool upscale single movie.mkv --encoder nvenc

  # Force software encoding (useful for debugging):
  media-tool upscale single movie.mkv --encoder software

  # Or use --no-hw shorthand:
  media-tool upscale single movie.mkv --no-hw

  # Disable automatic fallback (strict mode):
  media-tool upscale batch cinema/ --no-hw-fallback

  # Batch upscale with logging:
  media-tool upscale batch cinema/ --profile dvd-hq --encoder auto

======================================================================
ENCODER SELECTION PRIORITY
======================================================================

When encoder="auto" (the default), the system chooses in this order:

1. NVENC (hevc_nvenc)   — NVIDIA GPUs (RTX 3xxx/4xxx, RTX A-series)
   CRF equivalent → Quality comparable to libx265 -crf faster encoding
   Fastest, most widely available

2. AMF (hevc_amf)       — AMD Radeon GPUs
   Different QP scale; quality settings adapted per profile
   Good speed/quality balance

3. QSV (hevc_qsv)       — Intel Arc GPUs
   Rarely available in consumer systems
   Would be used if NVENC/AMF unavailable

4. libx265 (software)   — CPU fallback (always works)
   Standard H.265 encoding, ~0.3-1.5× realtime
   Used if no GPU available or --no-hw specified

======================================================================
PROFILE × ENCODER MAPPING
======================================================================

Each profile (dvd-fast, dvd-hq, etc.) has encoder-specific parameters:

PROFILE        NVENC           AMF             QSV             libx265
──────────────────────────────────────────────────────────────────────
dvd-fast       p3/cq26         speed/qp28-30   veryfast/cq26   crf26/medium
dvd-balanced   p5/cq24         balanced/qp26-28 medium/cq24   crf24/slow
dvd-hq         p7/cq22         quality/qp24-26 veryslow/cq22  crf22/slow
archive        p7/cq20         quality/qp22-24 veryslow/cq20  crf18/veryslow
anime          p5/cq23         balanced/qp25-27 medium/cq23   crf23/slow
1080p          p5/cq23         balanced/qp25-27 medium/cq23   crf23/medium
jellyfin       p5/cq24         balanced/qp26-28 medium/cq24   crf24/slow

Higher quality = slower encoding. Estimated encoding speed:

ENCODER         dvd-fast        dvd-balanced    dvd-hq          archive
────────────────────────────────────────────────────────────────────
NVENC RTX 3080  ~4× real-time   ~2.5× RT        ~1.5× RT        ~1× RT
AMF (RX 6700)   ~3× real-time   ~2× real-time   ~1.2× RT        ~0.8× RT
QSV (Arc A770)  ~2× real-time   ~1.5× RT        ~1× real-time   ~0.5× RT
libx265 (CPU)   ~1× real-time   ~0.6× RT        ~0.3× RT        ~0.1× RT

(Actual speeds vary by GPU model, CPU, and input resolution)

======================================================================
HARDWARE FALLBACK ON ERROR
======================================================================

If you enable hw_fallback_on_error=true (default), and GPU encoding fails
at runtime (e.g., GPU out of memory), the system:

1. Logs a warning: "Hardware encoder (nvenc) failed, retrying with libx265"
2. Cleans up the partial output file
3. Retries with software encoding (libx265)

This ensures upscaling completes even if GPU runs into memory limit.

Example log output:
  [upscaler] WARNING: movie.mkv — Hardware encoder (nvenc) failed (exit 1)
  [upscaler] Retrying with libx265 software encoder
  [upscaler] Done in 1234.5s. 3.000GB → 1.250GB (Δ 1.750GB)

To disable fallback:
  --no-hw-fallback

Then GPU encode failures are reported as upscale failures (exit code 1).

======================================================================
TROUBLESHOOTING
======================================================================

Q: detect command says "NVENC not found" but I have an NVIDIA GPU.

A: Check:
   1. NVIDIA drivers installed: nvidia-smi
   2. ffmpeg compiled with NVENC support:
      ffmpeg -hide_banner -encoders | grep nvenc
   3. Check for driver issues:
      media-tool upscale detect --force

   If NVENC is listed in -encoders but probe fails, the GPU driver may
   not be accessible (e.g., WSL2 without GPU passthrough).


Q: Upscaling used GPU once but failed on second encode.

A: NVIDIA consumer GPUs allow only 3 concurrent NVENC sessions by design.
   With multiple workers or batch jobs, the 4th encode hits this limit and
   falls back to CPU.

   Solution:
   [upscale]
   nvenc_max_sessions = 2    # Reduce from 3 to safe value

   Or use --no-hw to disable GPU when batch processing.


Q: Ambiguous encoder state (ffmpeg says encoder exists but probe fails).

A: Run:
   media-tool upscale detect --force

   If it fails with a timeout:
   [upscale]
   hw_probe_timeout_sec = 20    # Increase from 10 to 20


Q: I want CPU-only encoding (no GPU).

A: Use --no-hw flag:
   media-tool upscale single movie.mkv --no-hw

   Or config:
   [upscale]
   encoder = "software"


Q: GPU encodes are slower than expected!

A: Check:
   1. Is GPU actually being used?
      media-tool upscale detect

   2. Check ffmpeg command with high verbosity:
      Add -v debug to see encoder selection

   3. GPU memory shortage? Reduce quality:
      media-tool upscale single movie.mkv --profile dvd-fast

   4. Profile mismatch? Ensure profile exists:
      media-tool upscale profiles

======================================================================
KNOWN LIMITATIONS
======================================================================

NVIDIA Consumer GPUs (RTX 3xxx/4xxx):
- Max 3 concurrent NVENC sessions (driver limit on consumer hardware)
- Professional cards (A100, RTX 6000) allow up to 128 sessions
- Workaround: --workers 2 or nvenc_max_sessions=2

AMD Radeon + Linux:
- Requires ROCm drivers (not AMDGPU drivers alone)
- WSL2: GPU passthrough needed
- Fix: Install ROCm: https://rocmdocs.amd.com/

Intel Arc:
- Linux support via oneAPI compute runtime
- Windows: driver updates frequently improve stability

HDR/10-bit:
- NVENC/AMF/QSV support 10-bit encoding
- Currently mapped to 8-bit yuv420p; 10-bit support planned in Phase 2

======================================================================
ARCHITECTURE
======================================================================

Components:

1. HardwareDetector (hardware_detector.py)
   - Stage 1: Check ffmpeg -encoders for codec availability
   - Stage 2: Run probe encode to validate GPU accessibility
   - Caches results (clear with detect --force)

2. EncoderProfileBuilder (encoder_profile_builder.py)
   - Maps profiles (dvd-hq, etc.) → encoder-specific parameters
   - Translates profile names to NVENC presets, AMF QP values, etc.
   - Handles preferred encoder and force_software fallback

3. Upscaler Integration (upscaler.py)
   - _build_encoder_args(): Builds ffmpeg args using builder
   - Hardware fallback: Retries with libx265 if GPU fails
   - Compatible with existing UpscaleOptions

4. CLI (upscale_cmd.py)
   - detect subcommand: Shows available encoders
   - --encoder flag: Choose specific encoder
   - --no-hw / --no-hw-fallback: Override defaults

5. Config (config.py, media-tool.toml)
   - UpscaleConfig: Persistent encoder settings
   - Per-project encoder preference and fallback policy

======================================================================
NOT-BREAKING CHANGES
======================================================================

All existing workflows remain unchanged:
- upscale_dvd(source, target, opts) works as before
- UpscaleOptions maintains all existing fields
- Default behavior: auto-detect GPU if available, fall back to CPU

To stay on CPU (old behavior):
- Set encoder="software" (CLI/config)
- Or use --no-hw flag

This ensures:
- Existing scripts don't break
- GPU benefits are opt-in by default
- Full backward compatibility

======================================================================
MEASUREMENT & METRICS
======================================================================

To measure hardware encoder performance:

    # Measure GPU encoding
    time media-tool upscale single movie.mkv --encoder nvenc --profile dvd-hq
    # Compare with CPU encoding
    time media-tool upscale single movie.mkv --encoder software --profile dvd-hq

Expected result on RTX 3080 + Input 3GB 480p DVD:
    GPU (NVENC): ~300 seconds (1.5× realtime)
    CPU (libx265): ~1200 seconds (0.3× realtime)
    Speedup: ~4×

Logging for analytics:

    [upscaler] Selected encoder: hevc_nvenc (profile=dvd-hq → p7/cq22)
    [upscaler] Starting upscale: movie.mkv → movie - [DVD].mkv
    [upscaler] Encoder: nvenc (hardware: yes)
    [upscaler] Done in 305.2s. 3.000GB → 1.250GB (Δ 1.750GB)

Parse logs to track:
- GPU vs CPU encoding ratio
- Average performance per GPU model
- Failure rates and fallback frequency

======================================================================
FUTURE ENHANCEMENTS (Phase 2)
======================================================================

- 10-bit/HDR support (yuv420p10le)
- Multi-GPU distribution
- GPU memory management tuning
- Per-codec encoder selection (H.264 nvenc_h264, VP9 encoders, etc.)
- Batch GPU session queuing
- Performance profiling and auto-tuning
"""
