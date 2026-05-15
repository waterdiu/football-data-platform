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

迁移状态：

- [https://waterdiu.github.io/football-data-platform/api/migration-status.json](https://waterdiu.github.io/football-data-platform/api/migration-status.json)

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
- [2026-05-15-world-cup-predictor-integration-design.md](/Users/chamcham/Documents/AI/CODEX/soccer/football-data-platform/docs/2026-05-15-world-cup-predictor-integration-design.md)

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

与 `worldcup/2026` 兼容的页面数据镜像也已经进一步内收为平台 own 的 master 文件，
主发布流水线默认不再依赖 `worldcup/2026` 仓库本身。

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

它会串行重建：

- worldcup site 兼容镜像
- finals fixtures/results/standings/detail datasets
- model runtime datasets
- coverage
- qualifier public datasets
- runtime API / predictor API / source health / runtime health

如果需要从旧的 `worldcup/2026` 仓库回灌兼容数据镜像，再单独运行：

```bash
node scripts/import_worldcup_site_local_data.mjs
```

如果需要先把 predictor 已下载的世界杯数据迁到平台 master，再单独运行：

```bash
python3 scripts/import_world_cup_predictor_local_data.py
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
自动化可运行性报告：

```bash
python3 scripts/build_automation_readiness_report.py
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
- `api/worldcup/2026/predictor/*`
- `api/predictor/data-assets/manifest.json`

并校验关键数据集数量没有明显异常。

## Automation Readiness

当前已经分成两层：

- 已经适合放到 GitHub Actions 的：
  - Pages 部署
  - 线上接口活性监控
  - 世界杯完整数据重建

历史上阻塞自动化的兄弟仓库依赖已经从主发布流水线移除：

- `worldcup/2026` 现在只保留为兼容回灌来源
- `world-cup-predictor` 现在只保留为模型上下文和预测数据的可选回灌来源

`worldcup/2026` 兼容站点数据这一层，已经不再是主发布流水线阻塞项；它现在只保留为手动回灌来源。

当前机器可读报告：

- `reports/automation-readiness.json`

当前定时重建 workflow：

- `.github/workflows/rebuild-worldcup-data.yml`

## Predictor Integration Layer

平台现在还提供 predictor 专用接口目录：

- `data/public/api/worldcup/2026/predictor/manifest.json`
- `data/public/api/worldcup/2026/predictor/bundle.json`
- `data/public/api/worldcup/2026/predictor/health.json`

它同时提供：

- predictor 旧格式兼容数据
- platform 标准数据
- model runtime datasets
- predictor 对接层健康摘要

用于让 `world-cup-predictor` 按阶段切换，而不是一次性硬切。

当前接入状态：

- `world-cup-predictor` 第一阶段代码改造已完成
- `world-cup-predictor` 第二阶段 inbox 双写已完成
- 模型项目已进入平台强制读取模式：默认从 `football-data-platform` 读取，平台缺失时失败
- 本地 `backend/data` fallback 仅能通过 `FOOTBALL_DATA_PLATFORM_ALLOW_LOCAL_FALLBACK=1` 显式开启，用于调试或应急 rollback
- 已覆盖世界杯 fixture inputs、predictions、storage/history、训练与英超相关脚本的基础读取
- 平台侧已在接入完成后重新执行 `scripts/sync_predictor_data_assets.py`
- 世界杯预测和英超预测已经通过 `data/inbox/predictor/**` 发布到平台
- runtime odds、lineups、injuries、weather 和 context snapshots 的 inbox 文件当前仍缺失，等采样/上下文任务实际产出后自动进入同一发布流程
- 当前切换状态以 `data/public/api/migration-status.json` 为准；平台强制读取阶段的期望状态是 `platform_strict_complete_with_runtime_gaps`

## Predictor Full Data Assets

`world-cup-predictor/backend/data` 里已经下载过的全部数据资产，也已经可以镜像到平台本地资产区：

- 本地镜像根目录：`data/predictor-assets/files/`
- 规范化资产清单：`data/normalized/predictor_data_assets_manifest.json`
- 公开清单 API：`data/public/api/predictor/data-assets/manifest.json`
- 公开摘要 API：`data/public/api/predictor/data-assets/summary.json`

当前迁移规模：

- 文件数：`404`
- 总大小：`1146108149` bytes
- 最大类别：`raw.statsbomb_events`，`314` 个文件

完整原始文件只保存在平台本地镜像中，不发布到 GitHub Pages。Pages 只发布 manifest、summary 和 category index，用于让模型项目解析平台本地路径。

迁移命令：

```bash
python3 scripts/import_predictor_data_assets.py
python3 scripts/publish_predictor_data_assets_api.py
```

模型项目数据更新后的推荐同步命令：

```bash
python3 scripts/sync_predictor_data_assets.py
```

它会刷新：

- 全量本地资产镜像
- `api/predictor/data-assets/*`
- `api/worldcup/2026/predictor/*`
- predictor runtime health

对接说明：

- `docs/2026-05-15-world-cup-predictor-code-change-instructions.md`
- `docs/2026-05-15-world-cup-predictor-full-data-handoff.md`
- `docs/2026-05-15-predictor-phase-2-writeback-contract.md`

下一阶段写回入口：

```bash
python3 scripts/publish_predictor_inbox.py
```

模型项目后续应把输出副本写入 `data/inbox/predictor/**`，再由平台发布到 `data/normalized`、`data/model` 和 `data/public`。

运行期数据闭环入口：

```bash
python3 scripts/sync_predictor_runtime_inbox.py
```

该入口会在本地先调用兄弟仓库 `world-cup-predictor` 的 scheduled maintenance 生成 odds/context inbox，再发布平台数据、刷新 runtime API 和 `migration-status.json`。如果模型项目已经单独生成了 inbox 文件，可用：

```bash
python3 scripts/sync_predictor_runtime_inbox.py --skip-capture
```

`publish_predictor_inbox.py` 会区分 `missing` 和 `empty`。空数组或空 JSONL 不会覆盖平台正式数据，避免“采集任务运行了但没有源数据”被误判成 runtime enrichment 完成。

平台自有运行期采集入口：

```bash
python3 scripts/collect_world_cup_runtime_data.py
```

当前已从模型侧迁出的采集器：

- The Odds API 赔率采集：有 `THE_ODDS_API_KEY` 时写入 `data/normalized/world_cup_2026_model_odds_master.json`
- OpenWeather 天气采集：配置在 `configs/venues/world_cup_2026.json`，有 `OPENWEATHER_API_KEY` 时写入 `data/normalized/world_cup_2026_model_weather_master.json`

没有 key 时只写 `reports/world_cup_runtime_collection_report.json`，不会覆盖现有数据。可在同步闭环中一并运行：

```bash
python3 scripts/sync_predictor_runtime_inbox.py --skip-capture --collect-platform-runtime
```

## Repository Layout

```text
football-data-platform/
├── DESIGN.md
├── README.md
├── configs/
├── schemas/
├── data/
│   ├── normalized/
│   ├── predictor-assets/
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
