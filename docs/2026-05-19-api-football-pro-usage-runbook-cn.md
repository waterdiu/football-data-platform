# API-FOOTBALL Pro 使用手册

日期：2026-05-19  
项目：`football-data-platform`  
适用套餐：API-FOOTBALL Pro，$19/月，7,500 requests/day，1 seat  
状态：待用户升级后执行  
主设计基线：`DESIGN.md`

## 1. 目标

如果 2026-05-20 之后升级 API-FOOTBALL Pro，本平台把它作为 2026 世界杯 runtime 数据的优先生产候选源，但必须按配额管理，不允许无计划轮询。

目标：

- 世界杯前：验证 coverage、建立 API fixture/team/player 映射、补球队/球员/教练/伤停/赔率可用性。
- 世界杯中：每天稳定获得当日比赛赛果、事件、阵容、技术统计、球员评分、赔率快照、伤停状态。
- 世界杯后：归档 104 场完整赛果、事件、阵容、技术统计、球员统计/评分、射手榜、纪律榜，并补齐人物/球队画像。
- 空余请求：优先分配给数据质量复核、历史近期比赛补强、球员/教练/伤停画像，不用于无目的高频抓取。

## 2. 官方约束

| 项目 | Pro 套餐规则 | 处理方式 |
|---|---|---|
| 日额度 | 7,500 requests/day | 平台每日预算按 5,000 上限设计，保留 2,500 安全余量 |
| 分钟限额 | 300 requests/min | 平台限速设为不超过 120/min，默认串行/小批量 |
| 响应头 | `x-ratelimit-requests-limit`、`x-ratelimit-requests-remaining`、`X-RateLimit-Limit`、`X-RateLimit-Remaining` | 每次采集写入 quota ledger |
| 超额策略 | 达到额度后 API 停止处理请求，不额外收费 | 低优先级任务自动停止 |
| 免费层限制 | Free plan 对部分 season 受限 | Pro 升级后必须重跑 coverage probe |

官方依据：

- Pricing: https://www.api-football.com/pricing
- Rate limit: https://www.api-football.com/news/post/how-ratelimit-works
- World Cup 2026 guide: https://www.api-football.com/news/post/fifa-world-cup-2026-guide-to-using-data-with-api-sports
- Save API calls: https://www.api-football.com/news/post/how-to-save-calls-to-the-api
- Bulk fixtures by ids: https://www.api-football.com/news/post/how-to-get-all-fixtures-data-from-one-league

## 3. 总原则

1. 先 coverage，后采集。
2. 先批量，后单场。
3. 先状态行，后事实行。
4. 先当天比赛，后历史补强。
5. 先写 `data/raw/api-football` 和 `reports`，通过 schema/ID 映射后再进 `normalized/model/public`。
6. 所有请求必须记录 endpoint、params、request_count、remaining quota、run_id、trigger、purpose。
7. 不把无返回解释为“没有数据”，必须记录 `source_status/status_reason`。
8. odds 只保留赛前/临场时间戳快照，不用赛后赔率冒充赛前赔率。

## 4. 可获得数据

| 数据 | 端点 | 用途 | 采集条件 | 进入层级 |
|---|---|---|---|---|
| coverage | `/leagues?id=1&season=2026` | 判断 events/lineups/statistics/players/injuries/odds 是否支持 | 升级后立即，之后每日 | reports/runtime health |
| 104 场 fixture ID | `/fixtures?league=1&season=2026` | API fixture id 映射、赛程校验 | 升级后立即，赛程变化时 | runtime map/normalized |
| 比分/状态 | `/fixtures?league=1&season=2026&date=YYYY-MM-DD` 或 `/fixtures?ids=...` | 展示站赛果、模型结算 | 比赛日/赛后 | normalized/public/model |
| 批量比赛详情 | `/fixtures?ids=ID1-ID2...`，最多 20 ids | 节省请求，获取 fixture 及嵌入的 events/lineups/statistics/players | 比赛中/赛后 | raw -> normalized |
| 事件 | `/fixtures/events?fixture=ID` | 进球、红黄牌、换人、VAR、点球 | 比赛中/赛后；仅当批量详情缺字段时 | normalized/public |
| 技术统计 | `/fixtures/statistics?fixture=ID` | 控球、射门、射正、传球、角球、犯规等 | 比赛中/赛后 | normalized/model/public |
| 球员统计/评分 | `/fixtures/players?fixture=ID` | 球员评分、分钟、射门、传球、防守、进球助攻 | 比赛中/赛后 | normalized/model/public |
| 阵容 | `/fixtures/lineups?fixture=ID` | 确认首发、替补、阵型 | 赛前 30-60 分钟通常出现 | normalized/model/public |
| 伤停/停赛 | `/injuries?league=1&season=2026` 或 `/injuries?fixture=ID` | 赛前可用性、模型降权 | coverage.injuries=true 后 | normalized/model |
| 球员名单 | `/players?league=1&season=2026&page=N` | 球员档案、照片、年龄、身高体重 | coverage.players=true 后 | normalized/public |
| 教练 | `/coachs?team=TEAM_ID` | 主教练 DOB、国籍、履历、上任时间 | 建立 team_id 映射后 | normalized/public |
| 积分榜 | `/standings?league=1&season=2026` | 小组积分 | 比赛开始后 | public |
| 射手/助攻/黄红牌榜 | `/players/topscorers`、`/players/topassists`、`/players/topyellowcards`、`/players/topredcards` | 统计页 | 比赛开始后 | public |
| 预测 | `/predictions?fixture=ID` | 第三方模型参考，不覆盖自有模型 | 可选，低优先级 | reports/model-only |
| 赛前赔率 | `/odds?fixture=ID` | 1X2/AH/OU 快照；仅近 7 天 | 比赛前 7 天内 | model-only |
| 即时赔率 | `/odds/live?fixture=ID` | live odds 实验 | 默认不采，除非模型明确需要 | raw/model-only |
| H2H | `/fixtures/headtohead?h2h=TEAM_A-TEAM_B` | 历史交锋 | 赛前报告可选 | reports/model-only |

## 5. 请求预算

### 5.1 每日硬预算

| 档位 | 请求数 | 用途 |
|---|---:|---|
| P0 生产采集 | 0-1,500/day | 当日比赛、赛前窗口、赛后归档 |
| P1 补强采集 | 0-1,500/day | 球员、教练、伤停、积分榜、榜单、近期数据 |
| P2 实验/复核 | 0-1,000/day | predictions、H2H、异常复核、字段验证 |
| 安全余量 | >=2,500/day | 防止重跑、失败重试、临时修复 |
| 绝对停止线 | remaining < 1,000 | 停止 P1/P2，只保留 P0 |

设计上正常比赛日不应超过 1,000 请求。7,500/day 足够，但要避免“看起来很多就乱抓”。

### 5.2 请求优先级

| 优先级 | 数据 | 可停吗 |
|---|---|---|
| P0 | coverage、fixture id map、当日比分/状态、确认阵容、赛后事件/统计/球员评分、赛前关键伤停 | 不可停 |
| P1 | odds 快照、积分榜、射手榜、球员名单、教练档案 | quota 低时可降频 |
| P2 | predictions、H2H、历史补采、异常二次校验 | quota 低时停 |
| P3 | live odds、重复拉取已 confirmed 阵容、已归档比赛重复统计 | 默认停 |

## 6. 世界杯前使用方案

时间范围：升级后到 2026-06-10。

### 6.1 升级当天一次性验证

| 任务 | 请求估算 | 说明 |
|---|---:|---|
| `/leagues?id=1&season=2026` | 1 | 检查 coverage flags |
| `/fixtures?league=1&season=2026` | 1 | 建立 API fixture id map |
| `/teams?league=1&season=2026` | 1 | 建立 API team id map |
| `/players?league=1&season=2026&page=N` | 2-10 | 分页直到无下一页 |
| `/coachs?team=TEAM_ID` | 48 | 48 队教练 |
| `/injuries?league=1&season=2026` | 1 | 如果 coverage 支持 |
| `/standings?league=1&season=2026` | 1 | 若已可用 |
| `/odds?league=1&season=2026` 或按 fixture | 1-104 | 仅验证可用性，不全量刷 |

升级当天总量约 60-170 请求，远低于 7,500。

### 6.2 世界杯前日常

| 数据 | 频率 | 请求估算 |
|---|---|---:|
| coverage | 每日 1 次 | 1 |
| fixtures | 每日 1 次 | 1 |
| injuries league-level | 每日 2-4 次 | 2-4 |
| players | 每周 1-2 次；最终名单窗口每日 | 2-10 |
| coachs | 每周 1 次 | 48 |
| odds visibility | 进入比赛前 7 天后，仅未来 7 天 fixtures | 1-48 |
| predictions | 可选，仅未来 7 天 fixtures | 0-48 |

世界杯前正常每日应控制在 10-150 请求。

## 7. 世界杯比赛日使用方案

### 7.1 当日开赛前

| 时间 | 任务 | 请求策略 |
|---|---|---|
| T-72h | odds、injuries、weather 外部源同步 | API-FOOTBALL odds 每场 1 次 |
| T-24h | odds、injuries、predictions 可选 | 每场 2-3 次 |
| T-6h | odds、injuries、fixture status | 每场 2-3 次 |
| T-90/T-60/T-30 | lineups | 每场最多 3 次；一旦 confirmed 停止 |
| T-15 | final lineups check | 仅未 confirmed 的场次 |

单场赛前请求预算：

| 项 | 请求数 |
|---|---:|
| odds 快照 | 3-6 |
| injuries | 2-4 |
| lineups | 2-4 |
| predictions 可选 | 0-2 |
| fixture status | 1-2 |
| 合计 | 8-18 |

4 场比赛日约 32-72 请求。

### 7.2 比赛中

当前 `worldcup/2026` 不要求直播级页面，模型也不需要秒级 live。因此默认不按官方 15 秒更新频率抓。

推荐策略：

| 场景 | 频率 | 请求策略 |
|---|---|---|
| 无直播需求 | 每 15 分钟 | `/fixtures?live=all` 或当日 fixture 批量状态 |
| 需要基础 live score | 每 5 分钟 | 只拉 live fixtures，保存比分/状态/events |
| 需要技术统计跟踪 | 每 10-15 分钟 | `/fixtures?ids=...` 批量取所有进行中比赛 |
| 加时/点球 | 继续采 | status 为 `ET/P/BT` 时不停 |
| 同时开球 | 批量 ids | 最多 20 场一组，世界杯同组末轮两场可 1 个请求处理 |

比赛中请求估算：

| 模式 | 3 小时比赛窗口请求数 |
|---|---:|
| 15 分钟轻量 | 12 |
| 5 分钟比分 | 36 |
| 10 分钟详情 | 18 |
| 5 分钟比分 + 10 分钟详情 | 54 |

即使 4 场比赛分散开，也通常 <250 请求/日。

### 7.3 赛后归档

赛后归档是最重要的数据质量环节。

| 时间 | 任务 | 请求策略 |
|---|---|---|
| FT 后 15 分钟 | 初版归档 | `/fixtures?ids=...` 批量取详情 |
| FT 后 2 小时 | 复核 | 再拉一次批量详情 |
| 次日 06:00 UTC | 最终归档 | 再拉一次已完成比赛 |
| 如批量详情缺字段 | 单端点补 | events/statistics/players/lineups 按缺字段补 |

单场赛后请求预算：

| 方式 | 请求数 |
|---|---:|
| 批量详情足够 | 1/20 场，实际单日通常 1-2 |
| 单端点补全 | 最多 4/场 |
| 4 场比赛日极端补全 | 16-20 |

## 8. 世界杯后使用方案

时间范围：决赛结束后 7-14 天。

目标是把 104 场全部归档完整，而不是继续高频采。

| 任务 | 请求估算 | 说明 |
|---|---:|---|
| 获取 104 场最终 fixture id/status | 1 |
| 批量详情 `/fixtures?ids=`，20 场一组 | 6 | 104 场约 6 组 |
| 缺字段补 events/statistics/players/lineups | 0-416 | 只对缺字段单场补 |
| standings/topscorers/topassists/cards | 4-6 | 统计页 |
| players 全量分页 | 2-10 | 球员档案最终版 |
| coachs 48 队 | 48 | 教练档案最终版 |

世界杯后一次完整复核一般 <500 请求。

## 9. 空余请求如何分配

空余请求不是每天必须用完。只有在明确能提升数据质量时才用。

| 优先级 | 用途 | 触发条件 |
|---|---|---|
| 1 | 缺字段补采 | data-quality 显示 match stats/events/player stats missing |
| 2 | 球员/教练档案补全 | profiles 缺 DOB、身高体重、照片、career |
| 3 | 伤停历史 `/sidelined` | 只对核心球员或已伤停球员 |
| 4 | H2H/近期比赛 | 只对即将比赛的对阵 |
| 5 | API predictions 对照 | 只作为报告参考，不覆盖自有模型 |
| 6 | odds 快照加密 | 只在模型确认 AH/OU/CLV 需要时 |

禁止：

- 为了“用完额度”重复抓已确认数据。
- 对所有球员无限制拉 `/sidelined`。
- 对所有比赛每分钟拉单端点。
- 在 coverage false 时继续刷对应 endpoint。

## 10. 采集任务设计

### 10.1 必须新增/改造的脚本

| 脚本 | 职责 |
|---|---|
| `scripts/probe_api_football_worldcup_runtime.py` | 升级后重跑 coverage/endpoint probe |
| `scripts/collect_api_football_worldcup_daily.py` | 每日低频采集 coverage、fixtures、injuries、standings、odds visibility |
| `scripts/collect_api_football_matchday.py` | 比赛日按 T-window 和 live/post-match 采集 |
| `scripts/archive_api_football_worldcup.py` | 赛后/赛后 7 天完整归档 |
| `scripts/build_api_football_quota_report.py` | 汇总当日请求、剩余额度、错误、跳过原因 |

### 10.2 必须新增的状态文件

| 文件 | 用途 |
|---|---|
| `data/runtime/api_football_fixture_map.json` | 平台 match_id -> API fixture id |
| `data/runtime/api_football_team_map.json` | 平台 team_id -> API team id |
| `data/runtime/api_football_collection_state.json` | 每场比赛最近一次采集时间、确认状态、缺字段 |
| `reports/api_football_quota_report.json` | 每日请求消耗和 remaining quota |
| `reports/api_football_coverage_report.json` | coverage flags 和可用端点 |

### 10.3 原始数据保存

建议目录：

```text
data/raw/api-football/worldcup-2026/
  coverage/
  fixtures/
  fixtures-by-ids/
  lineups/
  injuries/
  odds/
  statistics/
  players/
  events/
```

所有 raw 文件必须带：

- `fetched_at`
- `endpoint`
- `params`
- `http_status`
- `rate_limit`
- `source_status`
- `payload`

## 11. 生产化 gate

一个 API-FOOTBALL 数据集进入 `normalized/model/public` 前必须满足：

1. endpoint 在 coverage 中为 true，或有实际 payload 证明可用。
2. API fixture/team/player id 已映射到平台 ID。
3. 字段含义已写入 schema 或 transform。
4. 缺失字段用 `null`，不填 0。
5. 有 `source_status`、`confidence`、`fetched_at`、`source_refs`。
6. 有 quota 记录。
7. 与现有平台事实冲突时，不直接覆盖官方/FIFA/manual canonical 数据。

## 12. 数据归并优先级

| 数据 | 主源优先级 |
|---|---|
| 赛程/开球时间 | 平台 canonical/FIFA/football-data.org > API-FOOTBALL |
| 赛果/状态 | football-data.org/API-FOOTBALL/FIFA 交叉校验 |
| 事件/技术统计/球员评分 | API-FOOTBALL > Sofascore experimental |
| 阵容 | FIFA match centre/API-FOOTBALL > BBC/Sofascore experimental |
| 伤停 | FIFA/足协官方 > API-FOOTBALL > 新闻 evidence |
| 赔率 | 授权 odds provider > API-FOOTBALL > experimental free source |
| 球员/教练档案 | FIFA/足协官方 > API-FOOTBALL > Reep/dcaribou 补充 |

## 13. 每日 runbook

### 非比赛日

1. 00:00 UTC：coverage + fixtures + standings。
2. 06:00 UTC：injuries league-level。
3. 12:00 UTC：未来 7 天 odds visibility。
4. 18:00 UTC：players/coachs 增量，名单窗口期才跑。
5. 生成 quota/data-quality/source-health 报告。

目标：<150 requests/day。

### 比赛日

1. 00:00 UTC：coverage + 当日 fixtures + standings。
2. 每场 T-24/T-6/T-1：odds + injuries。
3. 每场 T-90/T-60/T-30/T-15：lineups，confirmed 后停止。
4. 比赛中：默认 10-15 分钟批量详情；如无 live 需求可降为 15 分钟比分状态。
5. FT+15m、FT+2h、次日 06:00 UTC：赛后归档。
6. 生成 quota/data-quality/source-health。

目标：普通比赛日 <1,000 requests/day；高峰日 <1,500 requests/day。

### 赛后归档周

1. 每日全量批量详情 104 场，最多 6 请求。
2. 对缺字段场次单端点补。
3. 更新 standings/topscorers/topassists/cards。
4. 锁定 final archive 后停止高频采集。

目标：<500 requests/day。

## 14. 告警

| 条件 | 处理 |
|---|---|
| remaining < 2,500 | 停止 P2 |
| remaining < 1,000 | 只保留 P0 |
| minute remaining < 50 | 降速，暂停并发 |
| coverage 从 true 变 false | 标记 provider anomaly，不删除已有数据 |
| lineups T-30 仍 missing | 触发 FIFA/BBC/Sofascore experimental fallback 提醒 |
| FT+2h statistics/players still missing | 标记 post_match_incomplete，次日复核 |

## 15. 升级后第一件事

升级 Pro 后立即执行：

```bash
python3 scripts/probe_api_football_worldcup_runtime.py
```

预期变化：

- `/fixtures?league=1&season=2026` 不再返回 `plan_restricted`。
- report 能拿到 `sample_fixture_id`。
- 如果 fixture-scoped endpoints 当前仍 empty，需要看原因：未开赛/未到阵容窗口/coverage false，而不是继续盲刷。

然后再实现/启用正式 collector。
