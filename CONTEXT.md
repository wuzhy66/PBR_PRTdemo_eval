# PRTdemo Context

## Domain glossary

- **Renderer Mode**：同一 executable 中选择 direct-light BRDF 的 runtime 配置，当前值为 `Phong` 或 `PBR`。
- **Direct-light Adapter**：在 Renderer Mode seam 上计算直接反射的实现；CPU Surfel 与 GPU fragment shader 必须选择同一个 adapter。
- **Transport Pipeline**：两个 Renderer Mode 共享的 Scene triangle、Ray/Surfel、Irradiance convolution、SH projection、3D texture 与 reconstruction 数据流。

## Invariants

- Renderer Mode 只能改变 direct-light Adapter 和对应 light 参数，不能复制或分叉 Transport Pipeline。
- CPU Surfel 与 GPU rasterization 必须使用相同的 Renderer Mode 和 linear albedo。
- GI/PBR 修改遵循 `AGENTS.md` 的物理优先规则，不用艺术性 magic number 掩盖 transport 问题。
