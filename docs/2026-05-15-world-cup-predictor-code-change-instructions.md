# World Cup Predictor Code Change Instructions

Date: 2026-05-15

## Goal

Change `world-cup-predictor` so it uses `football-data-platform` as its data layer.

The first implementation should be platform-first with old local paths as fallback. Do not delete old fallback reads until prediction parity is verified.

## Platform Endpoints

World Cup runtime compatibility API:

- `https://waterdiu.github.io/football-data-platform/api/worldcup/2026/predictor/manifest.json`
- `https://waterdiu.github.io/football-data-platform/api/worldcup/2026/predictor/bundle.json`
- `https://waterdiu.github.io/football-data-platform/api/worldcup/2026/predictor/health.json`

Full predictor data asset API:

- `https://waterdiu.github.io/football-data-platform/api/predictor/data-assets/manifest.json`
- `https://waterdiu.github.io/football-data-platform/api/predictor/data-assets/summary.json`

Local platform asset root:

- `/Users/chamcham/Documents/AI/CODEX/soccer/football-data-platform/data/predictor-assets/files`

## Required Configuration

Add these environment variables to `world-cup-predictor`:

```bash
FOOTBALL_DATA_PLATFORM_ROOT=/Users/chamcham/Documents/AI/CODEX/soccer/football-data-platform
FOOTBALL_DATA_PLATFORM_ASSET_MANIFEST_URL=https://waterdiu.github.io/football-data-platform/api/predictor/data-assets/manifest.json
FOOTBALL_DATA_PLATFORM_WC_PREDICTOR_MANIFEST_URL=https://waterdiu.github.io/football-data-platform/api/worldcup/2026/predictor/manifest.json
FOOTBALL_DATA_PLATFORM_WC_PREDICTOR_BUNDLE_URL=https://waterdiu.github.io/football-data-platform/api/worldcup/2026/predictor/bundle.json
```

## Add A Data Platform Loader

Create:

- `backend/app/services/data_platform.py`

Responsibilities:

- Load the predictor asset manifest.
- Resolve `backend/data/<relative_path>` to `football-data-platform/data/predictor-assets/files/<relative_path>`.
- Fetch or read the World Cup predictor bundle.
- Provide old local path fallback during transition.

Required functions:

```python
def resolve_data_asset(relative_path: str) -> Path:
    ...

def read_text_asset(relative_path: str) -> str:
    ...

def read_json_asset(relative_path: str) -> object:
    ...

def read_csv_asset(relative_path: str) -> list[dict[str, str]]:
    ...

def load_world_cup_predictor_bundle() -> dict:
    ...

def load_world_cup_predictor_dataset(name: str) -> object:
    ...
```

Fallback rule:

- Try platform manifest `platform_path` first.
- If missing or unreadable, fall back to `backend/data/<relative_path>`.
- Log or return metadata showing whether data came from `platform` or `fallback`.

## File Mapping

Use `resolve_data_asset(relative_path)` for these old paths:

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
- `runtime/odds_snapshots.json`
- `runtime/context/*.jsonl`

Do not hardcode the full platform path in multiple scripts. Put all path resolution behind the loader.

## World Cup Runtime Mapping

Use `load_world_cup_predictor_dataset(name)` for:

- `shared_fixtures`
- `feature_inputs`
- `predictions_source`
- `fixtures`
- `results`
- `standings`
- `predictions`
- `data_coverage`
- `prematch_context`

First target scripts:

- `backend/scripts/build_fixture_inputs.py`
- `backend/scripts/generate_predictions.py`
- `backend/app/services/storage.py`

## Recommended Change Order

1. Add `backend/app/services/data_platform.py`.
2. Add unit tests for asset resolution and fallback behavior.
3. Change `build_fixture_inputs.py` to read World Cup shared fixtures and feature inputs from the platform bundle.
4. Change `generate_predictions.py` to read platform feature inputs, but keep output path unchanged first.
5. Change storage reads for `predictions.json` and `premier_league_predictions.json` to use the loader.
6. Change training and Premier League scripts to resolve CSV/JSON files through `resolve_data_asset`.
7. Run existing model scripts and compare outputs with the pre-migration outputs.
8. After parity, remove scattered direct `Path("backend/data/...")` usage.

## Update Flow After Model Writes New Data

If `world-cup-predictor` writes new data during transition, run this from `football-data-platform`:

```bash
python3 scripts/sync_predictor_data_assets.py
```

This refreshes:

- Full local asset mirror
- Predictor data-assets manifest
- World Cup predictor API
- Predictor health

## Acceptance Criteria

The model project change is complete when:

- `build_fixture_inputs.py` works with platform data.
- `generate_predictions.py` produces the same World Cup prediction count as before.
- Premier League prediction loading still works.
- History and training scripts can read CSV inputs through the platform loader.
- A missing platform file falls back to the old local path.
- No new direct `Path("backend/data/...")` reads are introduced.

## Known Current Gaps

The platform has the existing local predictor data, but current World Cup-specific live context still has known gaps:

- `odds_source` has no World Cup rows.
- `world_cup_context_snapshots.jsonl` does not exist.

This is exposed by:

- `https://waterdiu.github.io/football-data-platform/api/worldcup/2026/predictor/health.json`

Do not treat those two datasets as complete until the health endpoint no longer reports them as warnings.
