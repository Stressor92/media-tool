# Internal: Logging System

## Scope

Logging is centralized in `src/utils/logging_config.py` and is designed for both:

- readable interactive CLI output, and
- optional structured or persistent logs for debugging batch runs

---

## Entry Point

`setup_logging(...)` is called from the global CLI callback in `src/cli/main.py` before domain logic runs.

It accepts:

- `verbose`
- `debug`
- `quiet`
- `log_file`
- `log_json`

and configures the root logger for the whole process.

---

## Level Resolution

The effective log level is resolved with a simple priority order:

1. `quiet` -> `WARNING`
2. `debug` -> `DEBUG`
3. `verbose` -> `INFO`
4. default -> `WARNING`

This keeps the CLI behavior predictable and avoids ambiguous flag interactions.

---

## Handler Strategy

### Console output

A `RichHandler` is always attached for human-readable terminal logs with:

- rich tracebacks
- concise formatting
- optional structured context appended to the message

### File output

When `log_file` is set, a `RotatingFileHandler` is added with:

- UTF-8 encoding
- `maxBytes = 5 MiB`
- `backupCount = 3`

This makes long batch runs inspectable without producing unbounded log growth.

---

## Human vs JSON formatting

Two formatters are defined:

### `ContextFormatter`

Appends structured context (when present) to a readable log line.

### `JsonFormatter`

Serializes each record as one JSON object with fields such as:

- timestamp
- level
- logger
- message
- module
- function
- line
- optional `context`
- optional exception information

This is useful for post-processing or external log ingestion.

---

## Context Propagation

`ContextAdapter` merges base context and per-call `extra={"context": ...}` payloads so callers can attach structured values like:

- file path
- provider name
- return code
- operation id

without formatting those details into the message string itself.

This keeps logs both readable and machine-friendly.

---

## Design Intent

Important design choices visible in the implementation:

- root handlers are cleared before reconfiguration so repeated CLI entrypoints stay deterministic
- third-party noise (`urllib3`, `httpx`) is suppressed unless debug mode is enabled
- the logging layer is reusable across all domains rather than being CLI-specific

The result is a pragmatic logging system that works well for both interactive use and postmortem analysis of automated media jobs.