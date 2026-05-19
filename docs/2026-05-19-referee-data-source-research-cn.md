# 足球裁判数据源调研

日期：2026-05-19

## 目标

确认裁判画像数据通常从哪里来，GitHub 上是否有可复用项目，以及这些来源能否支撑 2026 世界杯裁判画像。

本调研只解决“来源可行性”和“字段覆盖”问题，不直接把新外部源写入 `normalized` 或 public API。任何网页采集、第三方 API 或 GitHub 项目进入生产前，仍需通过许可证、使用条款、稳定性、ID 映射和样本门槛检查。

## 当前平台基线

平台已经有两类裁判/比赛官员数据：

| 数据 | 状态 | 来源 | 用途 |
|---|---|---|---|
| FIFA 2026 比赛官员名单 | 已导入 | FIFA 官方 PDF | 管理页、人物基础档案、后续单场指派匹配 |
| 英超历史裁判样本 | 已导入 | `football-data.co.uk` / predictor assets | 裁判尺度样本、报告解释、低风险模型辅助 |

当前 FIFA 52 名世界杯主裁画像缺口由 `reports/world_cup_referee_profile_gap_report.json` 跟踪：

- 52 名主裁中只有 2 名命中本地强样本：`Michael Oliver`、`Anthony Taylor`。
- 50 名主裁仍缺可用于强画像的国际/洲际执法样本。
- 仍缺单场世界杯指派、犯规、点球、VAR 介入等强字段。

## 裁判数据通常从哪里来

### 1. 官方赛事与足协来源

| 来源 | 能拿什么 | 稳定性 | 生产建议 |
|---|---|---|---|
| FIFA match centre / match report | 世界杯单场主裁、助理裁判、VAR、比赛报告、事件 | 高，但需等比赛临近或赛后 | 生产主源 |
| UEFA / AFC / CAF / CONCACAF / CONMEBOL 官网 | 裁判名单、单场指派、部分比赛报告 | 中高 | 官方补源 |
| 各国足协公告 | 裁判入选名单、任命公告 | 中 | 证据源，不适合大规模统计 |

结论：官方源是裁判身份和单场指派的最终事实源，但通常不提供可直接聚合的职业执法统计。

### 2. 授权商业 API

| 来源 | 能拿什么 | 费用/门槛 | 生产建议 |
|---|---|---|---|
| SportMonks | Referee endpoint、referee search、referee statistics、fixture referee、cards/events | 付费 API | 最值得验证的裁判画像 API |
| API-FOOTBALL Pro | fixture referee、events/cards、lineups/statistics；可能需要按比赛聚合 | Pro $19/月起，7500 requests/day | 升级后优先 probe |
| Sportradar / Opta / Stats Perform | 深度事件、实时数据、裁判/比赛事实 | 企业报价 | 预算充足时考虑 |

SportMonks 的公开文档明确有 referee endpoint、referee search、referee statistics 类型和 fixture referee include。它比 API-FOOTBALL 更像“直接裁判画像源”。API-FOOTBALL 更可能需要从 fixtures/events 反向聚合。

SportMonks 当前确认规则：

- Free Plan 是长期免费，但足球只覆盖 Danish Superliga 和 Scottish Premiership，不覆盖 World Cup。
- 付费 API 计划有 14 天 free trial，Starter 起价约 `EUR 29/month`，可选 5 个 league；Growth 起价约 `EUR 99/month`，可选 30 个 league；所有计划声称功能相同，差异主要是 league 数和调用容量。
- SportMonks 页面另列 World Cup 2026 widget/API 方案，其中自建 API 方向有 `Advanced EUR 69/month`、`All-In EUR 129/month`。
- referee statistics 类型明确包含 `PENALTIES`、`FOULS`、`REDCARDS`、`YELLOWCARDS`、`YELLOWRED_CARDS`、`MATCHES`、`VAR_MOMENTS`。
- 结论：免费 plan 只能验证 API 结构，不能采 2026 世界杯；若要生产用，需要 trial/付费并确认 World Cup league 覆盖、历史深度和 referee statistics include 是否可用。

### 3. 免费结构化历史数据

| 来源 | 能拿什么 | 覆盖 | 生产建议 |
|---|---|---|---|
| football-data.co.uk | Referee、黄牌、红牌、犯规、角球、射门、赛果、赔率 | 主要欧洲联赛 | 已可生产使用 |
| DataHub football datasets | football-data.co.uk 的结构化镜像 | 英超等 | 可作校验，不优先 |
| soccerdata MatchHistory | football-data.co.uk 的 Python 封装 | 依赖 football-data.co.uk 覆盖 | 可作为下载/缓存工具 |

football-data.co.uk 字段对裁判画像很实用：`Referee`、`HY`、`AY`、`HR`、`AR`、`HF`、`AF`、`FTHG/FTAG/FTR` 等。缺点是非欧洲裁判和国际赛事覆盖不足。

### 4. 公开裁判档案网站

| 来源 | 能拿什么 | 风险 | 生产建议 |
|---|---|---|---|
| worldfootball.net referee pages | 裁判执法比赛、赛事、比分、可能有牌 | 页面采集稳定性和条款需验证 | 先 probe |
| WorldReferee | 国际裁判档案、比赛历史、牌、点球、犯规、活跃年份 | 页面采集稳定性和条款需验证 | 免费补源优先 probe |
| Wikipedia / Wikidata | 基础身份、国籍、生日、部分大赛记录 | 统计字段弱 | 只做身份和证据补充 |

结论：worldfootball.net 和 WorldReferee 是补 52 名世界杯主裁国际样本最可能的免费路线，但必须先做小样本 probe，不能直接进 public。

worldfootball.net 小样本验证结果：

- 目标样例：`https://www.worldfootball.net/referee_summary/szymon-marciniak/1/1/`。
- 当前平台运行环境直接 `curl` 返回 Cloudflare JavaScript challenge，不能稳定自动采集。
- 搜索索引能确认该站存在结构化裁判页，字段包括赛事/赛季、执法场次、黄牌、两黄变红、红牌、出生日期、国籍，以及按球队/赛事拆分的裁判历史页。
- 平台已记录阻断报告：`reports/worldfootball_referee_probe_report.json`。
- 结论：worldfootball.net 可以作为人工核验或未来合规访问策略的候选源，但现在不适合建设生产采集器；优先级排在 WorldReferee、API-FOOTBALL Pro 和 SportMonks 之后。

WorldReferee 小样本验证结果：

- 平台已新增 probe 脚本：`scripts/probe_worldreferee_referees.py`。
- 最新全量 52 名 FIFA 主裁 probe 输出：`reports/worldreferee_referee_probe_report.json`。
- 52 个 FIFA 主裁候选页面均可访问；其中 41 个有 `matches`、`competitions`、`yellow_cards`、`red_cards`、`active_years` 等概要字段。
- 32 个页面有点球字段，29 个页面有犯规字段。
- 52 人合计抽取到 849 条逐场历史样本。
- 11 个页面可访问但概要统计和逐场样本为空：`Yael Falcon Perez`、`Ma Ning`、`Juan Calderon`、`Amin Mohamed`、`Khalid Al Turais`、`Katia Garcia`、`Dahane Beida`、`Abdulrahman Al Jassim`、`Abongile Tom`、`Ivan Barton`、`Tori Penso`。
- 报告新增机器可读 `gap_summary`：按字段列出缺口名单，并按样本门槛输出 `sample_ge_20_report_explanation`、`sample_ge_30_style_distillation`、`sample_ge_50_strong_model_signal`。
- 按 WorldReferee 概要 `matches` 样本数粗算：30 人达到报告解释门槛，26 人达到风格蒸馏候选门槛，19 人达到强模型信号候选门槛。
- `Szymon Marciniak` 页面可访问，概要包含 134 场、38 项赛事、黄牌/红牌/点球/犯规、活跃年份和逐场比赛历史。
- `Facundo Tello` 页面可访问，概要包含 14 场、7 项赛事、黄牌/红牌/点球/犯规、2022 World Cup 逐场记录。
- `Mustapha Ghorbal` 页面可访问，概要包含 44 场、20 项赛事、黄牌/红牌/点球/犯规、CAF 和 World Cup 记录。
- `Alireza Faghani` 页面可访问，概要包含 132 场、40 项赛事、黄牌/红牌/点球/犯规、AFC/World Cup/Club World Cup 记录。
- 这说明 WorldReferee 对 UEFA、CONMEBOL、CAF、AFC 主裁都有一定覆盖，比 football-data.co.uk 更适合补世界杯主裁的国际样本。
- 风险：页面自称数据库记录，不是官方授权 API；需要条款/抓取频率/字段稳定性审核。当前只能进入 `reports` 或 `data/raw/experimental/referee_sources`，不得写入 `normalized` 或 public API。

### 5. 实验性网页/逆向源

| 来源 | 能拿什么 | 风险 | 生产建议 |
|---|---|---|---|
| Sofascore / FotMob / WhoScored | 单场裁判、事件、牌、评分上下文 | 反爬、条款、ID 映射 | experimental only |
| 雷速/懂球帝/500/雪缘园 | 中文展示页可能含裁判、牌、赛果 | 非授权、页面变动、法律/合规风险 | 不进 normalized/public |

这些只能作为人工校验或实验报告源。

## GitHub 搜索结论

### 有价值项目

| 项目 | 类型 | 许可证 | 结论 |
|---|---|---|---|
| `probberechts/soccerdata` | Python 数据封装 | GitHub API 返回 `NOASSERTION` | 可用作 football-data.co.uk/FBref/WhoScored 下载封装；不是专门裁判库 |
| `gmalbert/premier-league` | EPL 预测项目，含 `scrape_referees.py` | MIT | 可参考 EPL 裁判采集思路；覆盖窄 |
| `ERNESTOTALIB/FOOTBALLDATA` | 含 `scrape_referee_stats_worldfootball.py` | 未声明 license | 只能 probe/参考，不得复制或生产使用 |
| `ChristianPala/premier_league_api` | EPL API/采集项目，含 referee scraper | 未完成许可证审查 | 只能参考 |
| `datasets/football-datasets` | football-data.co.uk 结构化数据 | 数据镜像 | 可作为 football-data.co.uk 校验/补下载 |

### 大量不相关项目

GitHub 上 `referee football` 搜索结果大量是：

- 视频识别裁判位置的 CV 项目。
- VAR/裁判舆情分析。
- 裁判分配系统课程项目。
- 博彩预测项目里的临时代码。

这些不提供结构化裁判执法统计，对世界杯裁判画像价值低。

## 字段覆盖矩阵

| 字段 | football-data.co.uk | SportMonks | API-FOOTBALL Pro | worldfootball/WorldReferee | FIFA |
|---|---|---|---|---|---|
| 裁判姓名 | 有 | 有 | 有/fixture 中有 | 有 | 有 |
| 国籍/协会 | 弱 | 可能有 | 不确定 | 通常有 | 有 |
| 单场指派 | 历史欧洲联赛 | 有 | 有 | 有历史 | 世界杯官方 |
| 黄牌/红牌 | 有 | 有 | events 可聚合 | 可能有 | match report 可能有 |
| 犯规 | 部分联赛有 | 明确有 referee statistics type | statistics/events 取决覆盖 | WorldReferee 概要有 fouls | match report 取决公开程度 |
| 点球 | 需事件或手工推断 | 明确有 referee statistics type | events 可聚合 | WorldReferee 概要有 penalties | match report 可能有 |
| VAR | 无 | 明确有 `VAR_MOMENTS` type | 不确定 | 弱 | match report 可能有 |
| 主客倾向 | 可算 | 可算 | 可算 | 可算 | 需比赛样本 |
| 国际/洲际样本 | 弱 | 取决套餐覆盖 | 可按 fixtures 聚合 | 较强 | 官方报告分散 |

## 推荐采集路线

### P0：立即可做

1. 保持 FIFA 170 名比赛官员名单为官方身份源。
2. 用 `reports/world_cup_referee_profile_gap_report.json` 跟踪 52 名主裁缺口。
3. 用 football-data.co.uk 继续扩展欧洲主裁样本，不要只限英超。

### P1：API-FOOTBALL Pro 到位后

1. 先验证 `/fixtures` 是否能按裁判名或 fixture 返回 `referee`。
2. 抽取 10 名世界杯主裁，按最近 2-3 年国际赛/洲际赛 fixture 聚合 cards/events。
3. 如果能稳定拿到 events/cards，再扩到 52 名主裁。
4. 不假设 API-FOOTBALL 有“裁判统计 endpoint”；先按比赛聚合设计。

### P1：免费网页 probe

1. 先以 WorldReferee 做 10 人 probe：`Michael Oliver`、`Anthony Taylor`、`Szymon Marciniak`、`Facundo Tello`、`Mustapha Ghorbal`、`Alireza Faghani`，再补 CAF/AFC/CONCACAF/OFC 各 1 人。
2. 验证字段：比赛日期、赛事、主客队、比分、黄牌、红牌、点球、犯规。
3. 验证 ID 映射：FIFA 名字能否唯一匹配页面人物。
4. 验证条款和频率：如果不可批量抓取，只保留人工证据链接和小样本报告。
5. 只写 `reports` 或 `data/raw/experimental/referee_sources`，通过审查后再进入 normalized。

### P2：付费源

如果模型正式把裁判画像作为 D8/OU/牌/点球风险信号，优先考虑 SportMonks，因为它公开文档里对 referee endpoints 和 referee statistics 支持最明确。

## 生产准入规则

裁判画像进入 public/model 前必须满足：

- `source_url` 和 `source_status` 可追溯。
- `sample_size >= 20` 才能用于报告解释。
- `sample_size >= 30` 才能输出风格标签。
- `sample_size >= 50` 才能作为强模型信号。
- 缺字段必须为 `null`，不能填 0。
- FIFA 名单不能当单场指派。
- 英超样本不能代表世界杯执法风格，只能标 `historical_sample_only`。
- 网页/逆向源必须先过条款和稳定性审查。

## 当前结论

裁判画像可以继续补，但“免费稳定全量”不存在。

最现实的组合是：

1. FIFA：身份和世界杯单场指派。
2. football-data.co.uk：欧洲联赛历史样本。
3. API-FOOTBALL Pro：按比赛聚合国际/洲际样本，待验证。
4. worldfootball.net / WorldReferee：免费网页补源，先 experimental。
5. SportMonks：如果要更稳定裁判统计，作为付费候选。
