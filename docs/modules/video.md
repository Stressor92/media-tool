# Video Module

## Scope

The video domain handles file inspection, container conversion, duplicate-language merge operations, upscaling/re-encoding, and profile-driven encoding decisions.

## Main Components

- `converter`: format conversion and remux operations
- `merger`: stream-level merge and duplicate handling flows
- `inspector`: ffprobe-based media inventory extraction
- `upscaler`: upscale + encode operations
- `upscale_profiles`: profile registry and policy selection
- `hardware_detector`: capability probing (NVENC/AMF/QSV/software)
- `encoder_profile_builder`: turns profile decisions into ffmpeg arguments

## Processing Model

Video operations generally follow:

1. Probe source streams/metadata.
2. Select operation mode/profile.
3. Build ffmpeg argument list.
4. Execute via wrapper.
5. Validate outputs and return typed result.

The module is designed for deterministic transformation steps, with hardware acceleration selected opportunistically.

## Profile and Hardware Selection

Upscale behavior is profile-based rather than a monolithic settings block.

Implications:

- Profile definitions become stable design artifacts.
- Hardware detector can substitute encoders without changing higher-level pipeline logic.
- Same command can run on heterogeneous machines with best-available acceleration.

Trade-off:

- More indirection and profile complexity
- Better portability and operational resilience

## Integration Points

- Workflow steps `s01` to `s04` call merge/remux/upscale/re-encode behavior.
- Uses `utils.ffmpeg_runner` and `utils.ffprobe_runner` heavily.
- Backup can wrap destructive overwrites in caller layers.

## Failure Characteristics

Typical failures:

- Encoder unavailable on host
- Incompatible stream layout for copy/remux path
- Corrupt source media

Returned results usually include stderr/error details, enabling caller-level retry or fallback decisions.
