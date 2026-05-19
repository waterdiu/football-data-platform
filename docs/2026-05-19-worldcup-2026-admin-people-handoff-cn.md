# worldcup/2026 管理端人员页面数据交接

日期：2026-05-19

## 目标

`worldcup/2026` 管理界面可以新增“人员”入口，下面分为三个子页面：

- 球员
- 教练
- 裁判/比赛官员

页面形态先做列表 + 搜索框 + 详情页跳转。数据由 `football-data-platform` 的 World Cup 2026 runtime API 提供，前端不自行维护人员事实数据。

## 当前数据状态

| 类型 | 当前状态 | 可否先做页面 |
|---|---:|---|
| 教练 | 48 支球队主教练已发布 | 可以 |
| 裁判/比赛官员 | FIFA 官方 170 名比赛官员已发布；另有英超历史裁判样本 | 可以 |
| 球员 | 当前 9 队 234 人；剩余 39 队等待官方最终名单 | 可以做结构，完整上线等最终名单 |

## 推荐入口

优先从 manifest 读取路径，不要写死 URL：

- `api/worldcup/2026/manifest.json`
- `runtime_contract.core.people_index`
- `runtime_contract.core.coach_profiles`
- `runtime_contract.core.player_profiles`
- `runtime_contract.core.referee_profiles`
- `runtime_contract.core.officials`

当前核心文件：

- `api/worldcup/2026/core/people-index.json`
- `api/worldcup/2026/core/coach-profiles.json`
- `api/worldcup/2026/core/player-profiles.json`
- `api/worldcup/2026/core/referee-profiles.json`
- `api/worldcup/2026/core/officials.json`

## 列表页建议

### 教练

读取：

- `coach-profiles.json`

列表字段：

- `person_id`
- `display_name`
- `team_id`
- `team_name`
- `role_zh`
- `direct.nationality`
- `direct.age`
- `source_status`
- `updated_at`

搜索字段：

- `display_name`
- `name`
- `name_zh`
- `team_name`
- `team_id`

### 裁判/比赛官员

读取：

- `referee-profiles.json`
- 或列表只读 `officials.json`，详情再读 `referee-profiles.json`

列表字段：

- `person_id`
- `display_name`
- `role`
- `role_zh`
- `direct.association_code`
- `source_status`
- `direct.assignment_status`
- `updated_at`

筛选建议：

- `role=referee`
- `role=assistant_referee`
- `role=video_match_official`
- `source_status=official_fifa_match_official_list`
- `source_status=historical_sample_only`

注意：

- FIFA 170 人是比赛官员名单，不是每场比赛指派。
- 单场指派未来会进入 `match-official-assignments.json`。
- 英超历史样本只用于风格/尺度参考，不代表世界杯名单。

### 球员

读取：

- `player-profiles.json`

当前只覆盖 9 队官方名单，建议先完成页面结构，等 FIFA/足协最终名单补齐后再作为完整管理入口。

列表字段：

- `person_id`
- `display_name`
- `team_id`
- `team_name`
- `direct.position`
- `direct.club`
- `direct.shirt_number`
- `direct.status`
- `source_status`

注意：

- `shirt_number` 当前仍可能为 `null + pending_source`，不能展示为 0。
- `impact_proxy_score` 是展示型代理，不是真实缺阵影响百分比。

## 详情页建议

详情页按 `person_id` 从对应 profile 数组中查找：

- 教练：`coach-profiles.json`
- 球员：`player-profiles.json`
- 裁判/比赛官员：`referee-profiles.json`

通用展示模块：

- 基础身份：`direct`
- KPI：`kpis[]`
- 分区内容：`sections[]`
- 来源状态：`source_status`、`source_urls`、`updated_at`

前端只做渲染、搜索、筛选和空态；不要在前端计算胜率、能力评分、缺阵影响或风格标签。

## 当前数量

截至本次发布：

- `people-index.json`: 501
- `coach-profiles.json`: 48
- `player-profiles.json`: 234
- `officials.json`: 219
- `referee-profiles.json`: 219

`officials/referee-profiles` 的 219 条包括：

- FIFA 官方 2026 世界杯比赛官员：170 条
- 英超历史裁判样本唯一人物：49 条

英超历史原始样本中 `L Mason/l Mason` 是大小写重复身份，public 合并后保留唯一人物。
