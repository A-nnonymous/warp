# WARP

English: [`README.md`](README.md) | 中文：`README_CN.md`

**Workload-Aware Agents Routing Protocol** —— 一个面向任意目标仓库的多智能体编排协议与运行时控制平面。

WARP 定义了管理者代理（A0）如何规划工作、按依赖调度任务、为 worker 选择 provider、隔离分支并观测进展，所有这些都通过同一个带实时仪表盘的 control plane 完成。

它是**项目无关**的：把它指向任意仓库，定义 backlog，WARP 就能接手执行。

---

## 给人类使用者

### 第一原则

WARP 是一个**高度 agent 自治**的框架。

这意味着：

- **A0 是默认操作者**
- **A0 可以自主做决策、修订计划、重塑工作流**
- **control plane 主要用于人类观测、审计和异常干预**
- 当 A0 遇到歧义、风险或无法安全独立决策的问题时，人类再介入

不要把 dashboard 理解成人类必须手工驱动每一步的地方。

更准确的理解是：人类在这里观察系统、检查 durable state，并只在必要时干预。

### 快速开始

```bash
# 只启动 dashboard（默认 detach）
python runtime/control_plane.py serve

# 启动 dashboard，并拉起当前可运行的 workers
python runtime/control_plane.py up
```

默认监听地址：`0.0.0.0:8233`

### 快速决策表

| 如果你想…… | 应使用 | 默认姿态 |
|---|---|---|
| 看 A0 和 workers 在做什么 | **control plane dashboard** | 先观察 |
| 审批、驳回、解阻或调整 durable workflow 决策 | **A0 Console** | 只在需要时人工介入 |
| 高密度编码、调试、设计讨论 | **外部 Copilot** | 把高带宽对话放在外部 |
| 修改 owner、状态、依赖、plan state 等任务真相 | **Workflow update** | 把 durable 事实写回 |
| 给其他人或其他 agent 留 durable 协作上下文 | **Mailbox** | 只在影响他人时通知 |
| 暂停或移交未完成工作 | **Checkpoint** | 保证可恢复 |

### 推荐的人机协作方式

人性化优先的默认规则是：让 A0 默认自主运行，把 control plane 当作 durable source of truth，把外部 Copilot 会话当作高带宽工程工作台。

推荐默认循环：

1. 先用 dashboard 理解 A0 已经在做什么。
2. 除非出现歧义、风险或阻塞决策，否则让 A0 继续自主推进。
3. 只有在需要 durable manager 参与时，才使用 **A0 Console** 进行审批、解阻、owner 变更或 workflow 调整。
4. 用外部 Copilot 处理高密度实现、调试和设计讨论。
5. 在结束外部会话前，把 durable state 通过 workflow update、mailbox 或 checkpoint 写回 WARP。

这样既保留了工程协作的高带宽体验，也不会把人类降级成 A0 的手工替身。

### 什么场景该用哪个界面

| 场景 | 最佳界面 | 原因 |
|---|---|---|
| 审批 / 驳回 plan | **A0 Console** | 这是 manager 决策，应该对 A0 和后续会话可见 |
| 给 worker 解阻或恢复指导 | **A0 Console** | 指令应成为 durable workflow state |
| 修改 owner、claim state、gate、plan state 或 task status | **control plane 中的 Workflow update** | 这些是规范执行事实 |
| 跨 worker 协调或提醒 | **Team mailbox** | 其他 worker 与后续会话都能看到 |
| 大规模改代码、调试、设计探索 | **外部 Copilot** | 更好的带宽、迭代速度和交互体验 |
| 会话结束、handoff 或可能中断 | **Checkpoint + 可选 mailbox / workflow write-back** | 防止上下文隐性丢失 |

### 生命周期与持久化

推荐的运行模型是不对称的：

- **A0 + control plane** 应该是长生命周期的
- **外部 Copilot 会话** 应该是短生命周期、可替换的

在实践中：

- 把 A0 和 dashboard 作为团队的 durable operating memory
- 按任务、事件或设计主题开启外部 Copilot 会话
- 不要把外部聊天记录误当成系统记录本
- 在离开外部会话之前，回写最少但足够的 durable facts，确保下一个人类或 agent 不必重建上下文

好的 durable write-back 包括：

- 任务状态变化时写 workflow update
- 需要通知 A0 或其他 worker 时发 mailbox message
- 任务部分完成但尚未结束时写 checkpoint

### 什么时候必须写 Checkpoint

当满足以下任一条件时，应要求 worker 写 checkpoint：

- 会话即将结束
- 任务要移交给其他 agent 或稍后恢复
- 已有有意义进展，但尚未完成最终集成
- 当前状态包含不易重新发现的结论、阻塞或下一步

Checkpoint 的目标是让下一次接手成本更低，而不是把所有过程逐字记录下来。

### Mailbox 与 Workflow update 的边界

当**任务记录本身发生变化**时，使用 **workflow update**：

- owner
- claim state
- task status
- plan state
- dependencies
- manager note

当你需要传达 durable 上下文，但**不改变任务记录本身**时，使用 **mailbox**：

- handoff 说明
- blocker 通知
- 协调请求
- review 提醒
- 设计问题

如果两者都发生了，就先更新 workflow，再发送说明协作影响的 mailbox。

### 核心能力

| 能力 | 说明 |
|---|---|
| **依赖感知调度** | 只有当上游任务完成时才会启动 worker；monitor loop 每 5 秒自动拉起新可运行 agent |
| **Provider 路由** | 支持可插拔 provider 后端（ducc、claude、API-key 服务等），带优先级评分与资源池 |
| **分支隔离** | 每个 worker 都有独立 worktree 与 branch；合并由 merge queue 统一处理 |
| **软停止** | checkpoint 后停止：agent 在关闭前保存进度到 `checkpoints/agents/`，适合 handoff |
| **实时可观测性** | Task DAG、agent peek、heartbeats、team mailbox、manager report |
| **按 agent 隔离身份** | 每个 worker 使用自己的 git 身份提交（`A1-Protocol`、`A2-Auditor` 等） |

### 命令

| 命令 | 效果 |
|---|---|
| `serve` | 启动 dashboard，不启动 workers |
| `up` | 启动 dashboard，并拉起 workers |
| `stop-agents` | 向 workers 发送 SIGTERM，保留 dashboard |
| `soft-stop` | checkpoint + 停止 workers |
| `silent` | 关闭 dashboard，保留 workers |
| `stop-all` | 全部停止 |

常用参数：`--foreground`、`--open-browser`、`--bootstrap`、`--host`、`--port`、`--config`

### Dashboard 结构

**Toolbar**：Launch · Restart · Soft Stop · Stop Agents · Silent Mode · Stop All · Refresh

| 标签页 | 内容 |
|---|---|
| **Overview** | Task DAG、agent peek、进度指标、merge 状态、健康卡片 |
| **Operations** | Provider queue、processes、backlog、gates、topology、heartbeats、mailbox、manager report |
| **Settings** | 项目路径、资源池、merge policy、worker defaults、逐 worker override |

**A0 Console**：一个弹出式 manager 控制台，用于 plan 审批、解阻决策和 workflow patch。它适合 durable manager action，不适合承载漫长的工程对话。

### 配置

最小 `runtime/local_config.yaml`：

```yaml
project:
  local_repo_root: /path/to/target-repo
  integration_branch: main

providers:
  ducc:
    auth_mode: session
```

A0 会根据 backlog state 推导 worktree path、branch 和 test command。若要覆盖，可在 Settings 页面中调整；使用 `Reset to A0` 可清除人工 pin。

### 仓库结构

| 目录 | 用途 |
|---|---|
| `runtime/` | control plane、配置、dashboard 前端，以及统一收拢在 `runtime/generated/` 下的运行时产物 |
| `tests/` | 与生产代码分离的 Python 测试套件 |
| `strategy/` | 项目意图、范围与基线映射 |
| `governance/` | 操作规则、决策与机器策略 |
| `state/` | backlog、gates、heartbeats、mailbox、locks |
| `status/agents/` | 每个 worker 的状态流 |
| `checkpoints/` | manager / worker 的可恢复快照 |
| `reports/` | 交付工件与 manager report |
| `bootstrap/` | 给新 agent 会话使用的零上下文接管包 |

### 关键概念

| 术语 | 定义 |
|---|---|
| **A0 Plan** | 从 backlog + runtime + policies 派生出的目标状态，是所有 worker 的默认执行目标 |
| **Override** | 人工钉住的例外配置；`Reset to A0` 会移除它 |
| **Soft Stop** | checkpoint 后停止：每个 agent 在关闭前保存进度 |
| **Task DAG** | 依赖图（绿=done，蓝=active，黄=pending，灰=blocked） |
| **Peek** | 每个 agent 解析后输出的实时滑动窗口 |
| **Gate** | 同步屏障；位于 gate 之后的任务要等 gate 打开 |

### 前端重建

```bash
source ~/.bashrc && cd runtime/web && npm install && npm run build
```

### 示例部署

WARP 的初始部署目标是 Linux 上面向 Hopper / Blackwell GPU 的 SonicMoE FP8 kernel 交付。这只是一个示例；WARP 本身没有硬件绑定。

---

## 给 Agent

如果你是刚接管这个仓库的 AI agent，**不要全仓通读**。请走最低成本的接管路径。

### Bootstrap（零上下文接管）

先读 [`bootstrap/BOOTSTRAP.md`](bootstrap/BOOTSTRAP.md)。它定义了：

- 最小阅读顺序（governance → bootstrap files → README → governance protocols）
- 一个可直接粘贴到新会话中的标准 bootstrap prompt
- 接管审计要求和预期完成质量

### Resume（中断会话恢复）

如果是恢复被打断的现场，从 [`RESUME.md`](RESUME.md) 开始。它定义了 live state 的恢复顺序：

1. `checkpoints/manager/latest.md`
2. `reports/manager_report.md`
3. `state/backlog.yaml` + `state/gates.yaml`
4. `state/heartbeats.yaml` + `state/agent_runtime.yaml`
5. `state/team_mailbox.yaml` + `state/edit_locks.yaml`
6. `status/agents/` + `checkpoints/agents/`
7. `strategy/integration_plan.md` + `strategy/baseline_trace.md`

### 新机器接管

冷启动恢复时先读 `new_machine_prompt.md`。

### 基本规则

- 优先保持最简单的人类操作路径。
- 当 A0 可以推导出同样的数据时，不要退回到手工 YAML-first 配置。
- 文档、运行时、前端和测试要在同一改动中保持一致。
- 任何前端源码变更后，都要重建 `runtime/web/static`。
- 对高冲突文件执行单写者纪律：编辑前先在 `state/edit_locks.yaml` 中声明持锁。
