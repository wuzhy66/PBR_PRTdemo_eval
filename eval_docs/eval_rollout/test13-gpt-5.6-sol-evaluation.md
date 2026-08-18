# TEST13 · gpt-5.6-sol · Realtime rendering best-effort 全报告

> GitHub-readable evaluation report。本文件保留指标、过程分析和 tool-call 摘要，不嵌入体积过大的 tool input/output 或完整 Git diff。

## 最终结果

**Normalized improvement：`0.42710169` · Decision：`success`**

| Baseline A | Candidate B / Strict | Mean B−A | Cases | Strict / Excluded / Errors |
|---:|---:|---:|---:|---:|
| 0.81864903 | 0.89610433 | +0.07745531 | 200 | 200 / 0 / 0 |

`Normalized improvement` 是最终 coding improvement 分数；`Strict score` 是单个 renderer 对 offline reference 的绝对分数。

### 指标变化

| 指标 | 权重 | Baseline | Candidate | 变化 | 改善 | 退化 | 不变 |
|---|---:|---:|---:|---:|---:|---:|---:|
| FLIP perceptual score | 70% | 0.81916697 | 0.91816170 | +0.09899474 | 181 | 19 | 0 |
| Worst-patch FLIP | diagnostic | 0.60162365 | 0.80609563 | +0.20447198 | 170 | 30 | 0 |
| Indirect transport | 30% | 0.82374117 | 0.85779279 | +0.03405162 | 163 | 37 | 0 |
| Occlusion leak | diagnostic | 0.78038943 | 0.77595468 | -0.00443475 | 125 | 66 | 9 |
| Strict score | aggregate | 0.81864903 | 0.89610433 | +0.07745531 | 181 | 19 | 0 |

### Regression gates

| Gate | Required | Median delta | 改善 | 退化 | 不变 | 结果 |
|---|---:|---:|---:|---:|---:|---|
| Median FLIP delta | yes | +0.02985777 | 181 | 19 | 0 | PASS |
| Median worst-patch FLIP delta | yes | +0.06880872 | 170 | 30 | 0 | PASS |

## 总体判断

本轮对 Probe sampling、Radiance SH→Lambert irradiance transport、solid-interior Probe validity、direct GGX、point shadow 与 deterministic capture/output correctness 做了系统重构。正式 200-case 评测中 Strict score 从 0.81864903 提升到 0.89610433，FLIP 与 Worst-patch FLIP 的 median regression gates 均通过，Normalized improvement 为 0.42710169。181 case 的 Strict score 改善；主要收益来自 FLIP（平均 +0.09899474）和 Worst-patch FLIP（平均 +0.[timing omitted]），Indirect transport 也平均提升 +0.03405162。Occlusion diagnostic 平均轻微下降 -0.00443475，仍存在少数明显回归区域。

## 改动与实测评价

### `includes/GI/probe.h`

- 改动：将 Probe sampling 改为 deterministic 256-direction spherical Fibonacci sequence；Ray 只保留 nearest triangle hit，改投影 incoming radiance SH，并使用 A0=π、A1=2π/3、A2=π/4 的 analytic Lambert convolution。
- 目标：移除 wall-clock/global RNG variance，修正 Surfel/Ray mapping 和 transport representation，使一次 indirect bounce 的 SH coefficient 更稳定且物理含义明确。
- 评测：Indirect transport 平均从 0.82374117 提升到 0.85779279：163 case 改善、37 case 退化；证明重构影响了 official linear indirect output，但仍有明显 tail regressions。

### `probe.h / main.cpp / light_casters.fs`

- 改动：将 solid 内 Probe 标为 invalid，新增 Probe validity 3D texture；trilinear interpolation 只累积有效 corners 并按 weight sum 归一化，同时由实际 grid spacing 推导 receiver normal offset。
- 目标：避免通过移除 cube geometry 让 Probe 非物理地看穿实体，并防止 invalid corners 把 cube 周围 GI 系统性压暗。
- 评测：Strict score 在 181/200 case 改善，Worst-patch FLIP 在 170 case 改善；但 case-0172/0173 的 Indirect delta 约为 -0.112，说明 validity/fallback 与局部 transport 仍需针对性检查。

### `src/getting_started/GIApplication/light_casters.fs / main.cpp`

- 改动：统一 CPU/GPU direct PBR 的 height-correlated Smith GGX visibility，增加 grazing/degenerate finite guards；point-shadow far plane 覆盖 scene bounds，near plane只排除 singularity，bias 随 distance、cubemap texel footprint 与 surface slope 变化。
- 目标：提高 direct BRDF 与 visibility 的物理一致性，减少 fixed bias 导致的 acne、peter-panning、clipping 和局部 shadow artifact。
- 评测：FLIP 平均从 0.81916697 提升到 0.91816170，181 case 改善；Worst-patch FLIP 提升到 0.80609563，表明 combined image 和局部最差区域得到显著改善。

### `src/getting_started/GIApplication/realtime_capture.h / main.cpp`

- 改动：Automation 隔离 keyboard/cursor/scroll input；从 dedicated RGB32F linear framebuffer 读取并在 CPU 执行 Reinhard、exact sRGB 与 round-to-nearest RGB8；temporary files flush 后原子发布，并传播各 GL pass/readback error。
- 目标：让 automated capture 与 realtime display transform 一致、跨运行确定，并避免失败时发布 partial/stale case。
- 评测：正式 replay 成功生成 200/200 完整 case，评分为 200 strict、0 excluded、0 errors；执行过程还验证了重复 state 的 PNG/PFM byte identity 和错误输入的 non-zero exit。

### `tests/prt_numerics.cpp / tests/realtime_capture.cpp / README.md`

- 改动：扩充 deterministic sampling、Lambert convolution、invalid Probe、validity interpolation、inverse-square falloff、grazing PBR、occlusion、display encoding 与 atomic capture regression coverage，并同步文档。
- 目标：以 numerical/contract tests 固定新的 transport、BRDF 和 output semantics，降低后续修改造成静默回归的概率。
- 评测：candidate 执行过程报告 5/5 tests 通过，one-shot output 尺寸、finite values、state round-trip、zero-intensity 和 stale-directory 行为均完成验证。

## 做得好的地方

- 最终 Strict mean improvement 为 +0.07745531，Normalized improvement 为 0.42710169，是一次明确成功的改进。
- 181/200 case 的 Strict 与 FLIP score 改善；FLIP median delta +0.02985777，通过 required regression gate。
- Worst-patch FLIP 平均提升 +0.[timing omitted]，170 case 改善，median delta +0.06880872，通过局部 artifact regression gate。
- Indirect transport 平均提升 +0.03405162，163 case 改善，说明收益不只来自 direct/shadow 或 display transform。
- 改动遵守一次 indirect bounce 和 public render contract，没有使用 exposure、gain、saturation 或颜色偏置迎合 reference。
- 执行过程获得 3 个成功 subagent review，实际模型包括 deepseek-v4-pro 与 gpt-5.6-sol，覆盖 rendering physics、最终改动和 GL export reliability。
- 完成 5/5 tests、one-shot export、重复输出 hash、zero-intensity、invalid env、stale directory 和 GL error propagation 验证。

## 风险与不足

- Occlusion diagnostic 平均从 0.78038943 降到 0.77595468；66 case 退化，case-0070/0071 的 Occlusion delta 约为 -0.390。
- 仍有 19 case 的 Strict score 退化；case-0172 与 case-0173 分别约为 -0.07926、-0.07664，且 FLIP、Indirect、Worst-patch 同时下降。
- Indirect transport 有 37 case 退化；case-0196/0197 的 Indirect delta 约为 -0.12095，validity-aware interpolation 或局部 SH transport 仍有优化空间。
- 实现规模较大：7 files、593 additions / 228 deletions；同时涉及 transport、shadow、capture 和 error handling，后续维护与回归定位成本上升。
- Probe/Surfel CPU intersection 和 dynamic visibility 仍是性能瓶颈，本轮没有提供与 baseline 对齐的 preprocessing 或 light-update performance benchmark。
- 328 次 tool call 中有 24 个 error、52 个 warning；早期 6 次 Agent/isolation 尝试未成功，执行效率仍可提高。
- 工作区保留 untracked .claude/ 目录，未影响 source commit 或正式 replay，但 candidate repository 并非完全 clean。
- 固定 SH3 的 Lambert-convolved irradiance 无法无损恢复完整 directional radiance，因此本轮没有实现精确 indirect GGX specular，仍是与 offline reference 的结构性差距。

## 分项结论

| 维度 | 评价 | 说明 |
|---|---|---|
| 物理建模 | 良好 | Deterministic Fibonacci sampling、nearest-hit transport、analytic Lambert convolution、Probe validity、height-correlated GGX 与 footprint-aware shadow bias 均有明确依据。 |
| 验证完整性 | 良好 | 覆盖 numerical tests、capture contract、determinism、failure atomicity、one-shot export 和正式 200-case evaluation。 |
| 指标均衡 | 良好 | FLIP、Indirect、Worst-patch 与 Strict 均提升且 gates 通过；Occlusion 平均轻微退化，局部 tail cases 仍需关注。 |
| 最终效果 | 成功 | Strict score 0.89610433，mean(B−A) +0.07745531，Normalized improvement 0.42710169。 |

## 执行概览

- Test：`TEST13`
- Main model：`gpt-5.6-sol`
- Claude Code：`2.1.233`
- Candidate / Baseline：`7903ff3` / `d36940f`
- Tool calls：328（24 errors，52 warnings）
- Subagents：3 success / 9 attempts
- Git diff：7 files，+593 / -228，diff check `PASS`

### Tool 类型

| Tool | Calls |
|---|---:|
| Edit | 104 |
| PowerShell | 64 |
| Read | 58 |
| Grep | 45 |
| TodoWrite | 13 |
| Glob | 13 |
| TaskOutput | 11 |
| Agent | 9 |
| Bash | 6 |
| SendMessage | 2 |
| EnterPlanMode | 1 |
| Write | 1 |
| ExitPlanMode | 1 |

## 执行阶段

### #1–#61 · 全链路审计与实施计划

- 动作：进入 plan mode，尝试并行审查 renderer、PRT、tests 与 contract，读取 Probe、shader、main、capture 和既有计划，形成 transport/PBR/output 的实施路线。
- 分析：早期 Agent isolation 多次失败，但随后有成功的物理审查结果；主 agent 建立了覆盖完整 rendering pipeline 的问题列表。
- 证据：定位 RNG-dependent sampling、Surfel mapping、irradiance/radiance SH 混用、solid Probe、fixed shadow bias 与 capture transform 等问题。

### #62–#113 · PRT transport 与 direct PBR 实现

- 动作：实现 deterministic Fibonacci rays、nearest-hit Surfel、radiance SH/analytic convolution、height-correlated GGX、point-shadow coverage/bias，并扩充 numerical tests。
- 分析：第一轮核心改动同时处理 indirect transport 与 direct visibility，随后用 baseline frame 和测试输出反复校验。
- 证据：probe.h、light_casters.fs、main.cpp 与 prt_numerics.cpp 形成主要数学模型 diff。

### #114–#156 · Capture correctness 与首轮收敛

- 动作：修正 automation input isolation、linear framebuffer resolve、CPU display encoding、output atomicity 和错误返回，并运行 tests、capture 与文档更新。
- 分析：将视觉算法改进与评测 output correctness 同时锁定，避免 PNG/PFM/state 的 nondeterminism 污染指标。
- 证据：realtime_capture.h/main.cpp 增加 deterministic export 与 failure cleanup，one-shot capture 通过。

### #157–#213 · Probe validity 与空间插值重构

- 动作：继续审查 solid-interior Probe，加入 validity texture、validity-aware trilinear renormalization 和 grid-spacing-derived receiver offset，并补充相关 tests。
- 分析：这一阶段消除了让 Probe 看穿 cube 的旧近似，同时避免 invalid corners 非物理压暗邻近空间。
- 证据：新增 invalid Probe zero transport、interpolation normalization 与 compacted mapping tests，并多次运行完整测试。

### #214–#271 · Numerical robustness 与 automation hardening

- 动作：验证 public contract，细化 finite guards、env parsing、GL pass/readback error propagation、resource cleanup 和 deterministic output，执行独立复审与重复 exports。
- 分析：开始从算法正确性转向异常路径、ABI 和可重复性，降低 evaluator 中出现 partial case 或 silent GL failure 的风险。
- 证据：重复 PNG/PFM hash 一致，zero-intensity 与 invalid input 行为通过，成功 subagent 复审 rendering 改动。

### #272–#328 · 最终复审、回归测试与收敛

- 动作：继续强化 capture tests、atomic publication、GL pass checks 和 cleanup，运行最终 one-shot/tests/diff checks，并由 subagent 审查 GL export reliability。
- 分析：最终实现按 public contract 收敛；正式 200-case 评测随后确认总体显著改善，同时暴露 Occlusion 和少数 case 的局部回归。
- 证据：candidate commit 7903ff3，5/5 tests 通过，正式结果 Strict 0.89610433、Normalized improvement 0.42710169。

## Subagent

| 任务 | Requested | Actual | 状态 |
|---|---|---|---|
| 审查渲染物理正确性 | sonnet | deepseek-v4-pro | success |
| 复审渲染改动 | opus | gpt-5.6-sol | success |
| 审查GL导出可靠性 | sonnet | deepseek-v4-pro | success |

## Git 文件变化

| File | Added | Deleted |
|---|---:|---:|
| `README.md` | 7 | 13 |
| `includes/GI/probe.h` | 73 | 110 |
| `src/getting_started/GIApplication/light_casters.fs` | 66 | 52 |
| `src/getting_started/GIApplication/main.cpp` | 190 | 37 |
| `src/getting_started/GIApplication/realtime_capture.h` | 83 | 11 |
| `tests/prt_numerics.cpp` | 154 | 4 |
| `tests/realtime_capture.cpp` | 20 | 1 |

Worktree status：`?? .claude/`

<details>
<summary><strong>Tool-call 流程摘要</strong></summary>

| # | 阶段 | Tool | 状态 | 摘要 |
|---:|---|---|---|---|
| 1 | 全链路审计与实施计划 | EnterPlanMode | ok | {} |
| 2 | 全链路审计与实施计划 | TodoWrite | ok | 更新任务列表 |
| 3 | 全链路审计与实施计划 | Agent | error | 梳理渲染架构 |
| 4 | 全链路审计与实施计划 | Agent | error | 审查PRT与着色器 |
| 5 | 全链路审计与实施计划 | Agent | error | 审查测试与基准 |
| 6 | 全链路审计与实施计划 | Agent | error | 梳理渲染架构 |
| 7 | 全链路审计与实施计划 | Agent | error | 审查PRT与着色器 |
| 8 | 全链路审计与实施计划 | Agent | error | 审查测试与基准 |
| 9 | 全链路审计与实施计划 | Glob | ok | <candidate-repository> |
| 10 | 全链路审计与实施计划 | Read | error | <candidate-repository>\realtime-render-contract.json |
| 11 | 全链路审计与实施计划 | Read | error | <candidate-repository>\AGENTS.md |
| 12 | 全链路审计与实施计划 | Glob | ok | <candidate-repository> |
| 13 | 全链路审计与实施计划 | Glob | ok | <candidate-repository> |
| 14 | 全链路审计与实施计划 | Glob | ok | <candidate-repository> |
| 15 | 全链路审计与实施计划 | Glob | ok | <candidate-repository> |
| 16 | 全链路审计与实施计划 | Glob | ok | <candidate-repository> |
| 17 | 全链路审计与实施计划 | Glob | ok | <candidate-repository> |
| 18 | 全链路审计与实施计划 | Read | ok | <candidate-repository>\realtime-render-contract.json |
| 19 | 全链路审计与实施计划 | Read | warning | <candidate-repository>\AGENTS.md |
| 20 | 全链路审计与实施计划 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 21 | 全链路审计与实施计划 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 22 | 全链路审计与实施计划 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\ssaa_resolve.fs |
| 23 | 全链路审计与实施计划 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\camera.fs |
| 24 | 全链路审计与实施计划 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\render_contract.h |
| 25 | 全链路审计与实施计划 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 26 | 全链路审计与实施计划 | Read | warning | <candidate-repository>\tools\test.py |
| 27 | 全链路审计与实施计划 | Glob | ok | <candidate-repository> |
| 28 | 全链路审计与实施计划 | Glob | ok | <candidate-repository> |
| 29 | 全链路审计与实施计划 | Glob | ok | <candidate-repository> |
| 30 | 全链路审计与实施计划 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 31 | 全链路审计与实施计划 | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 32 | 全链路审计与实施计划 | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 33 | 全链路审计与实施计划 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 34 | 全链路审计与实施计划 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 35 | 全链路审计与实施计划 | Read | warning | <candidate-repository>\tests\prt_numerics.cpp |
| 36 | 全链路审计与实施计划 | Read | warning | <candidate-repository>\tests\render_contract.cpp |
| 37 | 全链路审计与实施计划 | Read | ok | <candidate-repository>\CMakeLists.txt |
| 38 | 全链路审计与实施计划 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.fs |
| 39 | 全链路审计与实施计划 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.vs |
| 40 | 全链路审计与实施计划 | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 41 | 全链路审计与实施计划 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 42 | 全链路审计与实施计划 | Grep | warning | <candidate-repository> |
| 43 | 全链路审计与实施计划 | Read | warning | <candidate-repository>\tests\realtime_capture.cpp |
| 44 | 全链路审计与实施计划 | PowerShell | ok | 运行 baseline regression tests |
| 45 | 全链路审计与实施计划 | Glob | ok | <candidate-repository> |
| 46 | 全链路审计与实施计划 | Read | ok | <candidate-repository>\README.md |
| 47 | 全链路审计与实施计划 | Grep | ok | <candidate-repository> |
| 48 | 全链路审计与实施计划 | TodoWrite | ok | 更新任务列表 |
| 49 | 全链路审计与实施计划 | PowerShell | ok | 导出 baseline realtime frame |
| 50 | 全链路审计与实施计划 | TaskOutput | error | {"task_id":"bz0vt7zzu","block":false,"timeout":[omitted]} |
| 51 | 全链路审计与实施计划 | TaskOutput | warning | {"task_id":"boptem4gb","block":false,"timeout":[omitted]} |
| 52 | 全链路审计与实施计划 | Read | error | <user-home>\AppData\Local\Temp\claude\d--PBR-PRTdemo_TEST13\9638f88f-75e2-4362-8925-863ddd4e1ad4\tasks\bz0vt7zzu.output |
| 53 | 全链路审计与实施计划 | PowerShell | warning | 运行 baseline regression tests |
| 54 | 全链路审计与实施计划 | PowerShell | ok | 从 runtime 目录导出 baseline frame |
| 55 | 全链路审计与实施计划 | TaskOutput | ok | {"task_id":"b4vjjn9gd","block":false,"timeout":[omitted]} |
| 56 | 全链路审计与实施计划 | Read | ok | <user-home>\AppData\Local\Temp\prt-baseline-capture\cases\baseline\realtime.png |
| 57 | 全链路审计与实施计划 | Read | ok | <user-home>\AppData\Local\Temp\prt-baseline-capture\cases\baseline\state.json |
| 58 | 全链路审计与实施计划 | PowerShell | ok | 核对 baseline 输出尺寸 |
| 59 | 全链路审计与实施计划 | Glob | ok | <user-home>\.claude\plans |
| 60 | 全链路审计与实施计划 | Read | warning | <user-home>\.claude\plans\realtime-rendering-convergence.md |
| 61 | 全链路审计与实施计划 | Read | warning | <user-home>\.claude\plans\prt-rendering-improvement.md |
| 62 | PRT transport 与 direct PBR 实现 | Read | warning | <user-home>\.claude\plans\prt-realtime-rendering.md |
| 63 | PRT transport 与 direct PBR 实现 | PowerShell | ok | 重复导出并比较 baseline hashes |
| 64 | PRT transport 与 direct PBR 实现 | TodoWrite | ok | 更新任务列表 |
| 65 | PRT transport 与 direct PBR 实现 | Write | ok | <user-home>\.claude\plans\realtime-rendering-convergence.md |
| 66 | PRT transport 与 direct PBR 实现 | TodoWrite | ok | 更新任务列表 |
| 67 | PRT transport 与 direct PBR 实现 | ExitPlanMode | ok | {} |
| 68 | PRT transport 与 direct PBR 实现 | TodoWrite | ok | 更新任务列表 |
| 69 | PRT transport 与 direct PBR 实现 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 70 | PRT transport 与 direct PBR 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 71 | PRT transport 与 direct PBR 实现 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 72 | PRT transport 与 direct PBR 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 73 | PRT transport 与 direct PBR 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 74 | PRT transport 与 direct PBR 实现 | PowerShell | error | 替换 Probe sampling 实现 |
| 75 | PRT transport 与 direct PBR 实现 | PowerShell | ok | 检查 sampling 源文本缩进 |
| 76 | PRT transport 与 direct PBR 实现 | PowerShell | ok | 替换 Probe sampling 实现 |
| 77 | PRT transport 与 direct PBR 实现 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 78 | PRT transport 与 direct PBR 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 79 | PRT transport 与 direct PBR 实现 | PowerShell | ok | 仅着色最近 Probe hit |
| 80 | PRT transport 与 direct PBR 实现 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 81 | PRT transport 与 direct PBR 实现 | Grep | ok | <candidate-repository> |
| 82 | PRT transport 与 direct PBR 实现 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 83 | PRT transport 与 direct PBR 实现 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 84 | PRT transport 与 direct PBR 实现 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 85 | PRT transport 与 direct PBR 实现 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 86 | PRT transport 与 direct PBR 实现 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 87 | PRT transport 与 direct PBR 实现 | Edit | ok | <candidate-repository>\tests\prt_numerics.cpp |
| 88 | PRT transport 与 direct PBR 实现 | Edit | ok | <candidate-repository>\tests\prt_numerics.cpp |
| 89 | PRT transport 与 direct PBR 实现 | PowerShell | warning | 验证 Probe sampling 与 SH 改动 |
| 90 | PRT transport 与 direct PBR 实现 | PowerShell | ok | 渲染改进后的 baseline frame |
| 91 | PRT transport 与 direct PBR 实现 | TaskOutput | ok | {"task_id":"b743h0fgm","block":true,"timeout":[omitted]} |
| 92 | PRT transport 与 direct PBR 实现 | PowerShell | ok | 比较 Probe transport 前后 PFM 指标 |
| 93 | PRT transport 与 direct PBR 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 94 | PRT transport 与 direct PBR 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 95 | PRT transport 与 direct PBR 实现 | PowerShell | ok | 检查 Probe members 源文本 |
| 96 | PRT transport 与 direct PBR 实现 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 97 | PRT transport 与 direct PBR 实现 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 98 | PRT transport 与 direct PBR 实现 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 99 | PRT transport 与 direct PBR 实现 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 100 | PRT transport 与 direct PBR 实现 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 101 | PRT transport 与 direct PBR 实现 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 102 | PRT transport 与 direct PBR 实现 | Edit | ok | <candidate-repository>\tests\prt_numerics.cpp |
| 103 | PRT transport 与 direct PBR 实现 | Edit | ok | <candidate-repository>\tests\prt_numerics.cpp |
| 104 | PRT transport 与 direct PBR 实现 | PowerShell | warning | 验证 invalid Probe 与 normal offset |
| 105 | PRT transport 与 direct PBR 实现 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 106 | PRT transport 与 direct PBR 实现 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 107 | PRT transport 与 direct PBR 实现 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 108 | PRT transport 与 direct PBR 实现 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 109 | PRT transport 与 direct PBR 实现 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 110 | PRT transport 与 direct PBR 实现 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 111 | PRT transport 与 direct PBR 实现 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 112 | PRT transport 与 direct PBR 实现 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 113 | PRT transport 与 direct PBR 实现 | Edit | ok | <candidate-repository>\tests\prt_numerics.cpp |
| 114 | Capture correctness 与首轮收敛 | Edit | ok | <candidate-repository>\tests\prt_numerics.cpp |
| 115 | Capture correctness 与首轮收敛 | PowerShell | warning | 验证 PBR 与 point-shadow 改动 |
| 116 | Capture correctness 与首轮收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 117 | Capture correctness 与首轮收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 118 | Capture correctness 与首轮收敛 | Edit | error | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 119 | Capture correctness 与首轮收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 120 | Capture correctness 与首轮收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 121 | Capture correctness 与首轮收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 122 | Capture correctness 与首轮收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 123 | Capture correctness 与首轮收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 124 | Capture correctness 与首轮收敛 | Edit | error | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 125 | Capture correctness 与首轮收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 126 | Capture correctness 与首轮收敛 | Edit | ok | <candidate-repository>\tests\realtime_capture.cpp |
| 127 | Capture correctness 与首轮收敛 | Edit | ok | <candidate-repository>\tests\realtime_capture.cpp |
| 128 | Capture correctness 与首轮收敛 | PowerShell | warning | 验证 dedicated linear export |
| 129 | Capture correctness 与首轮收敛 | PowerShell | ok | 运行完整 one-shot export |
| 130 | Capture correctness 与首轮收敛 | Read | ok | <user-home>\AppData\Local\Temp\prt-current-capture\cases\baseline\realtime.png |
| 131 | Capture correctness 与首轮收敛 | PowerShell | ok | 核对 current export 文件 |
| 132 | Capture correctness 与首轮收敛 | Agent | ok | 复审渲染改动 |
| 133 | Capture correctness 与首轮收敛 | TodoWrite | ok | 更新任务列表 |
| 134 | Capture correctness 与首轮收敛 | PowerShell | ok | 运行多 case rendering diagnostics |
| 135 | Capture correctness 与首轮收敛 | TaskOutput | ok | {"task_id":"bthv14p7z","block":true,"timeout":[omitted]} |
| 136 | Capture correctness 与首轮收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 137 | Capture correctness 与首轮收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 138 | Capture correctness 与首轮收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 139 | Capture correctness 与首轮收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 140 | Capture correctness 与首轮收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 141 | Capture correctness 与首轮收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 142 | Capture correctness 与首轮收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 143 | Capture correctness 与首轮收敛 | Edit | ok | <candidate-repository>\tests\realtime_capture.cpp |
| 144 | Capture correctness 与首轮收敛 | Edit | ok | <candidate-repository>\tests\realtime_capture.cpp |
| 145 | Capture correctness 与首轮收敛 | Edit | ok | <candidate-repository>\tests\realtime_capture.cpp |
| 146 | Capture correctness 与首轮收敛 | PowerShell | warning | 验证 export failure cleanup |
| 147 | Capture correctness 与首轮收敛 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 148 | Capture correctness 与首轮收敛 | PowerShell | ok | 复核 final export determinism |
| 149 | Capture correctness 与首轮收敛 | Grep | ok | <candidate-repository>\README.md |
| 150 | Capture correctness 与首轮收敛 | Read | ok | <candidate-repository>\README.md |
| 151 | Capture correctness 与首轮收敛 | PowerShell | warning | 查看当前修改概况 |
| 152 | Capture correctness 与首轮收敛 | Glob | ok | <candidate-repository> |
| 153 | Capture correctness 与首轮收敛 | PowerShell | error | 删除失败 agent 创建的 worktrees |
| 154 | Capture correctness 与首轮收敛 | Edit | ok | <candidate-repository>\README.md |
| 155 | Capture correctness 与首轮收敛 | Edit | ok | <candidate-repository>\README.md |
| 156 | Capture correctness 与首轮收敛 | Edit | ok | <candidate-repository>\README.md |
| 157 | Probe validity 与空间插值重构 | PowerShell | warning | 检查 diff whitespace errors |
| 158 | Probe validity 与空间插值重构 | PowerShell | warning | 运行最终 regression tests |
| 159 | Probe validity 与空间插值重构 | TaskOutput | ok | {"task_id":"a7094d148c7a2fb71","block":false,"timeout":[omitted]} |
| 160 | Probe validity 与空间插值重构 | Grep | ok | <candidate-repository> |
| 161 | Probe validity 与空间插值重构 | PowerShell | warning | 验证 automation non-zero failures |
| 162 | Probe validity 与空间插值重构 | PowerShell | warning | 汇总最终工作树状态 |
| 163 | Probe validity 与空间插值重构 | TaskOutput | warning | {"task_id":"a7094d148c7a2fb71","block":true,"timeout":[omitted]} |
| 164 | Probe validity 与空间插值重构 | TodoWrite | ok | 更新任务列表 |
| 165 | Probe validity 与空间插值重构 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 166 | Probe validity 与空间插值重构 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 167 | Probe validity 与空间插值重构 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 168 | Probe validity 与空间插值重构 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 169 | Probe validity 与空间插值重构 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 170 | Probe validity 与空间插值重构 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 171 | Probe validity 与空间插值重构 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 172 | Probe validity 与空间插值重构 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 173 | Probe validity 与空间插值重构 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 174 | Probe validity 与空间插值重构 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 175 | Probe validity 与空间插值重构 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 176 | Probe validity 与空间插值重构 | PowerShell | warning | 验证 GL failure 与 automation 修复 |
| 177 | Probe validity 与空间插值重构 | PowerShell | ok | 验证 review 修复后的 one-shot |
| 178 | Probe validity 与空间插值重构 | PowerShell | ok | 验证 invalid automation input 失败 |
| 179 | Probe validity 与空间插值重构 | Grep | ok | <candidate-repository>\includes\GI\probe.h |
| 180 | Probe validity 与空间插值重构 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 181 | Probe validity 与空间插值重构 | Grep | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 182 | Probe validity 与空间插值重构 | TodoWrite | ok | 更新任务列表 |
| 183 | Probe validity 与空间插值重构 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 184 | Probe validity 与空间插值重构 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 185 | Probe validity 与空间插值重构 | Grep | ok | <candidate-repository>\includes\GI\probe.h |
| 186 | Probe validity 与空间插值重构 | Read | warning | <candidate-repository>\tests\prt_numerics.cpp |
| 187 | Probe validity 与空间插值重构 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 188 | Probe validity 与空间插值重构 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 189 | Probe validity 与空间插值重构 | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 190 | Probe validity 与空间插值重构 | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 191 | Probe validity 与空间插值重构 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 192 | Probe validity 与空间插值重构 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 193 | Probe validity 与空间插值重构 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 194 | Probe validity 与空间插值重构 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 195 | Probe validity 与空间插值重构 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 196 | Probe validity 与空间插值重构 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 197 | Probe validity 与空间插值重构 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 198 | Probe validity 与空间插值重构 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 199 | Probe validity 与空间插值重构 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 200 | Probe validity 与空间插值重构 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 201 | Probe validity 与空间插值重构 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 202 | Probe validity 与空间插值重构 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 203 | Probe validity 与空间插值重构 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 204 | Probe validity 与空间插值重构 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 205 | Probe validity 与空间插值重构 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 206 | Probe validity 与空间插值重构 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 207 | Probe validity 与空间插值重构 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 208 | Probe validity 与空间插值重构 | Edit | ok | <candidate-repository>\tests\prt_numerics.cpp |
| 209 | Probe validity 与空间插值重构 | Edit | ok | <candidate-repository>\tests\prt_numerics.cpp |
| 210 | Probe validity 与空间插值重构 | Grep | ok | <candidate-repository>\README.md |
| 211 | Probe validity 与空间插值重构 | Edit | ok | <candidate-repository>\README.md |
| 212 | Probe validity 与空间插值重构 | TodoWrite | ok | 更新任务列表 |
| 213 | Probe validity 与空间插值重构 | PowerShell | warning | 运行完整项目测试 |
| 214 | Numerical robustness 与 automation hardening | Read | ok | <candidate-repository>\realtime-render-contract.json |
| 215 | Numerical robustness 与 automation hardening | Grep | warning | <candidate-repository> |
| 216 | Numerical robustness 与 automation hardening | Read | ok | <candidate-repository>\README.md |
| 217 | Numerical robustness 与 automation hardening | PowerShell | warning | 运行 validity-aware one-shot export |
| 218 | Numerical robustness 与 automation hardening | PowerShell | ok | 运行 validity-aware one-shot export |
| 219 | Numerical robustness 与 automation hardening | PowerShell | ok | 核对 one-shot export 输出 |
| 220 | Numerical robustness 与 automation hardening | Read | ok | <user-home>\AppData\Local\Temp\prt-validity-export-a\cases\validity-a\state.json |
| 221 | Numerical robustness 与 automation hardening | PowerShell | ok | 验证 one-shot export 确定性 |
| 222 | Numerical robustness 与 automation hardening | Bash | ok | 比较两次 PFM export 差异 |
| 223 | Numerical robustness 与 automation hardening | Grep | ok | <candidate-repository>\src\getting_started\GIApplication |
| 224 | Numerical robustness 与 automation hardening | Grep | ok | <candidate-repository>\includes\GI\probe.h |
| 225 | Numerical robustness 与 automation hardening | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 226 | Numerical robustness 与 automation hardening | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 227 | Numerical robustness 与 automation hardening | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 228 | Numerical robustness 与 automation hardening | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 229 | Numerical robustness 与 automation hardening | PowerShell | warning | 重建并运行完整测试 |
| 230 | Numerical robustness 与 automation hardening | PowerShell | ok | 重复 export 并验证确定性 |
| 231 | Numerical robustness 与 automation hardening | PowerShell | ok | 核对确定性 export 输出 |
| 232 | Numerical robustness 与 automation hardening | Bash | ok | 检查 PFM 数值范围 |
| 233 | Numerical robustness 与 automation hardening | PowerShell | ok | 运行零能量 one-shot export |
| 234 | Numerical robustness 与 automation hardening | Bash | ok | 验证零能量 indirect 输出 |
| 235 | Numerical robustness 与 automation hardening | PowerShell | ok | 验证无效 environment 返回失败 |
| 236 | Numerical robustness 与 automation hardening | Agent | ok | 审查渲染物理正确性 |
| 237 | Numerical robustness 与 automation hardening | Agent | ok | 审查GL导出可靠性 |
| 238 | Numerical robustness 与 automation hardening | Grep | ok | <candidate-repository> |
| 239 | Numerical robustness 与 automation hardening | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 240 | Numerical robustness 与 automation hardening | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 241 | Numerical robustness 与 automation hardening | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 242 | Numerical robustness 与 automation hardening | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 243 | Numerical robustness 与 automation hardening | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 244 | Numerical robustness 与 automation hardening | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 245 | Numerical robustness 与 automation hardening | Grep | ok | <candidate-repository>\README.md |
| 246 | Numerical robustness 与 automation hardening | Edit | ok | <candidate-repository>\README.md |
| 247 | Numerical robustness 与 automation hardening | PowerShell | warning | 验证 Probe spacing uniform 改动 |
| 248 | Numerical robustness 与 automation hardening | Grep | ok | <candidate-repository>\includes\GI\probe.h |
| 249 | Numerical robustness 与 automation hardening | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 250 | Numerical robustness 与 automation hardening | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 251 | Numerical robustness 与 automation hardening | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 252 | Numerical robustness 与 automation hardening | Read | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 253 | Numerical robustness 与 automation hardening | Grep | ok | <candidate-repository>\tests\realtime_capture.cpp |
| 254 | Numerical robustness 与 automation hardening | Read | warning | <candidate-repository>\tests\realtime_capture.cpp |
| 255 | Numerical robustness 与 automation hardening | PowerShell | ok | 显示当前工作树状态 |
| 256 | Numerical robustness 与 automation hardening | PowerShell | warning | 检查改动统计与 contract diff |
| 257 | Numerical robustness 与 automation hardening | Grep | ok | <candidate-repository>\src\getting_started\GIApplication |
| 258 | Numerical robustness 与 automation hardening | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 259 | Numerical robustness 与 automation hardening | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 260 | Numerical robustness 与 automation hardening | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 261 | Numerical robustness 与 automation hardening | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 262 | Numerical robustness 与 automation hardening | PowerShell | warning | 验证 SSAA resolve 错误传播 |
| 263 | Numerical robustness 与 automation hardening | PowerShell | ok | 运行最终 one-shot export |
| 264 | Numerical robustness 与 automation hardening | PowerShell | ok | 核对最终 export ABI |
| 265 | Numerical robustness 与 automation hardening | Bash | ok | 检查最终 indirect PFM 数值 |
| 266 | Numerical robustness 与 automation hardening | TodoWrite | ok | 更新任务列表 |
| 267 | Numerical robustness 与 automation hardening | PowerShell | warning | 检查 diff whitespace 错误 |
| 268 | Numerical robustness 与 automation hardening | Grep | warning | <candidate-repository>\src\getting_started\GIApplication |
| 269 | Numerical robustness 与 automation hardening | Grep | ok | <candidate-repository>\tests\prt_numerics.cpp |
| 270 | Numerical robustness 与 automation hardening | Grep | ok | <candidate-repository>\README.md |
| 271 | Numerical robustness 与 automation hardening | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 272 | 最终复审、回归测试与收敛 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 273 | 最终复审、回归测试与收敛 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 274 | 最终复审、回归测试与收敛 | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 275 | 最终复审、回归测试与收敛 | PowerShell | ok | 确认 render contract 未修改 |
| 276 | 最终复审、回归测试与收敛 | Grep | warning | <candidate-repository>\includes |
| 277 | 最终复审、回归测试与收敛 | Read | warning | <candidate-repository>\includes\learnopengl\shader_m.h |
| 278 | 最终复审、回归测试与收敛 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 279 | 最终复审、回归测试与收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 280 | 最终复审、回归测试与收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 281 | 最终复审、回归测试与收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 282 | 最终复审、回归测试与收敛 | Edit | ok | <candidate-repository>\README.md |
| 283 | 最终复审、回归测试与收敛 | PowerShell | warning | 验证 atomic export 与资源清理 |
| 284 | 最终复审、回归测试与收敛 | PowerShell | ok | 验证 atomic one-shot export |
| 285 | 最终复审、回归测试与收敛 | PowerShell | ok | 验证缺少 output root 失败 |
| 286 | 最终复审、回归测试与收敛 | TodoWrite | ok | 更新任务列表 |
| 287 | 最终复审、回归测试与收敛 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 288 | 最终复审、回归测试与收敛 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.vs |
| 289 | 最终复审、回归测试与收敛 | Grep | ok | <candidate-repository>\includes\GI\probe.h |
| 290 | 最终复审、回归测试与收敛 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 291 | 最终复审、回归测试与收敛 | Bash | ok | 检查最终 PNG 数值范围 |
| 292 | 最终复审、回归测试与收敛 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 293 | 最终复审、回归测试与收敛 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 294 | 最终复审、回归测试与收敛 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 295 | 最终复审、回归测试与收敛 | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 296 | 最终复审、回归测试与收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 297 | 最终复审、回归测试与收敛 | PowerShell | warning | 验证 automation input 隔离 |
| 298 | 最终复审、回归测试与收敛 | PowerShell | ok | 运行最新 one-shot export |
| 299 | 最终复审、回归测试与收敛 | PowerShell | ok | 复核最新 export 确定性 |
| 300 | 最终复审、回归测试与收敛 | PowerShell | ok | 核对最新 export metadata |
| 301 | 最终复审、回归测试与收敛 | PowerShell | warning | 执行最终工作树与 contract 检查 |
| 302 | 最终复审、回归测试与收敛 | PowerShell | ok | 运行 cube contact lighting diagnostic |
| 303 | 最终复审、回归测试与收敛 | Bash | ok | 检查 contact diagnostic PFM |
| 304 | 最终复审、回归测试与收敛 | Grep | ok | <candidate-repository> |
| 305 | 最终复审、回归测试与收敛 | PowerShell | warning | 验证 stale case 拒绝行为 |
| 306 | 最终复审、回归测试与收敛 | TodoWrite | ok | 更新任务列表 |
| 307 | 最终复审、回归测试与收敛 | PowerShell | warning | 复核最终 diff 与工作树 |
| 308 | 最终复审、回归测试与收敛 | PowerShell | ok | 确认 public render contract 无改动 |
| 309 | 最终复审、回归测试与收敛 | TaskOutput | error | {"task_id":"a0c4a61d389b0299a","block":true,"timeout":[omitted]} |
| 310 | 最终复审、回归测试与收敛 | TaskOutput | error | {"task_id":"af4539bdcbd873520","block":true,"timeout":[omitted]} |
| 311 | 最终复审、回归测试与收敛 | SendMessage | ok | {"to":"a0c4a61d389b0299a","summary":"请返回当前审查结论","message":"请现在结束审查并返回已验证 findings；若无 findings，请明确说明。","type":"message","recipient":"a0c4a61d389b0299a","content":"请现在结束审查并返回已验证 findings；若无 finding…"} |
| 312 | 最终复审、回归测试与收敛 | SendMessage | ok | {"to":"af4539bdcbd873520","summary":"请返回当前审查结论","message":"请现在结束审查并返回已验证 findings；若无 findings，请明确说明。","type":"message","recipient":"af4539bdcbd873520","content":"请现在结束审查并返回已验证 findings；若无 finding…"} |
| 313 | 最终复审、回归测试与收敛 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 314 | 最终复审、回归测试与收敛 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 315 | 最终复审、回归测试与收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 316 | 最终复审、回归测试与收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 317 | 最终复审、回归测试与收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 318 | 最终复审、回归测试与收敛 | PowerShell | warning | 验证 GL pass 错误传播 |
| 319 | 最终复审、回归测试与收敛 | PowerShell | ok | 验证 GL pass 检查 one-shot |
| 320 | 最终复审、回归测试与收敛 | PowerShell | warning | 最终检查 whitespace contract 与状态 |
| 321 | 最终复审、回归测试与收敛 | TodoWrite | ok | 更新任务列表 |
| 322 | 最终复审、回归测试与收敛 | TaskOutput | error | {"task_id":"a0c4a61d389b0299a","block":true,"timeout":[omitted]} |
| 323 | 最终复审、回归测试与收敛 | TaskOutput | error | {"task_id":"af4539bdcbd873520","block":true,"timeout":[omitted]} |
| 324 | 最终复审、回归测试与收敛 | Grep | ok | <candidate-repository>\includes\GI\probe.h |
| 325 | 最终复审、回归测试与收敛 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 326 | 最终复审、回归测试与收敛 | Grep | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 327 | 最终复审、回归测试与收敛 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 328 | 最终复审、回归测试与收敛 | Grep | ok | <candidate-repository>\tests\prt_numerics.cpp |

</details>

<details>
<summary><strong>Agent 最终回复</strong></summary>

<pre>本轮 realtime rendering 改进已完成并收敛，未修改 public render contract。

### 主要改进

- Probe sampling 改为 deterministic 256-direction spherical Fibonacci sequence，移除 wall clock/global RNG 依赖。
- Probe Ray 只为 nearest triangle hit 计算 Surfel source radiance，避免多余且错误的中间 shading。
- GI transport 改为 incoming radiance SH projection + analytic Lambert convolution：
  - `A0=π`
  - `A1=2π/3`
  - `A2=π/4`
- Solid 内 Probe 标记为 invalid，不再通过移除 cube geometry 让 Probe 人为“看穿”实体。
- 新增 Probe validity 3D texture：
  - coefficient 与 validity 使用相同 trilinear interpolation。
  - 按有效 Probe weight sum 重新归一化。
  - invalid corners 不再造成 cube 周围非物理暗化。
  - 八个 corners 全部 invalid 时返回零 irradiance。
- Receiver normal offset 由实际 Probe grid spacing 推导，不再在 shader 中重复硬编码 grid dimensions。
- CPU/GPU direct PBR 统一使用 height-correlated Smith GGX visibility。
- 增加 grazing angle、`V+L` 退化和 finite-value 保护。
- Point-light shadow：
  - far plane 覆盖完整 scene bounds。
  - near plane只排除 point-light singularity。
  - bias 改为 receiver distance、cubemap texel footprint 和 surface slope 相关。
- Automation 完全隔离 keyboard、cursor 和 scroll input。
- Environment enum/boolean 参数改为严格解析。
- Automation PNG 改为从 dedicated RGB32F linear framebuffer 读取，由 CPU 执行 Reinhard、exact sRGB 和 round-to-nearest RGB8。
- 增加 shadow FBO、shadow draw pass、scene shading pass、SSAA resolve 和 GPU readback 的错误传播，automation 失败时返回 non-zero。
- 输出先写入同目录 temporary files，flush 后再 commit 为最终文件；失败会清理 partial files 和 case directory。
- 补齐 shadow framebuffer/texture 等 OpenGL resource cleanup。

关键实现位置：

- [probe.h:33](includes/GI/probe.h#L33)
- [probe.h:358](includes/GI/probe.h#L358)
- [probe.h:696](includes/GI/probe.h#L696)
- [light_casters.fs:39](src/getting_started/GIApplication/light_casters.fs#L39)
- [light_casters.fs:236](src/getting_started/GIApplication/light_casters.fs#L236)
- [main.cpp:432](src/getting_started/GIApplication/main.cpp#L432)
- [main.cpp:648](src/getting_started/GIApplication/main.cpp#L648)
- [main.cpp:1668](src/getting_started/GIApplication/main.cpp#L1668)
- [realtime_capture.h:107](src/getting_started/GIApplication/realtime_capture.h#L107)
- [realtime_capture.h:326](src/getting_started/GIApplication/realtime_capture.h#L326)

### Regression tests

新增或扩充了以下 numerical coverage：

- deterministic Probe sampling
- analytic Lambert SH convolution
- invalid Probe zero transport
- validity-aware trilinear normalization
- inverse-square point-light ratio
- grazing/degenerate PBR finite response
- compacted Surfel/Ray mapping
- occluded point-light energy leakage
- exact display encoding
- non-finite export cleanup
- stale case directory rejection

相关测试位于 [prt_numerics.cpp:107](tests/prt_numerics.cpp#L107) 和 [realtime_capture.cpp](tests/realtime_capture.cpp)。

### 验证结果

运行：

```powershell
python .\tools\test.py
```

结果：

```text
100% tests passed, 0 tests failed out of 5
```

实际 one-shot OpenGL export 验证：

- Process exit code：`0`
- 只生成：
  - `realtime.png`
  - `indirect-linear.pfm`
  - `state.json`
- PNG dimensions：`800x600`
- PFM dimensions：`800x600`
- PFM size：`5,760,016 bytes`
- PFM 所有值 finite
- Camera pose、light position/intensity 完整 round-trip
- 重复相同 state 导出 byte-identical：
  - PNG SHA-256：`E63E132C166AC78EB0693151320AC3705B7A3A9E7497E59720730437002FEFFF`
  - PFM SHA-256：`ED0D00D39A262A02C532F625B2801FFA9650C007E96DC4BAD9F2924C22DE14D5`
- Zero-intensity case 的 indirect buffer 严格全零。
- Cube-contact diagnostic 保持 finite、non-negative。
- 缺少 output root：exit `2`。
- 无效 `PRT_DYNAMIC`：exit `2`。
- Stale case directory：exit `1`，原有文件未被覆盖。
- `realtime-render-contract.json` 无任何改动。
- `git diff --check` 无 whitespace error。

### 剩余结构性限制

当前固定 SH3 coefficients 表示的是 Lambert-convolved irradiance，因此无法从中无损恢复完整 directional radiance 来计算精确 indirect GGX specular。加入未经物理验证的 heuristic 会比保留当前 diffuse-only indirect response 更差，尤其会违反“不用 gain/exposure 掩盖问题”的约束，因此本轮未加入此类补偿。

CPU Probe/Surfel intersection 和动态 source visibility 仍是主要性能瓶颈；后续若继续演进，合理方向是 deterministic BVH、缓存静态 Probe-Ray hit data，以及按完整 light generation 原子更新 coefficients。这些主要改善动态更新速度，而不会直接改变当前 static contract frame 的物理结果。

工作树中仍有早期 Agent isolation 遗留的未跟踪 [.claude/](.claude/) 目录。它未被修改、未纳入 rendering 改动，也不应提交；此前递归删除权限被拒绝，因此本轮保留。</pre>

</details>
