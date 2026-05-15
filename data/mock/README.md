# Mock Data

这个目录用于存放本地开发和 CI 可用的样例输入。

用途：

- 没有 API key 时调试 pipeline
- 在 CI 中验证 schema 和 publish 流程
- 调试 authoritative match mapping，不依赖实时网络

建议命名：

- `football_data_world_cup_matches.sample.json`
- `api_football_qualifiers.sample.json`
- `predictions.sample.json`
