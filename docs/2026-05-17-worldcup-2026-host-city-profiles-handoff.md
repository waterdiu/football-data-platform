# worldcup/2026 Host City Profiles Handoff

日期：2026-05-17

## 目标

支持 `worldcup/2026` 城市详情页三栏信息区：

- 城市海报卡片
- 城市信息卡片
- 球场信息卡片

页面可以去掉“城市详情”、城市名大标题和说明文字，直接读取平台城市资料填充中间城市信息卡片。

## API 入口

推荐读取 core bundle：

- `https://waterdiu.github.io/football-data-platform/api/worldcup/2026/core/bundle.json`
- 路径：`datasets.host_city_profiles`

也可读取单文件：

- `https://waterdiu.github.io/football-data-platform/api/worldcup/2026/core/host-city-profiles.json`

manifest：

- `https://waterdiu.github.io/football-data-platform/api/worldcup/2026/manifest.json`
- 路径：`runtime_contract.core.host_city_profiles`

## 当前覆盖

覆盖 16 个主办城市：

- Atlanta
- Boston
- Dallas
- Guadalajara
- Houston
- Kansas City
- Los Angeles
- Mexico City
- Miami
- Monterrey
- New York New Jersey
- Philadelphia
- San Francisco Bay Area
- Seattle
- Toronto
- Vancouver

## 关键字段

- `city_id`：长期稳定 slug，例如 `new-york-new-jersey`
- `site_city_key`：必须等于 `worldcup/2026` 当前路由 key，例如 `New York New Jersey`
- `city_name_zh`
- `city_name_en`
- `country_zh`
- `country_en`
- `region_zh`
- `region_en`
- `timezone`
- `population`
- `city_tags`
- `climate_summary_zh`
- `climate_summary_en`
- `football_culture_zh`
- `football_culture_en`
- `transport_summary_zh`
- `transport_summary_en`
- `local_feature_zh`
- `local_feature_en`
- `primary_venue_id`
- `source_status`
- `source_urls`
- `updated_at`

## 前端匹配建议

当前 `worldcup/2026` 城市详情页使用英文城市名原文作为 key，并在 URL 里 `encodeURIComponent`。因此第一阶段建议按 `site_city_key` 无缝接入：

```ts
const cityProfile = hostCityProfiles.find((row) => row.site_city_key === city)
```

后续如果站点路由改成 slug，再切到：

```ts
const cityProfile = hostCityProfiles.find((row) => row.city_id === cityId)
```

## 展示规则

- `population` 当前为 `null`，前端应隐藏，不要显示 0 或 “未知人口”。
- `city_tags` 建议展示 3-5 个短标签。
- 摘要字段都控制在短句级别，适合卡片展示。
- 若任一可选摘要字段为 `null`，前端隐藏该行。

## Report Back

完成后请回报协调入口：

```text
Project: worldcup/2026
Task: 接入城市详情页 host_city_profiles 数据源
Status:
Completed:
Files changed:
Validation:
Data/API contract impact:
Needs data platform:
Blockers:
Next recommended step:
```
