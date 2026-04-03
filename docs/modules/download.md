# Download Module

## Scope

The download domain provides search and retrieval orchestration for remote media sources, primarily through yt-dlp wrappers.

## Main Components

- `download_manager`: higher-level orchestration and policy
- `models`: typed results and request/response structures
- `utils.ytdlp_runner`: subprocess adapter to yt-dlp command execution

## Execution Model

Download operations generally:

1. Build a query or target URL.
2. Run yt-dlp command path through wrapper.
3. Parse success/failure output into typed model.
4. Return result to CLI or pipeline caller.

## Design Choices

Using a wrapper instead of inline subprocess calls centralizes:

- Error normalization
- Timeout/exit-code handling
- Command argument construction

Trade-off:

- Additional abstraction layer
- Better reliability and testability for command assembly

## Integration Points

- Used by download-focused CLI commands
- Can feed later conversion/workflow stages depending on command path
- Shares logging and configuration behavior with other utility-backed domains

## Failure Characteristics

Network/provider volatility is expected. The module treats many failures as operational outcomes, returning rich error context rather than hard process termination.
