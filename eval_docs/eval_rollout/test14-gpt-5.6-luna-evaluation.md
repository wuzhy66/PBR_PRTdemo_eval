# TEST14 · gpt-5.6-luna · Realtime rendering best-effort 全报告

> GitHub-readable evaluation report。本文件保留指标、过程分析和 tool-call 摘要，不嵌入体积过大的 tool input/output 或完整 Git diff。

## 最终结果

**Normalized improvement：`0.00000000` · Decision：`failure`**

| Baseline A | Candidate B / Strict | Mean B−A | Cases | Strict / Excluded / Errors |
|---:|---:|---:|---:|---:|
| 0.81864903 | 0.81858219 | -0.00006684 | 200 | 200 / 0 / 0 |

`Normalized improvement` 是最终 coding improvement 分数；`Strict score` 是单个 renderer 对 offline reference 的绝对分数。

### 指标变化

| 指标 | 权重 | Baseline | Candidate | 变化 | 改善 | 退化 | 不变 |
|---|---:|---:|---:|---:|---:|---:|---:|
| FLIP perceptual score | 70% | 0.81916697 | 0.81907026 | -0.00009671 | 72 | 77 | 51 |
| Worst-patch FLIP | diagnostic | 0.60162365 | 0.60146897 | -0.00015467 | 10 | 24 | 166 |
| Indirect transport | 30% | 0.82374117 | 0.82374117 | +0.00000000 | 0 | 0 | 200 |
| Occlusion leak | diagnostic | 0.78038943 | 0.78038943 | +0.00000000 | 0 | 0 | 200 |
| Strict score | aggregate | 0.81864903 | 0.81858219 | -0.00006684 | 72 | 77 | 51 |

### Regression gates

| Gate | Required | Median delta | 改善 | 退化 | 不变 | 结果 |
|---|---:|---:|---:|---:|---:|---|
| Median FLIP delta | yes | +0.00000000 | 72 | 77 | 51 | FAIL |
| Median worst-patch FLIP delta | yes | +0.00000000 | 10 | 24 | 166 | FAIL |

## 总体判断

本轮改动集中在 deterministic Probe sampling、point-light shadow bias 与 shader 数值稳定性。正式 200-case 评测中 Strict score 从 0.81864903 降至 0.81858219，FLIP 与 Worst-patch FLIP 的 median regression gates 均未通过；Indirect 与 Occlusion diagnostic 在全部 case 中完全不变。最终 mean improvement 为 -0.00006684，Normalized improvement 为 0，判定改进失败。

## 改动与实测评价

### `includes/GI/probe.h`

- 改动：将 Probe sampling seed 固定为 1337，移除 wall-clock seed，同时保留 jittered stratified sampling 与 Monte Carlo normalization。
- 目标：消除不同运行之间的随机采样差异，使 PRT preprocessing 可复现。
- 评测：正式评测中 Indirect score 在全部 200 case 上与 baseline 完全相同，因此这一改动提高了 determinism，但没有转化为本协议下的图像质量收益。

### `src/getting_started/GIApplication/light_casters.fs`

- 改动：用与 receiver distance、surface-light angle 相关的 point-shadow bias 替换固定 0.05 bias，并增加 inverse-square denominator guard。
- 目标：减少固定 bias 导致的 detached shadow、self-shadow acne 与近光源数值异常。
- 评测：FLIP 平均变化 -0.00009671：72 case 改善、77 case 退化、51 case 不变；Worst-patch FLIP 平均变化 -0.00015467，说明新 bias 没有形成稳定、广泛的收益。

### `src/getting_started/GIApplication/light_casters.fs`

- 改动：对 reconstructed SH irradiance 施加 non-negative constraint，并在 indirect term 中使用 material.ao。
- 目标：避免负 irradiance，并让 indirect response 遵循 material occlusion 定义。
- 评测：当前公开评测 contract 中 material.ao 为 1，且 Indirect/Occlusion 指标逐 case 完全不变；这部分修改在当前数据集上没有可测输出影响。

## 做得好的地方

- 改动保持在可解释的物理与数值模型范围内，没有使用 exposure、gain 或颜色偏置等艺术性 magic number。
- 实现范围紧凑，仅修改 probe.h 与 light_casters.fs，共 20 additions / 24 deletions。
- 执行过程中完成 tools/test.py 的 5/5 tests，并验证 one-shot export 可生成有效的 800×600 输出。
- 正式 replay 完成 200/200 case，评分阶段没有 excluded case 或 error case。
- candidate source commit 保持干净；仅有 Claude 工作目录未被纳入提交。

## 风险与不足

- 最终 Strict mean improvement 为 -0.00006684，Normalized improvement 为 0，按协议判定失败。
- FLIP 与 Worst-patch FLIP 的 median improvement 都为 0，两个 required regression gate 均未通过。
- Indirect 与 Occlusion diagnostic 在 200 个 case 上全部不变，说明大部分预期修改没有影响被评分的输出路径。
- Worst-patch FLIP 只有 10 case 改善、24 case 退化、166 case 不变，局部 artifact 没有得到普遍改善。
- 两次 subagent 调用均失败，没有获得成功的独立代码审查结果。
- 133 次 tool call 中记录到 39 个 error，主要来自 Edit 精确匹配失败，执行过程存在明显的无效迭代。
- 固定单一 sampling seed 有利于 reproducibility，但本身不代表 sampling quality 提升。

## 分项结论

| 维度 | 评价 | 说明 |
|---|---|---|
| 物理建模 | 中等 | Shadow bias、inverse-square guard 与 non-negative irradiance 均有明确依据，但没有在正式指标上形成稳定改善。 |
| 验证完整性 | 良好 | 完成 5/5 tests、one-shot export 与 200-case replay；正式 scoring 无 error case。 |
| 指标均衡 | 失败 | FLIP 与 Worst-patch 均轻微退化，Indirect/Occlusion 完全不变，两个 regression gate 均失败。 |
| 最终效果 | 失败 | Strict score 0.81858219，mean(B−A) -0.00006684，Normalized improvement 0。 |

## 执行概览

- Test：`TEST14`
- Main model：`gpt-5.6-luna`
- Claude Code：`2.1.233`
- Candidate / Baseline：`411e7fa` / `e5105fa`
- Tool calls：133（39 errors，14 warnings）
- Subagents：0 success / 2 attempts
- Git diff：2 files，+20 / -24，diff check `PASS`

### Tool 类型

| Tool | Calls |
|---|---:|
| Edit | 52 |
| Read | 44 |
| PowerShell | 14 |
| Glob | 7 |
| Bash | 5 |
| TodoWrite | 4 |
| Grep | 3 |
| Agent | 2 |
| EnterPlanMode | 1 |
| ExitPlanMode | 1 |

## 执行阶段

### #1–#47 · 代码审计与计划

- 动作：读取 renderer、Probe、shader、tests 与项目约束，尝试调用两个 subagent，并制定 deterministic sampling 与 shadow 修正计划。
- 分析：审计覆盖了主要 realtime rendering 路径，但两次 subagent 尝试均失败，独立复核未能落地。
- 证据：完成核心文件与测试入口定位，形成围绕 Probe seed、SH response 和 point shadow 的实施范围。

### #48–#105 · Probe 与 shader 实现

- 动作：修改 Probe sampling seed、shadow bias、inverse-square guard、SH non-negative constraint 与 material AO response。
- 分析：实现保持紧凑，但多次 Edit 因精确文本不匹配失败，迭代效率较低。
- 证据：最终 diff 仅涉及 probe.h 与 light_casters.fs，共 20 additions / 24 deletions。

### #106–#122 · 构建、测试与输出验证

- 动作：运行 regression tests、构建 renderer，并通过 one-shot capture 检查输出尺寸与文件有效性。
- 分析：验证覆盖基本 contract 与可运行性，但没有在提交前获得完整 200-case 指标反馈。
- 证据：tools/test.py 通过 5/5，one-shot export 生成有效 800×600 输出。

### #123–#133 · 最终复查与收敛

- 动作：复查最终 diff、确认修改范围并提交 candidate commit。
- 分析：代码层面按既定方案收敛；事后正式评测显示输出变化过小且总体为负。
- 证据：candidate commit 为 411e7fa；正式结果 Strict -0.00006684，两个 required gates 均失败。

## Subagent

没有成功返回的 subagent。

## Git 文件变化

| File | Added | Deleted |
|---|---:|---:|
| `includes/GI/probe.h` | 5 | 9 |
| `src/getting_started/GIApplication/light_casters.fs` | 15 | 15 |

Worktree status：`?? .claude/`

<details>
<summary><strong>Tool-call 流程摘要</strong></summary>

| # | 阶段 | Tool | 状态 | 摘要 |
|---:|---|---|---|---|
| 1 | 代码审计与计划 | TodoWrite | ok | 更新任务列表 |
| 2 | 代码审计与计划 | EnterPlanMode | ok | {} |
| 3 | 代码审计与计划 | Agent | error | 审查渲染管线实现 |
| 4 | 代码审计与计划 | Agent | error | 审查渲染管线实现 |
| 5 | 代码审计与计划 | Glob | ok | <candidate-repository> |
| 6 | 代码审计与计划 | Grep | ok | <candidate-repository> |
| 7 | 代码审计与计划 | Read | error | <candidate-repository>\AGENTS.md |
| 8 | 代码审计与计划 | Read | error | <candidate-repository>\realtime-render-contract.json |
| 9 | 代码审计与计划 | Read | warning | <candidate-repository>\AGENTS.md |
| 10 | 代码审计与计划 | Read | ok | <candidate-repository>\realtime-render-contract.json |
| 11 | 代码审计与计划 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 12 | 代码审计与计划 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\render_contract.h |
| 13 | 代码审计与计划 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 14 | 代码审计与计划 | Glob | ok | <candidate-repository> |
| 15 | 代码审计与计划 | Glob | ok | <candidate-repository> |
| 16 | 代码审计与计划 | Glob | ok | <candidate-repository> |
| 17 | 代码审计与计划 | Glob | ok | <candidate-repository> |
| 18 | 代码审计与计划 | Glob | ok | <candidate-repository>\src |
| 19 | 代码审计与计划 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 20 | 代码审计与计划 | Read | ok | <candidate-repository>\CMakeLists.txt |
| 21 | 代码审计与计划 | Read | ok | <candidate-repository>\README.md |
| 22 | 代码审计与计划 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 23 | 代码审计与计划 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.vs |
| 24 | 代码审计与计划 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\ssaa_resolve.fs |
| 25 | 代码审计与计划 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\ssaa_resolve.vs |
| 26 | 代码审计与计划 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 27 | 代码审计与计划 | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 28 | 代码审计与计划 | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 29 | 代码审计与计划 | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 30 | 代码审计与计划 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 31 | 代码审计与计划 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 32 | 代码审计与计划 | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 33 | 代码审计与计划 | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 34 | 代码审计与计划 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.fs |
| 35 | 代码审计与计划 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.gs |
| 36 | 代码审计与计划 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.vs |
| 37 | 代码审计与计划 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 38 | 代码审计与计划 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 39 | 代码审计与计划 | Read | warning | <candidate-repository>\tests\prt_numerics.cpp |
| 40 | 代码审计与计划 | Read | warning | <candidate-repository>\tests\render_contract.cpp |
| 41 | 代码审计与计划 | Read | warning | <candidate-repository>\tests\realtime_capture.cpp |
| 42 | 代码审计与计划 | Read | warning | <candidate-repository>\tools\test.py |
| 43 | 代码审计与计划 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\camera.fs |
| 44 | 代码审计与计划 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 45 | 代码审计与计划 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 46 | 代码审计与计划 | Glob | ok | <candidate-repository> |
| 47 | 代码审计与计划 | ExitPlanMode | ok | {} |
| 48 | Probe 与 shader 实现 | TodoWrite | ok | 更新任务列表 |
| 49 | Probe 与 shader 实现 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 50 | Probe 与 shader 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 51 | Probe 与 shader 实现 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 52 | Probe 与 shader 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 53 | Probe 与 shader 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 54 | Probe 与 shader 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 55 | Probe 与 shader 实现 | Bash | error | 固定 Probe sample pattern 以消除非确定性 |
| 56 | Probe 与 shader 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 57 | Probe 与 shader 实现 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 58 | Probe 与 shader 实现 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 59 | Probe 与 shader 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 60 | Probe 与 shader 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 61 | Probe 与 shader 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 62 | Probe 与 shader 实现 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 63 | Probe 与 shader 实现 | Edit | error | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 64 | Probe 与 shader 实现 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 65 | Probe 与 shader 实现 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 66 | Probe 与 shader 实现 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 67 | Probe 与 shader 实现 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 68 | Probe 与 shader 实现 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 69 | Probe 与 shader 实现 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 70 | Probe 与 shader 实现 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 71 | Probe 与 shader 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 72 | Probe 与 shader 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 73 | Probe 与 shader 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 74 | Probe 与 shader 实现 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 75 | Probe 与 shader 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 76 | Probe 与 shader 实现 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 77 | Probe 与 shader 实现 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 78 | Probe 与 shader 实现 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 79 | Probe 与 shader 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 80 | Probe 与 shader 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 81 | Probe 与 shader 实现 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 82 | Probe 与 shader 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 83 | Probe 与 shader 实现 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 84 | Probe 与 shader 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 85 | Probe 与 shader 实现 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 86 | Probe 与 shader 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 87 | Probe 与 shader 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 88 | Probe 与 shader 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 89 | Probe 与 shader 实现 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 90 | Probe 与 shader 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 91 | Probe 与 shader 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 92 | Probe 与 shader 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 93 | Probe 与 shader 实现 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 94 | Probe 与 shader 实现 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 95 | Probe 与 shader 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 96 | Probe 与 shader 实现 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 97 | Probe 与 shader 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 98 | Probe 与 shader 实现 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 99 | Probe 与 shader 实现 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 100 | Probe 与 shader 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 101 | Probe 与 shader 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 102 | Probe 与 shader 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 103 | Probe 与 shader 实现 | Bash | ok | 检查 Probe header 损坏片段 |
| 104 | Probe 与 shader 实现 | Bash | ok | 修复 Probe fixed seed 语句 |
| 105 | Probe 与 shader 实现 | Bash | ok | 检查第一轮渲染改动 |
| 106 | 构建、测试与输出验证 | PowerShell | warning | 构建并运行全部 realtime regression tests |
| 107 | 构建、测试与输出验证 | Read | ok | <candidate-repository>\README.md |
| 108 | 构建、测试与输出验证 | PowerShell | error | 运行一次 one-shot realtime frame export |
| 109 | 构建、测试与输出验证 | PowerShell | ok | 检查 executable 与 shader runtime assets |
| 110 | 构建、测试与输出验证 | Read | warning | <candidate-repository>\includes\learnopengl\shader_m.h |
| 111 | 构建、测试与输出验证 | PowerShell | ok | 从 shader runtime 目录运行 one-shot export |
| 112 | 构建、测试与输出验证 | PowerShell | ok | 核对 one-shot export 三份输出 |
| 113 | 构建、测试与输出验证 | PowerShell | ok | 检查 indirect PFM header 与 float 数据 |
| 114 | 构建、测试与输出验证 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 115 | 构建、测试与输出验证 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 116 | 构建、测试与输出验证 | PowerShell | warning | 重新运行现有回归测试 |
| 117 | 构建、测试与输出验证 | PowerShell | ok | 重新构建 shader 与 executable |
| 118 | 构建、测试与输出验证 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 119 | 构建、测试与输出验证 | Edit | error | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 120 | 构建、测试与输出验证 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 121 | 构建、测试与输出验证 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 122 | 构建、测试与输出验证 | TodoWrite | ok | 更新任务列表 |
| 123 | 最终复查与收敛 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 124 | 最终复查与收敛 | Bash | ok | 检查 diff 格式与工作区状态 |
| 125 | 最终复查与收敛 | PowerShell | error | 清理临时导出与异常 worktree 目录 |
| 126 | 最终复查与收敛 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 127 | 最终复查与收敛 | PowerShell | ok | 清理临时 capture 输出并查看状态 |
| 128 | 最终复查与收敛 | Read | ok | <candidate-repository>\.gitignore |
| 129 | 最终复查与收敛 | PowerShell | ok | 检查异常 .claude 目录内容 |
| 130 | 最终复查与收敛 | PowerShell | ok | 检查残留 worktree 目录 |
| 131 | 最终复查与收敛 | PowerShell | error | 清理本次尝试创建的残留 worktree |
| 132 | 最终复查与收敛 | PowerShell | warning | 执行最终 build 与全部回归测试 |
| 133 | 最终复查与收敛 | TodoWrite | ok | 更新任务列表 |

</details>

<details>
<summary><strong>Agent 最终回复</strong></summary>

<pre>已完成一轮完整审查、实现与验证，当前改动集中在两个 realtime rendering 关键点：

### 已完成的渲染改进

- [probe.h](includes/GI/probe.h)
  - 将 Probe sample seed 固定为 `1337`。
  - 移除 static scene transport 对 `wall clock` 的依赖，避免每次启动产生不同的 GI sample pattern。
  - 保留原有 jittered stratified sampling 和 Monte Carlo normalization，未改变 one-bounce GI contract。

- [light_casters.fs](src/getting_started/GIApplication/light_casters.fs)
  - 改进 point-light shadow bias：
    - 从固定 `0.05` 改为基于 fragment distance 和入射角的 receiver-side bias。
    - 减少 shadow acne，同时降低固定大 bias 导致的 contact shadow 泄漏。
  - 对 point-light inverse-square attenuation 增加数值下限保护，避免光源极近时出现除零或 NaN。
  - 对 SH reconstruction 后的 irradiance 保持 non-negative projection。
  - 显式应用 `material.ao` 到 indirect irradiance；public contract 下 `ao=1`，默认输出不改变。
  - 保持 direct/indirect 均在线性 HDR 中计算，未使用 saturation、gain、exposure 或颜色偏置掩盖问题。

### 验证结果

已运行：

```powershell
python .\tools\test.py
```

结果：

- Build 成功
- `frame_timing` 通过
- `realtime_capture` 通过
- `render_contract` 通过
- `prt_numerics_pbr` 通过
- `prt_numerics_phong` 通过
- 共 5/5 tests passed

另外实际执行了一次 one-shot export，成功生成：

```text
cases/&lt;case-id&gt;/realtime.png
cases/&lt;case-id&gt;/indirect-linear.pfm
cases/&lt;case-id&gt;/state.json
```

其中：

- `realtime.png` 为 `800x600`
- `indirect-linear.pfm` 为 `800x600` RGB32F little-endian PFM
- `state.json` 成功保存实际 camera/light 状态
- process 在完整输出后正常结束

当前工作区的有效源码改动为：

- [includes/GI/probe.h](includes/GI/probe.h)
- [src/getting_started/GIApplication/light_casters.fs](src/getting_started/GIApplication/light_casters.fs)

另外，session 尝试创建的 `.claude/worktrees/` 残留目录未删除，因为其中可能包含既有 worktree 内容，自动清理被安全保护拦截；它们不影响 build/test，也未被纳入源码改动。</pre>

</details>
