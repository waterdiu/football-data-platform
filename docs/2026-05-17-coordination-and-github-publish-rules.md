# 数据层协调与 GitHub 发布规则

日期：2026-05-17  
状态：执行规则

## 1. 对话职责

本对话作为足球工作区的数据协调入口，统筹以下三个项目的数据对接：

- `/Users/chamcham/Documents/AI/CODEX/soccer/football-data-platform`
- `/Users/chamcham/Documents/AI/CODEX/soccer/world-cup-predictor`
- `/Users/chamcham/Documents/AI/CODEX/soccer/worldcup/2026`

但本对话的代码修改范围只限：

- `/Users/chamcham/Documents/AI/CODEX/soccer/football-data-platform`

如果发现需要修改模型项目或展示网站，不能在本对话直接改代码。必须输出交接说明，由用户转给对应项目对话执行。

## 2. 修改边界

允许本对话直接修改：

- 数据层 schema、配置、采集脚本、标准化脚本、发布脚本
- 数据层 `data/normalized`、`data/public`、`data/model`、`reports`
- 数据层设计文档、运行文档、交接文档

不允许本对话直接修改：

- `world-cup-predictor` 代码、测试、README、DESIGN
- `worldcup/2026` 代码、测试、README、DESIGN
- 消费项目本地 fallback、前端组件、模型训练逻辑、Kelly/EV 公式、页面展示逻辑

例外：如果用户明确要求本对话跨目录修改，必须先说明影响范围，再执行。

## 3. 跨项目交接格式

需要其他项目改动时，使用以下格式：

```text
Project:
Task:
Reason:
Required change:
Files likely affected:
Data/API contract impact:
Validation:
Blockers:
Return report expected:
```

交接说明必须足够具体，让对应项目对话可以直接执行，不需要重新推断边界。

## 4. GitHub 提交策略

正常优先级：

1. 先用 GitHub API 检查远端状态。
2. 再用短超时 Git HTTPS 判断普通 `git fetch` / `git push` 是否可用。
3. 如果 Git HTTPS 卡住、超时、HTTP2 报错或连接 GitHub 443 失败，停止反复重试。
4. 改用 GitHub Git Database API 发布提交。

原因：当前环境多次出现 `gh api` 可用但 Git HTTPS 传输不稳定的情况。反复重试 `git push` 会浪费时间和成本。

## 5. GitHub API 发布判定

当满足任一条件时，允许直接走 API 发布：

- `gh api repos/waterdiu/football-data-platform/commits/main` 可用，但 `git fetch` / `git push` 超时
- `git push` 出现 HTTP2、TLS、443 连接或 operation timed out 问题
- 本地提交与远端提交 SHA 不一致，但 tree 内容可验证一致
- 普通 Git 传输不稳定且当前改动需要及时发布到 Pages

API 发布后必须验证：

- 远端 `main` commit SHA
- 远端 commit tree SHA
- 本地 `HEAD^{tree}` 是否与远端 tree 一致
- GitHub Actions / Pages 部署是否成功

## 6. 本地 ahead 状态解释

如果使用 GitHub API 创建了远端等价提交，本地可能显示：

```text
## main...origin/main [ahead 1]
```

这不一定代表内容未同步。判断标准不是本地 `origin/main` 是否 stale，而是：

- 远端 `main` tree SHA
- 本地 `HEAD^{tree}`

两者一致时，内容已经同步。后续等 Git HTTPS 恢复后，再用普通 `git fetch` / `git rebase` 对齐本地元数据。

## 7. 禁止事项

- 不因 `ahead 1` 直接强推。
- 不用 `git reset --hard` 解决 API 推送造成的 SHA 差异，除非用户明确批准。
- 不在数据层对话里直接修改消费项目代码。
- 不把没有验证的远端状态写入协调结论。

## 8. 文档维护

以下情况必须更新本文件或主设计文档：

- 本对话职责边界变化
- 允许修改的目录变化
- GitHub 提交策略变化
- API 发布脚本或流程变化
- 三项目数据契约或交接格式变化
