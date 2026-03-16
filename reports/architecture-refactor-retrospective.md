# Architecture Refactor Retrospective

> 面向未来维护者/下一次类似重构的复用文档。重点不是流水账，而是这一轮为什么能收口、靠什么保证可验收、哪些方法值得继续沿用。

## 1. 本轮重构的目标与完成范围

### 原始目标

本轮 architecture refactor 的核心目标，不是“把旧系统拆得更好看”，而是把 control-plane 从**mixin 内联规则堆积**推进到更清晰的三层：

- `contracts.py`：typed contract，固定 manager-facing / runtime-facing payload shape
- `services/`：纯函数域逻辑，承载选择、整形、汇总、状态转换
- `stores/`：持久化与容错归一化
- mixins：尽量压回 IO / orchestration / state access

### 已完成范围

这一轮已经完成的主线，可按“验收通过”看待：

1. **routing / pool selection**
   - 任务策略、任务画像、provider/pool 选择规则已 service 化。
2. **dashboard / manager-facing views**
   - summary、merge queue、A0 request catalog、mailbox catalog、cleanup status 已收成可测试 service。
3. **workflow / backlog / notifications**
   - task action、workflow patch、mailbox notification routing 已脱离 mixin 内联大分支。
4. **provider / process telemetry & auth**
   - auth readiness、provider queue shaping、process snapshot metadata、telemetry usage/command shape 已 typed + service 化。
5. **contracts / stores / architecture tests**
   - manager/provider/process/backlog/mailbox 关键 payload 已统一到 contracts；stores 和 architecture tests 已围绕新结构建立防线。

### 明确不在本轮范围内的事

- 不追求兼容所有旧隐式行为
- 不重开 gateway/web 消费面的大改
- 不把尾声阶段又拉回“顺手重构更多模块”的扩散模式

收官标准不是“理论上还能更优雅”，而是：**主干职责已经清晰、关键 payload 已 typed、核心行为有定向测试兜底、剩余问题属于非阻塞优化。**

## 2. 为什么坚持“一个阶段一个 session、一个 commit、checkpoint”

这条纪律不是形式主义，而是这轮重构能够稳定推进的关键。

### 它解决了什么问题

1. **避免长跑失控**
   - control-plane 这种代码一旦连续改两三个方向，很容易把上下文、回归面、提交语义全部搅混。
2. **把风险锁在局部**
   - 每阶段只允许一刀，失败时更容易回退、定位、补测试。
3. **让 checkpoint 真正可恢复**
   - session 中断、上下文压缩、切换模型/窗口时，新的接手者能直接从 progress 文档和 commit 继续，而不是重新猜现场。
4. **让 commit 有语义密度**
   - 一条 commit 对应一个明确的“抽离/typed/索引/测试闭环”，后续 review 或回溯都更轻。

### 什么时候 checkpoint 最有价值

- 已经形成一个可描述的刀口
- 定向测试已绿
- 再继续做会跨到第二个主题
- 上下文开始发热、输出变慢、注意力开始分散

结论：**checkpoint 不只是备份，它是阶段边界。** 没有边界，重构很快就会从工程推进退化成持续搅动。

## 3. 如何选择下一刀：局部最优 vs 全局收尾

本轮实践下来，选择下一刀时最有效的判断标准不是“哪块最脏”，而是以下三条：

### 3.1 优先选“已存在自然边界”的地方

比如：

- scoring / ranking / shaping
- payload normalization
- request builder / view assembler
- workflow state transition

这些逻辑天然适合做纯函数 service，改完后容易单测，也不容易牵一发动全身。

### 3.2 优先选“已有测试锚点”的地方

如果某块已有 integration 覆盖，或者已有 contract 只差半步接线，那么它往往比“理论上更重要但完全没测试锚”的点更值得先做。

**经验：收官阶段选可验证的局部最优，通常比追求抽象上的全局最优更稳。**

### 3.3 当主线已经收官时，要切换目标函数

收尾阶段不再追求“大块架构推进”，而应改成：

- 对齐索引/导出面/注释/文档
- 清理小范围重复和命名噪音
- 把经验写下来，降低下一次重构成本

也就是说：

- 主线阶段问的是：**哪一刀最能降低结构复杂度？**
- 收尾阶段问的是：**哪一刀最能提高可维护性且不重新打开架构战线？**

## 4. 何时先 typed contract，何时先 service 抽离

这轮最值得复用的判断不是固定顺序，而是按场景选入口。

## 4.1 先做 typed contract 的信号

当出现以下情况时，优先做 contract：

- 同一个 payload 被多个 mixin / service / store / dashboard 消费
- 字段已经稳定，但仍在用松散 `dict[str, Any]`
- integration 失败经常来自字段漂移、脏 key、默认值不一致
- 希望 architecture test 有明确“守什么”的对象

典型收益：

- 把“系统真正暴露什么 shape”固定下来
- 让 store normalization、service return、dashboard assembler 对齐到同一份真相
- 后续重构时减少猜字段和补兼容的成本

## 4.2 先做 service 抽离的信号

当出现以下情况时，优先抽 service：

- mixin 同时承载 IO + 判断 + 汇总 +整形
- 某块逻辑本质是纯规则/纯转换
- 同一规则在两个地方重复或潜在分叉
- 目标是先把“大函数”压薄，而不是先统一 shape

典型收益：

- 先把“规则”从 orchestration 中剥离出来
- 先拿到纯函数单测能力
- 后续再补 typed contract 时，改动面会更小

## 4.3 实用判断法

可以直接用下面这条：

- **字段漂移是主要风险** → 先 contract
- **条件分支/规则堆积是主要风险** → 先 service
- **两者都重** → 先抽最纯的 service，再用 contract 收口其输入/输出

这轮中最稳的路径往往是：

**service 抽离拿到纯测试面 → contract 收紧边界 → store / mixin / architecture test 一起接线。**

## 5. 测试与验收策略

本轮有效的不是“全量狂跑”，而是分层验收。

### 5.1 三层测试面

1. **纯函数单测**
   - 验证 service 的规则、排序、整形、状态转换。
2. **architecture test**
   - 验证 contracts/stores/service 出口是否仍在、typed shape 是否仍接上线。
3. **定向 integration**
   - 只回归被当前刀口真正触达的链路，例如 mailbox、dashboard、provider auth、workflow patch。

### 5.2 为什么不优先全量回归

因为全量回归：

- 慢
- 容易把定位信息淹没
- 在单阶段提交纪律下，性价比不高

更有效的做法是：

- 先跑当前改动直接相关的单测
- 再跑 architecture test
- 最后补 2~6 条高相关 integration 用例

### 5.3 验收标准

一个阶段可以提交，至少满足：

- 改动点有单一主题
- 新旧职责边界更清晰，而不是只是挪代码
- CODE_INDEX / progress 文档与真实结构一致
- 定向测试全绿
- commit message 能准确概括这刀做了什么

## 6. 哪些做法证明有效

### 有效做法 1：先抽纯整形/决策，再保留 mixin 薄委托

这能把风险压到最低。mixin 继续负责 state access / runtime IO，不强行一次性推倒重来。

### 有效做法 2：同一主题内把“代码 + 测试 + 索引”一起提交

只改代码不补测试，后续很难守住；只改代码不刷索引，维护者会重新迷路。

### 有效做法 3：收尾阶段接受“兼容保留层”存在

比如新增嵌套 contract/helper，但暂时保留平铺字段给下游消费。这样能在不扩散到 web/gateway 的前提下收掉核心结构问题。

### 有效做法 4：让 progress 文档持续记录“当前断点 + 下一步”

这极大降低了 session 切换成本，也是多阶段推进不失控的基础设施。

### 有效做法 5：把重构目标从“多做一点”改成“再收一块可验证边界”

这条特别重要。真正让项目收官的，不是更激进，而是更克制。

## 7. 哪些坑需要避免

### 坑 1：在一个阶段里同时追两个方向

比如一边抽 service，一边顺手改 dashboard/web 消费面。这样最容易把提交语义打散，也最容易让回归面失控。

### 坑 2：把“结构改进”误做成“字段微调堆积”

如果一阶段只是改几个 key 名字、挪几条文案，但没有实质边界改善，那通常不值得单独开一刀。

### 坑 3：已经接近收尾时，还执着于彻底纯化所有下游

收尾阶段应该优先确保主干已经清晰可守，而不是为了完美把所有消费面一起重写。

### 坑 4：没有同步更新 CODE_INDEX / progress / tests

这样下一位维护者需要重新 reverse engineer 结构，等于把本轮重构成果又埋回去了。

### 坑 5：一次性全量回归、失败后再回头猜

正确顺序应该是：

- 先明确当前刀口
- 再跑定向验证
- 若失败，直接围绕这刀修

不是先把所有测试都打一遍，再在噪音里找问题。

## 8. 对未来继续演进的建议（非阻塞优化）

以下建议都不是当前阻塞项，只适合后续单独开阶段处理：

1. **继续减少剩余 mixin 中的松散 dict 输入/输出**
   - 尤其是 provider/config/routing 边界处，未来仍可逐步 contract 化。
2. **按需要继续细分 dashboard_queue 等“已可验收但仍稍厚”的模块**
   - 前提是有明确新边界，不要为了拆而拆。
3. **视下游消费情况，逐步切到新嵌套 contract**
   - 例如 process snapshot 的 `launch` / `runtime` 子 shape，可等下游自然迁移时再收旧平铺字段。
4. **保留 architecture test 作为“结构哨兵”持续扩充**
   - 未来每新增一个关键 contract/service，都应补最小守卫。
5. **继续维护 progress/retrospective 文档，而不是让经验只留在 commit 历史里**

## 9. 可直接复用的阶段执行模板

### 开工前

- 看 `git status`
- 看最近 10~12 条 commit
- 看 progress 文档和 CODE_INDEX
- 只选一个刀口

### 动手时

- 优先抽纯函数/service 或补 contract
- 不碰无关支线
- 同步补单测/架构测试
- 索引和文档一起更新

### 提交前

- 跑定向测试
- 确认改动主题单一
- 写清本阶段断点/完成范围
- 一个 commit 收口

## 10. 这轮最核心的结论

1. **重构要靠阶段纪律收口，不靠意志力硬顶。**
2. **收尾阶段优先可验证、可提交、可交接的局部最优。**
3. **typed contract 解决字段真相问题，service 抽离解决规则堆积问题；谁先做取决于当前主要风险。**
4. **“代码 + 测试 + 索引 + progress 文档”四件套一起落地，重构成果才不会回流成隐性知识。**
5. **当主线已完成，最有价值的工作往往不是继续拆，而是 polish + 经验沉淀。**
