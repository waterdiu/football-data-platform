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

共享协调文档例外：

- `/Users/chamcham/Documents/AI/CODEX/soccer/WORKSPACE_ORCHESTRATOR.md`
- `/Users/chamcham/Documents/AI/CODEX/soccer/WORKSPACE_STATUS.md`

这两份文件是数据层、模型层和展示站之间的交流机制，可以由本对话维护。它们不是模型或展示站代码，不视为跨项目代码修改。

如果发现需要修改模型项目或展示网站，不能在本对话直接改代码。必须输出交接说明，由用户转给对应项目对话执行。

## 2. 修改边界

允许本对话直接修改：

- 数据层 schema、配置、采集脚本、标准化脚本、发布脚本
- 数据层 `data/normalized`、`data/public`、`data/model`、`reports`
- 数据层设计文档、运行文档、交接文档
- 工作区共享协调文档：`WORKSPACE_ORCHESTRATOR.md`、`WORKSPACE_STATUS.md`

不允许本对话直接修改：

- `world-cup-predictor` 代码、测试、README、DESIGN
- `worldcup/2026` 代码、测试、README、DESIGN
- 消费项目本地 fallback、前端组件、模型训练逻辑、Kelly/EV 公式、页面展示逻辑

例外：如果用户明确要求本对话跨目录修改，必须先说明影响范围，再执行。

## 3. 模型层与数据层协同机制

模型层和数据层通过“平台读写契约 + inbox 写回 + 协调文档回报”协同，不通过互相改源码解决问题。

数据层向模型层提供：

- `data/public/api/worldcup/2026/predictor/*`
- `data/public/api/predictor/data-assets/*`
- `data/public/api/migration-status.json`
- `reports/source-health.json`
- `reports/world_cup_runtime_collection_report.json`

模型层读取平台 predictor bundle、runtime datasets 和 data-assets manifest。模型层不再拥有生产共享数据采集责任。

模型层向数据层写回：

- `data/inbox/predictor/**`

数据层再通过 publish 脚本校验、合并、发布到：

- `data/normalized`
- `data/model`
- `data/public`

模型层不得直接写 `data/public`、`data/model` 或 `data/normalized`。

当模型层发现平台数据缺失、字段不够或 contract 不匹配时，应回报给协调入口。协调入口判断：

- 属于数据源、schema、API、coverage、health、publish 的，留在 `football-data-platform` 修
- 属于特征、模型、训练、评估、Kelly/EV、报告解释的，交给 `world-cup-predictor` 修

模型层回报格式：

```text
Project: world-cup-predictor
Task:
Status:
Completed:
Files changed:
Validation:
Data/API contract impact:
Needs data platform:
Blockers:
Next recommended step:
```

## 4. 跨项目交接格式

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

## 5. GitHub 提交策略

当前仓库状态：

- `world-cup-predictor` 已验证 GitHub SSH 22 和 SSH over 443 可用，remote 已切到 `git@github.com:waterdiu/world-cup-predictor.git`，后续模型仓库提交可优先走普通 SSH `git push`
- `football-data-platform` 当前 remote 仍是 HTTPS：`https://github.com/waterdiu/football-data-platform.git`
- `football-data-platform` 本地仍存在 API 提交造成的本地/远端 commit SHA 分叉，不能直接普通 `git push`

`football-data-platform` 当前提交优先级：

1. 先用 GitHub API 检查远端状态。
2. 如果只是发布数据层文档或数据产物，继续使用 GitHub Git Database API，直到本地分支完成远端对齐。
3. 不允许在本地显示 `ahead` 且远端已通过 API 产生新提交链时直接 `git push`。
4. 后续可以把 `football-data-platform` remote 切到 SSH，但必须先完成本地分支对齐。

原因：当前环境多次出现 `gh api` 可用但 Git HTTPS 传输不稳定的情况。反复重试 `git push` 会浪费时间和成本。

完成 `football-data-platform` 本地对齐后，提交优先级改为：

1. 优先 SSH `git fetch` / `git push`
2. SSH 失败时再走 GitHub API
3. 禁止反复尝试不稳定的 HTTPS Git 传输

## 6. GitHub API 发布判定

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

## 7. 本地 ahead 状态解释

如果使用 GitHub API 创建了远端等价提交，本地可能显示：

```text
## main...origin/main [ahead 1]
```

这不一定代表内容未同步。判断标准不是本地 `origin/main` 是否 stale，而是：

- 远端 `main` tree SHA
- 本地 `HEAD^{tree}`

两者一致时，内容已经同步。后续等 Git HTTPS 恢复后，再用普通 `git fetch` / `git rebase` 对齐本地元数据。

如果远端已经在 API 提交后继续产生新的远端提交，本地 tree 和远端 tree 可能不再一致。这时 `ahead` 不再只是无害显示问题，而是本地提交链和远端提交链分叉。处理规则：

- 不直接 `git push`
- 先确认工作区无未提交改动
- 备份当前本地分支
- 切换 remote 到 SSH
- 通过 SSH fetch 远端 `main`
- 以远端 `origin/main` 作为本地 `main` 基线
- 只在确认本地有远端缺失的内容时，才 cherry-pick 或重新应用

## 8. 禁止事项

- 不因 `ahead 1` 直接强推。
- 不用 `git reset --hard` 解决 API 推送造成的 SHA 差异，除非用户明确批准。
- 不在数据层对话里直接修改消费项目代码。
- 不把模型层写回的 inbox 直接当成 public 真相源，必须经过数据层 publish 校验。
- 不把没有验证的远端状态写入协调结论。

## 9. 文档维护

以下情况必须更新本文件或主设计文档：

- 本对话职责边界变化
- 允许修改的目录变化
- GitHub 提交策略变化
- API 发布脚本或流程变化
- 三项目数据契约或交接格式变化
