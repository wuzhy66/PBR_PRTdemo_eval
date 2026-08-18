# TEST04 · gpt-5.6-luna · Realtime rendering best-effort 全报告

> GitHub-readable evaluation report。本文件保留指标、过程分析和 tool-call 摘要，不嵌入体积过大的 tool input/output 或完整 Git diff。

## 最终结果

**Normalized improvement：`0.41786051` · Decision：`success`**

| Baseline A | Candidate B / Strict | Mean B−A | Cases | Strict / Excluded / Errors |
|---:|---:|---:|---:|---:|
| 0.81864903 | 0.89442844 | +0.07577941 | 200 | 200 / 0 / 0 |

`Normalized improvement` 是最终 coding improvement 分数；`Strict score` 是单个 renderer 对 offline reference 的绝对分数。

### 指标变化

| 指标 | 权重 | Baseline | Candidate | 变化 | 改善 | 退化 | 不变 |
|---|---:|---:|---:|---:|---:|---:|---:|
| FLIP perceptual score | 70% | 0.81916697 | 0.90988384 | +0.09071687 | 185 | 15 | 0 |
| Worst-patch FLIP | diagnostic | 0.60162365 | 0.76316051 | +0.16153686 | 168 | 32 | 0 |
| Indirect transport | 30% | 0.82374117 | 0.86478603 | +0.04104485 | 174 | 26 | 0 |
| Occlusion leak | diagnostic | 0.78038943 | 0.75766328 | -0.02272616 | 111 | 80 | 9 |
| Strict score | aggregate | 0.81864903 | 0.89442844 | +0.07577941 | 183 | 17 | 0 |

### Regression gates

| Gate | Required | Median delta | 改善 | 退化 | 不变 | 结果 |
|---|---:|---:|---:|---:|---:|---|
| Median FLIP delta | yes | +0.03226492 | 185 | 15 | 0 | PASS |
| Median worst-patch FLIP delta | yes | +0.05669143 | 168 | 32 | 0 | PASS |

## 总体判断

执行采用较保守路线，集中保留 deterministic Fibonacci Probe sampling、point-shadow range/bias、Fresnel clamp 和 regression test。正式 200-case 评测中 Strict score 在 183/200 case 改善，Normalized improvement 为 0.41786051，排名第二；targeted 128 条分段分数 0.41037166，说明小范围改动具有较好的泛化性。

## 改动与实测评价

### `includes/GI/probe.h`

- 改动：100 random stratified directions 改为 256 deterministic spherical-Fibonacci；Fresnel cosine clamp。
- 目标：提高 sampling coverage、determinism 与数值稳定性。
- 评测：Indirect transport 平均提升 0.04104485，174 case 改善、26 case 退化；采样改动收益稳定。

### `light_casters.fs`

- 改动：shadow bias 0.05→0.02；GLSL Fresnel cosine clamp。
- 目标：减少 peter-panning 与 grazing numerical error。
- 评测：FLIP 平均提升 0.09071687，但固定 bias 仍伴随 occlusion leak 平均退化 0.02272616。

### `main.cpp`

- 改动：point-shadow near/far 使用 contract 0.1/100。
- 目标：避免移动 light 时近远 geometry 被 clip。
- 评测：range 覆盖安全但不紧；完整 Strict score 平均提升 0.07577941。

### `tests/prt_numerics.cpp`

- 改动：新增 deterministic Probe sampling test。
- 目标：防止重新引入 random/time dependency。
- 评测：直接锁定 deterministic sampling，正式 200-case 结果确认主要改动有效。

## 做得好的地方

- 修改范围集中在四个文件，没有为追求规模而扩张 pipeline。
- Fibonacci sampling 消除了 wall clock/global rand 依赖，并新增 deterministic regression test。
- 完整 build/CTest 和 one-shot export 被重复验证。
- 正式评测中 FLIP 为 185 case 改善、15 case 退化；Strict 为 183 case 改善、17 case 退化。

## 风险与不足

- 四次 Agent 调用全部因 Windows drive-letter case/isolation validator 失败。
- Shadow bias=0.02 仍是固定 world-space 常数，没有由 cubemap resolution、distance 和 receiver slope 推导。
- Occlusion leak 平均退化 0.02272616：111 case 改善、80 case 退化、9 case 不变；该项仅作诊断。
- 直接使用 far plane 100 大于场景实际需要，且没有修正旧 irradiance double projection error。

## 分项结论

| 维度 | 评价 | 说明 |
|---|---|---|
| 自主持续性 | 中等 | 完成多轮 build/export，但 subagent 失败后转为单 agent。 |
| 修改风险 | 较低 | 四文件、小范围、附 regression test，容易审查。 |
| 泛化性 | 良好 | balanced core 72 条和 targeted 128 条均获得稳定正改进。 |
| 模型归因 | 清晰 | 所有 subagent 均未启动，最终代码完全来自 gpt-5.6-luna 主 agent。 |
| 最终效果 | 成功 | Strict score 0.89442844，mean(B−A) +0.07577941，Normalized improvement 0.41786051。 |

## 执行概览

- Test：`TEST04`
- Main model：`gpt-5.6-luna`
- Claude Code：`2.1.233`
- Candidate / Baseline：`worktree-e3b0c44298fc` / `73b22e8`
- Tool calls：96（15 errors，12 warnings）
- Subagents：0 success / 4 attempts
- Git diff：0 files，+0 / -0，diff check `PASS`

### Tool 类型

| Tool | Calls |
|---|---:|
| Read | 27 |
| Edit | 15 |
| PowerShell | 13 |
| Grep | 12 |
| TaskOutput | 11 |
| Bash | 6 |
| Glob | 5 |
| Agent | 4 |
| EnterPlanMode | 1 |
| Write | 1 |
| ExitPlanMode | 1 |

## 执行阶段

### #1–#42 · Plan 与 pipeline 扫描

- 动作：进入 Plan Mode，尝试四个只读 subagent，读取 contract、PRT、shader、tests 与 export。
- 分析：扫描覆盖完整；所有 subagent 在开始推理前因 worktree isolation 失败。
- 证据：主 agent 独立建立修改计划和 baseline tests。

### #43–#55 · Sampling 实现

- 动作：替换 random Probe directions，反复 build/test，并进行首次 one-shot export。
- 分析：优先处理确定性和采样覆盖，是低风险高收益入口。
- 证据：Build/CTest 与 export 成功。

### #56–#80 · Shadow 与数值边界

- 动作：修改 shadow range、bias、CPU/GLSL Fresnel，并新增 sampling test。
- 分析：保持修改范围有限；shadow 参数依据不如 resolution-aware 方案充分。
- 证据：完整 tests 再次通过。

### #81–#96 · 最终验证与清理

- 动作：执行最终 export、state/dimensions 检查、diff review、清理临时产物并再次运行 tests。
- 分析：收尾验证完整，但未在 subagent 失败后重新建立独立 review。
- 证据：Session 报告 5/5 CTest、三份输出和 state round-trip 通过。

## Subagent

没有成功返回的 subagent。

## Git 文件变化

| File | Added | Deleted |
|---|---:|---:|

Worktree status：`?? .claude/`

<details>
<summary><strong>Tool-call 流程摘要</strong></summary>

| # | 阶段 | Tool | 状态 | 摘要 |
|---:|---|---|---|---|
| 1 | Plan 与 pipeline 扫描 | EnterPlanMode | ok | {} |
| 2 | Plan 与 pipeline 扫描 | Glob | ok | <candidate-repository> |
| 3 | Plan 与 pipeline 扫描 | Grep | ok | <candidate-repository> |
| 4 | Plan 与 pipeline 扫描 | Agent | error | 审查渲染架构 |
| 5 | Plan 与 pipeline 扫描 | Agent | error | 审查测试契约 |
| 6 | Plan 与 pipeline 扫描 | Glob | ok | <candidate-repository> |
| 7 | Plan 与 pipeline 扫描 | Glob | ok | <candidate-repository> |
| 8 | Plan 与 pipeline 扫描 | Glob | ok | <candidate-repository> |
| 9 | Plan 与 pipeline 扫描 | Read | error | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 10 | Plan 与 pipeline 扫描 | Read | error | <candidate-repository>\includes\GI\probe.h |
| 11 | Plan 与 pipeline 扫描 | Read | error | <candidate-repository>\realtime-render-contract.json |
| 12 | Plan 与 pipeline 扫描 | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 13 | Plan 与 pipeline 扫描 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 14 | Plan 与 pipeline 扫描 | Read | ok | <candidate-repository>\realtime-render-contract.json |
| 15 | Plan 与 pipeline 扫描 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 16 | Plan 与 pipeline 扫描 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\probe.fs |
| 17 | Plan 与 pipeline 扫描 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\ssaa_resolve.fs |
| 18 | Plan 与 pipeline 扫描 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\render_contract.h |
| 19 | Plan 与 pipeline 扫描 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.vs |
| 20 | Plan 与 pipeline 扫描 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.fs |
| 21 | Plan 与 pipeline 扫描 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.vs |
| 22 | Plan 与 pipeline 扫描 | Read | warning | <candidate-repository>\tests\prt_numerics.cpp |
| 23 | Plan 与 pipeline 扫描 | Read | warning | <candidate-repository>\tools\test.py |
| 24 | Plan 与 pipeline 扫描 | Glob | ok | <candidate-repository> |
| 25 | Plan 与 pipeline 扫描 | Read | warning | <candidate-repository>\tests\render_contract.cpp |
| 26 | Plan 与 pipeline 扫描 | Read | warning | <candidate-repository>\tests\realtime_capture.cpp |
| 27 | Plan 与 pipeline 扫描 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 28 | Plan 与 pipeline 扫描 | Read | error | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.cpp |
| 29 | Plan 与 pipeline 扫描 | Read | ok | <candidate-repository>\CMakeLists.txt |
| 30 | Plan 与 pipeline 扫描 | Read | ok | <candidate-repository>\README.md |
| 31 | Plan 与 pipeline 扫描 | Read | ok | <candidate-repository>\tools\build.py |
| 32 | Plan 与 pipeline 扫描 | Grep | ok | <candidate-repository> |
| 33 | Plan 与 pipeline 扫描 | Bash | ok | 检查工作树与最近提交 |
| 34 | Plan 与 pipeline 扫描 | Agent | error | 审查着色器物理性 |
| 35 | Plan 与 pipeline 扫描 | Agent | error | 审查 PRT 数值模型 |
| 36 | Plan 与 pipeline 扫描 | Bash | ok | 运行基线 build 与 regression tests |
| 37 | Plan 与 pipeline 扫描 | TaskOutput | warning | {"task_id":"brbvtfk0k","block":true,"timeout":[omitted]} |
| 38 | Plan 与 pipeline 扫描 | Read | error | <claude-project>\memory\feedback_language_preference.md |
| 39 | Plan 与 pipeline 扫描 | TaskOutput | error | {"task_id":"researcher","block":false,"timeout":[omitted]} |
| 40 | Plan 与 pipeline 扫描 | Write | ok | <user-home>\.claude\plans\prt-realtime-rendering.md |
| 41 | Plan 与 pipeline 扫描 | ExitPlanMode | ok | {} |
| 42 | Plan 与 pipeline 扫描 | Grep | ok | <candidate-repository> |
| 43 | Sampling 实现 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 44 | Sampling 实现 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 45 | Sampling 实现 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 46 | Sampling 实现 | PowerShell | ok | 运行基线 build 与 regression tests |
| 47 | Sampling 实现 | TaskOutput | warning | {"task_id":"b83oqrysk","block":true,"timeout":[omitted]} |
| 48 | Sampling 实现 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 49 | Sampling 实现 | PowerShell | ok | 重新运行 build 与 regression tests |
| 50 | Sampling 实现 | TaskOutput | warning | {"task_id":"bv4dja7k0","block":true,"timeout":[omitted]} |
| 51 | Sampling 实现 | PowerShell | ok | 执行一次 deterministic realtime frame export |
| 52 | Sampling 实现 | TaskOutput | warning | {"task_id":"br9708oty","block":true,"timeout":[omitted]} |
| 53 | Sampling 实现 | PowerShell | ok | 从 shader asset 目录执行 realtime export |
| 54 | Sampling 实现 | TaskOutput | ok | {"task_id":"b8e18vsqe","block":true,"timeout":[omitted]} |
| 55 | Sampling 实现 | PowerShell | ok | 验证 realtime export 文件与尺寸 |
| 56 | Shadow 与数值边界 | Edit | error | <candidate-repository>\src\getting_started\main.cpp |
| 57 | Shadow 与数值边界 | Edit | error | <candidate-repository>\src\getting_started\main.cpp |
| 58 | Shadow 与数值边界 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 59 | Shadow 与数值边界 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 60 | Shadow 与数值边界 | Grep | ok | <candidate-repository>\includes\GI\probe.h |
| 61 | Shadow 与数值边界 | Read | error | <user-home>\AppData\Local\Temp\claude\d--PBR_PRTdemo-TEST04\d49378d8-29ab-4ac4-a3d8-074bc16159c9\tasks\br9708oty.output |
| 62 | Shadow 与数值边界 | PowerShell | ok | 重新构建 renderer |
| 63 | Shadow 与数值边界 | TaskOutput | ok | {"task_id":"b6jy61vqr","block":true,"timeout":[omitted]} |
| 64 | Shadow 与数值边界 | PowerShell | ok | 验证 shadow range 改动的 realtime export |
| 65 | Shadow 与数值边界 | TaskOutput | ok | {"task_id":"bvkl2fq9a","block":true,"timeout":[omitted]} |
| 66 | Shadow 与数值边界 | PowerShell | ok | 校验改进后导出结果 |
| 67 | Shadow 与数值边界 | Read | warning | <candidate-repository>\tests\prt_numerics.cpp |
| 68 | Shadow 与数值边界 | Grep | ok | <candidate-repository> |
| 69 | Shadow 与数值边界 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication |
| 70 | Shadow 与数值边界 | Bash | ok | 查看当前渲染改动差异 |
| 71 | Shadow 与数值边界 | Grep | ok | <candidate-repository>\tests |
| 72 | Shadow 与数值边界 | Grep | ok | <candidate-repository>\includes\GI\probe.h |
| 73 | Shadow 与数值边界 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 74 | Shadow 与数值边界 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 75 | Shadow 与数值边界 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 76 | Shadow 与数值边界 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 77 | Shadow 与数值边界 | Edit | ok | <candidate-repository>\tests\prt_numerics.cpp |
| 78 | Shadow 与数值边界 | Edit | ok | <candidate-repository>\tests\prt_numerics.cpp |
| 79 | Shadow 与数值边界 | PowerShell | ok | 运行完整 build 与 regression tests |
| 80 | Shadow 与数值边界 | TaskOutput | warning | {"task_id":"b5cn1xkiw","block":true,"timeout":[omitted]} |
| 81 | 最终验证与清理 | PowerShell | ok | 执行最终 deterministic realtime frame export |
| 82 | 最终验证与清理 | TaskOutput | ok | {"task_id":"bj4sv0m14","block":true,"timeout":[omitted]} |
| 83 | 最终验证与清理 | PowerShell | ok | 验证最终导出文件和 round-trip state |
| 84 | 最终验证与清理 | Bash | error | 检查最终 diff 与空白错误 |
| 85 | 最终验证与清理 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 86 | 最终验证与清理 | PowerShell | ok | 清理临时导出并检查工作树 |
| 87 | 最终验证与清理 | Bash | ok | 复核最终渲染改动 |
| 88 | 最终验证与清理 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 89 | 最终验证与清理 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 90 | 最终验证与清理 | PowerShell | ok | 确认清理后仍通过完整测试 |
| 91 | 最终验证与清理 | TaskOutput | warning | {"task_id":"bc0y8p9m7","block":true,"timeout":[omitted]} |
| 92 | 最终验证与清理 | Bash | ok | 最终检查 diff 与工作树状态 |
| 93 | 最终验证与清理 | Grep | ok | <candidate-repository>\includes\GI\probe.h |
| 94 | 最终验证与清理 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication |
| 95 | 最终验证与清理 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication |
| 96 | 最终验证与清理 | Grep | ok | <candidate-repository>\tests |

</details>

<details>
<summary><strong>Agent 最终回复</strong></summary>

<pre>已完成一轮完整 realtime rendering 改进，并持续验证到当前收敛点。主要修改如下：

### 已完成的渲染改进

- **Probe sampling**
  - 将原先每个 Probe 的 `10x10=100` 个随机方向改为 `256` 个 deterministic spherical-Fibonacci samples。
  - 移除 `rand()`、`time()` 和 global random state 依赖，避免 Probe generation 和 dynamic-light 更新产生不可复现结果。
  - 保持原有 `4π/N` Monte Carlo normalization、Ray/Surfel index mapping 与 one-bounce transport 语义。
  - 位置：[probe.h:292](includes/GI/probe.h#L292)

- **Point-light shadow range**
  - 将 point shadow cubemap 的 depth range 从 `near=1/far=25` 调整为 contract-compatible `near=0.1/far=100`。
  - 避免移动光源或较远场景几何超出 shadow range 后产生错误漏光/阴影裁剪。
  - 位置：[main.cpp:560](src/getting_started/GIApplication/main.cpp#L560)

- **Shadow bias**
  - 将固定的较大 bias 从 `0.05` 调整为更小的 world-space bias `0.02`，减少近距离阴影被错误抹除的情况。
  - 位置：[light_casters.fs:77](src/getting_started/GIApplication/light_casters.fs#L77)

- **Fresnel 数值边界**
  - 对 GLSL 与 CPU-side Fresnel Schlick 的 `cosTheta` 显式 clamp 到 `[0,1]`，避免 grazing/数值误差导致非物理 Fresnel 值。
  - 位置：[light_casters.fs:168](src/getting_started/GIApplication/light_casters.fs#L168)、[probe.h:55](includes/GI/probe.h#L55)

- **Regression coverage**
  - 增加 deterministic Probe sampling regression test，验证默认 sample 数量和方向序列稳定。
  - 位置：[prt_numerics.cpp:53](tests/prt_numerics.cpp#L53)

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
- **100% tests passed**

另外实际执行了 one-shot realtime export，结果：

- process exit code：`0`
- `realtime.png`：`800x600` RGB8 PNG
- `indirect-linear.pfm`：`800x600` RGB32F PFM
- `state.json`：camera/light state round-trip 正确
- 输出目录只包含 contract 要求的三份文件

未修改 `realtime-render-contract.json`，未改变 scene geometry、material、camera、light intensity、SSAA、tone mapping、color space 或 one-bounce 限制。</pre>

</details>
