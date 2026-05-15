# Football Data Platform Design

日期：2026-05-15  
状态：主设计基线

## 1. Purpose

`football-data-platform` 是一个独立的足球公共数据层，服务多个消费项目，包括：

- 世界杯展示网站
- 足球预测模型项目
- 后续英超、欧冠、欧洲杯等扩展项目
- 后台报表和数据监控

它负责统一接入数据源、标准化字段与 ID、缓存原始数据、输出标准数据集，并记录覆盖率与质量情况。

它不负责前端页面、不负责模型训练、不负责用户系统。

## 2. Goals

核心目标：

1. 统一接入足球数据源
2. 统一球队、比赛、赛事主键和字段结构
3. 减少重复抓取和配额浪费
4. 输出稳定 JSON / CSV 数据集
5. 让展示项目和预测项目通过数据契约共享，而不是互相引用源码
6. 支持从世界杯扩展到联赛、杯赛和国家队赛事
7. 提供覆盖率、缺失和冲突报告

## 3. Non-Goals

第一阶段不做：

- 通用在线 API 服务
- 完整数据库平台
- 用户系统
- 模型训练流水线
- 页面渲染
- 多项目源码耦合

## 4. Consumers

### 4.1 World Cup Site

项目：`/Users/chamcham/Documents/AI/CODEX/soccer/worldcup/2026`

主要消费：

- `canonical_teams.json`
- `teams.json`
- `fixtures.json`
- `results.json`
- `standings.json`
- `qualifier-matches.json`
- `predictions.json`
- `data-coverage.json`

### 4.2 Predictor

项目：`/Users/chamcham/Documents/AI/CODEX/soccer/world-cup-predictor`

主要消费：

- `canonical_teams.json`
- `teams.json`
- `fixtures.json`
- `historical_matches.csv`
- `odds_snapshots.json`
- `lineups.json`
- `injuries.json`
- `prematch_context.json`
- `weather.json`

主要回写：

- `predictions.json`

## 5. Architecture

主流程：

`providers -> raw cache -> normalize -> canonical mapping -> merge -> validate -> publish -> consumers`

```mermaid
flowchart LR
  subgraph S["Sources"]
    S1["football-data.org"]
    S2["API-FOOTBALL"]
    S3["openfootball"]
    S4["StatsBomb / Understat"]
    S5["Odds APIs / crawlers"]
    S6["Official sites / media"]
    S7["Weather API"]
  end

  subgraph P["football-data-platform"]
    P1["configs"]
    P2["source adapters"]
    P3["raw cache"]
    P4["normalize"]
    P5["canonical registry"]
    P6["merge"]
    P7["validate + coverage"]
    P8["publish"]
  end

  subgraph C["Consumers"]
    C1["worldcup/2026"]
    C2["world-cup-predictor"]
    C3["reports/admin"]
  end

  S1 --> P2
  S2 --> P2
  S3 --> P2
  S4 --> P2
  S5 --> P2
  S6 --> P2
  S7 --> P2

  P1 --> P2
  P2 --> P3
  P3 --> P4
  P5 --> P4
  P4 --> P6
  P5 --> P6
  P6 --> P7
  P7 --> P8
  P8 --> C1
  P8 --> C2
  P7 --> C3
  C2 -->|write predictions| P8
```

## 6. Repository Layout

```text
football-data-platform/
├── DESIGN.md
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

## 7. Core Datasets

第一阶段核心数据集：

- `canonical_teams`
- `teams`
- `fixtures`
- `results`
- `standings`
- `qualifier_matches`
- `predictions`
- `data_coverage`
- `model lineups`
- `model odds_snapshots`
- `model injuries`
- `model prematch_context`
- `model weather`

后续扩展：

- `standings`
- `events`
- `lineups`
- `match_stats`
- `advanced_stats`
- `odds_snapshots`
- `injuries`
- `prematch_context`
- `weather`

## 8. Canonical IDs

统一主键：

- `competition_id`
- `season_id`
- `match_id`
- `team_id`
- `player_id`

示例：

```json
{
  "competition_id": "fifa_world_cup",
  "season_id": "2026",
  "match_id": "fifa_world_cup:2026:fdorg:123456",
  "team_id": "mexico"
}
```

规则：

- 平台内部主键稳定，不依赖单一 provider
- `match_id` 不应长期依赖人工编排序号
- 当存在权威主源时，`match_id` 应以主源稳定 ID 为基础
- bootstrap 阶段允许使用带来源前缀的临时 ID，例如 `fifa_world_cup:2026:schedule_csv:001`
- provider 原始 ID 一律保存在 `source_refs`
- 球队名称、别名、中文名统一收敛到 `teams` 主表

示例：

```json
{
  "match_id": "fifa_world_cup:2026:fdorg:123456",
  "source_refs": {
    "football_data_org": "123456",
    "api_football": "456789",
    "openfootball": "2026/001"
  }
}
```

在第一阶段，如果某数据集还没有接入权威比赛 ID，允许使用临时 `match_id`，但必须满足：

- 带明确来源前缀
- 可批量重映射
- 不作为最终长期契约对外承诺

此外，平台内部应保留一个稳定匹配键思路，用于后续对齐多源同场比赛：

- `competition_id`
- `season_id`
- `date_utc`
- `home_team_id`
- `away_team_id`

## 9. Core Schemas

### canonical_teams.json

这是球队名称规范化主表，也是所有 provider 标准化脚本的唯一映射入口。

包含：

- `team_id`
- `name`
- `short_name`
- `localized_name`
- `aliases`
- `source_aliases`
- `sources`
- `updated_at`

规则：

- 所有数据源的球队名称都必须先映射到 `canonical_teams.json`
- 不允许各项目继续维护分叉的球队名映射表作为长期真相来源
- `teams.json` 可作为面向消费方的公开球队集，而 `canonical_teams.json` 是内部规范化基线

### teams.json

包含：

- `team_id`
- `name`
- `short_name`
- `localized_name`
- `flag_emoji`
- `fifa_rank`
- `aliases`
- `sources`
- `updated_at`

### fixtures.json

包含：

- `match_id`
- `competition_id`
- `season_id`
- `stage`
- `round`
- `group`
- `date_utc`
- `status`
- `home_team_id`
- `away_team_id`
- `venue_id`
- `source_refs`
- `updated_at`

### results.json

包含：

- `match_id`
- `status`
- `score`
- `winner`
- `result_type`
- `provider`
- `updated_at`

### predictions.json

包含：

- `match_id`
- `model_name`
- `generated_at`
- `probabilities`
- `predicted_score`
- `confidence`
- `summary`
- `inputs`

### data-coverage.json

包含：

- `match_id`
- `fixture`
- `result`
- `events`
- `lineups`
- `match_stats`
- `odds`
- `injuries`
- `weather`
- `prediction`
- `last_checked_at`

### standings.json

包含：

- `competition_id`
- `season_id`
- `stage`
- `group`
- `rank`
- `team_id`
- `team_name`
- `played`
- `won`
- `drawn`
- `lost`
- `goals_for`
- `goals_against`
- `goal_difference`
- `points`

### events / lineups / match_stats

第二阶段详情数据当前已固定独立 schema：

- `schemas/event.schema.json`
- `schemas/lineup.schema.json`
- `schemas/match-stats.schema.json`

这些 schema 先保持宽松，重点固定：

- `match_id`
- provider 标识
- 主客队或事件归属
- 时间戳 / confidence / captured_at 等元信息

### model datasets schemas

模型侧数据当前已固定独立 schema：

- `schemas/odds-snapshot.schema.json`
- `schemas/injury.schema.json`
- `schemas/prematch-context.schema.json`
- `schemas/weather.schema.json`

这些 schema 主要约束：

- `match_id`
- `source` / `source_status` / `confidence`
- `readiness` 与 `source_statuses`
- 书商覆盖、sharp bookmaker 标记
- 赛前上下文摘要对象

状态字段不应只支持简单字符串。对于预测相关数据，覆盖报告需要记录可信度与来源质量。

推荐结构：

```json
{
  "match_id": "fifa_world_cup:2026:fdorg:123456",
  "odds": {
    "status": "available",
    "bookmaker_count": 3,
    "has_sharp": true,
    "confidence": "medium"
  },
  "injuries": {
    "status": "partial",
    "source": "news_inference",
    "confidence": "low"
  },
  "lineups": {
    "status": "available",
    "source": "official",
    "confidence": "high"
  },
  "last_checked_at": "2026-05-15T00:00:00Z"
}
```

其中：

- `status` 解决有没有
- `confidence` 解决靠不靠谱
- `source` / `bookmaker_count` / `has_sharp` 等字段解决为什么可信度不同

这个结构直接服务预测系统的降档、阻断和 Kelly 风控逻辑。

## 10. Source Strategy

| Dataset | Primary | Secondary |
| --- | --- | --- |
| local 2026 site datasets | `worldcup/2026/src/data/*` | shared snapshots | local-only |
| fixtures/results | football-data.org | openfootball / API-FOOTBALL |
| qualifiers | API-FOOTBALL | official confederation pages |
| events/lineups/stats | API-FOOTBALL | official pages / paid enrichments |
| historical data | football-data.co.uk / openfootball | local CSV |
| xG/advanced | StatsBomb / Understat | FBref |
| odds | The Odds API / local harvesters | other odds providers |
| news | FIFA / BBC / official sites | manual |
| weather | OpenWeather | Visual Crossing |

## 11. Refresh Cadence

| Dataset | Pre-match | Matchday | Post-match |
| --- | --- | --- | --- |
| fixtures | daily | every 6h | daily |
| results/status | daily | 1-5 min | confirm 1-3 times |
| events | none | 5-10 min | final pull |
| lineups | T-90/T-60/T-30 | active | confirm |
| stats | none | 10-15 min | final pull |
| odds | every 1-3h | every 15-30 min in final window | stop |
| injuries/news | 2-4 times/day | every 2-4h | stop |
| weather | every 6h | every 1h | stop |
| predictions | on input change | T-6h / T-1h | archive |

世界杯和大型杯赛比赛日需要额外规则：

- 如果比赛进入加时赛或点球大战，结果轮询不能在常规 90 分钟后停止
- 如果同组最后一轮或淘汰赛阶段存在多场同时开球，采集必须支持并发处理

建议在 `configs/schedules/matchday.json` 中明确：

- `continue_on_extra_time`
- `continue_on_penalties`
- `concurrent_match_handling`

## 12. Processing Stages

### Fetch

保存原始响应到 `data/raw`

对于已经在本地项目中落地的数据，不再重复走外部接口抓取。当前 `worldcup/2026` 已有的：

- `groups`
- `groupFixtures`
- `groupStageMatches`
- `bracket`
- `fullSchedule`
- `finalsMatchResults`
- `finalsDataCoverage`
- `qualifierMatches`

优先通过：

- `scripts/import_worldcup_site_local_data.mjs`

迁移到共享层，作为本地静态输入源。

### Normalize

统一字段、时间、队名、阶段、比分结构

### Merge

多源按优先级合并，避免每个消费项目各自做选择逻辑

### Validate

检测缺失、冲突、重复和结构异常

### Publish

输出：

- `data/public/*`
- `data/model/*`
- `reports/*`

当前世界杯已具备一个可重复执行的串行发布入口：

- `scripts/publish_all_world_cup_data.py`

它按顺序重建：

1. `worldcup/2026` 本地数据镜像导入
2. `results`
3. `standings`
4. `finals detail datasets`
5. `model datasets`
6. `data_coverage`

当需要赛前上下文时，该入口还可以先执行：

- `--capture-context`

即先调用：

- `scripts/capture_world_cup_context_from_predictor.py`

再继续后续发布。

此外，平台提供统一健康报告入口：

- `scripts/build_source_health_report.py`

它聚合：

- `public` 数据集数量
- `model` 数据集数量
- `coverage` 可用率
- 世界杯 / 预选赛导入报告

为减少跨仓库人工操作，平台还提供一个跨仓库上下文采集触发器：

- `scripts/capture_world_cup_context_from_predictor.py`

它负责调用预测项目的 `run_scheduled_maintenance.py`，只执行世界杯 context capture，
然后再由平台自己的 `build_world_cup_model_datasets.py` 消费生成的 snapshots。

写入权限必须明确：

- `data/raw/`：只由 fetch / source adapter 写入
- `data/normalized/`：只由 normalize / merge 流程写入
- `data/model/`：允许预测系统或模型脚本写入，作为模型侧输出落点
- `data/public/`：只允许 publish 流程写入，任何消费项目不得直接写
- `reports/`：只由 validate / publish 流程写入

因此，预测项目不应直接写 `data/public/predictions.json`，而应先写：

- `data/model/predictions.json`

再由平台 publish 流程做：

- 校验
- 去重
- 契约格式化
- 合并到 `data/public/predictions.json`

## 13. Multi-Competition Design

平台必须是配置驱动，而不是写死世界杯。

配置示例：

- `configs/competitions/fifa_world_cup.json`
- `configs/competitions/premier_league.json`
- `configs/competitions/champions_league.json`
- `configs/competitions/uefa_euro.json`

每个赛事配置定义：

- `competition_id`
- `season_format`
- `supported_datasets`
- `provider_priority`
- `polling_schedule`

## 14. Phases

### Phase 1

先打通：

- `canonical_teams`
- `teams`
- `fixtures`
- `results`
- `qualifier_matches`
- `predictions`
- `data_coverage`

### Phase 2

增加：

- `events`
- `lineups`
- `match_stats`
- `odds_snapshots`
- `prematch_context`

### Phase 3

平台化：

- database
- scheduling
- source health dashboard
- quota tracking
- automated conflict checks

## 15. Local Development and Mock Mode

平台必须支持在没有真实 API key 的情况下运行最小开发流程。

建议：

- 提供 `data/fixtures/` 或 `data/mock/` 目录，存放本地测试输入
- fetch 脚本支持 `--mock` 或等价模式
- CI 和新成员本地启动时，可以只依赖 mock 数据完成 schema 校验、publish 流程和消费方联调

mock 模式的目标不是替代真实采集，而是保证：

- 无 key 时也能开发
- 无网络时也能调试
- CI 环境也能跑基础契约校验

## 16. Documentation Rule

本文件是该项目当前主设计基线。

凡是影响以下内容的改动，都必须同步更新本文件：

- 架构
- 目录结构
- 数据集
- schema
- 数据源
- 优先级
- 刷新频率
- 消费方边界
- 多赛事扩展方式

如果实现已变而文档未更新，则任务未完成。
