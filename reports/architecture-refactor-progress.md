# Architecture Refactor Progress

- 时间：2026-03-16 11:xx CST
- 当前阶段：进入单独的“测试增强”阶段，目标不是继续拆 service，而是补系统外沿高风险面：config / launch / CLI / API / bootstrap 长链路。
- 本阶段代码成果：
  - 新增 `runtime/test_control_plane_runtime_edges.py`，补 `config_mixin.py` / `launch_mixin.py` / `cli.py` / `network.py` 的高风险分支：stale provider/pool repair、workers section filtering、脏 worktree 阻断、sync failure 透传、bootstrap config resolve、命令参数净化、静态路径防穿越。
  - 扩展 `runtime/test_control_plane_integration.py`，新增两条系统级 smoke：
    - `test_cli_api_smoke_suite_covers_config_text_peek_and_stop_listener_alias`
    - `test_bootstrap_cold_start_config_save_then_launch_smoke`
  - 更新 `reports/architecture-refactor-coverage-audit.md`，把本轮系统外沿补测记录进 audit，明确哪些盲区已补、哪些仍未完全覆盖。
- 已验证：
  - `uv run --no-project --with 'PyYAML>=6.0.2' python3 -m unittest runtime.test_control_plane_runtime_edges runtime.test_control_plane_architecture runtime.test_control_plane_integration` ✅（41 tests, OK）
- 当前断点：
  - 主干 coverage guard 仍维持 `contracts + services + stores` 的 97% 门槛；本轮主要增加的是系统级保障，不改变 guard 统计口径。
  - config / launch / CLI / API 面已经补到一轮高价值 smoke，但完整 failure matrix（如 worktree branch 冲突、bind 失败恢复、更多 handler 组合）仍有余量。
- 下一步：
  1. 保持本阶段停在测试增强 + 文档 + 单独 commit。
  2. push 当前分支，不继续打开下一阶段。


- 时间：2026-03-16 10:2x CST
- 当前阶段：主线已收官，转入全局 polish + 经验沉淀。本阶段不再打开新的架构支线，只做 service 导出面/索引一致性打磨，并补 architecture refactor 复盘文档。
- 本阶段代码成果：
  - 整理 `runtime/cp/services/__init__.py`，补上 barrel module docstring，并把纯 service 导出面收成显式、稳定、按字母序可扫描的 API surface，降低后续维护者在 service 层入口处的认知负担。
  - 更新 `runtime/test_control_plane_architecture.py`，新增对 `runtime.cp.services` barrel export 的守卫测试，确保核心 helper 继续通过统一入口可导入，同时保持 `__all__` 有序、可审阅。
  - 更新 `runtime/cp/CODE_INDEX.md`，明确 `services/__init__.py` 是 curated barrel export；新增 `reports/architecture-refactor-retrospective.md`，沉淀本轮 refactor 的阶段纪律、切分原则、typed contract vs service 抽离判断法、测试/验收策略与后续建议。
- 已验证：
  - `uv run --no-project --with 'PyYAML>=6.0.2' python3 -m unittest runtime.test_control_plane_architecture runtime.test_dashboard_queue_service runtime.test_cleanup_view_service runtime.test_provider_auth_service runtime.test_provider_queue_service runtime.test_telemetry_view_service runtime.test_mailbox_view_service runtime.test_backlog_notification_service runtime.test_workflow_patch_service runtime.test_task_routing_service runtime.test_pool_selection_service` ✅
- 当前断点：
  - architecture refactor 主线维持“已完成”判断；本阶段只做收官后的可维护性打磨与经验沉淀，不继续扩散到 gateway/web 或新的 service 拆分。
- 下一步：
  1. 保持本阶段唯一 commit 停在 checkpoint，不 push。
  2. 后续若再继续演进，应另开新 session、另选单一刀口。

- 时间：2026-03-16 10:3x CST
- 当前整体状态：本轮 architecture refactor 主线已完成，可按“验收通过”看待。routing / pool selection / dashboard summary / dashboard queue / mailbox views / cleanup views / backlog notifications / workflow patch / telemetry / provider auth / provider queue 已全部沉到 `runtime/cp/services/`，manager/provider/process/backlog/mailbox 关键视图与状态转换已从 mixin 里的大段规则分支收成可测试纯函数。
- 本阶段（最终收尾）代码成果：
  - 新增 `runtime/cp/services/cleanup_views.py`，把 `cleanup_status()` 中最后残留的 cleanup review 汇总、锁文件归并、全局 blocker 聚合、worker row shaping 抽成纯 helper/service：`cleanup_review_maps()`、`cleanup_locked_files()`、`cleanup_worker_row()`、`cleanup_status_view()`。
  - `runtime/cp/mailbox_mixin.py` 的 `cleanup_status()` 现在只保留 runtime/heartbeat/process 状态采集与薄委托，不再内嵌 cleanup blocker / pending review / worker row 组装细节，最后一块 manager-facing cleanup 视图残留已经收掉。
  - 新增 `runtime/test_cleanup_view_service.py`，并更新 `runtime/test_control_plane_architecture.py`、`runtime/cp/services/__init__.py`、`runtime/cp/CODE_INDEX.md`，把 cleanup view service 纳入纯函数测试、架构测试面与索引；同时修正 CODE_INDEX 中 `cleanup_status()` 的归属说明。
- 已完成主线：
  1. routing / pool selection：任务策略、provider/pool 选择规则已 service 化。
  2. dashboard / manager-facing views：summary、merge queue、A0 request catalog、mailbox catalog、cleanup status 已拆成纯 view service。
  3. backlog / workflow：task action、workflow patch、mailbox notification routing 已 service 化。
  4. provider / process：telemetry normalization、launch/runtime metadata、auth readiness、provider queue row shaping 已 service 化并接入 typed contracts。
  5. contracts / stores / architecture tests：核心 manager-facing 与 runtime-facing payload 已统一到 `contracts.py`，stores 与 architecture tests 已覆盖新结构。
- 剩余风险 / 后续可选优化（非阻塞）：
  - `record_a0_user_message()` 仍属于 manager-console 写入编排，当前体量已小且职责明确；若未来继续细化，可再评估是否拆成单独 console-write helper。
  - `dashboard_queue.py` 仍同时承载 merge queue 与 A0 request 聚合；当前已足够验收，如后续继续瘦身，可再考虑按 read/write or queue/request 语义拆模块。
  - CODE_INDEX 的行数统计未来若继续波动，可在后续非功能改动时顺手刷新；本轮以职责与索引一致性为准。
- 下一步：执行最终定向测试 + 更广回归；若全绿，直接创建本阶段唯一 commit 并 push 当前分支。

- 时间：2026-03-16 10:1x CST
- 当前阶段：收 `dashboard_queue.py` 的 A0 request catalog 尾巴，把 backlog review request 与 merge-queue intervention/unlock request 生成从大函数内联分支拆成明确 helper，优先一刀收掉 manager-facing request shaping 残留。
- 本阶段代码成果：
  - 重构 `runtime/cp/services/dashboard_queue.py`，新增 `backlog_plan_review_request()`、`backlog_task_review_request()`、`merge_queue_intervention_request()`、`merge_queue_unlock_request()` 与共用 saved/body helper，把 `build_a0_request_catalog()` 压回聚合/排序层，不再内嵌四类 request 的具体 shaping。
  - merge queue 的 unlock 请求现在单独产出 `request_type="unlock"`，与 `worker_intervention` 明确分流；unlock/intervention 的 request id 也改成按语义稳定生成，避免继续把标题文案耦进持久化 key。
  - 更新 `runtime/test_dashboard_queue_service.py` 与 `runtime/cp/CODE_INDEX.md`，把 plan/task review、worker intervention、unlock request 的分流与排序行为纳入定向单测与索引说明。
- 已验证：
  - `uv run --no-project --with 'PyYAML>=6.0.2' python3 -m unittest runtime.test_dashboard_queue_service runtime.test_control_plane_architecture runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_task_actions_drive_plan_and_review_flow runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_a0_console_records_user_reply runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_team_mailbox_send_and_acknowledge_flow` ✅
- 当前断点：
  - `build_a0_request_catalog()` 的 request shaping 残留已基本收干净，但 `dashboard_queue.py` 仍同时承载 merge queue row shaping 与 A0 request aggregation；若还要继续细收，可再评估是否把 A0 request builders 独立成更专门模块。
  - mailbox/cleanup 侧残留仍主要在 `mailbox_mixin.py` 的 `cleanup_status()` blockers / worker-row shaping，以及 `record_a0_user_message()` 这类 manager-console 写入编排，已比 request catalog 更像最后一刀范围。
- 下一步：
  1. 优先转去 `mailbox_mixin.py` 的 `cleanup_status()`，把 pending review / lock / blocker / worker row shaping 抽成纯 view service，收掉 manager-facing cleanup 尾巴。
  2. 若坚持继续细拆 dashboard queue，则只做更彻底的模块分离，不再回到 request 字段微调。
  3. 继续坚持“单阶段、单刀口、定向测试、单 commit”节奏。

- 时间：2026-03-16 10:0x CST
- 当前阶段：收 mailbox/mailbox_mixin 尾巴，把 mailbox catalog / A0 inbox filtering / pending 统计从 mixin/dashboard 消费面一起抽到独立 view service，优先压缩 backlog-mailbox 剩余面。
- 本阶段代码成果：
  - 新增 `runtime/cp/services/mailbox_views.py`，沉淀 `pending_mailbox_messages()`、`manager_inbox()`、`build_team_mailbox_catalog()`，统一承载 team mailbox catalog shaping、A0 inbox 过滤与 pending 计数。
  - `mailbox_mixin.py` 的 `team_mailbox_catalog()` 改成薄委托；`dashboard_mixin.py` / `services/dashboard_queue.py` 不再各自重算 mailbox inbox，而是直接消费 `TeamMailboxState.a0_inbox`，让 mailbox payload shaping 与 A0 request 聚合对齐到同一来源。
  - `runtime/cp/contracts.py` 为 `TeamMailboxState` 补上 `a0_inbox` typed shape；新增 `runtime/test_mailbox_view_service.py`，并更新 `runtime/test_dashboard_queue_service.py`、`runtime/test_control_plane_architecture.py`、`runtime/cp/services/__init__.py`、`runtime/cp/CODE_INDEX.md`，把 mailbox view service 纳入纯函数测试、架构测试面与索引。
- 已验证：
  - `uv run --no-project --with 'PyYAML>=6.0.2' python3 -m unittest runtime.test_mailbox_view_service runtime.test_dashboard_queue_service runtime.test_control_plane_architecture runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_team_mailbox_send_and_acknowledge_flow runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_a0_console_records_user_reply runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_task_actions_drive_plan_and_review_flow` ✅
- 当前断点：
  - mailbox catalog / A0 inbox filtering / pending 统计已从 mixin 与 dashboard 双侧散落逻辑收成单一 service，但 `build_a0_request_catalog()` 本体里 backlog plan-review / task-review / worker intervention request 生成仍是另一大块 manager-facing 聚合逻辑，尚未继续拆细 helper。
  - `mailbox_mixin.py` 里 cleanup/status 与 record-a0-message 仍混在同一 mixin；若继续追求彻底收尾，后面可再评估是否把 cleanup blockers 视图或 manager-console message shaping 再切开。
- 下一步：
  1. 优先继续 mailbox/dashboard 收尾时，可把 `build_a0_request_catalog()` 内部的 backlog review request / intervention request 生成拆成更明确 helper，进一步压缩 dashboard/mailbox 消费面残留。
  2. 若 mailbox/dashboard 这条线已够薄，则回头只做真正剩余的大块——`cleanup_status()` 的 blockers/worker-row shaping，而不是再碰 provider/process 边角。
  3. 继续坚持“单阶段、单刀口、定向测试、单 commit”节奏。

- 时间：2026-03-16 09:54 CST
- 当前阶段：转切 backlog 支线，把 `backlog_mixin.py` 里的 mailbox fanout / notification routing 从 manager orchestration 中抽到纯 service，优先缩短 backlog/mailbox 残留尾巴。
- 本阶段代码成果：
  - 新增 `runtime/cp/services/backlog_notifications.py`，沉淀 `task_action_notification()`、`workflow_patch_notifications()`、`mailbox_notification()`，统一承载 task action 的 manager/direct 路由、workflow patch 的 recipient fanout，以及 outbound mailbox payload shaping。
  - `backlog_mixin.py` 的 `perform_task_action()` / `patch_workflow_item()` 改成薄委托：mixin 只保留 backlog 持久化与实际 mailbox append，recipient/topic/scope/body 决策不再内嵌在 manager-side orchestration。
  - 新增 `runtime/test_backlog_notification_service.py`，并更新 `runtime/test_control_plane_architecture.py`、`runtime/cp/services/__init__.py`、`runtime/cp/CODE_INDEX.md`，把 backlog notification service 纳入纯函数测试、架构测试面与索引。
- 已验证：
  - `uv run --no-project --with 'PyYAML>=6.0.2' python3 -m unittest runtime.test_backlog_notification_service runtime.test_workflow_patch_service runtime.test_control_plane_architecture runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_task_actions_drive_plan_and_review_flow runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_workflow_update_allows_a0_replan runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_team_mailbox_send_and_acknowledge_flow` ✅
- 当前断点：
  - backlog 支线里，task/workflow 触发的 mailbox routing 已脱离 `backlog_mixin.py`，但 worker stop / cleanup 这类非 backlog 的 mailbox append 仍在 mixin 侧，暂未统一到同一通知 service。
  - A0 request 生成仍主要由 dashboard/mailbox 汇总层消费 mailbox 状态；如果还要继续收 backlog/mailbox 尾巴，下一刀更可能落在 mailbox catalog / inbox filtering，而不是回到 workflow 状态转换。
- 下一步：
  1. 继续 backlog/mailbox 支线时，优先评估把 `mailbox_mixin.py` 的 A0 inbox / pending 过滤与 catalog shaping 抽成纯 service，进一步收掉 manager-facing mailbox 组装尾巴。
  2. 若 backlog/mailbox 已足够验收，再看是否回头做 provider/process 消费面收口，而不是继续深挖同一支线。
  3. 继续坚持“单阶段、单刀口、定向测试、单 commit”节奏。

- 时间：2026-03-16 09:4x CST
- 当前阶段：沿 provider/process 主线继续收 `process_snapshot` 顶层 launch/runtime metadata，把 `wrapper_path` / `recursion_guard` 一类平铺字段补成更内聚的子 contract + helper，优先收掉 process 视图尾巴。
- 本阶段代码成果：
  - 在 `runtime/cp/contracts.py` 新增 `ProcessLaunchMetadata` 与 `ProcessRuntimeMetadata`，把 `process_snapshot` 的 launch/runtime 元数据固定成明确 typed 子 shape，同时保留既有顶层字段兼容 dashboard/web 消费面。
  - `runtime/cp/services/telemetry_views.py` 新增 `process_launch_metadata()`、`process_runtime_metadata()`，并让 `process_snapshot_entry()` 统一组装嵌套 launch/runtime contract；`state_mixin.py` 继续只做 telemetry 采集与薄委托。
  - 更新 `runtime/test_telemetry_view_service.py`、`runtime/test_control_plane_architecture.py`、`runtime/test_control_plane_integration.py`、`runtime/cp/services/__init__.py`、`runtime/cp/CODE_INDEX.md`，把新子 contract / helper 纳入纯函数测试、架构测试面、定向集成断言与索引。
- 已验证：
  - `uv run --no-project --with 'PyYAML>=6.0.2' python3 -m unittest runtime.test_telemetry_view_service runtime.test_control_plane_architecture runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_session_backed_provider_launches_without_api_key runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_ducc_prompt_file_flag_is_sanitized_for_stale_configs` ✅
- 当前断点：
  - `process_snapshot` 的 launch/runtime metadata 已有内聚子 contract，但 dashboard/web 仍主要消费兼容保留的平铺字段；若要彻底收口，可视情况让前端/下游逐步转读 `launch` / `runtime`。
  - provider/process 主线剩余尾巴已明显变短，接下来更像是补兼容消费面或转切另一条支线，而不是继续大拆。
- 下一步：
  1. 若继续收 provider/process 主线，优先把 dashboard/runtime/web 对 `process_snapshot` 的消费面切到 `launch` / `runtime` 子 shape，顺手评估是否可删除重复平铺字段。
  2. 若主线已足够验收，则转切 `backlog_mixin.py` 的 mailbox fanout / notification routing，清理剩余 manager-side 支线。
  3. 继续坚持“单阶段、单刀口、定向测试、单 commit”节奏。

- 时间：2026-03-16 09:5x CST
- 当前阶段：收尾优先，沿 provider/process 主线把 `provider_auth_status()` 的 session probe / api-key readiness / auth detail shaping 从 `provider_mixin.py` 抽到纯 service，优先减少同主线剩余尾巴。
- 本阶段代码成果：
  - 新增 `runtime/cp/services/provider_auth.py`，沉淀 `configured_api_key()`、`provider_auth_mode()`、`provider_probe_timeout()`、`provider_probe_values()`、`provider_auth_status()`，统一承载 provider auth-mode 归一化、session probe 执行、api-key readiness 判定与 detail shaping。
  - `provider_mixin.py` 的 `configured_api_key()` / `provider_auth_mode()` / `provider_probe_timeout()` / `provider_probe_values()` / `provider_auth_status()` 改成薄委托；mixin 继续保留 wrapper/launch-policy/pool evaluation 编排，但不再内嵌 auth readiness 细节。
  - 新增 `runtime/test_provider_auth_service.py`，并更新 `runtime/test_control_plane_architecture.py`、`runtime/cp/services/__init__.py`、`runtime/cp/CODE_INDEX.md`，把 provider auth service 纳入纯函数测试、架构测试面与索引。
- 已验证：
  - `uv run --no-project --with 'PyYAML>=6.0.2' python3 -m unittest runtime.test_provider_auth_service runtime.test_provider_queue_service runtime.test_control_plane_architecture runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_session_backed_provider_launches_without_api_key runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_session_probe_failure_surfaces_actionable_error runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_ducc_prompt_file_flag_is_sanitized_for_stale_configs` ✅
- 当前断点：
  - provider/process 主线里，`provider_queue` 的 auth shaping 已抽离，但 `process_snapshot` 顶层 launch/runtime metadata（如 `wrapper_path` / `recursion_guard`）仍是平铺 typed 字段，若要彻底收尾可考虑补成更内聚的 launch metadata 子 contract。
  - backlog 的 mailbox fanout / notification routing 仍是另一条未收口支线；不过 provider 主线的 auth 尾巴已经明显缩短。
- 下一步：
  1. 优先评估是否直接把 `process_snapshot` 的 launch/runtime metadata 收成子 contract，完成 provider/process 主线最后一段可验收收口。
  2. 若主线已足够稳定，则转切 `backlog_mixin.py` 的 mailbox fanout / notification routing，清理剩余 manager-side 支线。
  3. 继续坚持“单阶段、单刀口、定向测试、单 commit”节奏。

- 时间：2026-03-16 09:5x CST
- 当前阶段：继续沿 provider/process 主线削薄 `provider_mixin.py`，把 provider queue item 的 score / failure-detail / view-model shaping 下沉到纯 service。
- 本阶段代码成果：
  - 新增 `runtime/cp/services/provider_queue.py`，沉淀 `provider_connection_quality()`、`provider_failure_detail()`、`provider_queue_item()`，统一承载 provider queue 的连接质量、失败详情与最终 typed view-model 组装。
  - `provider_mixin.py` 的 `evaluate_resource_pool()` 改成薄委托：mixin 只保留 binary/auth 探测、stats 读取与 usage 汇总，queue item 评分与字段拼装下沉到 service，`ProviderQueueItem` contract 保持不变。
  - 新增 `runtime/test_provider_queue_service.py`，并更新 `runtime/test_control_plane_architecture.py`、`runtime/cp/services/__init__.py`、`runtime/cp/CODE_INDEX.md`，把 provider queue service 纳入纯函数测试、架构测试面与索引。
- 已验证：
  - `uv run --no-project --with 'PyYAML>=6.0.2' python3 -m unittest runtime.test_provider_queue_service runtime.test_telemetry_view_service runtime.test_control_plane_architecture runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_session_backed_provider_launches_without_api_key runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_ducc_prompt_file_flag_is_sanitized_for_stale_configs runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_session_probe_failure_surfaces_actionable_error` ✅
- 当前断点：
  - provider/process 这条线里，`provider_auth_status()` 本身的 session/api-key readiness 分支仍留在 `provider_mixin.py`；若继续同主线，下一刀可把 auth readiness/result contract 也抽成独立纯 service。
  - `process_snapshot` 顶层 launch/runtime metadata 仍是平铺 typed 字段；若想继续内聚，也可把 launch metadata 再拆成更细子 contract。
- 下一步：
  1. 继续沿 provider/process 主线，把 provider auth/session probe result shaping 抽成纯 service，进一步削薄 `provider_mixin.py`。
  2. 或在 process/provider 共线补 launch metadata 子 contract，收掉 `wrapper_path` / `recursion_guard` 一类平铺字段。
  3. 继续坚持“单阶段、单刀口、定向测试、单 commit”节奏。

- 时间：2026-03-16 09:4x CST
- 当前阶段：沿 provider/process 主线把 telemetry normalization 从 `state_mixin.py` 抽到纯 service，继续削薄 mixin 内的 view-model shaping。
- 本阶段代码成果：
  - 新增 `runtime/cp/services/telemetry_views.py`，沉淀 `normalize_usage()`、`command_contract()`、`running_agent_telemetry()`、`summarize_pool_usage()`、`process_snapshot_entry()`，统一承载 usage / command / running-agent / process snapshot 的纯 shaping 逻辑。
  - `state_mixin.py` 的 `pool_usage_summary()` 与 `process_snapshot()` 改成薄委托：mixin 只负责遍历进程与读取 telemetry，具体 view-model 归一化下沉到 service，typed contract 保持不变。
  - 更新 `runtime/cp/services/__init__.py`、`runtime/cp/CODE_INDEX.md`、`runtime/test_control_plane_architecture.py`，并新增 `runtime/test_telemetry_view_service.py`，把 telemetry view service 纳入索引、架构测试面与纯函数单测。
- 已验证：
  - `uv run --no-project --with 'PyYAML>=6.0.2' python -m unittest runtime.test_telemetry_view_service runtime.test_control_plane_architecture runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_session_backed_provider_launches_without_api_key runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_ducc_prompt_file_flag_is_sanitized_for_stale_configs` ✅
- 当前断点：
  - `evaluate_resource_pool()` 里 provider queue 的 provider/auth/score/failure detail shaping 仍在 `provider_mixin.py`，若继续同主线，下一刀可把 provider queue item assembler 也下沉成纯 service。
  - `process_snapshot` 顶层的 launch/runtime metadata（如 `wrapper_path`、`recursion_guard`）虽然已稳定 typed，但仍是平铺字段；后续若要继续细化，可再拆 launch metadata 子 contract。
- 下一步：
  1. 继续沿 provider/process 主线，把 `evaluate_resource_pool()` 返回的 provider queue item shaping 抽到纯 service，进一步削薄 `provider_mixin.py`。
  2. 或在同一主线补 process/provider 共用 launch metadata 子 contract，把 `wrapper_path` / `recursion_guard` 等字段再收成更细 typed shape。
  3. 继续坚持“单阶段、单刀口、定向测试、单 commit”节奏。

- 时间：2026-03-16 09:3x CST
- 当前阶段：继续沿 dashboard provider/process 子视图往内收，把 queue/snapshot 内层 telemetry、usage、command shape 收成明确 typed contract。
- 本阶段代码成果：
  - 在 `runtime/cp/contracts.py` 新增 `TelemetryUsage`、`ProcessCommand`、`RunningAgentTelemetry`、`PoolUsageSummary`，把 `provider_queue.running_agents` / `provider_queue.usage` / `process_snapshot.usage` / `process_snapshot.command` 从松散嵌套 dict/list 收成明确 contract。
  - `state_mixin.py` 新增 usage/command 归一化 helper；`pool_usage_summary()` 改为返回 `PoolUsageSummary`，每个 running agent 现在携带完整 typed usage；`process_snapshot()` 也改为输出 typed command/usage，provider/process 两条 dashboard telemetry 视图共用一致 shape。
  - 更新 `runtime/test_control_plane_architecture.py`、`runtime/test_control_plane_integration.py` 与 `runtime/cp/CODE_INDEX.md`，把新内层 contracts 纳入架构测试面，并回归 wrapper command / usage 聚合的 dashboard 集成断言。
- 已验证：
  - `uv run --no-project --with 'PyYAML>=6.0.2' python3 -m unittest runtime.test_control_plane_architecture runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_session_backed_provider_launches_without_api_key runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_ducc_prompt_file_flag_is_sanitized_for_stale_configs` ✅
- 当前断点：
  - provider/process 这条线的核心内层 telemetry 已 typed 化，但 `evaluate_resource_pool()` / `process_snapshot()` 里的 telemetry shaping 还留在 mixin 内；若下一阶段继续同主线，可把 usage/command/running-agent 归一化继续下沉成纯 helper/service，进一步削薄 mixin。
  - `process_snapshot` 顶层仍保留 `wrapper_path` 与 `recursion_guard` 等平铺字段；若后续继续深挖，也可以考虑把 process launch/runtime metadata 再拆成更细 contract。
- 下一步：
  1. 继续沿 provider/process 主线，把 telemetry normalization（usage / command / running-agent shaping）抽成纯 service 或独立 helper 模块，减少 `state_mixin.py` 继续堆 view-model 细节。
  2. 或在这条线再补一刀，把 process/provider 共用的 launch metadata 也 typed 化成更细子 contract。
  3. 继续坚持“单阶段、单刀口、定向测试、单 commit”节奏。

- 时间：2026-03-16 08:5x CST
- 当前阶段：已把 dashboard 下钻子视图中最顺手的一刀收成明确 typed contract，provider/process/cleanup/launch-policy 这组返回面不再继续裸奔。
- 本阶段代码成果：
  - 在 `runtime/cp/contracts.py` 新增 `LaunchPolicyState`，并把 `DashboardState.launch_policy` 从 `dict[str, Any]` 收紧为明确 contract；同时把既有的 `ProcessSnapshot` / `ProviderQueueItem` / `CleanupState` 真正接到对应子视图返回面。
  - `provider_mixin.py` 的 `evaluate_resource_pool()` / `provider_queue()` / `launch_policy_state()` 全部改为返回 typed contract，让 dashboard 的 provider queue 与 launch policy 子视图直接暴露稳定 shape，而不是继续用松散 dict。
  - `state_mixin.py` 的 `process_snapshot()` 改成返回 `dict[str, ProcessSnapshot]`；`mailbox_mixin.py` 的 `cleanup_status()` 改成返回 `CleanupState`，并把 worker rows 明确成 `CleanupWorkerState` 列表，dashboard 的 process/cleanup 子视图正式接上 contracts。
  - 更新 `runtime/test_control_plane_architecture.py` 与 `runtime/cp/CODE_INDEX.md`，把 `LaunchPolicyState`、`ProcessSnapshot`、`ProviderQueueItem`、`CleanupWorkerState` 这些子视图 contract 纳入架构测试面与索引。
- 已验证：
  - `uv run --no-project --with 'PyYAML>=6.0.2' python -m unittest runtime.test_control_plane_architecture runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_session_backed_provider_launches_without_api_key runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_session_probe_failure_surfaces_actionable_error runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_initial_launch_provider_falls_back_to_configured_ducc runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_ducc_prompt_file_flag_is_sanitized_for_stale_configs` ✅
- 当前断点：
  - dashboard 四个候选子视图里，这一刀已经把 `launch_policy_state()`、`provider_queue()`、`process_snapshot()`、`cleanup_status()` 的返回 contract 接上了，但字段内部仍有少量嵌套 `dict[str, Any]`（例如 `running_agents` / `usage` / command telemetry），如果下一阶段继续收紧，可以进一步把这些内层 payload 也拆成更细 typed shape。
  - `backlog_mixin.py` 的 mailbox fanout / notification routing service 仍是另一条自然支线；但若继续优先 dashboard，这时可以顺手补 provider/process/cleanup 子视图相关纯 helper 或更细粒度 contract，而不是回头做顶层 assembler。
- 下一步：
  1. 继续沿 dashboard 子视图往内收：优先把 `provider_queue` / `process_snapshot` 内层 usage、running-agent、command telemetry 再细分成 typed contract。
  2. 或在确认 dashboard 再往内一刀性价比下降后，切到 `backlog_mixin.py`，抽 mailbox fanout / notification routing service。
  3. 继续坚持“单阶段、单刀口、定向测试、单 commit”节奏。

- 时间：2026-03-16 03:3x CST
- 当前阶段：已把 dashboard/runtime assembler 的顶层视图 contract typed 化，dashboard 现在不只 service 层 typed，连 assembler 返回面也开始有统一 shape。
- 本阶段代码成果：
  - 在 `runtime/cp/contracts.py` 新增 `GateState`、`ManagerControlState`、`WorkerHandoffSummary`、`CommandMap`、`DashboardMode`、`DashboardState`，把 dashboard 顶层 payload、manager control 摘要、worker handoff 摘要、CLI command/mode 这些 manager-facing assembler shape 固定下来。
  - `dashboard_mixin.py` 的 `build_dashboard_state()`、`build_cli_commands()`、`manager_runtime_entry()`、`dashboard_runtime_state()`、`compute_manager_control_state()`、`manager_heartbeat_entry()`、`dashboard_heartbeats_state()`、`worker_handoff_summary()` 全部改成返回明确 typed contract，runtime/heartbeat/dashboard assembler 链路不再只靠裸 `dict[str, Any]` 串起来。
  - `services/dashboard_summary.py`、`services/dashboard_queue.py` 也同步接到 `ManagerControlState` / `WorkerHandoffSummary`，让 dashboard summary/queue service 与 assembler 共用同一套 typed view model。
  - 更新 `runtime/test_control_plane_architecture.py` 与 `runtime/cp/CODE_INDEX.md`，把新增 dashboard assembler contracts 纳入架构测试面与索引。
- 已验证：
  - `uv run --no-project --with 'PyYAML>=6.0.2' python -m unittest runtime.test_control_plane_architecture runtime.test_dashboard_service runtime.test_dashboard_queue_service runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_dashboard_exposes_manager_identity_and_handoff_details runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_a0_console_records_user_reply runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_team_mailbox_send_and_acknowledge_flow` ✅
- 当前断点：
  - dashboard 顶层 assembler 已有 typed contract，但 `launch_policy_state()`、`process_snapshot()`、`cleanup_status()`、`provider_queue()` 等子视图内部仍有较多松散 `dict[str, Any]`，后续若继续推进 typed 化，可沿 dashboard 入口继续往这些子域下钻。
  - `backlog_mixin.py` 的 mailbox fanout / notification routing 仍是另一条自然支线，若下一阶段转切 service 抽离，这块仍然是最顺手的薄化点。
- 下一步：
  1. 继续把 dashboard 子视图（尤其 launch policy / process snapshot / cleanup / provider queue）收成 typed contract。
  2. 或切去 `backlog_mixin.py`，抽 mailbox fanout / notification routing service，进一步削薄 manager-side orchestration。
  3. 继续坚持“一个阶段一个 checkpoint + 定向测试 + 单独 commit”节奏。

- 时间：2026-03-16 03:0x CST
- 当前阶段：已把 workflow/dashboard/mailbox 这条 manager-facing payload 链路收紧到 typed contract，contracts 不再只停留在 service 签名，开始接到 store / mixin / architecture test。
- 本阶段代码成果：
  - 在 `runtime/cp/contracts.py` 补齐并接线 `WorkflowPatch`、`TeamMailboxMessage`、`A0ConsoleRequest`、`A0ConsoleMessage`、`A0ConsoleState`、`ManagerConsoleState`，让 workflow patch、manager console、team mailbox 都有明确 shape。
  - `backlog_mixin.py`、`dashboard_mixin.py`、`mailbox_mixin.py`、`state_mixin.py`、`services/dashboard_queue.py`、`services/workflow_patch.py` 全面改成 typed return / typed input，manager-facing queue/request/mailbox 链路不再继续传播裸 `dict[str, Any]`。
  - `stores/manager_console_store.py` 增加 request/message 归一化过滤，持久化前主动丢弃脏 key / 非 dict message；`stores/mailbox_store.py` 也对 mailbox message 使用统一 typed contract。
  - 更新 `runtime/cp/CODE_INDEX.md` 与 `runtime/test_control_plane_architecture.py`，把新增 contracts 和 manager-console normalization 行为纳入索引与架构测试面。
- 已验证：
  - `uv run --no-project --with 'PyYAML>=6.0.2' python -m unittest runtime.test_control_plane_architecture runtime.test_dashboard_queue_service runtime.test_workflow_patch_service runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_task_actions_drive_plan_and_review_flow runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_a0_console_records_user_reply runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_team_mailbox_send_and_acknowledge_flow` ✅
- 当前断点：
  - dashboard / mailbox / workflow patch 的 payload shape 已收紧，但 `merge_queue()` / `build_dashboard_state()` / 其他 dashboard assembler 仍有不少 `dict[str, Any]` 入口，后续若继续压字段漂移，可以把 runtime/dashboard 聚合视图整体升级成 typed state。
  - backlog mailbox fanout 的 recipient/topic 决策仍留在 `backlog_mixin.py`，如果下一刀继续做 service 化，这块很适合抽成纯 notification payload service。
- 下一步：
  1. 继续往 dashboard runtime/state assembler 推 typed contract，把 manager-facing API/view model 再收一层。
  2. 或回到 `backlog_mixin.py`，把 mailbox fanout / notification routing 抽成纯 service，进一步削薄 manager-side orchestration。
  3. 继续坚持“一个阶段一个 checkpoint + 定向测试 + 单独 commit”节奏。

- 时间：2026-03-16 02:1x CST
- 当前阶段：已把 `backlog_mixin.py` 中 task action / workflow patch 的核心状态转换抽到纯 service，manager-side backlog 状态机开始脱离 mixin。
- 本阶段代码成果：
  - 新增 `runtime/cp/services/workflow_patch.py`，沉淀 `apply_task_action()`、`apply_workflow_patch()`、`validate_workflow_updates()`、`summarize_workflow_patch()`，统一承载 claim/start/plan/review/complete/reopen 与 workflow patch 的纯状态转换。
  - `backlog_mixin.py` 的 `perform_task_action()` / `patch_workflow_item()` / `summarize_workflow_patch()` 改成薄委托：mixin 只保留 backlog 持久化、mailbox fanout 与 manager-owned orchestration。
  - 新增 `runtime/test_workflow_patch_service.py`，覆盖 task action 状态流转、plan-approval completion guard、workflow patch list/timestamp shaping、非法字段校验与 patch summary。
  - 更新 `runtime/cp/services/__init__.py` 与 `runtime/cp/CODE_INDEX.md`，把 workflow patch service 纳入统一 service 层出口与索引。
- 已验证：
  - `uv run --no-project --with 'PyYAML>=6.0.2' python -m unittest runtime.test_workflow_patch_service runtime.test_control_plane_architecture runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_task_actions_drive_plan_and_review_flow runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_workflow_update_allows_a0_replan` ✅
- 当前断点：
  - backlog 的纯状态转换已抽离，但 mailbox recipient/topic 决策仍在 `backlog_mixin.py`；若继续收口，下一刀可以把 manager notification fanout 也提成 service payload。
  - workflow/task action 现在仍返回松散 dict；若想继续压字段漂移风险，可以在 `contracts.py` 里补 task action / workflow patch 相关 typed payload。
- 下一步：
  1. 评估是否继续把 backlog mailbox fanout / notification payload 也抽成纯 service。
  2. 或补 `contracts.py` typed contract，把 workflow/task action 的 service I/O 收紧。
  3. 继续坚持“小块 service 抽离 + 定向 integration 回归 + checkpoint commit”，不回到大颗粒长跑。

---

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

---

- 时间：2026-03-16 01:58 CST
- 当前阶段：已把 dashboard 的 merge queue / A0 console request 聚合从 `dashboard_mixin.py` 抽到纯 service，manager-facing queue 规则开始脱离 mixin。
- 本阶段代码成果：
  - 新增 `runtime/cp/services/dashboard_queue.py`，沉淀 `build_merge_queue()`、`manager_inbox()`、`build_a0_request_catalog()`，统一承载 merge queue 行拼装、A0 inbox 过滤、plan/task review request 生成、worker intervention request 归并与排序。
  - `dashboard_mixin.py` 的 `merge_queue()` / `a0_request_catalog()` 改成薄委托：mixin 只负责采集 runtime / heartbeat / backlog / mailbox / manager_console 状态，并把 handoff 摘要与持久化 response state 交给 service 消费。
  - 新增 `runtime/test_dashboard_queue_service.py`，覆盖 manager-facing merge queue 行 shaping、A0 request 排序、plan/task review 与 intervention/unlock 标题规则、inbox 过滤与 pending count 计算。
  - 更新 `runtime/cp/services/__init__.py` 与 `runtime/cp/CODE_INDEX.md`，把 dashboard queue service 纳入统一出口与索引。
- 已验证：
  - `uv run --no-project --with 'PyYAML>=6.0.2' python -m unittest runtime.test_control_plane_architecture runtime.test_dashboard_service runtime.test_dashboard_queue_service runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_dashboard_exposes_manager_identity_and_handoff_details runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_a0_console_records_user_reply runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_process_exit_surfaces_escalation_in_attention_summary runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_task_actions_drive_plan_and_review_flow runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_team_mailbox_send_and_acknowledge_flow` ✅
- 当前断点：
  - `dashboard_mixin.py` 的 queue / request 聚合已抽离，但 handoff / merge queue / A0 console payload 仍是松散 dict；若继续收紧，下一刀适合补 `contracts.py` 的 dashboard queue / request typed shape。
  - `backlog_mixin.py` 里 workflow patch / task action 规则仍偏重，manager-side 状态机还没沉到纯 service。
- 下一步：
  1. 评估是否把 dashboard queue / request payload 升级成 typed contracts，顺手压缩 web/api 两侧的字段漂移风险。
  2. 或转切 `backlog_mixin.py`，把 workflow patch / task action / review 状态转换抽到纯 service，继续削薄 manager-side mixin。
  3. 继续坚持“小块 service 抽离 + 定向 integration 回归 + checkpoint commit”，避免回到大颗粒长跑。

---

- 时间：2026-03-16 01:5x CST
- 当前阶段：已把 dashboard 的 manager-control 分类与 worker handoff 摘要从 `dashboard_mixin.py` 抽到纯 service，继续把 mixin 压回 IO/编排层。
- 本阶段代码成果：
  - 新增 `runtime/cp/services/dashboard_summary.py`，沉淀 `compute_manager_control_state()` 与 `summarize_worker_handoff()` 两块 dashboard 核心决策逻辑。
  - `dashboard_mixin.py` 对上述逻辑改为薄委托：mixin 只负责读取 runtime/heartbeat/backlog 与 status/checkpoint markdown，再把纯数据交给 service 判定。
  - 新增 `runtime/test_dashboard_service.py`，覆盖 agent 分类（active / runnable / attention / blocked）与 handoff attention summary 优先级、去重、resume/next-checkin 组装。
  - 更新 `runtime/cp/services/__init__.py` 与 `runtime/cp/CODE_INDEX.md`，把 dashboard service 纳入统一 service 层出口与索引。
- 已验证：
  - `uv run --no-project --with 'PyYAML>=6.0.2' python -m unittest runtime.test_control_plane_architecture runtime.test_task_routing_service runtime.test_pool_selection_service runtime.test_dashboard_service` ✅
  - `uv run --no-project --with 'PyYAML>=6.0.2' python -m unittest runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_dashboard_exposes_manager_identity_and_handoff_details runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_a0_console_records_user_reply runtime.test_control_plane_integration.ControlPlaneIntegrationTest.test_process_exit_surfaces_escalation_in_attention_summary` ✅
- 当前断点：
  - `dashboard_mixin.py` 里 `merge_queue()` / `a0_request_catalog()` 仍有较重的 manager-console 聚合与 request 归并规则，尚未抽成纯 service。
  - handoff / control state 现在已独立，但返回值仍是松散 dict；下一刀若要继续收紧，可以补 `contracts.py` 中的 dashboard typed payload。
- 下一步：
  1. 优先把 `merge_queue` / `a0_request_catalog` 的 request 生成与排序规则抽成 dashboard service，进一步缩小 mixin。
  2. 或者转切 `backlog_mixin.py` 的 workflow patch / task action 规则，把 manager-side 状态机也压进纯 service。
  3. 继续坚持“小块 service 抽离 + 定向 integration 回归 + checkpoint commit”节奏，不回到全量长跑。
