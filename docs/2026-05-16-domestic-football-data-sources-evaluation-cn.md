# 国内与第三方足球数据源 GitHub 项目评估

日期：2026-05-16  
项目：`football-data-platform`  
状态：候选数据源评估文档  
主基线文档：`/Users/chamcham/Documents/AI/CODEX/soccer/football-data-platform/DESIGN.md`

## 1. 评估目标

本评估用于判断国内或中文生态相关足球数据源是否适合进入 `football-data-platform`。

重点关注：

- 球员、教练、裁判档案
- 实时比分、赛程、阵容、事件
- 欧赔、亚盘、大小球、盘口变化
- 能否稳定进入生产数据层
- 是否只能作为实验性补源

评估原则：

- 官方授权 API 优先。
- 离线公开数据集优先于逆向实时爬虫。
- 爬虫/逆向项目默认不进入生产主链路。
- 能进入 `data/normalized` 的数据必须可追溯、可复现、可解释。
- 高风险数据最多进入 `data/raw/experimental`，不得默认发布到 public API。

## 2. 国内源总体判断

国内源不是不能用，但应分层使用：

| 层级 | 数据源类型 | 是否推荐 | 用途 |
|---|---|---|---|
| 官方公开网页 | 中国足协、竞彩官网、赛事官网 | 中 | 公告、赛程、名单、裁判公告 |
| 资讯平台页面 | 懂球帝、雷速、雪缘园等 | 低到中 | 线索、人工校验、非生产补源 |
| 逆向接口/爬虫 | 雷速、懂球帝、500 彩票等非公开接口 | 低 | 实验、研究、离线验证 |
| 授权商业 API | 正规赔率/体育数据 API | 高 | 生产采集主链路 |
| GitHub 开源数据集 | CSV/Parquet/identity mapping | 高到中 | 离线基础档案和 ID 映射 |

结论：

- 国内数据源可以补强赔率、中文名称、国内赛事、资讯线索。
- 不应把国内逆向爬虫作为世界杯生产数据主链路。
- 对人物档案和风格蒸馏，国内源更适合作为“补充线索”，不是能力评分主依据。

## 3. 已检索 GitHub 项目

### 3.1 懂球帝相关

项目：`pengshiqi/Dongqiudi`

地址：`https://github.com/pengshiqi/Dongqiudi`

检索结果说明：

- 该项目是懂球帝 App 抓包和分析项目。
- README 提到使用 Charles 抓包懂球帝 App API。
- 更偏研究与逆向分析。

适配判断：

| 项目 | 判断 |
|---|---|
| 数据覆盖 | 新闻、App API、部分足球实体线索 |
| 稳定性 | 低 |
| 合规风险 | 高 |
| 上手成本 | 中 |
| 是否进生产 | 否 |
| 推荐用途 | 实验性研究、中文名称/资讯线索验证 |

平台策略：

- 不写入 `data/normalized`。
- 如需试验，只允许进入 `data/raw/experimental/dongqiudi`。
- 不发布 public API。

### 3.2 雷速相关

已知类别：

- `bet3651/foot`
- `leisu-urllib`
- `leisu-spider`
- `leisu-mqtt`
- 其他 data.leisu.com 示例项目

当前判断：

- 雷速确实有比分、赔率、盘口、部分阵容/事件类展示数据。
- 但 GitHub 项目大多是逆向或爬虫，没有官方 API 保障。
- 赔率数据价值高，但生产风险也高。

适配判断：

| 项目类型 | 判断 |
|---|---|
| 数据覆盖 | 高，尤其赔率/盘口/比分 |
| 稳定性 | 低到中 |
| 合规风险 | 高 |
| 上手成本 | 中到高 |
| 是否进生产 | 否 |
| 推荐用途 | 赔率结构研究、离线校验、盘口字段设计参考 |

平台策略：

- 不作为 `odds` 主源。
- 不进入自动采集流水线。
- 不发布到 public API。
- 如需验证，只放 `data/raw/experimental/leisu`。
- 转入 normalized 前必须人工确认，并标记 `source_status=experimental_third_party_verified`。

### 3.2.1 雪缘园（OKOOO）补充评估（重要）

定位：雪缘园（`okooo.com`）相对“资讯平台”更偏竞彩聚合与历史数据展示，潜在价值不在于实时抓取，而在于：

- 历史赛果/赔率的离线校验与回测补充（尤其是国内联赛、杯赛、竞彩口径的历史赔率走势）。
- 作为“历史一致性验证补源”，用于检测主源的缺失或异常（不用于实时生产采集）。

平台策略：

- 默认不进入生产采集流水线。
- 允许以“离线一次性导入 + 人工抽样校验”的方式落 `data/raw/experimental/okooo`。
- 只有在明确授权/条款允许、并且与至少一个官方/授权源交叉验证通过后，才允许以 `verified_third_party` 状态进入 `data/normalized`（且默认不发布 public API）。

### 3.3 500 彩票 / 中国竞彩网相关

检索结论：

- GitHub 上存在大量彩票/赔率爬虫或开奖爬虫，但足球专项、稳定维护、字段清晰的项目较少。
- 500彩票网和竞彩网适合赔率/赛程/赛果线索，但爬虫稳定性和合规边界需要谨慎。

适配判断：

| 数据 | 判断 |
|---|---|
| 赛程/赛果 | 可作为校验源 |
| 赔率 | 有价值但合规敏感 |
| 球员/教练/裁判 | 覆盖弱 |
| 生产可用性 | 不建议 |

平台策略：

- 只作为赔率字段结构参考或人工校验来源。
- 不作为人物档案主源。
- 不高频抓取。

### 3.4 港澳来源：HKJC API

项目：`Bobosky2005/hkjc-api`

地址：`https://github.com/Bobosky2005/hkjc-api`

检索结果说明：

- Node.js 包，封装香港赛马会 GraphQL API。
- 包含 Football API。
- 可获取比赛、详情和多种赔率玩法。

适配判断：

| 项目 | 判断 |
|---|---|
| 数据覆盖 | 足球比赛、赔率 |
| 稳定性 | 中 |
| 合规风险 | 中到高，必须优先确认使用条款 |
| 上手成本 | 低到中 |
| 是否进生产 | 条款确认前不进；条款允许后可作为“硬书商基准”候选 |
| 推荐用途 | 合规优先验证；若允许，作为 sharp bookmaker 赔率补源/校验源 |

平台策略：

- 将 HKJC 从“字段结构实验”提升为“优先合规验证”事项（先看条款，再谈接入）。
- 条款确认前，依然只允许落 `data/raw/experimental/hkjc`（且低频抓取）。
- 若条款允许进入数据分析/研究用途，再评估是否进入 `data/normalized` 的 `odds` 校验链路（仍默认不发布 public API）。

### 3.5 国内授权商业数据 API（调研占位）

现状：本阶段尚未选定“明确授权、可稳定使用”的国内商业足球数据 API 供应商。

为什么要单列这一类：

- 合规风险显著低于逆向/抓包。
- 稳定性和可维护性更适合进入生产采集链路。

平台策略：

- 后续若引入，必须把授权证明/条款摘要写入 `docs/` 并在 `DESIGN.md` 的数据源表中登记。
- 未完成条款确认前，不得进入 `data/normalized` 和 public API。

## 4. 非国内但高价值 GitHub 项目

### 4.1 Reep

项目：`withqwerty/reep`

地址：`https://github.com/withqwerty/reep`

价值：

- 足球实体身份映射库。
- 覆盖球员、教练、球队、赛事、赛季。
- `people.csv` 当前版本 444,707 人（Reep `meta.json` data_version `2026.17`）。
- 支持 Transfermarkt、FBref、UEFA、Sofascore 等多 provider ID 映射。
- 仓库许可证为 CC0-1.0。

适配判断：

| 项目 | 判断 |
|---|---|
| 数据覆盖 | 球员/教练身份映射很强 |
| 稳定性 | 中到高 |
| 合规风险 | 中，需看数据来源/许可证 |
| 上手成本 | 低 |
| 是否推荐 | 推荐评估接入 |

平台策略：

- 优先作为 `person_id_map_master` 的候选源。
- 不覆盖 FIFA 官方名单。
- 用于解决同名球员、不同平台 ID 映射问题。
- 接入前必须先做世界杯名单覆盖率验证，命中率低于 70% 则不作为世界杯人物映射主选。
- 覆盖率验证脚本：`scripts/validate_reep_worldcup_coverage.py`
- 覆盖率报告：`reports/reep_worldcup_coverage.json`
- 当前状态：覆盖率验证已通过。基于当前 208 名已导入世界杯球员，命中 197 人，命中率 94.7115%，高于 70% 门槛；仍必须完成许可证审查和歧义匹配处理后才能进入正式 ID map。
- 许可证状态：已确认 CC0-1.0；当前允许作为 `person_id_map_master` 候选导入源，但不得覆盖官方 roster/player master。
- 导入脚本：`scripts/import_reep_person_id_map.py`
- 导入报告：`reports/person_id_map_import_report.json`
- 当前导入结果：208 条映射，205 条已唯一解析到 Reep，0 条 ambiguous，3 条 Reep missing；11 条同名/拼写差异已通过 `data/patches/person_id_map.manual.json` 人工审查消歧，2 条通过 Reep `names.csv` 别名表解析。剩余 3 条 missing 已在 `data/patches/person_id_map.external_unresolved.json` 保存外部 provider 证据，并以 `identity_status=platform_identity_with_external_refs` 作为平台自有身份供后续消费；因 Reep 缺行，仍不发布为 Reep 映射。未解决清单见 `reports/person_id_map_unresolved_report.json`。

### 4.2 StatsBomb Open Data

价值：

- 官方开源事件数据。
- 适合训练风格标签规则和事件指标。

限制：

- 不保证 2026 世界杯实时覆盖。
- 覆盖赛事有限。

平台策略：

- 用于 `person_style_profiles` 的 historical evidence。
- 不作为实时名单/赛程源。

### 4.3 dcaribou Transfermarkt Datasets

价值：

- 离线 CSV/Parquet 更适合批量导入。
- 比实时爬虫稳定。

限制：

- 非官方 Transfermarkt 派生数据。
- 需要确认许可证和字段质量。

平台策略：

- 适合进入 `third_party_transfermarkt_dataset` 导入流程。
- confidence 默认 `medium`。

## 5. 推荐分级

### 可以优先做验证

| 源 | 目的 | 原因 |
|---|---|---|
| Reep | 人物 ID 映射 | 解决球员/教练跨平台 ID |
| dcaribou transfermarkt-datasets | 人物基础档案补充 | 离线数据比爬虫稳 |
| StatsBomb Open Data | 风格蒸馏样本 | 事件级数据权威 |
| HKJC API | 优先合规验证 | 若条款允许，可作为硬书商赔率基准候选 |

### 只做实验，不进生产

| 源 | 原因 |
|---|---|
| 雷速爬虫/逆向 | 无官方 API，反爬和合规风险高 |
| 懂球帝 App 逆向 | 抓包项目，不适合作为平台主源 |
| 500 彩票/竞彩网爬虫 | 赔率合规敏感，字段稳定性不确定 |
| OddsPortal 爬虫 | 国际源，但同样属于爬虫风险 |

## 6. 数据层接入策略

### 6.1 新增实验目录

```text
data/raw/experimental/
  leisu/
  dongqiudi/
  hkjc/
  cnlottery/
```

实验源规则：

- 默认不运行。
- 默认不发布。
- 默认不进入 normalized。
- 必须有 `source_risk.json`。
- 必须记录采集时间、URL、请求频率、字段样例。

### 6.2 新增候选源评估报告

建议输出：

- `reports/third_party_source_evaluation.json`

字段：

```json
{
  "source_id": "leisu",
  "category": "domestic_scraper",
  "coverage": ["odds", "scores", "lineups"],
  "stability": "low",
  "legal_risk": "high",
  "production_allowed": false,
  "normalized_allowed": false,
  "public_api_allowed": false,
  "recommended_use": "experimental_validation_only"
}
```

### 6.3 normalized 准入规则

实验源数据进入 normalized 需要满足：

1. 非唯一事实源。
2. 有官方或授权源交叉验证。
3. 字段映射稳定。
4. 采集方式低频、可复现。
5. `source_status` 明确标记为 `experimental_third_party_verified`。

## 7. 30 天窗口内行动时间轴（建议）

当前日期：2026-05-16；世界杯开赛：2026-06-11。

- 本周：用 `scripts/validate_reep_worldcup_coverage.py` 验证 Reep 对已导入世界杯官方名单的覆盖率，决定是否继续推进 Reep 作为世界杯 ID 映射候选。
- 本周：对 HKJC 做“条款与合规可用性”优先验证，结论写入本文件并同步更新 `reports/third_party_source_evaluation.json`。
- 下周：接入 `dcaribou/transfermarkt-datasets` 的离线导入流程，用于补齐人物基础事实字段（不影响世界杯前主链路）。
- 5 月底前：随着 FIFA/足协名单逐步公布，持续用 manual patch 流水线导入世界杯 rosters（见 roster 专题文档与脚本）。

## 8. 对人物档案层的影响

人物档案数据源优先级调整：

1. FIFA / 足协官网：名单、主教练、官方公告。
2. Reep：人物 ID 映射。
3. Transfermarkt 离线数据集：年龄、俱乐部、身价、转会历史补充。
4. StatsBomb：事件特征和风格 evidence。
5. 国内资讯/爬虫源：只做线索，不直接进入 master。

裁判数据：

- 国内源对世界杯裁判帮助有限。
- 裁判主源仍应是 FIFA official list 和 match centre。
- 雷速等源可用于历史执法倾向线索，但不进 production。

赔率数据：

- 国内源可帮助理解亚盘/大小球字段。
- 正式赔率源仍优先可授权 API。
- 雷速/HKJC/竞彩网等必须先做合规审查。

## 9. 当前结论

国内源值得研究，但不是生产主链路的答案。

更合理的路线：

1. 用国内源补充赔率字段理解和中文资讯线索。
2. 用 Reep 和 Transfermarkt 离线数据集补人物身份与基础档案。
3. 用 StatsBomb Open Data 做风格蒸馏样本。
4. 把雷速/懂球帝等逆向源隔离在 experimental。
5. 生产 API 只发布官方、授权、或经过人工审核的数据。
