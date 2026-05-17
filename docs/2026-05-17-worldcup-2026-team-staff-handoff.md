# worldcup/2026 Team Staff Handoff

日期：2026-05-17

## 目标

`worldcup/2026` 球队详情页可以切换教练数据来源，从本地/硬编码来源改为 `football-data-platform` runtime API。

## 数据源

主入口：

- `https://waterdiu.github.io/football-data-platform/api/worldcup/2026/core/team-staff.json`

也可从 core bundle 读取：

- `https://waterdiu.github.io/football-data-platform/api/worldcup/2026/core/bundle.json`
- 路径：`datasets.team_staff`

manifest 契约：

- `https://waterdiu.github.io/football-data-platform/api/worldcup/2026/manifest.json`
- 路径：`runtime_contract.core.team_staff`

## 当前覆盖

已补 32 支球队主教练，其中包括 9 支已有官方 26 人名单球队。当前覆盖：

- Algeria：Vladimir Petkovic
- Argentina：Lionel Scaloni
- Belgium：Rudi Garcia
- Bosnia and Herzegovina：Sergej Barbarez
- Brazil：Carlo Ancelotti
- Canada：Jesse Marsch
- Colombia：Nestor Lorenzo
- Cote d'Ivoire：Emerse Fae
- Croatia：Zlatko Dalic
- Czechia：Miroslav Koubek
- Ecuador：Sebastian Beccacece
- England：Thomas Tuchel
- France：Didier Deschamps
- Germany：Julian Nagelsmann
- Haiti：Sebastien Migne
- IR Iran：Amir Ghalenoei
- Japan：Hajime Moriyasu
- Korea Republic：Hong Myungbo
- Mexico：Javier Aguirre
- Morocco：Mohamed Ouahbi
- Netherlands：Ronald Koeman
- New Zealand：Darren Bazeley
- Paraguay：Gustavo Alfaro
- Portugal：Roberto Martinez
- Saudi Arabia：Herve Renard
- South Africa：Hugo Broos
- Spain：Luis de la Fuente
- Sweden：Graham Potter
- Tunisia：Sabri Lamouchi
- United States：Mauricio Pochettino
- Uruguay：Marcelo Bielsa
- Uzbekistan：Fabio Cannavaro

## 字段

每行包含：

- `competition_id`
- `season_id`
- `team_id`
- `team_name`
- `staff_id`
- `name`
- `display_name`
- `name_zh`
- `role`
- `role_zh`
- `status`
- `nationality`
- `date_of_birth`
- `age`
- `appointed_at`
- `contract_until`
- `source_status`
- `sources`
- `source_refs`
- `source_url`
- `updated_at`

说明：

- 当前 `role=head_coach`，`role_zh=主教练`。
- `source_status=official_fifa`。
- `date_of_birth` / `age` 在没有审计生日来源前为 `null`，前端应允许为空。

## 建议前端处理

按 `team_id` 过滤：

```ts
const coaches = teamStaff.filter((row) => row.team_id === teamId && row.role === 'head_coach')
```

展示优先级：

1. `name_zh` 如果存在
2. `display_name`
3. `name`

如果没有该队教练行，显示“暂未公布 / 数据待补充”，不要 fallback 到硬编码旧数据作为生产事实。

## Report Back

完成后请回报协调入口：

```text
Project: worldcup/2026
Task: 切换球队详情页教练数据来源
Status:
Completed:
Files changed:
Validation:
Data/API contract impact:
Needs data platform:
Blockers:
Next recommended step:
```
