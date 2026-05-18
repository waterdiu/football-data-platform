# 模型侧新需求后的数据缺口评估

日期：2026-05-18  
项目：`football-data-platform`  
消费方：`world-cup-predictor`  
主基线文档：`/Users/chamcham/Documents/AI/CODEX/soccer/football-data-platform/DESIGN.md`

## 1. 背景

`world-cup-predictor` 这一轮已补上 D2 / D3 / D6 等模型逻辑框架，但模型本身不再承担生产共享数据采集。以下数据需要由 `football-data-platform` 采集、标准化、发布和标注覆盖状态。

本评估只回答三个问题：

- 哪些数据平台已经有或已有入口。
- 哪些数据可以通过现有渠道继续补齐。
- 哪些数据目前获取方式未定，或已明确不能作为当前免费/生产数据源。

## 2. 分类结论

### 2.1 已经具备或已有稳定入口

| 数据 | 当前状态 | 当前路径 / 渠道 | 可用范围 | 备注 |
| --- | --- | --- | --- | --- |
| 世界杯 104 场赛程、`kickoff_at`、场馆 | 已具备 | `api/worldcup/2026/predictor/shared-fixtures.json`、`fixtures.json` | 世界杯 | `kickoff_at` 已补齐为 UTC。 |
| 国家队最近 10 场基础赛果 | 已具备 | `team-recent-matches.json` | 世界杯球队 | 支持日期、赛事、主客队、比分、地点/场馆如有。 |
| 世界杯历史战绩年度汇总 | 已具备 | `team-world-cup-history.json` | 48 队 | 适合展示和低阶历史强度解释。 |
| 主教练基础档案 | 部分具备 | `team-staff.json`、`coach-profiles.json` | 48 队 | 主教练姓名/球队已具备；`appointed_at` / `contract_until` 未具备。 |
| 球员基础档案 | 部分具备 | `players.json`、`player-profiles.json` | 当前 9 队 234 人 | 姓名、位置、球队、状态、部分 club/DOB/age/caps/goals 已有。 |
| 球员历史活动数据 | 已具备补充层 | `player-dcaribou-activity.json` | 234 人 | 历史出场、分钟、进球助攻、牌、历史号码候选；不是 2026 官方号码/首发/伤停影响。 |
| 裁判历史样本画像 | 部分具备 | `official-ratings.json`、`referee-profiles.json` | 英超历史样本 | 可做裁判尺度样本；不是世界杯裁判名单或单场指派。 |
| 运行期 API 占位契约 | 已具备 | `runtime-summary.json`、`lineups.json`、`injuries.json`、`weather.json`、`odds-snapshots.json` | 世界杯 | 即使为空也应输出覆盖状态，模型按 coverage 降权。 |
| 赛程负荷基础版 | 已具备基础版 | `schedule-load.json` | 世界杯 104 场 | 提供休息天数和近 7/14/30 天比赛数；旅行距离因上一场坐标缺失仍为 missing。 |
| 主客/中立拆分基础版 | 已具备基础版 | `team-home-away-splits.json` | 48 队 | 基于最近 10 场，输出 overall/home/away/neutral split；国家队中立场不强行归入主客。 |
| 人物数据源就绪度 | 已具备 | `reports/person_data_source_readiness.json` | 数据层诊断 | 已识别 dcaribou DuckDB 表、salimt license 阻断、StatsBomb 样本用途。 |

### 2.2 可以通过现有渠道继续补齐

| 数据需求 | 现有可用渠道 | 可补字段 | 优先级 | 风险 / 限制 |
| --- | --- | --- | --- | --- |
| 主客场细分基础数据 | `team-recent-matches.json`、`international-results`、已迁移 predictor normalized matches | 近 10/20 场主客场 W/D/L、进球、失球、零封、主客/中立标签 | P0/P1 | 基础版已发布到 `team-home-away-splits.json`；国家队很多比赛是中立场，不能硬套俱乐部主客场逻辑。 |
| 完整赛程与体能负荷 | dcaribou `appearances/games`、football-data.co.uk、predictor assets、openfootball | 日期间隔、连续客场、跨赛事比赛数量 | P0 | 基础版已发布到 `schedule-load.json`；俱乐部多线赛程可做，国家队球员俱乐部赛程与国家队赛程合并需要身份映射。 |
| 旅行距离 | `venues.json` / host city 经纬度、比赛城市、球队/俱乐部所在地 | 城市间距离、跨国/跨洲、连续客场距离 | P1 | 球队出发地不一定等于俱乐部城市或国家首都，需要明确假设。 |
| 球员能力与影响力 proxy | dcaribou players/activity、FBref/Understat/predictor assets | 身价、caps、goals、出场、分钟、首发、进球助攻、牌、近期活动 | P0/P1 | 当前只能做 proxy，不是 `absence_impact_pct`。 |
| 英超高级过程数据 | FBref、Understat、StatsBomb 样本、predictor assets | xG/xGA、射门、控球、传球、部分防守指标 | P1 | 可先支持英超测试；字段覆盖不一定全。 |
| 世界杯/国家队基础高级代理 | `team-recent-matches`、国际赛结果、预选赛数据 | 近 10/20 场进失球、射门/控球如 API 有返回 | P1 | PPDA、传球成功率、xG 大概率缺失或不稳定。 |
| 天气 | Open-Meteo、场馆经纬度 | 温度、风速、降雨、天气风险标签 | P1 | 真实预测只有进入天气窗口后才有；窗口外只能 `unavailable/outside_forecast_window`。 |
| 新闻语义情报 | 已有 `prematch_news` 配置化采集 | 伤停 evidence、轮换暗示、教练表态、战意线索 | P2 | 只能作为 evidence 和解释，不得直接覆盖官方状态。 |
| 世界杯赛后事件/技术统计 | API-FOOTBALL、football-data.org、openfootball 兜底 | 比分、事件、红黄牌、换人、技术统计 | P1/P2 | 比赛开始后可赛后一次性补；当前无需 5-10 分钟直播级采集。 |

### 2.3 获取方式待验证

| 数据需求 | 待验证渠道 | 阻断点 | 当前处理 |
| --- | --- | --- | --- |
| 确认首发与替补 | FIFA match centre、API-FOOTBALL、BBC/Sofascore 增强 | 只有赛前 60-90 分钟才出现；当前正赛未开始 | 输出占位和 `outside_lineup_window`。 |
| 伤停/停赛/出场概率 | FIFA/国家队官网、API-FOOTBALL injuries、新闻源、Transfermarkt | 国家队伤停结构化源不稳定；新闻 evidence 易误判 | 保守 evidence；不把无 evidence 当无伤停。 |
| 世界杯裁判名单与单场指派 | FIFA 官方、比赛报告、API-FOOTBALL | 需等官方公布/比赛日指派 | 当前只发布英超历史裁判样本。 |
| AH / OU / closing odds | API-FOOTBALL odds、BSD/Bzzoiro probe、HKJC 合规验证、授权商业源 | 免费源 World Cup/AH 覆盖未确认；逆向源不能进生产 | 继续 probe，不通过不得入 normalized/public。 |
| 多机构盘口时间序列 | 付费/授权 odds provider、API-FOOTBALL、合规 HKJC | 免费层覆盖不足，closing odds 需要持续采样 | 当前模型只能弱赔率分析。 |
| PPDA / 传球成功率 / 控球率的世界杯全量 | API-FOOTBALL stats、StatsBomb/FBref 样本、Sofascore experimental probe | 正赛未开始；免费源不保证字段；Sofascore 非官方 endpoint 不能进生产；当前 live smoke test 返回 HTTP 403 | 缺失字段必须 `null`，不能填 0；Sofascore 只写 raw experimental/report。 |
| 跑动距离 / 高强度跑 / 冲刺 | SkillCorner/Wyscout/Opta 类商业源 | 通常是付费 tracking 数据 | 暂不作为 P0。 |
| 教练 `appointed_at` / `contract_until` | 足协公告、FIFA profile、Wikidata qualifier、Transfermarkt manager profile | 结构化覆盖不稳定，Transfermarkt 页面有 WAF | 需要人工审计 patch 或 Wikidata probe。 |

### 2.4 已明确不能作为当前免费/生产源

| 数据 / 来源 | 结论 | 原因 |
| --- | --- | --- |
| TheOddsAPI 免费层足球赔率 | 当前不能用 | 免费邮件明确只覆盖 NBA + MLB，足球需 Business。 |
| iSportsAPI 免费试用 | 不作为生产源 | 15 天试用，用户已明确不付费，不能做长期数据层依赖。 |
| salimt/football-datasets 直接入库 | 当前不能进 normalized/public | GitHub license metadata 为空，仓库缺 `LICENSE`，只能 probe。 |
| 雷速/赔率逆向爬虫 | 不能作为生产主源 | 合规和稳定性风险，只能 experimental/raw。 |
| dcaribou 历史号码候选 = 2026 官方球衣号码 | 不能等同 | 来源是历史 lineups，混合俱乐部/国家队上下文。 |
| dcaribou activity = 真实缺阵影响 | 不能等同 | 缺少伤停、可用性、球队表现反事实样本。 |
| 当前英超裁判样本 = 世界杯裁判指派 | 不能等同 | 只是历史样本，不包含 FIFA 2026 指派。 |
| 天气窗口外填 0 或晴天 | 禁止 | 天气预测窗口外只能标记 unavailable，不能伪造数值。 |

## 3. 按模型维度归纳

### D2 过程型竞技状态

需要：

- 控球率、传球成功率、PPDA。
- 射门、射正、xG、xGA。
- 抢断、拦截、压迫强度。
- 近 5/10/20 场滚动聚合和逐场明细。

现状：

- 英超可通过 FBref / Understat / predictor assets 部分补。
- 世界杯/国家队已发布基础结果代理到 `team-advanced-stats.json`：覆盖 48 队，提供最近 10 场进失球、胜平负率和样本 basis。
- 完整 PPDA/xG、控球、传球和射门过程数据仍需要付费源、合规公开源或赛后统计源验证。

数据层下一步：

- 继续做 `team_advanced_stats` 的英超测试集。
- 世界杯过程型字段已按 `null + missing_advanced_fields_reason` 发布，不得填 0。

### D3 体能负荷 / 多线作战 / 旅行

需要：

- 全部赛事日期：联赛、欧冠、欧联、欧协、足总杯、联赛杯、国家队比赛。
- 比赛城市/场馆坐标。
- 旅行距离、休息天数、连续客场。

现状：

- 世界杯场馆与 `kickoff_at` 已有。
- dcaribou games/appearances 可用于球员俱乐部历史活动，但需要映射到球员/球队。
- 国内杯赛/欧战全量赛程不一定已标准化。

数据层下一步：

- `schedule_load` 基础版已发布：`days_since_last_match`、`matches_last_7/14/30_days`、上一场文本地点和 `travel_origin_assumption`。
- `travel_distance_km` 仍为 `null`，原因是 `team-recent-matches` 只有上一场城市/国家文本，没有经纬度。

### D5 / D6 阵容结构、主客场、板凳深度

需要：

- 确认首发、替补、阵型。
- 球员位置、是否主力、是否轮换。
- 主客场拆分表现。
- 核心球员缺阵、中轴线强度。

现状：

- 球员基础和历史活动 proxy 已覆盖当前 234 人。
- 确认首发必须等赛前窗口。
- 主客/中立基础版已从最近比赛数据派生；国家队中立场明确保持 neutral。

数据层下一步：

- `lineups.json` 保持占位，进入 T-90/T-60/T-30 后采集。
- `team_home_away_splits` 已从 `team-recent-matches` 派生基础版本，覆盖 48 队。
- `player_impact_proxy` 可以基于 market value/caps/minutes 输出，但必须标记不是 absence impact。

### D8 裁判、天气、盘口、环境

需要：

- 裁判任命和画像。
- 天气/场地。
- 1X2/AH/OU opening、T-24h、T-6h、T-1h、closing。

现状：

- 天气可用 Open-Meteo，但只在预测窗口内有效。
- 裁判只有英超历史样本；世界杯指派未有。
- 赔率最大缺口仍是稳定 AH/OU 和 closing odds。

数据层下一步：

- 继续 odds free/low-cost probe，但未通过前不进入生产。
- 继续 Sofascore 字段覆盖 probe，验证 match statistics / lineups / shotmap / xG；未授权前只允许 raw experimental。
- `soccerdata` 的 Sofascore reader 已验证只支持 league/table/schedule，不能提供 match statistics、lineups、shotmap/xG、player ratings 或 PPDA inputs。
- 裁判名单/指派等 FIFA 官方或 API-FOOTBALL。
- 天气按窗口采集，窗口外输出 `unavailable`。

## 4. 当前最应该转给数据层执行的任务清单

### P0

1. **盘口快照源继续 probe**
   - 目标：1X2 / AH / OU，至少 opening、T-24h、T-6h、T-1h、closing。
   - 当前缺口：免费稳定源未确认；TheOddsAPI 免费足球不可用；iSportsAPI 不采用。
   - 输出：`odds-snapshots.json`、`odds-source.json`、`data_coverage.odds_*`。

2. **确认首发 / 替补 / 阵型采集占位与窗口规则**
   - 目标：T-90/T-60/T-30/T-1h 确认首发。
   - 当前缺口：赛前窗口未到，源待验证。
   - 输出：`lineups.json`，窗口外标 `unavailable/outside_lineup_window`。

3. **伤停 / 停赛 / 出场概率**
   - 目标：confirmed out、doubtful、late fitness test、suspended。
   - 当前缺口：国家队结构化源不稳定。
   - 输出：`injuries.json`，新闻 evidence 保守入库。

4. **完整赛程与负荷 proxy**
   - 目标：休息天数、多线作战、连续客场、旅行距离。
   - 当前状态：基础版已发布 `schedule-load.json`，覆盖 104 场；旅行距离仍缺上一场经纬度。
   - 后续缺口：跨联赛/杯赛/国家队数据未统一。

### P1

5. **主客场/中立场拆分**
   - 已从 `team-recent-matches` 派生近 10/20 场 home/away/neutral split。
   - 国家队必须显式处理中立场，不能把中立场硬算主客。

6. **高级过程数据**
   - 英超先补 FBref/Understat 可得字段。
   - 世界杯先输出 schema 和缺失状态。

7. **球员能力与影响力 proxy**
   - 基于 dcaribou activity、market value、caps、minutes 输出 proxy。
   - 不命名为 `absence_impact_pct`，除非有伤停可用性和反事实样本。

8. **裁判画像**
   - 英超历史样本继续可用。
   - 世界杯裁判名单/指派等待 FIFA/API。

### P2

9. **新闻语义信号**
   - motivation、rotation_risk、injury_confidence、rivalry_heat、coach_tactical_note。
   - 只能做解释和 evidence，不能直接覆盖事实状态。

10. **跑动高阶数据**
    - 跑动距离、高强度跑、冲刺次数。
    - 当前只能作为商业源调研项，不作为免费数据 P0。

## 5. 给模型侧的当前缺口摘要

这一轮模型改完后，模型侧仍应视为缺失或低置信的数据：

- 稳定 AH / OU 多机构盘口时间序列。
- opening / closing odds 和 CLV 所需收盘价。
- 确认首发、替补名单、阵型。
- 国家队真实伤停 / 停赛 / 出场概率。
- 世界杯裁判名单和单场裁判指派。
- 世界杯全量 xG、PPDA、传球成功率、控球率。
- 真实 `absence_impact_pct`。
- 赛程负荷基础 proxy 已有；旅行距离仍缺。
- 跑动距离、高强度跑、冲刺次数。

模型可以先使用平台已有数据降级运行：

- `kickoff_at`、赛程、场馆、球队。
- 最近 10 场基础赛果。
- 球员基础档案、club/DOB/age/caps/goals。
- dcaribou 历史活动 proxy。
- `schedule-load.json` 和 `team-home-away-splits.json` 基础版。
- 英超历史裁判样本。
- runtime-summary 的 coverage 状态。

但模型报告必须继续暴露 `missing_optional_runtime_datasets` 和 `runtime_confidence`，不能把缺失字段当成 0 或确定事实。
