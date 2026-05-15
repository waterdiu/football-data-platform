# World Cup Predictor Integration Design

日期：2026-05-15  
状态：平台侧对接设计基线

## 1. Purpose

这份文档定义 `football-data-platform` 与 `world-cup-predictor` 之间的世界杯数据对接层。

目标不是立刻让 predictor 全量切换，而是先完成三件事：

1. 把 predictor 已经下载并落盘的世界杯相关数据迁移到平台
2. 在平台内定义 predictor 可直接消费的静态契约
3. 为 predictor 后续切换提供低风险的分阶段路径

## 2. Why The Predictor Needs A Separate Integration Layer

`worldcup/2026` 的接入主要是展示数据，旧结构较薄，适合直接用 `site/*` 兼容接口替换。

`world-cup-predictor` 不一样：

- 同时存在训练输入、赛前运行输入、模型输出、上下文快照
- 已下载数据分散在 `raw / processed / runtime`
- 一部分文件是 platform 标准层可以直接复用的
- 另一部分文件是 predictor 特有的旧格式，不能直接要求模型脚本当天全部改掉

因此 predictor 需要一个单独的 compatibility layer。

## 3. Scope

本设计最初只覆盖“世界杯对接层需要的已下载数据”。截至 2026-05-15，平台侧已经扩展为两层：

- World Cup predictor runtime compatibility layer
- Full predictor data asset manifest layer

全量资产层已经把 `world-cup-predictor/backend/data` 的现有文件镜像到平台本地资产区，并通过 manifest 发布索引。

纳入范围：

- `backend/data/raw/world_cup_2026_shared_fixtures.json`
- `backend/data/processed/world_cup_2026_fixtures.json`
- `backend/data/processed/predictions.json`
- `backend/data/runtime/odds_snapshots.json` 中的世界杯条目
- `backend/data/runtime/context/world_cup_context_snapshots.jsonl`，如果存在

已纳入全量资产镜像：

- Premier League 训练资产
- StatsBomb 全量历史原始文件
- 通用模型训练 CSV
- 非世界杯 context probe 调试文件
- runtime odds / context / cooldown / probe 文件

大型原始文件只保存在平台本地镜像，不发布到 GitHub Pages runtime bundle。

## 4. Platform-Owned Masters

迁移后，这些文件会沉淀为平台 own master：

- `data/normalized/world_cup_2026_predictor_shared_fixtures_master.json`
- `data/normalized/world_cup_2026_predictor_feature_inputs_master.json`
- `data/normalized/world_cup_2026_predictor_predictions_source_master.json`
- `data/normalized/world_cup_2026_predictor_odds_source_master.json`
- `data/normalized/world_cup_2026_predictor_context_source_master.json`

其中：

- `shared_fixtures_master` 保留 predictor 旧的 `world_cup_2026_shared_fixtures.json` 形状
- `feature_inputs_master` 保留 predictor 旧的 `world_cup_2026_fixtures.json` 形状
- `predictions_source_master` 保留 predictor 旧的 `processed/predictions.json` 形状
- `odds_source_master` 和 `context_source_master` 只记录实际存在的世界杯条目

## 5. Predictor Contract

平台对 predictor 发布两层数据：

### 5.1 Compatibility Datasets

用于最小改动切换 predictor：

- `shared-fixtures.json`
- `feature-inputs.json`
- `predictions-source.json`
- `odds-source.json`
- `context-source.json`

### 5.2 Standard Datasets

用于后续真正收敛到平台标准契约：

- `canonical-teams.json`
- `teams.json`
- `fixtures.json`
- `results.json`
- `standings.json`
- `predictions.json`
- `data-coverage.json`
- `odds-snapshots.json`
- `lineups.json`
- `injuries.json`
- `prematch-context.json`
- `weather.json`

## 6. Publish Surface

平台提供 predictor 专用静态接口目录：

- `data/public/api/worldcup/2026/predictor/manifest.json`
- `data/public/api/worldcup/2026/predictor/bundle.json`

以及拆分数据文件：

- `shared-fixtures.json`
- `feature-inputs.json`
- `predictions-source.json`
- `odds-source.json`
- `context-source.json`
- `fixtures.json`
- `results.json`
- `standings.json`
- `predictions.json`
- `data-coverage.json`
- `odds-snapshots.json`
- `lineups.json`
- `injuries.json`
- `prematch-context.json`
- `weather.json`

平台还提供 predictor 全量数据资产清单接口：

- `data/public/api/predictor/data-assets/manifest.json`
- `data/public/api/predictor/data-assets/summary.json`
- `data/public/api/predictor/data-assets/categories/*.json`

全量文件本体位于：

- `data/predictor-assets/files/**`

## 7. Recommended Migration Path

推荐顺序：

1. predictor 先读 `shared-fixtures.json`
2. 再读 `feature-inputs.json`
3. 再切到平台标准 `fixtures.json / results.json / standings.json`
4. 预测输出继续写本地，再由平台导入
5. 最后再切 `odds / injuries / prematch-context / weather`

原因：

- 先切 compatibility layer，最小化改动
- 先验证结果一致性，再逐步移除旧路径
- 把最容易变动的上下文层放到最后切

## 8. Current Reality

截至 2026-05-15：

- predictor 本地存在完整的世界杯 feature inputs 与 predictions source
- predictor 本地不存在 `world_cup_context_snapshots.jsonl`
- predictor 当前 `odds_snapshots.json` 未发现世界杯条目

因此平台当前可以先完成：

- fixtures / feature inputs / predictions source 迁移
- predictor compatibility API 发布

但还不能假装：

- 世界杯 odds 已经迁完
- 世界杯 context snapshots 已经迁完

这些缺口需要等 predictor 后续实际生成对应快照，再回灌到平台。

## 9. Full Asset Layer Current Reality

截至 2026-05-15：

- 已迁移文件数：`404`
- 已迁移总大小：`1146108149` bytes
- 最大类别：`raw.statsbomb_events`，`314` 个文件
- 平台本地镜像：`data/predictor-assets/files`
- 公开清单：`https://waterdiu.github.io/football-data-platform/api/predictor/data-assets/manifest.json`
- 公开摘要：`https://waterdiu.github.io/football-data-platform/api/predictor/data-assets/summary.json`

模型项目后续应该通过一个统一 loader 解析平台 manifest，再读取 `platform_path` 指向的本地文件；旧的 `backend/data/<relative_path>` 只作为迁移期 fallback。
