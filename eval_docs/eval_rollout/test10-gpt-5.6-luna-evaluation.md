# TEST10 · gpt-5.6-luna · Realtime rendering best-effort 全报告

> GitHub-readable evaluation report。本文件保留指标、过程分析和 tool-call 摘要，不嵌入体积过大的 tool input/output 或完整 Git diff。

## 最终结果

**Normalized improvement：`0.40233022` · Decision：`success`**

| Baseline A | Candidate B / Strict | Mean B−A | Cases | Strict / Excluded / Errors |
|---:|---:|---:|---:|---:|
| 0.81864903 | 0.89161200 | +0.07296298 | 200 | 200 / 0 / 0 |

`Normalized improvement` 是最终 coding improvement 分数；`Strict score` 是单个 renderer 对 offline reference 的绝对分数。

### 指标变化

| 指标 | 权重 | Baseline | Candidate | 变化 | 改善 | 退化 | 不变 |
|---|---:|---:|---:|---:|---:|---:|---:|
| FLIP perceptual score | 70% | 0.81916697 | 0.89999818 | +0.08083121 | 143 | 57 | 0 |
| Worst-patch FLIP | diagnostic | 0.60162365 | 0.75514122 | +0.15351757 | 141 | 59 | 0 |
| Indirect transport | 30% | 0.82374117 | 0.87796963 | +0.05422846 | 186 | 14 | 0 |
| Occlusion leak | diagnostic | 0.78038943 | 0.76365390 | -0.01673553 | 104 | 87 | 9 |
| Strict score | aggregate | 0.81864903 | 0.89161200 | +0.07296298 | 177 | 23 | 0 |

### Regression gates

| Gate | Required | Median delta | 改善 | 退化 | 不变 | 结果 |
|---|---:|---:|---:|---:|---:|---|
| Median FLIP delta | yes | +0.01991672 | 143 | 57 | 0 | PASS |
| Median worst-patch FLIP delta | yes | +0.03401622 | 141 | 59 | 0 | PASS |

## 总体判断

执行集中于 deterministic Probe sampling、point-shadow coverage/bias 和 PBR numerical stability，改动规模较小。正式 200-case 评测中 Strict score 从 0.81864903 提升到 0.89161200，177 case 改善，FLIP 和 Worst-patch FLIP median gates 均通过，Normalized improvement 为 0.40233022。Indirect transport 收益强，但 Occlusion leak diagnostic 平均退化 0.01673553。

## 改动与实测评价

### `includes/GI/probe.h`

- 改动：将每个 Probe 的 10×10 random rays 改为 512 条 deterministic Fibonacci-sphere directions，移除 rand()/time() 依赖，并为 zero-length view/half vectors 增加 fallback。
- 目标：降低 Probe projection 的 sampling variance 和跨平台随机性，避免 normalize(0) 产生 NaN。
- 评测：Indirect transport 平均提升 0.05422846，186/200 case 改善，是本轮最稳定的收益来源。

### `src/getting_started/GIApplication/main.cpp`

- 改动：Point-shadow near plane 从 1.0 改为 0.1，far plane 根据 light 到 contract scene bounds 的最远距离动态推导并保留 margin。
- 目标：覆盖 room 内所有合法 light positions，避免近表面和远端 blocker 因 clip range 丢失 shadow。
- 评测：FLIP 平均提升 0.08083121，143 case 改善、57 case 退化；Strict 最终为 177 case 改善、23 case 退化。

### `src/getting_started/GIApplication/light_casters.fs`

- 改动：将固定 0.05 shadow bias 改为小幅 slope-aware bias，并增加 view/half-vector numerical guards。
- 目标：在 shadow acne 与 peter-panning 之间根据 receiver angle 调节，同时保证 grazing/degenerate PBR input finite。
- 评测：Worst-patch FLIP 平均提升 0.15351757，median +0.03401622，141 case 改善、59 case 退化。

### `capture-validation outputs`

- 改动：Candidate commit 还包含两组 one-shot realtime.png、indirect-linear.pfm 和 state.json。
- 目标：保留 baseline 与 corner-light validation 证据。
- 评测：这些二进制产物不影响 renderer 评分，但不应进入 realtime candidate commit；路径名还暴露了采集日期格式，属于 repository hygiene 问题。

## 做得好的地方

- 113 次 tool call 完成从 pipeline 扫描、实现到两组 one-shot validation，收敛路径较紧凑。
- 修改均有可解释的数值/物理依据，未使用 exposure、gain、saturation 或颜色偏置。
- 完整 regression tests 通过，中央与 corner light one-shot 都生成了 PNG/PFM/state，并检查 PFM finite 和 state round-trip。
- Strict、FLIP、Worst-patch FLIP 和 Indirect 均为正收益，两项 cross-case regression gates 都通过。

## 风险与不足

- Occlusion leak diagnostic 平均从 0.78038943 降到 0.76365390，净退化 0.01673553；87 case 退化。
- FLIP 仍有 57 case 退化，Worst-patch FLIP 有 59 case 退化，说明局部 shadow/visibility 改善不均匀。
- 两次 subagent 尝试均因 worktree isolation 问题失败，没有实际获得独立 review。
- Candidate commit 提交了约 14 MB validation PNG/PFM 产物与带日期格式的目录，这与 realtime-only 实验仓库的精简性不符。

## 分项结论

| 维度 | 评价 | 说明 |
|---|---|---|
| 物理建模 | 良好 | Deterministic Probe directions、dynamic shadow range 和 slope-aware bias 都有明确依据。 |
| 验证完整性 | 良好 | 覆盖 regression tests、两组 one-shot 和 200-case trusted evaluation，但没有成功 subagent review。 |
| 指标均衡 | 良好 | Strict 177 case 改善且 Indirect 收益强，但 Occlusion diagnostic 平均退化。 |
| 最终效果 | 成功 | Strict score 0.89161200，mean(B−A) +0.07296298，Normalized improvement 0.40233022。 |

## 执行概览

- Test：`TEST10`
- Main model：`gpt-5.6-luna`
- Claude Code：`2.1.233`
- Candidate / Baseline：`1c0d88f` / `2039d94`
- Tool calls：113（10 errors，18 warnings）
- Subagents：0 success / 2 attempts
- Git diff：9 files，+54 / -34，diff check `FAIL`

### Tool 类型

| Tool | Calls |
|---|---:|
| Read | 40 |
| Edit | 17 |
| TaskOutput | 16 |
| Bash | 13 |
| Grep | 9 |
| Glob | 8 |
| TodoWrite | 4 |
| Agent | 2 |
| EnterPlanMode | 1 |
| Write | 1 |
| ExitPlanMode | 1 |
| PowerShell | 1 |

## 执行阶段

### #1–#47 · Pipeline 扫描与计划

- 动作：审计 renderer、Probe、PBR shader、point-shadow、contract 与 tests，尝试 subagent review 并形成实施计划。
- 分析：两次 subagent 都因 isolation worktree 失败，主 agent 自行完成扫描；实施范围最终聚焦三个高优先级点。
- 证据：计划覆盖 deterministic Probe sampling、shadow range/bias 和 PBR numerical stability。

### #48–#77 · Probe 与 shadow 实现

- 动作：运行 baseline build/tests，实现 512-direction Fibonacci sampling、dynamic point-shadow range 和 slope-aware bias，反复构建回归。
- 分析：改动量较小且直接对应可见 rendering artifact，实现后立即用 tests 检查。
- 证据：probe.h、main.cpp 和 light_casters.fs 形成核心 diff，完整 regression suite 通过。

### #78–#96 · Baseline export 与数值保护

- 动作：生成 baseline one-shot，读取 realtime image/state/PFM，修正 zero-half-vector 与 zero-view-vector guards，再次运行测试。
- 分析：将渲染输出检查与 shader numerical stability 联系，防止仅编译通过但 image 出现 NaN。
- 证据：Baseline PNG/PFM/state 成功，linear HDR 数值 finite。

### #97–#113 · Corner-light 验证与收敛

- 动作：完成最后 numerical guards，运行 corner-light + non-uniform RGB intensity one-shot，检查 PFM 与最终 diff/status。
- 分析：用 contract 边界附近的 light state 检查 dynamic shadow coverage，随后停止继续扩大改动。
- 证据：Corner-light 三件套输出完整，最终 commit 1c0d88f。

## Subagent

没有成功返回的 subagent。

## Git 文件变化

| File | Added | Deleted |
|---|---:|---:|
| `capture-validation-[timing omitted]/cases/baseline-fibonacci-shadow/indirect-linear.pfm` | - | - |
| `capture-validation-[timing omitted]/cases/baseline-fibonacci-shadow/realtime.png` | - | - |
| `capture-validation-[timing omitted]/cases/baseline-fibonacci-shadow/state.json` | 1 | 0 |
| `capture-validation-[timing omitted]/cases/corner-light-fibonacci-shadow/indirect-linear.pfm` | - | - |
| `capture-validation-[timing omitted]/cases/corner-light-fibonacci-shadow/realtime.png` | - | - |
| `capture-validation-[timing omitted]/cases/corner-light-fibonacci-shadow/state.json` | 1 | 0 |
| `includes/GI/probe.h` | 23 | 28 |
| `src/getting_started/GIApplication/light_casters.fs` | 13 | 4 |
| `src/getting_started/GIApplication/main.cpp` | 16 | 2 |

Worktree status：`?? .claude/`

<details>
<summary><strong>Tool-call 流程摘要</strong></summary>

| # | 阶段 | Tool | 状态 | 摘要 |
|---:|---|---|---|---|
| 1 | Pipeline 扫描与计划 | EnterPlanMode | ok | {} |
| 2 | Pipeline 扫描与计划 | Agent | error | 审查渲染架构 |
| 3 | Pipeline 扫描与计划 | Agent | error | 审查渲染架构 |
| 4 | Pipeline 扫描与计划 | Glob | ok | <candidate-repository> |
| 5 | Pipeline 扫描与计划 | Grep | ok | <candidate-repository> |
| 6 | Pipeline 扫描与计划 | Read | error | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 7 | Pipeline 扫描与计划 | Read | error | <candidate-repository>\includes\GI\probe.h |
| 8 | Pipeline 扫描与计划 | Read | error | <candidate-repository>\realtime-render-contract.json |
| 9 | Pipeline 扫描与计划 | Read | error | <candidate-repository>\tests\prt_numerics.cpp |
| 10 | Pipeline 扫描与计划 | Read | error | <candidate-repository>\tools\test.py |
| 11 | Pipeline 扫描与计划 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 12 | Pipeline 扫描与计划 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 13 | Pipeline 扫描与计划 | Read | ok | <candidate-repository>\realtime-render-contract.json |
| 14 | Pipeline 扫描与计划 | Read | warning | <candidate-repository>\tests\prt_numerics.cpp |
| 15 | Pipeline 扫描与计划 | Read | warning | <candidate-repository>\tools\test.py |
| 16 | Pipeline 扫描与计划 | Grep | ok | <candidate-repository>\includes\GI\probe.h |
| 17 | Pipeline 扫描与计划 | Grep | ok | <candidate-repository>\src |
| 18 | Pipeline 扫描与计划 | Glob | ok | <candidate-repository> |
| 19 | Pipeline 扫描与计划 | Glob | ok | <candidate-repository> |
| 20 | Pipeline 扫描与计划 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 21 | Pipeline 扫描与计划 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\render_contract.h |
| 22 | Pipeline 扫描与计划 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 23 | Pipeline 扫描与计划 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.vs |
| 24 | Pipeline 扫描与计划 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\ssaa_resolve.fs |
| 25 | Pipeline 扫描与计划 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\camera.fs |
| 26 | Pipeline 扫描与计划 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 27 | Pipeline 扫描与计划 | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 28 | Pipeline 扫描与计划 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 29 | Pipeline 扫描与计划 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 30 | Pipeline 扫描与计划 | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 31 | Pipeline 扫描与计划 | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 32 | Pipeline 扫描与计划 | Read | warning | <candidate-repository>\tests\realtime_capture.cpp |
| 33 | Pipeline 扫描与计划 | Bash | ok | 运行现有 build 与 regression tests |
| 34 | Pipeline 扫描与计划 | Read | warning | <candidate-repository>\tests\render_contract.cpp |
| 35 | Pipeline 扫描与计划 | Read | warning | <candidate-repository>\tests\frame_timing.cpp |
| 36 | Pipeline 扫描与计划 | Read | ok | <candidate-repository>\tools\build.py |
| 37 | Pipeline 扫描与计划 | Grep | ok | <candidate-repository>\tests |
| 38 | Pipeline 扫描与计划 | Read | ok | <candidate-repository>\CMakeLists.txt |
| 39 | Pipeline 扫描与计划 | Read | ok | <user-home>\AppData\Local\Temp\claude\d--PBR-PRTdemo-TEST10\e7f3418d-f342-4b45-8336-fe16ac3b5746\tasks\b5enr9lsy.output |
| 40 | Pipeline 扫描与计划 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.fs |
| 41 | Pipeline 扫描与计划 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.vs |
| 42 | Pipeline 扫描与计划 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.gs |
| 43 | Pipeline 扫描与计划 | Read | ok | <candidate-repository>\README.md |
| 44 | Pipeline 扫描与计划 | Grep | ok | <candidate-repository>\includes\GI\probe.h |
| 45 | Pipeline 扫描与计划 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 46 | Pipeline 扫描与计划 | Write | ok | <user-home>\.claude\plans\prt-rendering-improvement.md |
| 47 | Pipeline 扫描与计划 | ExitPlanMode | ok | {} |
| 48 | Probe 与 shadow 实现 | TodoWrite | ok | 更新任务列表 |
| 49 | Probe 与 shadow 实现 | Read | ok | <candidate-repository>\tools\_tooling.py |
| 50 | Probe 与 shadow 实现 | Bash | ok | 运行 Windows build 与 regression tests |
| 51 | Probe 与 shadow 实现 | TaskOutput | ok | {"task_id":"be4ub3rd0","block":true,"timeout":[omitted]} |
| 52 | Probe 与 shadow 实现 | TaskOutput | warning | {"task_id":"be4ub3rd0","block":true,"timeout":[omitted]} |
| 53 | Probe 与 shadow 实现 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 54 | Probe 与 shadow 实现 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 55 | Probe 与 shadow 实现 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 56 | Probe 与 shadow 实现 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 57 | Probe 与 shadow 实现 | Bash | ok | 验证 deterministic Probe sampling 修改 |
| 58 | Probe 与 shadow 实现 | TaskOutput | ok | {"task_id":"bpo6hbwb0","block":true,"timeout":[omitted]} |
| 59 | Probe 与 shadow 实现 | TaskOutput | ok | {"task_id":"bpo6hbwb0","block":true,"timeout":[omitted]} |
| 60 | Probe 与 shadow 实现 | TaskOutput | warning | {"task_id":"bpo6hbwb0","block":true,"timeout":[omitted]} |
| 61 | Probe 与 shadow 实现 | Grep | ok | <candidate-repository> |
| 62 | Probe 与 shadow 实现 | Read | ok | <candidate-repository>\README.md |
| 63 | Probe 与 shadow 实现 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 64 | Probe 与 shadow 实现 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 65 | Probe 与 shadow 实现 | Edit | error | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 66 | Probe 与 shadow 实现 | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 67 | Probe 与 shadow 实现 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 68 | Probe 与 shadow 实现 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 69 | Probe 与 shadow 实现 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 70 | Probe 与 shadow 实现 | Bash | ok | 验证 Probe 与 point shadow 修改 |
| 71 | Probe 与 shadow 实现 | TaskOutput | warning | {"task_id":"b4zr192xw","block":true,"timeout":[omitted]} |
| 72 | Probe 与 shadow 实现 | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 73 | Probe 与 shadow 实现 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 74 | Probe 与 shadow 实现 | Bash | ok | 重跑 build 与 regression tests |
| 75 | Probe 与 shadow 实现 | TaskOutput | ok | {"task_id":"blol2cwg5","block":true,"timeout":[omitted]} |
| 76 | Probe 与 shadow 实现 | TaskOutput | ok | {"task_id":"blol2cwg5","block":true,"timeout":[omitted]} |
| 77 | Probe 与 shadow 实现 | TaskOutput | warning | {"task_id":"blol2cwg5","block":true,"timeout":[omitted]} |
| 78 | Baseline export 与数值保护 | TodoWrite | ok | 更新任务列表 |
| 79 | Baseline export 与数值保护 | PowerShell | ok | 运行 baseline one-shot realtime export |
| 80 | Baseline export 与数值保护 | TaskOutput | warning | {"task_id":"betcu4s9m","block":true,"timeout":[omitted]} |
| 81 | Baseline export 与数值保护 | Bash | ok | 从 shader 工作目录运行 one-shot export |
| 82 | Baseline export 与数值保护 | TaskOutput | ok | {"task_id":"bo4e6rx6l","block":true,"timeout":[omitted]} |
| 83 | Baseline export 与数值保护 | Glob | ok | <candidate-repository> |
| 84 | Baseline export 与数值保护 | Read | ok | <candidate-repository>\capture-validation-[timing omitted]\cases\baseline-fibonacci-shadow\state.json |
| 85 | Baseline export 与数值保护 | Read | ok | <candidate-repository>\capture-validation-[timing omitted]\cases\baseline-fibonacci-shadow\realtime.png |
| 86 | Baseline export 与数值保护 | Grep | ok | <candidate-repository> |
| 87 | Baseline export 与数值保护 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 88 | Baseline export 与数值保护 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 89 | Baseline export 与数值保护 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 90 | Baseline export 与数值保护 | Bash | ok | 验证 PBR zero-half-vector 数值保护 |
| 91 | Baseline export 与数值保护 | TaskOutput | ok | {"task_id":"bjqxq7b86","block":true,"timeout":[omitted]} |
| 92 | Baseline export 与数值保护 | TaskOutput | warning | {"task_id":"bjqxq7b86","block":true,"timeout":[omitted]} |
| 93 | Baseline export 与数值保护 | Bash | ok | 检查当前渲染修改差异 |
| 94 | Baseline export 与数值保护 | Glob | ok | <candidate-repository> |
| 95 | Baseline export 与数值保护 | Glob | ok | <candidate-repository> |
| 96 | Baseline export 与数值保护 | Glob | ok | <candidate-repository> |
| 97 | Corner-light 验证与收敛 | Grep | warning | <candidate-repository> |
| 98 | Corner-light 验证与收敛 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 99 | Corner-light 验证与收敛 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 100 | Corner-light 验证与收敛 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 101 | Corner-light 验证与收敛 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 102 | Corner-light 验证与收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 103 | Corner-light 验证与收敛 | Bash | ok | 验证 view vector 数值保护 |
| 104 | Corner-light 验证与收敛 | TaskOutput | ok | {"task_id":"b0j0cp8c6","block":true,"timeout":[omitted]} |
| 105 | Corner-light 验证与收敛 | TaskOutput | warning | {"task_id":"b0j0cp8c6","block":true,"timeout":[omitted]} |
| 106 | Corner-light 验证与收敛 | TodoWrite | ok | 更新任务列表 |
| 107 | Corner-light 验证与收敛 | Bash | ok | 运行 corner-light one-shot export |
| 108 | Corner-light 验证与收敛 | TaskOutput | ok | {"task_id":"b435edx5i","block":true,"timeout":[omitted]} |
| 109 | Corner-light 验证与收敛 | Bash | ok | 检查 corner-light indirect PFM 数值 |
| 110 | Corner-light 验证与收敛 | Bash | ok | 检查 baseline indirect PFM 数值 |
| 111 | Corner-light 验证与收敛 | Bash | ok | 查看最终工作区状态 |
| 112 | Corner-light 验证与收敛 | Glob | ok | <candidate-repository> |
| 113 | Corner-light 验证与收敛 | TodoWrite | ok | 更新任务列表 |

</details>

<details>
<summary><strong>Agent 最终回复</strong></summary>

<pre>已继续完成一轮 realtime rendering 改进，并完成验证。

## 已实现的修改

- [probe.h](includes/GI/probe.h)
  - 将 Probe ray sampling 从每个 Probe 的 `10×10` 随机采样改为 `512` samples 的 deterministic Fibonacci sphere。
  - 去除 `global rand()` 与 `time()` 依赖，避免 Probe 间重复随机序列和 frame-to-frame noise。
  - 保留原有 `4π/N` Monte Carlo normalization 与 `surfelRayIndices` 映射。
  - 对 zero-length view vector 与 half vector 增加稳定 fallback，避免 `normalize(0)` 产生 NaN。

- [main.cpp](src/getting_started/GIApplication/main.cpp)
  - point-shadow `near_plane` 从 `1.0` 改为 `0.1`。
  - shadow `far_plane` 根据 point light 到 contract scene bounds 的最远距离动态计算，覆盖 room 内任意合法 light position。
  - 保留 margin，避免边界几何体因深度范围不足而错误丢失 shadow。

- [light_casters.fs](src/getting_started/GIApplication/light_casters.fs)
  - 将固定 `0.05` shadow bias 改为基于 surface normal/light direction 的小型 slope-aware bias。
  - 修正 shader 中 zero-length view/half vector 的数值稳定性。
  - 没有使用 exposure、gain、saturation 或颜色偏置。

## 验证结果

完整项目测试通过：

```text
100% tests passed, 0 tests failed out of 5
```

包括：

- `frame_timing`
- `realtime_capture`
- `render_contract`
- `prt_numerics_pbr`
- `prt_numerics_phong`

另外完成了两个 one-shot realtime export：

- 中央光源 + 默认强度
- corner light `7,5,7` + 非均匀 RGB intensity `350,250,150`

两组输出都成功生成：

```text
realtime.png
indirect-linear.pfm
state.json
```

并检查了：

- `state.json` pose/light round-trip 正确
- PFM 为 `800x600`、little-endian、linear HDR
- indirect buffer 中全部数值 finite
- 没有出现 NaN/Inf
- corner-light case 的 indirect lighting 随 RGB light intensity 正常变化

当前工作区修改集中在：

- [includes/GI/probe.h](includes/GI/probe.h)
- [src/getting_started/GIApplication/main.cpp](src/getting_started/GIApplication/main.cpp)
- [src/getting_started/GIApplication/light_casters.fs](src/getting_started/GIApplication/light_casters.fs)

没有修改 public render contract。</pre>

</details>
