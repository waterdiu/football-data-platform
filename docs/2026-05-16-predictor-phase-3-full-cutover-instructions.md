# Predictor Phase 3 Full Data-Layer Cutover Instructions

Date: 2026-05-16

## Purpose

This document is for the `world-cup-predictor` project.

Phase 1 made the predictor read `football-data-platform` first.
Phase 2 made the predictor write selected outputs into the platform inbox.
Phase 3 completes the ownership split:

- `football-data-platform` owns shared football data, runtime collection, public/model data publishing, health, and migration reports.
- `world-cup-predictor` owns model code, feature calculation, training, evaluation, and prediction generation.
- The predictor must not silently use old local production data when platform data is missing.

After Phase 3, the predictor should behave as:

```text
football-data-platform data/API
  -> world-cup-predictor model pipeline
  -> prediction outputs
  -> football-data-platform inbox
  -> platform validation/publish
```

## Current Platform Status

Platform repository:

- `/Users/chamcham/Documents/AI/CODEX/soccer/football-data-platform`

Public base URL:

- `https://waterdiu.github.io/football-data-platform`

Current platform endpoints:

- `https://waterdiu.github.io/football-data-platform/api/worldcup/2026/predictor/manifest.json`
- `https://waterdiu.github.io/football-data-platform/api/worldcup/2026/predictor/bundle.json`
- `https://waterdiu.github.io/football-data-platform/api/worldcup/2026/predictor/health.json`
- `https://waterdiu.github.io/football-data-platform/api/predictor/data-assets/manifest.json`
- `https://waterdiu.github.io/football-data-platform/api/predictor/data-assets/summary.json`
- `https://waterdiu.github.io/football-data-platform/api/migration-status.json`

Platform-owned World Cup runtime collectors now exist for:

- The Odds API odds snapshots
- API-FOOTBALL injuries
- API-FOOTBALL lineups
- OpenWeather weather
- Public-news prematch context

The platform collector entrypoint is:

```bash
python3 scripts/collect_world_cup_runtime_data.py
```

The platform publish/refresh entrypoint is:

```bash
python3 scripts/sync_predictor_runtime_inbox.py --skip-capture --collect-platform-runtime
```

## Required Predictor Behavior After Phase 3

### 1. Reads Must Be Platform-Strict In Production

Default behavior must be:

- Read from `football-data-platform`.
- If required platform data is missing, fail fast with a clear error.
- Do not silently fall back to `backend/data/...`.

Allowed fallback:

- Local fallback is allowed only when explicitly enabled for development or emergency rollback.
- The flag must be explicit:

```bash
FOOTBALL_DATA_PLATFORM_ALLOW_LOCAL_FALLBACK=1
```

If this variable is not set, fallback must be disabled.

Required error style:

```text
Missing required platform dataset: <dataset_name>
Checked:
- local platform path: <path>
- remote platform URL: <url>
Set FOOTBALL_DATA_PLATFORM_ALLOW_LOCAL_FALLBACK=1 only for local debugging or emergency rollback.
```

### 2. Runtime Data Collection Must Move Out Of The Predictor

The predictor should stop being the production owner for:

- World Cup odds collection
- World Cup injuries collection
- World Cup lineups collection
- World Cup weather collection
- World Cup prematch news/context collection

These jobs are now platform-owned.

Predictor scripts that currently collect these datasets should be changed to one of these states:

- Removed from production scheduled flows.
- Kept as local diagnostic tools only.
- Renamed or documented as legacy/manual probes.
- Blocked behind an explicit flag such as `--legacy-local-collector`.

The predictor should not write runtime datasets directly into platform normalized/model/public directories.
Only the platform writes:

- `football-data-platform/data/normalized`
- `football-data-platform/data/model`
- `football-data-platform/data/public`

### 3. Predictor May Still Write Prediction Outputs

The predictor should still generate model outputs.

Allowed predictor write path:

- `football-data-platform/data/inbox/predictor/...`

Do not write directly to:

- `football-data-platform/data/normalized`
- `football-data-platform/data/model`
- `football-data-platform/data/public`

World Cup prediction output:

- `data/inbox/predictor/worldcup-2026/predictions.json`

Premier League prediction output:

- `data/inbox/predictor/premier-league/predictions.json`

Optional compatibility local outputs may remain temporarily, but they must be documented as non-production artifacts.

## Data Contract

### Platform Input Contract Used By Predictor

Use the platform loader for these World Cup datasets:

- `shared_fixtures`
- `feature_inputs`
- `predictions_source`
- `fixtures`
- `results`
- `standings`
- `predictions`
- `data_coverage`
- `prematch_context`
- `odds_snapshots`
- `lineups`
- `injuries`
- `weather`

Preferred source:

- `api/worldcup/2026/predictor/bundle.json`

Health source:

- `api/worldcup/2026/predictor/health.json`

The predictor must check health before running production predictions.

Minimum required World Cup datasets for prediction generation:

- `feature_inputs`
- `shared_fixtures`
- `prematch_context`

Optional but recommended runtime enrichment:

- `odds_snapshots`
- `lineups`
- `injuries`
- `weather`

If optional runtime enrichment is missing, the predictor may still run, but the output metadata must lower confidence and record the missing datasets.

### Full Data Asset Contract

Use the platform data-assets manifest for historical/model training files:

- `api/predictor/data-assets/manifest.json`

The predictor should resolve old `backend/data/<relative_path>` inputs through the platform data asset loader.

Examples:

- `processed/training_features.csv`
- `processed/normalized_matches.csv`
- `processed/xg_matches.csv`
- `processed/player_ability.csv`
- `processed/premier_league_matches.csv`
- `processed/premier_league_matches_with_xg.csv`
- `processed/premier_league_training_features.csv`
- `processed/premier_league_2025_2026_fixtures.json`
- `processed/premier_league_predictions.json`
- `processed/world_cup_2026_fixtures.json`
- `processed/predictions.json`
- `raw/international_matches.csv`
- `raw/premier_league_xg.csv`
- `raw/fbref_premier_league_player_stats.csv`
- `raw/fbref_premier_league_team_match_stats.csv`
- `raw/transfermarkt_player_values.csv`
- `raw/premier_league/*.csv`
- `raw/understat/*`
- `raw/statsbomb_events/*.json`

## Required Environment Variables

Recommended local configuration:

```bash
FOOTBALL_DATA_PLATFORM_ROOT=/Users/chamcham/Documents/AI/CODEX/soccer/football-data-platform
FOOTBALL_DATA_PLATFORM_PUBLIC_BASE_URL=https://waterdiu.github.io/football-data-platform
FOOTBALL_DATA_PLATFORM_ASSET_MANIFEST_URL=https://waterdiu.github.io/football-data-platform/api/predictor/data-assets/manifest.json
FOOTBALL_DATA_PLATFORM_WC_PREDICTOR_MANIFEST_URL=https://waterdiu.github.io/football-data-platform/api/worldcup/2026/predictor/manifest.json
FOOTBALL_DATA_PLATFORM_WC_PREDICTOR_BUNDLE_URL=https://waterdiu.github.io/football-data-platform/api/worldcup/2026/predictor/bundle.json
FOOTBALL_DATA_PLATFORM_WC_PREDICTOR_HEALTH_URL=https://waterdiu.github.io/football-data-platform/api/worldcup/2026/predictor/health.json
FOOTBALL_DATA_PLATFORM_PREDICTOR_INBOX=data/inbox/predictor
FOOTBALL_DATA_PLATFORM_ALLOW_LOCAL_FALLBACK=0
```

Production/default rule:

- Treat missing `FOOTBALL_DATA_PLATFORM_ALLOW_LOCAL_FALLBACK` as disabled.
- Treat `FOOTBALL_DATA_PLATFORM_ALLOW_LOCAL_FALLBACK=0` as disabled.
- Only `FOOTBALL_DATA_PLATFORM_ALLOW_LOCAL_FALLBACK=1` enables fallback.

## Required Code Changes In `world-cup-predictor`

### A. Harden `backend/app/services/data_platform.py`

The existing loader should be upgraded to expose strict/optional reads.

Required functions or equivalent behavior:

```python
def platform_fallback_enabled() -> bool:
    ...

def require_json_asset(relative_path: str) -> object:
    ...

def require_csv_asset(relative_path: str) -> list[dict[str, str]]:
    ...

def load_world_cup_predictor_bundle(required: bool = True) -> dict:
    ...

def require_world_cup_predictor_dataset(name: str) -> object:
    ...

def optional_world_cup_predictor_dataset(name: str, default: object | None = None) -> object:
    ...

def validate_world_cup_predictor_health(required: list[str], optional: list[str]) -> dict:
    ...
```

Implementation rules:

- Required reads must fail if platform data is unavailable and fallback is disabled.
- Optional reads may return an empty list or configured default.
- All fallback use must be visible in logs or returned metadata.
- No model script should implement its own platform path/URL resolution.

### B. Remove Implicit Direct Reads From `backend/data`

Search for direct reads:

```bash
rg "backend/data|Path\\(.*data|DATA_DIR|processed/|raw/" backend
```

Change production reads to use `data_platform.py`.

Allowed direct local reads after Phase 3:

- Unit test fixtures.
- Temporary files.
- Model artifacts that are not shared input data.
- Explicit legacy/debug code paths documented as non-production.

### C. Stop Scheduled Runtime Collection In The Predictor

Review these scripts and services:

- `backend/scripts/run_scheduled_maintenance.py`
- `backend/scripts/probe_oddspapi_ah_coverage.py`
- `backend/scripts/capture_premier_league_context_snapshots.py`
- `backend/scripts/validate_world_cup_realtime_sources.py`
- any API-FOOTBALL context collection entrypoint
- any OpenWeather context collection entrypoint
- any prematch news/context scraping entrypoint

Required changes:

- Remove World Cup runtime collection from default scheduled maintenance.
- If the scripts remain, label them legacy/manual diagnostics.
- Do not run them automatically in production.
- Do not make them the source of truth for platform runtime datasets.

### D. Keep Prediction Generation And Write-Back

Prediction generation remains in the model project.

World Cup output still writes to:

```text
football-data-platform/data/inbox/predictor/worldcup-2026/predictions.json
```

Premier League output still writes to:

```text
football-data-platform/data/inbox/predictor/premier-league/predictions.json
```

The platform publish step remains platform-owned:

```bash
cd /Users/chamcham/Documents/AI/CODEX/soccer/football-data-platform
python3 scripts/publish_predictor_inbox.py
python3 scripts/import_world_cup_predictions.py
python3 scripts/publish_world_cup_predictor_api.py
python3 scripts/build_source_health_report.py
python3 scripts/build_migration_status.py
```

Prefer using the platform wrapper when appropriate:

```bash
python3 scripts/sync_predictor_runtime_inbox.py --skip-capture --collect-platform-runtime
```

## Required Script Behavior

### `generate_predictions.py`

Required:

- Load World Cup `feature_inputs` from the platform.
- Load runtime enrichment from platform bundle or model API.
- Fail if required datasets are missing.
- Continue to write prediction output to the platform inbox.

Recommended:

- Include `data_source.platform_status` in prediction metadata.
- Include `missing_optional_runtime_datasets` in prediction metadata.
- Include `runtime_confidence` or equivalent confidence downgrade if odds/injuries/lineups/weather are unavailable.

### `build_fixture_inputs.py`

Required:

- Use platform fixtures and shared team mappings as the source of truth.
- Do not regenerate canonical match IDs independently.
- Do not read stale local fixture files unless explicit fallback is enabled.

### Training Scripts

Required:

- Resolve historical CSV/JSON files through the platform asset manifest.
- Fail clearly if a required training asset is missing.

Allowed:

- Local fallback for development only with `FOOTBALL_DATA_PLATFORM_ALLOW_LOCAL_FALLBACK=1`.

### Storage/History Services

Required:

- Read predictions and historical datasets through the platform loader.
- Do not silently mix platform and local datasets in the same production run.

## Production Run Flow After Phase 3

### Platform Updates Runtime Data

Run in `football-data-platform`:

```bash
python3 scripts/sync_predictor_runtime_inbox.py --skip-capture --collect-platform-runtime
```

This should:

- Collect platform-owned runtime data.
- Publish existing predictor inbox files.
- Rebuild model datasets.
- Rebuild public World Cup predictor API.
- Refresh health and migration status.

### Predictor Generates Predictions

Run in `world-cup-predictor`:

```bash
python3 backend/scripts/generate_predictions.py
```

The script should:

- Read platform datasets.
- Generate predictions.
- Write prediction output to the platform inbox.

### Platform Publishes Prediction Output

Run in `football-data-platform`:

```bash
python3 scripts/sync_predictor_runtime_inbox.py --skip-capture
```

This should publish new predictor outputs without calling legacy predictor collectors.

## Acceptance Criteria

Phase 3 is complete only when all of these are true:

- `generate_predictions.py` succeeds with platform data and fallback disabled.
- `build_fixture_inputs.py` succeeds with platform data and fallback disabled.
- Training/evaluation scripts read required historical assets through the platform loader.
- Production scripts do not silently read `backend/data/...`.
- World Cup runtime collection is no longer run by predictor scheduled maintenance.
- Predictor writes World Cup predictions to platform inbox.
- Predictor writes Premier League predictions to platform inbox.
- If `football-data-platform` is unavailable, production prediction fails clearly.
- If optional runtime datasets are missing, prediction metadata records the missing datasets and confidence downgrade.
- Existing tests cover strict platform mode and explicit fallback mode.

Suggested verification commands in `world-cup-predictor`:

```bash
FOOTBALL_DATA_PLATFORM_ALLOW_LOCAL_FALLBACK=0 python3 backend/scripts/build_fixture_inputs.py
FOOTBALL_DATA_PLATFORM_ALLOW_LOCAL_FALLBACK=0 python3 backend/scripts/generate_predictions.py
FOOTBALL_DATA_PLATFORM_ALLOW_LOCAL_FALLBACK=0 python3 backend/scripts/build_features.py
FOOTBALL_DATA_PLATFORM_ALLOW_LOCAL_FALLBACK=0 python3 backend/scripts/train_models.py
FOOTBALL_DATA_PLATFORM_ALLOW_LOCAL_FALLBACK=0 python3 backend/scripts/generate_premier_league_predictions.py
pytest
```

If any command requires an old local file, that is a Phase 3 blocker unless the file is explicitly classified as a non-shared model artifact.

## Test Requirements

Add or update tests for:

- Platform strict mode succeeds when platform data exists.
- Platform strict mode fails when a required dataset is missing.
- Local fallback is disabled by default.
- Local fallback works only with `FOOTBALL_DATA_PLATFORM_ALLOW_LOCAL_FALLBACK=1`.
- `generate_predictions.py` records missing optional runtime datasets.
- Scheduled maintenance no longer runs World Cup runtime collectors by default.
- Prediction output is written to platform inbox.

## What Not To Do

Do not:

- Copy platform datasets back into `world-cup-predictor/backend/data` as a new production source.
- Add a second set of canonical team or match ID mappings in the predictor.
- Write directly to `football-data-platform/data/public`.
- Write directly to `football-data-platform/data/model`.
- Write directly to `football-data-platform/data/normalized`.
- Keep automatic World Cup runtime scraping in predictor scheduled maintenance.
- Hide platform failures by silently using stale local files.

## Compatibility Notes

During Phase 3, local compatibility outputs may remain if removing them is risky.
They must be documented as compatibility artifacts, not production data owners.

Recommended classification:

- `backend/data` input files: legacy fallback/test fixture only.
- `backend/data` prediction outputs: temporary compatibility output only.
- Platform inbox: production handoff point.
- Platform public/model/normalized directories: platform-owned published outputs.

## Expected Final Boundary

Final owner split:

| Area | Owner |
|---|---|
| Canonical teams | `football-data-platform` |
| Canonical fixtures and match IDs | `football-data-platform` |
| Historical raw/processed shared data | `football-data-platform` |
| World Cup odds | `football-data-platform` |
| World Cup injuries | `football-data-platform` |
| World Cup lineups | `football-data-platform` |
| World Cup weather | `football-data-platform` |
| World Cup prematch context | `football-data-platform` |
| Model feature engineering | `world-cup-predictor` |
| Model training | `world-cup-predictor` |
| Model evaluation | `world-cup-predictor` |
| Prediction generation | `world-cup-predictor` |
| Prediction publish validation | `football-data-platform` |
| Public predictor API | `football-data-platform` |

## Handoff Summary For The Predictor Agent

Implement Phase 3 in `world-cup-predictor`:

1. Make platform strict mode the default and disable local fallback unless `FOOTBALL_DATA_PLATFORM_ALLOW_LOCAL_FALLBACK=1`.
2. Remove World Cup runtime collection from predictor production/scheduled flows.
3. Read World Cup runtime datasets from `football-data-platform`.
4. Keep prediction generation in the predictor.
5. Write prediction outputs to the platform inbox.
6. Add tests for strict mode, fallback mode, missing dataset failures, and inbox write-back.
7. Update `world-cup-predictor/DESIGN.md` and `README.md` to reflect the final owner boundary.
