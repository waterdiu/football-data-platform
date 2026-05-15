# Scripts

这个目录用于放手动运行或定时任务入口脚本。

建议入口：

- `fetch_competition.py`
- `publish_public_data.py`
- `publish_model_data.py`
- `backfill_historical_data.py`
- `bootstrap_world_cup_2026.py`

第一阶段先保持简单，先能手动触发，再考虑自动调度。

当前已落地的最小引导脚本：

- `import_worldcup_site_local_data.mjs`
  - 输入：`worldcup/2026/src/data/*`
  - 输出：`data/public/worldcup-site-*.json`
  - 并生成：`reports/worldcup_site_local_import_report.json`
- `bootstrap_world_cup_2026.py`
  - 输入：世界杯站的 `104 场 CSV` 与预测项目的球队翻译表
  - 输出：`data/public/teams.json` 和 `data/public/fixtures.json`
- `fetch_football_data_world_cup_matches.py`
  - 输入：本地可用的 `FOOTBALL_DATA_API_KEY`
  - 输出：`data/raw/football-data-org/world_cup_2026_matches.json`
- `map_world_cup_2026_authoritative_ids.py`
  - 输入：优先使用 `data/raw/football-data-org/world_cup_2026_matches.json`，否则回退到 mock sample
  - 输出：`data/normalized/world_cup_2026_authoritative_match_map.json`
  - 同时输出：`data/normalized/world_cup_2026_authoritative_fixtures.json`
- `publish_public_data.py`
  - 输入：标准化后的 authoritative fixtures
  - 输出：更新 `data/public/fixtures.json`
- `build_world_cup_results.py`
  - 输入：`football-data.org` raw matches + authoritative fixtures
  - 输出：`data/normalized/world_cup_2026_results.json`
  - 同时发布：`data/public/results.json`
- `build_world_cup_standings.py`
  - 输入：`fixtures.json`、`results.json`、`teams.json`
  - 输出：`data/normalized/world_cup_2026_standings.json`
  - 同时发布：`data/public/standings.json`
- `build_world_cup_coverage.py`
  - 输入：`fixtures.json`、`results.json`、`predictions.json`、正赛 detail datasets、model datasets
  - 输出：`data/normalized/world_cup_2026_data_coverage.json`
  - 同时发布：`data/public/data-coverage.json`
- `import_world_cup_predictions.py`
  - 输入：预测项目的 `backend/data/processed/predictions.json`
  - 输出：`data/model/predictions.json`
  - 同时发布：`data/public/predictions.json`
  - 并生成未匹配报告：`reports/world_cup_predictions_import_report.json`
- `export_world_cup_fixtures_for_predictor.py`
  - 输入：共享层 `data/public/fixtures.json`
  - 输出：预测项目 `backend/data/raw/world_cup_2026_shared_fixtures.json`
- `import_qualifier_matches.mjs`
  - 输入：展示站现有 `apiFootballQualifierMatches.ts` 和 `qualifierMatches.ts`
  - 输出：`data/public/qualifier-matches.json`
  - 并生成：`reports/qualifier_matches_import_report.json`
- `extract_qualifier_detail_datasets.py`
  - 输入：`data/public/qualifier-matches.json`
  - 输出：
    - `data/public/qualifier-events.json`
    - `data/public/qualifier-lineups.json`
    - `data/public/qualifier-match-stats.json`
  - 并生成：`reports/qualifier_detail_extract_report.json`
- `build_world_cup_detail_datasets.py`
  - 输入：世界杯 `football-data.org` raw payload + `fixtures.json`
  - 输出：
    - `data/public/finals-events.json`
    - `data/public/finals-lineups.json`
    - `data/public/finals-match-stats.json`
  - 并生成：`reports/world_cup_detail_extract_report.json`
- `build_world_cup_model_datasets.py`
  - 输入：`fixtures.json`、`finals-lineups.json`、预测项目可用的 `runtime/odds_snapshots.json`
  - 输出：
    - `data/model/odds_snapshots.json`
    - `data/model/lineups.json`
    - `data/model/injuries.json`
    - `data/model/prematch_context.json`
    - `data/model/weather.json`
  - 并生成：`reports/world_cup_model_dataset_report.json`
- `publish_all_world_cup_data.py`
  - 按顺序执行世界杯公共数据发布流水线
  - 先导入 `worldcup/2026` 已有本地数据镜像
  - 默认会重建：`results`、`standings`、`finals detail datasets`、`model datasets`、`coverage`
  - 可选 `--capture-context`，先触发预测项目的世界杯 context capture，再继续发布
- `build_source_health_report.py`
  - 聚合 `public/*`、`model/*` 和各类 report，输出统一的 `reports/source-health.json`
- `capture_world_cup_context_from_predictor.py`
  - 调用 `world-cup-predictor` 的 `run_scheduled_maintenance.py`
  - 只触发 `world_cup` 的 context capture，不跑 odds / predictions / evaluation
