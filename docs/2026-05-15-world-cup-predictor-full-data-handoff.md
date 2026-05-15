# World Cup Predictor Full Data Handoff

Date: 2026-05-15

## Purpose

This document describes the second integration step for `world-cup-predictor`: use `football-data-platform` as the canonical location for all already-downloaded predictor data assets, while keeping large raw provider files out of GitHub Pages runtime bundles.

## Current Platform Outputs

World Cup predictor runtime API:

- `https://waterdiu.github.io/football-data-platform/api/worldcup/2026/predictor/manifest.json`
- `https://waterdiu.github.io/football-data-platform/api/worldcup/2026/predictor/bundle.json`
- `https://waterdiu.github.io/football-data-platform/api/worldcup/2026/predictor/health.json`

Full predictor data asset manifest API:

- `https://waterdiu.github.io/football-data-platform/api/predictor/data-assets/manifest.json`
- `https://waterdiu.github.io/football-data-platform/api/predictor/data-assets/summary.json`

Local full asset mirror:

- `/Users/chamcham/Documents/AI/CODEX/soccer/football-data-platform/data/predictor-assets/files`

## Data Ownership

`football-data-platform` now owns two predictor-facing layers:

- Runtime compatibility layer: small World Cup datasets required by prediction scripts.
- Full local asset mirror: all already-downloaded `world-cup-predictor/backend/data` files.

The full mirror is local-only by design. It includes large raw archives such as StatsBomb event JSON files, Understat pages, historical CSVs, runtime probes, odds snapshots, and processed model inputs.

## First Integration Rule

Model code should not hardcode paths under `world-cup-predictor/backend/data` for newly migrated data.

Instead:

1. Load the platform asset manifest.
2. Resolve the required `relative_path`.
3. Read the file from `platform_path`.
4. Fall back to the old local predictor path only while migration is incomplete.

## Recommended Predictor Loader

Add a small loader module in `world-cup-predictor`, for example:

- `backend/app/services/data_platform.py`

Responsibilities:

- Read `api/predictor/data-assets/manifest.json` from a configured local platform checkout.
- Resolve an asset by `relative_path`, such as `processed/training_features.csv`.
- Provide fallback to `backend/data/<relative_path>` during transition.
- Read the World Cup predictor bundle from the live URL for runtime-compatible datasets.

Suggested configuration:

- `FOOTBALL_DATA_PLATFORM_ROOT=/Users/chamcham/Documents/AI/CODEX/soccer/football-data-platform`
- `FOOTBALL_DATA_PLATFORM_PREDICTOR_ASSET_MANIFEST=data/public/api/predictor/data-assets/manifest.json`
- `FOOTBALL_DATA_PLATFORM_WC_PREDICTOR_MANIFEST_URL=https://waterdiu.github.io/football-data-platform/api/worldcup/2026/predictor/manifest.json`

## Mapping From Old Predictor Paths

Old predictor data path:

- `backend/data/<relative_path>`

New platform local mirror path:

- `football-data-platform/data/predictor-assets/files/<relative_path>`

Manifest entry:

- `relative_path`
- `category`
- `bytes`
- `source_path`
- `platform_path`
- `platform_relative_path`
- `is_public_payload`

## Migration Order

Recommended order for `world-cup-predictor` changes:

1. Add the data platform loader.
2. Switch World Cup runtime inputs to `/api/worldcup/2026/predictor/`.
3. Switch processed CSV/JSON reads to the asset manifest.
4. Switch raw provider archives to the asset manifest.
5. Switch runtime context and odds files to the asset manifest.
6. Keep fallback paths until parity is verified.
7. Remove direct `backend/data` reads once all callers use the loader.

## Update Flow After Predictor Produces New Data

When `world-cup-predictor` refreshes local data, predictions, odds, context snapshots, or processed training files, run this command from `football-data-platform`:

```bash
python3 scripts/sync_predictor_data_assets.py
```

This command refreshes:

- `data/predictor-assets/files/**`
- `data/normalized/predictor_data_assets_manifest.json`
- `data/public/api/predictor/data-assets/**`
- `data/public/api/worldcup/2026/predictor/**`
- `data/public/api/worldcup/2026/predictor/health.json`

For a faster manifest-only check without copying files:

```bash
python3 scripts/sync_predictor_data_assets.py --skip-full-copy
```

## Important Boundary

The full asset mirror is not a public web data API. It is a platform-local data archive with a public manifest.

Large raw files are intentionally not published to GitHub Pages. This keeps the runtime API small and reliable while still making the platform the canonical local source for model data.
