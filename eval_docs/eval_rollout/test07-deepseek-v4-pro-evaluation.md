# TEST07 · deepseek-v4-pro · Realtime rendering best-effort 全报告

> GitHub-readable evaluation report。本文件保留指标、过程分析和 tool-call 摘要，不嵌入体积过大的 tool input/output 或完整 Git diff。

## 最终结果

**Normalized improvement：`0.20662320` · Decision：`success`**

| Baseline A | Candidate B / Strict | Mean B−A | Cases | Strict / Excluded / Errors |
|---:|---:|---:|---:|---:|
| 0.81864903 | 0.85612035 | +0.03747132 | 200 | 200 / 0 / 0 |

`Normalized improvement` 是最终 coding improvement 分数；`Strict score` 是单个 renderer 对 offline reference 的绝对分数。

### 指标变化

| 指标 | 权重 | Baseline | Candidate | 变化 | 改善 | 退化 | 不变 |
|---|---:|---:|---:|---:|---:|---:|---:|
| FLIP perceptual score | 70% | 0.81916697 | 0.84137524 | +0.02220827 | 175 | 25 | 0 |
| Worst-patch FLIP | diagnostic | 0.60162365 | 0.63063569 | +0.02901204 | 156 | 44 | 0 |
| Indirect transport | 30% | 0.82374117 | 0.89992544 | +0.07618427 | 190 | 10 | 0 |
| Occlusion leak | diagnostic | 0.78038943 | 0.76570952 | -0.01467991 | 107 | 84 | 9 |
| Strict score | aggregate | 0.81864903 | 0.85612035 | +0.03747132 | 186 | 14 | 0 |

### Regression gates

| Gate | Required | Median delta | 改善 | 退化 | 不变 | 结果 |
|---|---:|---:|---:|---:|---:|---|
| Median FLIP delta | yes | +0.01927092 | 175 | 25 | 0 | PASS |
| Median worst-patch FLIP delta | yes | +0.01774288 | 156 | 44 | 0 | PASS |

## 总体判断

本轮通过提高 Probe ray 数与 grid density、改进 point-shadow slope-scaled bias，并修复从 repository root 加载 shader 的 runtime ABI。正式 200-case 评测中 Strict score 从 0.81864903 提升到 0.85612035，FLIP 与 Worst-patch FLIP 的 median regression gates 均通过，Normalized improvement 为 0.[timing omitted]。主要收益来自 Indirect transport（平均 +0.07618427），但 Occlusion diagnostic 平均下降 -0.01467991，说明遮挡区域仍存在明显的非均匀回归。

## 改动与实测评价

### `includes/GI/probe.h`

- 改动：将 GenerateSampleRays 的默认分层采样规模从 N=10 提高到 N=20，即每个 Probe 的 sample rays 从 100 增至 400。
- 目标：降低一次 indirect bounce 的 SH projection Monte Carlo variance，提高低频 transport coefficient 的稳定性。
- 评测：与更密 Probe grid 共同作用后，Indirect transport 平均从 0.82374117 提升到 0.89992544：190 case 改善、10 case 退化，是本轮最明确的指标收益。

### `src/getting_started/GIApplication/main.cpp`

- 改动：将 Probe grid 从 7×4×7（196 probes）提高到 11×7×11（847 probes），并使用 FileSystem::getPath 解析六个 shader runtime assets。
- 目标：减少 cube 与墙角附近 indirect lighting 的 trilinear spatial blur，同时保证 evaluator 从 repository root 启动时能够稳定加载 shader。
- 评测：Strict score 平均提升 0.03747132，186 case 改善、14 case 退化；shader path 属于 ABI correctness，主要画质收益应与更高的 spatial/sampling density 相关。

### `src/getting_started/GIApplication/light_casters.fs`

- 改动：将固定 0.05 world-unit point-shadow bias 改为 max(0.015×(1−N·L), 0.003) 的 slope-scaled receiver bias。
- 目标：降低过大固定 bias 导致的 peter-panning 与 light leak，同时在 grazing angle 保留抑制 shadow acne 的余量。
- 评测：FLIP 平均提升 0.02220827，Worst-patch FLIP 平均提升 0.02901204；但 Occlusion diagnostic 平均下降 0.01467991，说明 shadow/occlusion tail cases 仍需针对性检查。

## 做得好的地方

- 最终 186/200 case 的 Strict score 改善，mean improvement 为 +0.03747132。
- FLIP median delta +0.01927092、Worst-patch FLIP median delta +0.01774288，两个 required regression gate 均通过。
- Indirect transport 在 190 case 改善，平均提升 +0.07618427，改动确实影响了一次反弹 GI 的被评分输出。
- 修改范围紧凑，仅涉及 3 个 tracked source file，共 37 additions / 28 deletions。
- 执行过程完成 5/5 tests、one-shot export、state/PFM contract 检查和两次输出 hash determinism 验证。
- 改动都有可解释的 sampling density、spatial interpolation、shadow bias 或 runtime ABI 依据，没有使用艺术性调色参数。

## 风险与不足

- Occlusion diagnostic 平均从 0.78038943 降到 0.76570952；84 case 退化，少数较大退化抵消了更多轻微改善 case。
- 仍有 14 case 的 Strict score 退化，Worst-patch FLIP 也有 44 case 退化，局部 artifact 并未全面消除。
- Probe rays 增加 4 倍、Probe 数增加约 4.3 倍，理论 preprocessing work 大幅增加；报告没有给出与 baseline 对齐的启动时间或 light-update cost benchmark。
- 最终回复声称已无剩余高风险改进点，但正式评测中的 Occlusion 平均退化和局部 tail regression 不支持如此强的收敛结论。
- 90 次 tool call 中有 14 个 warning、4 个 error，且没有成功的 subagent 独立复审。

## 分项结论

| 维度 | 评价 | 说明 |
|---|---|---|
| 物理建模 | 良好 | Sampling、Probe density 与 slope-scaled bias 都有明确物理或数值依据，Indirect transport 获得显著实测提升。 |
| 验证完整性 | 良好 | 覆盖 build、5/5 tests、one-shot output ABI、PFM/state 检查及跨运行 determinism。 |
| 指标均衡 | 中等 | Strict、FLIP、Indirect 与 Worst-patch 均提升，但 Occlusion diagnostic 平均退化且存在局部 tail cases。 |
| 最终效果 | 成功 | Regression gates 全部通过，Strict score 0.85612035，mean(B−A) +0.03747132，Normalized improvement 0.[timing omitted]。 |

## 执行概览

- Test：`TEST07`
- Main model：`deepseek-v4-pro`
- Claude Code：`2.1.233`
- Candidate / Baseline：`8878766` / `2039d94`
- Tool calls：90（4 errors，14 warnings）
- Subagents：0 success / 0 attempts
- Git diff：3 files，+37 / -28，diff check `PASS`

### Tool 类型

| Tool | Calls |
|---|---:|
| Read | 35 |
| Bash | 21 |
| PowerShell | 11 |
| Edit | 7 |
| Write | 5 |
| Grep | 5 |
| TodoWrite | 3 |
| Glob | 2 |
| TaskStop | 1 |

## 执行阶段

### #1–#30 · Contract 与 renderer 审计

- 动作：读取 AGENTS、public render contract、renderer、shader、Probe、tests 与 build tooling，确认启动方式和主要 rendering data flow。
- 分析：先建立 direct PBR、PRT、shadow、SSAA 与 capture 的完整关系，再选择 sampling density 和 bias 作为优先实验项。
- 证据：完成核心 source、CMake、test.py 与 contract 文件检查，并定位 repository-root shader loading 问题。

### #31–#60 · Baseline capture 与参数实验

- 动作：生成 baseline/iteration captures，尝试更密 Probe grid、更多 rays 与 shadow bias，并读取图像和数值输出。
- 分析：实验聚焦于能够直接解释 cube 遮挡、color bleeding 与 shadow detachment 的参数，而非整体曝光或颜色补偿。
- 证据：对比 capture 后保留 N=20 rays、11×7×11 probes 与 slope-scaled bias。

### #61–#76 · 实现与回归测试

- 动作：落地 Probe、grid、shadow 与 shader path 改动，运行 build 和 regression tests，并继续审查 SH/BRDF 约定。
- 分析：代码改动保持在 3 个 source file 内，runtime ABI 修复与画质改进相互独立。
- 证据：最终 tracked diff 为 37 additions / 28 deletions，tests 通过。

### #77–#90 · Output ABI、determinism 与收敛

- 动作：验证 PNG/PFM/state 文件、重复运行 hash、一键 export 与最终 diff，并清理 scratch artifacts。
- 分析：验证证明输出可重现且符合 evaluator 输入要求；正式 200-case 结果随后确认总体改善，但暴露 Occlusion 平均退化。
- 证据：one-shot export 成功、两次独立输出 hash 一致，candidate commit 为 8878766。

## Subagent

没有成功返回的 subagent。

## Git 文件变化

| File | Added | Deleted |
|---|---:|---:|
| `includes/GI/probe.h` | 1 | 1 |
| `src/getting_started/GIApplication/light_casters.fs` | 11 | 15 |
| `src/getting_started/GIApplication/main.cpp` | 25 | 12 |

Worktree status：`clean`

<details>
<summary><strong>Tool-call 流程摘要</strong></summary>

| # | 阶段 | Tool | 状态 | 摘要 |
|---:|---|---|---|---|
| 1 | Contract 与 renderer 审计 | Bash | ok | List project root and directory structure |
| 2 | Contract 与 renderer 审计 | Read | warning | <candidate-repository>\AGENTS.md |
| 3 | Contract 与 renderer 审计 | Read | ok | <candidate-repository>\realtime-render-contract.json |
| 4 | Contract 与 renderer 审计 | Bash | ok | List source, tests, tools, includes files |
| 5 | Contract 与 renderer 审计 | Read | ok | <candidate-repository>\README.md |
| 6 | Contract 与 renderer 审计 | Bash | ok | Count lines in key source files |
| 7 | Contract 与 renderer 审计 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 8 | Contract 与 renderer 审计 | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 9 | Contract 与 renderer 审计 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 10 | Contract 与 renderer 审计 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.vs |
| 11 | Contract 与 renderer 审计 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\ssaa_resolve.fs |
| 12 | Contract 与 renderer 审计 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.fs |
| 13 | Contract 与 renderer 审计 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.gs |
| 14 | Contract 与 renderer 审计 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.vs |
| 15 | Contract 与 renderer 审计 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\render_contract.h |
| 16 | Contract 与 renderer 审计 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\probe.fs |
| 17 | Contract 与 renderer 审计 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 18 | Contract 与 renderer 审计 | Read | warning | <candidate-repository>\tests\prt_numerics.cpp |
| 19 | Contract 与 renderer 审计 | Read | warning | <candidate-repository>\tests\render_contract.cpp |
| 20 | Contract 与 renderer 审计 | Read | warning | <candidate-repository>\tools\test.py |
| 21 | Contract 与 renderer 审计 | Read | ok | <candidate-repository>\tools\build.py |
| 22 | Contract 与 renderer 审计 | Bash | warning | Build and run baseline tests |
| 23 | Contract 与 renderer 审计 | TodoWrite | ok | 更新任务列表 |
| 24 | Contract 与 renderer 审计 | Write | ok | <candidate-repository>\capture.ps1 |
| 25 | Contract 与 renderer 审计 | Bash | warning | Run baseline one-shot capture |
| 26 | Contract 与 renderer 审计 | Read | ok | <candidate-repository>\includes\learnopengl\filesystem.h |
| 27 | Contract 与 renderer 审计 | Read | warning | <candidate-repository>\includes\learnopengl\shader_m.h |
| 28 | Contract 与 renderer 审计 | Bash | ok | Find root_directory.h and how shader root is configured |
| 29 | Contract 与 renderer 审计 | Bash | ok | Inspect root_directory.h and CMake configuration |
| 30 | Contract 与 renderer 审计 | Read | ok | <candidate-repository>\CMakeLists.txt |
| 31 | Baseline capture 与参数实验 | Bash | error | Check shader file locations |
| 32 | Baseline capture 与参数实验 | Bash | ok | Check gitignore and tracked shader files |
| 33 | Baseline capture 与参数实验 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 34 | Baseline capture 与参数实验 | Bash | ok | Rebuild and run one-shot capture |
| 35 | Baseline capture 与参数实验 | Bash | ok | Check capture output files |
| 36 | Baseline capture 与参数实验 | Read | ok | <candidate-repository>\capture-out\cases\case-baseline\realtime.png |
| 37 | Baseline capture 与参数实验 | Bash | error | Check available Python imaging libraries |
| 38 | Baseline capture 与参数实验 | Write | ok | <candidate-repository>\analyze.py |
| 39 | Baseline capture 与参数实验 | Bash | ok | Analyze baseline render output |
| 40 | Baseline capture 与参数实验 | Read | ok | <candidate-repository>\capture-out\cases\case-baseline\_preview.png |
| 41 | Baseline capture 与参数实验 | Read | ok | <candidate-repository>\capture-out\cases\case-baseline\_preview_indirect.png |
| 42 | Baseline capture 与参数实验 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 43 | Baseline capture 与参数实验 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 44 | Baseline capture 与参数实验 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 45 | Baseline capture 与参数实验 | Bash | warning | Rebuild and run tests |
| 46 | Baseline capture 与参数实验 | Edit | ok | <candidate-repository>\capture.ps1 |
| 47 | Baseline capture 与参数实验 | Bash | ok | Capture with improvements and analyze |
| 48 | Baseline capture 与参数实验 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 49 | Baseline capture 与参数实验 | Bash | warning | Rebuild and test with finer probe grid |
| 50 | Baseline capture 与参数实验 | Bash | ok | Capture with finer probe grid and analyze |
| 51 | Baseline capture 与参数实验 | TodoWrite | ok | 更新任务列表 |
| 52 | Baseline capture 与参数实验 | Bash | warning | Run full test suite (build + tests) |
| 53 | Baseline capture 与参数实验 | Bash | ok | Run two captures for determinism comparison |
| 54 | Baseline capture 与参数实验 | TaskStop | ok | {"task_id":"bmxi2g229"} |
| 55 | Baseline capture 与参数实验 | Write | ok | <candidate-repository>\run_capture.py |
| 56 | Baseline capture 与参数实验 | Bash | ok | Run determinism check: capture twice and compare |
| 57 | Baseline capture 与参数实验 | Write | ok | <candidate-repository>\diff_cases.py |
| 58 | Baseline capture 与参数实验 | Bash | ok | Compare baseline vs current output |
| 59 | Baseline capture 与参数实验 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 60 | Baseline capture 与参数实验 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 61 | 实现与回归测试 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 62 | 实现与回归测试 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 63 | 实现与回归测试 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 64 | 实现与回归测试 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 65 | 实现与回归测试 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 66 | 实现与回归测试 | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 67 | 实现与回归测试 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 68 | 实现与回归测试 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 69 | 实现与回归测试 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 70 | 实现与回归测试 | Glob | ok | src/getting_started/GIApplication/*.vs |
| 71 | 实现与回归测试 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.vs |
| 72 | 实现与回归测试 | Glob | ok | src/getting_started/GIApplication/*depth* |
| 73 | 实现与回归测试 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.gs |
| 74 | 实现与回归测试 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.fs |
| 75 | 实现与回归测试 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 76 | 实现与回归测试 | Read | warning | <candidate-repository>\tools\test.py |
| 77 | Output ABI、determinism 与收敛 | PowerShell | warning | Build and run the regression test suite |
| 78 | Output ABI、determinism 与收敛 | PowerShell | ok | Run one-shot export to a fresh output directory |
| 79 | Output ABI、determinism 与收敛 | PowerShell | error | Verify output files dimensions and state.json round-trip |
| 80 | Output ABI、determinism 与收敛 | Write | ok | <candidate-repository>\verify_output.py |
| 81 | Output ABI、determinism 与收敛 | PowerShell | ok | Run output verification script |
| 82 | Output ABI、determinism 与收敛 | PowerShell | ok | Re-run export and compare hashes for determinism |
| 83 | Output ABI、determinism 与收敛 | PowerShell | ok | Check git status for untracked helper files |
| 84 | Output ABI、determinism 与收敛 | PowerShell | ok | Remove scratch helper scripts and output directories |
| 85 | Output ABI、determinism 与收敛 | PowerShell | ok | Show full diff of tracked changes |
| 86 | Output ABI、determinism 与收敛 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 87 | Output ABI、determinism 与收敛 | PowerShell | error | Final one-shot export sanity check after comment fix |
| 88 | Output ABI、determinism 与收敛 | PowerShell | ok | Run one-shot export directly and verify PNG |
| 89 | Output ABI、determinism 与收敛 | PowerShell | ok | Clean up final check directory and confirm git status |
| 90 | Output ABI、determinism 与收敛 | TodoWrite | ok | 更新任务列表 |

</details>

<details>
<summary><strong>Agent 最终回复</strong></summary>

<pre>已完成收敛。本轮对完整 realtime PBR/PRT 渲染器的修改全部落在 public render contract 允许的范围内，最终状态如下。

## 改动内容（3 个 tracked 文件）

1. **shadow bias（`light_casters.fs`）**：把固定 `0.05` 的 world-unit bias 换成 slope-scaled bias `max(0.015*(1-N·L), 0.003)`。原值相对 2048² shadow map 的 texel 尺寸（约 0.004~0.012 unit）偏大 4~12 个 texel，会造成明显 peter-panning / light leak；新值在垂直入射用 ~1 texel 最小量、grazing 时按角度抬升，既避免 light leak 又保留硬阴影边界（point light 物理上应为硬阴影，故未引入 PCF）。

2. **indirect GI 采样质量（`probe.h` + `main.cpp`）**：ray 数量 100→400（`GenerateSampleRays(N=20)`），probe grid 从 7×4×7=196 加密到 11×7×11=847。前者降低 SH 系数里的 Monte-Carlo 噪声，后者提升靠近 cube/墙角的 color bleeding 与局部遮挡插值精度，减少 trilinear blur。

3. **shader 加载 ABI（`main.cpp`）**：6 个 `Shader` 构造从 CWD 相对路径改为 `FileSystem::getPath` 绝对 source 目录解析，使 `--renderer PBR` 在 repository root 启动时（contract 的启动方式）能正确读到 shader，此前会 `FILE_NOT_SUCCESFULLY_READ` 并 EXIT=1。

## 验证结果

- `python .\tools\test.py`：build 无重编译（已是最新），5/5 tests 通过（frame_timing / realtime_capture / render_contract / prt_numerics_pbr / prt_numerics_phong）。
- one-shot export：`realtime.png` 800×600 RGB8、`indirect-linear.pfm` 800×600 RGB32F little-endian（header `PF`、scale `-1.0`、range [0, 0.124]）、`state.json` 仅含 `id`+camera pose+light 且 round-trip 精确，`EXIT=0`。
- determinism：两次独立运行 PNG/PFM 字节哈希一致（`PRT_VISUAL_TEST=1` 固定 seed=1337）。

## 收敛评估（逐项排查后无剩余高风险改进点）

- BRDF/direct：Cook-Torrance + GGX + Smith + Schlick，`metallic=0/roughness=1` 下 specular 可忽略、diffuse 为 `albedo/π`，能量守恒（含 kD=(1-F)）；direct 与 CPU surfel 侧 `getFragColor` 公式一致，无 albedo 二次计数。
- SH 约定：CPU 投影与 GPU 重建的 `CalculateSphericalHarmonic` 公式逐项一致，probe 存储顺序与 3D texture 布局（x-fastest）一致，`probeGridMin/Max` 与 11×7×11 grid 匹配。
- 剩余的都是标准 probe-based GI 的固有近似，改动反而会引入回归：probe 离 floor/ceiling 0.5 unit 的 clamp、cube 内部 probe 的 transparent-cube 近似（`improve_probesInCubes`，仅影响 6/847 个 probe）、SH3 截断的负值 clamp——这些都与 offline reference 的差异在可接受范围，且 contract 固定 3-band SH、1 bounce，无空间再提升。

工作树干净，仅保留上述 3 个源码文件改动（未提交，按你偏好未加署名）。</pre>

</details>
