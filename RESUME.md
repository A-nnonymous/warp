# Resume

## Purpose

Use this file after repo migration, machine migration, or interrupted sessions.

For a first-time startup on a clean machine, use `new_machine_prompt.md`.

## Read order

1. `checkpoints/manager/latest.md`
2. `reports/manager_report.md`
3. `state/backlog.yaml`
4. `state/gates.yaml`
5. `state/heartbeats.yaml`
6. `state/edit_locks.yaml`
7. `state/agent_runtime.yaml`
8. `status/agents/`
9. `checkpoints/agents/`
10. `experiments/registry.yaml`
11. `strategy/integration_plan.md`
12. `strategy/baseline_trace.md`

## Resume prompt

Paste this into the next chat session after migration:

```text
你现在是 warp 的总控 agent，负责协调目标仓库的交付。请先不要写代码，按以下顺序恢复上下文并汇报：
1. 阅读 checkpoints/manager/latest.md
2. 阅读 reports/manager_report.md
3. 阅读 state/backlog.yaml
4. 阅读 state/gates.yaml
5. 阅读 state/heartbeats.yaml
6. 阅读 state/edit_locks.yaml
7. 阅读 state/agent_runtime.yaml
8. 阅读 status/agents/ 下全部 agent 状态
9. 阅读 checkpoints/agents/ 下全部 agent checkpoint
10. 阅读 experiments/registry.yaml
11. 阅读 strategy/integration_plan.md
12. 阅读 strategy/baseline_trace.md

恢复后请输出：
- 当前项目阶段
- 已通过和未通过的 gate
- 当前 blocker
- 当前可并行的 agent 集合
- 当前 agent 心跳与存活状态
- 当前 provider / worktree / branch / env 拓扑
- 当前高冲突文件的写锁状态
- 推荐的下一步动作

除非我明确要求，否则先不要进入真实实验或大规模代码修改。
```

## Terminal bootstrap command

If you want a quick local preflight after migration, run:

```bash
git status --short && \
sed -n '1,220p' checkpoints/manager/latest.md && \
sed -n '1,220p' reports/manager_report.md && \
sed -n '1,220p' state/heartbeats.yaml && \
sed -n '1,220p' state/agent_runtime.yaml && \
sed -n '1,220p' state/edit_locks.yaml
```