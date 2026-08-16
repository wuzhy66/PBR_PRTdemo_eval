# CPU offline reference renderer

这是一个独立于 OpenGL、Vulkan、DirectX、window system 与 GPU 的 deterministic CPU reference renderer，用于生成严格匹配 PRTdemo realtime PBR one-bounce transport 的离线参考结果。

它复用当前项目的关键参数：

- room、6 个 axis-aligned cubes 与对应 linear albedo
- `metallic=0`、`roughness=1`、`IOR=1.5`、`AO=1`
- point light 使用 inverse-square attenuation；standalone 默认 intensity 为 `RGB=(150,150,150)`，dataset reference 使用每条 test case 的 RGB intensity
- direct light 与 secondary surface 使用当前 Cook–Torrance GGX BRDF，包括 denominator 的 `+0.001`
- primary indirect receiver 使用 realtime shader 相同的 `fresnelSchlickRoughness` 与 `kD * albedo / PI`
- Reinhard tone mapping 与 sRGB encoding

Offline renderer 使用 next-event estimation。primary receiver 按 cosine hemisphere sampling，之后只访问一个 secondary surface；`--bounces` 被强制为 `2`，严格对应 realtime PRT 的 one indirect bounce。Realtime 与 offline 都采用 deterministic 2×2 SSAA，固定使用 `(0.25,0.25)`、`(0.75,0.25)`、`(0.25,0.75)`、`(0.75,0.75)` 四个 subpixel center，在 linear HDR 中等权 resolve，之后才做 Reinhard tone mapping 与 sRGB encoding。`--spp` 表示每个最终输出 pixel 的总 sample 数，必须是 4 的倍数，并在四个 subpixel 间均分；因此 `4096 spp` 是每个 subpixel `1024` 个 one-bounce sample，不会隐式扩大成 `16384 spp`。每个 subpixel 使用独立 random shift 的 low-discrepancy bases `2,3` 生成 hemisphere sample，以降低 Monte Carlo variance；除此之外不包含 denoise、radiance clamp 或任何艺术性调色。

Reference 不复刻 3-band SH truncation、Probe density/ray count、trilinear Probe interpolation、shadow cubemap resolution/bias 等 realtime approximation，因为这些正是 candidate 与 reference 之间需要量化的误差。Offline 使用 exact ray visibility；因此 GI 模型评分应优先比较 `*-indirect-linear.pfm`，避免 direct shadow-map error 混入分数。

Secondary surface 的 Cook–Torrance view direction 使用实际的 `secondary → primary hit`。Realtime PRT 在 surfel shading 时以 `secondary → probe` 近似该方向；这属于 Probe approximation，不能复制进 ground-truth reference，否则会把 probe-position error 定义成满分答案。

Realtime 在 lighting pass 之后额外绘制的 light sphere 只是 visualization overlay，不参与 light transport，offline reference 不包含它。评分输入应导出 overlay 之前的 indirect linear buffer；如果只能取得最终 screenshot，必须先排除 light sphere pixels，不能把 overlay 差异计入 GI score。

PNG 用于观察，PFM 保存经过同一 2×2 linear resolve、但尚未 tone-map 的 linear HDR 数据，可作为后续 metric evaluator 的输入。正式评分 reference 默认使用 `4096 spp`；需要快速开发预览时可显式传入较低、且能被 4 整除的 SPP。

## Linux

```bash
python3 ./tools/build_offline_renderer.py
./offline/build-auto-linux-ninja/prt_offline_reference --self-test
./offline/build-auto-linux-ninja/prt_offline_reference \
  --output test-results/offline-reference/reference \
  --width 800 --height 600 --spp 4096 --bounces 2
```

不需要任何第三方 graphics 或 image library。

## Windows

```powershell
python .\tools\render_offline_reference.py

# 生成正式评分 reference
python .\tools\render_offline_reference.py `
    --width 800 --height 600 --samples-per-pixel 4096 `
    --max-bounces 2 --seed 20260812

# 快速预览一个 snapshot
python .\tools\render_offline_reference.py `
    --only wide-center --width 320 --height 240 `
    --samples-per-pixel 64 --max-bounces 2

# 构建并验证 offline/realtime alignment contract
python .\tools\build_offline_renderer.py
.\offline\build-auto-vs2022-ninja\prt_offline_reference.exe --self-test

# 复现任意 realtime camera/light 状态；坐标使用逗号分隔且不能含空格
.\offline\build-auto-vs2022-ninja\prt_offline_reference.exe `
    --output test-results/offline-reference/custom `
    --spp 4096 `
    --camera-position=-9.61,7.82,-9.44 `
    --camera-yaw=37.57 --camera-pitch=-46.52 --camera-fov=45 `
    --light-position=-4.2,5,-6.6 --light-intensity=150,150,150
```

每个 snapshot 输出：

- `offline.png`：自定义测试 case 的 offline combined display reference
- `<name>.png`：内置 snapshot 的 combined display preview
- `<name>-indirect.png`：indirect-only display preview
- `<name>-linear.pfm`：combined linear HDR
- `<name>-direct-linear.pfm`：direct linear HDR
- `<name>-indirect-linear.pfm`：indirect linear HDR
- `<name>-occlusion-mask.pgm`：由 exact ray visibility 生成的 primary-surface cube cast-shadow mask，供 light leaking metric 使用

`manifest.json` 记录 camera、light、samples、bounces 和 seed。

固定 snapshot 使用 realtime visual test 的 `wide`、`cube-top` 两个 camera，并为每个 camera 配置中央、左前、右后三个 point-light position。非中央光源保持 `y=5`，且 X/Z 坐标均为 realtime keyboard control 的 `0.3` 单位整数倍。
