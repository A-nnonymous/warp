# Architecture Refactor Coverage Audit

- 时间：2026-03-16 11:xx CST
- 阶段目标：在上一轮 coverage / smoke 之后，继续清理 orchestration / A0 / mailbox / workflow 剩余测试盲区，重点补齐 A0 的取消 / 中断 / 改规划（replan）能力覆盖。

## 1. 结论

在 coverage guard 落地之后，本轮又补了一阶段**系统级测试增强**，重点不再是提高主干 service/store 的统计数字，而是补此前 audit 已点名的外沿高风险面：

- `config_mixin.py`：补 stale provider/pool repair、section-scope validation filtering 等高风险配置分支
- `launch_mixin.py`：补脏 worktree / sync failure 这类启动前阻断分支
- `cli.py` / `api_mixin.py` / `network.py`：补 bootstrap cold-start、config_text + peek smoke、`stop-listener` alias、命令参数净化与静态路径防穿越
- integration：新增 template/bootstrap -> 保存配置 -> 成功 launch 的长链路烟测

这一阶段新增的关键补洞是：

- `runtime/test_control_plane_integration.py`
  - 新增一个极小 Dummy DAG fixture（`A1-001 -> A2-001`）
  - 覆盖 A0 对 root lane 的取消：关闭 pending plan review，并验证下游依赖不被误推进
  - 覆盖 manager-facing unlock -> intervention 状态切换，以及 A0 对 request 的 `resume` / `cancel` 响应
  - 覆盖 replan 后 owner/claimed_by 迁移、team mailbox fanout，以及**旧 A0 request state 被失效**，避免旧 `resume` 把新 plan-review 请求错误标成已处理
- `runtime/cp/backlog_mixin.py`
  - 新增极小支撑修补：`patch_workflow_item()` 在 workflow update 后清掉对应 task 的 `plan_review` / `task_review` 持久化 request state，保证 replan 后 A0 看到的是新的 pending request，而不是继承旧回复状态

主干 coverage 门槛本身仍然由下面这个守卫脚本负责：

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
- 最终 coverage：**97%**（主干 guard 统计口径不变）
- 同次运行中，全量测试结果：**99 tests, OK**

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
- `runtime/test_control_plane_runtime_edges.py`
  - 覆盖 `repair_config_resource_pool_references()` 的 stale provider/pool 清理
  - 覆盖 `validate_config_section("workers")` 的 section-scope 过滤，避免 project/dashboard 噪音串进 workers 校验
  - 覆盖 `ensure_worktree()` 的脏目录阻断分支
  - 覆盖 `ensure_environment()` 的 sync failure stderr 透传
  - 覆盖 `resolve_runtime_config()` 的 bootstrap/template 解析分支
  - 覆盖 `strip_command_args()` 与 `safe_relative_web_path()` 的 network/CLI 基础 smoke

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
- `runtime/test_control_plane_integration.py`
  - 新增 `test_cli_api_smoke_suite_covers_config_text_peek_and_stop_listener_alias`
  - 新增 `test_bootstrap_cold_start_config_save_then_launch_smoke`
  - 把 config_text 保存、peek API、`stop-listener` CLI alias、bootstrap cold-start -> save -> launch 长链路纳入集成烟测

## 5. 未覆盖风险点

下面这些风险点本阶段没有被纳入 90% coverage 门槛，仍然值得明确记账：

1. **`config_mixin.py` 大量配置校验/修复分支**
   - 本轮已补 stale provider/pool repair 与 workers section filtering，但完整 validation matrix 仍远未穷尽
2. **`launch_mixin.py` 的 worktree / environment / worker lifecycle**
   - 本轮已补脏 worktree / sync failure 阻断；真正高风险点仍在 git worktree 冲突、wrapper/子进程失败、端口占用等组合行为
3. **`api_mixin.py` / `cli.py` / `network.py` 的 HTTP/CLI/server 面**
   - 本轮已补 config_text / peek / `stop-listener` / bootstrap cold-start smoke；但更多 handler 组合、bind 失败与异常恢复仍需更偏集成的测试
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
