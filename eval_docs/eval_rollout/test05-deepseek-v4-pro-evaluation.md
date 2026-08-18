# TEST05 · deepseek-v4-pro · Realtime rendering best-effort 全报告

> GitHub-readable evaluation report。本文件保留指标、过程分析和 tool-call 摘要，不嵌入体积过大的 tool input/output 或完整 Git diff。

## 最终结果

**Normalized improvement：`0.52008568` · Decision：`success`**

| Baseline A | Candidate B / Strict | Mean B−A | Cases | Strict / Excluded / Errors |
|---:|---:|---:|---:|---:|
| 0.81864903 | 0.91296707 | +0.09431804 | 200 | 200 / 0 / 0 |

`Normalized improvement` 是最终 coding improvement 分数；`Strict score` 是单个 renderer 对 offline reference 的绝对分数。

### 指标变化

| 指标 | 权重 | Baseline | Candidate | 变化 | 改善 | 退化 | 不变 |
|---|---:|---:|---:|---:|---:|---:|---:|
| FLIP perceptual score | 70% | 0.81916697 | 0.92474161 | +0.10557465 | 200 | 0 | 0 |
| Worst-patch FLIP | diagnostic | 0.60162365 | 0.78646260 | +0.18483895 | 181 | 19 | 0 |
| Indirect transport | 30% | 0.82374117 | 0.89123328 | +0.06749211 | 190 | 10 | 0 |
| Occlusion leak | diagnostic | 0.78038943 | 0.75634792 | -0.02404152 | 96 | 95 | 9 |
| Strict score | aggregate | 0.81864903 | 0.91296707 | +0.09431804 | 200 | 0 | 0 |

### Regression gates

| Gate | Required | Median delta | 改善 | 退化 | 不变 | 结果 |
|---|---:|---:|---:|---:|---:|---|
| Median FLIP delta | yes | +0.04557052 | 200 | 0 | 0 | PASS |
| Median worst-patch FLIP delta | yes | +0.07816103 | 181 | 19 | 0 | PASS |

## 总体判断

执行过程集中改进 PRT sampling、analytic SH cosine convolution 与 point-light shadow range/bias，并用 deterministic export、默认/角落光源 sanity check 和 regression tests 收敛。正式 200-case 评测中 FLIP 与 Strict score 均在全部 case 提升，Normalized improvement 为 0.52008568，排名第一；occlusion leak 仍有退化，但该项仅作诊断。

## 改动与实测评价

### `includes/GI/probe.h`

- 改动：使用 deterministic 2048-ray Fibonacci sphere，并以 analytic SH band factors 卷积 incoming radiance。
- 目标：降低 SH projection variance，消除 wall-clock sampling 与二次 Monte Carlo convolution。
- 评测：Indirect transport 平均提升 0.06749211，190 case 改善、10 case 退化；targeted 128 条平均提升 0.08292821。

### `src/getting_started/GIApplication/light_casters.fs`

- 改动：固定 shadow bias 改为 0.005～0.05 的 normal-aware bias。
- 目标：在 acne 与 peter-panning 之间按 receiver angle 调节。
- 评测：FLIP 平均提升 0.10557465，200/200 case 改善；targeted cases 的平均提升达到 0.14836651。

### `src/getting_started/GIApplication/main.cpp`

- 改动：应用 analytic convolution；shadow near/far 改为 0.1/50，覆盖室内近表面与房间对角线。
- 目标：修正 shadow clip coverage，同时保持一次 indirect bounce。
- 评测：完整 Strict score 从 0.81864903 提升到 0.91296707，平均 B−A 为 0.09431804。

### `tests/prt_numerics.cpp`

- 改动：新增 constant-radiance analytic convolution regression。
- 目标：验证 cosine kernel 对常量 radiance 输出 PI 倍 irradiance。
- 评测：局部数学回归与 FLIP/Indirect 的大范围 image-space 提升一致。

## 做得好的地方

- 先完成 renderer、contract、shader、PRT、capture 与 tests 的全链路扫描，再运行 baseline build/tests。
- 同时覆盖 GI 与 direct shadow，没有把任务局限于单一指标，也没有使用 exposure/gain 等艺术性 magic number。
- 对默认光源和角落光源分别 export，检查 PNG/PFM/state 与数值范围后再收敛。
- 正式 200-case 评测中 FLIP 与 Strict score 均为 200/200 case 改善；targeted cases 的分段 Normalized improvement 为 0.52177205。

## 风险与不足

- Occlusion leak 平均退化 0.02404152：96 case 改善、95 case 退化、9 case 不变；该项不参与总分，但仍提示遮挡区域值得继续检查。
- 70/30 正式协议下没有 Strict score 退化 case；后续仍应针对诊断图检查局部遮挡配置。
- 2048 rays 显著增加 Probe precomputation 成本；本协议不评分性能，但 128 条新 capture 的运行成本已明显高于 baseline。
- 没有成功 subagent review；对 probe-in-cube 问题仅做风险判断，没有实现 visibility-aware invalid-probe interpolation。
- 模型最终回复称工作区未提交，但实际 candidate 已形成 commit；执行描述与最终 repository provenance 存在轻微不一致。

## 分项结论

| 维度 | 评价 | 说明 |
|---|---|---|
| 物理建模 | 优秀 | SH cosine convolution、inverse-square direct lighting 与 shadow clip/bias 均有明确物理或数值依据。 |
| 验证完整性 | 良好 | 覆盖 baseline、regression、default/corner export 与 output numerics；trusted 200-case 评测进一步量化了收益与回归。 |
| 指标均衡 | 中等 | FLIP 与 indirect 提升强，但 occlusion leak 在 targeted stress cases 中出现显著净退化。 |
| 最终效果 | 成功 | Strict score 0.91296707，mean(B−A) +0.09431804，Normalized improvement 0.52008568。 |

## 执行概览

- Test：`TEST05`
- Main model：`deepseek-v4-pro`
- Claude Code：`2.1.233`
- Candidate / Baseline：`9d8d5b7` / `2a1c9dc`
- Tool calls：98（2 errors，13 warnings）
- Subagents：0 success / 0 attempts
- Git diff：4 files，+91 / -38，diff check `PASS`

### Tool 类型

| Tool | Calls |
|---|---:|
| Read | 50 |
| Bash | 18 |
| Edit | 11 |
| Grep | 8 |
| TodoWrite | 5 |
| PowerShell | 5 |
| Glob | 1 |

## 执行阶段

### #1–#30 · 全链路扫描与 baseline

- 动作：读取 renderer、contract、PRT、shadow、SSAA、capture 与 tests，运行 baseline build/tests。
- 分析：直接建立完整 rendering pipeline 心智模型，避免只优化 GI；没有成功调用 subagent。
- 证据：核心 source/test 全部覆盖，baseline tests 通过。

### #31–#60 · GI 与 shadow 实现

- 动作：实现 Fibonacci 2048 rays、analytic convolution、normal-aware shadow bias 与 regression test。
- 分析：修改集中且物理可解释；通过 export 图像与 PFM 数值检查，而非仅依赖编译。
- 证据：四个文件形成 91 additions / 38 deletions，tests 通过。

### #61–#89 · Shadow range 与场景检查

- 动作：分析输出、调整 near/far plane，并对默认和角落光源执行 one-shot export。
- 分析：用 contract room diagonal 约束 far plane，避免任意扩大；默认 case 对照降低改动风险。
- 证据：默认输出保持一致，角落光源成功覆盖，完整 tests 再次通过。

### #90–#98 · 收敛与清理

- 动作：检查 scene constants、最终 diff、工作区状态并清理临时 export。
- 分析：明确列出检查但未修改的 probe density、probe-in-cube、PCF 与 roughness 项，停止条件较清晰。
- 证据：最终只保留四个源码/测试文件改动，diff check 通过。

## Subagent

没有成功返回的 subagent。

## Git 文件变化

| File | Added | Deleted |
|---|---:|---:|
| `includes/GI/probe.h` | 42 | 21 |
| `src/getting_started/GIApplication/light_casters.fs` | 10 | 7 |
| `src/getting_started/GIApplication/main.cpp` | 13 | 10 |
| `tests/prt_numerics.cpp` | 26 | 0 |

Worktree status：`clean`

<details>
<summary><strong>Tool-call 流程摘要</strong></summary>

| # | 阶段 | Tool | 状态 | 摘要 |
|---:|---|---|---|---|
| 1 | 全链路扫描与 baseline | Bash | ok | List repo structure and git history |
| 2 | 全链路扫描与 baseline | Glob | ok | **/*.{cpp,h,hpp,glsl,vert,frag,comp,json,txt,py,md} |
| 3 | 全链路扫描与 baseline | Bash | ok | List project source files excluding third-party includes |
| 4 | 全链路扫描与 baseline | Bash | ok | Count lines in source files |
| 5 | 全链路扫描与 baseline | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 6 | 全链路扫描与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 7 | 全链路扫描与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\render_contract.h |
| 8 | 全链路扫描与 baseline | Read | ok | <candidate-repository>\realtime-render-contract.json |
| 9 | 全链路扫描与 baseline | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 10 | 全链路扫描与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\ssaa_resolve.fs |
| 11 | 全链路扫描与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\ssaa_resolve.vs |
| 12 | 全链路扫描与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.gs |
| 13 | 全链路扫描与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.fs |
| 14 | 全链路扫描与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.vs |
| 15 | 全链路扫描与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\probe.fs |
| 16 | 全链路扫描与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\camera.fs |
| 17 | 全链路扫描与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 18 | 全链路扫描与 baseline | Read | warning | <candidate-repository>\tests\render_contract.cpp |
| 19 | 全链路扫描与 baseline | Read | warning | <candidate-repository>\tests\prt_numerics.cpp |
| 20 | 全链路扫描与 baseline | Read | warning | <candidate-repository>\tests\realtime_capture.cpp |
| 21 | 全链路扫描与 baseline | Read | warning | <candidate-repository>\tests\frame_timing.cpp |
| 22 | 全链路扫描与 baseline | Read | warning | <candidate-repository>\tools\test.py |
| 23 | 全链路扫描与 baseline | Read | ok | <candidate-repository>\tools\build.py |
| 24 | 全链路扫描与 baseline | Read | ok | <candidate-repository>\tools\_tooling.py |
| 25 | 全链路扫描与 baseline | Read | ok | <candidate-repository>\CMakeLists.txt |
| 26 | 全链路扫描与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.vs |
| 27 | 全链路扫描与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\cube.vs |
| 28 | 全链路扫描与 baseline | Bash | ok | Locate learnopengl headers and root_directory template |
| 29 | 全链路扫描与 baseline | TodoWrite | ok | 更新任务列表 |
| 30 | 全链路扫描与 baseline | Bash | ok | Run baseline build and tests |
| 31 | GI 与 shadow 实现 | Grep | ok | CalculateIrradiance\|ProjectIrradianceFunctionSH\|ProjectRadianceFunctionSH\|\.irradiances\|GenerateSampleRays |
| 32 | GI 与 shadow 实现 | Read | warning | <user-home>\AppData\Local\Temp\claude\d--PBR-PRTdemo-TEST05\aa9274a1-ce90-4ec3-a5b8-bfb5f88ceab5\tasks\b7m9ahuwr.output |
| 33 | GI 与 shadow 实现 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 34 | GI 与 shadow 实现 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 35 | GI 与 shadow 实现 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 36 | GI 与 shadow 实现 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 37 | GI 与 shadow 实现 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 38 | GI 与 shadow 实现 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 39 | GI 与 shadow 实现 | TodoWrite | ok | 更新任务列表 |
| 40 | GI 与 shadow 实现 | Bash | ok | Build and run tests after GI changes |
| 41 | GI 与 shadow 实现 | Read | warning | <user-home>\AppData\Local\Temp\claude\d--PBR-PRTdemo-TEST05\aa9274a1-ce90-4ec3-a5b8-bfb5f88ceab5\tasks\bd38c610v.output |
| 42 | GI 与 shadow 实现 | PowerShell | error | Run one-shot export with GI changes |
| 43 | GI 与 shadow 实现 | Read | warning | <candidate-repository>\includes\learnopengl\shader_m.h |
| 44 | GI 与 shadow 实现 | Read | ok | <candidate-repository>\includes\learnopengl\filesystem.h |
| 45 | GI 与 shadow 实现 | Bash | ok | Check shader locations and gitignore |
| 46 | GI 与 shadow 实现 | PowerShell | ok | Run one-shot export from exe directory |
| 47 | GI 与 shadow 实现 | Read | ok | <candidate-repository>\_export_gi\cases\gi-check\realtime.png |
| 48 | GI 与 shadow 实现 | Bash | ok | Check Python imaging libraries |
| 49 | GI 与 shadow 实现 | Bash | ok | Analyze exported PNG and PFM |
| 50 | GI 与 shadow 实现 | Read | ok | <candidate-repository>\_export_gi\thumb.png |
| 51 | GI 与 shadow 实现 | Bash | ok | Convert thumbnail to JPEG |
| 52 | GI 与 shadow 实现 | Read | ok | <candidate-repository>\_export_gi\thumb.jpg |
| 53 | GI 与 shadow 实现 | Read | ok | <candidate-repository>\tests\prt_numerics.cpp |
| 54 | GI 与 shadow 实现 | Edit | ok | <candidate-repository>\tests\prt_numerics.cpp |
| 55 | GI 与 shadow 实现 | Edit | ok | <candidate-repository>\tests\prt_numerics.cpp |
| 56 | GI 与 shadow 实现 | Bash | ok | Rebuild and test with new convolution test |
| 57 | GI 与 shadow 实现 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 58 | GI 与 shadow 实现 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 59 | GI 与 shadow 实现 | Read | warning | <user-home>\AppData\Local\Temp\claude\d--PBR-PRTdemo-TEST05\aa9274a1-ce90-4ec3-a5b8-bfb5f88ceab5\tasks\bxbx7jrlr.output |
| 60 | GI 与 shadow 实现 | TodoWrite | ok | 更新任务列表 |
| 61 | Shadow range 与场景检查 | Bash | warning | 运行 test.py 验证 shadow 修改后构建与测试 |
| 62 | Shadow range 与场景检查 | PowerShell | ok | 运行 one-shot export 验证 shadow 修改并计时 |
| 63 | Shadow range 与场景检查 | Bash | error | 数值分析 PNG/PFM 检测 acne 与回归 |
| 64 | Shadow range 与场景检查 | Bash | ok | 无 scipy 数值分析 PNG/PFM/state.json |
| 65 | Shadow range 与场景检查 | TodoWrite | ok | 更新任务列表 |
| 66 | Shadow range 与场景检查 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 67 | Shadow range 与场景检查 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 68 | Shadow range 与场景检查 | Grep | ok | <candidate-repository>\includes\GI\probe.h |
| 69 | Shadow range 与场景检查 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 70 | Shadow range 与场景检查 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 71 | Shadow range 与场景检查 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 72 | Shadow range 与场景检查 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 73 | Shadow range 与场景检查 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\ssaa_resolve.fs |
| 74 | Shadow range 与场景检查 | Read | ok | <candidate-repository>\realtime-render-contract.json |
| 75 | Shadow range 与场景检查 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.gs |
| 76 | Shadow range 与场景检查 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.fs |
| 77 | Shadow range 与场景检查 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.vs |
| 78 | Shadow range 与场景检查 | Read | warning | <candidate-repository>\tools\test.py |
| 79 | Shadow range 与场景检查 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 80 | Shadow range 与场景检查 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 81 | Shadow range 与场景检查 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 82 | Shadow range 与场景检查 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 83 | Shadow range 与场景检查 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 84 | Shadow range 与场景检查 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 85 | Shadow range 与场景检查 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 86 | Shadow range 与场景检查 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 87 | Shadow range 与场景检查 | Bash | warning | 重建并运行测试验证 shadow near/far 修改 |
| 88 | Shadow range 与场景检查 | PowerShell | ok | 验证 shadow near/far 修改后默认 case export 不变 |
| 89 | Shadow range 与场景检查 | PowerShell | ok | 角落光源 sanity check 验证 far_plane 修复 |
| 90 | 收敛与清理 | Grep | ok | <candidate-repository>\includes |
| 91 | 收敛与清理 | Grep | ok | WallPositions\|CubePositions\|NearPlane\|FarPlane\|CubeAlbedo |
| 92 | 收敛与清理 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\render_contract.h |
| 93 | 收敛与清理 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 94 | 收敛与清理 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 95 | 收敛与清理 | Bash | ok | 查看工作区变更 |
| 96 | 收敛与清理 | Bash | ok | 查看完整 diff 审查改动 |
| 97 | 收敛与清理 | Bash | ok | 清理临时 export 目录 |
| 98 | 收敛与清理 | TodoWrite | ok | 更新任务列表 |

</details>

<details>
<summary><strong>Agent 最终回复</strong></summary>

<pre>已完成一轮收敛迭代。以下是本轮改动与验证结论。

## 本轮改动（4 项物理正确性改进）

1. **GI 精度：分析式 cosine 卷积**（[probe.h:716](includes/GI/probe.h#L716)）
   用 Ramamoorthi &amp; Hanrahan 2001 的对角卷积矩阵 `{π, 2π/3, π/4, 0, -π/24}` 把 incoming radiance 的 SH 系数精确转为 irradiance 系数，替代原先 O(N²) 的 Monte-Carlo 逐样本卷积，同时消除了 probe 构造函数里的 `CalculateIrradiance()` 冗余开销。

2. **GI 采样：Fibonacci sphere 2048 rays**（[probe.h:297](includes/GI/probe.h#L297)）
   由 `time(NULL)` 种子 + 少量 stratified 采样改为完全确定、近均匀的 Fibonacci 球面分布，降低 SH 投影方差，同时满足 contract 的 determinism 要求（不再读取 wall clock）。

3. **Shadow：法线相关 bias**（[light_casters.fs:77](src/getting_started/GIApplication/light_casters.fs#L77)）
   由固定 `0.05` 改为 `max(0.05*(1-|N·L|), 0.005)`：正对光源表面用小 bias 贴合几何阴影，grazing 表面用大 bias 抑制 acne，避免固定大 bias 的 peter-panning。

4. **Shadow：near/far clip 范围**（[main.cpp:561](src/getting_started/GIApplication/main.cpp#L561)）
   `near_plane 1.0→0.1`、`far_plane 25→50`，覆盖房间对角线约 29.7，保证光源位于任意角落时远墙阴影不被裁剪、近墙几何不漏阴影。

## 验证结果

- `python tools/test.py`：build + 5 项 ctest 全绿（含新增的 `testAnalyticConvolutionGivesPiForConstantRadiance` 单元测试）。
- one-shot export：`realtime.png` 800×600、`indirect-linear.pfm` RGB32F、`state.json` pose round-trip 全部正确，exit 0，耗时约 3.8s。
- 默认 case（light 0,5,0）输出与 baseline 一致（mean [66.63, 127.06, 68.02]），证明 near/far 改动不影响默认场景；角落光源 case 也正常导出。

## 检查过但判定无需改动的点（收敛依据）

- **probe 网格密度**（7×4×7=196）：房间彩色 bleed 为低频，SH3+196 probes 已足够，提升密度收益边际、且会放大 probe-in-cube 光漏问题。
- **probe-in-cube 光漏**（`improve_probesInCubes` 让立方体内 probe「看穿」自身）：仅影响 6/196 个 probe、6 个小侧立方体，正确修复需引入 invalid-probe + 重归一化插值，风险高收益低。
- **PCF 软阴影**：point light 为无穷小光源，硬阴影是物理正确的，2×2 SSAA 已做边缘抗锯齿。
- **roughness=1 的小 specular**：粗糙 dielectric 的 Fresnel F0=0.04 反射是物理正确的，非 bug。
- **SH ringing**：shader 已在重建后做 `max(irradiance, 0)` 非负钳制（物理约束，非颜色偏置）。

改动留在工作区未提交（按规则不主动 commit）。如需我提交，请告知。</pre>

</details>
