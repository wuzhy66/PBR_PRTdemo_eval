# TEST01 · gpt-5.6-luna · Realtime rendering best-effort 全报告

> GitHub-readable evaluation report。本文件保留指标、过程分析和 tool-call 摘要，不嵌入体积过大的 tool input/output 或完整 Git diff。

## 最终结果

**Normalized improvement：`0.00000000` · Decision：`failed-regression`**

| Baseline A | Candidate B / Strict | Mean B−A | Cases | Strict / Excluded / Errors |
|---:|---:|---:|---:|---:|
| 0.81864903 | 0.83486219 | +0.01621316 | 200 | 200 / 0 / 0 |

`Normalized improvement` 是最终 coding improvement 分数；`Strict score` 是单个 renderer 对 offline reference 的绝对分数。

### 指标变化

| 指标 | 权重 | Baseline | Candidate | 变化 | 改善 | 退化 | 不变 |
|---|---:|---:|---:|---:|---:|---:|---:|
| FLIP perceptual score | 70% | 0.81916697 | 0.83209304 | +0.01292608 | 56 | 144 | 0 |
| Worst-patch FLIP | diagnostic | 0.60162365 | 0.68586534 | +0.08424170 | 77 | 123 | 0 |
| Indirect transport | 30% | 0.82374117 | 0.84905252 | +0.02531134 | 170 | 30 | 0 |
| Occlusion leak | diagnostic | 0.78038943 | 0.76897901 | -0.01141043 | 99 | 92 | 9 |
| Strict score | aggregate | 0.81864903 | 0.83486219 | +0.01621316 | 68 | 132 | 0 |

### Regression gates

| Gate | Required | Median delta | 改善 | 退化 | 不变 | 结果 |
|---|---:|---:|---:|---:|---:|---|
| Median FLIP delta | yes | -0.05811342 | 56 | 144 | 0 | FAIL |
| Median worst-patch FLIP delta | yes | -0.05081133 | 77 | 123 | 0 | FAIL |

## 总体判断

执行过程覆盖 PRT sampling、SH convolution、point-light shadow、数值稳定性、回归测试与 deterministic export，但没有在结束前进行与 offline reference 的 image-space A/B 检查。虽然 ungated normalized improvement 为 0.08940213，但 FLIP median delta 为 −0.05811342、Worst-patch FLIP median delta 为 −0.05081133，两项 regression gates 均失败，正式 Normalized improvement 为 0。

## 改动与实测评价

### `includes/GI/probe.h`

- 改动：以 deterministic spherical Fibonacci samples 替换 rand/time sampling；新增 analytic Lambertian SH convolution。
- 目标：降低 sampling 与二次 Monte Carlo projection 噪声，使输出可重复。
- 评测：Indirect transport 平均提升 0.02531134，170 case 改善、30 case 退化，方向总体有效。

### `src/getting_started/GIApplication/main.cpp`

- 改动：应用 analytic SH convolution，shadow near plane 改为 0.05，depth cubemap 使用 32-bit float。
- 目标：改善 PRT projection 与近距离 shadow coverage/precision。
- 评测：SH 改动有收益；shadow 参数造成旧 72 条系统性回归，新 targeted cases 则出现部分强收益。

### `src/getting_started/GIApplication/light_casters.fs`

- 改动：加入 normal-aware receiver bias 与 safe inverse-square distance。
- 目标：减少 contact shadow detachment、避免除零与 NaN/Inf。
- 评测：FLIP 平均仅提升 0.01292608，且 144/200 case 退化，说明 receiver bias 对场景配置高度敏感。

### `tests/prt_numerics.cpp`

- 改动：新增 constant-radiance analytic convolution regression。
- 目标：验证 SH cosine kernel band factors。
- 评测：覆盖局部数学性质，但未覆盖最终 image-space shadow correctness。

## 做得好的地方

- 从 baseline build/test 开始，随后对 sampling、SH projection、shadow 与 output contract 分层检查。
- 移除 wall-clock random sampling，并用重复导出的 SHA-256 验证 deterministic output。
- 新增 analytic convolution regression，完整 public tests 与 one-shot export 均通过。
- 保持一次 indirect bounce，没有用 exposure、gain 或颜色偏置掩盖误差。
- balanced core 72 条的分段 Normalized improvement 为 0.14588032，证明部分算法改动并非完全无效。

## 风险与不足

- 没有在提交结论前比较 baseline/candidate 与 offline reference 的完整画面；public tests 无法发现视觉回归。
- balanced core 为 30/72 改善，targeted cases 为 38/128 改善，泛化稳定性很弱。
- FLIP 有 56 case 改善、144 case 退化；Occlusion leak 平均退化 0.01141043，但该项仅作诊断。
- 两次 Agent 调用均失败，最终没有独立 shader/PRT review；工作区改动也未形成 candidate commit。

## 分项结论

| 维度 | 评价 | 说明 |
|---|---|---|
| 物理建模 | 局部有效 | analytic convolution 与 deterministic sampling 改善 indirect transport，但 shadow receiver bias 未稳定适配 scene scale。 |
| 验证完整性 | 不足 | unit tests 和 deterministic 检查充分，但缺少最终 image-space A/B。 |
| 泛化稳定性 | 较弱 | 旧集系统性退化，新 stress cases 部分强改善，结果高度依赖场景分布。 |
| 最终效果 | 失败 | Strict score 0.83486219，mean(B−A) +0.01621316，但 regression gates 失败；ungated 0.08940213，正式 Normalized improvement 0。 |

## 执行概览

- Test：`TEST01`
- Main model：`gpt-5.6-luna`
- Claude Code：`2.1.233`
- Candidate / Baseline：`worktree-c112401e4720` / `2a1c9dc`
- Tool calls：94（11 errors，11 warnings）
- Subagents：0 success / 2 attempts
- Git diff：4 files，+93 / -48，diff check `PASS`

### Tool 类型

| Tool | Calls |
|---|---:|
| Read | 27 |
| Edit | 21 |
| Bash | 15 |
| Glob | 9 |
| TaskOutput | 7 |
| Grep | 6 |
| TodoWrite | 4 |
| Agent | 2 |
| EnterPlanMode | 1 |
| Write | 1 |
| ExitPlanMode | 1 |

## 执行阶段

### #1–#40 · Contract 与 baseline

- 动作：读取 AGENTS/contract、renderer/shader/PRT/test，尝试 subagent review，并运行 baseline build/tests 后形成计划。
- 分析：覆盖面合理，但 Agent review 未成功；计划主要依赖代码推导，没有建立可量化的 image-space baseline。
- 证据：读取核心链路，baseline tests 通过，完成 implementation plan。

### #41–#67 · Sampling、SH 与 shadow

- 动作：实现 Fibonacci sampling、analytic cosine convolution、shadow precision/bias 与 regression tests。
- 分析：PRT 修改具备物理解释；shadow bias 同时改变大面积 direct visibility，风险高于局部数值测试能覆盖的范围。
- 证据：修改四个源码/测试文件，修复一次 regression 后全部 public tests 通过。

### #68–#85 · Export 与修正

- 动作：执行 contract one-shot export、检查 PFM/PNG/state，并继续调整 shader/main 后重复测试。
- 分析：验证了格式、finite/non-negative 与 contract，却没有检查画面是否更接近 offline reference。
- 证据：800×600 output、state round-trip 与完整 regression 均通过。

### #86–#94 · 收敛与可重复性

- 动作：最终 export、数值核对、diff review、重复导出 hash 比较并清理产物。
- 分析：工程收尾完整；把 deterministic correctness 当成视觉 correctness 的替代证据，导致系统性 shadow 回归未被发现。
- 证据：重复输出 hash 一致，工作区仅保留四个 staged 文件。

## Subagent

没有成功返回的 subagent。

## Git 文件变化

| File | Added | Deleted |
|---|---:|---:|
| `includes/GI/probe.h` | 47 | 25 |
| `src/getting_started/GIApplication/light_casters.fs` | 14 | 16 |
| `src/getting_started/GIApplication/main.cpp` | 7 | 7 |
| `tests/prt_numerics.cpp` | 25 | 0 |

Worktree status：`M  includes/GI/probe.h<br>M  src/getting_started/GIApplication/light_casters.fs<br>M  src/getting_started/GIApplication/main.cpp<br>M  tests/prt_numerics.cpp`

<details>
<summary><strong>Tool-call 流程摘要</strong></summary>

| # | 阶段 | Tool | 状态 | 摘要 |
|---:|---|---|---|---|
| 1 | Contract 与 baseline | EnterPlanMode | ok | {} |
| 2 | Contract 与 baseline | Glob | ok | <candidate-repository> |
| 3 | Contract 与 baseline | Grep | ok | <candidate-repository> |
| 4 | Contract 与 baseline | Read | error | <candidate-repository>\AGENTS.md |
| 5 | Contract 与 baseline | Read | error | <candidate-repository>\realtime-render-contract.json |
| 6 | Contract 与 baseline | Read | error | <candidate-repository>\AGENTS.md |
| 7 | Contract 与 baseline | Read | error | <candidate-repository>\realtime-render-contract.json |
| 8 | Contract 与 baseline | Glob | ok | <candidate-repository> |
| 9 | Contract 与 baseline | Glob | ok | <candidate-repository> |
| 10 | Contract 与 baseline | Glob | ok | <candidate-repository> |
| 11 | Contract 与 baseline | Read | warning | <candidate-repository>\AGENTS.md |
| 12 | Contract 与 baseline | Read | ok | <candidate-repository>\realtime-render-contract.json |
| 13 | Contract 与 baseline | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 14 | Contract 与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\render_contract.h |
| 15 | Contract 与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 16 | Contract 与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.vs |
| 17 | Contract 与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\ssaa_resolve.fs |
| 18 | Contract 与 baseline | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 19 | Contract 与 baseline | Read | warning | <candidate-repository>\tools\test.py |
| 20 | Contract 与 baseline | Read | warning | <candidate-repository>\tests\prt_numerics.cpp |
| 21 | Contract 与 baseline | Agent | error | 审查实时光照实现 |
| 22 | Contract 与 baseline | Agent | error | 审查实时光照实现 |
| 23 | Contract 与 baseline | Read | ok | <candidate-repository>\CMakeLists.txt |
| 24 | Contract 与 baseline | Grep | ok | <candidate-repository> |
| 25 | Contract 与 baseline | Read | warning | <candidate-repository>\tests\render_contract.cpp |
| 26 | Contract 与 baseline | Read | warning | <candidate-repository>\tests\realtime_capture.cpp |
| 27 | Contract 与 baseline | Bash | ok | 检查仓库状态与最近提交 |
| 28 | Contract 与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.fs |
| 29 | Contract 与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.gs |
| 30 | Contract 与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.vs |
| 31 | Contract 与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 32 | Contract 与 baseline | Grep | ok | <candidate-repository>\src\getting_started\GIApplication |
| 33 | Contract 与 baseline | Read | ok | <candidate-repository>\README.md |
| 34 | Contract 与 baseline | Glob | ok | <candidate-repository> |
| 35 | Contract 与 baseline | Glob | ok | <candidate-repository> |
| 36 | Contract 与 baseline | Bash | ok | 运行基线 build 与 regression tests |
| 37 | Contract 与 baseline | Glob | ok | <candidate-repository> |
| 38 | Contract 与 baseline | TaskOutput | warning | {"task_id":"bdoe73xlz","block":false,"timeout":[omitted]} |
| 39 | Contract 与 baseline | Write | ok | <candidate-repository>\.claude\plans\realtime-render-improvement.md |
| 40 | Contract 与 baseline | ExitPlanMode | ok | {} |
| 41 | Sampling、SH 与 shadow | TodoWrite | ok | 更新任务列表 |
| 42 | Sampling、SH 与 shadow | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 43 | Sampling、SH 与 shadow | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 44 | Sampling、SH 与 shadow | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 45 | Sampling、SH 与 shadow | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 46 | Sampling、SH 与 shadow | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 47 | Sampling、SH 与 shadow | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 48 | Sampling、SH 与 shadow | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 49 | Sampling、SH 与 shadow | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 50 | Sampling、SH 与 shadow | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 51 | Sampling、SH 与 shadow | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 52 | Sampling、SH 与 shadow | Edit | error | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 53 | Sampling、SH 与 shadow | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 54 | Sampling、SH 与 shadow | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 55 | Sampling、SH 与 shadow | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 56 | Sampling、SH 与 shadow | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 57 | Sampling、SH 与 shadow | Edit | ok | <candidate-repository>\.claude\plans\realtime-render-improvement.md |
| 58 | Sampling、SH 与 shadow | Edit | ok | <candidate-repository>\tests\prt_numerics.cpp |
| 59 | Sampling、SH 与 shadow | Edit | ok | <candidate-repository>\tests\prt_numerics.cpp |
| 60 | Sampling、SH 与 shadow | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 61 | Sampling、SH 与 shadow | TodoWrite | ok | 更新任务列表 |
| 62 | Sampling、SH 与 shadow | Bash | ok | 构建并运行修改后的全部 regression tests |
| 63 | Sampling、SH 与 shadow | TaskOutput | warning | {"task_id":"bos86v0cd","block":true,"timeout":[omitted]} |
| 64 | Sampling、SH 与 shadow | Edit | ok | <candidate-repository>\tests\prt_numerics.cpp |
| 65 | Sampling、SH 与 shadow | Bash | ok | 重新运行完整 regression tests |
| 66 | Sampling、SH 与 shadow | TaskOutput | warning | {"task_id":"bzrwfkw55","block":true,"timeout":[omitted]} |
| 67 | Sampling、SH 与 shadow | TodoWrite | ok | 更新任务列表 |
| 68 | Export 与修正 | Glob | ok | <candidate-repository> |
| 69 | Export 与修正 | Bash | ok | 执行一次 contract one-shot realtime export |
| 70 | Export 与修正 | TaskOutput | warning | {"task_id":"bre6cy094","block":true,"timeout":[omitted]} |
| 71 | Export 与修正 | Bash | ok | 从 shader 工作目录执行 one-shot export |
| 72 | Export 与修正 | TaskOutput | ok | {"task_id":"b1r3snwrg","block":true,"timeout":[omitted]} |
| 73 | Export 与修正 | Glob | ok | <candidate-repository> |
| 74 | Export 与修正 | Read | ok | <candidate-repository>\render-output-check\cases\baseline\state.json |
| 75 | Export 与修正 | Bash | ok | 检查导出 PFM 的尺寸与数值范围 |
| 76 | Export 与修正 | Grep | ok | <candidate-repository> |
| 77 | Export 与修正 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 78 | Export 与修正 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 79 | Export 与修正 | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 80 | Export 与修正 | Grep | error | <candidate-repository> |
| 81 | Export 与修正 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 82 | Export 与修正 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 83 | Export 与修正 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 84 | Export 与修正 | Bash | ok | 验证最终代码并运行全部测试 |
| 85 | Export 与修正 | TaskOutput | warning | {"task_id":"boffnps3o","block":true,"timeout":[omitted]} |
| 86 | 收敛与可重复性 | Bash | ok | 执行最终 one-shot realtime export |
| 87 | 收敛与可重复性 | TaskOutput | ok | {"task_id":"bsn8raz8f","block":true,"timeout":[omitted]} |
| 88 | 收敛与可重复性 | Bash | ok | 核对最终 realtime export 文件与数值 |
| 89 | 收敛与可重复性 | Bash | ok | 检查最终 diff 与工作区状态 |
| 90 | 收敛与可重复性 | Bash | ok | 清理验证产物并确认工作区 diff |
| 91 | 收敛与可重复性 | Bash | ok | 审阅最终 realtime rendering diff |
| 92 | 收敛与可重复性 | Bash | ok | 验证相同输入下 one-shot export 可重复 |
| 93 | 收敛与可重复性 | Bash | ok | 清理重复性验证产物 |
| 94 | 收敛与可重复性 | TodoWrite | ok | 更新任务列表 |

</details>

<details>
<summary><strong>Agent 最终回复</strong></summary>

<pre>已完成一轮 realtime rendering 物理质量改进，并完成构建、测试与 one-shot export 验证。

### 主要修改

- **改进 PRT indirect transport**
  - 将应用路径从“先计算 irradiance，再进行第二次 SH projection”改为：
    - 直接投影 incoming radiance；
    - 使用 analytic Lambertian cosine convolution；
    - 使用正确的 SH band factors：
      - `A0 = PI`
      - `A1 = 2PI / 3`
      - `A2 = PI / 4`
      - `l &gt;= 3 = 0`
  - 减少二次 Monte Carlo projection 带来的噪声和空间闪烁。
  - 保持 one indirect bounce，不改变 public render contract。
  - 相关位置：[probe.h](includes/GI/probe.h)、[main.cpp](src/getting_started/GIApplication/main.cpp)

- **改进 Probe sampling**
  - 移除 `rand()` 与 `time(NULL)`。
  - 使用 deterministic spherical Fibonacci samples。
  - 根据 probe 的稳定空间位置生成 phase，避免所有 probes 使用完全相同的样本排列。
  - 固定输入下输出现在可重复。

- **改进 point-light shadow**
  - shadow cubemap 使用明确的 `GL_DEPTH_COMPONENT32F`。
  - shadow projection `near_plane` 从 `1.0` 调整为 `0.05`，减少近距离光源或表面被裁剪的情况。
  - 使用 normal-aware receiver bias，降低接触阴影分离和 shadow acne。
  - 相关位置：[main.cpp](src/getting_started/GIApplication/main.cpp)、[light_casters.fs](src/getting_started/GIApplication/light_casters.fs)

- **改进 PBR 数值稳定性**
  - 对 point-light distance 使用 epsilon clamp。
  - 仍然保持正常情况下的 exact inverse-square falloff。
  - 避免 light 与 surface 极近时产生除零、NaN 或 Inf。

- **新增数值回归**
  - 增加 analytic Lambertian convolution 的 constant-radiance regression。
  - 相关位置：[prt_numerics.cpp](tests/prt_numerics.cpp)

### 验证结果

已运行：

```powershell
python .\tools\test.py
```

结果：

```text
100% tests passed, 0 tests failed out of 5
```

通过项目中的全部测试：

- `frame_timing`
- `realtime_capture`
- `render_contract`
- `prt_numerics_pbr`
- `prt_numerics_phong`

已执行 contract one-shot export，确认：

- process exit code 为 `0`
- 输出文件仅包含：
  - `realtime.png`
  - `indirect-linear.pfm`
  - `state.json`
- PNG dimensions：`800x600`
- PFM dimensions：`800x600`
- PFM float count：`1,440,000`
- PFM 数据全部 finite
- indirect lighting 非负
- state round-trip 正确
- 相同输入连续导出两次的三个文件 SHA-256 完全一致

当前工作区只保留 4 个源码/测试文件修改，没有保留验证生成物。</pre>

</details>
