# Sources

这个目录用于放 provider adapter。

建议按 provider 建子目录，例如：

- `football_data_org/`
- `api_football/`
- `openfootball/`
- `odds/`
- `weather/`

当前已有的运行期 adapter：

- `openweather.py`：OpenWeather 当前天气，有 key 时使用。
- `open_meteo.py`：Open-Meteo 无 key 短期天气 fallback，覆盖 16 天预报窗口。
- `api_football.py`：API-FOOTBALL 阵容、伤停、fixture id 发现。
- `the_odds_api.py`：The Odds API 赔率快照。
- `prematch_news.py`：公开新闻页赛前上下文。

每个 adapter 负责：

- 拉取原始数据
- 保留 provider 原始字段
- 不直接做最终业务聚合
