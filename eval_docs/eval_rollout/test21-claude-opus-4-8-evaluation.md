# TEST21 · claude-opus-4-8 · Realtime rendering best-effort 全报告

> GitHub-readable evaluation report。本文件保留指标、过程分析和 tool-call 摘要，不嵌入体积过大的 tool input/output 或完整 Git diff。

## 最终结果

**Normalized improvement：`0.56714054` · Decision：`success`**

| Baseline A | Candidate B / Strict | Mean B−A | Cases | Strict / Excluded / Errors |
|---:|---:|---:|---:|---:|
| 0.81864903 | 0.92150052 | +0.10285149 | 200 | 200 / 0 / 0 |

`Normalized improvement` 是最终 coding improvement 分数；`Strict score` 是单个 renderer 对 offline reference 的绝对分数。

### 指标变化

| 指标 | 权重 | Baseline | Candidate | 变化 | 改善 | 退化 | 不变 |
|---|---:|---:|---:|---:|---:|---:|---:|
| FLIP perceptual score | 70% | 0.81916697 | 0.93489607 | +0.11572910 | 200 | 0 | 0 |
| Worst-patch FLIP | diagnostic | 0.60162365 | 0.81318421 | +0.21156056 | 190 | 10 | 0 |
| Indirect transport | 30% | 0.82374117 | 0.89422592 | +0.07048475 | 189 | 11 | 0 |
| Occlusion leak | diagnostic | 0.78038943 | 0.79619655 | +0.01580712 | 101 | 90 | 9 |
| Strict score | aggregate | 0.81864903 | 0.92150052 | +0.10285149 | 199 | 1 | 0 |

### Regression gates

| Gate | Required | Median delta | 改善 | 退化 | 不变 | 结果 |
|---|---:|---:|---:|---:|---:|---|
| Median FLIP delta | yes | +0.04428135 | 200 | 0 | 0 | PASS |
| Median worst-patch FLIP delta | yes | +0.08820071 | 190 | 10 | 0 | PASS |

## 总体判断

本轮围绕 point-shadow correctness 与 PRT sampling convergence 做系统性改进：修复 shadow cubemap coverage，以 texel world scale 构造 normal-offset、slope-scaled bias 和 5-tap PCF，将每 Probe rays 从 100 提高到 1024，并把 Probe grid 从 196 加密到 405。正式 200-case 评测中 Strict score 从 0.81864903 提升到 0.92150052，FLIP 200/200 case 改善，Indirect 189/200 case 改善，两个 required median gates 均通过；最终 Normalized improvement 为 0.56714054，判定成功。

## 改动与实测评价

### `CMakeLists.txt`

- 改动：MSVC build 显式加入 /utf-8 source charset。
- 目标：消除中文 UTF-8 注释在非 UTF-8 active code page 下触发的编译失败，恢复可验证的 deterministic build。
- 评测：该项不直接改变渲染结果，但解决了 baseline build blocker；正式 replay 使用相同候选源码成功完成 200/200 case。

### `includes/GI/probe.h`

- 改动：将每 Probe 的 stratified uniform-sphere sample 从 10×10 提高到 32×32，即 100 rays 提高到 1024 rays。
- 目标：降低一次 indirect bounce 的 Monte-Carlo coefficient noise 与 sampling bias，使 SH irradiance 更接近收敛参考。
- 评测：与 Probe grid 加密共同作用后，Indirect transport 从 0.82374117 提升到 0.89422592，平均 +0.07048475，189 case 改善、11 case 退化；方向得到 official metric 强支持，但预计算 ray work 显著增加。

### `src/getting_started/GIApplication/main.cpp`

- 改动：将 Probe grid 从 7×4×7（196 probes）加密到 9×5×9（405 probes）；同时把 point-shadow near/far plane 从 1/25 改为 0.05/40，并向 shader 传递 shadowTexelWorldScale。
- 目标：提高 near-field irradiance 空间分辨率，并确保 cubemap depth 覆盖室内 point light 到任意墙面/立方体的最远距离。
- 评测：Indirect 指标显著改善；完整图像 FLIP 从 0.81916697 提升到 0.93489607，200/200 case 改善。far-plane coverage 是明确的 correctness 修复，但 aggregate 无法与 bias/PCF 的贡献完全拆分。

### `src/getting_started/GIApplication/light_casters.fs`

- 改动：用随 shadow texel world size 与 grazing angle 缩放的 normal offset/bias 替换固定 0.05 world bias，并加入十字形 5-tap PCF。
- 目标：同时减少 self-shadow acne、peter-panning 和 shadow-map stair-stepping；kernel 半径约一个 texel，限制人工软化。
- 评测：Combined-image FLIP 平均 +0.11572910 且 200/200 case 改善；worst-patch FLIP 平均 +0.21156056，190 case 改善、10 case 退化，median +0.08820071，说明 shadow correctness/aliasing 获得广泛收益。少量局部 worst-patch 与 occlusion regression 仍需注意。

### `tools/capture_case.py / crop.py / pfm_diff.py / pfm_view.py`

- 改动：新增本地 one-shot capture、crop、PFM 可视化和 PFM 差异诊断工具，并把 dev-captures 等临时产物加入 gitignore。
- 目标：支持光照、阴影、GI convergence 与局部区域的反复定量/视觉检查。
- 评测：这些工具不进入 runtime rendering path，但支持了 ray/grid sweep、shadow crop 与 output ABI 检查；正式评测仍由 trusted harness 独立执行。

## 做得好的地方

- 最终 Normalized improvement 为 0.56714054，Strict score 从 0.81864903 提升到 0.92150052，是明显且通过 gates 的整体收益。
- FLIP 平均 +0.11572910，200/200 case 改善，median +0.04428135；没有任何 combined-image FLIP regression。
- Worst-patch FLIP 平均 +0.21156056，190/200 case 改善，median +0.08820071，局部最差区域也获得广泛改善。
- Indirect transport 平均 +0.07048475，189/200 case 改善，median +0.05071512；Probe sampling/grid 方向得到正式数据支持。
- 199/200 case 的 Strict total 改善，只有 case-0071 轻微下降 -0.00290719。
- 修改有明确的几何、采样和 shadow-map texel 尺度依据，没有使用 exposure、gain、saturation 或颜色偏置。
- 执行过程包含 build blocker 修复、多个自选 pose、ray-count/grid-density convergence sweep、shadow crop、低/高亮度检查和 output ABI 验证。
- 正式 strict scoring 完成 200/200 case，0 excluded、0 errors。

## 风险与不足

- 每 Probe rays 增加 10.24 倍、Probe 数增加约 2.07 倍，静态预计算的 ray-probe work 理论上约增加 21 倍；本次 200-case replay 明显较慢。
- Worst-patch FLIP 仍有 10 case 退化，case-0070 与 case-0071 分别约 -0.11015、-0.09547，说明某些相近视角的 shadow edge 局部质量仍有回归。
- Occlusion leak diagnostic 仅平均 +0.01580712，101 case 改善、90 case 退化、9 case 不变；case-0066/0067 的 diagnostic 约下降 -0.19576。该指标不计入总分，但暴露局部 visibility 风险。
- case-0071 是唯一 Strict regression：FLIP 虽 +0.00330，但 Indirect -0.01665、Worst-patch -0.09547、Occlusion -0.09233，最终 total -0.00291。
- 5-tap PCF 仍会混合相邻 visibility samples；虽然半径限制在约一个 texel，零面积 point light 的理想几何阴影仍是 hard shadow。
- ray/grid/shadow 修改在同一 renderer commit 中落地，official aggregate 无法精确归因每个单项贡献；后续若追求成本收益比，应做 controlled ablation。
- 134 次 tool call 未使用 subagent 独立复审；本轮好在 official gates 强正向，但 process 结论仍主要来自同一 agent 的自证。

## 分项结论

| 维度 | 评价 | 说明 |
|---|---|---|
| 物理建模 | 优秀 | shadow coverage、texel-scaled bias、采样收敛与 Probe 空间分辨率都有可解释依据，并遵守一次 indirect bounce 限制。 |
| 验证完整性 | 良好 | 本地 sweep 与正式 200-case strict scoring 均完成；不足是缺少分项 ablation 与独立复审。 |
| 指标均衡 | 优秀 | FLIP 200/200 改善、Indirect 189/200 改善、两个 median gates 均通过；仅少量 worst-patch/occlusion 局部回归。 |
| 最终效果 | 成功 | Strict 0.92150052，mean(B−A) +0.10285149，Normalized improvement 0.56714054。 |

## 执行概览

- Test：`TEST21`
- Main model：`claude-opus-4-8`
- Claude Code：`2.1.233`
- Candidate / Baseline：`ab4ef0c` / `1799977`
- Tool calls：134（3 errors，10 warnings）
- Subagents：0 success / 0 attempts
- Git diff：9 files，+308 / -25，diff check `PASS`

### Tool 类型

| Tool | Calls |
|---|---:|
| Bash | 59 |
| Read | 54 |
| Edit | 15 |
| Write | 6 |

## 执行阶段

### #1–#28 · Renderer 审计与 build 恢复

- 动作：读取 contract、shader、Probe、capture 与 tests，定位 MSVC source encoding blocker，加入 /utf-8 后完成 build/test。
- 分析：先恢复可编译、可采集的基线，并建立 direct、indirect、shadow 与 SSAA pipeline 心智模型。
- 证据：候选可 clean build；正式评测也成功构建并完成 200-case replay。

### #29–#51 · Baseline capture 与 shadow coverage 诊断

- 动作：编写 one-shot capture/PFM viewer/crop 工具，采集默认与角落灯光视角，定位 far-plane clipping 和 contact shadow 问题。
- 分析：通过房间对角距离与局部 crop，把远墙伪暗和固定 bias 问题转化为可验证的 shadow-map coverage/texel-scale 修复。
- 证据：确认原 far_plane=25 小于室内最远距离约 34.6，并获得 corner-light/shadow crop 对照。

### #52–#73 · Shadow model 修复与初步验证

- 动作：实现 near/far coverage、normal-offset 和 slope-scaled bias，重建并在多个 cube/角落视角检查 shadow contact 与完整图。
- 分析：以 shadow texel 的 world-space footprint 统一 bias 尺度，避免固定 world bias 对距离和 grazing angle 的不一致。
- 证据：正式 FLIP 后续达到 200/200 case 改善；本地多个 pose 未出现 build/capture failure。

### #74–#96 · Probe rays 与 grid convergence

- 动作：新增 PFM diff，扫描多个 ray count 与 Probe grid density，比较误差、偏差、时延和 under-cube near-field 细节，选择 1024 rays 与 405 probes。
- 分析：以收敛实验替代主观调色，分别提高 angular Monte-Carlo sample count 与 spatial irradiance resolution。
- 证据：正式 Indirect 平均 +0.07048475，189/200 case 改善。

### #97–#126 · Stress views、PCF 与完整链路复核

- 动作：检查 ceiling/front wall、高低亮度、shadow edge 和 direct/indirect balance；加入约一 texel 半径的 5-tap PCF，并复查 contact shadow。
- 分析：把 PCF 限定为 shadow-map discretization antialiasing，而非模拟 area light；同时复核 PBR/PRT energy 与 output path。
- 证据：Worst-patch FLIP 平均 +0.21156056，190/200 case 改善，required median gate 通过。

### #127–#134 · 最终 clean validation 与收敛

- 动作：更新内部记录，review diff，执行 clean rebuild、5/5 tests、output ABI、failure path 和最终多视角 capture。
- 分析：工程状态和 capture contract 完整收敛，但 agent 没有接触 trusted official evaluator；最终效果由本次独立评测确认。
- 证据：正式 200-case：Strict +0.10285149，两个 regression gates 均通过，decision=success。

## Subagent

没有成功返回的 subagent。

## Git 文件变化

| File | Added | Deleted |
|---|---:|---:|
| `.gitignore` | 3 | 0 |
| `CMakeLists.txt` | 7 | 0 |
| `includes/GI/probe.h` | 5 | 1 |
| `src/getting_started/GIApplication/light_casters.fs` | 39 | 17 |
| `src/getting_started/GIApplication/main.cpp` | 19 | 7 |
| `tools/capture_case.py` | 59 | 0 |
| `tools/crop.py` | 89 | 0 |
| `tools/pfm_diff.py` | 29 | 0 |
| `tools/pfm_view.py` | 58 | 0 |

Worktree status：`clean`

<details>
<summary><strong>Tool-call 流程摘要</strong></summary>

| # | 阶段 | Tool | 状态 | 摘要 |
|---:|---|---|---|---|
| 1 | Renderer 审计与 build 恢复 | Read | warning | <candidate-repository>\AGENTS.md |
| 2 | Renderer 审计与 build 恢复 | Read | ok | <candidate-repository>\realtime-render-contract.json |
| 3 | Renderer 审计与 build 恢复 | Bash | ok | List repo files and recent commits |
| 4 | Renderer 审计与 build 恢复 | Bash | ok | List source files |
| 5 | Renderer 审计与 build 恢复 | Bash | ok | Count lines in key files |
| 6 | Renderer 审计与 build 恢复 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 7 | Renderer 审计与 build 恢复 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 8 | Renderer 审计与 build 恢复 | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 9 | Renderer 审计与 build 恢复 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\ssaa_resolve.fs |
| 10 | Renderer 审计与 build 恢复 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\render_contract.h |
| 11 | Renderer 审计与 build 恢复 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.vs |
| 12 | Renderer 审计与 build 恢复 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\ssaa_resolve.vs |
| 13 | Renderer 审计与 build 恢复 | Bash | ok | List tools/tests dirs |
| 14 | Renderer 审计与 build 恢复 | Read | warning | <candidate-repository>\tools\test.py |
| 15 | Renderer 审计与 build 恢复 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 16 | Renderer 审计与 build 恢复 | Read | ok | <candidate-repository>\tools\_tooling.py |
| 17 | Renderer 审计与 build 恢复 | Read | ok | <candidate-repository>\tools\build.py |
| 18 | Renderer 审计与 build 恢复 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.fs |
| 19 | Renderer 审计与 build 恢复 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\point_shadows_depth.gs |
| 20 | Renderer 审计与 build 恢复 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\probe.fs |
| 21 | Renderer 审计与 build 恢复 | Bash | warning | Build PBR renderer baseline |
| 22 | Renderer 审计与 build 恢复 | Bash | warning | Show first build errors |
| 23 | Renderer 审计与 build 恢复 | Read | ok | <candidate-repository>\CMakeLists.txt |
| 24 | Renderer 审计与 build 恢复 | Bash | ok | Check file encoding and BOM |
| 25 | Renderer 审计与 build 恢复 | Edit | ok | <candidate-repository>\CMakeLists.txt |
| 26 | Renderer 审计与 build 恢复 | Bash | ok | Rebuild with UTF-8 flag |
| 27 | Renderer 审计与 build 恢复 | Bash | warning | Run test suite |
| 28 | Renderer 审计与 build 恢复 | Bash | ok | Check for existing test set |
| 29 | Baseline capture 与 shadow coverage 诊断 | Write | ok | <candidate-repository>\tools\capture_case.py |
| 30 | Baseline capture 与 shadow coverage 诊断 | Bash | warning | Capture baseline frame |
| 31 | Baseline capture 与 shadow coverage 诊断 | Bash | ok | Check root dir and shader loading |
| 32 | Baseline capture 与 shadow coverage 诊断 | Edit | ok | <candidate-repository>\tools\capture_case.py |
| 33 | Baseline capture 与 shadow coverage 诊断 | Bash | ok | Capture baseline frame from exe dir |
| 34 | Baseline capture 与 shadow coverage 诊断 | Read | ok | <candidate-repository>\dev-captures\cases\dev-default\realtime.png |
| 35 | Baseline capture 与 shadow coverage 诊断 | Write | ok | <candidate-repository>\tools\pfm_view.py |
| 36 | Baseline capture 与 shadow coverage 诊断 | Bash | ok | Convert PFM to viewable PNG |
| 37 | Baseline capture 与 shadow coverage 诊断 | Read | ok | <candidate-repository>\dev-captures\cases\dev-default\indirect-linear_x4.png |
| 38 | Baseline capture 与 shadow coverage 诊断 | Bash | ok | Capture off-center light case |
| 39 | Baseline capture 与 shadow coverage 诊断 | Read | ok | <candidate-repository>\dev-captures\cases\dev-corner-light\realtime.png |
| 40 | Baseline capture 与 shadow coverage 诊断 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 41 | Baseline capture 与 shadow coverage 诊断 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 42 | Baseline capture 与 shadow coverage 诊断 | Bash | ok | Rebuild and recapture corner light |
| 43 | Baseline capture 与 shadow coverage 诊断 | Read | ok | <candidate-repository>\dev-captures\cases\dev-corner-light2\realtime.png |
| 44 | Baseline capture 与 shadow coverage 诊断 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 45 | Baseline capture 与 shadow coverage 诊断 | Edit | ok | <candidate-repository>\tools\capture_case.py |
| 46 | Baseline capture 与 shadow coverage 诊断 | Read | warning | <candidate-repository>\tests\prt_numerics.cpp |
| 47 | Baseline capture 与 shadow coverage 诊断 | Write | ok | <candidate-repository>\tools\crop.py |
| 48 | Baseline capture 与 shadow coverage 诊断 | Bash | ok | Crop cube shadow contact region |
| 49 | Baseline capture 与 shadow coverage 诊断 | Read | ok | <candidate-repository>\dev-captures\cases\dev-corner-light2\realtime_crop.png |
| 50 | Baseline capture 与 shadow coverage 诊断 | Bash | ok | Capture default and view indirect at high exposure |
| 51 | Baseline capture 与 shadow coverage 诊断 | Read | ok | <candidate-repository>\dev-captures\cases\dev-gi\indirect-linear_x6.png |
| 52 | Shadow model 修复与初步验证 | Write | ok | <user-home>\.claude\projects\g--PBR-PRTdemo-TEST21\memory\prt-realtime-project.md |
| 53 | Shadow model 修复与初步验证 | Read | ok | <user-home>\.claude\CLAUDE.md |
| 54 | Shadow model 修复与初步验证 | Bash | ok | Check project memory index |
| 55 | Shadow model 修复与初步验证 | Write | ok | <user-home>\.claude\projects\g--PBR-PRTdemo-TEST21\memory\MEMORY.md |
| 56 | Shadow model 修复与初步验证 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 57 | Shadow model 修复与初步验证 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 58 | Shadow model 修复与初步验证 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 59 | Shadow model 修复与初步验证 | Bash | ok | Find far_plane uniform sets |
| 60 | Shadow model 修复与初步验证 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 61 | Shadow model 修复与初步验证 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 62 | Shadow model 修复与初步验证 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 63 | Shadow model 修复与初步验证 | Bash | ok | Rebuild and test new shadow |
| 64 | Shadow model 修复与初步验证 | Read | ok | <candidate-repository>\dev-captures\cases\dev-shadow2\realtime_crop.png |
| 65 | Shadow model 修复与初步验证 | Read | ok | <candidate-repository>\dev-captures\cases\dev-shadow2\realtime.png |
| 66 | Shadow model 修复与初步验证 | Bash | warning | Run tests |
| 67 | Shadow model 修复与初步验证 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 68 | Shadow model 修复与初步验证 | Bash | ok | Capture corner and near-cube views |
| 69 | Shadow model 修复与初步验证 | Read | ok | <candidate-repository>\dev-captures\cases\dev-corner-view\realtime.png |
| 70 | Shadow model 修复与初步验证 | Read | ok | <candidate-repository>\dev-captures\cases\dev-cube-near\realtime.png |
| 71 | Shadow model 修复与初步验证 | Bash | ok | View corner indirect |
| 72 | Shadow model 修复与初步验证 | Read | ok | <candidate-repository>\dev-captures\cases\dev-corner-view\indirect-linear_x4.png |
| 73 | Shadow model 修复与初步验证 | Bash | ok | Measure end-to-end capture time |
| 74 | Probe rays 与 grid convergence | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 75 | Probe rays 与 grid convergence | Write | ok | <candidate-repository>\tools\pfm_diff.py |
| 76 | Probe rays 与 grid convergence | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 77 | Probe rays 与 grid convergence | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 78 | Probe rays 与 grid convergence | Bash | ok | Capture at different ray counts |
| 79 | Probe rays 与 grid convergence | Bash | ok | Diff ray count convergence |
| 80 | Probe rays 与 grid convergence | Bash | ok | Test higher ray convergence |
| 81 | Probe rays 与 grid convergence | Bash | ok | Measure timing vs ray count |
| 82 | Probe rays 与 grid convergence | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 83 | Probe rays 与 grid convergence | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 84 | Probe rays 与 grid convergence | Bash | ok | Verify new default matches converged |
| 85 | Probe rays 与 grid convergence | Bash | ok | Run test suite |
| 86 | Probe rays 与 grid convergence | Bash | ok | Crop under-cube region |
| 87 | Probe rays 与 grid convergence | Read | ok | <candidate-repository>\dev-captures\cases\dev-corner-view\realtime_crop.png |
| 88 | Probe rays 与 grid convergence | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 89 | Probe rays 与 grid convergence | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 90 | Probe rays 与 grid convergence | Bash | ok | Capture grid density variants |
| 91 | Probe rays 与 grid convergence | Bash | ok | Diff grid density |
| 92 | Probe rays 与 grid convergence | Bash | ok | Grid timing and probe counts |
| 93 | Probe rays 与 grid convergence | Read | ok | <candidate-repository>\dev-captures\cases\dev-grid-6\indirect-linear_x4.png |
| 94 | Probe rays 与 grid convergence | Read | ok | <candidate-repository>\dev-captures\cases\dev-grid-10\indirect-linear_x4.png |
| 95 | Probe rays 与 grid convergence | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 96 | Probe rays 与 grid convergence | Bash | ok | Rebuild and test |
| 97 | Stress views、PCF 与完整链路复核 | Bash | ok | Capture final default views |
| 98 | Stress views、PCF 与完整链路复核 | Read | ok | <candidate-repository>\dev-captures\cases\dev-final-default\realtime.png |
| 99 | Stress views、PCF 与完整链路复核 | Bash | ok | Capture ceiling and front(red) wall views |
| 100 | Stress views、PCF 与完整链路复核 | Read | ok | <candidate-repository>\dev-captures\cases\dev-frontwall\realtime.png |
| 101 | Stress views、PCF 与完整链路复核 | Read | ok | <candidate-repository>\dev-captures\cases\dev-ceiling\realtime.png |
| 102 | Stress views、PCF 与完整链路复核 | Bash | ok | Review changed files |
| 103 | Stress views、PCF 与完整链路复核 | Bash | ok | Bright corner light and dim ceiling light |
| 104 | Stress views、PCF 与完整链路复核 | Read | ok | <candidate-repository>\dev-captures\cases\dev-bright\realtime.png |
| 105 | Stress views、PCF 与完整链路复核 | Read | ok | <candidate-repository>\dev-captures\cases\dev-low\realtime.png |
| 106 | Stress views、PCF 与完整链路复核 | Bash | ok | Crop left cube in bright case |
| 107 | Stress views、PCF 与完整链路复核 | Read | ok | <candidate-repository>\dev-captures\cases\dev-bright\realtime_crop.png |
| 108 | Stress views、PCF 与完整链路复核 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 109 | Stress views、PCF 与完整链路复核 | Bash | ok | Zoom shadow edge for aliasing |
| 110 | Stress views、PCF 与完整链路复核 | Read | ok | <candidate-repository>\dev-captures\cases\dev-shadow2\realtime_crop.png |
| 111 | Stress views、PCF 与完整链路复核 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 112 | Stress views、PCF 与完整链路复核 | Bash | ok | Rebuild with PCF and check edge |
| 113 | Stress views、PCF 与完整链路复核 | Read | ok | <candidate-repository>\dev-captures\cases\dev-shadow-pcf\realtime_crop.png |
| 114 | Stress views、PCF 与完整链路复核 | Bash | ok | Check contact and run tests |
| 115 | Stress views、PCF 与完整链路复核 | Read | ok | <candidate-repository>\dev-captures\cases\dev-shadow-pcf\realtime_crop.png |
| 116 | Stress views、PCF 与完整链路复核 | Bash | ok | Check git status and gitignore |
| 117 | Stress views、PCF 与完整链路复核 | Bash | ok | Measure full capture time with defaults |
| 118 | Stress views、PCF 与完整链路复核 | Bash | error | Debug capture failure |
| 119 | Stress views、PCF 与完整链路复核 | Bash | ok | Verify capture succeeds |
| 120 | Stress views、PCF 与完整链路复核 | Bash | ok | Capture direct/indirect/combined for balance |
| 121 | Stress views、PCF 与完整链路复核 | Read | error | <candidate-repository>\dev-captures\bal\cases\i\realtime.png |
| 122 | Stress views、PCF 与完整链路复核 | Bash | error | Locate balance captures |
| 123 | Stress views、PCF 与完整链路复核 | Bash | ok | Find bal outputs |
| 124 | Stress views、PCF 与完整链路复核 | Bash | ok | Capture indirect-only mode |
| 125 | Stress views、PCF 与完整链路复核 | Bash | ok | View default indirect PFM |
| 126 | Stress views、PCF 与完整链路复核 | Read | ok | <candidate-repository>\dev-captures\cases\dev-verify\indirect-linear_x4.png |
| 127 | 最终 clean validation 与收敛 | Edit | ok | <user-home>\.claude\projects\g--PBR-PRTdemo-TEST21\memory\prt-realtime-project.md |
| 128 | 最终 clean validation 与收敛 | Bash | ok | Review probe.h diff |
| 129 | 最终 clean validation 与收敛 | Bash | warning | Clean rebuild and full test |
| 130 | 最终 clean validation 与收敛 | Bash | ok | Verify output ABI |
| 131 | 最终 clean validation 与收敛 | Bash | ok | Verify non-zero failure path |
| 132 | 最终 clean validation 与收敛 | Bash | ok | Final validation captures |
| 133 | 最终 clean validation 与收敛 | Read | ok | <candidate-repository>\dev-captures\cases\final-b\realtime.png |
| 134 | 最终 clean validation 与收敛 | Bash | ok | Final diff summary |

</details>

<details>
<summary><strong>Agent 最终回复</strong></summary>

<pre>All changes are complete and validated. Let me provide a summary of the work.

## 总结

我对 PRT realtime renderer 做了系统性的物理准确性改进，在不改动 public render contract 的前提下让完整 realtime image 明显更接近 offline reference。所有改动都基于可解释的物理模型与数值收敛,没有用 saturation/gain/exposure/颜色偏置掩盖问题。

### 完成的改进(按发现顺序)

1. **修复 build 阻塞** ([CMakeLists.txt](CMakeLists.txt)):源码含 UTF-8 中文注释,MSVC 默认按系统 GBK codepage 解析导致**整个项目无法编译**。加 `/utf-8` 使任意 locale 下都能确定性编译。这是修改一切的前提。

2. **shadow far/near plane** ([main.cpp:558](src/getting_started/GIApplication/main.cpp#L558)):cubemap `far_plane=25` 小于房间对角 ≈34.6,把远墙 depth clamp 成 1.0 → 远墙被误判为阴影(可见伪暗带)。改为 40/0.05。depth 线性写入,放大 far 不损精度。

3. **normal-offset + slope-scaled shadow bias** ([light_casters.fs:63](src/getting_started/GIApplication/light_casters.fs#L63)):固定 `0.05` world bias 造成**peter-panning**(阴影与 cube 底部脱离)。改用随距离/grazing 缩放的 texel-world-size 偏移,同时消除 acne 与 peter-panning。

4. **5-tap PCF** ([light_casters.fs](src/getting_started/GIApplication/light_casters.fs)):单点采样使 cast-shadow 边缘出现 shadow-map 量化的 stair-stepping。加半径 ≈1 texel 的 world-space PCF 抗锯齿,不引入非物理软阴影。

5. **probe 采样 100→1024 rays** ([probe.h:296](includes/GI/probe.h#L296)):用 pfm_diff 量化出 100 rays 有 **17% MC 噪声 + 7% 系统性偏暗**;1024 rays 降到 ~4% 并消除偏暗,更接近 reference。

6. **probe grid 196→405** ([main.cpp:391](src/getting_started/GIApplication/main.cpp#L391)):更密网格恢复 cube 底部的 near-field contact darkening(path tracer 会呈现的效果)。

### 验证

- `python tools/test.py` 全绿(clean rebuild,5/5 passed)。
- Output ABI 完整:3 个文件、800×600、PFM little-endian、pose 精确 round-trip、缺输入返回 non-zero。
- end-to-end capture ≈3s,远低于 2100-frame timeout。
- 新增 4 个本地诊断工具(tools/,dev-captures/ 已 gitignore),非 contract 产物。

我已充分排查并收敛:GI transport 数学(uniform-sphere MC + cosine convolution + SH 投影)经验证正确;direct/indirect BRDF 一致(都用 kD Fresnel);tone mapping、SSAA resolve、inverse-square 均符合 contract。剩余的 direct/indirect specular 差异对该 matte 材质(roughness=1)影响极小且已能量一致,继续调整会进入无法可靠对齐 reference 的推测区。

改动未 commit(遵循仅在你要求时提交)。需要我提交或继续探索某个方向吗?</pre>

</details>
