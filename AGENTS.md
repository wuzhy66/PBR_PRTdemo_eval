## 仓库用途

- 本仓库主要用于通过根目录的 `test_by_code.py` 对 coding model 修改后的 PRT realtime renderer 进行 trusted evaluation，不是普通的 renderer demo 仓库。
- Evaluation 固定只从 `/workspace` 和 `/test_files` 读取输入，并只向 `/eval` 写入 runtime artifact 与最终 `code_result.json`：`/workspace` 是 candidate repository snapshot，`/test_files` 保存 hidden test states、render contract、score config、offline references 和 precomputed baseline。
- `/test_files` 必须同时满足递归文件数不超过 500、总大小不超过 500 MB，且当前交付不使用压缩包。Compact bundle 可在完整 200-state test set 中提供任意非空 case subset；实际评测集合由 `references/cases/` 下名称以 `case` 开头且以 numeric state ID 结尾的目录决定。每个 case 保留 800×600 `offline.png`，Indirect/Occlusion diagnostics 使用 200×150 linear area-average 数据。
- `baseline-score-report.json` 必须与正式 Linux software-rendering backend、test set 和 diagnostic protocol 一致；禁止用 Windows/GPU 或不同 Mesa/LLVM 版本生成的 baseline 与 Linux llvmpipe candidate 混合比较。
- 正式目标环境为 Ubuntu 24.04 x86-64、G++ 13.3、CMake 3.28.3、Ninja 1.11.1、Mesa 25.2.8、llvmpipe LLVM 20.1.2、Xvfb 1600×1200×24。修改 evaluator、reference layout 或 scoring protocol 后，必须验证 public tests、所选 case subset 的 capture/scoring 与 baseline compatibility。

## 渲染修改原则

- Realtime rendering 修复必须优先采用可解释的物理模型、材质参数、单位与能量守恒关系，禁止用 saturation、gain、exposure、颜色偏置等艺术性 magic number 掩盖算法或数据问题。
- 若确实需要艺术调色，必须先获得用户明确授权，并实现为有含义、可配置且默认关闭的参数；不得硬编码到渲染链路中。
- GI 只考虑一次反弹的效果；该限制只约束 indirect transport depth，不限制 direct lighting、BRDF/material response、shadow/visibility、sampling/rasterization、数值精度或 output correctness 的改进。
- 评测目标是使完整 realtime rendering 结果尽可能物理准确、真实并接近 offline reference，而不是只优化 GI。
