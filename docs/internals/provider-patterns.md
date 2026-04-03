# Internals: Provider Patterns and Interfaces

## Scope

Multiple domains use protocol/provider interfaces to isolate orchestration from concrete external backends.

## Key Interface Areas

- Subtitle providers (`subtitle_provider` contract)
- Translation backends (`translator_protocol`)
- Ebook metadata providers
- Ebook cover providers
- Audio metadata providers

## Architectural Benefits

- Backend swap without rewriting orchestration logic
- Easier testing via mock/fake implementations
- Better long-term maintainability for changing APIs

## Runtime Selection

Factory/service layers choose provider implementations based on configuration and environment availability.

## Trade-offs

- Additional abstraction layers can obscure concrete behavior during debugging.
- Capability mismatch between providers can force lowest-common-denominator feature sets in shared paths.

## Reliability Guidance

Caller code should treat provider outputs as probabilistic and validate confidence/completeness before writing durable metadata or performing destructive organization changes.
