# World Cup 2026 Runtime API

日期：2026-05-15  
状态：可交付给 `worldcup/2026` 接入

## 1. Purpose

这套接口用于让 `worldcup/2026` 在页面运行时直接读取 `football-data-platform` 的静态 JSON，
而不是继续依赖“构建前同步成本地 TS 文件”。

第一阶段目标不是改页面结构，而是先提供一套稳定、清晰、可版本化的静态接口。

## 2. Entry Points

主入口：

- `data/public/api/worldcup/2026/manifest.json`

推荐页面层入口：

- `data/public/api/worldcup/2026/site/bundle.json`

标准化数据入口：

- `data/public/api/worldcup/2026/core/bundle.json`

## 3. Contract

### 3.1 Site API

`site/*` 主要服务 `worldcup/2026` 现有页面，尽量保持旧数据形状，减少接入改动。

包含：

- `site/groups.json`
- `site/group-fixtures.json`
- `site/group-stage-matches.json`
- `site/bracket.json`
- `site/full-schedule.json`
- `site/finals-results.json`
- `site/finals-coverage.json`
- `site/qualifier-matches.json`
- `site/qualifier-missing-data.json`
- `site/qualifier-source-reports.json`
- `site/bundle.json`

推荐优先用 `site/bundle.json`，减少前端请求数量。

### 3.2 Core API

`core/*` 提供平台标准化数据集，适合未来替换页面内部旧结构。

包含：

- `core/canonical_teams.json`
- `core/teams.json`
- `core/fixtures.json`
- `core/results.json`
- `core/standings.json`
- `core/predictions.json`
- `core/data-coverage.json`
- `core/qualifier-events.json`
- `core/qualifier-lineups.json`
- `core/qualifier-match-stats.json`
- `core/bundle.json`

## 4. Recommended Migration Path

推荐顺序：

1. 先让 `worldcup/2026` 增加一个 `DataClient`
2. `DataClient` 优先读取 `site/bundle.json`
3. 读取失败时 fallback 到当前 `src/data/*.ts`
4. 页面稳定后，再逐步把页面逻辑切向 `core/*`

这样可以：

- 保证实时性
- 保留构建期 fallback
- 不需要一次性重写全部页面数据结构

## 5. Freshness

当前这套静态 API 会在以下流程中更新：

- `python3 scripts/publish_all_world_cup_data.py`
- `python3 scripts/publish_worldcup_2026_api.py`

因此只要 `football-data-platform` 更新数据并重新发布，`worldcup/2026` 页面刷新后就能拿到最新 JSON，
不需要重新构建 `worldcup/2026`。

## 6. Notes

- `site/*` 是迁移接口，不是长期终态
- `core/*` 才是平台长期标准契约
- 在 `worldcup/2026` 完成运行时接入前，当前的同步脚本机制仍可保留作为 fallback
