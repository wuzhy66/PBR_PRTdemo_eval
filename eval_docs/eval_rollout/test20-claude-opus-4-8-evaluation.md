# TEST20 · claude-opus-4-8 · Realtime rendering best-effort 全报告

> GitHub-readable evaluation report。本文件保留指标、过程分析和 tool-call 摘要，不嵌入体积过大的 tool input/output 或完整 Git diff。

## 最终结果

**Normalized improvement：`0.00000000` · Decision：`failure`**

| Baseline A | Candidate B / Strict | Mean B−A | Cases | Strict / Excluded / Errors |
|---:|---:|---:|---:|---:|
| 0.81864903 | 0.81444750 | -0.00420153 | 200 | 200 / 0 / 0 |

`Normalized improvement` 是最终 coding improvement 分数；`Strict score` 是单个 renderer 对 offline reference 的绝对分数。

### 指标变化

| 指标 | 权重 | Baseline | Candidate | 变化 | 改善 | 退化 | 不变 |
|---|---:|---:|---:|---:|---:|---:|---:|
| FLIP perceptual score | 70% | 0.81916697 | 0.78320035 | -0.03596661 | 56 | 144 | 0 |
| Worst-patch FLIP | diagnostic | 0.60162365 | 0.60283268 | +0.00120903 | 71 | 129 | 0 |
| Indirect transport | 30% | 0.82374117 | 0.89585999 | +0.07211881 | 195 | 5 | 0 |
| Occlusion leak | diagnostic | 0.78038943 | 0.72933184 | -0.05105760 | 65 | 126 | 9 |
| Strict score | aggregate | 0.81864903 | 0.81444750 | -0.00420153 | 69 | 131 | 0 |

### Regression gates

| Gate | Required | Median delta | 改善 | 退化 | 不变 | 结果 |
|---|---:|---:|---:|---:|---:|---|
| Median FLIP delta | yes | -0.06551542 | 56 | 144 | 0 | FAIL |
| Median worst-patch FLIP delta | yes | -0.07150545 | 71 | 129 | 0 | FAIL |

## 总体判断

本轮用五个连续 commit 提高 Probe rays/grid density，修复 shadow far-plane coverage，引入 slope-scaled bias 与 20-tap PCF，以 tricubic B-spline 重建 Probe volume，并为 indirect lighting 补充 Fresnel specular。正式 200-case 评测显示 Indirect transport 显著提升 +0.07211881，195 case 改善；但 combined-image FLIP 平均下降 -0.03596661，144 case 退化，Occlusion diagnostic 也下降 -0.05105760。Strict score 从 0.81864903 降到 0.81444750，两个 required median gates 均失败，Normalized improvement 为 0，判定改进失败。

## 改动与实测评价

### `includes/GI/probe.h / main.cpp`

- 改动：将每 Probe stratified samples 从 N=10（100 rays）提高到 N=24（576 rays），使用完整 RAND_MAX jitter；Probe grid 从 7×4×7（196 probes）加密到 13×7×13（1183 probes），并增加研究用 environment overrides。
- 目标：降低 SH coefficient sampling error 与空间插值 blur，使一次 indirect bounce 更接近高密度、高采样参考。
- 评测：与后续 tricubic/Fresnel 修改共同作用后，Official Indirect transport 从 0.82374117 提升到 0.89585999：195 case 改善、5 case 退化，是本轮唯一广泛且稳定的正式指标收益。

### `src/getting_started/GIApplication/main.cpp`

- 改动：将 point-shadow near/far plane 从 1/25 改为 0.2/35，使 cubemap 覆盖合法灯光位置到房间角落的完整距离。
- 目标：消除 far-plane 截断产生的球形全遮挡弧，并减少近光源遮挡漏检。
- 评测：Scene coverage 修复具有明确正确性依据；但它与 PCF/bias 同时影响 combined image，最终 FLIP 平均仍下降，无法从 aggregate 中单独确认净收益大小。

### `src/getting_started/GIApplication/light_casters.fs`

- 改动：将固定 shadow bias 改为 max(0.15×(1−N·L), 0.02)，并以随距离变化的 disk radius 执行 20-tap cubemap PCF。
- 目标：降低 shadow acne 和锯齿，使有限分辨率 shadow boundary 更平滑。
- 评测：FLIP 平均下降 -0.03596661，144 case 退化；Worst-patch median delta -0.07150545，129 case 退化；Occlusion 平均下降 -0.05105760。对零半径 point light 而言，20-tap PCF 引入的人工 penumbra 与较大 slope bias 很可能是 combined/shadow 回归的主要来源。

### `src/getting_started/GIApplication/light_casters.fs`

- 改动：以 Sigg–Hadwiger 8-fetch tricubic B-spline 替换 coefficient 3D textures 的 hardware trilinear sampling。
- 目标：提高 Probe irradiance field 的连续性，减少 cell boundary gradient discontinuity 和可见 banding。
- 评测：正式 Indirect 指标总体显著提升，支持更高采样/空间重建方向；但 B-spline 是 smoothing reconstruction 而非严格 interpolant，可能模糊真实的遮挡梯度，且每个 coefficient texture 的 fetch 数明显增加。

### `src/getting_started/GIApplication/light_casters.fs`

- 改动：使用 Karis split-sum EnvBRDF approximation，为 rough indirect response 增加基于 F0、NdotV 与 roughness 的 Fresnel specular term。
- 目标：补回 baseline indirect diffuse path 中被 kD 排除、但未由 indirect specular 接收的 Fresnel 反射能量。
- 评测：Indirect 平均提升方向与其能量修复目标一致；但当前 SH3 只提供 normal-direction irradiance，并非完整 reflection-direction prefiltered radiance，因此该项仍是 roughness=1 contract 下的近似。

## 做得好的地方

- Indirect transport 平均提升 +0.07211881，195/200 case 改善，median delta +0.04572951，说明 PRT/GI 方向取得广泛收益。
- Probe sampling、grid density、shadow range、B-spline reconstruction 与 Fresnel energy 都有明确的数值或物理动机，没有使用 exposure、gain 或颜色偏置。
- 通过五个小型 commit 保存实验演进，便于区分 sampling、far-plane、shadow、reconstruction 和 Fresnel 修改。
- 执行过程进行了 sample/grid convergence sweep、corner-light shadow test、banding proxy、Fresnel furnace analysis、one-shot export 和 5/5 tests。
- Candidate 累计 diff 保持紧凑：5 files、175 additions / 43 deletions，最终 worktree clean。
- 正式 replay/score 完成 200/200 strict cases，0 excluded、0 errors。

## 风险与不足

- 最终 Strict mean improvement 为 -0.00420153，131/200 case 退化，Normalized improvement 为 0。
- FLIP median delta -0.06551542、Worst-patch median delta -0.07150545，两个 required regression gate 均失败。
- 20-tap PCF 为零半径 point light 引入非物理软阴影；bias 在 grazing angle 可接近 0.15 world unit，也可能导致 peter-panning 和遮挡漏光。
- Occlusion diagnostic 平均下降 -0.05105760，126 case 退化；说明 direct shadow/visibility 的错误并非只出现在少数极端视角。
- Worst regression 很严重：case-0131 Strict delta -0.17323、FLIP -0.24716、Worst-patch -0.33885；case-0103～0105 也出现约 -0.15 至 -0.16 Strict regression。
- Probe rays 增加约 5.8 倍、Probe 数增加约 6 倍，precompute ray work 理论上约增加 35 倍；20-tap PCF 与 tricubic coefficient fetch 还显著增加 fragment cost。
- 本地验证主要使用自选视角、高密度自建 reference、relL1 和 banding proxy，没有在 commit 收敛前运行 official 200-case FLIP/worst-patch gates，因此未发现大范围 combined-image regression。
- 184 次 tool call 没有 subagent 独立复审；最终回复称已收敛，但 official regression gates 与大幅 worst-case 退化反驳了这一结论。

## 分项结论

| 维度 | 评价 | 说明 |
|---|---|---|
| 物理建模 | 中等 | Probe density、far-plane coverage 和 Fresnel energy 有明确依据；PCF soft shadow 与大 slope bias 不符合零半径 point-light reference。 |
| 验证完整性 | 中等 | 本地 convergence 与 contract tests 丰富，但缺少 official multi-case feedback，导致 shadow regression 未在提交前被发现。 |
| 指标均衡 | 失败 | Indirect 显著提升，但 FLIP、Occlusion 和多数 worst patches 退化，两个 median gates 均失败。 |
| 最终效果 | 失败 | Strict score 0.81444750，mean(B−A) -0.00420153，Normalized improvement 0。 |

## 执行概览

- Test：`TEST20`
- Main model：`claude-opus-4-8`
- Claude Code：`2.1.233`
- Candidate / Baseline：`d459630` / `1799977`
- Tool calls：184（3 errors，19 warnings）
- Subagents：0 success / 0 attempts
- Git diff：5 files，+175 / -43，diff check `PASS`

### Tool 类型

| Tool | Calls |
|---|---:|
| Bash | 98 |
| Read | 61 |
| Edit | 16 |
| Grep | 9 |

## 执行阶段

### #1–#44 · Renderer 审计与 baseline 建立

- 动作：读取 contract、renderer、Probe、shader 与 tests，完成 build、baseline one-shot export、图像/state 检查和初步性能定位。
- 分析：先建立完整 PBR/PRT pipeline 心智模型，并选择 Probe convergence、shadow coverage 和 interpolation continuity 作为实验方向。
- 证据：完成核心 source 阅读、baseline capture 与 output contract 检查。

### #45–#69 · Probe sample/grid convergence

- 动作：扫描多个 N 和 Probe grid density，量化相对高精度自建参考的 error/bias 与计算成本，选择 N=24、13×7×13 grid 并提交。
- 分析：该方向最终得到 official Indirect metric 的强支持，但也显著提高 preprocessing work。
- 证据：commit 9106f28；正式 Indirect 平均 +0.07211881。

### #70–#97 · Shadow coverage、bias 与 PCF

- 动作：构造角落灯光与阴影视角，修复 far-plane clipping，随后加入 slope-scaled bias 和 20-tap PCF，并分别提交。
- 分析：far-plane coverage 是正确修复，但 PCF 与较大 bias 依据少量自选视角收敛，没有覆盖 official test distribution。
- 证据：commits bc7cda1、f307013；正式 FLIP 144 case 退化、Occlusion 126 case 退化。

### #98–#148 · GI 误差分析与 tricubic reconstruction

- 动作：检查 Probe/cube overlap、color bleeding、低光强与 grid convergence，构建 banding proxy，实现 8-fetch tricubic B-spline 并提交。
- 分析：自建指标显示 relL1/bias 和二阶差分能量改善；official Indirect 也整体提升，但该阶段没有同时审查 combined FLIP/shadow interactions。
- 证据：commit 2e32b75；实现 sampleProbeTricubic 并完成 dense-reference comparisons。

### #149–#165 · Indirect Fresnel energy 修复

- 动作：进行 Fresnel energy 与 furnace 分析，实现 Karis EnvBRDF approximation 的 indirect specular term，验证能量变化并提交。
- 分析：该修改对 roughness=1 material 有合理动机，并与 Indirect 指标正向变化一致；仍受 SH3 directional information 限制。
- 证据：commit d459630；正式 Indirect 在 195 cases 改善。

### #166–#184 · 剩余限制探索与最终收敛

- 动作：分析 grid boundary、SH ringing 与 per-Probe seed，revert 无效 seed 实验，清理 temporary artifacts，重跑 build/tests 和最终 one-shot。
- 分析：工程状态收敛且 tests 通过，但没有 official 200-case scoring，因此错误地把本地代理指标下的收敛视为整体画质收敛。
- 证据：最终 HEAD d459630、worktree clean；正式评测 decision=failure。

## Subagent

没有成功返回的 subagent。

## Git 文件变化

| File | Added | Deleted |
|---|---:|---:|
| `.gitignore` | 3 | 0 |
| `CMakeLists.txt` | 7 | 0 |
| `includes/GI/probe.h` | 15 | 2 |
| `src/getting_started/GIApplication/light_casters.fs` | 121 | 30 |
| `src/getting_started/GIApplication/main.cpp` | 29 | 11 |

Worktree status：`clean`

<details>
<summary><strong>Tool-call 流程摘要</strong></summary>

| # | 阶段 | Tool | 状态 | 摘要 |
|---:|---|---|---|---|
| 1 | Renderer 审计与 baseline 建立 | Read | warning | <candidate-repository>\AGENTS.md |
| 2 | Renderer 审计与 baseline 建立 | Bash | ok | 列出主要源文件 |
| 3 | Renderer 审计与 baseline 建立 | Bash | ok | 列出项目自身源文件 |
| 4 | Renderer 审计与 baseline 建立 | Bash | ok | 列出目录结构和 shader 文件 |
| 5 | Renderer 审计与 baseline 建立 | Bash | ok | 统计各文件行数 |
| 6 | Renderer 审计与 baseline 建立 | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 7 | Renderer 审计与 baseline 建立 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 8 | Renderer 审计与 baseline 建立 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 9 | Renderer 审计与 baseline 建立 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\ssaa_resolve.fs |
| 10 | Renderer 审计与 baseline 建立 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\render_contract.h |
| 11 | Renderer 审计与 baseline 建立 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.vs |
| 12 | Renderer 审计与 baseline 建立 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\realtime_capture.h |
| 13 | Renderer 审计与 baseline 建立 | Read | warning | <candidate-repository>\tools\test.py |
| 14 | Renderer 审计与 baseline 建立 | Read | ok | <candidate-repository>\realtime-render-contract.json |
| 15 | Renderer 审计与 baseline 建立 | Read | ok | <candidate-repository>\tools\build.py |
| 16 | Renderer 审计与 baseline 建立 | Bash | ok | 查看项目根和工具,查找 reference renderer |
| 17 | Renderer 审计与 baseline 建立 | Read | ok | <candidate-repository>\README.md |
| 18 | Renderer 审计与 baseline 建立 | Read | ok | <candidate-repository>\tools\_tooling.py |
| 19 | Renderer 审计与 baseline 建立 | Bash | warning | 构建 PBR renderer 建立基线 |
| 20 | Renderer 审计与 baseline 建立 | Bash | warning | 查看构建错误开头 |
| 21 | Renderer 审计与 baseline 建立 | Read | ok | <candidate-repository>\CMakeLists.txt |
| 22 | Renderer 审计与 baseline 建立 | Edit | ok | <candidate-repository>\CMakeLists.txt |
| 23 | Renderer 审计与 baseline 建立 | Bash | ok | 重新构建验证 UTF-8 修复 |
| 24 | Renderer 审计与 baseline 建立 | Bash | warning | 运行回归测试 |
| 25 | Renderer 审计与 baseline 建立 | Bash | error | 运行 baseline one-shot 导出 |
| 26 | Renderer 审计与 baseline 建立 | Bash | ok | 检查 shader 位置和 filesystem 路径逻辑 |
| 27 | Renderer 审计与 baseline 建立 | Bash | ok | 查看 filesystem 路径解析 |
| 28 | Renderer 审计与 baseline 建立 | Bash | ok | 从 bin 目录运行 one-shot 导出 |
| 29 | Renderer 审计与 baseline 建立 | Read | ok | <candidate-repository>/tmp_out/cases/baseline/realtime.png |
| 30 | Renderer 审计与 baseline 建立 | Read | ok | <candidate-repository>/tmp_out/cases/baseline/state.json |
| 31 | Renderer 审计与 baseline 建立 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 32 | Renderer 审计与 baseline 建立 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 33 | Renderer 审计与 baseline 建立 | Read | ok | <candidate-repository>\realtime-render-contract.json |
| 34 | Renderer 审计与 baseline 建立 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\render_contract.h |
| 35 | Renderer 审计与 baseline 建立 | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 36 | Renderer 审计与 baseline 建立 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 37 | Renderer 审计与 baseline 建立 | Bash | ok | 检查 python/numpy 可用性 |
| 38 | Renderer 审计与 baseline 建立 | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 39 | Renderer 审计与 baseline 建立 | Bash | ok | 分析 indirect PFM 强度与颜色 |
| 40 | Renderer 审计与 baseline 建立 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 41 | Renderer 审计与 baseline 建立 | Read | warning | <candidate-repository>\tests\frame_timing.cpp |
| 42 | Renderer 审计与 baseline 建立 | Grep | ok | irradiances\|CalculateIrradiance\|ProjectRadianceFunctionSH\|ProjectIrradianceFunctionSH |
| 43 | Renderer 审计与 baseline 建立 | Read | warning | <candidate-repository>\tests\prt_numerics.cpp |
| 44 | Renderer 审计与 baseline 建立 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 45 | Probe sample/grid convergence | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 46 | Probe sample/grid convergence | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 47 | Probe sample/grid convergence | Bash | ok | 重新构建 PBR renderer |
| 48 | Probe sample/grid convergence | Bash | ok | 扫描 N=10/16/24/40/64 采样收敛性 |
| 49 | Probe sample/grid convergence | Bash | ok | 量化各 N 相对参考的收敛误差 |
| 50 | Probe sample/grid convergence | Bash | ok | 测量各 N 的总耗时 |
| 51 | Probe sample/grid convergence | Bash | ok | 测量各 N 总耗时(毫秒) |
| 52 | Probe sample/grid convergence | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 53 | Probe sample/grid convergence | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 54 | Probe sample/grid convergence | Bash | ok | 重建 |
| 55 | Probe sample/grid convergence | Bash | ok | 扫描 probe grid 密度 |
| 56 | Probe sample/grid convergence | Bash | ok | 量化 grid 密度收敛 |
| 57 | Probe sample/grid convergence | Bash | ok | 测量组合配置的耗时 |
| 58 | Probe sample/grid convergence | Bash | ok | 生成参考与候选配置 |
| 59 | Probe sample/grid convergence | Bash | ok | 量化候选相对高精度参考 |
| 60 | Probe sample/grid convergence | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 61 | Probe sample/grid convergence | Edit | error | <candidate-repository>\includes\GI\probe.h |
| 62 | Probe sample/grid convergence | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 63 | Probe sample/grid convergence | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 64 | Probe sample/grid convergence | Bash | warning | 运行完整回归测试 |
| 65 | Probe sample/grid convergence | Bash | ok | 默认配置生产采集并验证输出 |
| 66 | Probe sample/grid convergence | Read | ok | <candidate-repository>/tmp_out2/cases/prod/realtime.png |
| 67 | Probe sample/grid convergence | Bash | ok | 查看待提交变更 |
| 68 | Probe sample/grid convergence | Bash | ok | 仅暂存源码改动并忽略临时目录 |
| 69 | Probe sample/grid convergence | Bash | ok | 提交采样与网格密度改进 |
| 70 | Shadow coverage、bias 与 PCF | Bash | ok | 生成能观察阴影的视角 |
| 71 | Shadow coverage、bias 与 PCF | Read | ok | <candidate-repository>/tmp_look/cases/shadow/realtime.png |
| 72 | Shadow coverage、bias 与 PCF | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 73 | Shadow coverage、bias 与 PCF | Bash | ok | 极端角落灯光测试 far_plane 截断 |
| 74 | Shadow coverage、bias 与 PCF | Bash | ok | 查看失败原因 |
| 75 | Shadow coverage、bias 与 PCF | Bash | ok | combined 模式角落灯光 |
| 76 | Shadow coverage、bias 与 PCF | Read | ok | <candidate-repository>/tmp_far/cases/corner/realtime.png |
| 77 | Shadow coverage、bias 与 PCF | Bash | ok | 验证 far_plane 球形截断伪影 |
| 78 | Shadow coverage、bias 与 PCF | Read | ok | <candidate-repository>/tmp_arc/cases/arc/realtime.png |
| 79 | Shadow coverage、bias 与 PCF | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 80 | Shadow coverage、bias 与 PCF | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 81 | Shadow coverage、bias 与 PCF | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 82 | Shadow coverage、bias 与 PCF | Bash | ok | 重建 |
| 83 | Shadow coverage、bias 与 PCF | Bash | ok | 修复后重跑 arc 测试 |
| 84 | Shadow coverage、bias 与 PCF | Read | ok | <candidate-repository>/tmp_arc2/cases/arc/realtime.png |
| 85 | Shadow coverage、bias 与 PCF | Bash | warning | 回归测试 |
| 86 | Shadow coverage、bias 与 PCF | Bash | ok | 提交 far_plane 修复 |
| 87 | Shadow coverage、bias 与 PCF | Bash | ok | 列出所有 shader |
| 88 | Shadow coverage、bias 与 PCF | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 89 | Shadow coverage、bias 与 PCF | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 90 | Shadow coverage、bias 与 PCF | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 91 | Shadow coverage、bias 与 PCF | Bash | ok | 重建 |
| 92 | Shadow coverage、bias 与 PCF | Bash | ok | 重跑角落 acne 视角 |
| 93 | Shadow coverage、bias 与 PCF | Read | ok | <candidate-repository>/tmp_acne/cases/acne/realtime.png |
| 94 | Shadow coverage、bias 与 PCF | Bash | ok | 重跑阴影视角确认阴影完好 |
| 95 | Shadow coverage、bias 与 PCF | Read | ok | <candidate-repository>/tmp_sh2/cases/shadow/realtime.png |
| 96 | Shadow coverage、bias 与 PCF | Bash | warning | 完整回归测试 |
| 97 | Shadow coverage、bias 与 PCF | Bash | ok | 提交 shadow 质量改进 |
| 98 | GI 误差分析与 tricubic reconstruction | Bash | ok | 统计 probe 分布与 cube 交叠 |
| 99 | GI 误差分析与 tricubic reconstruction | Bash | ok | 标准视角 baseline vs 改进对比 |
| 100 | GI 误差分析与 tricubic reconstruction | Bash | ok | 测试 color bleeding 与低光强 |
| 101 | GI 误差分析与 tricubic reconstruction | Bash | ok | 红墙 color bleeding 视角 |
| 102 | GI 误差分析与 tricubic reconstruction | Read | ok | <candidate-repository>/tmp_matrix/cases/redwall/realtime.png |
| 103 | GI 误差分析与 tricubic reconstruction | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 104 | GI 误差分析与 tricubic reconstruction | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 105 | GI 误差分析与 tricubic reconstruction | Bash | ok | cd /g/PBR_PRTdemo_TEST20 && git log --oneline -8 && echo "---STATUS---" && git status --short |
| 106 | GI 误差分析与 tricubic reconstruction | Read | ok | <candidate-repository>\.gitignore |
| 107 | GI 误差分析与 tricubic reconstruction | Edit | ok | <candidate-repository>\.gitignore |
| 108 | GI 误差分析与 tricubic reconstruction | Read | warning | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 109 | GI 误差分析与 tricubic reconstruction | Grep | ok | <candidate-repository>\src\getting_started\GIApplication |
| 110 | GI 误差分析与 tricubic reconstruction | Read | ok | <candidate-repository>\src\getting_started\GIApplication\ssaa_resolve.fs |
| 111 | GI 误差分析与 tricubic reconstruction | Bash | ok | python -c "import json;d=json.load(open('realtime-render-contract.json'));print(json.dumps(d,indent=1)[:2500])" |
| 112 | GI 误差分析与 tricubic reconstruction | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 113 | GI 误差分析与 tricubic reconstruction | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 114 | GI 误差分析与 tricubic reconstruction | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 115 | GI 误差分析与 tricubic reconstruction | Bash | ok | python ./tools/build.py --renderer pbr 2>&1 \| tail -12 |
| 116 | GI 误差分析与 tricubic reconstruction | Grep | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 117 | GI 误差分析与 tricubic reconstruction | Bash | ok | cat > tmp_cmp.py << 'EOF' import struct, sys, os def read_pfm(path):     with open(path,'rb') as f:         hdr=f.readline().decode().strip()         assert hdr=='PF'         w,h=map(int,f.readline().split())         scale=float(f.readline( |
| 118 | GI 误差分析与 tricubic reconstruction | Bash | error | cd /g/PBR_PRTdemo_TEST20/bin/getting_started  run_case () {   local root="$1"; local cid="$2"; shift 2   env PRT_VISUAL_TEST=1 PRT_RENDERER=PBR PRT_TEST_MODE=combined PRT_DYNAMIC=0 \       PRT_DIRECT_SHADOW=1 PRT_PROBE_SHADOW=1 PRT_BANDS=3  |
| 119 | GI 误差分析与 tricubic reconstruction | Bash | ok | cd /g/PBR_PRTdemo_TEST20/bin/getting_started env PRT_VISUAL_TEST=1 PRT_RENDERER=PBR PRT_TEST_MODE=combined PRT_DYNAMIC=0 \     PRT_DIRECT_SHADOW=1 PRT_PROBE_SHADOW=1 PRT_BANDS=3 \     PRT_TEST_CAMERA_POSITION="0,4.5,8" PRT_TEST_CAMERA_YAW=- |
| 120 | GI 误差分析与 tricubic reconstruction | Bash | ok | cd /g/PBR_PRTdemo_TEST20/bin/getting_started env PRT_VISUAL_TEST=1 PRT_RENDERER=PBR PRT_TEST_MODE=combined PRT_DYNAMIC=0 \     PRT_DIRECT_SHADOW=1 PRT_PROBE_SHADOW=1 PRT_BANDS=3 \     PRT_TEST_CAMERA_POSITION="0,4.5,8" PRT_TEST_CAMERA_YAW=- |
| 121 | GI 误差分析与 tricubic reconstruction | Bash | ok | cd /g/PBR_PRTdemo_TEST20 && python tmp_cmp.py tmp_def/cases/defA/indirect-linear.pfm tmp_ref/cases/refA/indirect-linear.pfm |
| 122 | GI 误差分析与 tricubic reconstruction | Bash | ok | ls tools/ && echo "---" && grep -rl "path.trace\\|pathtrace\\|offline\\|reference\\|montecarlo\\| groundtruth\\|ground_truth" --include=*.py --include=*.cpp --include=*.h -i . 2>/dev/null \| grep -v tmp_ \| head |
| 123 | GI 误差分析与 tricubic reconstruction | Bash | ok | cd /g/PBR_PRTdemo_TEST20/bin/getting_started # 正对 -X 侧 cube (-7,1,0)，相机在其 +X 前方，看 color bleeding + 是否漏光 env PRT_VISUAL_TEST=1 PRT_RENDERER=PBR PRT_TEST_MODE=combined PRT_DYNAMIC=0 \     PRT_DIRECT_SHADOW=1 PRT_PROBE_SHADOW=1 PRT_BANDS=3 \   |
| 124 | GI 误差分析与 tricubic reconstruction | Read | ok | <candidate-repository>\tmp_cube\cases\cubeface\realtime.png |
| 125 | GI 误差分析与 tricubic reconstruction | Bash | ok | cd /g/PBR_PRTdemo_TEST20 && grep -rn "timeout\\|budget\\|2100\\|frame\\|deadline\\|elapsed" tools/test.py \| head -20 |
| 126 | GI 误差分析与 tricubic reconstruction | Read | warning | <candidate-repository>\tools\test.py |
| 127 | GI 误差分析与 tricubic reconstruction | Bash | warning | sed -n '1,60p' tests/frame_timing.cpp |
| 128 | GI 误差分析与 tricubic reconstruction | Bash | ok | cd /g/PBR_PRTdemo_TEST20/bin/getting_started for cfg in "12 6" "16 8" "20 10"; do   set -- $cfg   t0=$(date +%s.%N)   env PRT_VISUAL_TEST=1 PRT_RENDERER=PBR PRT_TEST_MODE=combined PRT_DYNAMIC=0 \       PRT_DIRECT_SHADOW=1 PRT_PROBE_SHADOW=1 |
| 129 | GI 误差分析与 tricubic reconstruction | Bash | ok | cd /g/PBR_PRTdemo_TEST20/bin/getting_started for cfg in "12 6" "16 8" "20 10"; do   set -- $cfg   t0=$(python -c "import time;print(time.time())")   env PRT_VISUAL_TEST=1 PRT_RENDERER=PBR PRT_TEST_MODE=combined PRT_DYNAMIC=0 \       PRT_DIR |
| 130 | GI 误差分析与 tricubic reconstruction | Bash | ok | cd /g/PBR_PRTdemo_TEST20/bin/getting_started rm -rf /g/PBR_PRTdemo_TEST20/tmp_time env PRT_VISUAL_TEST=1 PRT_RENDERER=PBR PRT_TEST_MODE=combined PRT_DYNAMIC=0 \     PRT_DIRECT_SHADOW=1 PRT_PROBE_SHADOW=1 PRT_BANDS=3 \     PRT_TEST_CAMERA_PO |
| 131 | GI 误差分析与 tricubic reconstruction | Bash | ok | cd /g/PBR_PRTdemo_TEST20 && grep -rn "timeout\\|Timeout\\|maxFrames\\|2100\\|30\b\\|deadline\\|seconds" tests/realtime_capture.cpp tests/render_contract.cpp 2>/dev/null \| head; echo "---test-set---"; ls test-set/ 2>/dev/null; echo "---capture loo |
| 132 | GI 误差分析与 tricubic reconstruction | Read | ok | <candidate-repository>\src\getting_started\GIApplication\main.cpp |
| 133 | GI 误差分析与 tricubic reconstruction | Bash | ok | grep -n "AUTOMATION_CAPTURE_TIMEOUT_FRAMES\\|step_length" src/getting_started/GIApplication/main.cpp |
| 134 | GI 误差分析与 tricubic reconstruction | Bash | ok | cd /g/PBR_PRTdemo_TEST20/bin/getting_started # dense reference for cubeface view (grid 16x8, N=32) — the near-truth env PRT_VISUAL_TEST=1 PRT_RENDERER=PBR PRT_TEST_MODE=combined PRT_DYNAMIC=0 \     PRT_DIRECT_SHADOW=1 PRT_PROBE_SHADOW=1 PRT |
| 135 | GI 误差分析与 tricubic reconstruction | Read | ok | <candidate-repository>\tmp_cref\cases\cubeRef\realtime.png |
| 136 | GI 误差分析与 tricubic reconstruction | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 137 | GI 误差分析与 tricubic reconstruction | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 138 | GI 误差分析与 tricubic reconstruction | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 139 | GI 误差分析与 tricubic reconstruction | Bash | ok | cd /g/PBR_PRTdemo_TEST20 && python ./tools/build.py --renderer pbr 2>&1 \| tail -4 |
| 140 | GI 误差分析与 tricubic reconstruction | Bash | ok | cd /g/PBR_PRTdemo_TEST20/bin/getting_started env PRT_VISUAL_TEST=1 PRT_RENDERER=PBR PRT_TEST_MODE=combined PRT_DYNAMIC=0 \     PRT_DIRECT_SHADOW=1 PRT_PROBE_SHADOW=1 PRT_BANDS=3 \     PRT_TEST_CAMERA_POSITION="-3,1.5,0" PRT_TEST_CAMERA_YAW= |
| 141 | GI 误差分析与 tricubic reconstruction | Read | ok | <candidate-repository>\tmp_cubic\cases\cubeface\realtime.png |
| 142 | GI 误差分析与 tricubic reconstruction | Bash | ok | cd /g/PBR_PRTdemo_TEST20/bin/getting_started # 新 tricubic binary：默认网格 + 稠密参考，baseline 视角 env PRT_VISUAL_TEST=1 PRT_RENDERER=PBR PRT_TEST_MODE=combined PRT_DYNAMIC=0 \     PRT_DIRECT_SHADOW=1 PRT_PROBE_SHADOW=1 PRT_BANDS=3 \     PRT_TEST_CAM |
| 143 | GI 误差分析与 tricubic reconstruction | Bash | ok | cd /g/PBR_PRTdemo_TEST20/bin/getting_started # 稠密参考也用 tricubic（同 binary），网格 16x8 N=48 env PRT_VISUAL_TEST=1 PRT_RENDERER=PBR PRT_TEST_MODE=combined PRT_DYNAMIC=0 \     PRT_DIRECT_SHADOW=1 PRT_PROBE_SHADOW=1 PRT_BANDS=3 \     PRT_TEST_CAMERA |
| 144 | GI 误差分析与 tricubic reconstruction | Bash | ok | cd /g/PBR_PRTdemo_TEST20 cat > tmp_band.py << 'EOF' import struct,sys def read_pfm(p):     with open(p,'rb') as f:         assert f.readline().decode().strip()=='PF'         w,h=map(int,f.readline().split()); s=float(f.readline())         d |
| 145 | GI 误差分析与 tricubic reconstruction | Bash | warning | python ./tools/test.py 2>&1 \| tail -20 |
| 146 | GI 误差分析与 tricubic reconstruction | Bash | ok | cd /g/PBR_PRTdemo_TEST20/bin/getting_started rm -rf /g/PBR_PRTdemo_TEST20/tmp_verify env PRT_VISUAL_TEST=1 PRT_RENDERER=PBR PRT_TEST_MODE=combined PRT_DYNAMIC=0 \     PRT_DIRECT_SHADOW=1 PRT_PROBE_SHADOW=1 PRT_BANDS=3 \     PRT_TEST_CAMERA_ |
| 147 | GI 误差分析与 tricubic reconstruction | Bash | ok | cd /g/PBR_PRTdemo_TEST20/bin/getting_started env PRT_VISUAL_TEST=1 PRT_RENDERER=PBR PRT_TEST_MODE=combined PRT_DYNAMIC=0 \     PRT_DIRECT_SHADOW=1 PRT_PROBE_SHADOW=1 PRT_BANDS=3 \     PRT_TEST_CAMERA_POSITION="0,4.5,8" PRT_TEST_CAMERA_YAW=- |
| 148 | GI 误差分析与 tricubic reconstruction | Bash | ok | cd /g/PBR_PRTdemo_TEST20 && git add .gitignore src/getting_started/GIApplication/light_casters.fs && git commit -q -m "probe irradiance 采用 tricubic B-spline 重建消除 trilinear banding  硬件 trilinear 只有 C0 连续性，probe grid 每个 cell 边界处梯度跳变，被人眼 放大为 M |
| 149 | Indirect Fresnel energy 修复 | Bash | ok | cd /g/PBR_PRTdemo_TEST20/bin/getting_started # 广角房间视图，灯偏一侧，看 wall banding、shadow、color bleeding 综合 env PRT_VISUAL_TEST=1 PRT_RENDERER=PBR PRT_TEST_MODE=combined PRT_DYNAMIC=0 \     PRT_DIRECT_SHADOW=1 PRT_PROBE_SHADOW=1 PRT_BANDS=3 \     PR |
| 150 | Indirect Fresnel energy 修复 | Read | ok | <candidate-repository>\tmp_wide\cases\wide\realtime.png |
| 151 | Indirect Fresnel energy 修复 | Bash | ok | cd /g/PBR_PRTdemo_TEST20 python3 - << 'EOF' # Fresnel-roughness kD 在不同 NdotV 下丢弃的能量比例 (F0=0.04, roughness=1) F0=0.04 def F_rough(ndotv, rough=1.0):     # fresnelSchlickRoughness: F0 + (max(1-rough,F0)-F0)*(1-c)^5 ; 1-rough=0 -> max(0,0.04)= |
| 152 | Indirect Fresnel energy 修复 | Bash | ok | cd /g/PBR_PRTdemo_TEST20 python3 - << 'EOF' # Furnace test: 均匀环境 radiance L -> irradiance E=piL. rough dielectric F0=0.04 F0=0.04 for rho in [1.0,0.5]:     diffuse_only = (1-F0)*rho      # 当前: kD*rho     correct      = F0 + (1-F0)*rho # 物理正 |
| 153 | Indirect Fresnel energy 修复 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 154 | Indirect Fresnel energy 修复 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 155 | Indirect Fresnel energy 修复 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 156 | Indirect Fresnel energy 修复 | Bash | ok | cd /g/PBR_PRTdemo_TEST20 python3 - << 'EOF' import math def EnvBRDFApprox(NdotV, rough):     c0=(-1.0,-0.0275,-0.572,0.022); c1=(1.0,0.0425,1.04,-0.04)     r=[rough*c0[i]+c1[i] for i in range(4)]     a004=min(r[0]*r[0], 2**(-9.28*NdotV))*r[ |
| 157 | Indirect Fresnel energy 修复 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 158 | Indirect Fresnel energy 修复 | Edit | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 159 | Indirect Fresnel energy 修复 | Bash | ok | python ./tools/build.py --renderer pbr 2>&1 \| tail -3 |
| 160 | Indirect Fresnel energy 修复 | Bash | ok | cd /g/PBR_PRTdemo_TEST20/bin/getting_started env PRT_VISUAL_TEST=1 PRT_RENDERER=PBR PRT_TEST_MODE=combined PRT_DYNAMIC=0 \     PRT_DIRECT_SHADOW=1 PRT_PROBE_SHADOW=1 PRT_BANDS=3 \     PRT_TEST_CAMERA_POSITION="0,5,9" PRT_TEST_CAMERA_YAW=-90 |
| 161 | Indirect Fresnel energy 修复 | Read | ok | <candidate-repository>\tmp_spec\cases\wide\realtime.png |
| 162 | Indirect Fresnel energy 修复 | Bash | warning | python ./tools/test.py 2>&1 \| tail -8 |
| 163 | Indirect Fresnel energy 修复 | Bash | ok | cd /g/PBR_PRTdemo_TEST20/bin/getting_started rm -rf /g/PBR_PRTdemo_TEST20/tmp_vfy2 env PRT_VISUAL_TEST=1 PRT_RENDERER=PBR PRT_TEST_MODE=combined PRT_DYNAMIC=0 \     PRT_DIRECT_SHADOW=1 PRT_PROBE_SHADOW=1 PRT_BANDS=3 \     PRT_TEST_CAMERA_PO |
| 164 | Indirect Fresnel energy 修复 | Read | ok | <candidate-repository>\src\getting_started\GIApplication\light_casters.fs |
| 165 | Indirect Fresnel energy 修复 | Bash | ok | cd /g/PBR_PRTdemo_TEST20 && git add src/getting_started/GIApplication/light_casters.fs && git commit -q -m "indirect lighting 补回丢失的 Fresnel specular 能量  direct PBR 同时输出 kD*diffuse 与单次散射 Cook-Torrance specular，但 indirect 之前只保留 kD=(1-F) 的漫反射、 |
| 166 | 剩余限制探索与最终收敛 | Bash | ok | cd /g/PBR_PRTdemo_TEST20 python3 - << 'EOF' # 墙内表面在 x=±9.9，probe grid 到 x=±9.5。CLAMP_TO_EDGE 意味着 [9.5,9.9] 的 # 墙面片段全部采样最外层 probe（x=9.5）的 irradiance。该 probe 距墙 0.4， # 其半球采样已包含墙面反射，用它近似墙面 0.4 内的 irradiance 误差多大？ # 房间半宽 9.9，0.4/9.9 ≈ 4% 的空间外推。 |
| 167 | 剩余限制探索与最终收敛 | Bash | ok | cd /g/PBR_PRTdemo_TEST20/bin/getting_started run () {   env PRT_VISUAL_TEST=1 PRT_RENDERER=PBR PRT_TEST_MODE=combined PRT_DYNAMIC=0 \       PRT_DIRECT_SHADOW=1 PRT_PROBE_SHADOW=1 PRT_BANDS=3 \       PRT_TEST_CAMERA_POSITION="$2" PRT_TEST_CA |
| 168 | 剩余限制探索与最终收敛 | Read | ok | <candidate-repository>\tmp_mtx\cases\bright\realtime.png |
| 169 | 剩余限制探索与最终收敛 | Read | ok | <candidate-repository>\tmp_mtx\cases\corner\realtime.png |
| 170 | 剩余限制探索与最终收敛 | Bash | ok | cd /g/PBR_PRTdemo_TEST20 python3 - << 'EOF' import struct def read_pfm(p):     f=open(p,'rb');assert f.readline().decode().strip()=='PF'     w,h=map(int,f.readline().split());s=float(f.readline())     v=struct.unpack('<'+str(w*h*3)+'f',f.re |
| 171 | 剩余限制探索与最终收敛 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 172 | 剩余限制探索与最终收敛 | Read | ok | <candidate-repository>\includes\GI\probe.h |
| 173 | 剩余限制探索与最终收敛 | Edit | ok | <candidate-repository>\includes\GI\probe.h |
| 174 | 剩余限制探索与最终收敛 | Bash | ok | grep -n "GenerateSampleRays\\|srand\\|1337\\|position\\|Probe\\|seed\\|Random\\|rays\[" tests/prt_numerics.cpp \| head -40 |
| 175 | 剩余限制探索与最终收敛 | Bash | warning | python ./tools/build.py --renderer pbr 2>&1 \| tail -3 && python ./tools/test.py --skip-build 2>&1 \| tail -6 |
| 176 | 剩余限制探索与最终收敛 | Bash | ok | cd /g/PBR_PRTdemo_TEST20/bin/getting_started env PRT_VISUAL_TEST=1 PRT_RENDERER=PBR PRT_TEST_MODE=combined PRT_DYNAMIC=0 \     PRT_DIRECT_SHADOW=1 PRT_PROBE_SHADOW=1 PRT_BANDS=3 \     PRT_TEST_CAMERA_POSITION="0,4.5,8" PRT_TEST_CAMERA_YAW=- |
| 177 | 剩余限制探索与最终收敛 | Read | ok | <candidate-repository>\tmp_seed\cases\bright\realtime.png |
| 178 | 剩余限制探索与最终收敛 | Bash | ok | git checkout includes/GI/probe.h && echo reverted |
| 179 | 剩余限制探索与最终收敛 | Bash | ok | rm -rf tmp_* tmp_cmp.py tmp_band.py 2>/dev/null; git status --short; echo "--- clean ---" |
| 180 | 剩余限制探索与最终收敛 | Bash | warning | python ./tools/build.py --renderer pbr 2>&1 \| tail -2 && python ./tools/test.py --skip-build 2>&1 \| tail -5 |
| 181 | 剩余限制探索与最终收敛 | Bash | ok | git status --short && git diff --stat && echo "HEAD:" && git log --oneline -4 |
| 182 | 剩余限制探索与最终收敛 | Bash | ok | cd /g/PBR_PRTdemo_TEST20/bin/getting_started env PRT_VISUAL_TEST=1 PRT_RENDERER=PBR PRT_TEST_MODE=combined PRT_DYNAMIC=0 \     PRT_DIRECT_SHADOW=1 PRT_PROBE_SHADOW=1 PRT_BANDS=3 \     PRT_TEST_CAMERA_POSITION="0,4.5,8" PRT_TEST_CAMERA_YAW=- |
| 183 | 剩余限制探索与最终收敛 | Read | ok | <candidate-repository>\tmp_final\cases\baseline\realtime.png |
| 184 | 剩余限制探索与最终收敛 | Bash | ok | rm -rf /g/PBR_PRTdemo_TEST20/tmp_final && cd /g/PBR_PRTdemo_TEST20 && git status --short && echo "clean" |

</details>

<details>
<summary><strong>Agent 最终回复</strong></summary>

<pre>The canonical baseline renders cleanly with both improvements active. Working tree is clean.

I&#x27;ve reached convergence on the safely-improvable physical-accuracy points this session. Summary of what I investigated and did:

## 本轮完成的改进（均已 commit、全部测试通过）

**1. `2e32b75` — Probe irradiance 改用 tricubic B-spline 重建**
- 问题:硬件 trilinear 只有 C0 连续性,probe grid 每个 cell 边界梯度跳变,被人眼放大为 Mach banding(在 cube 表面尤其明显)。
- 方案:Sigg–Hadwiger 8-tap tricubic B-spline,C2 连续、每轴权重构成 partition of unity(常量场精确复原、能量守恒),借助 GPU linear 采样把 4³ taps 折叠为 8 次 fetch,**precompute 零额外成本**。
- 实测:indirect relL1 1.88%→1.79%,meanBias −0.65%→−0.44%,cube 表面二阶差分能量(banding proxy)↓约 16%。

**2. `d459630` — Indirect lighting 补回丢失的 Fresnel specular 能量**
- 问题:direct PBR 同时输出 `kD·diffuse` 与单次散射 GGX specular,但 indirect 之前只留 `kD=(1−F)` 漫反射、**完全丢弃 Fresnel 反射的入射能量**(roughness=1 dielectric 恒定损失约 4%,灰 albedo 约 7.7%,掠射更高),非能量守恒且比 offline 偏暗。
- 方案:解析 split-sum EnvBRDF(Karis),与 direct 共用同一单次散射 BRDF 模型;roughness=1 时 GGX 镜叶覆盖半球,prefiltered radiance 即 E/π。**恢复物理反射项,非 gain/saturation**。
- 实测:indirect 平均能量 +4.3%,与丢失分量吻合,无 hotspot 伪影。

## 排查后判定为不可/不应改动的点
- **Indirect GI 采样精度**:relL1 已 &lt;2%、bias &lt;0.5%,采样/网格密度已饱和,继续加密是 O(n³) 且收益递减。
- **光斑辐条(bright/baseline 地面与背墙)**:根因是 contract 锁定的 **3-band SH** 无法表达点光源造成的尖锐 irradiance 梯度(角向 ringing)+ 网格对角走样。试过 per-probe 去相关 seed,反而增加噪声、辐条未消,已 revert。用 SH windowing 去除会过度模糊、损失物理准确性,不采纳。
- **Reinhard tone mapping / sRGB / SSAA / 材质 / 相机 / 灯光模型**:contract 强制固定,不得改动。
- **墙面 0.4 外推**:probe grid 到 ±9.5、墙在 ±9.9,CLAMP_TO_EDGE 外推 4%,几何固有且对光滑场可接受。

两处改进都是可解释的物理修正(能量守恒 + 重建连续性),使 realtime image 更接近 offline reference,且完整保持 render contract 与 ABI。所有 5 项 CTest 通过,一次 one-shot export 已核对三份输出、`800×600` 尺寸、pose round-trip 与 non-zero 失败行为。至此已收敛到在 contract 约束内无法再找到不牺牲物理准确性的可改进点。</pre>

</details>
