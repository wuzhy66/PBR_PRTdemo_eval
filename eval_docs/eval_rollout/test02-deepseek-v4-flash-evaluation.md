# TEST02 · deepseek-v4-flash · Realtime rendering best-effort 全报告

> GitHub-readable evaluation report。本文件保留指标、过程分析和 tool-call 摘要，不嵌入体积过大的 tool input/output 或完整 Git diff。

## 最终结果

**Normalized improvement：`0.37673252` · Decision：`success`**

| Baseline A | Candidate B / Strict | Mean B−A | Cases | Strict / Excluded / Errors |
|---:|---:|---:|---:|---:|
| 0.81864903 | 0.88696984 | +0.06832081 | 200 | 200 / 0 / 0 |

`Normalized improvement` 是最终 coding improvement 分数；`Strict score` 是单个 renderer 对 offline reference 的绝对分数。

### 指标变化

| 指标 | 权重 | Baseline | Candidate | 变化 | 改善 | 退化 | 不变 |
|---|---:|---:|---:|---:|---:|---:|---:|
| FLIP perceptual score | 70% | 0.81916697 | 0.91356613 | +0.09439917 | 188 | 12 | 0 |
| Worst-patch FLIP | diagnostic | 0.60162365 | 0.79481200 | +0.19318835 | 164 | 36 | 0 |
| Indirect transport | 30% | 0.82374117 | 0.84133128 | +0.01759011 | 157 | 43 | 0 |
| Occlusion leak | diagnostic | 0.78038943 | 0.73872031 | -0.04166912 | 93 | 98 | 9 |
| Strict score | aggregate | 0.81864903 | 0.88696984 | +0.06832081 | 187 | 13 | 0 |

### Regression gates

| Gate | Required | Median delta | 改善 | 退化 | 不变 | 结果 |
|---|---:|---:|---:|---:|---:|---|
| Median FLIP delta | yes | +0.02039275 | 188 | 12 | 0 | PASS |
| Median worst-patch FLIP delta | yes | +0.04379948 | 164 | 36 | 0 | PASS |

## 总体判断

执行进行了大量 baseline capture、局部 A/B 与回退实验，最终保留 Probe sample、point-shadow range/bias 和 cube interior Probe reconstruction 三类修改。正式 200-case 评测中 Strict score 在 187/200 case 改善，Normalized improvement 为 0.37673252，排名第三；occlusion leak 出现显著净退化，但该项仅作诊断。

## 改动与实测评价

### `includes/GI/probe.h`

- 改动：默认 Probe ray grid 从 10×10 提高到 16×16；solid 内 Probe 改为复制最近外部 Probe transport。
- 目标：降低 sampling noise，并减少 cube 外表面被内部 Probe 压暗。
- 评测：Indirect transport 平均提升 0.01759011；最近外部 Probe 复制对部分场景有效，但缺少 visibility/geometry 约束。

### `light_casters.fs`

- 改动：固定 shadow bias 改为与 slope/far plane 相关的 bias。
- 目标：平衡 acne 与 peter-panning。
- 评测：FLIP 平均提升 0.09439917，但 occlusion leak 平均退化 0.04166912，反向 light vector 风险在 stress cases 中仍然明显。

### `main.cpp`

- 改动：point-shadow near/far 调整为 0.1/36。
- 目标：覆盖室内最远 geometry，并保留近光源遮挡。
- 评测：scene-bound range 思路正确，完整 Strict score 平均提升 0.06832081。

## 做得好的地方

- 先建立 public contract、build、CTest 和 one-shot baseline，再进入修改，验证顺序完整。
- 尝试 2×2 PCF 后检测到过度压暗并主动回退。
- 围绕 far plane、cube face 与 interior Probe 做了多轮 before/after capture。
- 正式评测中 FLIP 为 188 case 改善、12 case 退化，targeted 128 条 Normalized improvement 达到 0.36131435。

## 风险与不足

- Shadow bias 使用反向 light vector，slope adaptation 的物理依据不正确。
- solid 内 Probe 复制最近外部 Probe 可能跨遮挡边界传播不属于该位置的 radiance。
- Occlusion leak 平均退化 0.04166912：93 case 改善、98 case 退化、9 case 不变。
- 会话末尾写入 Claude project memory，可能造成跨模型实验污染。

## 分项结论

| 维度 | 评价 | 说明 |
|---|---|---|
| 自主持续性 | 强 | 进行了多轮实验、回退、baseline capture 和局部诊断。 |
| 验证覆盖 | 强 | Public tests、one-shot、A/B capture 和输出 ABI 均被检查。 |
| 指标均衡 | 有明显风险 | FLIP 提升强，但 occlusion leak 是五组中净退化最大的一组。 |
| 最终效果 | 成功 | Strict score 0.88696984，mean(B−A) +0.06832081，Normalized improvement 0.37673252。 |

## 执行概览

- Test：`TEST02`
- Main model：`deepseek-v4-flash`
- Claude Code：`2.1.233`
- Candidate / Baseline：`worktree-e3b0c44298fc` / `5592dc5`
- Tool calls：132（10 errors，11 warnings）
- Subagents：0 success / 0 attempts
- Git diff：0 files，+0 / -0，diff check `PASS`

### Tool 类型

| Tool | Calls |
|---|---:|
| Bash | 86 |
| Read | 26 |
| Edit | 12 |
| TodoWrite | 6 |
| Write | 2 |

## 执行阶段

### #1–#39 · Contract 与 baseline

- 动作：读取 pipeline/contract/tests，构建 baseline，生成并分析 one-shot、PFM 与局部预览。
- 分析：先建立可重复反馈环，避免直接凭视觉印象修改。
- 证据：Baseline build、CTest、capture 和输出检查均被执行。

### #40–#79 · Shadow 与 sampling

- 动作：修改 shadow range/bias 与 Probe sample；尝试 PCF、对比局部统计并回退过暗版本。
- 分析：实验覆盖广，但部分统计只衡量亮度变化，不能证明更接近 reference。
- 证据：PCF 被撤销；保留 N=16 与新的 range/bias。

### #80–#121 · Cube Probe 深入诊断

- 动作：通过 stash、diagnostic override、cube-face capture 比较旧 see-through 与 exterior-field Probe。
- 分析：确实深入定位 cube 邻域问题；但最终 nearest external field 仍是未被 exact visibility 证明的启发式。
- 证据：最终修改 improve_probesInCubes，并恢复 clean rendering path。

### #122–#132 · 收敛与验证

- 动作：清理 scratch，运行完整 tests、最终 one-shot、diff review，并写入 memory。
- 分析：代码与 ABI 验证完整；memory 写入会影响独立实验的隔离性。
- 证据：Session 报告 5/5 CTest 与三份输出通过。

## Subagent

没有成功返回的 subagent。

## Git 文件变化

| File | Added | Deleted |
|---|---:|---:|

Worktree status：`clean`

<details>
<summary><strong>Tool-call 流程摘要</strong></summary>

| # | 阶段 | Tool | 状态 | 摘要 |
|---:|---|---|---|---|
| 1 | Contract 与 baseline | Bash | ok | List project structure and JSON files |
| 2 | Contract 与 baseline | Read | ok | <candidate-repository>\realtime-render-contract.json |
| 3 | Contract 与 baseline | Bash | ok | List source files |
| 4 | Contract 与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 5 | Contract 与 baseline | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 6 | Contract 与 baseline | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 7 | Contract 与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\ssaa_resolve.fs |
| 8 | Contract 与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\render_contract.h |
| 9 | Contract 与 baseline | Read | warning | <candidate-repository>\tools\test.py |
| 10 | Contract 与 baseline | TodoWrite | ok | 更新任务列表 |
| 11 | Contract 与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 12 | Contract 与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.fs |
| 13 | Contract 与 baseline | Bash | ok | Check python and tools |
| 14 | Contract 与 baseline | Bash | ok | Build project baseline |
| 15 | Contract 与 baseline | Bash | warning | Run ctest suite |
| 16 | Contract 与 baseline | Read | warning | <candidate-repository>\tests\prt_numerics.cpp |
| 17 | Contract 与 baseline | Bash | warning | Run baseline one-shot capture |
| 18 | Contract 与 baseline | Bash | ok | Find filesystem and shader loader |
| 19 | Contract 与 baseline | Read | ok | <candidate-repository>\includes\learnopengl\filesystem.h |
| 20 | Contract 与 baseline | Bash | ok | Check root dir config and shader constructor |
| 21 | Contract 与 baseline | Bash | ok | Locate shader loading path setup |
| 22 | Contract 与 baseline | Bash | ok | Check root directory generated header |
| 23 | Contract 与 baseline | Read | warning | <candidate-repository>\includes\learnopengl\shader_m.h |
| 24 | Contract 与 baseline | Bash | ok | Check CMakeLists for shader handling |
| 25 | Contract 与 baseline | Bash | ok | List shader copies in bin dir |
| 26 | Contract 与 baseline | Bash | ok | Run baseline capture from exe dir |
| 27 | Contract 与 baseline | Bash | ok | Run baseline capture with absolute output root |
| 28 | Contract 与 baseline | Bash | ok | Verify baseline capture files |
| 29 | Contract 与 baseline | Bash | ok | Create PFM analysis helper |
| 30 | Contract 与 baseline | Bash | error | Analyze baseline indirect PFM |
| 31 | Contract 与 baseline | Bash | ok | Analyze baseline indirect PFM values |
| 32 | Contract 与 baseline | Read | ok | <candidate-repository>\baseline_out\cases\baseline-test\realtime.png |
| 33 | Contract 与 baseline | Bash | ok | Check available Python imaging libs |
| 34 | Contract 与 baseline | Bash | ok | Prepare baseline preview images |
| 35 | Contract 与 baseline | Bash | ok | Save region-of-interest crops |
| 36 | Contract 与 baseline | Read | ok | <candidate-repository>\baseline_out\baseline_preview.png |
| 37 | Contract 与 baseline | TodoWrite | ok | 更新任务列表 |
| 38 | Contract 与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.gs |
| 39 | Contract 与 baseline | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.vs |
| 40 | Shadow 与 sampling | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 41 | Shadow 与 sampling | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 42 | Shadow 与 sampling | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 43 | Shadow 与 sampling | Bash | ok | Rebuild with probe ray + shadow changes |
| 44 | Shadow 与 sampling | Bash | ok | Capture improved render |
| 45 | Shadow 与 sampling | Bash | ok | Compare baseline vs improved indirect stats |
| 46 | Shadow 与 sampling | Bash | ok | Capture corner light case |
| 47 | Shadow 与 sampling | Bash | ok | Debug corner capture exit code |
| 48 | Shadow 与 sampling | Bash | ok | Analyze corner indirect |
| 49 | Shadow 与 sampling | Bash | ok | Check git status of changes |
| 50 | Shadow 与 sampling | TodoWrite | ok | 更新任务列表 |
| 51 | Shadow 与 sampling | Bash | error | Measure indirect spatial noise baseline vs improved |
| 52 | Shadow 与 sampling | Bash | error | Measure indirect spatial noise corrected |
| 53 | Shadow 与 sampling | Bash | error | Measure indirect noise with corrected shapes |
| 54 | Shadow 与 sampling | Bash | ok | Measure indirect noise with final fix |
| 55 | Shadow 与 sampling | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 56 | Shadow 与 sampling | Bash | ok | Rebuild with PCF shadow |
| 57 | Shadow 与 sampling | Bash | ok | Capture with PCF shadow |
| 58 | Shadow 与 sampling | Bash | ok | Prepare hard vs soft previews |
| 59 | Shadow 与 sampling | Bash | ok | Test PNG decode helper |
| 60 | Shadow 与 sampling | Bash | ok | Diff hard vs soft shadow renders |
| 61 | Shadow 与 sampling | Bash | ok | Verify indirect identical between variants |
| 62 | Shadow 与 sampling | Bash | ok | Compare shadow row profile hard vs soft |
| 63 | Shadow 与 sampling | Bash | ok | Check for over-shadowing darkening |
| 64 | Shadow 与 sampling | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 65 | Shadow 与 sampling | Bash | ok | Rebuild and capture with clean tuned bias |
| 66 | Shadow 与 sampling | Bash | ok | Verify no over-darkening vs baseline |
| 67 | Shadow 与 sampling | Bash | error | Capture corner-light clean build |
| 68 | Shadow 与 sampling | Bash | ok | Analyze corner clean indirect |
| 69 | Shadow 与 sampling | Bash | ok | Build original far_plane=25 and capture stress case |
| 70 | Shadow 与 sampling | Bash | ok | Restore far=48, rebuild, capture same stress case |
| 71 | Shadow 与 sampling | Bash | ok | Compare far_plane 25 vs 48 shadow stress captures |
| 72 | Shadow 与 sampling | Bash | warning | Run full validation suite |
| 73 | Shadow 与 sampling | Bash | ok | Overall brightness baseline vs new |
| 74 | Shadow 与 sampling | Bash | error | Inspect indirect-only color fidelity toward green wall |
| 75 | Shadow 与 sampling | Bash | ok | Locate shadow resolution constant |
| 76 | Shadow 与 sampling | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 77 | Shadow 与 sampling | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 78 | Shadow 与 sampling | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 79 | Shadow 与 sampling | Bash | ok | Verify indirect color bleed spatial correctness |
| 80 | Cube Probe 深入诊断 | Bash | ok | Check git status and scratch dirs |
| 81 | Cube Probe 深入诊断 | Bash | ok | Remove scratch dirs and temp files |
| 82 | Cube Probe 深入诊断 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 83 | Cube Probe 深入诊断 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 84 | Cube Probe 深入诊断 | Bash | ok | Confirm final near/far plane values |
| 85 | Cube Probe 深入诊断 | Bash | ok | Check stash list and diff |
| 86 | Cube Probe 深入诊断 | Bash | warning | Stash changes to build original baseline |
| 87 | Cube Probe 深入诊断 | Bash | ok | Build and capture original committed baseline |
| 88 | Cube Probe 深入诊断 | Bash | ok | Restore my changes from stash |
| 89 | Cube Probe 深入诊断 | Bash | ok | Rebuild and capture final improved state |
| 90 | Cube Probe 深入诊断 | Bash | ok | Rigorous original vs improved A/B |
| 91 | Cube Probe 深入诊断 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.vs |
| 92 | Cube Probe 深入诊断 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 93 | Cube Probe 深入诊断 | Bash | ok | Review complete diff |
| 94 | Cube Probe 深入诊断 | Bash | warning | Rebuild with far_plane=36 and run full suite |
| 95 | Cube Probe 深入诊断 | TodoWrite | ok | 更新任务列表 |
| 96 | Cube Probe 深入诊断 | Bash | ok | Capture and analyze cube face indirect |
| 97 | Cube Probe 深入诊断 | Bash | error | Downsample indirect to view block structure |
| 98 | Cube Probe 深入诊断 | Bash | ok | Downsample indirect luminance to view structure |
| 99 | Cube Probe 深入诊断 | Bash | ok | Capture cube-face view and analyze indirect |
| 100 | Cube Probe 深入诊断 | Bash | ok | Row profiles to locate cube silhouette in indirect |
| 101 | Cube Probe 深入诊断 | Bash | ok | ASCII map of indirect luminance to find cube silhouette |
| 102 | Cube Probe 深入诊断 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.vs |
| 103 | Cube Probe 深入诊断 | Bash | ok | Find cube mesh construction and model matrices |
| 104 | Cube Probe 深入诊断 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 105 | Cube Probe 深入诊断 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 106 | Cube Probe 深入诊断 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 107 | Cube Probe 深入诊断 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 108 | Cube Probe 深入诊断 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 109 | Cube Probe 深入诊断 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 110 | Cube Probe 深入诊断 | Bash | ok | Build and run probe diagnostic |
| 111 | Cube Probe 深入诊断 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 112 | Cube Probe 深入诊断 | Bash | ok | Rebuild and re-run probe diagnostic after fix |
| 113 | Cube Probe 深入诊断 | Bash | warning | Save fix render and revert probe.h to committed version |
| 114 | Cube Probe 深入诊断 | Bash | ok | Restore N=16 onto committed see-through version |
| 115 | Cube Probe 深入诊断 | Bash | ok | Build and capture the true 'before' (see-through) render |
| 116 | Cube Probe 深入诊断 | Bash | error | Compare before (see-through) vs after (exterior-field) renders |
| 117 | Cube Probe 深入诊断 | Bash | ok | Inspect AFTER and BEFORE directory layout |
| 118 | Cube Probe 深入诊断 | Bash | error | Re-run comparison with corrected AFTER path |
| 119 | Cube Probe 深入诊断 | Bash | ok | Robust before-after comparison |
| 120 | Cube Probe 深入诊断 | Bash | ok | Restore fixed probe.h (exterior-field interior probes) |
| 121 | Cube Probe 深入诊断 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 122 | 收敛与验证 | TodoWrite | ok | 更新任务列表 |
| 123 | 收敛与验证 | Bash | ok | Clean up scratch directories and check git status |
| 124 | 收敛与验证 | Bash | warning | Run full test suite (build + contract validation + ctest) |
| 125 | 收敛与验证 | Bash | ok | Run final one-shot export covering the full contract ABI |
| 126 | 收敛与验证 | Bash | ok | Verify output dimensions, state round-trip, and content sanity |
| 127 | 收敛与验证 | Bash | ok | Review complete diff of all three changed files |
| 128 | 收敛与验证 | Bash | ok | Review light_casters.fs diff and confirm far_plane consistency |
| 129 | 收敛与验证 | TodoWrite | ok | 更新任务列表 |
| 130 | 收敛与验证 | Write | ok | <claude-project>\memory\prt-renderer-knowns.md |
| 131 | 收敛与验证 | Read | error | <claude-project>\memory\MEMORY.md |
| 132 | 收敛与验证 | Write | ok | <claude-project>\memory\MEMORY.md |

</details>

<details>
<summary><strong>Agent 最终回复</strong></summary>

<pre>All validation complete. Here is the converged final state.

## 收敛结果总结

已反复扫描 pipeline，确认收敛到没有更多可信的、物理有据的改进点。最终改动为**三个源文件**（未触碰 `realtime-render-contract.json` 与任何 ABI）：

### 本轮新增的改进
**修正实心立方体内部探针导致的间接光照缺陷**（[probe.h](includes/GI/probe.h)）

- **物理缺陷**：稀疏 3D probe grid + trilinear 插值会把&quot;落在实心立方体内部&quot;的探针值带到立方体外表面 fragment。旧 `improve_probesInCubes` 用&quot;移除该立方体再做 see-through 重算&quot;，仍让立方体的 `-X` 表面（朝房间那面）间接光从几何正确的 ~1.2 被压到 ~0.67——外表面物理上正视房间，不该被内部遮挡拉低。
- **修正**：内部探针改为**继承最近外部探针的 irradiance 场**。这是&quot;体积插值跨几何边界&quot;这一网格固有近似的物理正确解法（外表面几乎不被自身遮挡，其值就是外部场）。
- **A/B 验证**：只点亮立方体朝外的 `-X` 表面（2079 像素），**100% 只变亮、0 压暗**，mean +0.022 linear；combined 图 mean-luminance 0.444→0.444，总能量守恒。

### 之前已完成的改进（本会话收敛链）
- **shadow `far_plane` 25→36、`near_plane` 1.0→0.1**（[main.cpp](src/getting_started/GIApplication/main.cpp)）：房间对角线 ~29.7 m，旧 25 m 会让角落光源远端表面漏光（真实物理能量 bug）；depth pass 投影与 shader uniform 三处一致更新。
- **直接阴影 normal-offset bias**（[light_casters.fs](src/getting_started/GIApplication/light_casters.fs#L62)）：掠射角自适应 + far_plane 缩放，替代固定 0.05；曾试过的 2x2 PCF 因自遮挡（38% 像素变暗、0% 变亮）而回退。
- **探针 ray 采样 N=10→16**（100→256 ray/探针），降低间接方差。

### 验证
- `python ./tools/test.py`：构建 + contract 校验 + 5/5 ctest（frame_timing / realtime_capture / render_contract / prt_numerics_pbr / prt_numerics_phong）全部 **PASS**。
- One-shot export：`realtime.png`(600×800 RGB8)、`indirect-linear.pfm`(600×800 RGB32F, 无负值)、`state.json`(camera/light pose **round-trip 精确匹配**输入) 三份齐全，exit 0。
- scratch 目录（orig_ref/new_ref/BEFORE/AFTER/cube_probe/final_export）已全部清理。

### 明确判定为&quot;不再改动&quot;的收敛点（避免回归）
- **shadow 分辨率保持 2048**：4096 在 llvmpipe/软件渲染下内存与自动化帧预算风险过高。
- **不加间接 specular**：材质固定 roughness=1, F≈0.04，specular 间接能量 &lt;4%，diffuse irradiance 已主导，收益不足以支撑 radiance 级 SH 复杂度。
- **不加 2x2 PCF**、**SH 能量归一化保持不动**（已用 [tests/prt_numerics.cpp](tests/prt_numerics.cpp) 数学验证正确）。

改动已验证到物理层面正确、能量守恒、契约完整可运行，达到收敛。未做 commit（按你的全局规则，如需提交请告知）。</pre>

</details>
