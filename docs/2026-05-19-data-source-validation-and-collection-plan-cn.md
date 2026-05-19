# 足球数据源验证与采集总计划

日期：2026-05-19  
项目：`football-data-platform`  
状态：执行基线  
主设计基线：`DESIGN.md`  
关联调研归档：`docs/2026-05-19-data-source-research-status-cn.md`

## 1. 原则

后续不再围绕单个数据源无限深入。所有数据工作按下面顺序推进：

1. 明确两个消费项目需要哪些数据。
2. 列出每类数据可能来源。
3. 对每个来源做最小可验证 probe。
4. 明确能拿什么、不能拿什么、为什么不能拿。
5. 给每个来源打标签：`production`、`model_only`、`experimental_only`、`manual_patch`、`pass`。
6. 决定采集方式和频率：一次性、定期、赛前窗口、赛后、持续采样。
7. 只在通过 gate 后进入 `normalized`、`model` 或 public API。
8. 未通过 gate 的来源只允许写 `reports/` 或 `data/raw/experimental/`。

## 2. 数据分层

| 层级 | 目录 / 输出 | 允许内容 | 禁止内容 |
|---|---|---|---|
| raw experimental | `data/raw/experimental/*` | 非官方、逆向、低频实验原始数据 | 直接给前端或模型生产读取 |
| reports | `reports/*.json` | probe 结果、覆盖率、候选集、失败原因 | 作为事实数据源发布 |
| normalized | `data/normalized/*` | 通过 schema、ID 映射和来源审查的标准数据 | 未验证爬虫、name-only 匹配 |
| model | `data/model/*` | 模型专用、可解释、已标 source/confidence 的数据 | 无来源状态的空值/0 |
| public API | `data/public/api/*` | 展示站可直接消费的数据 | experimental-only、低置信赔率、未授权数据 |

## 3. 验证状态定义

| 状态 | 含义 | 可进入 normalized/public |
|---|---|---|
| `verified_production` | 官方或授权源，字段/ID/刷新可验证 | 可以 |
| `verified_model_only` | 字段可用但只适合模型内部，不适合公开展示 | 只能 model |
| `verified_experimental` | live 或离线验证可用，但有授权/稳定/ID 风险 | 不可以 |
| `metadata_only` | 只看过文档或代码，未 live 验证 | 不可以 |
| `blocked` | 网站/套餐/接口不支持 | 不可以 |
| `pending_window` | 数据只能临近比赛或赛后获得 | 暂不可以 |
| `pending_key_or_plan` | 缺 key 或套餐受限 | 不可以 |

## 4. 总控矩阵

### 4.1 世界杯展示站 P0/P1 数据

| 数据 | 当前状态 | 候选源 | 已验证结果 | 采集方式 | 采集频率 | 清洗 / 归并 |
|---|---|---|---|---|---|---|
| 104 场正赛赛程 | 已提供 | FIFA/本地赛程/openfootball/football-data.org | 平台已有 `fixtures`，UTC 已补齐 | 静态导入 + 校验 | 赛前每日，赛程变更时立即 | canonical `match_id`、`date_utc/kickoff_at`、venue/team slug |
| 球队基础信息 | 已提供 | 本地 canonical、FIFA、Reep | 已有 48 队 | 静态维护 | 低频 | `team_id` 为 canonical slug，别名归并 |
| 小组/淘汰赛结构 | 已提供 | FIFA/本地配置 | 已发布 | 静态配置 | 赛程变化时 | group/stage/round 标准化 |
| 主教练 | 已提供基础版 | FIFA、足协官网、Reep、Transfermarkt/Wikidata | 48 队主教练已发布；上任/合同缺结构化源 | 官方优先 + manual patch | 每周，名单公告期每日 | `staff_id`、role、source_status |
| 球队世界杯历史 | 已提供 | openfootball、Wikipedia/FIFA 校验 | 44 队有历史，4 队无参赛史 | 静态导入 | 低频 | 年度汇总优先，逐场可后补 |
| 最近 10 场国家队 | 已提供基础版 | 国际赛历史 CSV、API-FOOTBALL、FIFA | 基础比分已可用，高级统计缺 | 离线导入 + API 补 | 每周/赛前每日 | team name alias -> canonical team_id |
| 球员名单 | 部分提供 | FIFA/足协官方名单 | 9 队 234 人 | 官方名单导入 | 名单公布期每日 | 只采官方名单；第三方只补事实字段 |
| 城市/球场 | 已提供基础版 | FIFA、场馆官网、Wikipedia/OpenStreetMap | `venue_id/host_city_id` 已统一 | 静态导入 | 低频 | capacity/surface/roof/altitude/source_urls |
| 正赛赛果 | 待比赛 | football-data.org、API-FOOTBALL、FIFA | 正赛未开始 | API + 赛后校验 | 赛后一次；如需要可比赛日轮询 | score/status/period 标准化 |
| 赛后事件/技术统计 | 待比赛 | API-FOOTBALL、Sofascore experimental、FIFA match report | Sofascore wrapper 可拿事件/统计，但 experimental | 赛后采集 | 赛后一次，复核一次 | 不稳定源只进 raw/report，授权源才进 normalized |

### 4.2 模型 P0/P1 数据

| 数据 | 当前状态 | 候选源 | 已验证结果 | 采集方式 | 采集频率 | 清洗 / 归并 |
|---|---|---|---|---|---|---|
| feature inputs / fixtures | 已提供 | 平台 core fixtures | 已切平台严格读取 | publish pipeline | 每次发布 | `kickoff_at` 必填，UTC |
| 主客/中立拆分 | 已提供基础版 | fixtures + venues | 中立场已保留 | 派生 | 每次 fixture 更新 | 不强行把国家队中立赛归主客 |
| 赛程负荷 | 已提供基础版 | fixtures/recent matches | 休息天数可用，旅行距离缺 | 派生 | 每次赛程更新 | 需要 venue/team coordinates |
| 球队高级状态 | 部分提供 | FBref、Sofascore、API-FOOTBALL、StatsBomb/WhoScored | 当前多为基础 proxy；Sofascore experimental 可取控球/射门/xG | 先 report/raw，再 model-only | 每周/赛前 | 缺字段为 null，不填 0 |
| 赔率 1X2/AH/OU | 缺生产源 | Odds-API.io、BSD/Bzzoiro、TheOddsAPI Business、雷速 experimental | Odds-API.io 可取足球 AH/OU；World Cup 未验证；BSD 无 AH/World Cup 映射 | experimental sampling | 比赛前 5 天复查；若可见再 T-24/T-6/T-1/closing | `market/bookmaker/line/odds/captured_at/snapshot_type` |
| 确认首发 | 待窗口 | FIFA match centre、API-FOOTBALL、Sofascore experimental | 只能赛前 60-90 分钟 | API/官方页 | T-90/T-60/T-30/T-15 | `confirmed` 后不可覆盖，只新增快照 |
| 伤停/停赛 | 部分 evidence | FIFA/足协/新闻、API-FOOTBALL、Transfermarkt | API-FOOTBALL free 对 WC 2026 restricted；新闻只做 evidence | 官方/新闻抽取 | 赛前 7 天每日，赛前 48h 加密 | status/confidence/evidence_url，不把无命中当无伤停 |
| 天气 | 状态行已提供 | Open-Meteo、OpenWeather | Open-Meteo 可 fallback，赛前 16 天窗口 | API | T-72/T-24/T-6/T-1 | venue lat/lon -> forecast |
| 裁判画像 | 英超样本可用 | FIFA 指派、football-data.co.uk、worldfootball | 世界杯裁判指派待官方 | 历史派生 + 官方指派 | 指派公布后；赛后补执法 | sample_size < 20 不入强结论 |
| 球员影响力 | 候选中 | FBref EPL、Transfermarkt、Sofascore experimental、FPL/俱乐部数据 | FBref 命中 31 个 review-ready EPL 候选，但 xG/xA 列不可用 | report-only -> model-only 评估 | 赛前每周/名单更新后 | player_id 映射、字段置信度、zero-only 防误用 |

### 4.3 赔率源验证矩阵

| 源 | 当前状态 | 能拿什么 | 不能确认 / 问题 | 下一步 |
|---|---|---|---|---|
| Odds-API.io free | `verified_experimental` | 足球 ML、Spread/AH、Totals/OU；Sbobet + Bet365 | 免费层 2 家书商；World Cup/成年国家队未可见；不能做共识/CLV | 世界杯首场前 5 天重跑 event scan |
| BSD/Bzzoiro | `verified_experimental` for 1X2/OU | 通用 odds、15 bookmaker、1X2/OU/BTTS/DC/DNB | World Cup `league_id=16&season_id=82` 返回 0；AH 未文档化 | 找真实 World Cup event mapping；若无 AH 则降级 |
| TheOddsAPI | `blocked_by_plan` | 免费只 NBA/MLB | 足球需 Business $99/月 | 只有正式做 AH/OU/CLV 再评估 |
| API-FOOTBALL odds | `blocked_by_plan_current_free_key` | 当前 Free key 对 WC 2026 fixtures/odds 返回 plan restricted | 拿不到 sample fixture id，lineups/injuries/events/statistics 只能等套餐升级或比赛窗口后重验 | 若升级 Pro 或以上，重跑 `scripts/probe_api_football_worldcup_runtime.py` |
| 雷速类 | `metadata_only` | 旧项目代码有比分/1X2/AH/OU 字段解析 | 未 live 验证；逆向/页面/合规风险 | 仅如必要建立 raw experimental probe |

### 4.4 高级统计源验证矩阵

| 源 | 当前状态 | 能拿什么 | 不能确认 / 问题 | 下一步 |
|---|---|---|---|---|
| Sofascore wrappers | `verified_experimental` | 控球、射门、射正、传球、xG、shotmap、阵容、事件、评分等 | 非官方；World Cup event mapping 未验证；PPDA 无直接字段 | 只对国际赛/世界杯 event 做低频 raw 实验 |
| soccerdata FBref | `verified_experimental` | EPL team/player stats、赛程、场馆、裁判、部分 lineup/events | live 会挂/反爬；世界杯国家队不稳定 | 用本地/缓存补 EPL 球员和球队 proxy |
| FBref local player asset | `verified_model_candidate` | 31 个世界杯球员候选的 90s/Starts/Gls/Ast | xG/xAG/PrgP/Tkl/Int 全为 zero-only；无 FBref native id | 只给模型评估，不写 public |
| soccerdata FotMob | `blocked` | 无 | 本机 soccerdata 1.9.0 无 FotMob reader | 暂停，除非单独找 FotMob 包 |
| WhoScored | `metadata_only/experimental` | events/missing players 理论可推导部分指标 | 高反爬；未 live 稳定验证 | 后置 |
| StatsBomb Open Data | `pending_scope` | 事件/xG 样本 | 覆盖赛事有限，不保证 2026 WC | 适合训练/规则样本，不做实时 |

### 4.5 人物数据源验证矩阵

| 数据 | 当前源 | 当前状态 | 缺口 | 下一步 |
|---|---|---|---|---|
| 球员基础事实 | FIFA/足协名单、Transfermarkt dataset、Reep | 9 队已补，第三方字段可用 | 剩余 39 队官方名单 | 等官方名单，第三方只补 DOB/club/height 等 |
| 球员近期俱乐部表现 | FBref EPL local asset、Sofascore experimental | FBref 31 个候选 | 非英超、xG/xA/评分缺 | 继续找授权/稳定联赛源 |
| 主教练基础事实 | FIFA/manual/Reep | 已有 48 队 | appointed_at/contract_until | Wikidata/足协公告/Transfermarkt manager profile 交叉验证 |
| 裁判画像 | football-data.co.uk EPL | 英超样本可用 | 世界杯裁判名单/指派 | 等 FIFA 官方公布后接入 |

## 5. 采集频率策略

| 数据类型 | 采集方式 | 频率 |
|---|---|---|
| 静态事实：球队、城市、球场、历史战绩 | 手动/脚本导入 + source_urls | 低频；变更时更新 |
| 官方名单/教练/裁判名单 | 官方源监控 + manual patch | 名单期每日；平时每周 |
| 近期比赛基础结果 | 历史 CSV/API | 每周；赛前每日 |
| 赔率 event 可见性 | Odds-API.io/BSD probe | 世界杯首场前 5 天必须复查 |
| 赔率快照 | 若 World Cup 可见才采 | T-24/T-6/T-1/closing；免费源只实验 |
| 伤停/新闻 evidence | 官方/新闻 | 赛前 7 天每日，赛前 48h 每 6-12h |
| 天气 | Open-Meteo/OpenWeather | T-72/T-24/T-6/T-1 |
| 确认首发 | 官方/API | T-90/T-60/T-30/T-15 |
| 赛后技术统计 | 授权 API/官方报告/experimental wrappers | 赛后一次，必要时复核 |

## 6. 清洗与归并规则

- 所有时间统一 UTC ISO 8601。
- 所有球队用 canonical `team_id`。
- 所有比赛用平台 `match_id`，外部 ID 只放 `source_refs`。
- 所有人物用平台 `person_id/player_id`，第三方 ID 只作辅助映射。
- 缺失字段必须是 `null` 或明确 `source_status/status_reason`，不得填 0。
- `zero_only_fields` 必须显式标记，不能被模型解释为真实 0。
- experimental 来源默认不得覆盖 production 来源。
- 多源冲突时按来源优先级、更新时间、字段置信度合并。
- 模型专用候选数据进入 `reports` 或 `data/model` 前必须有 `confidence` 和 `production_write_allowed/public_write_allowed` 标记。

## 7. 下一步执行顺序

1. 完成主办球场增强：capacity、surface、roof_type、altitude、source_urls。
2. 建立官方名单 source checklist：剩余 39 队官方名单公布后快速导入。
3. 继续验证 FBref/英超球员候选是否可以成为 `model_only` 数据，不进入 public。
4. 对 Sofascore wrapper 做世界杯/成年国际赛 event mapping 低频 raw 实验。
5. 世界杯首场前 5 天重跑 Odds-API.io event scan。
6. 若升级 API-FOOTBALL Pro 或以上，重跑 `scripts/probe_api_football_worldcup_runtime.py` 验证 odds、lineups、injuries、statistics、events。
7. 如果仍缺生产级赔率，最后再评估付费源。

## 8. 当前明确不做

- 不把雷速、OddsPortal、Sofascore wrapper 等逆向/非官方源直接写入 `normalized` 或 public API。
- 不因为一个源能返回字段就立即接生产。
- 不把免费赔率两家书商当市场共识。
- 不把 FBref 当前本地资产里的 zero-only xG/xA/防守列当真实数据。
- 不在比赛开始前强行采确认首发。
