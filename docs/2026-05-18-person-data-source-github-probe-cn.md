# 人物数据 GitHub 源调研报告

日期：2026-05-18  
项目：`football-data-platform`  
状态：数据源调研 / 接入前评估  
主基线文档：`/Users/chamcham/Documents/AI/CODEX/soccer/football-data-platform/DESIGN.md`

## 1. 目标

本次调研只回答一个问题：GitHub 上是否有可复用的足球人物数据项目，可以补齐：

- 主教练 `appointed_at` / `contract_until`
- 球员 `shirt_number` / caps / goals / minutes / injuries / impact / style
- 裁判名单、执法记录和裁判风格画像

调研结论不能自动进入 canonical 数据。任何第三方数据都必须先经过许可证、字段覆盖率、身份映射、来源状态和数据质量检查。

## 2. 总体结论

GitHub 上有可用人物数据项目，但没有一个项目能直接完整解决三类人物档案：

- 主教练 `appointed_at` / `contract_until`：未找到可直接生产接入的开源结构化源。
- 球员基础和国家队表现：有候选源，其中 `dcaribou/transfermarkt-datasets` 可继续生产接入，`salimt/football-datasets` 字段看起来有价值但许可证缺失，暂不能进入生产。
- 球员真实风格：需要事件级数据。`statsbomb/open-data` 可做历史样本和风格规则训练，但覆盖不等于 2026 世界杯全量球员。
- 裁判画像：`football-data.co.uk` 历史 CSV 已能做裁判尺度样本；世界杯裁判名单和单场指派仍必须等 FIFA 官方。

## 3. 数据源评估

| 源 | 仓库 | 许可证状态 | 可用字段 | 生产结论 |
| --- | --- | --- | --- | --- |
| Reep | `withqwerty/reep` | CC0-1.0，已审查 | 人物 ID、Wikidata、Transfermarkt、NFT、FBref 等 provider refs | 已用于 `person_id_map`，不能覆盖官方事实 |
| dcaribou Transfermarkt datasets | `dcaribou/transfermarkt-datasets` | CC0-1.0 | players、clubs；仓库通常还包含 appearances/games/lineups/events 等数据表 | 可继续生产接入，当前已用 players/clubs 补 profile |
| salimt football-datasets | `salimt/football-datasets` | GitHub license metadata 为空 | `player_profiles.csv`、`player_national_performances.csv`、`player_injuries.csv` 等 | 只能 probe，不得写 normalized/public，除非许可证明确 |
| StatsBomb open-data | `statsbomb/open-data` | 非标准许可证 / NOASSERTION | events、lineups、matches、360 | 可做研究和风格规则样本；生产发布前需许可证审查 |
| 非官方 Transfermarkt client | `wcarmesini/transfermarkt_api_client` 等 | 非官方接口 | 球员/教练/裁判抓取 | 只能 experimental，不进生产链路 |

`salimt/football-datasets` 的授权状态需要特别记录：GitHub repository API 返回 `license=null`；根目录 contents 只有 `.gitattributes`、`.github`、`README.md`、`README_data.md` 和 `datalake`；直接请求 `LICENSE` 返回 404；递归 tree 未发现 `license`、`copying`、`notice` 类文件。README 中虽然有 GitHub License badge 并链接到 `/blob/main/LICENSE`，但目标文件不存在。因此该源只能做字段和覆盖率 probe，不能进入 `normalized` 或 `public`。

## 4. 字段覆盖判断

### 4.1 主教练任期

当前可用数据：

- Reep coach rows：可补 `nationality`、`date_of_birth`、`age`、`key_wikidata`、`key_transfermarkt_manager`。
- FIFA 官方文章：可确认当前主教练身份。

当前不可直接补：

- `appointed_at`
- `contract_until`

原因：

- Reep 不提供任期字段。
- Transfermarkt manager profile 页面存在 WAF human verification，不能作为稳定自动采集源。
- Wikidata 是否有当前国家队任期 qualifier 需要逐项验证，不能假设 48 人都有。

生产规则：

- `appointed_at` 只能来自足协公告、FIFA 官方 profile、Wikidata 带 start-time qualifier 的当前职务、或人工审计 patch。
- `contract_until` 只能来自官方公告或明确可信 profile；没有明确来源时保持 `pending_source`。

### 4.2 球员基础和影响力

当前已生产接入：

- `dcaribou/transfermarkt-datasets` players 表
- 通过 Reep `key_transfermarkt` 映射补 `club`、DOB、age、caps、goals、market value 和展示型 `impact_proxy_score`

仍缺：

- `shirt_number`
- 真正的 `absence_impact_pct`
- minutes / recent appearances
- 事件级风格

下一步优先扩展：

- dcaribou additional tables：`appearances`、`games`、`game_lineups`、`game_events`、`player_valuations`
- salimt probe：`player_national_performances.csv`、`player_injuries.csv`

限制：

- salimt 仓库没有明确 license metadata，不能直接进入 normalized/public。
- `impact_proxy_score` 只是展示型代理分，不是缺阵百分比，也不是模型投注信号。

### 4.3 球员风格

真实风格需要：

- 事件数据
- 出场分钟
- 足够样本
- 位置/角色上下文

可用方向：

- StatsBomb open-data：做风格规则样本，不覆盖全量。
- dcaribou appearances/events：可做出场、进球、助攻、牌、比赛级行为 proxy，但不是完整事件风格。

规则：

- 样本不足时继续 `distillation_status=insufficient_sample`。
- 不允许用名字、名气、身价直接生成风格标签。

### 4.4 裁判

当前已生产接入：

- `football-data.co.uk` / predictor migrated EPL CSV 中的 `Referee`、红黄牌、赛果、进球
- 已发布 50 名英超历史裁判样本

仍缺：

- FIFA 2026 世界杯裁判名单
- 单场裁判指派
- 世界杯/国际赛裁判样本

规则：

- 历史英超裁判样本只能做风格/尺度参考，不代表世界杯裁判名单。
- 世界杯裁判名单必须等 FIFA 官方。

## 5. 推荐接入顺序

1. 扩展 dcaribou Transfermarkt 数据表。
   - 目标：minutes、appearances、goals/assists、cards、player valuation history。
   - 状态：可生产接入，许可证已知。

2. 建 salimt source probe。
   - 目标：只下载样本头部和 coverage，不写 normalized/public。
   - 阻断：许可证缺失。

3. 建 coach tenure manual patch。
   - 目标：允许人工审计写入 `appointed_at` / `contract_until`。
   - 来源：足协公告、FIFA、Wikidata qualifier、官方 profile。

4. 建 StatsBomb style sample pipeline。
   - 目标：抽取历史事件样本，训练/验证风格蒸馏规则。
   - 限制：非全量人物覆盖，生产发布需许可证审查。

## 6. 当前决策

- 不把 `salimt/football-datasets` 直接接入生产。
- 不用非官方 Transfermarkt API client 做生产抓取。
- 继续优先扩展 dcaribou CC0 离线数据。
- 教练任期走 manual audited patch + 可验证官方/Wikidata evidence。
- 球员风格保持 evidence-first，样本不足继续 `insufficient_sample`。

## 7. 本地就绪度探针

已新增只读探针：

- 脚本：`scripts/build_person_data_source_readiness.py`
- 报告：`reports/person_data_source_readiness.json`

当前报告结论：

- 本地 dcaribou 资产现在包括人工下载的 `transfermarkt-datasets.duckdb`，可读表包含 `games`、`appearances`、`game_events`、`game_lineups`、`club_games`、`player_valuations` 等完整活动表。
- dcaribou DuckDB 可继续补球员 club、DOB、age、caps、goals、market value、历史出场、分钟、进球助攻、牌、历史号码候选和身价历史。
- dcaribou 仍不能直接给出 FIFA 2026 官方 `shirt_number`，也不能单独生成真实 `absence_impact_pct` 或事件级风格；这些仍需要官方号码、伤停/可用性 evidence、国家队上下文和样本规则。
- dcaribou README 提供公开 R2 下载入口：`transfermarkt-datasets.duckdb`、`transfermarkt-datasets.zip`，以及 `players.csv.gz`、`games.csv.gz`、`appearances.csv.gz`、`game_events.csv.gz`、`game_lineups.csv.gz`、`club_games.csv.gz` 等单表 URL，基础路径为 `https://pub-e682421888d945d684bcae8890b0ec20.r2.dev/data/`。当前环境对 R2 的 HEAD probe 长时间无响应，暂记录为“入口已发现，连通性未验证”，不能直接进入自动下载生产任务。
- 本地 StatsBomb 资产有 314 场比赛、314 个事件文件、约 110 万事件、2285 个球员名，可用于风格规则样本验证，但不能视为 2026 世界杯名单全量覆盖。
- 本地 FBref / player ability / EPL availability 资产只能作为英超或规则样本，不能覆盖 2026 世界杯国家队事实。

因此，下一步如果要继续补人物页数据，优先任务不是改前端或模型，而是补齐 dcaribou 的 CC0 追加表，或建立经过审计的官方 / Wikidata / 人工 patch 链路。

建议导入顺序：

1. 先人工下载或 CI 下载 `transfermarkt-datasets.duckdb` 到 `data/raw/vendor/dcaribou_transfermarkt/`，不提交大文件。
2. 用 DuckDB 导出平台需要的窄表：`players`、`national_teams`、`games`、`appearances`、`game_lineups`、`game_events`、`club_games`、`player_valuations`。
3. 只把经过 roster / person_id_map 匹配后的世界杯相关增量写入 normalized；原始全量文件留在 raw/vendor 或外部缓存。
4. 导出字段必须保留 dcaribou player_id / game_id / source table / generated_at，便于回溯。

当前已落地：

- 脚本：`scripts/import_dcaribou_person_activity.py`
- 输入：本地 `transfermarkt-datasets.duckdb`，默认查找 `data/raw/vendor/dcaribou_transfermarkt/transfermarkt-datasets.duckdb` 或 `/Users/chamcham/Downloads/transfermarkt-datasets.duckdb`
- 输出：`data/normalized/person_player_dcaribou_activity_master.json`
- API：`api/worldcup/2026/core/player-dcaribou-activity.json`
- 覆盖：234 名已映射或兜底匹配球员，其中 198 名有出场/分钟汇总，222 名有历史号码候选，215 名有事件汇总，175 名有身价历史
- 韩国队补齐规则：Reep 缺少 24 名韩国队球员的 `key_transfermarkt`。导入脚本使用 dcaribou DuckDB 的“国家 + 姓名倒序唯一匹配”兜底，已补 22 名。`Kim Taehyeon` 和 `Lee Kihyuk` 已通过 audited external evidence 补入 Transfermarkt provider refs。
- 未匹配报告：`reports/dcaribou_person_activity_unresolved_report.json`，仅用于人工审计，不进入 public API；当前 unresolved count 为 0。

限制：

- 历史号码候选来自 Transfermarkt lineups，可能混合俱乐部和国家队场景，不是 FIFA 2026 官方球衣号码。
- 活动数据可以用于人物页“历史活动/经验/近期出场”展示，不可直接作为确认首发、伤停影响或 betting model signal。
