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

Predictor runtime requirements baseline:

- `docs/2026-05-17-predictor-runtime-data-requirements-cn.md`

This document is the working contract for model-facing runtime data: confirmed lineups, AH/OU odds snapshots, injuries/player impact, weather, advanced team stats, and referee profiles.

Current model-facing aggregate entrypoint:

- `api/worldcup/2026/predictor/runtime-summary.json`
- Built by `scripts/publish_world_cup_predictor_api.py`
- Must output one row per fixture and explicitly mark missing runtime fields; it must not omit matches just because a runtime source is unavailable.

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

- TheOddsAPI is not a free soccer source. Its free tier covers NBA/MLB only; football requires Business. Keep it disabled for soccer unless `THE_ODDS_API_SOCCER_ENABLED=1` is explicitly set after a paid plan is active.
- API-FOOTBALL odds coverage, HKJC compliance validation, or another approved paid source
- OddsHarvester/OddsPortal where legally and operationally safe
- OddsPapi or other paid source if approved source coverage is insufficient
- Free/open source feasibility probes are tracked in `reports/free_odds_source_probe.json`. Current candidates are Odds-API.io, SharpAPI, and BSD/Bzzoiro as probe-only or pre-production candidates; OddsPortal/Leisu scrapers remain `experimental_only`, and BetStack is `pass` until reliable docs are found.

Acceptance criteria:

- Each upcoming match has odds freshness metadata.
- `predictor/health.json` shows odds rows and fixture coverage.
- `migration-status.json` no longer reports World Cup odds as a runtime gap when configured keys and source coverage exist.
- Missing odds do not break prediction generation, but they are recorded as optional runtime gaps.
- AH / OU snapshot rules, opening/closing semantics, bookmaker quality thresholds, and UTC anti-leakage requirements are defined in `docs/2026-05-17-predictor-runtime-data-requirements-cn.md`.

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
- Each match has source status: `available`, `partial`, `unavailable`, `missing_auth`, `missing`, or `provider_error`.
- Current baseline is explicit status coverage rather than empty files: 104 lineup rows are published as `unavailable/outside_lineup_window`, and injury rows expose the provider reason, such as `missing_auth`, `plan_restricted`, or `provider_error`. A local Free-plan probe confirmed API-FOOTBALL World Cup `league=1,season=2026` returns plan restriction rather than fixture rows.
- Placeholder rows are low confidence and must not be interpreted as "no injuries" or "no lineup"; they only explain why provider-backed facts are not yet available.
- News-derived injury evidence is supported through `scripts/build_world_cup_injury_evidence.py`. It adds `absence_evidence_summary` to injury rows from `prematch_context` injury/suspension mentions. This is evidence only, not an official availability verdict. The extractor is intentionally conservative: a mention is retained only when the entity matches an official platform roster player, the injury/suspension keyword has a word boundary match, and the player entity appears near that keyword. This prevents club lists, squad-list prose, or cross-headline text from creating false injury evidence.
- Lineup freshness supports pre-match windows: 90/60/30 minutes before kickoff.
- Injury status distinguishes confirmed absence, doubtful, suspension, and unknown.
- Confirmed lineups and injury/player-impact fields must follow `docs/2026-05-17-predictor-runtime-data-requirements-cn.md`.

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
- Weather rows must expose model-facing risk tags and minimum fields defined in `docs/2026-05-17-predictor-runtime-data-requirements-cn.md`.
- Fixtures outside the provider forecast window are published as explicit placeholders with `source_status=unavailable` and `status_reason=outside_forecast_window`; this prevents the predictor from treating missing future weather as zero wind or clear weather.

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

Advanced model-facing statistics:

- Predictor P1 requires possession, pass accuracy, passes completed, progressive passes, shots, shots on target, PPDA, xG for, and xG against.
- Missing advanced fields must be `null`, not `0`.
- `matches >= 5` is required for display trend claims; `matches >= 10` is required before using the field for strong model/report conclusions.

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
- `data/public/people-index.json`
- `data/public/coach-profiles.json`
- `data/public/player-profiles.json`
- `data/public/referee-profiles.json`

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

### 7.1 Team World Cup History And Recent Matches

Owner:

- `football-data-platform`

Status:

- `team_recent_matches` is published from `data/raw/international-results/results.csv` (`martj42/international_results`), with 48 teams and 10 matches per team.
- The full international results CSV is committed under `data/raw/international-results/` so CI can rebuild the dataset without relying on local predictor migration assets. If that source is absent, `scripts/build_team_history_datasets.py` falls back to migrated predictor `normalized_matches.csv`, then preserves an existing non-empty public snapshot or falls back to `public/qualifier-matches.json` only when needed.
- `team_world_cup_history` is published for 48 teams from openfootball World Cup JSON. Completed finals history covers 1930-2022; 2026 qualification is represented as `qualified_not_started`.
- `worldcup/2026` confirmed P0 display scope: main coach only, annual-level World Cup history, last 10 basic scores, player name/position/status/team_id, post-match updates only, no site odds display.

Required datasets:

- `data/normalized/team_world_cup_history_master.json`
- `data/normalized/team_recent_matches_master.json`
- `data/public/team-world-cup-history.json`
- `data/public/team-recent-matches.json`

Remaining work:

- Cross-check openfootball-derived summaries against FIFA/RSSSF/Kaggle historical sources before adding more presentation claims.
- Improve `best_finish`, `stage_reached`, and `finish` wording where early tournament formats are ambiguous.
- Keep `available` and `available_no_prior_appearances` visible so the site can distinguish historical participants from 2026 first-time qualifiers.
- Continue importing official rosters and head coaches as FIFA/FA squad announcements arrive.

Acceptance criteria:

- `team_world_cup_history` no longer contains `pending_source` for current 48 teams.
- `team_recent_matches` includes last 10 international matches for every actual 2026 team. Current criterion is met for 48 teams.
- World Cup site can show team history cards without maintaining local historical data.
- Predictor can consume recent-form data from platform instead of local CSV assumptions.

### 7.2 Referee Profiles And Officials Ratings

Owner:

- `football-data-platform`

Goal:

- Provide referee profile samples for model reports and non-odds risk explanations.

Required outputs:

- `data/public/api/worldcup/2026/core/officials.json`
- `data/public/api/worldcup/2026/core/official-ratings.json`
- `data/public/api/worldcup/2026/predictor/officials.json`
- `data/public/api/worldcup/2026/predictor/official-ratings.json`

Current status:

- `scripts/build_referee_sample_profiles.py` builds historical Premier League referee samples from `data/predictor-assets/files/processed/premier_league_matches.csv`.
- Published sample: 50 officials, 50 official ratings, 4,139 matches, 33 ratings with `sample_size >= 20`.
- Current rows use `source_status=historical_sample_only`. They are model/report style samples only, not FIFA World Cup 2026 referee assignments.
- Person profile Phase 1.5 is published for page rendering: 48 coach profiles have recent-team derived metrics from `team-recent-matches.json`; 234 player profiles expose direct field coverage and impact boxes; 50 referee profiles expose `assigned_matches=[]` and `assignment_status=missing_referee_assignment`.
- Player external facts are now partially filled from dcaribou Transfermarkt via Reep `key_transfermarkt`: 197 external-fact rows, 190 with club/caps/goals, 197 with DOB/age, 196 with display `impact_proxy_score`.
- Staff external facts are now partially filled from Reep coach rows: 44 external-fact rows, 43 with nationality and 44 with DOB/age.
- Player `shirt_number`, true `absence_impact_pct`, coach `appointed_at`, and coach `contract_until` remain `pending_source` because current official roster/staff patches and audited third-party sources do not contain reliable values.

Remaining work:

- Import FIFA World Cup 2026 referee assignments when available.
- Add international referee samples from FIFA/worldfootball/public match records where legally usable.
- Emit `missing_referee_assignment` when no referee is assigned and `low_referee_sample` when sample size is below 20.
- Keep `runtime-summary.json.referee_profile` as `missing_referee_assignment` until actual World Cup match referee assignments are imported.
- Import an audited roster source with player shirt number and minutes before enabling true absence impact percentages.
- Import audited FA/FIFA/official coach profile sources before filling `appointed_at` and `contract_until`.

Acceptance criteria:

- `sample_size >= 20` before a referee profile can influence model/report conclusions.
- `sample_size < 20` is published but marked low-confidence.
- Style tags and metrics follow `docs/2026-05-17-predictor-runtime-data-requirements-cn.md`.

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
- Production publish jobs run through a single serial entrypoint. Do not run writer scripts in parallel against `data/model/*`, `data/public/*`, or `reports/*`.
- Core runtime publish scripts use atomic JSON writes via `scripts/json_io.py`.
- `.github/workflows/rebuild-worldcup-data.yml` runs the serial collection/publish flow every 6 hours and has a `worldcup-data-publish` concurrency group.
- Workflow secrets are documented and optional by source: `API_FOOTBALL_KEY`, `OPENWEATHER_API_KEY`, `FOOTBALL_DATA_API_KEY`, `THE_ODDS_API_KEY`, `THE_ODDS_API_SOCCER_ENABLED`.
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
- Data quality report: `reports/data-quality.json`

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
- `data-quality.json` is generated by `scripts/build_data_quality_report.py` and provides `pass` / `attention` / `blocked` checks plus runbook text for fixture count, coverage, predictions, runtime odds, lineups, injuries, weather, prematch context, and automation readiness.

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
