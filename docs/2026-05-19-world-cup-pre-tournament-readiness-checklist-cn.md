# 2026 世界杯开赛前数据 Readiness Checklist

日期：2026-05-19  
项目：`football-data-platform`  
状态：执行清单  
主设计基线：`DESIGN.md`  
关联文档：

- `docs/2026-05-19-api-football-pro-usage-runbook-cn.md`
- `docs/2026-05-19-data-source-validation-and-collection-plan-cn.md`
- `docs/2026-05-19-data-source-research-status-cn.md`
- `reports/data-quality.json`

## 1. 目标

这份清单用于 2026 世界杯开赛前把数据层从“已设计/部分验证”推进到“可运行/可监控/可降级”。

核心目标：

- 不再临时乱抓数据，所有采集都按优先级、窗口和配额执行。
- API-FOOTBALL Pro 开通后，先验证覆盖，再接生产，不浪费 7,500 requests/day。
- 明确哪些数据已经稳定，哪些必须等赛前窗口，哪些只能实验，哪些需要付费或放弃。
- 给 `worldcup/2026` 和 `world-cup-predictor` 一个清晰的上线前状态判断。

## 2. 当前总状态

| 数据域 | 当前状态 | 判断 |
|---|---|---|
| 核心赛程/球队/城市/球场 | 已可用 | 可支撑展示站基础页面 |
| 104 场 `kickoff_at` | 已补齐 | 模型报告窗口可用 |
| 球队历史/近期比赛基础版 | 已可用 | 展示站可显示，模型可用作基础 proxy |
| 预测结果 | 已可用 | 模型已写回平台，104 场覆盖 |
| 球员名单 | 部分可用 | 9 队已导入，剩余等官方最终名单 |
| 主教练基础档案 | 已可用基础版 | 上任时间/合同仍缺可靠结构化源 |
| 确认首发 | 待窗口 | 只能赛前 60-90 分钟验证 |
| 伤停/停赛 | 部分 evidence | API-FOOTBALL Free 受限，Pro 后重验 |
| 天气 | 状态行可用 | 真实 forecast 需进入预报窗口 |
| 裁判画像 | 英超样本可用 | 世界杯裁判名单/指派等官方 |
| 赔率 1X2/AH/OU | 无生产源 | Odds-API.io 实验可用，世界杯未验证 |
| 赛后事件/技术统计 | 待比赛 | API-FOOTBALL Pro 或官方赛后报告 |
| 高级过程数据 | 部分实验 | Sofascore/FBref 只能 model-only 或 experimental |

## 3. P0 开赛前必须完成

### 3.1 API-FOOTBALL Pro 覆盖复验

触发条件：用户升级 API-FOOTBALL Pro 后立即执行。

执行项：

| 检查 | 目标 | 通过标准 | 失败处理 |
|---|---|---|---|
| coverage flags | 确认 WC 2026 支持项 | `/leagues?id=1&season=2026` 能返回 `fixtures/events/lineups/statistics/players/injuries/odds` 覆盖信息 | 记录 `plan_restricted` 或缺字段，不接生产 |
| fixture id map | 建立 104 场 API fixture id | `/fixtures?league=1&season=2026` 返回可映射 fixture | 无法映射则停止 lineups/events/stats 接入 |
| team id map | 建立 48 队 API team id | `/teams?league=1&season=2026` 可映射 | 缺队伍时只用已有 canonical，API 数据降级 |
| injuries | 验证伤停端点 | `/injuries?league=1&season=2026` 或 fixture 级返回结构可解析 | 若无覆盖，继续用官方/新闻 evidence |
| lineups | 验证阵容端点结构 | 可能赛前窗口前为空，但不能是 plan restricted | 若 plan restricted，不能作为确认首发源 |
| events/statistics/players | 验证赛后端点结构 | 至少 sample fixture 或历史同赛事 fixture 可解析 | 若开赛前无样本，赛后第一场重验 |
| odds | 验证 1X2/AH/OU 可见性 | 能返回 bookmaker、market、line、odds、更新时间 | 若无 AH/OU，只作为低优先级补源 |

执行脚本：

- `scripts/probe_api_football_worldcup_runtime.py`

输出检查：

- `reports/api_football_worldcup_runtime_probe.json`
- `reports/source-health.json`
- `reports/data-quality.json`

### 3.2 官方名单补齐

触发条件：FIFA 或各队足协公布最终名单。

执行项：

| 检查 | 目标 | 通过标准 |
|---|---|---|
| roster source checklist | 48 队官方名单状态 | 每队有 `source_status` 和 `source_url` |
| player direct facts | 姓名、位置、球队、状态 | 不用第三方伪造官方名单 |
| shirt number | 号码 | 只在官方名单确认后写入 public |
| DOB/age/club | 基础字段 | 官方优先，第三方补充需标 source |

输出目标：

- `api/worldcup/2026/core/player-profiles.json`
- `api/worldcup/2026/core/people-index.json`
- predictor `person_profile_snapshot` 的 player 部分

### 3.3 伤停/停赛 evidence

执行项：

| 检查 | 目标 | 通过标准 |
|---|---|---|
| API-FOOTBALL injuries | 授权源可用性 | Pro 后能返回结构化数据或明确 unavailable |
| 官方/新闻 evidence | 关键球员状态 | 每条 evidence 有 URL、时间、source、confidence |
| status 行覆盖 | 104 场 | 无数据时也输出 `source_status/status_reason` |

关键约束：

- 没查到伤停不等于没有伤停。
- 新闻源只能作为 evidence，不能覆盖官方状态，除非来源明确。

### 3.4 赔率实验复查

执行项：

| 源 | 复查时间 | 目标 | 结果处理 |
|---|---|---|---|
| Odds-API.io | 首场前 5 天 | 查 World Cup / senior international event 是否可见 | 可见则做 3-5 场 AH/OU 采样；不可见则维持 experimental |
| API-FOOTBALL Pro odds | Pro 开通后 + 赛前 7 天内 | 验证 1X2/AH/OU 和 bookmaker 字段 | 可用则进入 model-only；不足则不做强 Kelly |
| BSD/Bzzoiro | 空余时间 | 找真实 World Cup event mapping | 找不到则降级为 1X2/OU 实验源 |
| HKJC/雷速 | 暂停主线 | 仅保留实验记录 | 不进 normalized/public/model runtime |

生产门槛：

- 每场至少 3 家 bookmaker 才能作为较可信赔率样本。
- 免费 2 家 bookmaker 只能做实验和报告弱信号。
- 没有 opening/T-24/T-6/T-1/closing 序列时，不能做 CLV 强结论。

## 4. P1 开赛前应完成

### 4.1 天气与场馆

| 检查 | 目标 | 通过标准 |
|---|---|---|
| venue lat/lon | 16 个主办球场 | 全部有坐标 |
| roof/surface/altitude | 场地环境 | 全部有稳定字段或 null + source_status |
| forecast window | 赛前 16 天内 | Open-Meteo fallback 可返回 forecast |
| model weather rows | 104 场 | 每场有状态行，真实 forecast 未到窗口时标 unavailable |

### 4.2 裁判名单与画像

| 检查 | 目标 | 通过标准 |
|---|---|---|
| FIFA 裁判名单 | 获取参赛裁判 | 官方发布后导入 referee profiles |
| referee assignment | 每场指派 | 官方公布后写入 match context |
| historical profile | 画像样本 | `sample_size >= 20` 才能模型弱使用；低于 20 只展示 |

### 4.3 球队高级状态

| 字段 | 当前策略 | 开赛前目标 |
|---|---|---|
| 控球/传球/射门 | API-FOOTBALL Pro 或 Sofascore experimental | 先建立 model-only 候选，不进 public |
| xG/xA | Sofascore/FBref/StatsBomb 候选 | 没稳定源则 null，不填 0 |
| PPDA | 当前无稳定生产源 | 暂不作为强特征 |
| 近 5/10/20 场滚动 | recent matches + API 补强 | 有基础比分，过程数据按源可用性补 |

### 4.4 人物档案快照

目标：支撑模型 D5/D6/D8 和展示站人物页，但不把人物档案变成单独预测模型。

| 模块 | 开赛前可做 | 不足时处理 |
|---|---|---|
| 球员基础能力 | 身价、出场、位置、俱乐部、国家队角色 | confidence 低时只报告，不强修正 |
| 缺阵影响 | availability + ability + importance 初版 | `sample_size < 10` 只 Kelly 降权 |
| 首发强度 | 确认首发窗口后计算 | 无确认首发时用 predicted/unavailable |
| 教练轮换风险 | 新闻/发布会 evidence | 只解释和降权，不直接改概率 |
| 裁判风险 | 历史黄红牌/点球样本 | 样本不足使用赛事平均 |

## 5. P2 空余配额历史回填

触发条件：

- 当天 P0/P1 已完成。
- API-FOOTBALL remaining 高于安全线。
- 普通日安全线：`remaining >= 1000`。
- 比赛日安全线：`remaining >= 2500`。

回填顺序：

| 顺位 | 回填目标 | 用途 |
|---|---|---|
| 1 | 2026 世界杯缺字段 | 直接服务展示站/模型 |
| 2 | 世界杯历史赛季 | 历史战绩、风格、模型训练 |
| 3 | 48 队近 20/50 场国家队比赛 | form、强度、伤停影响 |
| 4 | 英超 | 模型主训练联赛 |
| 5 | 西甲、意甲、德甲、法甲 | 模型泛化与球员能力 |
| 6 | H2H 与核心球员历史 | 赛前报告 |
| 7 | 伤停历史与 sidelined | 缺阵影响模型 |

配置入口：

- `configs/backfill/api_football_historical_backfill.json`

## 6. 赛前 T-window 执行

### T-7 天

- 检查 API-FOOTBALL injuries/odds/predictions 是否对未来 7 天比赛可见。
- 启动新闻/伤停 evidence 加密采集。
- 运行 Odds-API.io event scan，查 World Cup event 是否出现。
- 复查天气是否进入 forecast window。

### T-72 小时

- 抓 injuries、weather、odds 初版。
- 建立每场 `runtime_summary` 状态。
- 若赔率只有 1-2 家 bookmaker，标 `data_quality=low`。

### T-24 小时

- 刷新 injuries、weather、odds。
- 新闻/发布会 evidence 进入人工关注。
- 若有裁判指派，生成 referee profile。

### T-6 小时

- 刷新 injuries、weather、odds。
- 检查预计首发源。
- 生成模型赛前报告输入快照。

### T-90/T-60/T-30/T-15

- 查询确认首发。
- 一旦 `status=confirmed`，不可覆盖，只能新增快照。
- 若 T-30 仍无确认首发，标记 `lineups.source_status=unavailable`，模型降权。

### 赛后

- FT 后 15 分钟抓初版 score/events/stats/players。
- FT 后 2 小时复核。
- 次日 06:00 UTC 最终归档。
- 加时/点球必须继续保留 period/status，不在 90 分钟停止。

## 7. 上线前验收

### 展示站 `worldcup/2026`

| 检查 | 通过标准 |
|---|---|
| manifest | 能读取 `api/worldcup/2026/manifest.json` |
| core datasets | teams/fixtures/groups/bracket/venues/cities/history/recent matches 可用 |
| team pages | 主教练、球员基础、历史战绩、最近比赛至少有基础展示 |
| city pages | 16 城市和球场字段稳定 |
| fallback | runtime API 失败时前端有明确 fallback，不把旧数据当最新 |
| data timestamp | 页面可展示或调试 `updated_at/source_status` |

### 模型 `world-cup-predictor`

| 检查 | 通过标准 |
|---|---|
| predictor bundle | `shared-fixtures/feature-inputs/predictions-source` 104 场 |
| kickoff_at | 缺失数为 0 |
| runtime_summary | 104 场稳定行 |
| odds | 无生产源时明确 missing/low，不阻断预测 |
| lineups | 未到窗口时 unavailable，不误判为无阵容 |
| injuries | 缺授权或缺 evidence 时 missing_auth/partial，不误判为无伤停 |
| weather | 未到 forecast window 时 unavailable |
| person_profile_snapshot | 可缺失降级，但有 schema 和 confidence |

## 8. 阻断项与降级策略

| 阻断/风险 | 当前策略 |
|---|---|
| API-FOOTBALL Pro 未开通 | 只用现有平台静态/基础数据，不声称有官方 runtime 深度数据 |
| API-FOOTBALL Pro 仍不覆盖 WC 2026 | 继续 official/FIFA/football-data.org 基础数据，深度数据用赛后官方报告/实验源补 |
| 赔率无生产源 | 模型不做强 AH/OU/CLV 结论，只保留实验和低置信报告 |
| 确认首发未到窗口 | 不采；输出 unavailable 状态行 |
| 官方名单未全量公布 | 不用第三方名单冒充官方名单 |
| 裁判指派未公布 | 用 referee missing 状态，不用英超裁判样本替代世界杯指派 |
| 高级过程数据缺失 | 字段保持 null，不填 0 |

## 9. 下一步顺序

1. 等 API-FOOTBALL Pro 开通后，立即跑 coverage/runtime probe。
2. 根据 probe 结果更新 `reports/data-quality.json` 和 `reports/source-health.json`。
3. 若 API-FOOTBALL 覆盖可用，先接 injuries/lineups/events/statistics/players，不先扩赔率。
4. 首场前 5 天重跑 Odds-API.io event scan。
5. 每天把 P0/P1 采集剩余额度按 backfill 配置用于历史补强。
6. 开赛前最后一周每日检查官方名单、裁判、伤停、天气、赔率可见性。
