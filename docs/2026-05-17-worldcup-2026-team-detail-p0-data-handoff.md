# worldcup/2026 Team Detail P0 Data Handoff

日期：2026-05-17

## 目标

对齐 `worldcup/2026` 球队详情页近期 P0 数据范围：

- 教练模块只展示主教练。
- 历届世界杯战绩作为球队详情页展示内容，优先年度级汇总。
- 最近比赛展示最近 10 场基础比分。
- 球员 P0 只展示姓名、位置、状态、`team_id`。
- 正赛比赛详情页先按赛后一次性更新，不做直播级实时。
- 展示站不展示赔率，数据层不为站点处理 odds。

## API 入口

推荐读取 core bundle：

- `https://waterdiu.github.io/football-data-platform/api/worldcup/2026/core/bundle.json`

也可读取单文件：

- `https://waterdiu.github.io/football-data-platform/api/worldcup/2026/core/team-staff.json`
- `https://waterdiu.github.io/football-data-platform/api/worldcup/2026/core/team-world-cup-history.json`
- `https://waterdiu.github.io/football-data-platform/api/worldcup/2026/core/team-recent-matches.json`
- `https://waterdiu.github.io/football-data-platform/api/worldcup/2026/core/rosters.json`
- `https://waterdiu.github.io/football-data-platform/api/worldcup/2026/core/players.json`
- `https://waterdiu.github.io/football-data-platform/api/worldcup/2026/core/data-coverage.json`

manifest：

- `https://waterdiu.github.io/football-data-platform/api/worldcup/2026/manifest.json`

## 当前覆盖

| 数据集 | 当前覆盖 | 说明 |
| --- | ---: | --- |
| `team_staff` | 8 队 | 已有官方 26 人名单球队的主教练，`role=head_coach` |
| `rosters` | 8 队 | 已有 FIFA 官方名单文章的 26 人名单 |
| `players` | 208 人 | P0 可用字段：姓名、位置、状态、`team_id` |
| `team_recent_matches` | 48 队 | 每队最近 10 场基础比分 |
| `team_world_cup_history` | 48 队 | 38 队有 2002-2022 源内世界杯正赛汇总，10 队仍为 `pending_source` |

## 字段说明

### team_staff

`worldcup/2026` 球队详情页只需要：

- `team_id`
- `team_name`
- `name`
- `role`
- `role_zh`
- `status`
- `source_status`
- `source_url`
- `updated_at`

筛选规则：

```ts
const headCoach = teamStaff.find((row) => row.team_id === teamId && row.role === 'head_coach')
```

若没有该队主教练行，显示“暂未公布 / 数据待补充”，不要回退到旧硬编码生产事实。

### team_recent_matches

每队一行，`matches` 保留最近 10 场。P0 字段：

- `match_id`
- `date`
- `tournament`
- `home_team`
- `away_team`
- `home_score`
- `away_score`
- `opponent_name`
- `home_away`
- `score_for`
- `score_against`
- `result`
- `city`
- `country`
- `venue`
- `neutral`

当前来源是已迁移模型历史赛果：`data/predictor-assets/files/processed/normalized_matches.csv`。

### team_world_cup_history

每队一行，包含：

- `summary.appearances`
- `summary.matches_played`
- `summary.won`
- `summary.drawn`
- `summary.lost`
- `summary.goals_for`
- `summary.goals_against`
- `editions[]`

重要限制：

- 当前只从已迁移历史赛果里计算源内存在的 `FIFA World Cup` 正赛，覆盖年份为 2002-2022。
- `source_status=available_partial` 表示可以展示为“平台已覆盖年份内的世界杯历史汇总”，不能文案写成“完整历届世界杯历史”。
- `source_status=pending_source` 的球队没有源内世界杯正赛记录，前端应显示“历史数据待补充”。
- `best_finish`、`stage_reached`、`finish` 暂时为 `null`，前端不要伪造。

当前仍为 `pending_source` 的球队：

- Austria
- Cabo Verde
- Congo DR
- Curacao
- Haiti
- Iraq
- Jordan
- Norway
- Scotland
- Uzbekistan

## data_coverage

`data-coverage.json` 已增加：

- `rosters`
- `team_staff`

含义：

- `available`：本场两队均有该类数据。
- `partial`：本场只有一队有该类数据。
- `missing`：本场两队都没有该类数据。

## 非目标

本阶段不处理：

- 完整教练组。
- 球员俱乐部、球衣号、生日、中文名。
- 最近比赛事件、阵容、技术统计。
- 正赛直播级事件轮询。
- 展示站赔率。

## Report Back

完成后请回报协调入口：

```text
Project: worldcup/2026
Task: 接入球队详情页 P0 数据源
Status:
Completed:
Files changed:
Validation:
Data/API contract impact:
Needs data platform:
Blockers:
Next recommended step:
```
