# Windows/Linux 自动 build 与 evaluation

仓库支持同一套闭环：

`修改 C++/GLSL → platform build → contract/numerics tests → deterministic one-shot capture → offline reference → FLIP/indirect/occlusion score`

## Platform preflight

Windows PowerShell：

```powershell
python .\PBR_PRTdemo\tools\test.py
python .\tools\build_offline_renderer.py
.\offline\build-auto-vs2022-ninja\prt_offline_reference.exe --self-test
python .\tools\test_prt_numerics.py
```

Ubuntu 24.04：

```bash
python3 ./PBR_PRTdemo/tools/test.py
python3 ./tools/build_offline_renderer.py
./offline/build-auto-linux-ninja/prt_offline_reference --self-test
python3 ./tools/test_prt_numerics.py
```

Realtime tests 不创建窗口；它们验证 `frame_timing`、capture schema、public render contract 和 PBR/Phong PRT numerics。Parent numerical test 额外验证 one-bounce receiver、Irradiance convolution 与 Ray/Surfel mapping。

## 无 GPU Linux one-shot capture

安装 Mesa llvmpipe 与 Xvfb 后运行：

```bash
python3 ./tools/replay_render_dataset.py \
  --test-set ./test-set/cases.jsonl \
  --realtime-repository ./PBR_PRTdemo \
  --output-root ./test-results/runs/linux-baseline-v4/realtime \
  --software-rendering \
  --llvmpipe-threads 8
```

没有 `DISPLAY` 时 script 会自动通过 `xvfb-run` 重启；`--software-rendering` 强制 `LIBGL_ALWAYS_SOFTWARE=true` 和 `GALLIUM_DRIVER=llvmpipe`。每条 case 必须得到 `realtime.png`、`indirect-linear.pfm`、`state.json`，任一 shader compile/link、OpenGL init 或 export 失败都返回 non-zero。

该模式用于 image correctness 与 coding model 评分，不用于 GPU FPS、driver 或 RenderDoc performance evaluation。

正式模型 A/B 必须固定同一 OS image、Mesa/llvmpipe version、Xvfb screen、`LP_NUM_THREADS`、test set、render contract 和 reference。Windows GPU 与 Linux llvmpipe 可能有微小 floating-point/edge rasterization 差异，不能把跨 backend 分数差当作模型改进。

## Windows interactive visual regression

需要检查 Phong/PBR、SH2/SH3/SH4、dynamic light 和窗口交互时，可在带 GPU 的 Windows workstation 运行：

```powershell
python .\tools\test_visual.py --renderer all --include-dynamic
```

这个 legacy interactive screenshot runner 依赖 Win32 window capture。正式模型排名应使用 dataset one-shot capture 与 strict scorer，而不是窗口截图 RMS。

## 自动测试环境变量

测试脚本启动 demo 时会设置以下变量；日常交互运行不受影响：

- `PRT_VISUAL_TEST=1`：启用固定 camera 和 deterministic Probe sampling。
- `PRT_RENDERER=Phong|PBR`：选择同一 executable 中的 Renderer Mode。
- `PRT_TEST_MODE=combined|direct|indirect|probes`：指定渲染场景。
- `PRT_BANDS=2|3|4`：选择 SH bands，默认 `3`（9 coefficients）。
- `PRT_DYNAMIC=0|1`：控制动态光源。
- `PRT_DIRECT_SHADOW=0|1`：覆盖直接光 shadow 开关。
- `PRT_PROBE_SHADOW=0|1`：覆盖 Probe shadow 开关。
- `PRT_TEST_CAMERA=wide|cube-top`：切换全景或 cube 顶面固定 camera。

Interactive pixel test 只能发现画面空白、模式失效、明显回归和 dynamic light 停止。正式 light leaking、SH truncation 与 indirect transport 差异由 dataset scorer 量化，并结合生成的 error maps 审阅。

## Dataset 评分图

运行 `tools/Score-RenderDataset.py` 后，每个 realtime case 会生成三组 Offline / Realtime / Error 对照图，以及汇总两项计分指标和两项 diagnostics 的 `metrics-explained.png`。最终 Strict score 使用 FLIP `70%` 与 indirect transport `30%` 的 weighted geometric mean；worst-patch FLIP 与 occlusion leak 不参与 case total。A/B compare 还要求 FLIP 与 worst-patch FLIP 的 per-case median improvement 均为正，否则正式 Normalized improvement 为 0。Offline 侧的 `offline-indirect.png` 与 `offline-occlusion-leak.png` 会在 reference render 阶段提前准备。完整公式、色标、regression gates 和 case 示例见 [渲染评分指标说明](render-score-metrics.html)。
