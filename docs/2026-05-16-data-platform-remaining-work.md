# Football Data Platform Remaining Data-Layer Work

Date: 2026-05-16

## Purpose

This document lists the remaining data-layer work that should stay in `football-data-platform`.

The data layer has been moved out of `worldcup/2026` and `world-cup-predictor`.
The remaining work below should not be assigned to `world-cup-predictor` unless explicitly marked as model-owned.

## Ownership Boundary

`football-data-platform` owns:

- Data collection
- Source adapters
- Raw cache
- Normalization and canonical IDs
- Public/model dataset publishing
- Health reports
- Coverage reports
- Data freshness and source degradation reporting
- Runtime data automation

`world-cup-predictor` owns:

- Feature engineering
- Model training
- Model evaluation
- Probability prediction
- EV/Kelly/report logic
- Prediction output generation
- Writing prediction outputs to platform inbox

The predictor must read platform data and write model outputs back to the platform inbox.
It must not own production shared data collection.

## Current Completed Platform Migration

Already moved into `football-data-platform`:

- Canonical 2026 World Cup fixtures
- Canonical teams
- World Cup site API for `worldcup/2026`
- World Cup predictor bundle/API for `world-cup-predictor`
- Predictor data-assets manifest
- Predictor inbox publishing
- World Cup predictions publishing
- Premier League prediction normalized master publishing
- World Cup runtime collector entrypoint
- The Odds API adapter
- API-FOOTBALL lineups/injuries adapter
- OpenWeather adapter
- Public-news prematch context adapter
- Migration status API
- Source health report
- Runtime health report

Primary platform runtime collector:

```bash
python3 scripts/collect_world_cup_runtime_data.py
```

Primary platform runtime publish/refresh wrapper:

```bash
python3 scripts/sync_predictor_runtime_inbox.py --skip-capture --collect-platform-runtime
```

## Remaining Data-Layer Tasks

### 1. World Cup Runtime Odds Coverage

Owner:

- `football-data-platform`

Status:

- The Odds API adapter is platform-owned.
- It requests `h2h,spreads,totals` by default.
- It standardizes market summaries into `h2h`, `over_under`, `asian_handicap`, `has_1x2`, `has_over_under`, and `has_asian_handicap`.
- Remaining work requires configured provider keys and provider coverage for 2026 World Cup fixtures.

Goal:

- Produce reliable World Cup odds datasets for prediction and health reporting.

Required datasets:

- `data/normalized/world_cup_2026_model_odds_master.json`
- `data/model/odds_snapshots.json`
- `data/public/api/worldcup/2026/predictor/bundle.json`

Required markets:

- 1X2
- Over/Under
- Asian Handicap

Later markets:

- BTTS
- Half-time/full-time
- Correct score

Sources:

- The Odds API
- OddsHarvester/OddsPortal where legally and operationally safe
- OddsPapi or other paid source if The Odds API coverage is insufficient

Acceptance criteria:

- Each upcoming match has odds freshness metadata.
- `predictor/health.json` shows odds rows and fixture coverage.
- `migration-status.json` no longer reports World Cup odds as a runtime gap when configured keys and source coverage exist.
- Missing odds do not break prediction generation, but they are recorded as optional runtime gaps.

### 2. World Cup Lineups And Injuries Coverage

Owner:

- `football-data-platform`

Goal:

- Own production lineup and injury collection.

Required datasets:

- `data/normalized/world_cup_2026_model_lineups_master.json`
- `data/normalized/world_cup_2026_model_injuries_master.json`
- `data/model/lineups.json`
- `data/model/injuries.json`

Sources:

- API-FOOTBALL
- Official team/FIFA match pages as fallback
- Manual patch file for critical gaps if provider coverage is incomplete

Acceptance criteria:

- API-FOOTBALL fixture ID mapping is maintained in `data/runtime/api_football_fixture_map.json`.
- Each match has source status: `available`, `partial`, `missing`, or `provider_error`.
- Lineup freshness supports pre-match windows: 90/60/30 minutes before kickoff.
- Injury status distinguishes confirmed absence, doubtful, suspension, and unknown.

### 3. World Cup Prematch Context Coverage

Owner:

- `football-data-platform`

Goal:

- Keep production prematch news/context collection in the platform.

Required dataset:

- `data/normalized/world_cup_2026_model_prematch_context_master.json`
- `data/model/prematch_context.json`

Current adapter:

- `sources/prematch_news.py`

Remaining work:

- Source-level freshness timestamps: completed. `reports/world_cup_runtime_collection_report.json` and collected `prematch_news_summary.source_freshness` include source `status`, `last_checked_at`, `pages_collected`, and errors.
- Per-fixture confidence score into coverage reporting: initial support completed through `prematch_context.readiness_score` and `runtime_summary.confidence_score`; continue tuning after real provider rows arrive.
- Source allowlist/config file instead of hardcoding all news URLs: completed through `configs/prematch_news/world_cup_2026.json`; code keeps built-in fallback if the config file is unavailable.
- Add optional manual context patch file for important injuries or official announcements.

Acceptance criteria:

- `prematch_context` is not a pending adapter.
- Public predictor bundle contains `prematch_context`.
- Health reports show rows, freshness, and source errors.

### 4. World Cup Weather Coverage

Owner:

- `football-data-platform`

Goal:

- Produce match-weather snapshots for model consumption and match pages.

Required datasets:

- `data/normalized/world_cup_2026_model_weather_master.json`
- `data/model/weather.json`

Source:

- OpenWeather

Acceptance criteria:

- Every venue has latitude/longitude in `configs/venues/world_cup_2026.json`.
- Weather rows include provider timestamp and fixture timestamp.
- Missing API key or provider errors are visible in runtime collection report.

### 5. World Cup Data Coverage Table

Owner:

- `football-data-platform`

Status:

- First implementation completed in `scripts/build_world_cup_coverage.py`.
- Current output includes per-match `runtime_summary` and field-level status/confidence/source/last_updated metadata where available.
- Remaining work is to improve confidence scoring as real provider rows arrive and to add richer technical-stat/xG/player-rating sources if subscribed.

Goal:

- Maintain one per-match coverage table usable by site pages and predictor confidence logic.

Required output:

- `data/public/data-coverage.json`
- `data/public/api/worldcup/2026/data-coverage.json`
- `data/public/api/worldcup/2026/predictor/health.json`

Coverage fields:

- result
- events
- standings
- odds
- asian_handicap
- over_under
- injuries
- lineups
- weather
- prematch_context
- technical_stats
- xg
- player_ratings

Each field should include:

- `status`
- `confidence`
- `source`
- `last_updated`
- relevant row/count metadata

Acceptance criteria:

- Predictor can use coverage to downgrade runtime confidence. Initial support is available through `runtime_summary`.
- Site can show missing-data states without hardcoding provider logic. Initial support is available through field-level coverage objects.
- Coverage is rebuilt after every collection/publish cycle.

### 6. World Cup Results And Match Stats Runtime Updates

Owner:

- `football-data-platform`

Goal:

- Own live and post-match updates after the tournament starts.

Required data:

- Match status
- Full-time score
- Half-time score
- Extra-time score
- Penalty shootout score
- Goals and minutes
- Cards
- Substitutions
- VAR events where available
- Shots
- Shots on target
- Possession
- Corners
- Fouls
- Offsides
- Saves
- xG if a reliable source exists
- Player ratings if a reliable source exists

Sources:

- football-data.org
- API-FOOTBALL
- BALLDONTLIE GOAT if subscribed and verified
- openfootball as static fallback

Acceptance criteria:

- Live collector continues through extra time and penalty shootouts.
- Concurrent same-group matches are collected in parallel or without serial blocking.
- Final post-match rows are marked as finalized.
- Site and predictor consume platform results only.

### 7. National Team Rosters And Player Data

Owner:

- `football-data-platform`

Goal:

- Provide canonical national-team roster/player inputs.

Required datasets:

- `data/normalized/world_cup_2026_rosters_master.json`
- `data/normalized/world_cup_2026_players_master.json`
- `data/model/players.json`
- `data/model/rosters.json`

Fields:

- player_id
- canonical name
- aliases
- team_id
- position
- club
- age/date of birth
- market value if available
- national team caps/goals if available
- injury/suspension status
- ability/rating features if available

Sources:

- FIFA official squads
- National federation pages
- Transfermarkt-derived existing local data where license permits
- Existing predictor player ability assets

Acceptance criteria:

- Predictor no longer maintains separate production player/team mappings.
- Roster updates are versioned by source and timestamp.

### 8. Premier League Public API Standardization

Owner:

- `football-data-platform`

Goal:

- Bring Premier League data to the same platform API standard as World Cup.

Current state:

- Premier League predictions are accepted into normalized masters.
- Public Premier League API is not yet standardized.

Required outputs:

- `data/public/api/premier-league/manifest.json`
- `data/public/api/premier-league/health.json`
- `data/public/api/premier-league/predictor/bundle.json`
- `data/public/api/premier-league/predictor/manifest.json`

Datasets:

- fixtures
- results
- historical matches
- training features
- predictions
- odds snapshots
- context snapshots
- coverage

Acceptance criteria:

- Premier League predictor scripts can run from platform API/assets without local production data.
- Health reports show dataset row counts and freshness.

### 9. Platform Automation

Owner:

- `football-data-platform`

Goal:

- Make data collection and publishing repeatable without manual local runs.

Required automation:

- GitHub Actions or another scheduler for runtime collectors.
- Secrets for provider API keys.
- Scheduled publish of model/public APIs.
- Runtime health rebuild.
- Migration status rebuild.

Suggested schedules:

- Pre-tournament fixtures/static data: daily.
- Matchday live status/results: every 1-5 minutes.
- Matchday events/stats: every 5-15 minutes.
- Odds: every 1-3 hours from 72h before kickoff, every 15-30 minutes inside final 6h.
- Lineups: 90/60/30 minutes before kickoff, then post-match final.
- Weather: every 6h from 72h before kickoff, hourly on matchday.
- Prematch context: daily, then every 2-4h from 72h before kickoff.

Acceptance criteria:

- A fresh clone with configured secrets can run the full platform collection/publish cycle.
- Failures are visible in `reports/*` and public health endpoints.
- Automation does not depend on `world-cup-predictor` checkout for production runtime data.

### 10. Data Quality Alerts And Runbooks

Owner:

- `football-data-platform`

Goal:

- Make missing or stale data obvious.

Required reports:

- Source health
- Runtime collection report
- Coverage report
- API quota report
- Data conflict report
- Automation readiness report

Required runbooks:

- Missing API key
- Provider outage
- Stale public API
- Fixture ID mismatch
- Odds coverage missing
- Lineups unavailable before kickoff
- Manual patch process

Acceptance criteria:

- Health endpoints can be checked by a monitor.
- A human can diagnose source failure without reading model code.
- `source-health.json` includes a summarized `world_cup_sources.runtime_collection` section so humans can see runtime dataset status, auth gaps, provider errors, and source freshness counts from one report.

## Tasks That Should Not Move To The Platform

Keep these in `world-cup-predictor`:

- Probability model code
- Model calibration
- Feature weighting
- EV/Kelly logic
- Prediction report language
- Backtesting methodology
- Model training orchestration
- Prediction generation

The platform should provide data and quality metadata, not decide model probabilities.

## Handoff Summary

Remaining data-layer work to continue in `football-data-platform`:

1. Complete World Cup runtime odds coverage.
2. Complete lineups/injuries/weather/prematch context freshness and coverage.
3. Build per-match data coverage with confidence metadata.
4. Add live/post-match results and match stats update pipelines.
5. Add national team roster/player datasets.
6. Standardize Premier League public/predictor API.
7. Automate collection and publishing.
8. Add alerts, runbooks, quota reports, and data conflict reporting.

`world-cup-predictor` should only implement the Phase 3 strict platform consumer changes described in:

- `docs/2026-05-16-predictor-phase-3-full-cutover-instructions.md`
