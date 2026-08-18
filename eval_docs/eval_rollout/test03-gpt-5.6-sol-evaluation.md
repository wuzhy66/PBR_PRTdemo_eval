# TEST03 · gpt-5.6-sol · Realtime rendering best-effort 全报告

> GitHub-readable evaluation report。本文件保留指标、过程分析和 tool-call 摘要，不嵌入体积过大的 tool input/output 或完整 Git diff。

## 最终结果

**Normalized improvement：`0.28633464` · Decision：`success`**

| Baseline A | Candidate B / Strict | Mean B−A | Cases | Strict / Excluded / Errors |
|---:|---:|---:|---:|---:|
| 0.81864903 | 0.87057609 | +0.05192707 | 200 | 200 / 0 / 0 |

`Normalized improvement` 是最终 coding improvement 分数；`Strict score` 是单个 renderer 对 offline reference 的绝对分数。

### 指标变化

| 指标 | 权重 | Baseline | Candidate | 变化 | 改善 | 退化 | 不变 |
|---|---:|---:|---:|---:|---:|---:|---:|
| FLIP perceptual score | 70% | 0.81916697 | 0.89722119 | +0.07805422 | 127 | 73 | 0 |
| Worst-patch FLIP | diagnostic | 0.60162365 | 0.76145977 | +0.15983613 | 108 | 92 | 0 |
| Indirect transport | 30% | 0.82374117 | 0.82790243 | +0.00416126 | 122 | 78 | 0 |
| Occlusion leak | diagnostic | 0.78038943 | 0.87630374 | +0.09591431 | 170 | 21 | 9 |
| Strict score | aggregate | 0.81864903 | 0.87057609 | +0.05192707 | 124 | 76 | 0 |

### Regression gates

| Gate | Required | Median delta | 改善 | 退化 | 不变 | 结果 |
|---|---:|---:|---:|---:|---:|---|
| Median FLIP delta | yes | +0.00870467 | 127 | 73 | 0 | PASS |
| Median worst-patch FLIP delta | yes | +0.00892218 | 108 | 92 | 0 | PASS |

## 总体判断

这是覆盖面最广、迭代最深的一次执行：同时修改 Probe transport、SH convolution、BRDF、shadow、reconstruction 和 capture correctness，并通过独立 review 撤销非物理 gain。正式 200-case 评测的 Normalized improvement 为 0.28633464，排名第四；Occlusion leak 提升最强但只作诊断，Indirect transport 平均收益很小，说明大规模改动在正式计分项上的收益并不均衡。

## 改动与实测评价

### `includes/GI/probe.h`

- 改动：256-direction deterministic Fibonacci、nearest-hit shading、radiance SH + analytic cosine convolution、correlated Smith GGX。
- 目标：降低 sampling/projection error，并统一物理 BRDF。
- 评测：Occlusion leak 平均提升 0.09591431，但 Indirect transport 仅提升 0.00416126；transport/BRDF 多项改动存在相互抵消。

### `light_casters.fs`

- 改动：resolution/slope-aware point-shadow bias、correlated Smith GGX、normal-directed Probe query offset。
- 目标：改善 shadow 与 geometry boundary reconstruction。
- 评测：完整 FLIP 平均提升 0.07805422；normal offset 与 shadow 改动仍造成 73 个 FLIP case 退化。

### `main.cpp`

- 改动：scene-bound shadow range、invalid Probe、root shader path、combined/indirect RGB32F capture 与 OpenGL cleanup。
- 目标：提高完整 pipeline correctness、determinism 与 ABI 稳定性。
- 评测：完整 pipeline correctness 改动覆盖广，Strict score 平均提升 0.05192707。

### `realtime_capture.h`

- 改动：CPU exact Reinhard+sRGB+rounding，写入失败清理 partial files。
- 目标：消除 default framebuffer/driver conversion 差异。
- 评测：cross-platform output correctness 有明确价值，但其独立画质贡献未做 ablation。

### `tests + README + .gitignore`

- 改动：新增 SH/sampling/display tests，同步 pipeline 文档并忽略 Agent worktree。
- 目标：锁定不变量并保持工作树可复现。
- 评测：测试覆盖强；正式 200-case 评测确认改动总体有效。

## 做得好的地方

- 将 incoming radiance SH projection 与 analytic clamped-cosine convolution 分离。
- nearest-hit 后再执行 source shading，并建立 determinism、zero-light 与 failure semantics 不变量。
- 独立 review 发现 validity renormalization 会形成 spatially varying gain，随后主动撤销。
- Occlusion leak 为 170 case 改善、21 case 退化、9 case 不变，是五组中该指标表现最强的方案。

## 风险与不足

- CPU/GPU BRDF 改为 correlated Smith GGX，与当前 offline reference 的 baseline geometry term 不完全一致。
- solid 内 Probe 清零再用 normal offset 查询，可能在 cube surface 附近产生能量丢失。
- Indirect transport 平均只提升 0.00416126，78 case 退化；大规模改动缺少逐项 ablation。
- 成功 subagent 混用 gpt-5.6-sol、deepseek-v4-pro 与 deepseek-v4-flash，因此结果不是纯主模型归因。

## 分项结论

| 维度 | 评价 | 说明 |
|---|---|---|
| 自主持续性 | 很强 | 经历多轮实现、独立 review、撤销和再验证。 |
| 物理建模 | 强但有 target mismatch 风险 | SH 与 shadow 依据清晰，BRDF 与 offline target 未完全对齐。 |
| 指标均衡 | 中等 | 诊断用 Occlusion leak 提升突出，但计分用 indirect transport 几乎持平。 |
| 模型归因 | 混合 | 主 agent 之外成功使用多个不同 backend model 的 subagent。 |
| 最终效果 | 成功 | Strict score 0.87057609，mean(B−A) +0.05192707，Normalized improvement 0.28633464。 |

## 执行概览

- Test：`TEST03`
- Main model：`gpt-5.6-sol`
- Claude Code：`2.1.233`
- Candidate / Baseline：`worktree-e3b0c44298fc` / `254e8a1`
- Tool calls：295（20 errors，34 warnings）
- Subagents：4 success / 8 attempts
- Git diff：0 files，+0 / -0，diff check `PASS`

### Tool 类型

| Tool | Calls |
|---|---:|
| Read | 94 |
| Edit | 80 |
| Grep | 36 |
| PowerShell | 33 |
| Glob | 17 |
| Bash | 12 |
| TodoWrite | 10 |
| Agent | 8 |
| TaskOutput | 2 |
| EnterPlanMode | 1 |
| Write | 1 |
| ExitPlanMode | 1 |

## 执行阶段

### #1–#61 · Plan 与广泛扫描

- 动作：进入 Plan Mode，尝试 subagent，系统读取 contract、shader、PRT、tests、capture 与 build path。
- 分析：覆盖面完整；四次初始 subagent 因 Windows worktree path 校验失败。
- 证据：建立完整 pipeline map 和 baseline regression。

### #62–#104 · Transport 与 BRDF

- 动作：实现 deterministic sampling、nearest-hit、analytic SH convolution、CPU/GPU BRDF 与 shadow 修改。
- 分析：核心算法链条连贯；同时改动多个变量，缺少单项 ablation。
- 证据：新增 numerics tests，并通过 transport/BRDF/shadow regression。

### #105–#168 · Capture correctness

- 动作：重构 combined/indirect RGB32F resolve/readback、CPU display transform、root shader path 和 failure cleanup。
- 分析：从 GI 扩展到完整 output correctness，符合新版任务目标。
- 证据：完成 one-shot、hash determinism 与 zero-intensity 检查。

### #169–#220 · 独立复查与文档

- 动作：运行最终 tests/export，引入成功 subagent review，补充 README 与 resource/capture 检查。
- 分析：通过独立审查寻找 confirmed issue，而不是只接受自己的实现。
- 证据：成功 subagent 开始参与；文档同步到新 pipeline。

### #221–#295 · Probe visibility 收敛

- 动作：实验 Probe validity、继续 review，撤销非物理 gain，完成 final determinism、zero-light 与 diff 检查。
- 分析：能根据 review 撤销高风险方案，是本次最重要的收敛行为。
- 证据：最终保留 zero invalid Probe + normal offset，移除 validity renormalization。

## Subagent

| 任务 | Requested | Actual | 状态 |
|---|---|---|---|
| 复查当前 rendering 修改 | opus | gpt-5.6-sol | success |
| 分析 dynamic GI 性能 | sonnet | deepseek-v4-pro | success |
| 审查 rendering 改动 | sonnet | deepseek-v4-pro | success |
| 最终独立代码审查 | haiku | deepseek-v4-flash | success |

## Git 文件变化

| File | Added | Deleted |
|---|---:|---:|

Worktree status：`clean`

<details>
<summary><strong>Tool-call 流程摘要</strong></summary>

| # | 阶段 | Tool | 状态 | 摘要 |
|---:|---|---|---|---|
| 1 | Plan 与广泛扫描 | EnterPlanMode | ok | {} |
| 2 | Plan 与广泛扫描 | TodoWrite | ok | 更新任务列表 |
| 3 | Plan 与广泛扫描 | Agent | error | 梳理渲染管线 |
| 4 | Plan 与广泛扫描 | Agent | error | 审查测试契约 |
| 5 | Plan 与广泛扫描 | Glob | ok | <candidate-repository> |
| 6 | Plan 与广泛扫描 | Glob | ok | <candidate-repository> |
| 7 | Plan 与广泛扫描 | Agent | error | 梳理渲染管线 |
| 8 | Plan 与广泛扫描 | Agent | error | 审查测试契约 |
| 9 | Plan 与广泛扫描 | Glob | ok | <candidate-repository> |
| 10 | Plan 与广泛扫描 | Glob | ok | <candidate-repository> |
| 11 | Plan 与广泛扫描 | Glob | ok | <candidate-repository> |
| 12 | Plan 与广泛扫描 | Glob | ok | <candidate-repository> |
| 13 | Plan 与广泛扫描 | Read | error | <candidate-repository>\realtime-render-contract.json |
| 14 | Plan 与广泛扫描 | Read | error | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 15 | Plan 与广泛扫描 | Read | error | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 16 | Plan 与广泛扫描 | Read | error | <candidate-repository>\src\getting_started\GIApplication\ssaa_resolve.fs |
| 17 | Plan 与广泛扫描 | Read | error | <candidate-repository>\src\getting_started\GIApplication\render_contract.h |
| 18 | Plan 与广泛扫描 | Read | error | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 19 | Plan 与广泛扫描 | Read | error | <candidate-repository>\tools\test.py |
| 20 | Plan 与广泛扫描 | Read | ok | <candidate-repository>\realtime-render-contract.json |
| 21 | Plan 与广泛扫描 | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 22 | Plan 与广泛扫描 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 23 | Plan 与广泛扫描 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\ssaa_resolve.fs |
| 24 | Plan 与广泛扫描 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\render_contract.h |
| 25 | Plan 与广泛扫描 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 26 | Plan 与广泛扫描 | Read | warning | <candidate-repository>\tools\test.py |
| 27 | Plan 与广泛扫描 | Glob | ok | <candidate-repository> |
| 28 | Plan 与广泛扫描 | Glob | ok | <candidate-repository> |
| 29 | Plan 与广泛扫描 | Grep | ok | <candidate-repository> |
| 30 | Plan 与广泛扫描 | Grep | ok | <candidate-repository> |
| 31 | Plan 与广泛扫描 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 32 | Plan 与广泛扫描 | Read | warning | <candidate-repository>\tests\prt_numerics.cpp |
| 33 | Plan 与广泛扫描 | Read | warning | <candidate-repository>\tests\render_contract.cpp |
| 34 | Plan 与广泛扫描 | Read | warning | <candidate-repository>\tests\realtime_capture.cpp |
| 35 | Plan 与广泛扫描 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.vs |
| 36 | Plan 与广泛扫描 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.gs |
| 37 | Plan 与广泛扫描 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.fs |
| 38 | Plan 与广泛扫描 | Glob | ok | <candidate-repository> |
| 39 | Plan 与广泛扫描 | Glob | ok | <candidate-repository> |
| 40 | Plan 与广泛扫描 | Read | ok | <candidate-repository>\CMakeLists.txt |
| 41 | Plan 与广泛扫描 | Read | ok | <candidate-repository>\tools\build.py |
| 42 | Plan 与广泛扫描 | Grep | warning | <candidate-repository> |
| 43 | Plan 与广泛扫描 | Bash | ok | 查看近期提交和工作树状态 |
| 44 | Plan 与广泛扫描 | Glob | ok | <candidate-repository> |
| 45 | Plan 与广泛扫描 | Glob | ok | <candidate-repository> |
| 46 | Plan 与广泛扫描 | Glob | ok | <candidate-repository> |
| 47 | Plan 与广泛扫描 | Grep | ok | <candidate-repository> |
| 48 | Plan 与广泛扫描 | Read | ok | <candidate-repository>\README.md |
| 49 | Plan 与广泛扫描 | Read | ok | <candidate-repository>\README.md |
| 50 | Plan 与广泛扫描 | Read | ok | <candidate-repository>\tools\_tooling.py |
| 51 | Plan 与广泛扫描 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication |
| 52 | Plan 与广泛扫描 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 53 | Plan 与广泛扫描 | Grep | ok | <candidate-repository>\README.md |
| 54 | Plan 与广泛扫描 | Glob | ok | <user-home>\.claude\plans |
| 55 | Plan 与广泛扫描 | TodoWrite | ok | 更新任务列表 |
| 56 | Plan 与广泛扫描 | Write | ok | <user-home>\.claude\plans\realtime-rendering-convergence.md |
| 57 | Plan 与广泛扫描 | TodoWrite | ok | 更新任务列表 |
| 58 | Plan 与广泛扫描 | ExitPlanMode | ok | {} |
| 59 | Plan 与广泛扫描 | TodoWrite | ok | 更新任务列表 |
| 60 | Plan 与广泛扫描 | PowerShell | ok | 运行完整 regression tests 建立基线 |
| 61 | Plan 与广泛扫描 | Grep | ok | <candidate-repository>\README.md |
| 62 | Transport 与 BRDF | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 63 | Transport 与 BRDF | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 64 | Transport 与 BRDF | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 65 | Transport 与 BRDF | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 66 | Transport 与 BRDF | Grep | ok | <candidate-repository>\includes\GI\probe.h |
| 67 | Transport 与 BRDF | Bash | ok | 替换 Probe deterministic sampling 实现 |
| 68 | Transport 与 BRDF | Bash | ok | 优化 Surfel nearest-hit shading |
| 69 | Transport 与 BRDF | Bash | ok | 改用 SH analytic cosine convolution |
| 70 | Transport 与 BRDF | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 71 | Transport 与 BRDF | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 72 | Transport 与 BRDF | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 73 | Transport 与 BRDF | Bash | ok | 增加 Probe sampling 与 SH tests |
| 74 | Transport 与 BRDF | PowerShell | ok | 验证 Probe transport 修改 |
| 75 | Transport 与 BRDF | Grep | ok | <candidate-repository>\includes\GI\probe.h |
| 76 | Transport 与 BRDF | Read | warning | <user-home>\AppData\Local\Temp\claude\d--PBR-PRTdemo-TEST03\ce531919-fa23-4677-b923-d68638935941\tasks\byio1cn4h.output |
| 77 | Transport 与 BRDF | Read | warning | <user-home>\AppData\Local\Temp\claude\d--PBR-PRTdemo-TEST03\ce531919-fa23-4677-b923-d68638935941\tasks\bldr7hzpa.output |
| 78 | Transport 与 BRDF | Edit | ok | <candidate-repository>\tests\prt_numerics.cpp |
| 79 | Transport 与 BRDF | PowerShell | ok | 运行 center one-shot baseline export |
| 80 | Transport 与 BRDF | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 81 | Transport 与 BRDF | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 82 | Transport 与 BRDF | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 83 | Transport 与 BRDF | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 84 | Transport 与 BRDF | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 85 | Transport 与 BRDF | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 86 | Transport 与 BRDF | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 87 | Transport 与 BRDF | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 88 | Transport 与 BRDF | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 89 | Transport 与 BRDF | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 90 | Transport 与 BRDF | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 91 | Transport 与 BRDF | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 92 | Transport 与 BRDF | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 93 | Transport 与 BRDF | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 94 | Transport 与 BRDF | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 95 | Transport 与 BRDF | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 96 | Transport 与 BRDF | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 97 | Transport 与 BRDF | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 98 | Transport 与 BRDF | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 99 | Transport 与 BRDF | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 100 | Transport 与 BRDF | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 101 | Transport 与 BRDF | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 102 | Transport 与 BRDF | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 103 | Transport 与 BRDF | Grep | ok | <candidate-repository> |
| 104 | Transport 与 BRDF | PowerShell | ok | 运行 transport、BRDF 与 shadow tests |
| 105 | Capture correctness | Grep | ok | <candidate-repository> |
| 106 | Capture correctness | Bash | ok | 改为 CPU exact display export |
| 107 | Capture correctness | Edit | error | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 108 | Capture correctness | Read | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 109 | Capture correctness | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 110 | Capture correctness | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 111 | Capture correctness | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 112 | Capture correctness | Bash | ok | 增加 combined linear export target |
| 113 | Capture correctness | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 114 | Capture correctness | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 115 | Capture correctness | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 116 | Capture correctness | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 117 | Capture correctness | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 118 | Capture correctness | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 119 | Capture correctness | Edit | ok | <candidate-repository>\tests\realtime_capture.cpp |
| 120 | Capture correctness | Bash | ok | 增加 exact display transform tests |
| 121 | Capture correctness | Read | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 122 | Capture correctness | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 123 | Capture correctness | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 124 | Capture correctness | PowerShell | ok | 验证 linear export 与 display transform |
| 125 | Capture correctness | Read | warning | <user-home>\AppData\Local\Temp\claude\d--PBR-PRTdemo-TEST03\ce531919-fa23-4677-b923-d68638935941\tasks\b31nmhz4k.output |
| 126 | Capture correctness | Grep | ok | <candidate-repository>\tools\launch_renderdoc.py |
| 127 | Capture correctness | PowerShell | ok | 在 runtime 目录运行 one-shot export |
| 128 | Capture correctness | Read | warning | <candidate-repository>\includes\learnopengl\shader_m.h |
| 129 | Capture correctness | Read | ok | <candidate-repository>\includes\learnopengl\filesystem.h |
| 130 | Capture correctness | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 131 | Capture correctness | Read | warning | <user-home>\AppData\Local\Temp\claude\d--PBR-PRTdemo-TEST03\ce531919-fa23-4677-b923-d68638935941\tasks\bnc39pz76.output |
| 132 | Capture correctness | Read | warning | <user-home>\AppData\Local\Temp\claude\d--PBR-PRTdemo-TEST03\ce531919-fa23-4677-b923-d68638935941\tasks\brjo9etxn.output |
| 133 | Capture correctness | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 134 | Capture correctness | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 135 | Capture correctness | PowerShell | ok | 重新构建并运行完整 tests |
| 136 | Capture correctness | Read | ok | <user-home>\AppData\Local\Temp\claude\d--PBR-PRTdemo-TEST03\ce531919-fa23-4677-b923-d68638935941\tasks\b7jcjg6gt.output |
| 137 | Capture correctness | PowerShell | ok | 从 repository root 运行 one-shot export |
| 138 | Capture correctness | TodoWrite | ok | 更新任务列表 |
| 139 | Capture correctness | Agent | ok | 复查当前 rendering 修改 |
| 140 | Capture correctness | Read | warning | <user-home>\AppData\Local\Temp\claude\d--PBR-PRTdemo-TEST03\ce531919-fa23-4677-b923-d68638935941\tasks\bwg8nxz3n.output |
| 141 | Capture correctness | Read | warning | <user-home>\AppData\Local\Temp\claude\d--PBR-PRTdemo-TEST03\ce531919-fa23-4677-b923-d68638935941\tasks\b4burwfko.output |
| 142 | Capture correctness | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 143 | Capture correctness | PowerShell | ok | 重建 renderer 验证 readback 修复 |
| 144 | Capture correctness | PowerShell | ok | 比较 two one-shot output hashes |
| 145 | Capture correctness | Read | ok | <user-home>\AppData\Local\Temp\claude\d--PBR-PRTdemo-TEST03\ce531919-fa23-4677-b923-d68638935941\tasks\bhygs5cd4.output |
| 146 | Capture correctness | PowerShell | ok | 运行并 hash one-shot output |
| 147 | Capture correctness | PowerShell | ok | 运行 zero-intensity physical invariant case |
| 148 | Capture correctness | Read | ok | <user-home>\AppData\Local\Temp\claude\d--PBR-PRTdemo-TEST03\ce531919-fa23-4677-b923-d68638935941\tasks\beazumttk.output |
| 149 | Capture correctness | PowerShell | ok | 重复 render 并验证 byte determinism |
| 150 | Capture correctness | Read | ok | <user-home>\AppData\Local\Temp\claude\d--PBR-PRTdemo-TEST03\ce531919-fa23-4677-b923-d68638935941\tasks\bbt27yxw5.output |
| 151 | Capture correctness | PowerShell | ok | 检查 zero-intensity output invariants |
| 152 | Capture correctness | PowerShell | ok | 验证 zero-light PNG 为黑色 |
| 153 | Capture correctness | Read | ok | <user-home>\AppData\Local\Temp\claude\d--PBR-PRTdemo-TEST03\ce531919-fa23-4677-b923-d68638935941\tasks\bxdqanxqp.output |
| 154 | Capture correctness | Read | ok | <user-home>\AppData\Local\Temp\prt-one-shot-c\cases\center\realtime.png |
| 155 | Capture correctness | Read | ok | <user-home>\AppData\Local\Temp\prt-one-shot-c\cases\center\indirect-linear.pfm |
| 156 | Capture correctness | TodoWrite | ok | 更新任务列表 |
| 157 | Capture correctness | Grep | ok | <candidate-repository>\includes\learnopengl\shader_m.h |
| 158 | Capture correctness | Read | warning | <candidate-repository>\includes\learnopengl\shader_m.h |
| 159 | Capture correctness | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 160 | Capture correctness | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 161 | Capture correctness | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 162 | Capture correctness | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 163 | Capture correctness | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 164 | Capture correctness | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 165 | Capture correctness | Bash | ok | 清理失败 export 的 partial files |
| 166 | Capture correctness | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 167 | Capture correctness | Read | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 168 | Capture correctness | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 169 | 独立复查与文档 | PowerShell | ok | 运行最终 regression tests |
| 170 | 独立复查与文档 | Bash | ok | 检查修改统计与 whitespace errors |
| 171 | 独立复查与文档 | Bash | warning | 审查 shader 与 render pass diff |
| 172 | 独立复查与文档 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 173 | 独立复查与文档 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 174 | 独立复查与文档 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 175 | 独立复查与文档 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 176 | 独立复查与文档 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 177 | 独立复查与文档 | Read | warning | <user-home>\AppData\Local\Temp\claude\d--PBR-PRTdemo-TEST03\ce531919-fa23-4677-b923-d68638935941\tasks\bzvs85dws.output |
| 178 | 独立复查与文档 | PowerShell | ok | 验证 present 与 cleanup 最终修改 |
| 179 | 独立复查与文档 | Read | warning | <user-home>\AppData\Local\Temp\claude\d--PBR-PRTdemo-TEST03\ce531919-fa23-4677-b923-d68638935941\tasks\a7def6fcbfbba30ea.output |
| 180 | 独立复查与文档 | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 181 | 独立复查与文档 | Read | warning | <user-home>\AppData\Local\Temp\claude\d--PBR-PRTdemo-TEST03\ce531919-fa23-4677-b923-d68638935941\tasks\buujvb2y5.output |
| 182 | 独立复查与文档 | PowerShell | ok | 执行最终 one-shot export 验证 |
| 183 | 独立复查与文档 | Bash | ok | 检查最终 diff 与 working tree |
| 184 | 独立复查与文档 | Read | ok | <candidate-repository>\.gitignore |
| 185 | 独立复查与文档 | Glob | ok | <candidate-repository> |
| 186 | 独立复查与文档 | TodoWrite | ok | 更新任务列表 |
| 187 | 独立复查与文档 | PowerShell | ok | 检查工作树与 diff 格式 |
| 188 | 独立复查与文档 | Grep | ok | <candidate-repository>\tools |
| 189 | 独立复查与文档 | Grep | ok | <candidate-repository> |
| 190 | 独立复查与文档 | Read | ok | <candidate-repository>\README.md |
| 191 | 独立复查与文档 | Read | ok | <candidate-repository>\README.md |
| 192 | 独立复查与文档 | Read | ok | <candidate-repository>\README.md |
| 193 | 独立复查与文档 | Read | ok | <candidate-repository>\README.md |
| 194 | 独立复查与文档 | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 195 | 独立复查与文档 | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 196 | 独立复查与文档 | Agent | ok | 审查 rendering 改动 |
| 197 | 独立复查与文档 | PowerShell | ok | 运行并核验 one-shot export |
| 198 | 独立复查与文档 | Agent | ok | 分析 dynamic GI 性能 |
| 199 | 独立复查与文档 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 200 | 独立复查与文档 | Grep | ok | <candidate-repository> |
| 201 | 独立复查与文档 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\gl_debug_labels.h |
| 202 | 独立复查与文档 | Read | warning | <candidate-repository>\tests\realtime_capture.cpp |
| 203 | 独立复查与文档 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 204 | 独立复查与文档 | Grep | ok | <candidate-repository> |
| 205 | 独立复查与文档 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\render_contract.h |
| 206 | 独立复查与文档 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication |
| 207 | 独立复查与文档 | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 208 | 独立复查与文档 | Edit | ok | <candidate-repository>\README.md |
| 209 | 独立复查与文档 | Edit | ok | <candidate-repository>\README.md |
| 210 | 独立复查与文档 | Read | ok | <candidate-repository>\README.md |
| 211 | 独立复查与文档 | Edit | ok | <candidate-repository>\README.md |
| 212 | 独立复查与文档 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 213 | 独立复查与文档 | Grep | ok | <candidate-repository>\tests\prt_numerics.cpp |
| 214 | 独立复查与文档 | Read | ok | <candidate-repository>\tests\prt_numerics.cpp |
| 215 | 独立复查与文档 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 216 | 独立复查与文档 | Grep | ok | <candidate-repository> |
| 217 | 独立复查与文档 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 218 | 独立复查与文档 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 219 | 独立复查与文档 | Read | ok | <user-home>\AppData\Local\Temp\claude\d--PBR-PRTdemo-TEST03\ce531919-fa23-4677-b923-d68638935941\tasks\b4ipj39k9.output |
| 220 | 独立复查与文档 | TodoWrite | ok | 更新任务列表 |
| 221 | Probe visibility 收敛 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\ssaa_resolve.fs |
| 222 | Probe visibility 收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 223 | Probe visibility 收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 224 | Probe visibility 收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 225 | Probe visibility 收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 226 | Probe visibility 收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 227 | Probe visibility 收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 228 | Probe visibility 收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 229 | Probe visibility 收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 230 | Probe visibility 收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 231 | Probe visibility 收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 232 | Probe visibility 收敛 | Edit | ok | <candidate-repository>\README.md |
| 233 | Probe visibility 收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 234 | Probe visibility 收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 235 | Probe visibility 收敛 | PowerShell | ok | 构建并运行完整 regression tests |
| 236 | Probe visibility 收敛 | PowerShell | ok | 检查当前 diff 与状态 |
| 237 | Probe visibility 收敛 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 238 | Probe visibility 收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 239 | Probe visibility 收敛 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 240 | Probe visibility 收敛 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 241 | Probe visibility 收敛 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 242 | Probe visibility 收敛 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.fs |
| 243 | Probe visibility 收敛 | Read | ok | <candidate-repository>\realtime-render-contract.json |
| 244 | Probe visibility 收敛 | Read | warning | <user-home>\AppData\Local\Temp\claude\d--PBR-PRTdemo-TEST03\ce531919-fa23-4677-b923-d68638935941\tasks\bzfhzdeby.output |
| 245 | Probe visibility 收敛 | TodoWrite | ok | 更新任务列表 |
| 246 | Probe visibility 收敛 | PowerShell | ok | 验证 Probe validity 改动与 determinism |
| 247 | Probe visibility 收敛 | PowerShell | ok | 验证 stale 与 missing-input 失败 |
| 248 | Probe visibility 收敛 | Read | ok | <candidate-repository>\.gitignore |
| 249 | Probe visibility 收敛 | TaskOutput | error | {"task_id":"a9b7b9b21caf33edd","block":false,"timeout":[omitted]} |
| 250 | Probe visibility 收敛 | Glob | ok | <candidate-repository> |
| 251 | Probe visibility 收敛 | PowerShell | ok | 检查 worktree 副作用状态 |
| 252 | Probe visibility 收敛 | Glob | ok | <candidate-repository> |
| 253 | Probe visibility 收敛 | Grep | ok | <candidate-repository>\AGENTS.md |
| 254 | Probe visibility 收敛 | Edit | ok | <candidate-repository>\.gitignore |
| 255 | Probe visibility 收敛 | PowerShell | ok | 确认 worktree 文件已忽略 |
| 256 | Probe visibility 收敛 | Read | ok | <user-home>\AppData\Local\Temp\claude\d--PBR-PRTdemo-TEST03\ce531919-fa23-4677-b923-d68638935941\tasks\bbrsc98ew.output |
| 257 | Probe visibility 收敛 | Read | ok | <user-home>\AppData\Local\Temp\claude\d--PBR-PRTdemo-TEST03\ce531919-fa23-4677-b923-d68638935941\tasks\b3wpv5dna.output |
| 258 | Probe visibility 收敛 | PowerShell | ok | 重新确认 failure exit behavior |
| 259 | Probe visibility 收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 260 | Probe visibility 收敛 | Grep | warning | <candidate-repository>\tests\render_contract.cpp |
| 261 | Probe visibility 收敛 | Grep | ok | <candidate-repository>\includes\GI\probe.h |
| 262 | Probe visibility 收敛 | TaskOutput | error | {"task_id":"a988345c60d02b5b4","block":false,"timeout":[omitted]} |
| 263 | Probe visibility 收敛 | Read | warning | <user-home>\AppData\Local\Temp\claude\d--PBR-PRTdemo-TEST03\ce531919-fa23-4677-b923-d68638935941\tasks\a988345c60d02b5b4.output |
| 264 | Probe visibility 收敛 | PowerShell | ok | 运行最终完整 regression tests |
| 265 | Probe visibility 收敛 | Read | warning | <user-home>\AppData\Local\Temp\claude\d--PBR-PRTdemo-TEST03\ce531919-fa23-4677-b923-d68638935941\tasks\a9b7b9b21caf33edd.output |
| 266 | Probe visibility 收敛 | Grep | ok | <candidate-repository>\includes\GI\probe.h |
| 267 | Probe visibility 收敛 | Read | warning | <user-home>\AppData\Local\Temp\claude\d--PBR-PRTdemo-TEST03\ce531919-fa23-4677-b923-d68638935941\tasks\bgceeo5d4.output |
| 268 | Probe visibility 收敛 | PowerShell | ok | 运行最新最终 one-shot export |
| 269 | Probe visibility 收敛 | PowerShell | warning | 执行最终 diff 与状态检查 |
| 270 | Probe visibility 收敛 | Agent | warning | 最终独立代码审查 |
| 271 | Probe visibility 收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 272 | Probe visibility 收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 273 | Probe visibility 收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 274 | Probe visibility 收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 275 | Probe visibility 收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 276 | Probe visibility 收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 277 | Probe visibility 收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 278 | Probe visibility 收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 279 | Probe visibility 收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 280 | Probe visibility 收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 281 | Probe visibility 收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 282 | Probe visibility 收敛 | Edit | ok | <candidate-repository>\README.md |
| 283 | Probe visibility 收敛 | Grep | ok | <candidate-repository> |
| 284 | Probe visibility 收敛 | PowerShell | ok | 验证移除非物理 Probe gain |
| 285 | Probe visibility 收敛 | Read | ok | <user-home>\AppData\Local\Temp\claude\d--PBR-PRTdemo-TEST03\ce531919-fa23-4677-b923-d68638935941\tasks\bnaes39vn.output |
| 286 | Probe visibility 收敛 | Read | warning | <user-home>\AppData\Local\Temp\claude\d--PBR-PRTdemo-TEST03\ce531919-fa23-4677-b923-d68638935941\tasks\bauywr1hj.output |
| 287 | Probe visibility 收敛 | PowerShell | ok | 验证最终 determinism 与 zero-light invariant |
| 288 | Probe visibility 收敛 | PowerShell | warning | 检查最终 diff 与工作树 |
| 289 | Probe visibility 收敛 | Grep | ok | <candidate-repository> |
| 290 | Probe visibility 收敛 | Read | ok | <user-home>\AppData\Local\Temp\claude\d--PBR-PRTdemo-TEST03\ce531919-fa23-4677-b923-d68638935941\tasks\bj6q6f02u.output |
| 291 | Probe visibility 收敛 | TodoWrite | ok | 更新任务列表 |
| 292 | Probe visibility 收敛 | Grep | ok | <candidate-repository>\includes\GI\probe.h |
| 293 | Probe visibility 收敛 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 294 | Probe visibility 收敛 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 295 | Probe visibility 收敛 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |

</details>

<details>
<summary><strong>Agent 最终回复</strong></summary>

<pre>已完成本轮 realtime rendering 收敛优化，未修改 public [realtime-render-contract.json](realtime-render-contract.json)，也未创建 commit。

## 主要改进

- Probe sampling 改为 256-direction deterministic Spherical Fibonacci，消除 wall-clock/global PRNG 噪声，并提升球面覆盖质量：[probe.h:280](includes/GI/probe.h#L280)
- Ray transport 改为先寻找 nearest hit，再仅对最近 Surfel 执行一次 source shading：[probe.h:347](includes/GI/probe.h#L347)
- Runtime irradiance 计算改为：
  - incoming-radiance SH projection
  - analytic clamped-cosine convolution
  - `A0=π`、`A1=2π/3`、`A2=π/4`
  
  避免旧实现的双重 Monte Carlo sampling error：[probe.h:694](includes/GI/probe.h#L694)
- CPU/GPU PBR 统一使用 correlated Smith GGX visibility，保持 Cook-Torrance BRDF 一致：[probe.h:33](includes/GI/probe.h#L33)、[light_casters.fs:141](src/getting_started/GIApplication/light_casters.fs#L141)
- Point-shadow cubemap：
  - near plane 降为 `0.05`
  - far plane 动态覆盖完整 scene bounds
  - bias 根据 distance、cubemap texel footprint 和 surface slope 计算
  
  位置见 [main.cpp:593](src/getting_started/GIApplication/main.cpp#L593)、[light_casters.fs:63](src/getting_started/GIApplication/light_casters.fs#L63)
- Cube interior Probe 不再通过移除所在 cube 来“看穿”实体 geometry；invalid Probe 保持零 transport。
- Receiver reconstruction 沿 surface normal 做 geometry-aware query offset，减少背侧 Probe leakage：[light_casters.fs:221](src/getting_started/GIApplication/light_casters.fs#L221)
- 最终独立 review 发现 validity-weight renormalization 会构成 spatially varying GI gain，因此已撤销，没有保留该非物理补偿。
- Shader asset path 改为从 repository root 解析，满足公开 root-directory launch ABI：[main.cpp:157](src/getting_started/GIApplication/main.cpp#L157)
- Automation export 使用 dedicated `RGB32F` combined/indirect resolve framebuffer，不再依赖 default back buffer：[main.cpp:217](src/getting_started/GIApplication/main.cpp#L217)
- `realtime.png` 在 CPU 上明确执行：
  - Reinhard
  - exact sRGB OETF
  - round-to-nearest RGB8
  
  避免 driver/platform 的 float-to-UNORM 差异：[realtime_capture.h:225](src/getting_started/GIApplication/realtime_capture.h#L225)
- Export 写入失败会清理 partial files；已有 case directory 会被拒绝：[realtime_capture.h:316](src/getting_started/GIApplication/realtime_capture.h#L316)
- 补齐 OpenGL shadow/capture/VAO resource cleanup。
- README 已同步新的 PRT 和 export pipeline：[README.md](README.md)
- 将 Agent 临时 worktree 目录加入 [.gitignore](.gitignore)，避免工具副作用进入 repository 状态。

## 验证结果

### 完整 regression tests

执行：

```powershell
python .\tools\test.py
```

结果：

- `frame_timing` passed
- `realtime_capture` passed
- `render_contract` passed
- `prt_numerics_pbr` passed
- `prt_numerics_phong` passed
- **5/5 tests passed**

### 最新 one-shot export

从 repository root 使用公开 executable ABI 成功执行：

```powershell
.\bin\getting_started\PRTdemo.exe --renderer PBR
```

验证结果：

- process exit code：`0`
- 只生成三份文件：
  - `realtime.png`
  - `indirect-linear.pfm`
  - `state.json`
- PNG dimensions：`800x600`
- PFM：`PF`、`800 600`、little-endian scale `-1.0`
- PFM file size：`5,760,016` bytes
- camera/light state round-trip 正确

### Determinism 与物理 invariant

- 相同 render state 重复运行：
  - `realtime.png` SHA-256 完全一致
  - `indirect-linear.pfm` SHA-256 完全一致
- zero-intensity point light：
  - indirect PFM 全零
  - realtime PNG 全黑
  - dimensions 仍为 `800x600`
- stale case directory：返回 non-zero
- 缺少 required input：返回 non-zero
- `git diff --check` 通过，仅有 Windows line-ending 提示。

## 当前工作树

修改文件：

- [.gitignore](.gitignore)
- [README.md](README.md)
- [probe.h](includes/GI/probe.h)
- [light_casters.fs](src/getting_started/GIApplication/light_casters.fs)
- [main.cpp](src/getting_started/GIApplication/main.cpp)
- [realtime_capture.h](src/getting_started/GIApplication/realtime_capture.h)
- [prt_numerics.cpp](tests/prt_numerics.cpp)
- [realtime_capture.cpp](tests/realtime_capture.cpp)

尚未创建 commit。Linux/Mesa llvmpipe 路径由于当前环境为 Windows，未在本机实际运行；其 build/launch ABI 未被修改。</pre>

</details>
