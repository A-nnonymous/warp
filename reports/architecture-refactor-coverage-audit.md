# Architecture Refactor Coverage Audit

- 时间：2026-03-16 10:xx CST
- 阶段目标：对 architecture refactor 主干补一轮 coverage / 全量测试盘点，把 coverage >90% 落成可执行、可失败、可回归的门槛。

## 1. 结论

本阶段把 coverage 门槛落成了一个可直接运行的守卫脚本：

```bash
uv run --no-project --with 'PyYAML>=6.0.2' --with 'coverage>=7.6.0' python3 runtime/check_cp_refactor_coverage.py
```

它会做三件事：

1. 用 `coverage run --source=runtime/cp` 跑完整 `runtime/test_*.py` 套件
2. 只对本轮 refactor 的主干范围出 report：
   - `runtime/cp/contracts.py`
   - `runtime/cp/services/*.py`
   - `runtime/cp/stores/*.py`
3. 在覆盖率低于 90% 时直接失败（`coverage report --fail-under=90`）

本次实测结果：

- 覆盖统计范围：`runtime/cp/contracts.py` + `runtime/cp/services/*.py` + `runtime/cp/stores/*.py`
- 最终 coverage：**97%**（1423 statements / 39 missed）
- 同次运行中，全量测试结果：**88 tests, OK**

额外核对：

```bash
uv run --no-project --with 'PyYAML>=6.0.2' python3 -m unittest discover -s runtime -p 'test_*.py'
```

结果同样为：`Ran 88 tests ... OK`

## 2. 为什么 coverage 门槛只落在这个范围

这轮 architecture refactor 的真实主干，不是整个 `runtime/cp` 包，而是新引入并持续扩展的三层：

- `contracts.py`：typed contract 真相层
- `services/`：抽离出的纯函数域逻辑
- `stores/`：持久化与归一化边界

如果把 90% 门槛直接压到整个 `runtime/cp`：

- 当前实测全包 coverage 只有 **39%**
- 主要缺口集中在 `api_mixin.py`、`cli.py`、`config_mixin.py`、`launch_mixin.py`、`dashboard_mixin.py`、`provider_mixin.py` 等 IO / orchestration / CLI / server 面
- 这些模块当前没有与 refactor 同量级的测试锚点，直接强行设 90% 会把门槛变成“统计上好看但工程上不可信”的假要求

所以本阶段的选择是：

- **门槛只覆盖本轮真正作为“新结构真相”的主干**
- **测试执行仍跑全量 `runtime/test_*.py`**，避免守卫只在小圈子里自嗨
- 这样既保证 coverage 口径可信，又不偷换“是否有更广回归”的问题

## 3. 已覆盖功能

### 3.1 contracts

- `runtime/cp/contracts.py` 全量导入并被 architecture / service / integration 测试持续消费
- manager-facing / runtime-facing 的关键 typed payload 已在测试里形成稳定锚点

### 3.2 services

已覆盖的 service 主干包括：

- `task_routing.py`
  - provider 默认偏好顺序
  - initial provider 选择
  - task policy defaults / types / rules 归一化
  - rule 匹配（agent / task_id / title_contains）
  - worker 对应任务选择
  - task profile / branch name 组装
- `pool_selection.py`
  - worker/default queue 候选池选择
  - provider affinity 排序
  - explicit pool override
  - preferred-provider launch-ready 锁定
  - best-pool provider/worker helper 与异常分支
- `dashboard_summary.py`
  - active / attention / runnable / blocked 分类
  - dependency-blocked 判定
  - handoff attention summary 的优先级链路
  - process_exit / stale / blockers / pending_work / fallback next_checkin
- `workflow_patch.py`
  - task action：claim / release / start / submit_plan / approve_plan / reject_plan / request_review / complete / reopen
  - plan approval completion guard
  - workflow patch 列表字段归一化、布尔字段、claimed/review/completed/plan-review 时间戳修正
  - workflow patch summary
- 其余已存在测试覆盖并在本次 guard 中继续纳入统计的 service：
  - `backlog_notifications.py`
  - `cleanup_views.py`
  - `dashboard_queue.py`
  - `mailbox_views.py`
  - `provider_auth.py`
  - `provider_queue.py`
  - `telemetry_views.py`
  - `services/__init__.py`

### 3.3 stores

已覆盖的 store 主干包括：

- `BacklogStore`
  - item normalize 的 claim/status/plan_state 衍生规则
  - load 缺文件 / 非 dict payload 容错
  - persist 时过滤脏 item、补 `last_updated`
- `MailboxStore`
  - manager/direct scope 归一化
  - ack_state 默认化
  - related_task_ids 去重
  - 缺文件 / 非 dict payload 容错
  - persist/load 回写一致性
- `RuntimeStore`
  - worker normalize 默认值
  - 缺文件 / 非 dict payload 容错
  - persist/load 的 schema / project / workers 回写一致性
- 其余已存在测试继续覆盖并纳入统计：
  - `HeartbeatStore`
  - `LockStore`
  - `ManagerConsoleStore`
  - `ProviderStatsStore`
  - `stores/__init__.py`

## 4. 本阶段新增 / 修改的测试

### 新增

- `runtime/test_store_normalization.py`
  - 覆盖 backlog/mailbox/runtime store 的 normalize/load/persist 容错与字段归一化

### 扩展

- `runtime/test_workflow_patch_service.py`
  - 补 task-action 的冲突/释放/拒绝计划/完成/重开等分支
  - 补 workflow patch 的列表非法输入、时间戳回填/清空、空更新校验
- `runtime/test_task_routing_service.py`
  - 补 policy normalizer、rule filter、fallback provider、explicit task type / branch override 等分支
- `runtime/test_pool_selection_service.py`
  - 补 default pool fallback、无资源池、无 launch-ready preferred provider、异常分支
- `runtime/test_dashboard_service.py`
  - 补 stale / dependency-blocked 分类、handoff attention fallback 链路

## 5. 未覆盖风险点

下面这些风险点本阶段没有被纳入 90% coverage 门槛，仍然值得明确记账：

1. **`config_mixin.py` 大量配置校验/修复分支**
   - 目前整体 coverage 很低，且条件组合多
2. **`launch_mixin.py` 的 worktree / environment / worker lifecycle**
   - 真正高风险点在文件系统、git、子进程、provider launch 行为
3. **`api_mixin.py` / `cli.py` / `network.py` 的 HTTP/CLI/server 面**
   - 需要更偏集成/端到端的测试，不适合靠纯 service 单测凑 coverage
4. **`dashboard_mixin.py` / `provider_mixin.py` / `state_mixin.py` / `mailbox_mixin.py` 的 orchestration 薄委托链路**
   - 现在主要靠定向 integration 守，没有形成系统级 coverage 门槛
5. **`telemetry.py` / `markdown.py` 等工具层边缘解析输入**
   - 异常/脏输入组合仍不充分
6. **provider probe / launch 失败与 attention summary 的跨模块联动**
   - 虽已有部分 integration，但组合场景仍可能有漏口

## 6. 建议后续补的 8 个关键用例

1. **Config repair / validation matrix**
   - 非法 `resource_pool`、缺 provider、坏 section 组合下的 `config_mixin` 修复与报错优先级
2. **Launch worker failure matrix**
   - worktree 已存在、branch 冲突、环境缺失、provider wrapper 缺失、端口占用
3. **Dashboard assembler end-to-end snapshot**
   - `build_dashboard_state()` 在多 worker / mixed heartbeat / mixed backlog 状态下的完整 payload 快照
4. **Provider auth + queue + launch policy integration**
   - session probe 失败、api-key 缺失、fallback provider、launch policy 限制一起出现时的最终决策
5. **Cleanup status integration**
   - 多 worker cleanup blockers、lock 文件、pending review 混合输入下的 manager-facing 结果
6. **A0 console / mailbox / dashboard request loop**
   - manager console request 被 mailbox / dashboard 消费后的状态迁移与去重
7. **Telemetry parser dirty-input cases**
   - 非法 usage/progress/message payload、截断日志、半结构化日志文本
8. **CLI / API smoke suite**
   - `run_up` / `run_serve` / stop commands / 常见 GET/POST handler 的最小烟测

## 7. 运行命令清单

### coverage 门槛守卫（会失败）

```bash
uv run --no-project --with 'PyYAML>=6.0.2' --with 'coverage>=7.6.0' python3 runtime/check_cp_refactor_coverage.py
```

### 全量 unittest 回归

```bash
uv run --no-project --with 'PyYAML>=6.0.2' python3 -m unittest discover -s runtime -p 'test_*.py'
```

### 如果需要看整个 `runtime/cp` 的真实 coverage 背景值

```bash
uv run --no-project --with 'PyYAML>=6.0.2' --with 'coverage>=7.6.0' python3 -m coverage run --source=runtime/cp -m unittest discover -s runtime -p 'test_*.py'
uv run --no-project --with 'PyYAML>=6.0.2' --with 'coverage>=7.6.0' python3 -m coverage report -m
```

当前这个“全包背景值”约为 **39%**。它用于说明仓库全貌，不用于本阶段 90% 门槛判定。
