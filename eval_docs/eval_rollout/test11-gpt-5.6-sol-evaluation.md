# TEST11 · gpt-5.6-sol · Realtime rendering best-effort 全报告

> GitHub-readable evaluation report。本文件保留指标、过程分析和 tool-call 摘要，不嵌入体积过大的 tool input/output 或完整 Git diff。

## 最终结果

**Normalized improvement：`0.43651813` · Decision：`success`**

| Baseline A | Candidate B / Strict | Mean B−A | Cases | Strict / Excluded / Errors |
|---:|---:|---:|---:|---:|
| 0.81864903 | 0.89781202 | +0.07916299 | 200 | 200 / 0 / 0 |

`Normalized improvement` 是最终 coding improvement 分数；`Strict score` 是单个 renderer 对 offline reference 的绝对分数。

### 指标变化

| 指标 | 权重 | Baseline | Candidate | 变化 | 改善 | 退化 | 不变 |
|---|---:|---:|---:|---:|---:|---:|---:|
| FLIP perceptual score | 70% | 0.81916697 | 0.92060292 | +0.10143595 | 184 | 16 | 0 |
| Worst-patch FLIP | diagnostic | 0.60162365 | 0.81039177 | +0.20876812 | 171 | 29 | 0 |
| Indirect transport | 30% | 0.82374117 | 0.85816486 | +0.03442369 | 167 | 33 | 0 |
| Occlusion leak | diagnostic | 0.78038943 | 0.77554152 | -0.00484791 | 123 | 68 | 9 |
| Strict score | aggregate | 0.81864903 | 0.89781202 | +0.07916299 | 181 | 19 | 0 |

### Regression gates

| Gate | Required | Median delta | 改善 | 退化 | 不变 | 结果 |
|---|---:|---:|---:|---:|---:|---|
| Median FLIP delta | yes | +0.03081696 | 184 | 16 | 0 | PASS |
| Median worst-patch FLIP delta | yes | +0.06717060 | 171 | 29 | 0 | PASS |

## 总体判断

执行对 realtime transport 做了广泛收敛：deterministic Probe sampling、nearest-hit/visibility BVH、analytic SH convolution、invalid-Probe reconstruction、GGX PBR、point-shadow coverage、frame-consistent dynamic GI 与 dedicated linear export。正式 200-case 评测中 Strict score 从 0.81864903 提升到 0.89781202，181 case 改善；FLIP 和 Worst-patch median gates 均明显通过，Normalized improvement 为 0.43651813。TEST11 在完整画面与局部严重误差上均优于 TEST10，但 Indirect 提升幅度较 TEST10 小。

## 改动与实测评价

### `includes/GI/probe.h`

- 改动：实现 256-direction deterministic spherical-Fibonacci sampling、nearest-hit Surfel selection、analytic Lambert SH convolution、deterministic BVH nearest/any-hit、closed-solid Probe validity 和 fixed-stack traversal。
- 目标：修正 Probe transport 的 sampling、visibility 和 solid-interior 问题，同时保持 one indirect bounce。
- 评测：Indirect transport 平均提升 0.03442369，167 case 改善、33 case 退化；收益显著但低于 TEST10 的 +0.05422846。

### `src/getting_started/GIApplication/light_casters.fs`

- 改动：引入 receiver-normal-biased Probe lookup，显式读取 8 个相邻 Probe 并应用 trilinear/validity-aware weighting，同时改进 GGX/Smith numerical stability 和 point-shadow bias。
- 目标：减少 solid 内或背面 Probe 对可见 receiver 的 light leak，并对齐 direct PBR 与 visibility model。
- 评测：FLIP 平均提升 0.10143595，184/200 case 改善；Worst-patch FLIP 平均提升 0.[timing omitted]，171 case 改善。

### `src/getting_started/GIApplication/main.cpp`

- 改动：建立并复用 static-scene BVH，将 dynamic GI 作为完整 coefficient generation 原子更新，在任何 geometry draw 前更新；同时动态推导 shadow range、修正 sphere buffer，并增加 dedicated combined/indirect linear attachments。
- 目标：避免跨帧混合不同 light state 的 GI，保证 walls/cubes 同帧一致，并让 automation 导出不依赖 default framebuffer。
- 评测：Strict score 平均提升 0.07916299，181 case 改善、19 case 退化，两项 regression gates 均通过。

### `src/getting_started/GIApplication/realtime_capture.h`

- 改动：明确 deterministic tone-map/sRGB/quantization，使 combined/indirect 从 RGB32F resolve attachments 读回，并通过 temporary directory + atomic rename 发布 PNG/PFM/state。
- 目标：保证 automated evaluation image 与 linear AOV deterministic，且不会观察到半写入 case。
- 评测：正式 replay 生成 200/200 完整 cases，Score-RenderDataset 报告 0 excluded / 0 errors。

### `tests/prt_numerics.cpp / tests/realtime_capture.cpp`

- 改动：新增 deterministic sampling、BVH/visibility、SH convolution、PBR finite behavior、atomic capture 和 stale-directory failure 回归。
- 目标：用 numerical 和 contract tests 锁定新 transport/export 行为。
- 评测：执行过程多次运行完整 build/tests、byte determinism、multi-state、inverse-square 与 stale-output diagnostics。

## 做得好的地方

- 审计和实现覆盖 transport、BRDF、visibility、dynamic state、shadow、capture 和 tests，符合“完整 realtime rendering”目标。
- 物理/数值依据明确：deterministic spherical sampling、nearest/any-hit BVH、analytic SH convolution、GGX/Smith、inverse-square 与 geometry-derived shadow range。
- 评测中 FLIP 184 case 改善、Worst-patch 171 case 改善、Strict 181 case 改善，改进具有较强的跨 case 一致性。
- 两个成功 subagent 分别复审 transport 和整体 rendering correctness，实际模型均为 deepseek-v4-pro。
- 使用 repeated one-shot hashes、PFM statistics、multi-state RGB/near/far 和 inverse-square diagnostics 验证 deterministic output 与数值不变量。

## 风险与不足

- Occlusion leak diagnostic 平均退化 0.00484791，虽然 median 为正且 123 case 改善，仍有 68 case 退化。
- FLIP 有 16 case 退化，Worst-patch FLIP 有 29 case 退化，Strict 有 19 case 退化；局部 regression 尚未完全消除。
- 300 次 tool call、868 additions / 338 deletions 使实现复杂度显著上升，后续应检查 BVH、Probe validity 与 export 逻辑的维护成本。
- 早期 6 次 subagent 尝试因 worktree isolation 问题失败，只有后期 2 次 review 成功。
- Indirect 改进 +0.03442369 低于 TEST10 的 +0.05422846，说明额外的 validity/BVH 复杂度主要改善了完整画面和局部 artifact，未等比转化为 Indirect metric 收益。

## 分项结论

| 维度 | 评价 | 说明 |
|---|---|---|
| 物理建模 | 优秀 | Transport、visibility、PBR、shadow 和 dynamic-state consistency 均有清晰的物理/数值模型。 |
| 验证完整性 | 优秀 | 覆盖 regression tests、deterministic hashes、PFM numerics、multi-state/inverse-square diagnostics 和 200-case trusted evaluation。 |
| 指标均衡 | 良好 | FLIP/Worst-patch/Strict 大范围提升，Indirect 也为正；Occlusion diagnostic 平均轻微退化。 |
| 最终效果 | 成功 | Strict score 0.89781202，mean(B−A) +0.07916299，Normalized improvement 0.43651813。 |

## 执行概览

- Test：`TEST11`
- Main model：`gpt-5.6-sol`
- Claude Code：`2.1.233`
- Candidate / Baseline：`2934471` / `2039d94`
- Tool calls：300（25 errors，36 warnings）
- Subagents：2 success / 9 attempts
- Git diff：6 files，+868 / -338，diff check `PASS`

### Tool 类型

| Tool | Calls |
|---|---:|
| Read | 84 |
| Edit | 84 |
| PowerShell | 55 |
| Grep | 33 |
| Glob | 19 |
| Agent | 9 |
| TodoWrite | 9 |
| EnterPlanMode | 2 |
| Write | 2 |
| ExitPlanMode | 2 |
| TaskOutput | 1 |

## 执行阶段

### #1–#67 · 全链路审计与 baseline

- 动作：尝试并行审计 architecture/GI/tests，读取 contract、Probe、shader、capture 与 tests，建立 deterministic baseline 与收敛计划。
- 分析：早期 subagent worktree isolation 失败，主 agent 直接完成审计；计划覆盖整个 rendering/evaluation pipeline。
- 证据：Baseline repeated hashes/PFM statistics 成功，形成 transport、validity、PBR、shadow 和 export 任务列表。

### #68–#140 · Deterministic transport 与 BVH

- 动作：实现 Fibonacci directions、analytic SH convolution、nearest-hit Surfel selection 和 BVH nearest/any-hit，增加 numerical tests 并反复构建/export。
- 分析：第一轮从 sampling variance 扩展到 geometry visibility，并通过成功 subagent review 修正 transport 细节。
- 证据：Analytic-SH 与 BVH one-shot 成功，BVH/brute-force 回归和完整 test suite 通过。

### #141–#219 · Probe validity、PBR 与 shadow

- 动作：设计 invalid-solid Probe 处理，实现 validity-aware 8-neighbor reconstruction、receiver normal bias、GGX/Smith 修正和 dynamic shadow range/bias。
- 分析：该阶段直接面向 light leaking 和 PBR/shadow artifact，用 byte determinism 与 PFM 数值不变量验证。
- 证据：Validity diagnostic、repeated one-shot hash 和 PBR shadow tests 完成。

### #220–#265 · Linear export 与 frame-consistent GI

- 动作：实现 dedicated RGB32F combined/indirect attachments、deterministic capture/atomic publication，并使 dynamic light coefficients 在完整 generation 后一次上传。
- 分析：将 image correctness 与 evaluation output correctness 同时纳入收敛，避免 default framebuffer 和跨帧混合引入不确定性。
- 证据：Dedicated-linear one-shot 三文件 byte deterministic，atomic/stale-directory tests 通过。

### #266–#300 · 多状态诊断与最终收敛

- 动作：运行 rendering-correctness subagent review、zero/RGB/near/far/inverse-square diagnostics，修正 GI update order 和 automation failure behavior，完成最终 tests/diff review。
- 分析：用多种 light state 检查新 pipeline 的 energy scaling 和 frame consistency，并在最后发现 wall/cube coefficient update order 后继续修正。
- 证据：Final one-shot/PFM dimensions 正确，missing-input/stale-output 返回 non-zero，最终 commit 2934471。

## Subagent

| 任务 | Requested | Actual | 状态 |
|---|---|---|---|
| 审查首轮 transport | sonnet | deepseek-v4-pro | success |
| 审查 rendering correctness | sonnet | deepseek-v4-pro | success |

## Git 文件变化

| File | Added | Deleted |
|---|---:|---:|
| `includes/GI/probe.h` | 393 | 156 |
| `src/getting_started/GIApplication/light_casters.fs` | 119 | 79 |
| `src/getting_started/GIApplication/main.cpp` | 120 | 79 |
| `src/getting_started/GIApplication/realtime_capture.h` | 94 | 17 |
| `tests/prt_numerics.cpp` | 107 | 5 |
| `tests/realtime_capture.cpp` | 35 | 2 |

Worktree status：`clean`

<details>
<summary><strong>Tool-call 流程摘要</strong></summary>

| # | 阶段 | Tool | 状态 | 摘要 |
|---:|---|---|---|---|
| 1 | 全链路审计与 baseline | EnterPlanMode | ok | {} |
| 2 | 全链路审计与 baseline | Agent | error | 审计渲染架构 |
| 3 | 全链路审计与 baseline | Agent | error | 审计GI与着色器 |
| 4 | 全链路审计与 baseline | Agent | error | 审计测试与基准 |
| 5 | 全链路审计与 baseline | Agent | error | 审计渲染架构 |
| 6 | 全链路审计与 baseline | Agent | error | 审计GI与着色器 |
| 7 | 全链路审计与 baseline | Agent | error | 审计测试与基准 |
| 8 | 全链路审计与 baseline | TodoWrite | ok | 更新任务列表 |
| 9 | 全链路审计与 baseline | Glob | ok | <candidate-repository> |
| 10 | 全链路审计与 baseline | Glob | ok | <candidate-repository> |
| 11 | 全链路审计与 baseline | Grep | ok | <candidate-repository> |
| 12 | 全链路审计与 baseline | Glob | ok | <candidate-repository> |
| 13 | 全链路审计与 baseline | Glob | ok | <candidate-repository> |
| 14 | 全链路审计与 baseline | Glob | ok | <candidate-repository> |
| 15 | 全链路审计与 baseline | Glob | ok | <candidate-repository> |
| 16 | 全链路审计与 baseline | Glob | ok | <candidate-repository> |
| 17 | 全链路审计与 baseline | Glob | ok | <candidate-repository> |
| 18 | 全链路审计与 baseline | Read | error | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 19 | 全链路审计与 baseline | Read | error | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 20 | 全链路审计与 baseline | Read | error | <candidate-repository>\src\getting_started\GIApplication\ssaa_resolve.fs |
| 21 | 全链路审计与 baseline | Read | error | <candidate-repository>\includes\GI\probe.h |
| 22 | 全链路审计与 baseline | Read | error | <candidate-repository>\realtime-render-contract.json |
| 23 | 全链路审计与 baseline | Read | error | <candidate-repository>\tests\prt_numerics.cpp |
| 24 | 全链路审计与 baseline | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 25 | 全链路审计与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 26 | 全链路审计与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\ssaa_resolve.fs |
| 27 | 全链路审计与 baseline | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 28 | 全链路审计与 baseline | Read | ok | <candidate-repository>\realtime-render-contract.json |
| 29 | 全链路审计与 baseline | Read | warning | <candidate-repository>\tests\prt_numerics.cpp |
| 30 | 全链路审计与 baseline | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 31 | 全链路审计与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\render_contract.h |
| 32 | 全链路审计与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 33 | 全链路审计与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.vs |
| 34 | 全链路审计与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.fs |
| 35 | 全链路审计与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.gs |
| 36 | 全链路审计与 baseline | Read | warning | <candidate-repository>\tools\test.py |
| 37 | 全链路审计与 baseline | Read | ok | <candidate-repository>\tools\build.py |
| 38 | 全链路审计与 baseline | Read | warning | <candidate-repository>\tests\render_contract.cpp |
| 39 | 全链路审计与 baseline | Read | warning | <candidate-repository>\tests\realtime_capture.cpp |
| 40 | 全链路审计与 baseline | Read | ok | <candidate-repository>\CMakeLists.txt |
| 41 | 全链路审计与 baseline | Glob | ok | <candidate-repository> |
| 42 | 全链路审计与 baseline | Grep | ok | <candidate-repository>\src\getting_started\GIApplication |
| 43 | 全链路审计与 baseline | Grep | warning | <candidate-repository> |
| 44 | 全链路审计与 baseline | Grep | ok | <candidate-repository>\src\getting_started\GIApplication |
| 45 | 全链路审计与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\ssaa_resolve.vs |
| 46 | 全链路审计与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.vs |
| 47 | 全链路审计与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\probe.fs |
| 48 | 全链路审计与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\camera.fs |
| 49 | 全链路审计与 baseline | Read | ok | <candidate-repository>\tools\_tooling.py |
| 50 | 全链路审计与 baseline | Glob | ok | <candidate-repository> |
| 51 | 全链路审计与 baseline | Read | ok | <candidate-repository>\README.md |
| 52 | 全链路审计与 baseline | PowerShell | ok | 查看最近提交历史 |
| 53 | 全链路审计与 baseline | PowerShell | ok | 查看当前工作树状态 |
| 54 | 全链路审计与 baseline | Glob | ok | <candidate-repository> |
| 55 | 全链路审计与 baseline | Glob | ok | <candidate-repository> |
| 56 | 全链路审计与 baseline | Glob | ok | <candidate-repository> |
| 57 | 全链路审计与 baseline | Grep | ok | <candidate-repository> |
| 58 | 全链路审计与 baseline | PowerShell | ok | 查看 plan 相关环境变量 |
| 59 | 全链路审计与 baseline | Glob | ok | <user-home>\.claude\plans |
| 60 | 全链路审计与 baseline | Glob | ok | <claude-project> |
| 61 | 全链路审计与 baseline | Read | warning | <user-home>\.claude\plans\realtime-rendering-convergence.md |
| 62 | 全链路审计与 baseline | Read | warning | <user-home>\.claude\plans\prt-realtime-rendering.md |
| 63 | 全链路审计与 baseline | Read | warning | <user-home>\.claude\plans\prt-rendering-improvement.md |
| 64 | 全链路审计与 baseline | TodoWrite | ok | 更新任务列表 |
| 65 | 全链路审计与 baseline | Write | ok | <user-home>\.claude\plans\realtime-rendering-convergence.md |
| 66 | 全链路审计与 baseline | TodoWrite | ok | 更新任务列表 |
| 67 | 全链路审计与 baseline | ExitPlanMode | ok | {} |
| 68 | Deterministic transport 与 BVH | TodoWrite | ok | 更新任务列表 |
| 69 | Deterministic transport 与 BVH | PowerShell | warning | 构建并运行全部 regression tests |
| 70 | Deterministic transport 与 BVH | Glob | ok | <candidate-repository> |
| 71 | Deterministic transport 与 BVH | PowerShell | error | 生成 deterministic one-shot baseline |
| 72 | Deterministic transport 与 BVH | PowerShell | ok | 在 shader 目录生成 one-shot baseline |
| 73 | Deterministic transport 与 BVH | Glob | ok | <user-home>\AppData\Local\Temp\prt-baseline-a |
| 74 | Deterministic transport 与 BVH | PowerShell | ok | 计算 baseline hash 和 PNG 尺寸 |
| 75 | Deterministic transport 与 BVH | Read | ok | <user-home>\AppData\Local\Temp\prt-baseline-a\cases\baseline\state.json |
| 76 | Deterministic transport 与 BVH | PowerShell | ok | 检查 Python 调用环境 |
| 77 | Deterministic transport 与 BVH | PowerShell | ok | 重复 baseline 并检查 determinism |
| 78 | Deterministic transport 与 BVH | PowerShell | ok | 统计 baseline PFM 线性数据 |
| 79 | Deterministic transport 与 BVH | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 80 | Deterministic transport 与 BVH | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 81 | Deterministic transport 与 BVH | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 82 | Deterministic transport 与 BVH | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 83 | Deterministic transport 与 BVH | PowerShell | ok | 检查 Probe 源码精确换行与缩进 |
| 84 | Deterministic transport 与 BVH | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 85 | Deterministic transport 与 BVH | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 86 | Deterministic transport 与 BVH | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 87 | Deterministic transport 与 BVH | Grep | ok | <candidate-repository> |
| 88 | Deterministic transport 与 BVH | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 89 | Deterministic transport 与 BVH | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 90 | Deterministic transport 与 BVH | Read | warning | <candidate-repository>\tests\prt_numerics.cpp |
| 91 | Deterministic transport 与 BVH | Edit | ok | <candidate-repository>\tests\prt_numerics.cpp |
| 92 | Deterministic transport 与 BVH | Edit | ok | <candidate-repository>\tests\prt_numerics.cpp |
| 93 | Deterministic transport 与 BVH | PowerShell | warning | 验证 Probe transport 第一轮修改 |
| 94 | Deterministic transport 与 BVH | PowerShell | ok | 渲染 analytic SH 候选输出 |
| 95 | Deterministic transport 与 BVH | PowerShell | ok | 计算 analytic SH 输出 hash |
| 96 | Deterministic transport 与 BVH | PowerShell | ok | 统计 analytic SH PFM 数据 |
| 97 | Deterministic transport 与 BVH | Read | ok | <user-home>\AppData\Local\Temp\prt-analytic-sh\cases\analytic\realtime.png |
| 98 | Deterministic transport 与 BVH | Read | ok | <user-home>\AppData\Local\Temp\prt-baseline-a\cases\baseline\realtime.png |
| 99 | Deterministic transport 与 BVH | Agent | error | 审查首轮 transport |
| 100 | Deterministic transport 与 BVH | Agent | ok | 审查首轮 transport |
| 101 | Deterministic transport 与 BVH | TodoWrite | ok | 更新任务列表 |
| 102 | Deterministic transport 与 BVH | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 103 | Deterministic transport 与 BVH | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 104 | Deterministic transport 与 BVH | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 105 | Deterministic transport 与 BVH | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 106 | Deterministic transport 与 BVH | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 107 | Deterministic transport 与 BVH | PowerShell | ok | 检查 Ray intersection 函数签名 |
| 108 | Deterministic transport 与 BVH | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 109 | Deterministic transport 与 BVH | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 110 | Deterministic transport 与 BVH | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 111 | Deterministic transport 与 BVH | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 112 | Deterministic transport 与 BVH | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 113 | Deterministic transport 与 BVH | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 114 | Deterministic transport 与 BVH | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 115 | Deterministic transport 与 BVH | PowerShell | ok | 检查 Surfel 源码精确格式 |
| 116 | Deterministic transport 与 BVH | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 117 | Deterministic transport 与 BVH | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 118 | Deterministic transport 与 BVH | PowerShell | ok | 检查 Probe constructor 精确格式 |
| 119 | Deterministic transport 与 BVH | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 120 | Deterministic transport 与 BVH | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 121 | Deterministic transport 与 BVH | Grep | ok | <candidate-repository>\includes\GI\probe.h |
| 122 | Deterministic transport 与 BVH | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 123 | Deterministic transport 与 BVH | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 124 | Deterministic transport 与 BVH | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 125 | Deterministic transport 与 BVH | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 126 | Deterministic transport 与 BVH | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 127 | Deterministic transport 与 BVH | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 128 | Deterministic transport 与 BVH | Grep | ok | <candidate-repository> |
| 129 | Deterministic transport 与 BVH | PowerShell | warning | 构建并验证 BVH acceleration 修改 |
| 130 | Deterministic transport 与 BVH | Edit | ok | <candidate-repository>\tests\prt_numerics.cpp |
| 131 | Deterministic transport 与 BVH | Edit | ok | <candidate-repository>\tests\prt_numerics.cpp |
| 132 | Deterministic transport 与 BVH | PowerShell | warning | 运行当前 regression tests |
| 133 | Deterministic transport 与 BVH | PowerShell | warning | 重建并运行新增 BVH tests |
| 134 | Deterministic transport 与 BVH | PowerShell | ok | 验证 BVH one-shot 输出与耗时 |
| 135 | Deterministic transport 与 BVH | Read | ok | <user-home>\AppData\Local\Temp\prt-bvh-valid\cases\bvh\realtime.png |
| 136 | Deterministic transport 与 BVH | Grep | ok | <candidate-repository> |
| 137 | Deterministic transport 与 BVH | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 138 | Deterministic transport 与 BVH | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 139 | Deterministic transport 与 BVH | PowerShell | ok | 检查工作树修改和 diff 统计 |
| 140 | Deterministic transport 与 BVH | PowerShell | ok | 构建并运行完整测试套件 |
| 141 | Probe validity、PBR 与 shadow | TodoWrite | ok | 更新任务列表 |
| 142 | Probe validity、PBR 与 shadow | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 143 | Probe validity、PBR 与 shadow | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 144 | Probe validity、PBR 与 shadow | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 145 | Probe validity、PBR 与 shadow | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 146 | Probe validity、PBR 与 shadow | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 147 | Probe validity、PBR 与 shadow | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 148 | Probe validity、PBR 与 shadow | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 149 | Probe validity、PBR 与 shadow | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 150 | Probe validity、PBR 与 shadow | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 151 | Probe validity、PBR 与 shadow | Read | warning | <candidate-repository>\tests\prt_numerics.cpp |
| 152 | Probe validity、PBR 与 shadow | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 153 | Probe validity、PBR 与 shadow | Read | error | <candidate-repository>\includes\render_contract.h |
| 154 | Probe validity、PBR 与 shadow | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 155 | Probe validity、PBR 与 shadow | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 156 | Probe validity、PBR 与 shadow | Grep | ok | <candidate-repository>\includes |
| 157 | Probe validity、PBR 与 shadow | Glob | ok | <candidate-repository> |
| 158 | Probe validity、PBR 与 shadow | Read | ok | <candidate-repository>\src\getting_started\GIApplication\render_contract.h |
| 159 | Probe validity、PBR 与 shadow | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 160 | Probe validity、PBR 与 shadow | EnterPlanMode | ok | {} |
| 161 | Probe validity、PBR 与 shadow | Read | warning | <user-home>\.claude\plans\realtime-rendering-convergence.md |
| 162 | Probe validity、PBR 与 shadow | ExitPlanMode | ok | {} |
| 163 | Probe validity、PBR 与 shadow | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 164 | Probe validity、PBR 与 shadow | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 165 | Probe validity、PBR 与 shadow | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 166 | Probe validity、PBR 与 shadow | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 167 | Probe validity、PBR 与 shadow | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 168 | Probe validity、PBR 与 shadow | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 169 | Probe validity、PBR 与 shadow | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 170 | Probe validity、PBR 与 shadow | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 171 | Probe validity、PBR 与 shadow | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 172 | Probe validity、PBR 与 shadow | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 173 | Probe validity、PBR 与 shadow | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 174 | Probe validity、PBR 与 shadow | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 175 | Probe validity、PBR 与 shadow | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 176 | Probe validity、PBR 与 shadow | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 177 | Probe validity、PBR 与 shadow | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 178 | Probe validity、PBR 与 shadow | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 179 | Probe validity、PBR 与 shadow | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 180 | Probe validity、PBR 与 shadow | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 181 | Probe validity、PBR 与 shadow | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 182 | Probe validity、PBR 与 shadow | Edit | error | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 183 | Probe validity、PBR 与 shadow | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 184 | Probe validity、PBR 与 shadow | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 185 | Probe validity、PBR 与 shadow | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 186 | Probe validity、PBR 与 shadow | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 187 | Probe validity、PBR 与 shadow | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 188 | Probe validity、PBR 与 shadow | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 189 | Probe validity、PBR 与 shadow | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 190 | Probe validity、PBR 与 shadow | PowerShell | warning | 构建并验证 validity reconstruction 修改 |
| 191 | Probe validity、PBR 与 shadow | Grep | ok | <claude-project>\44205ccf-54ca-4e97-aeb6-126ca30968a1.jsonl |
| 192 | Probe validity、PBR 与 shadow | Grep | ok | <claude-project>\44205ccf-54ca-4e97-aeb6-126ca30968a1.jsonl |
| 193 | Probe validity、PBR 与 shadow | Glob | ok | <candidate-repository> |
| 194 | Probe validity、PBR 与 shadow | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 195 | Probe validity、PBR 与 shadow | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 196 | Probe validity、PBR 与 shadow | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 197 | Probe validity、PBR 与 shadow | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 198 | Probe validity、PBR 与 shadow | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 199 | Probe validity、PBR 与 shadow | PowerShell | warning | 运行 validity-aware one-shot 渲染 |
| 200 | Probe validity、PBR 与 shadow | PowerShell | ok | 运行 validity-aware one-shot 渲染 |
| 201 | Probe validity、PBR 与 shadow | PowerShell | ok | 核对 one-shot 输出文件和 hash |
| 202 | Probe validity、PBR 与 shadow | PowerShell | ok | 检查 indirect PFM 数值不变量 |
| 203 | Probe validity、PBR 与 shadow | PowerShell | ok | 输出 one-shot 文件 SHA256 |
| 204 | Probe validity、PBR 与 shadow | PowerShell | ok | 重复 one-shot 并验证 byte determinism |
| 205 | Probe validity、PBR 与 shadow | Read | ok | <user-home>\AppData\Local\Temp\prt-validity-diagnostic\cases\validity-center\realtime.png |
| 206 | Probe validity、PBR 与 shadow | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 207 | Probe validity、PBR 与 shadow | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.fs |
| 208 | Probe validity、PBR 与 shadow | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.gs |
| 209 | Probe validity、PBR 与 shadow | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 210 | Probe validity、PBR 与 shadow | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 211 | Probe validity、PBR 与 shadow | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 212 | Probe validity、PBR 与 shadow | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 213 | Probe validity、PBR 与 shadow | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 214 | Probe validity、PBR 与 shadow | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 215 | Probe validity、PBR 与 shadow | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 216 | Probe validity、PBR 与 shadow | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 217 | Probe validity、PBR 与 shadow | Edit | ok | <candidate-repository>\tests\prt_numerics.cpp |
| 218 | Probe validity、PBR 与 shadow | Edit | ok | <candidate-repository>\tests\prt_numerics.cpp |
| 219 | Probe validity、PBR 与 shadow | PowerShell | warning | 验证 PBR 和 point-shadow 修改 |
| 220 | Linear export 与 frame-consistent GI | PowerShell | ok | 运行 PBR shadow one-shot diagnostic |
| 221 | Linear export 与 frame-consistent GI | Read | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 222 | Linear export 与 frame-consistent GI | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 223 | Linear export 与 frame-consistent GI | Read | warning | <candidate-repository>\tests\realtime_capture.cpp |
| 224 | Linear export 与 frame-consistent GI | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 225 | Linear export 与 frame-consistent GI | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 226 | Linear export 与 frame-consistent GI | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 227 | Linear export 与 frame-consistent GI | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 228 | Linear export 与 frame-consistent GI | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 229 | Linear export 与 frame-consistent GI | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 230 | Linear export 与 frame-consistent GI | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 231 | Linear export 与 frame-consistent GI | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 232 | Linear export 与 frame-consistent GI | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 233 | Linear export 与 frame-consistent GI | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 234 | Linear export 与 frame-consistent GI | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 235 | Linear export 与 frame-consistent GI | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 236 | Linear export 与 frame-consistent GI | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 237 | Linear export 与 frame-consistent GI | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 238 | Linear export 与 frame-consistent GI | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 239 | Linear export 与 frame-consistent GI | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 240 | Linear export 与 frame-consistent GI | Grep | ok | <candidate-repository> |
| 241 | Linear export 与 frame-consistent GI | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 242 | Linear export 与 frame-consistent GI | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 243 | Linear export 与 frame-consistent GI | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 244 | Linear export 与 frame-consistent GI | Edit | ok | <candidate-repository>\tests\realtime_capture.cpp |
| 245 | Linear export 与 frame-consistent GI | Edit | ok | <candidate-repository>\tests\realtime_capture.cpp |
| 246 | Linear export 与 frame-consistent GI | Edit | ok | <candidate-repository>\tests\realtime_capture.cpp |
| 247 | Linear export 与 frame-consistent GI | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 248 | Linear export 与 frame-consistent GI | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 249 | Linear export 与 frame-consistent GI | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 250 | Linear export 与 frame-consistent GI | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 251 | Linear export 与 frame-consistent GI | PowerShell | warning | 验证 dedicated linear export pipeline |
| 252 | Linear export 与 frame-consistent GI | PowerShell | ok | 验证 dedicated linear one-shot export |
| 253 | Linear export 与 frame-consistent GI | Read | ok | <user-home>\AppData\Local\Temp\prt-linear-export-diagnostic\cases\center\realtime.png |
| 254 | Linear export 与 frame-consistent GI | PowerShell | ok | 重复验证三文件 byte determinism |
| 255 | Linear export 与 frame-consistent GI | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 256 | Linear export 与 frame-consistent GI | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 257 | Linear export 与 frame-consistent GI | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 258 | Linear export 与 frame-consistent GI | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 259 | Linear export 与 frame-consistent GI | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 260 | Linear export 与 frame-consistent GI | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 261 | Linear export 与 frame-consistent GI | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 262 | Linear export 与 frame-consistent GI | PowerShell | warning | 验证 atomic dynamic GI generation |
| 263 | Linear export 与 frame-consistent GI | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 264 | Linear export 与 frame-consistent GI | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 265 | Linear export 与 frame-consistent GI | TodoWrite | ok | 更新任务列表 |
| 266 | 多状态诊断与最终收敛 | Agent | ok | 审查 rendering correctness |
| 267 | 多状态诊断与最终收敛 | PowerShell | error | 运行 zero、RGB、near/far 多状态 diagnostics |
| 268 | 多状态诊断与最终收敛 | PowerShell | error | 运行 zero、RGB、near/far 多状态 diagnostics |
| 269 | 多状态诊断与最终收敛 | PowerShell | ok | 渲染 zero、RGB、near/far diagnostic cases |
| 270 | 多状态诊断与最终收敛 | Write | ok | <candidate-repository>\diagnostics-multistate-temp-2\analyze.py |
| 271 | 多状态诊断与最终收敛 | PowerShell | ok | 分析多状态 indirect PFM 数值 |
| 272 | 多状态诊断与最终收敛 | PowerShell | ok | 渲染 inverse-square diagnostic cases |
| 273 | 多状态诊断与最终收敛 | PowerShell | warning | 验证 stale case directory 返回 non-zero |
| 274 | 多状态诊断与最终收敛 | PowerShell | ok | 删除本地 diagnostic 临时输出 |
| 275 | 多状态诊断与最终收敛 | PowerShell | ok | 清理失败 agent worktree 临时目录 |
| 276 | 多状态诊断与最终收敛 | PowerShell | warning | 检查最终工作树和修改统计 |
| 277 | 多状态诊断与最终收敛 | Grep | warning | <candidate-repository> |
| 278 | 多状态诊断与最终收敛 | Grep | ok | <candidate-repository> |
| 279 | 多状态诊断与最终收敛 | PowerShell | warning | 运行最终完整构建和测试 |
| 280 | 多状态诊断与最终收敛 | PowerShell | ok | 运行最终 one-shot 并记录 hash |
| 281 | 多状态诊断与最终收敛 | PowerShell | ok | 核对最终 PFM 数值与 dimensions |
| 282 | 多状态诊断与最终收敛 | Read | ok | <candidate-repository>\final-one-shot-temp\cases\final\state.json |
| 283 | 多状态诊断与最终收敛 | PowerShell | ok | 删除最终 one-shot 临时输出 |
| 284 | 多状态诊断与最终收敛 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 285 | 多状态诊断与最终收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 286 | 多状态诊断与最终收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 287 | 多状态诊断与最终收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 288 | 多状态诊断与最终收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 289 | 多状态诊断与最终收敛 | PowerShell | warning | 验证 frame-consistent GI 更新顺序 |
| 290 | 多状态诊断与最终收敛 | PowerShell | ok | 运行最终 one-shot smoke test |
| 291 | 多状态诊断与最终收敛 | PowerShell | warning | 检查 diff whitespace 和最终状态 |
| 292 | 多状态诊断与最终收敛 | TodoWrite | ok | 更新任务列表 |
| 293 | 多状态诊断与最终收敛 | PowerShell | ok | 验证缺少 automation input 返回 non-zero |
| 294 | 多状态诊断与最终收敛 | TaskOutput | warning | {"task_id":"abef03cb3d6f914f2","block":true,"timeout":[omitted]} |
| 295 | 多状态诊断与最终收敛 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 296 | 多状态诊断与最终收敛 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 297 | 多状态诊断与最终收敛 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 298 | 多状态诊断与最终收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 299 | 多状态诊断与最终收敛 | PowerShell | warning | 运行收敛后的最终测试和状态检查 |
| 300 | 多状态诊断与最终收敛 | TodoWrite | ok | 更新任务列表 |

</details>

<details>
<summary><strong>Agent 最终回复</strong></summary>

<pre>已完成一轮完整的 realtime rendering 物理准确性收敛，未修改 public render contract。

### 主要改进

- [probe.h](includes/GI/probe.h)
  - Probe sampling 改为 256 条 deterministic Spherical Fibonacci directions，移除 `rand()`、wall clock 和平台相关随机序列。
  - 每条 Probe ray 先确定 nearest hit，再执行 Surfel shading。
  - Incoming radiance 直接投影到 SH，并使用 Lambert analytic convolution：
    - `A0 = π`
    - `A1 = 2π/3`
    - `A2 = π/4`
  - 新增 deterministic BVH，支持 nearest-hit 和 any-hit。
  - BVH traversal 使用固定容量 stack，避免每条 ray 动态分配。
  - CPU PBR 改用更准确的 GGX Smith masking-shadowing，并处理 grazing angle、退化 half-vector 和除零问题。

- [main.cpp](src/getting_started/GIApplication/main.cpp)
  - Static scene 建立一次 BVH，Probe 初始化和动态 light visibility 复用。
  - 删除让实体内部 Probe “看穿” cube 的 workaround。
  - 位于 closed solid 内部的 Probe 显式标记为 invalid。
  - Dynamic light 每个 state 完整生成一套 coefficients 后一次性上传，不再混合不同 frame/light state。
  - GI 更新移动到任何 evaluated geometry draw 之前，确保 walls 和 cubes 使用同一套 coefficients。
  - Point-shadow near plane 改为 `0.01`，far plane 根据 light 到 scene bounds 的最大距离动态推导。
  - 增加 dedicated combined/indirect linear resolve attachments。
  - Automation 不再从 default `GL_BACK` framebuffer 导出 PNG。
  - Automation 明确禁用 dithering。
  - 修复 visualization sphere 的 interleaved vertex buffer 被整体反转的问题。

- [light_casters.fs](src/getting_started/GIApplication/light_casters.fs)
  - 加入 receiver-normal-biased Probe lookup。
  - 显式读取相邻 8 个 Probe，应用：
    - trilinear weight
    - Probe validity
    - 有效权重归一化
  - 无有效 Probe 时保持零间接能量，不注入额外亮度。
  - GPU direct PBR 与 CPU Surfel PBR 使用一致的 exact GGX Smith 模型。
  - Point-shadow bias 改为由 cubemap angular texel footprint、receiver distance 和 surface incidence 推导，替换固定 `0.05` world-space bias。

- [realtime_capture.h](src/getting_started/GIApplication/realtime_capture.h)
  - PNG 从 dedicated combined linear HDR buffer 在 CPU 上执行：
    1. non-negative clamp
    2. Reinhard tone mapping
    3. exact piecewise sRGB
    4. RGB8 round/clamp
  - 导出前拒绝 NaN/Inf。
  - 三个文件先写入 temporary files，再 rename commit。
  - 任一写入或 rename 失败时清理整个 partial case directory。
  - 保持 PFM 为 little-endian RGB32F linear indirect。

- Tests
  - [prt_numerics.cpp](tests/prt_numerics.cpp) 新增 deterministic sampling、Lambert band factors、BVH 对照、GGX finite/reciprocity 等测试。
  - [realtime_capture.cpp](tests/realtime_capture.cpp) 新增 Reinhard+sRGB known values、RGB8 PNG、non-finite rejection 和 partial-output cleanup 测试。

### 验证结果

完整执行：

```powershell
python .\tools\test.py
```

结果：

- `frame_timing` passed
- `realtime_capture` passed
- `render_contract` passed
- `prt_numerics_pbr` passed
- `prt_numerics_phong` passed
- **100% tests passed**

实际 one-shot export 验证：

- Process exit code：`0`
- 三份必要输出且无额外文件
- PNG：`800x600 RGB8`
- PFM：`800x600 RGB32F little-endian`
- PFM finite：`true`
- PFM non-negative：`true`
- PFM min：`0`
- PFM max：`0.115658402`
- PFM mean：`0.0571926171`
- 相同 state 重复运行时 PNG、PFM、state 三者均 byte-level deterministic。

最终代表性输出 SHA256：

```text
realtime.png
2EDC2CEB5ED96EA54A2A1641CEFCA04B58D3027A6C0D8E0CA5F7D7C72B7062B9

indirect-linear.pfm
D30C42B678FCB4653A0E2B886FD58FD68ABC37C02FF5288B9E166D00E2559430
```

多状态 diagnostics 也确认：

- Zero intensity：完整 indirect buffer 为零。
- Red-only light：green/blue indirect channels 为零。
- Near-cube 和 far-corner light：输出 finite、non-negative。
- Existing/stale case directory：返回 non-zero。
- 缺少 automation input：返回 non-zero。
- one-shot 启动、渲染和导出约 `1.7 s`。

当前剩余视觉限制主要来自 contract 固定的 sparse SH3 Probe reconstruction、one indirect bounce 和 point-source light 模型。Dynamic GI 现在优先保证每帧 transport state 完整一致；进一步并行化可能减少 frame hitch，但不会直接提高图像物理准确性，且需要额外维护跨平台 deterministic reduction。

工作树包含上述 6 个已修改文件，未创建 commit。</pre>

</details>
