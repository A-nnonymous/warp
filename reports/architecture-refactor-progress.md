# Architecture Refactor Progress

- 时间：2026-03-15 20:xx CST
- 当前阶段：先读 diff 与 integration 失败，正在定位兼容性回归。
- 已观察到的高优先级失败：A0 console / manager_console、port busy launch failure、invalid pool repair、missing provider credentials aggregation、workflow/attention summary 相关。
- 当前断点：新 stores 抽象替换后，若 load() 默认结构与旧 mixin 预期不完全一致，会直接打爆 integration。
- 未决问题：
  - ManagerConsoleStore 是否完整保留 requests/messages 旧结构与容错。
  - MailboxStore/LockStore 是否保留旧字段默认值、列表/字典兜底。
  - launch failure 聚合链路是否仍把 provider/port busy 错误写入 attention summary / escalation。
  - workflow patch 是否仍兼容旧 tests 对状态文件 patch/读取方式的假设。
- 下一步：
  1. 跑失败用例单测并抓完整 traceback。
  2. 对照 contracts.py 与 stores/ 的 load/persist 默认结构，逐个补兼容层。
  3. 优先修 launch failure aggregation、workflow patch、mailbox/manager_console。
  4. 回归跑 integration 直到全绿；若未全绿，不提交。

---

- 时间：2026-03-16 00:5x CST
- 当前阶段：已把 routing 中任务策略/任务画像/默认 provider 顺序抽到纯 service，开始把 mixin 从“规则承载者”压回“编排层”。
- 本阶段代码成果：
  - 新增 `runtime/cp/services/task_routing.py`，沉淀 `task_policy_*`、`build_task_profile`、`select_task_record_for_worker`、`suggested_*` 等纯函数。
  - `routing_mixin.py` 对上述逻辑改为薄委托，减少 domain 规则继续堆在 mixin 里。
  - 新增 `runtime/test_task_routing_service.py`，覆盖 provider 优先级、initial provider、任务选择、规则命中、branch 命名。
- 已验证：
  - `uv run --no-project --with 'PyYAML>=6.0.2' python -m unittest runtime.test_control_plane_architecture runtime.test_task_routing_service` ✅
- 当前断点：
  - `routing` 的任务画像规则已可独立演进，但 `recommended_pool_plan()` 仍留在 mixin，下一刀可以继续把 pool ranking/lock reason 抽成独立 service。
  - `provider/dashboard/backlog` 仍有大块业务规则混在 mixin 内；integration 全量回归一次超时中断，后续需要分组跑或延长超时继续收口。
- 下一步：
  1. 继续抽 `routing` 的 pool recommendation / queue ranking 逻辑，或转切 `dashboard` 的 manager-control 聚合逻辑。
  2. 针对 integration 失败/超时点做分组回归，避免全量一次性跑太久。
  3. 若下一阶段仍是纯 domain 抽离，优先保持“新 service + 薄 mixin + 单测”节奏。

---

- 时间：2026-03-16 01:35 CST
- 当前阶段：已把 routing/provider 共用的 pool selection 主干从 mixin 中抽到纯 service，`recommended_pool_plan()` 不再承载具体排序规则。
- 本阶段代码成果：
  - 新增 `runtime/cp/services/pool_selection.py`，沉淀 `configured_pool_candidates`、`queue_pool_candidates`、`rank_pool_candidates`、`recommended_pool_plan`、`best_pool_for_provider`、`best_pool_for_worker` 等纯函数。
  - `routing_mixin.py` 的 `recommended_pool_plan()` 改成薄委托，保留编排，不再内嵌 pool ranking / lock reason 细节。
  - `provider_mixin.py` 的 candidate/best-pool 选择逻辑改为复用同一组 service，减少 routing/provider 两套并行演化风险。
  - 新增 `runtime/test_pool_selection_service.py`，覆盖 candidate shaping、provider affinity ranking、preferred-provider lock、explicit override、best-pool helper。
  - 更新 `runtime/cp/CODE_INDEX.md`，把 `pool_selection.py` 纳入 service 层索引。
- 已验证：
  - `uv run --no-project --with 'PyYAML>=6.0.2' python -m unittest runtime.test_control_plane_architecture runtime.test_task_routing_service runtime.test_pool_selection_service` ✅
  - `uv run --no-project --with 'PyYAML>=6.0.2' python -m unittest runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_multi_agent_launch_policies_and_heartbeats` ✅
- 当前断点：
  - `routing` 的 pool recommendation 主干已抽离，但返回 payload 仍是松散 dict；若下一刀继续收紧，可以把 pool plan / provider choice 升级成 typed contract。
  - `dashboard/backlog` 仍有大块 manager-control 与 workflow 聚合规则留在 mixin，下一阶段可沿同样套路继续拆纯 service。
- 下一步：
  1. 评估是否为 pool/provider 决策补 `contracts.py` typed dict，顺手把 dashboard 对应消费面收紧。
  2. 在 `dashboard_mixin.py` / `backlog_mixin.py` 中选一块高频决策逻辑继续抽纯 service。
  3. 继续用“service 抽离 + 定向 integration 回归”推进，避免再回到一次性全量长跑。
