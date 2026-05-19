# 2026 世界杯赔率源 Readiness Runbook

日期：2026-05-19  
项目：`football-data-platform`  
状态：执行规则  
主设计基线：`DESIGN.md`

## 1. 目标

这份 runbook 只处理 2026 世界杯赔率源复查，不解决模型赔率分析逻辑。

目标：

- 明确哪些赔率源可以继续验证，哪些已经暂停。
- 明确什么时候跑、跑什么命令、看什么报告。
- 避免把免费/实验源误当生产源。
- 为 `world-cup-predictor` 提供 1X2 / AH / OU / closing / CLV 的数据可行性判断。

## 2. 当前结论

| 源 | 当前状态 | 结论 |
|---|---|---|
| Odds-API.io free | `verified_experimental` | 能拿足球 ML、AH、OU；免费层 2 家书商；世界杯 event 未可见 |
| API-FOOTBALL odds | `pending_plan` | Free 对 WC 2026 plan restricted；Pro 后重验 |
| BSD/Bzzoiro | `verified_experimental_for_1x2_ou` | 能拿通用 1X2/OU 和 bookmaker；World Cup 映射未命中，AH 未公开文档化 |
| TheOddsAPI | `blocked_by_plan` | 免费只 NBA/MLB；足球 Business $99/月 |
| HKJC | `experimental_blocked_live` | GraphQL 基础可达，但 football `matches/matchResult` 返回 `WHITELIST_ERROR` |
| 雷速 | `live_blocked_by_waf` | 首页可发现比赛；详情/赔率/数据页被 WAF / UA ACL 阻断 |

当前生产判断：

- 没有免费源满足生产级 World Cup 赔率要求。
- Odds-API.io 可以做 AH/OU schema 实验，不足以做 market consensus / CLV 强结论。
- API-FOOTBALL Pro 开通后必须先验证 odds 覆盖，再决定是否进入 model-only。

## 3. 环境变量

| 源 | 环境变量 | 当前用途 |
|---|---|---|
| Odds-API.io | `ODDS_API_IO_KEY` | event scan 和 AH/OU 小样本实验 |
| BSD/Bzzoiro | `BSD_API_TOKEN` | bookmaker、通用 odds、World Cup 映射 probe |
| API-FOOTBALL | `API_FOOTBALL_KEY` | Pro 后验证 WC 2026 odds |
| TheOddsAPI | `THE_ODDS_API_KEY` + `THE_ODDS_API_SOCCER_ENABLED=1` | 仅付费 Business 后启用 |

密钥只允许放 `.env.local`、环境变量或 GitHub Secrets，不得写入命令、报告或仓库。

## 4. 触发时间

| 时间 | 动作 |
|---|---|
| API-FOOTBALL Pro 开通当天 | 重跑 World Cup runtime probe，确认 odds 是否 plan restricted |
| 首场前 7 天 | 检查 API-FOOTBALL odds 是否出现未来 7 天比赛 |
| 首场前 5 天 | 必须重跑 Odds-API.io event scan |
| 首场前 72 小时 | 若 World Cup event 可见，开始 T-72/T-24/T-6/T-1 实验采样 |
| 首场前 15 分钟 | 若已有稳定源，保存 latest/closing 候选快照 |
| 比赛开始后 | 不允许用赛后或开赛后赔率回填赛前 opening/T-window |

## 5. Odds-API.io 执行

### 5.1 Event scan

目的：确认免费层是否能看到 2026 World Cup 或成年国家队赛事。

命令：

```bash
python3 scripts/sample_odds_api_io_snapshots.py \
  --scan-events \
  --pages 5 \
  --page-size 30 \
  --bookmakers Sbobet,Bet365
```

输出：

- `reports/odds_api_io_event_scan_report.json`

通过标准：

- `has_world_cup_candidate=true`，或
- `has_senior_international_candidate=true` 且候选能映射到平台 `match_id`

失败处理：

- 如果没有 World Cup / senior international 候选，保持 `world_cup_2026=unknown_or_not_visible_on_free_tier`。
- 不继续抓 event odds，避免浪费请求。

### 5.2 小样本采样

目的：确认 AH/OU 字段稳定性和 bookmaker 行稳定性。

命令：

```bash
python3 scripts/sample_odds_api_io_snapshots.py \
  --limit 5 \
  --bookmakers Sbobet,Bet365
```

输出：

- `reports/odds_api_io_sampling_report.json`
- `data/raw/experimental/odds-api-io/*.raw.json`
- `data/raw/experimental/odds-api-io/*.mapped.json`

通过标准：

- `normalized_row_count > 0`
- `market_row_counts.asian_handicap > 0`
- `market_row_counts.over_under > 0`
- `bookmaker_row_counts` 至少包含 2 家稳定书商

使用限制：

- 只允许写 `reports/` 和 `data/raw/experimental/odds-api-io`。
- 不得写 `data/normalized`、`data/model` 或 public API。
- 不得用于 market consensus、sharp/soft 分层或 CLV 强结论。

## 6. API-FOOTBALL Pro 执行

目的：确认 Pro 套餐是否覆盖 2026 World Cup odds，并判断是否能进入 model-only。

命令：

```bash
python3 scripts/probe_api_football_worldcup_runtime.py
```

输出：

- `reports/api_football_worldcup_runtime_probe.json`

赔率通过标准：

- WC 2026 fixture id 可映射。
- `/odds` 不再返回 `plan_restricted`。
- 至少能拿到 1X2。
- 若存在 AH/OU，必须有 bookmaker、market、line、odds、captured_at 或 provider update timestamp。

使用策略：

- 如果只提供 1X2，不作为 AH/OU 主源。
- 如果 AH/OU 可用，先进入 `model-only` 候选，不直接 public。
- 如果 bookmaker 少于 3 家，只能低置信使用。
- 如果没有 opening/T-window/closing 序列，不能做 CLV。

## 7. BSD/Bzzoiro 执行

目的：确认是否能找到真实 World Cup event mapping，以及是否有可用 1X2/OU。

命令：

```bash
python3 scripts/probe_free_odds_sources.py --live
```

输出：

- `reports/free_odds_source_probe.json`

当前已知问题：

- `league_id=16&season_id=82` 的 World Cup events 返回 0。
- AH 未公开文档化。
- 通用 odds 可见 1X2/OU，但不能映射到 World Cup。

通过标准：

- `world_cup_2026=observed`
- `one_x_two=observed`
- `over_under=observed`
- event id 能映射到平台 `match_id`

失败处理：

- 若 World Cup 仍不可见，BSD 只保留 1X2/OU 实验补源。
- 若 AH 仍未文档化，不把 BSD 用于 AH。

## 8. TheOddsAPI Business

当前不启用。

只有满足以下条件才考虑付费：

- 模型明确要正式做 AH/OU/CLV。
- 免费/低价源无法覆盖 World Cup。
- Business 确认覆盖 FIFA World Cup、AH/OU、bookmaker 明细、至少一个 sharp bookmaker、closing 或 near-closing 快照。

已知价格：

- Business：$99/月。
- 免费层：NBA/MLB，不能满足足球。

## 9. 暂停源

### HKJC

暂停原因：

- `timeOffset { fb }` 这类基础 GraphQL 查询可用。
- football `matches` / `matchResult` 查询返回 `WHITELIST_ERROR`。
- 加 `origin`、`referer`、`user-agent` 后仍失败。
- 非官方 wrapper 不等于授权数据 API。

后续只有在解决白名单、条款和字段采样后，才允许重新评估。

### 雷速

暂停原因：

- 首页可匿名发现 match id。
- `data.leisu.com`、`odds.leisu.com`、单场详情、数据分析页、情报页被 WAF / UA ACL 阻断。
- 旧 GitHub 项目多为页面/逆向爬虫，维护和合规风险高。

只允许保留 `data/raw/experimental/leisu` 级别实验，不进生产。

## 10. 数据质量门槛

| 用途 | 最低门槛 |
|---|---|
| 页面展示赔率 | 当前不做 |
| 模型弱信号 | 1X2/AH/OU 至少 1-2 家，明确 `data_quality=low` |
| 模型正常赔率输入 | 每个 market 至少 3 家 bookmaker，含时间戳 |
| 市场共识 | 至少 5 家 bookmaker，最好区分 sharp/soft |
| CLV | 有 opening、T-24、T-6、T-1、closing 或 near-closing |
| 强 Kelly | 有稳定多书商、非赛后赔率、完整时间序列 |

## 11. 禁止事项

- 不把 experimental odds 写入 `data/normalized`、`data/model` 或 public API。
- 不用赛后 odds 冒充赛前 odds。
- 不把 2 家 bookmaker 当 market consensus。
- 不把 youth friendly / club event 的覆盖结论外推到 World Cup。
- 不把 HKJC/雷速逆向源当生产源。
- 不把 API-FOOTBALL Free 的 plan restricted 当临时网络错误反复重试。

## 12. 当前下一步

1. 继续保留 `runtime_odds` 为 daily action 的唯一 `do_now`。
2. 首场前 5 天重跑 Odds-API.io event scan。
3. API-FOOTBALL Pro 开通后重跑 World Cup runtime probe。
4. 若两条低成本路线都失败，再评估是否需要 TheOddsAPI Business。
