## 渲染修改原则

- Realtime rendering 修复必须优先采用可解释的物理模型、材质参数、单位与能量守恒关系，禁止用 saturation、gain、exposure、颜色偏置等艺术性 magic number 掩盖算法或数据问题。
- 若确实需要艺术调色，必须先获得用户明确授权，并实现为有含义、可配置且默认关闭的参数；不得硬编码到渲染链路中。
- GI 只考虑一次反弹的效果；该限制只约束 indirect transport depth，不限制 direct lighting、BRDF/material response、shadow/visibility、sampling/rasterization、数值精度或 output correctness 的改进。
- 评测目标是使完整 realtime rendering 结果尽可能物理准确、真实并接近 offline reference，而不是只优化 GI。
