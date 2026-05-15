# Transforms

这个目录用于放标准化与合并逻辑。

建议拆分：

- `canonical_ids`
- `normalize_*`
- `merge_*`
- `validate_*`

这里的代码负责把 provider 数据转成平台内部 schema。
