# Football Data Platform

统一的足球公共数据层，服务：

- `worldcup/2026` 展示网站
- `world-cup-predictor` 预测系统
- 后续英超、欧冠、欧洲杯等扩展项目

这个仓库当前最重要的职责，是为 `worldcup/2026` 提供可直接运行时读取的静态 JSON API，而不是继续让站点靠“构建前同步 TS 文件”获取数据。

主设计文档见 [DESIGN.md](/Users/chamcham/Documents/AI/CODEX/soccer/football-data-platform/DESIGN.md)。

## Live Endpoints

GitHub Pages 已上线，`worldcup/2026` 可以直接请求这些地址：

- Manifest:
  - [https://waterdiu.github.io/football-data-platform/api/worldcup/2026/manifest.json](https://waterdiu.github.io/football-data-platform/api/worldcup/2026/manifest.json)
- Site bundle:
  - [https://waterdiu.github.io/football-data-platform/api/worldcup/2026/site/bundle.json](https://waterdiu.github.io/football-data-platform/api/worldcup/2026/site/bundle.json)
- Core bundle:
  - [https://waterdiu.github.io/football-data-platform/api/worldcup/2026/core/bundle.json](https://waterdiu.github.io/football-data-platform/api/worldcup/2026/core/bundle.json)

Pages 首页：

- [https://waterdiu.github.io/football-data-platform/](https://waterdiu.github.io/football-data-platform/)

## What The 2026 Site Should Read

推荐顺序：

1. 先请求 `manifest.json`
2. 页面层优先读取 `manifest.runtime_contract.preferred_site_url`
3. 失败时 fallback 到 `worldcup/2026/src/data/*.ts`
4. 页面稳定后，再逐步从 `site/*` 切到 `core/*`

原因：

- `site/*` 保留接近 `worldcup/2026` 现有页面结构，接入风险低
- `core/*` 是平台长期标准契约，适合后续统一页面和模型侧数据结构

完整交接文档见：

- [2026-05-15-worldcup-2026-integration-handoff.md](/Users/chamcham/Documents/AI/CODEX/soccer/football-data-platform/docs/2026-05-15-worldcup-2026-integration-handoff.md)
- [2026-05-15-worldcup-2026-runtime-api.md](/Users/chamcham/Documents/AI/CODEX/soccer/football-data-platform/docs/2026-05-15-worldcup-2026-runtime-api.md)

## Current Runtime Contract

### Site API

用于低风险接入 `worldcup/2026` 现有页面。

`site/bundle.json` 包含：

- `groups`
- `group_fixtures`
- `group_stage_matches`
- `bracket`
- `full_schedule`
- `finals_results`
- `finals_coverage`
- `qualifier_matches`
- `qualifier_missing_data`
- `qualifier_source_reports`

### Core API

用于后续收敛到平台标准 schema。

`core/bundle.json` 包含：

- `canonical_teams`
- `teams`
- `fixtures`
- `results`
- `standings`
- `predictions`
- `data_coverage`
- `qualifier_events`
- `qualifier_lineups`
- `qualifier_match_stats`

## Current Data Ownership

### World Cup finals

世界杯正赛基础层已经切成“本地迁移数据优先”：

- `fixtures`
- `results`
- `standings`
- `data_coverage`

它们会优先基于 `worldcup/2026` 已经落地的本地数据镜像重建，而不是重复请求外部接口。

### World Cup qualifiers

预选赛当前已经有平台内主维护源：

- `data/normalized/world_cup_2026_qualifier_matches_master.json`

对外公共输出：

- `data/public/qualifier-matches.json`
- `data/public/qualifier-events.json`
- `data/public/qualifier-lineups.json`
- `data/public/qualifier-match-stats.json`

`worldcup/2026` 里的旧预选赛数据文件现在只保留为兼容导入源，不再应视为唯一上游。

## Commands

世界杯主发布流水线：

```bash
python3 scripts/publish_all_world_cup_data.py
```

带上下文采集的世界杯发布：

```bash
python3 scripts/publish_all_world_cup_data.py --capture-context --context-limit 4
```

预选赛公共数据发布：

```bash
python3 scripts/publish_qualifier_data.py
```

运行时 API 发布：

```bash
python3 scripts/publish_worldcup_2026_api.py
```

健康报告：

```bash
python3 scripts/build_source_health_report.py
```

运行时健康快照：

```bash
python3 scripts/build_worldcup_2026_runtime_health.py
```
## Publish Model

当前线上部署通过 GitHub Pages 完成：

- workflow: `.github/workflows/deploy-pages.yml`
- 发布目录：`data/public/`

这意味着只要 `football-data-platform` 更新并重新发布，`worldcup/2026` 页面刷新后就能拿到最新 JSON，不需要重新构建站点。

## Monitoring

当前已提供两个监控入口：

- Pages 上的运行时健康快照：
  - [https://waterdiu.github.io/football-data-platform/api/worldcup/2026/health.json](https://waterdiu.github.io/football-data-platform/api/worldcup/2026/health.json)
- GitHub Actions 定时检查：
  - `.github/workflows/monitor-runtime-api.yml`

这个监控 workflow 每 30 分钟检查：

- `manifest.json`
- `site/bundle.json`
- `core/bundle.json`
- `health.json`

并校验关键数据集数量没有明显异常。
## Repository Layout

```text
football-data-platform/
├── DESIGN.md
├── README.md
├── configs/
├── schemas/
├── data/
│   ├── normalized/
│   ├── public/
│   └── model/
├── reports/
├── scripts/
└── docs/
```

## Write Boundaries

- `data/raw/`：抓取侧写入
- `data/normalized/`：平台标准化与主维护源写入
- `data/model/`：模型侧输出写入
- `data/public/`：只由发布流程写入

消费项目不应直接写 `data/public/`。
