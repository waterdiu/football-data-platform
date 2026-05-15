# Sources

这个目录用于放 provider adapter。

建议按 provider 建子目录，例如：

- `football_data_org/`
- `api_football/`
- `openfootball/`
- `odds/`
- `weather/`

每个 adapter 负责：

- 拉取原始数据
- 保留 provider 原始字段
- 不直接做最终业务聚合
