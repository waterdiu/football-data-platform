# Football Data Platform

统一的足球公共数据层，服务展示网站、预测系统和后续多赛事扩展项目。

当前阶段目标：

- 建立稳定的数据目录与契约
- 统一球队、比赛、赛事 ID
- 输出可共享的 `JSON / CSV` 数据集
- 支持世界杯、英超，并可扩展到更多联赛和杯赛

主设计文档见 [DESIGN.md](/Users/chamcham/Documents/AI/CODEX/soccer/football-data-platform/DESIGN.md)。

## Repository Layout

```text
football-data-platform/
├── DESIGN.md
├── README.md
├── .env.example
├── configs/
├── schemas/
├── sources/
├── transforms/
├── pipelines/
├── data/
│   ├── raw/
│   ├── normalized/
│   ├── public/
│   └── model/
├── reports/
└── scripts/
```

## Phase 1 Outputs

第一阶段公共输出：

- `data/public/canonical_teams.json`
- `data/public/teams.json`
- `data/public/fixtures.json`
- `data/public/results.json`
- `data/public/standings.json`
- `data/public/qualifier-matches.json`
- `data/public/predictions.json`
- `data/public/data-coverage.json`

当前还会保留一组来自 `worldcup/2026` 本地数据模块的迁移镜像：

- `data/public/worldcup-site-groups.json`
- `data/public/worldcup-site-group-fixtures.json`
- `data/public/worldcup-site-group-stage-matches.json`
- `data/public/worldcup-site-bracket.json`
- `data/public/worldcup-site-full-schedule.json`
- `data/public/worldcup-site-finals-results.json`
- `data/public/worldcup-site-finals-coverage.json`
- `data/public/worldcup-site-qualifier-matches.json`

当前已发布的第二阶段细分数据：

- `data/public/finals-events.json`
- `data/public/finals-lineups.json`
- `data/public/finals-match-stats.json`
- `data/public/qualifier-events.json`
- `data/public/qualifier-lineups.json`
- `data/public/qualifier-match-stats.json`

当前已固定的补充 schema：

- `schemas/standing.schema.json`
- `schemas/event.schema.json`
- `schemas/lineup.schema.json`
- `schemas/match-stats.schema.json`
- `schemas/odds-snapshot.schema.json`
- `schemas/injury.schema.json`
- `schemas/prematch-context.schema.json`
- `schemas/weather.schema.json`

当前已固化的模型侧数据集：

- `data/model/odds_snapshots.json`
- `data/model/lineups.json`
- `data/model/injuries.json`
- `data/model/prematch_context.json`
- `data/model/weather.json`

## Initial Workflow

1. 在 `configs/competitions` 定义赛事配置
2. 在 `sources/` 为 provider 建立 adapter
3. 把原始响应缓存到 `data/raw`
4. 标准化后写到 `data/normalized`
5. 聚合并发布到 `data/public` 和 `data/model`
6. 生成 `reports/` 下的覆盖率和健康报告

当前可直接运行的一键入口：

- `python3 scripts/publish_all_world_cup_data.py`
- `python3 scripts/publish_all_world_cup_data.py --capture-context --context-limit 4`

当前可直接生成的平台健康报告：

- `python3 scripts/build_source_health_report.py`

当前可直接触发的跨仓库世界杯上下文采集入口：

- `python3 scripts/capture_world_cup_context_from_predictor.py --context-limit 4`

## Write Ownership

- `data/raw/`：只由抓取流程写入
- `data/normalized/`：只由平台内部标准化流程写入
- `data/model/`：由模型侧写入中间或最终模型产物
- `data/public/`：只由 publish 流程写入

消费项目不应直接写 `data/public/`。

## Mock Mode

本仓库提供 `data/mock/` 目录，供本地开发和 CI 使用。

当前包含：

- `football_data_world_cup_matches.sample.json`

authoritative match mapping 脚本默认可直接使用该 sample 做本地验证。
