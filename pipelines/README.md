# Pipelines

这个目录用于放流程编排逻辑。

建议阶段：

- `fetch/`
- `normalize/`
- `merge/`
- `validate/`
- `publish/`

pipeline 负责串联流程，不负责实现 provider 细节。
