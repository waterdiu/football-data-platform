# Predictor Runtime Data Requirements

Date: 2026-05-17

## 目标

为 `world-cup-predictor` 模型层提供统一、可追踪、可降级的赛前运行期数据输入。

模型层只负责建模、预测、EV/Kelly、报告和写回预测结果；以下数据的采集、标准化、发布、健康检查和覆盖率报告都归 `football-data-platform`。

优先支持：

- 2026 世界杯正赛预测。
- 英超测试比赛与回归验证。

统一要求：

- 所有时间字段使用 UTC ISO 8601。
- 缺失字段必须使用 `null` 或明确的 `missing/partial/unavailable` 状态，不能用 `0` 冒充缺失。
- 每条运行期数据必须包含 `source`、`captured_at` 或等价更新时间字段。
- 赛前快照不得使用开赛后或赛后数据回填。
- 模型层根据 `data_coverage` 自动降权，数据层必须把缺失原因暴露出来。

## P0 数据

### 1. 确认首发 / 赛前阵容

用途：

- T-1h 赛前报告。
- 球员影响力修正。
- 关键球员缺阵风险提示。
- 最终推荐降权。

建议输出：

```json
{
  "match_id": "string",
  "competition": "premier_league | world_cup",
  "source": "premierleague_official | fifa | bbc | sofascore | api_football | other",
  "captured_at": "UTC ISO",
  "kickoff_at": "UTC ISO",
  "status": "predicted | confirmed | unavailable",
  "home": {
    "team": "string",
    "formation": "string|null",
    "starting_xi": [
      {
        "player_id": "string|null",
        "name": "string",
        "position": "GK|DEF|MID|FWD|null",
        "shirt_number": "number|null",
        "is_key_player": "boolean|null",
        "impact_score": "number|null"
      }
    ],
    "bench": []
  },
  "away": {
    "team": "string",
    "formation": "string|null",
    "starting_xi": [],
    "bench": []
  }
}
```

刷新频率：

- T-24h：可抓预测阵容。
- T-6h：刷新一次。
- T-1h 到开赛：每 15 分钟检查确认首发。
- 一旦 `status=confirmed`，该版本不可覆盖，只能新增快照。

优先数据源：

- 英超：Premier League official match centre、BBC Sport。
- 世界杯：FIFA match centre、官方发布阵容。
- API-FOOTBALL 可作为结构化源。
- Sofascore 只作为增强源，不作为阻断源。

最低验收：

- 能按 `match_id` 输出双方首发状态。
- 确认首发与预测首发必须用 `status` 区分。
- 缺失时不得只发布空数组；必须发布 `source_status` 和 `status_reason`。例如比赛距离开球仍超过采集窗口时，输出 `source_status=unavailable`、`status_reason=outside_lineup_window`，并在 `data_coverage.lineups=unavailable` 中暴露给模型层。

### 2. AH / OU 实时赔率快照

用途：

- 盘口报告。
- 理论盘口 vs 实盘盘口。
- EV/Kelly。
- 模拟投注。
- 盘口移动信号。

AH 快照：

```json
{
  "match_id": "string",
  "competition": "string",
  "market": "asian_handicap",
  "source": "api_football | oddspapi | oddsharvester | oddsportal | hkjc | other",
  "bookmaker": "pinnacle | sbobet | bet365 | williamhill | 188bet | other",
  "bookmaker_type": "sharp | soft | exchange | unknown",
  "captured_at": "UTC ISO",
  "kickoff_at": "UTC ISO",
  "line": "number",
  "home_odds": "number|null",
  "away_odds": "number|null",
  "is_opening": "boolean",
  "is_closing": "boolean",
  "snapshot_type": "opening | t72 | t24 | t6 | t1 | t15m | latest | closing"
}
```

OU 快照：

```json
{
  "match_id": "string",
  "competition": "string",
  "market": "over_under",
  "source": "api_football | oddspapi | oddsharvester | oddsportal | hkjc | other",
  "bookmaker": "string",
  "bookmaker_type": "sharp | soft | exchange | unknown",
  "captured_at": "UTC ISO",
  "kickoff_at": "UTC ISO",
  "line": "number",
  "over_odds": "number|null",
  "under_odds": "number|null",
  "is_opening": "boolean",
  "is_closing": "boolean",
  "snapshot_type": "opening | t72 | t24 | t6 | t1 | t15m | latest | closing"
}
```

采样规则：

- `opening`：首次采到即保存，不覆盖。
- T-72h 到 T-24h：每 12 小时。
- T-24h 到 T-1h：每 4 小时。
- T-1h 到 kickoff：每 15 分钟。
- `closing`：开赛前最后一个可用快照。

最低目标：

- AH 至少 3 家，最好包含 Pinnacle 或其他 sharp book。
- OU 至少 3 家。
- 5 家以上标记为高质量盘口样本。
- 低于 3 家仍保存，但 `data_quality=low`。

硬约束：

- `captured_at` 必须早于 `kickoff_at` 才能作为赛前赔率。
- 不允许用赛后或开赛后的赔率冒充赛前赔率。
- `opening` 必须早于 `kickoff_at - 24h`，否则不能作为 opening 入模特征。
- TheOddsAPI 免费层不提供足球，除非付费且显式启用，否则不能作为足球赔率主源。

### 3. 伤停与球员影响力

用途：

- 球队实力报告。
- 球员影响力修正。
- 首发缺失风险。
- 临场推荐降权。

建议输出：

```json
{
  "match_id": "string|null",
  "team_id": "string|null",
  "team_name": "string",
  "source": "fpl | premierleague_official | transfermarkt | premierinjuries | fifa | news | other",
  "captured_at": "UTC ISO",
  "players": [
    {
      "player_id": "string|null",
      "name": "string",
      "position": "GK|DEF|MID|FWD|null",
      "status": "available | doubtful | injured | suspended | ruled_out | unknown",
      "chance_of_playing": "number|null",
      "reason": "string|null",
      "expected_return": "string|null",
      "impact_score": "number|null",
      "minutes_share": "number|null",
      "xg_contribution": "number|null",
      "xa_contribution": "number|null",
      "market_value_eur": "number|null",
      "is_key_player": "boolean|null"
    }
  ]
}
```

最低可用标准：

- 至少区分 `injured`、`suspended`、`doubtful`、`available`。
- `impact_score` 可以先为空，但必须保留字段。
- 新闻源只能作为 evidence，不能直接覆盖官方状态，除非有明确来源时间和链接。

平台实现要求：

- `injuries.json.absence_evidence_summary` 可由公开新闻页赛前上下文生成。
- 该 evidence 只能用于报告提示、置信度降权和人工复核，不能直接等同于官方 `injured/suspended/available` 状态。
- 没有新闻证据时必须标记 `no_news_absence_evidence`，不能解释为“没有伤停”。

优先数据源：

- 英超：FPL、Premier League official、Premier Injuries、Transfermarkt。
- 世界杯：FIFA 官方、国家队新闻、Transfermarkt、可信体育新闻站。
- Sofascore 作为实验增强源。

### 4. 天气

用途：

- 大小球解释。
- 比赛节奏风险。
- 传控质量风险。
- 极端天气提示。

建议输出：

```json
{
  "match_id": "string",
  "venue_id": "string|null",
  "venue_name": "string|null",
  "captured_at": "UTC ISO",
  "forecast_for": "UTC ISO",
  "source": "openweather | open_meteo | meteostat | weatherapi | other",
  "temperature_c": "number|null",
  "humidity_pct": "number|null",
  "wind_speed_mps": "number|null",
  "precipitation_mm": "number|null",
  "condition": "clear | cloudy | rain | storm | snow | extreme_heat | unknown",
  "risk_tags": ["heavy_rain", "strong_wind", "extreme_heat", "low_visibility"]
}
```

刷新频率：

- T-72h：首次天气预测。
- T-24h：刷新。
- T-6h：刷新。
- T-1h：最终赛前天气。

最低可用标准：

- 至少需要 `temperature_c`、`wind_speed_mps`、`condition`。
- 所有场馆必须在 `configs/venues/world_cup_2026.json` 有经纬度。
- 目前 Open-Meteo fallback 已存在；真实天气行只有进入天气预报窗口后才会出现。
- 当比赛超出天气预报窗口时，平台必须发布占位天气行：`source_status=unavailable`、`status_reason=outside_forecast_window`，并在 `runtime-summary.json.data_coverage.weather` 标记为 `unavailable`。这表示“暂时不可采集”，不是采集失败，也不能当成缺省晴天或 0 风速。

## P1 数据

### 5. 高级技术统计：控球率、传球成功率、PPDA

用途：

- 球队广义实力。
- 近期状态。
- 战术风格。
- 强弱队压制力判断。

建议输出：

```json
{
  "team_id": "string|null",
  "team_name": "string",
  "competition": "premier_league | world_cup | international",
  "scope": "last_5 | last_10 | season | home | away",
  "matches": "number",
  "possession_pct": "number|null",
  "pass_accuracy_pct": "number|null",
  "passes_completed_per_match": "number|null",
  "progressive_passes_per_match": "number|null",
  "shots_per_match": "number|null",
  "shots_on_target_per_match": "number|null",
  "ppda": "number|null",
  "xg_for_per_match": "number|null",
  "xga_per_match": "number|null",
  "source": "fbref | statsbomb | sofascore | understat | other",
  "last_updated": "UTC ISO"
}
```

优先级：

- 英超：FBref、StatsBomb open data、existing Understat。
- 世界杯：如果没有实时高级统计，先提供历史国家队近 10/20 场基础统计和 xG；PPDA 可为空但必须标记缺失。

最低可用标准：

- `matches >= 5` 才能展示近期趋势。
- `matches >= 10` 才能进入模型特征或强结论。
- 缺失字段必须是 `null`，不能填 `0`。

### 6. 裁判画像样本

用途：

- 非赔率因素解释。
- 犯规、红黄牌、点球、比赛节奏、大小球风险说明。

建议输出：

```json
{
  "referee_id": "string|null",
  "referee_name": "string",
  "competition_scope": "premier_league | international | all",
  "sample_size": "number",
  "matches": "number",
  "yellow_cards_per_match": "number|null",
  "red_cards_per_match": "number|null",
  "fouls_per_match": "number|null",
  "penalties_per_match": "number|null",
  "home_win_rate": "number|null",
  "away_win_rate": "number|null",
  "draw_rate": "number|null",
  "avg_goals": "number|null",
  "style_tags": ["strict", "card-heavy", "penalty-prone", "home-friendly"],
  "last_updated": "UTC ISO",
  "source": "football-data.co.uk | worldfootball | transfermarkt | other"
}
```

最低可用标准：

- `sample_size >= 20` 才能参与报告结论。
- `sample_size < 20` 只能展示“样本不足”，不能影响模型。

优先数据源：

- 英超：football-data.co.uk 的 `Referee` 字段 + 红黄牌字段。
- 世界杯/国际赛：FIFA 裁判名单、worldfootball、公开比赛记录。

## 统一发布建议

平台应该在 predictor runtime bundle 中暴露按比赛聚合的 runtime 输入，结构可以是：

```json
{
  "match_id": "string",
  "competition": "string",
  "kickoff_at": "UTC ISO",
  "lineups": [],
  "injuries": [],
  "weather": {},
  "referee_profile": {},
  "team_advanced_stats": {
    "home": {},
    "away": {}
  },
  "odds_snapshots": {
    "ah": [],
    "ou": [],
    "one_x_two": []
  },
  "data_coverage": {
    "lineups": "available | partial | missing",
    "injuries": "available | partial | missing",
    "weather": "available | partial | missing",
    "referee_profile": "available | partial | missing",
    "advanced_stats": "available | partial | missing",
    "ah_odds": "available | partial | missing",
    "ou_odds": "available | partial | missing"
  }
}
```

现有 World Cup predictor API 已经有这些入口：

- `api/worldcup/2026/predictor/lineups.json`
- `api/worldcup/2026/predictor/injuries.json`
- `api/worldcup/2026/predictor/weather.json`
- `api/worldcup/2026/predictor/odds-snapshots.json`
- `api/worldcup/2026/predictor/data-coverage.json`
- `api/worldcup/2026/predictor/runtime-summary.json`
- `api/worldcup/2026/predictor/bundle.json`

后续需要补充：

- `referee-profile` 或并入 `official-ratings.json`
- `team-advanced-stats`

`runtime-summary.json` 是模型层优先读取的按比赛聚合入口。即使底层 `lineups`、`injuries`、`weather`、`odds` 暂时为空，该文件也必须为 104 场输出稳定行，并在 `data_coverage` 里显式标记 `missing`、`partial` 或 `available`。裁判画像和高级技术统计在未完成采集前必须输出 `missing` 和 `null` 字段，不能填 `0`。

当前状态契约已扩展为允许 `unavailable`。含义是“平台知道这项数据当前不可采集或未授权”，不同于 `missing`。例如：赛前首发还没进入 T-24/T-1h 窗口时，`lineups` 使用 `unavailable/outside_lineup_window`；本地或部署环境没有 `API_FOOTBALL_KEY` 时，`injuries` 使用 `missing_auth/missing_auth`；provider 免费层不开放 2026 season 时，使用 `plan_restricted`。模型层必须把这些状态作为降权依据，不能当成无伤停、无首发或数值 0。

## 优先级

P0，直接影响报告和赛前推荐：

1. 确认首发。
2. AH / OU 实时快照。
3. 伤停与球员影响力。
4. 天气。

P1，提升球队实力报告质量：

1. 控球率、传球成功率、PPDA。
2. 裁判画像。

P2，后续增强：

1. 新闻源实体画像。
2. 更细球员贡献拆分。
3. 多源一致性评分。

## 测试验收样例

以 Arsenal vs Burnley 这类英超测试比赛为例，数据层需要能输出：

- 比赛 UTC `kickoff_at`。
- 双方可用 / 伤停 / 停赛球员列表。
- 至少一个天气快照。
- 至少 3 家 AH 或 OU 快照；如果没有，明确 `missing` 和原因。
- 双方近 5 / 10 场高级技术统计，缺失字段必须是 `null`。
- 裁判字段如果没有裁判名，标记 `missing_referee_assignment`。
- 如果有裁判名但样本不足，标记 `low_referee_sample`。

模型层按这些 `data_coverage` 标记自动降权或显示“数据不足”，不能把缺失数据当成 0。
