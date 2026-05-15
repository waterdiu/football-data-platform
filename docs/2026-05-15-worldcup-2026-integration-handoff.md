# World Cup 2026 Integration Handoff

日期：2026-05-15  
状态：可直接交给 `worldcup/2026` 实施

## 1. Goal

让 `worldcup/2026` 从“构建前同步 TS 文件”过渡到“页面运行时直接读取 `football-data-platform` 静态 JSON API”。

第一阶段目标不是重写页面，而是：

- 先接稳定 endpoint
- 保留本地 `src/data/*.ts` fallback
- 优先用 `site/*` 兼容接口
- 页面稳定后再逐步切向 `core/*`

## 2. Production Endpoints

发现入口：

- `https://waterdiu.github.io/football-data-platform/api/worldcup/2026/manifest.json`

页面兼容入口：

- `https://waterdiu.github.io/football-data-platform/api/worldcup/2026/site/bundle.json`

标准化入口：

- `https://waterdiu.github.io/football-data-platform/api/worldcup/2026/core/bundle.json`

## 3. Recommended Read Order

页面层统一按这个顺序读：

1. 请求 `manifest.json`
2. 从 `manifest.runtime_contract.preferred_site_url` 读取 `site/bundle.json`
3. 如果远端请求失败，fallback 到当前本地 `src/data/*.ts`
4. 只在确实需要标准化数据时，再读取 `core/*`

## 4. What To Use First

优先让这些页面入口改读 `site/bundle.json`：

- `groups`
- `group_fixtures`
- `group_stage_matches`
- `bracket`
- `full_schedule`
- `finals_results`
- `finals_coverage`
- `qualifier_matches`

对应 `site/bundle.json` 里的字段：

- `datasets.groups`
- `datasets.group_fixtures`
- `datasets.group_stage_matches`
- `datasets.bracket`
- `datasets.full_schedule`
- `datasets.finals_results`
- `datasets.finals_coverage`
- `datasets.qualifier_matches`

## 5. Fallback Rule

运行时读取失败时，页面必须 fallback 到现有本地数据：

- `src/data/groups.ts`
- `src/data/groupFixtures.ts`
- `src/data/groupStageMatches.ts`
- `src/data/bracket.ts`
- `src/data/fullSchedule.ts`
- `src/data/finalsMatchResults.ts`
- `src/data/finalsDataCoverage.ts`
- `src/data/qualifierMatches.ts`

这样即使 Pages 临时不可用，站点也不会白屏。

## 6. Suggested Data Client

建议在 `worldcup/2026` 新增一个统一读取层，例如：

- `src/lib/dataClient.ts`

它至少提供：

- `getWorldCupSiteBundle()`
- `getWorldCupCoreBundle()`
- `getWorldCupManifest()`

逻辑要求：

1. 先请求线上 `manifest.json`
2. 按 manifest 返回的 `preferred_site_url` 读 bundle
3. 如果网络失败、JSON 失败或超时，切本地 fallback
4. 返回的数据形状尽量贴近当前页面已有结构

## 7. Minimal Runtime Contract

### site/bundle.json

适合直接替换现有页面数据入口，字段：

- `generated_at`
- `competition_id`
- `season_id`
- `datasets`

`datasets` 下包含：

- `groups`
- `group_fixtures`
- `group_stage_matches`
- `bracket`
- `full_schedule`
- `finals_results`
- `finals_coverage`
- `qualifier_matches`
- `qualifier_missing_data`
- `qualifier_source_reports`

### core/bundle.json

适合后续重构页面数据层，字段：

- `canonical_teams`
- `teams`
- `fixtures`
- `results`
- `standings`
- `predictions`
- `data_coverage`
- `qualifier_events`
- `qualifier_lineups`
- `qualifier_match_stats`

## 8. Migration Sequence

推荐分三步做：

### Step 1

增加 `DataClient`，但页面暂时不大改：

- DataClient 优先读线上 `site/bundle.json`
- 失败时 fallback 本地 TS

### Step 2

把这些页面的数据来源切过去：

- Home
- Matches
- Groups
- GroupDetail
- Qualifiers
- MatchDetail

### Step 3

等页面稳定后，再逐步把以下逻辑改成读 `core/*`：

- 预测展示
- 数据覆盖提示
- 预选赛详情增强
- 后续 stats / standings 的标准化展示

## 9. Current Freshness Model

当前数据更新方式：

1. `football-data-platform` 更新数据
2. 发布到 GitHub Pages
3. `worldcup/2026` 页面刷新后直接拿到新 JSON

这意味着：

- 不需要重新 build `worldcup/2026`
- 不需要继续依赖 prebuild/pretest 的同步机制作为主链路

同步 TS 脚本现在只应该保留为 fallback 和迁移过渡手段。

## 10. Notes For The 2026 Thread

需要明确给 `worldcup/2026` 会话的实现要求：

1. 不要直接删掉本地 `src/data/*.ts`
2. 不要第一轮就把页面全部改成标准化 `core/*`
3. 第一轮先接 `site/bundle.json`
4. 先保证线上接口失败时站点仍然可用
5. 第一轮完成后，再决定哪些页面继续迁到 `core/*`
