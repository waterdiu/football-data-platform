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

当前 `fixtures / results / standings / coverage` 的世界杯主发布链，已经默认优先基于这批 `worldcup-site-*` 本地迁移镜像重建，而不是重复请求外部接口。

当前已发布的第二阶段细分数据：

- `data/public/finals-events.json`
- `data/public/finals-lineups.json`
- `data/public/finals-match-stats.json`
- `data/public/qualifier-events.json`
- `data/public/qualifier-lineups.json`
- `data/public/qualifier-match-stats.json`

当前预选赛数据的维护边界：

- 平台内部主维护源：`data/normalized/world_cup_2026_qualifier_matches_master.json`
- 对外公共输出：`data/public/qualifier-*.json`
- `worldcup/2026` 当前保留为兼容导入源，不再是预选赛唯一上游

当前已经为 `worldcup/2026` 准备好可直接运行时读取的静态 JSON API：

- `data/public/api/worldcup/2026/manifest.json`
- `data/public/api/worldcup/2026/site/bundle.json`
- `data/public/api/worldcup/2026/core/bundle.json`

对应 GitHub Pages 线上地址：

- `https://waterdiu.github.io/football-data-platform/api/worldcup/2026/manifest.json`
- `https://waterdiu.github.io/football-data-platform/api/worldcup/2026/site/bundle.json`
- `https://waterdiu.github.io/football-data-platform/api/worldcup/2026/core/bundle.json`

其中：

- `site/*` 保留接近 `worldcup/2026` 现有页面数据结构，适合低风险迁移
- `core/*` 提供平台标准化数据集，适合后续彻底重构页面数据层

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

当前世界杯主发布顺序：

1. 导入 `worldcup/2026` 本地数据镜像
2. 从 `worldcup-site-full-schedule.json` 重建 `fixtures.json`
3. 从 `worldcup-site-finals-results.json` 重建 `results.json`
4. 基于共享层 `fixtures + results` 重建 `standings / coverage / model datasets`
5. 发布 `api/worldcup/2026/*` 运行时静态接口

当前预选赛推荐更新顺序：

1. 优先直接更新平台内 `world_cup_2026_qualifier_matches_master.json`
2. 运行 `python3 scripts/publish_qualifier_data.py`
3. 如需从旧站点兼容刷新，再运行 `node scripts/import_qualifier_matches.mjs` 后重新 publish

当前可直接生成的平台健康报告：

- `python3 scripts/build_source_health_report.py`

当前可直接发布 `worldcup/2026` 运行时静态接口：

- `python3 scripts/publish_worldcup_2026_api.py`

Pages 部署入口：

- `.github/workflows/deploy-pages.yml`

它会把 `data/public/` 直接发布到 GitHub Pages，因此 `worldcup/2026` 后续可以直接 fetch Pages URL，不再依赖构建前同步。

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
