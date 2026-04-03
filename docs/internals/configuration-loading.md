# Internals: Configuration Loading

## Scope

Configuration logic in `utils.config` resolves active settings from file sources and environment overrides, with legacy mapping support.

## Resolution Model

Typical order:

1. Discover candidate configuration file(s)
2. Parse and load structured settings
3. Apply environment variable overrides
4. Normalize and expose cached config objects

Exact precedence is implementation-dependent where multiple config locations coexist.

## Environment Override Behavior

The module supports direct environment overrides and legacy variable mappings. This allows gradual migration of config keys without immediate breakage.

## Caching and Invalidation

Configuration values are cached using cache keys tied to relevant inputs.

Benefits:

- Avoid repeated parse overhead
- Keep command startup responsive

Risk:

- Stale config if external mutation occurs without cache invalidation in long-lived process contexts

## Design Trade-off

A flexible merge model improves portability and backward compatibility, at the cost of higher complexity when diagnosing unexpected effective values.
