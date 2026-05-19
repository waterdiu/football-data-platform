# 足球数据源调研与缺口总览

日期：2026-05-19  
项目：`football-data-platform`  
消费方：`worldcup/2026`、`world-cup-predictor`  
主基线文档：`/Users/chamcham/Documents/AI/CODEX/soccer/football-data-platform/DESIGN.md`

## 1. 目的

这份文档把近期关于世界杯网站、预测模型、赔率源、高级技术统计、人物档案、Sofascore、FBref、WhoScored、雷速、BSD/Bzzoiro、Odds-API.io 等调研集中记录，避免后续重复调查。

本文只定义数据层状态和证据，不改变生产采集策略。所有未授权、逆向、爬虫、免费源 probe 结果默认不得进入 `data/normalized`、`data/model` 或 public API。

后续同类调研必须自动落档归并：新增数据源、GitHub 项目、API key probe、字段覆盖验证、失败原因、费用规则或生产化判断时，必须优先更新本文；如果新增脚本、配置、报告或输出契约，还必须同步更新主基线 `DESIGN.md`。调研记录必须包含：来源、访问方式、能获取字段、不能获取字段、限制原因、是否允许进入 normalized/public、下一步验证条件。

## 2. 两个消费项目需要的数据

### 2.1 `worldcup/2026` 展示站

| 数据 | 优先级 | 当前状态 | 稳定性 | 当前路径 / API | 备注 |
|---|---:|---|---|---|---|
| 104 场正赛赛程、时间、场馆 | P0 | 已提供 | 稳定 | `api/worldcup/2026/core/fixtures.json`、`predictor/shared-fixtures.json` | `kickoff_at/date_utc` 已补齐 UTC。 |
| 48 队基础信息 | P0 | 已提供 | 稳定 | `core/teams.json` | canonical team slug 由平台维护。 |
| 小组、淘汰赛、赛程结构 | P0 | 已提供 | 稳定 | `core/groups.json`、`core/bracket.json` 等 | 供展示站 runtime fetch。 |
| 主教练 | P0 | 已提供 | 中高 | `core/team-staff.json`、`core/coach-profiles.json` | 48 队主教练已发布；`appointed_at/contract_until` 仍缺可靠结构化来源。 |
| 球队世界杯历史战绩 | P0 | 已提供 | 中高 | `core/team-world-cup-history.json` | 44 队有历史正赛记录；4 队为无历史参赛而非缺失。 |
| 最近 10 场国家队比赛 | P0 | 已提供 | 中 | `core/team-recent-matches.json` | 来源为国际赛历史 CSV；高级技术统计不在此数据集中。 |
| 球员姓名、位置、状态、team_id | P0 | 部分提供 | 中高 | `core/players.json`、`core/player-profiles.json` | 目前覆盖已导入官方名单的 9 队 234 人；其余队等待 FIFA/足协最终名单。 |
| 城市/球场资料 | P0/P1 | 已提供基础版 | 中高 | `core/host-city-profiles.json`、`core/venues.json` | `venue_id/host_city_id/site_city_key` 已统一；容量、草皮、屋顶、海拔等可继续增强。 |
| 正赛赛果/赛后技术统计 | P1 | 契约有，正赛未开始 | 待赛后 | `core/finals-results.json`、coverage | 展示站当前不要求比赛中实时更新，赛后一次性补可接受。 |
| 赔率 | 不展示 | 不需要 | - | - | 展示站明确不展示赔率。 |

### 2.2 `world-cup-predictor` 模型层

| 数据 | 优先级 | 当前状态 | 稳定性 | 当前路径 / API | 备注 |
|---|---:|---|---|---|---|
| predictor bundle / fixtures / feature inputs | P0 | 已提供 | 稳定 | `api/worldcup/2026/predictor/*` | 模型严格读平台，`missing_kickoff_count=0`。 |
| 预测写回入口 | P0 | 已提供 | 稳定 | `data/inbox/predictor/*` -> publish | 模型写 inbox，平台 publish 校验后进入 public/model。 |
| 主客/中立拆分 | P0/P1 | 已提供基础版 | 中 | `predictor/team-home-away-splits.json` | 国家队中立场保留 neutral，不硬归主客。 |
| 赛程负荷 | P0/P1 | 已提供基础版 | 中 | `predictor/schedule-load.json` | 休息天数/近 7/14/30 天比赛数已有；旅行距离仍缺坐标映射。 |
| 球队高级状态代理 | P1 | 已提供基础版 | 中 | `predictor/team-advanced-stats.json` | 当前是最近 10 场基础代理；控球、传球、PPDA、xG 多为 `null`。 |
| 阵容/首发 | P0 | 状态行已提供 | 稳定契约，事实待赛前 | `predictor/lineups.json` | 现在是 `outside_lineup_window`；确认首发只能赛前 60-90 分钟。 |
| 伤停/停赛 | P0 | 状态行 + 新闻 evidence | 低到中 | `predictor/injuries.json` | API-FOOTBALL free 对 2026 World Cup 受限；新闻只做 evidence。 |
| 天气 | P1 | 状态行已提供 | 中 | `predictor/weather.json` | Open-Meteo fallback 已有；进入 16 天预报窗口后才有真实值。 |
| 裁判画像 | P1 | 英超历史样本已提供 | 中 | `core/referee-profiles.json`、`official-ratings.json` | 不是世界杯裁判指派；世界杯单场裁判需等官方 match centre/report。 |
| 赔率 1X2/AH/OU/CLV | P0 for betting model | 缺生产源 | 低 | `predictor/odds-snapshots.json` | 赔率是当前最弱环节，见第 5 节。 |
| 球员影响力/风格 | P1/P2 | 基础 proxy | 低到中 | `player-profiles.json`、dcaribou activity | 缺真实 xG/xA、评分、伤停影响反事实样本。 |

## 3. 已经提供的数据层成果

| 类别 | 已提供内容 | 稳定性 | 说明 |
|---|---|---|---|
| World Cup core API | fixtures、teams、groups、bracket、venues、cities、team history、recent matches、staff、players | 稳定到中高 | 主要服务展示站。 |
| Predictor API | shared fixtures、feature inputs、predictions source、runtime summary、coverage | 稳定 | 主要服务模型。 |
| Person profile API | people index、coach/player/referee profiles、official ratings | 中 | 直接事实可用；派生/蒸馏仍受样本限制。 |
| Runtime status rows | lineups、injuries、weather、odds snapshots | 稳定契约 | 即使无事实也输出 `source_status/status_reason`，避免模型误把缺失当 0。 |
| 数据覆盖/健康 | source-health、data-coverage、data-quality | 稳定 | 用于定位缺口和消费端降级。 |

## 4. 高级技术统计来源调研

### 4.1 Sofascore

当前结论：能补非赔率高级数据，但只能 `experimental_only`。

| 方式 | 是否实际验证 | 能拿到什么 | 缺什么 | 结论 |
|---|---|---|---|---|
| 直接 Sofascore web endpoint | 已测 | 无 | HTTP 403；sample event `13981725` 的 statistics/lineups/incidents/shotmap/graph 也被拒绝 | 当前环境不能作为生产采集器，也不能作为直接采集主线。 |
| `pysofascore` | 已 live 验证 | statistics、控球、xG、射门、射正、传球、准确传球、lineups、incidents、shotmap、momentum、best players | 直接 PPDA、授权稳定性、世界杯覆盖 | 最强实验候选，仅限 wrapper 隔离实验。 |
| `ScraperFC` | 已 live 验证 | match dict、team stats、shots/xG、player stats、ratings、heatmaps、momentum | 直接 PPDA、incidents 未在验证 API surface 直接暴露 | 强实验候选。 |
| `tunjayoff/sofascore_scraper` | 已 live 验证部分 | event basic、statistics、lineups、incidents、h2h | shotmap/xG/player ratings 未验证 | 可用但不如前两个完整。 |

对当前项目的补充：

- 可补世界杯赛后技术统计：控球、射门、射正、传球、xG、事件、阵容。
- 可补球员影响力 proxy：评分、出场分钟、xG/xA、热区、传球、抢断/拦截。
- 不能直接补：PPDA、生产级授权数据源、稳定世界杯 event mapping。

当前阻断原因：

- 非官方 endpoint / wrapper，存在授权、字段稳定、ID 映射、反爬风险。
- 当前 direct API live probe 对 player endpoints 和 sample event endpoints 返回 403/网络错误；后续只能走 wrapper 隔离验证，不能把 direct API 作为采集路径。
- 尚未在 2026 世界杯 event 上验证覆盖。
- 因此只能写 `reports/` 或 `data/raw/experimental/sofascore`，不得写 normalized/public。

### 4.2 `soccerdata` 的 FBref / FotMob / WhoScored

当前结论：FBref 有补充价值，FotMob 在当前 `soccerdata 1.9.0` 走不通，WhoScored 只适合高风险事件实验。

| 来源 | soccerdata reader | 实际验证 | 能获得什么 | 与已有数据关系 | 结论 |
|---|---|---|---|---|---|
| FBref | 有 | capability + 缓存 HTML 验证 | EPL 赛程、比分、场馆、裁判、球队主客场战绩、控球、射门、射正、牌、犯规、拦截、playing time、部分 lineup/events 方法 | 与已有赛果/赛程重复；补充控球、射门、犯规/拦截、裁判、主客拆分等 | 英超模型有价值；世界杯国家队不稳定。 |
| FotMob | 无 | 已确认 reader missing | 无 | 无 | 当前不能通过 soccerdata 获取。 |
| WhoScored | 有 | capability 验证 | schedule、missing players、events；控球/传球/PPDA 可理论从事件推导 | 与 Sofascore/FBref 部分重叠；可补事件推导 | 高反爬/浏览器风险，只能实验。 |

FBref 已确认的缓存字段示例：

- `schedule_ENG-Premier League_2425.html`：`Wk`、`Day`、`Date`、`Time`、`Home`、`Score`、`Away`、`Attendance`、`Venue`、`Referee`、`Match Report`。
- `teams_ENG-Premier League_2425_stats.html`：总体 W/D/L/GF/GA、主客场 W/D/L/GF/GA、`Poss`、出场时间、进球助攻、黄红牌、门将、射门、射正、射正率、犯规、被犯规、越位、传中、拦截、抢断成功、点球等。
- `matchlogs_Arsenal_2425_shooting.html`：逐场日期、赛事、轮次、主客、结果、进失球、对手、射门、射正、射正率、点球、match report。

FBref live 抓取验证结果：

- 显式允许 `--allow-browser-driver` 后，FBref live probe 启动并进入缓存流程，但长时间无输出，被手动停止。
- 这说明它不适合 production collector；可以低频手动验证或用缓存/离线文件做实验。

世界杯球员补强验证：

- 新增 report-only 脚本 `scripts/probe_fbref_worldcup_player_coverage.py`，报告为 `reports/fbref_worldcup_player_coverage_report.json`。
- 使用当前已公布的 234 名世界杯球员和本地 `data/predictor-assets/files/raw/fbref_premier_league_player_stats.csv` 做 normalized exact name 匹配。
- 结果：32 名球员命中，1 名球员歧义，201 名未命中，命中率 13.68%。命中集中在英超效力球员，例如比利时、法国、瑞典、日本、科特迪瓦、海地、突尼斯部分球员。
- 32 名命中球员中，31 名同时具备高置信 Transfermarkt/Reep 外部 ID，可进入下一步人工/规则审查；但当前仍没有 FBref 原生 player id 映射，因此不能自动写入生产画像或模型特征。
- 这证明 FBref/英超资产对世界杯核心球员模型有补强价值，尤其是英超效力球员的出场时间、首发、进球、助攻、俱乐部位置。
- 但当前本地 CSV 中 `xG/xAG/PrgP/Tkl/Int` 列全部为 0，不能当作真实高级能力输入；这些字段必须重新获取更完整 FBref 导出或保持 `null/zero_only_field`，不得把 0 解释为真实表现。
- 当前匹配是 name-only，不能写 normalized/public；必须先完成 player_id 映射、歧义处理和来源策略审查。
- 已新增候选集脚本 `scripts/build_fbref_player_enrichment_candidates.py`，输出 `reports/fbref_player_enrichment_candidates.json`。候选集只保留高置信 Transfermarkt/Reep 外部 ID、非歧义、且 `90s/Starts/Gls/Ast` 至少一项非零的球员；它只供模型侧评估是否值得接入，不进入 public API。

### 4.3 PPDA

当前没有稳定生产源。

可选路径：

- WhoScored events 或 StatsBomb event data 理论可推导，但覆盖和授权不足。
- Sofascore wrapper 没有直接 PPDA。
- FBref 当前缓存/reader 未直接暴露 PPDA。
- 商业源 Opta / StatsBomb paid / Wyscout / InStat 更靠谱，但需要付费授权。

处理规则：

- 平台不得把 PPDA 填 0。
- 未验证时统一为 `null`，并在 coverage 标记 `missing_ppda_source`。

## 5. 赔率源调研

### 5.1 当前赔率缺口

模型正式做 AH/OU/CLV 需要：

- 1X2、Asian Handicap、Over/Under 三类市场。
- opening、T-24h、T-6h、T-1h、closing 快照。
- bookmaker 维度明细。
- 至少 3 家 bookmaker，最好 5 家以上。
- sharp / soft / exchange 分层。
- UTC `captured_at`、`kickoff_at` 和 `snapshot_type`。

当前生产缺口：

- 免费源没有确认 2026 世界杯 + AH + OU + bookmaker 明细 + closing。
- `odds-snapshots.json` 只能保留契约和状态，不能给强赔率结论。

### 5.2 BSD / Bzzoiro

当前结论：有希望补 1X2/OU，但不能解决当前生产赔率主线。

已验证：

- 已 live 获取通用 odds 行。
- 已获取 15 个 bookmaker。
- 通用 odds 行中观察到 `1x2`、`btts`、`double_chance`、`draw_no_bet`、`over_under_15`、`over_under_25`、`over_under_35`。

未通过：

- `league_id=16&season_id=82` 的 World Cup events 返回 0。
- `league_id=16&season_id=82` 的 World Cup odds 返回 0。
- AH 在 public v2 odds consensus docs 中未见。

原因判断：

- 不是 key 缺失；token live 请求能返回 bookmaker 和通用 odds。
- 不是接口完全不可用；`/api/v2/odds/` 可返回数据。
- 阻断点是 World Cup 2026 赛事映射/赛季参数未命中，且 AH 市场未公开文档化。

下一步：

- 可继续用 BSD token 查找真实 World Cup league/season/event 映射。
- 若找不到 World Cup event 或 AH，BSD 只能作为 1X2/OU 实验补源。

### 5.3 Odds-API.io

当前结论：可作为 AH/OU 实验补源或低置信度补源；不能作为生产级赔率主源。

需要的 key：

- 平台环境变量名：`ODDS_API_IO_KEY`
- 当前 probe endpoint：`https://api.odds-api.io/v3/odds?sport=football&apiKey=<key>`
- 申请入口：`https://odds-api.io/`
- 文档入口：`https://docs.odds-api.io/`

公开信息：

- 官网 pricing/free 页写明 REST 免费层 `free forever`、不需要信用卡、`100 requests/hour`、无试用到期时间。
- 官网首页价格卡写明免费层为 2 个 bookmaker、REST API access；付费 Starter 为 5 个 bookmaker、5,000 requests/hour。
- WebSocket 不是 REST 免费层的一部分。官网定价页把 WebSocket 标为 premium add-on，价格为对应 REST plan 的 2 倍；docs 也写明 WebSocket 是 add-on feature，需要账号启用。用户看到的 `Try WebSocket free for 3 days` 应理解为 WebSocket 实时推送试用，不是 REST free key 的 3 天有效期。
- 官网文档声明 Football、pre-match odds、live odds、ML/Asian Handicap/Over-Under 等市场可用；但免费层只有 2 个 selected bookmakers，会限制模型对 market consensus、sharp/soft 分层和 CLV 的可靠性。
- 这不是 iSportsAPI；iSportsAPI 的 15 天免费试用限制不适用于 Odds-API.io。

必须验证：

- World Cup / international football 成年赛事是否可用。
- 免费层具体可选哪 2 家 bookmaker，是否能选 Pinnacle/Bet365/Betfair 等关键书商。
- WebSocket 3 天试用是否只对 WebSocket add-on 生效，以及试用结束后 REST key 是否保持可用。

当前状态：

- 已用用户提供的 key live 验证 REST API。
- 正确流程是先 `GET /v3/events?sport=football&status=pending,live&bookmaker=Sbobet` 获取 `eventId`，再 `GET /v3/odds?eventId=<id>&bookmakers=Sbobet,Bet365`。
- 已验证一个待赛足球 event 返回 `ML`、`Spread`、`Totals`、`Alternative Asian Handicap`、`Alternative Goal Line`、`Goals Over/Under` 等 market。
- `Spread` / `Alternative Asian Handicap` 可映射为 AH，`Totals` / `Goals Over/Under` 可映射为 OU。
- 已新增小型采样脚本 `scripts/sample_odds_api_io_snapshots.py`。它会选取 3-5 场 pending/live 足球比赛，把原始响应写入 `data/raw/experimental/odds-api-io`，把映射结果和字段稳定性摘要写入 `reports/odds_api_io_sampling_report.json`；采样结果不得进入 normalized/model/public。
- 首次小型采样结果：5 场 pending/live 足球比赛，映射出 163 条候选标准行，其中 1X2 11 条、AH 77 条、OU 75 条。书商样本为 `Bet365`、`Bet365 (no latency)`、`Sbobet`；赛事样本为 U20 国际友谊赛、印度超、中超。该结果证明 AH/OU schema 映射可行，但仍未验证 2026 World Cup / 成年国际赛覆盖。
- 已新增 event scan 模式，报告为 `reports/odds_api_io_event_scan_report.json`。当前用 `Sbobet` 过滤分页扫描前 3 页、每页 30 条，得到 88 个去重 pending/live football events，没有发现 World Cup 候选，也没有发现成年国家队国际赛候选；可见赛事主要是俱乐部联赛/杯赛、青年国际赛和国际俱乐部杯赛。因此 2026 World Cup 覆盖仍不能确认。
- 复查规则：在 2026 World Cup 首场比赛前 5 天，必须重跑 Odds-API.io event scan，参数建议 `--scan-events --pages 5 --page-size 30 --bookmakers Sbobet,Bet365`。如果出现 World Cup / FIFA / senior international 候选赛事，再继续做 `eventId -> platform match_id` 映射和 AH/OU 字段复验；如果仍无候选，则维持 `world_cup_2026=unknown_or_not_visible_on_free_tier`。
- 本次样本为 International Youth / U20 Friendly，不是 2026 World Cup；因此 `world_cup_2026` 仍是 unknown。
- 免费层只有 2 个 selected bookmakers，当前建议选择 `Sbobet + Bet365`。这能补 AH/OU 缺口，但不足以支撑 market consensus、sharp/soft 分层、closing line value 或强 Kelly 结论。

### 5.4 雷速类

当前结论：雷速首页可匿名返回比赛列表和 match id；单场详情、数据页、情报页、赔率域 live 请求被 WAF / UA ACL 阻断，不能作为生产源。

2026-05-19 复查：

- GitHub repository search：`leisu football odds`、`雷速 足球 赔率`、`data.leisu.com odds`、`odds-3 leisu` 均未找到维护良好、能直接用于当前项目的 GitHub 源。
- GitHub code search 对 `data.leisu.com odds`、`odds-3 leisu` 未返回可采信项目；部分搜索结果为无关博彩/赔率项目。
- live 验证：`https://www.leisu.com/` 返回 200，HTML 内可见足球比赛列表、比赛链接、球队图片、`live.leisu.com/detail-<match_id>`、`guide/swot-<match_id>`、`shujufenxi-<match_id>` 等字段，因此公开首页可作为 match discovery 的实验线索。
- live 验证：`https://data.leisu.com/` 跳转到 `https://www.leisu.com/data` 后被阿里云 WAF 405 阻断。
- live 验证：`https://odds.leisu.com/` 返回阿里云 WAF 405 阻断页。
- live 验证：`https://live.leisu.com/detail-4498954` 和 `https://live.leisu.com/shujufenxi-4498954` 默认 curl 返回 `denied by UA ACL = not in whitelist` 并跳转 `h5.leisu.com/403`；模拟浏览器 UA 后返回阿里云 WAF JavaScript challenge，而不是实际比赛 JSON/HTML。
- live 验证：`https://www.leisu.com/data/zuqiu/comp-542` 与 `https://www.leisu.com/guide/swot-4498954` 返回 WAF 405 或 challenge。
- 因此雷速不能表述为“已验证可抓取赔率”。当前只能表述为“首页可发现比赛，详情/赔率/数据接口被 WAF 阻断，旧代码字段解析逻辑仅供理解”。

已检查 GitHub 项目：

| 项目 | 状态 | 能确认的字段 | 问题 |
|---|---|---|---|
| `psnewer/leisu` | Scrapy 旧项目 | `Match`：洲/国家/联赛/赛季/日期/主客队/比分；`Odds`：让球主/盘/客，标准主/平/客，大小球大/盘/小 | 旧 HTML 解析、无 license、非官方、未 live 跑通。 |
| `guanrongjia/thor` | Selenium 旧项目 | free.leisu.com 页面比赛数据、完赛/进行中比分 | Python 2.7、ChromeDriver 73、2019 代码、页面型爬虫，维护成本高。 |

注意：雷速当前已经完成最小 live 请求验证，但验证结果是“首页可发现比赛，单场详情/赔率/数据接口被 WAF 阻断”。不能表述为“已验证可抓取赔率”，只能表述为“旧项目代码中存在比分、1X2、让球、大小球字段解析逻辑，且官网首页可提供 match discovery 线索”。后续如果继续验证，必须单独建立 `data/raw/experimental/leisu` probe，且不得进入 normalized/public。

字段含义：

- `rangzhu/rangpan/rangke`：让球盘三元组，接近 AH。
- `biaozhu/biaoping/biaoke`：标准胜平负 1X2。
- `da/dapan/xiao`：大小球三元组。

不进入生产原因：

- 非官方逆向/页面爬虫。
- 老项目依赖过时 Selenium/Chromedriver/Python 2.7 或旧 Scrapy 页面结构。
- 合规与稳定性风险高。
- 未验证 2026 世界杯覆盖。
- 真实单场数据/赔率 live 请求被 WAF/UA ACL 阻断，需要浏览器挑战 cookie 或逆向，不适合数据层生产采集。

允许用途：

- 只作为字段理解、实验、离线研究。
- 如需 live，只能写 `data/raw/experimental/leisu`，不得进入 normalized/public。

### 5.5 HKJC

当前结论：HKJC 是有价值的赔率候选，但当前只能列为 `experimental_blocked_live`，不能进入生产。

已验证：

- GitHub 候选：`Bobosky2005/hkjc-api`。
- 仓库许可：MIT。
- 最近更新时间：2026-05-17。
- README 声明支持 football matches、match details、running/live match data、historic match results、football odds。
- 支持的足球赔率类型包括 `HAD` 主客和、`HHA/HDC` 让球、`HIL` 大小、`FHA/FHL` 半场市场、`CRS/FCS` 波胆、`TTG` 总进球、`HFT` 半全场等。
- 源码确认默认 GraphQL endpoint 为 `https://info.cld.hkjc.com/graphql/base/`。
- 本机最小 GraphQL 查询 `timeOffset { fb }` 返回正常，说明 endpoint 可达。

未通过：

- 本机直接查询 `matches`（含 `HAD/HHA/HIL` 或 `HAD/HDC/HIL/CRS`）返回 `WHITELIST_ERROR`。
- 本机直接查询 `matchResult` 历史赛果同样返回 `WHITELIST_ERROR`。
- 加 `origin: https://football.hkjc.com`、`referer`、`user-agent` 后仍返回 `WHITELIST_ERROR`。

原因判断：

- 不是网络完全不可达，因为 `timeOffset` 查询成功。
- 阻断点是 HKJC football `matches/matchResult` 下游白名单或访问策略。
- `hkjc-api` 是非官方 wrapper，不等于 HKJC 授权开放 API。

可获取字段，如果白名单问题解决：

- 比赛 ID、前端 ID、日期、开球时间、状态、主客队、赛事、场地、TV、running score、角球。
- 赔率池 `foPools`，含 `oddsType`、状态、更新时间、盘口线、选项、currentOdds。
- 历史赛果与 result-only payout pools。

当前处理：

- 不写 `normalized`、`model` 或 public API。
- 不作为 World Cup AH/OU 主线。
- 若继续验证，只能新增 `data/raw/experimental/hkjc` probe，先解决 `WHITELIST_ERROR`、条款审查和 match_id 映射，再考虑模型低置信补源。

### 5.6 TheOddsAPI / API-FOOTBALL / 付费源

| 来源 | 当前结论 | 费用判断 | 适合场景 |
|---|---|---|---|
| TheOddsAPI | 用户邮件确认免费层只 NBA/MLB；足球需 Business | Business $99/月 | 只有模型正式做 AH/OU/CLV 且确认 World Cup 覆盖后再考虑。 |
| API-FOOTBALL | 已有 key；World Cup 2026 `league=1,season=2026` 的 fixtures/odds live probe 均返回 plan restricted | Pro $19/月起 | Free 当前不能承担 2026 世界杯 runtime 主源；若升级套餐再重跑 endpoint probe。 |
| Sportmonks | 有 World Cup 包和 odds add-on | €69/€129+ 级别 | 若需要一体化世界杯数据可评估。 |
| TheStatsAPI | 待进一步合同确认 | $50/月起公开说法待核 | 可作为 odds/closing odds 候选。 |

性价比判断：

1. 先不买 TheOddsAPI Business。
2. API-FOOTBALL 已用现有 key 验证：Free 对 2026 World Cup fixtures/odds 计划受限，拿不到 sample fixture id，因此 lineups/injuries/events/statistics 暂无法验证真实字段覆盖。
3. 若模型正式启用 AH/OU/CLV，再确认 TheOddsAPI Business 是否覆盖 FIFA World Cup、AH、OU、Pinnacle/锐盘、closing/archive。
4. 免费/逆向赔率源只能补研究，不能作为正式盘口结论依据。

## 6. 人物/球员/教练/裁判数据

| 数据 | 当前状态 | 来源 | 缺口 |
|---|---|---|---|
| 主教练姓名/国家队 | 已有 48 队 | FIFA 官方文章 + manual patch | 上任时间、合同到期缺结构化来源。 |
| 主教练 nationality/DOB/age | 已有补充 | Reep / provider refs /人工审计 | 仍需官方或 Wikidata 交叉验证。 |
| 球员名单 | 9 队 234 人 | FIFA/足协官方名单 | 剩余 39 队等最终名单。 |
| 球员 club/shirt_number/DOB/age | 部分已有 | 官方名单 + dcaribou/Reep 补充 | 真实 2026 官方号码需最终名单。 |
| 球员 caps/goals | 部分已有 | 官方/历史活动补充 | 覆盖不均。 |
| 球员影响力 | proxy | dcaribou activity、FBref/Sofascore 实验 | 缺真实缺阵反事实、评分/xG/xA 全量覆盖。 |
| 裁判画像 | 英超样本已有 | football-data.co.uk / predictor assets | 世界杯裁判单场指派需等 FIFA match centre/report。 |
| 裁判风格 | 部分派生 | 英超历史红黄牌/点球/胜平负 | 不能直接套到世界杯裁判。 |

## 7. 不能获取或暂不生产化的原因分类

| 原因 | 具体表现 | 示例 |
|---|---|---|
| 官网/服务不支持免费足球 | 免费层没有目标运动或市场 | TheOddsAPI free 只 NBA/MLB；iSportsAPI free 15 天。 |
| 免费额度/套餐受限 | API 返回 plan restricted | API-FOOTBALL Free 对 World Cup 2026 fixtures/odds 受限；无 fixture id 时 lineups/injuries/events/statistics 也无法验证。 |
| 赛事未开始或不在时间窗口 | 正赛未开、赛前阵容未发布、天气窗口未到 | lineups、weather、match stats。 |
| 网站有数据但非官方/逆向 | 可抓但合规/稳定性差 | 雷速、OddsPortal、Sofascore wrapper。 |
| reader 不存在 | 当前库没有对应 reader | soccerdata FotMob。 |
| reader 有但 live 风险高 | 需要浏览器/反爬/长时间挂起 | soccerdata FBref/WhoScored。 |
| 字段没有直接提供 | 需要事件级推导或付费 tracking | PPDA、跑动距离、冲刺。 |
| ID 映射未打通 | 有数据但无法稳定映射到平台 match/team/player_id | Sofascore World Cup event、BSD World Cup event。 |

## 8. 当前优先级

### P0

- 若升级 API-FOOTBALL 套餐，重跑 World Cup 2026 odds / lineups / injuries / statistics / events 覆盖 probe；当前 Free 已判定计划受限。
- 等 FIFA/足协最终名单，补剩余 39 队 roster。
- 赔率源继续 probe：BSD 查真实 World Cup event mapping；用户申请 `ODDS_API_IO_KEY` 后跑 Odds-API.io live probe。

### P1

- 用 Sofascore wrapper 对 World Cup/国际赛 event 做低频实验验证，只写 raw/report。
- 用 FBref 缓存/低频实验补英超模型的主客场、射门、控球、犯规/拦截、裁判字段。
- 增强 venues：capacity、surface、roof_type、altitude、source_urls。

### P2

- WhoScored events 推导 PPDA 的实验研究。
- 雷速/国内逆向源只保留字段理解和离线实验。
- 人物风格蒸馏等赛后/长期模块。

## 9. 相关报告和脚本

| 类型 | 文件 |
|---|---|
| 免费赔率源 probe | `reports/free_odds_source_probe.json` |
| API-FOOTBALL World Cup runtime probe | `reports/api_football_worldcup_runtime_probe.json` |
| Sofascore direct endpoint probe | `reports/sofascore_source_probe.json` |
| Sofascore sample event direct endpoint probe | `reports/sofascore_event_sample_probe.json` |
| Sofascore wrapper live 验证 | `reports/sofascore_wrapper_live_field_validation.json` |
| soccerdata Sofascore probe | `reports/soccerdata_sofascore_probe.json` |
| soccerdata FBref/FotMob/WhoScored probe | `reports/soccerdata_advanced_sources_probe.json` |
| 模型数据缺口评估 | `docs/2026-05-18-predictor-post-model-data-gap-assessment-cn.md` |
| 运行期数据需求 | `docs/2026-05-17-predictor-runtime-data-requirements-cn.md` |
| 国内/第三方源评估 | `docs/2026-05-16-domestic-football-data-sources-evaluation-cn.md` |
