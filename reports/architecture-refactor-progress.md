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
