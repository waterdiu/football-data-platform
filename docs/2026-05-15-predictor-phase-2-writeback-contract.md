# Predictor Phase 2 Write-Back Contract

Date: 2026-05-15

## Purpose

Phase 1 made `world-cup-predictor` read platform data first and fall back to local files.

Phase 2 moves selected predictor outputs and runtime snapshots into `football-data-platform` through an explicit inbox. The model project should write files into the inbox, and the platform publishes them into normalized, model, and public datasets.

Status: Phase 2 has been implemented for prediction outputs.

Completed:

- `worldcup-2026/predictions.json` is written by `world-cup-predictor` and published by the platform.
- `premier-league/predictions.json` is written by `world-cup-predictor` and published by the platform.
- `scripts/publish_predictor_inbox.py` has been run successfully.

Pending until upstream jobs produce data:

- `worldcup-2026/odds-snapshots.json`
- `worldcup-2026/lineups.json`
- `worldcup-2026/injuries.json`
- `worldcup-2026/prematch-context.json`
- `worldcup-2026/weather.json`
- `premier-league/odds-snapshots.json`
- `premier-league/context-snapshots.jsonl`

## Inbox Root

Local inbox root:

- `/Users/chamcham/Documents/AI/CODEX/soccer/football-data-platform/data/inbox/predictor`

Do not write directly to:

- `data/public`
- `data/model`
- `data/normalized`

Those directories are published by platform scripts only.

## World Cup 2026 Inbox Files

Write these files from `world-cup-predictor` when they are produced:

- `worldcup-2026/predictions.json`
- `worldcup-2026/odds-snapshots.json`
- `worldcup-2026/lineups.json`
- `worldcup-2026/injuries.json`
- `worldcup-2026/prematch-context.json`
- `worldcup-2026/weather.json`

Platform publish script:

```bash
python3 scripts/publish_predictor_inbox.py
```

## Premier League Inbox Files

Write these files from `world-cup-predictor` when they are produced:

- `premier-league/predictions.json`
- `premier-league/odds-snapshots.json`
- `premier-league/context-snapshots.jsonl`

Premier League public API is not yet standardized in this platform. These files are accepted into normalized masters first.

## Publish Mapping

World Cup files are mapped as follows:

- `worldcup-2026/predictions.json` -> `data/normalized/world_cup_2026_predictor_predictions_source_master.json` and `data/public/predictions.json`
- `worldcup-2026/odds-snapshots.json` -> `data/normalized/world_cup_2026_model_odds_master.json` and `data/model/odds_snapshots.json`
- `worldcup-2026/lineups.json` -> `data/normalized/world_cup_2026_model_lineups_master.json` and `data/model/lineups.json`
- `worldcup-2026/injuries.json` -> `data/normalized/world_cup_2026_model_injuries_master.json` and `data/model/injuries.json`
- `worldcup-2026/prematch-context.json` -> `data/normalized/world_cup_2026_model_prematch_context_master.json` and `data/model/prematch_context.json`
- `worldcup-2026/weather.json` -> `data/normalized/world_cup_2026_model_weather_master.json` and `data/model/weather.json`

Premier League files are mapped as normalized masters:

- `premier-league/predictions.json` -> `data/normalized/premier_league_predictor_predictions_master.json`
- `premier-league/odds-snapshots.json` -> `data/normalized/premier_league_predictor_odds_master.json`
- `premier-league/context-snapshots.jsonl` -> `data/normalized/premier_league_predictor_context_snapshots_master.jsonl`

## Recommended Model Project Change

Add a writer helper next to the phase 1 loader:

- `backend/app/services/data_platform.py`

Suggested functions:

```python
def predictor_inbox_path(relative_path: str) -> Path:
    ...

def write_predictor_inbox_json(relative_path: str, payload: object) -> Path:
    ...

def write_predictor_inbox_jsonl(relative_path: str, rows: Iterable[dict]) -> Path:
    ...
```

Configuration:

```bash
FOOTBALL_DATA_PLATFORM_ROOT=/Users/chamcham/Documents/AI/CODEX/soccer/football-data-platform
FOOTBALL_DATA_PLATFORM_PREDICTOR_INBOX=data/inbox/predictor
```

## Transition Rule

During phase 2, `world-cup-predictor` may keep writing its existing local files. It should additionally write a copy into the platform inbox.

Once the inbox publish path is verified, later phases can remove the duplicate local writes.

## Acceptance Criteria

Phase 2 is complete when:

- `world-cup-predictor` writes World Cup predictions to `data/inbox/predictor/worldcup-2026/predictions.json`.
- `python3 scripts/publish_predictor_inbox.py` publishes that file to platform `data/public/predictions.json`.
- Runtime files produced by predictor appear in the corresponding inbox files.
- Platform health reflects newly available odds/context rows when those files exist.
- Existing local model project outputs continue to work during transition.
