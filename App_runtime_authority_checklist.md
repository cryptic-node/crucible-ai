# App Runtime Authority Checklist

## Current state
- `grok` already points at `app.cli.main:main`
- `grok-legacy` still points at `src.main:main`
- wheel packaging still includes both `src` and `app`
- README still contains old `src` quick-start material

## Recommended changes for v1.0.1
1. Keep:
   - `grok = "app.cli.main:main"`

2. Keep temporarily, but mark deprecated:
   - `grok-legacy = "src.main:main"`

3. Update README:
   - remove or quarantine old `python -m grokenstein.src.main ...` examples
   - keep one authoritative quick-start based on `python -m app.cli.main ...` or `grok ...`

4. Freeze `src/`:
   - no new features
   - compatibility adapters only
   - startup warning when legacy CLI is used

5. Package cleanup target:
   - v1.0.1: ship both, deprecate `src`
   - v1.0.2 or v1.1.0: stop shipping `src` in wheel if migrations are complete

## Suggested pyproject end-state
```toml
[project.scripts]
grok = "app.cli.main:main"

[tool.hatch.build.targets.wheel]
packages = ["app"]
```
