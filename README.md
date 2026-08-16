# PRT rendering evaluation harness

本仓库是 trusted evaluation harness；realtime renderer 位于独立仓库 `PBR_PRTdemo/`。实验时只把 realtime 仓库的独立 clone/worktree 交给 coding agent，不向 agent 提供本仓库，从而隔离 reference renderer、评分实现、权重与测试产物。

> 仅把 Claude Code 的 working directory 设到嵌套目录不是安全边界；它仍可能访问 `..`。正式实验必须使用独立 clone、container 或 filesystem sandbox，只挂载 realtime 仓库。

创建不含 trusted harness 的独立 agent workspace：

```text
python ./tools/new_realtime_agent_workspace.py --destination ../experiments/model-a
```

每次更新 realtime repository 后运行隔离回归检查：

```text
python ./tools/test_realtime_isolation.py
```

## Claude Code 模型评测提示词

每个模型都从相同 baseline commit 的独立 workspace 开始，并原样使用以下一段 prompt；详细执行规范由 realtime 仓库的 `AGENTS.md` 提供，不追加定向提示或 hidden score 反馈：

```text
请自主、持续地改进本项目的完整 realtime rendering（光源动态变化，静态场景），使其在 public render contract 下尽可能物理真实（尽可能和离线渲染效果一样），包括但不限于 GI 本身的效果。尽量不向用户提问，不要在发现有效改进后就提前结束，充分反复检查本项目还存在的可改进实时渲染的效果优化，直到收敛到已经无法发现可改进实时渲染效果的点才结束。
```

该 prompt 测量的是一次无人干预的 `single-run best effort`，不是模型能力的统计上限。不同模型必须固定相同 baseline、Claude Code/scaffold、reasoning effort、permission mode、工具环境和外部 wall-time/token budget；运行期间不追加“继续”、定向提示或 hidden score 反馈。模型自然提前结束也属于本次 agent configuration 的观测结果。

## 仓库边界

- `PBR_PRTdemo/`：realtime PBR + PRT renderer、render-state test case capture、realtime frame export、RenderDoc 支持。
- `realtime-render-contract.json`：trusted render condition；`PBR_PRTdemo/` 内含完全一致的 public mirror。replay 会在启动前校验二者，统一 scene/material、camera resolution/viewport/FOV、light intensity 范围、SSAA 与 output transform。
- `test-set/cases.jsonl`：只保存 camera pose、point-light position 与 RGB intensity，不含图片、timestamp、采集时间或评分协议。
- `offline/`：trusted CPU renderer，仅对 evaluator 可见。
- `tools/Score-*`、`tools/Compare-*`：trusted metric 与 A/B improvement evaluator，仅对 evaluator 可见。
- `test-results/`：实验时生成的 realtime/reference images 与报告；不进入 realtime 仓库。

Realtime 仓库可以说明 GI 只考虑 **one indirect bounce**，但不包含 reference renderer 或评估指标实现。

## Test set schema

`test-set/cases.jsonl` 每行一个 case，严格只允许以下字段：

```json
{"camera":{"position":[0.0,4.5,8.0],"yawDegrees":-90.0,"pitchDegrees":-12.0},"light":{"position":[0.0,5.0,0.0],"intensity":[150.0,150.0,150.0]}}
```

Point light 没有 orientation，因此只记录 position 和 RGB intensity。F5 会按完整 render state canonical sort，测试集不保留相对采集顺序。Case identity 由 trusted harness 按文件顺序分配为 `case-0001` 等；测试集不记录 ID，避免通过 ID 暴露采集时间。

手动采集官方 test set 时，在启动 realtime renderer 前设置：

```powershell
$env:PRT_TEST_SET_PATH = (Resolve-Path .\test-set\cases.jsonl).Path
.\PBR_PRTdemo\bin\getting_started\PRTdemo.exe --renderer PBR
```

Linux workstation 对应命令：

```bash
PRT_TEST_SET_PATH="$PWD/test-set/cases.jsonl" \
  ./PBR_PRTdemo/bin/getting_started/PRTdemo --renderer PBR
```

移动 camera/light、用 `[`/`]` 调整 intensity 后按 `F5`。该操作只追加 render state，不读取 framebuffer，也不启动 reference renderer。

也可以 deterministic 生成当前 official test set：`72` 条 balanced core（`24` 个 camera pose × `3` 档 intensity）加 `128` 条 targeted stress cases（`64` 组 camera/light geometry × `2` 档既有 intensity），共 `200` case：

```powershell
python .\tools\Generate-RenderTestSet.py
```

## 如何运行测试

下面命令均在 trusted harness repository root 执行，支持 Windows 10/11 与 x86-64 Linux（已在 Ubuntu 24.04 验证）。两端都要求 Python 3.10+，首次使用先安装 Python dependencies：

评测平台的 exact dependency lock、固定目录、权限、llvmpipe preflight 与完整复现步骤见
[`docs/test-by-code-container.md`](docs/test-by-code-container.md)。

```text
python -m pip install -r requirements.txt
```

Windows 还要求带 `Desktop development with C++` 和 `C++ CMake tools for Windows` 的 VS2022；工具通过 `vswhere` 动态发现安装位置。Ubuntu 24.04 安装：

```bash
sudo apt-get update
sudo apt-get install -y \
  build-essential cmake ninja-build pkg-config \
  libgl1-mesa-dev libgl1-mesa-dri mesa-utils \
  libglfw3-dev libassimp-dev \
  libx11-dev libxrandr-dev libxinerama-dev libxi-dev libxcursor-dev libxxf86vm-dev \
  xvfb python3-venv
```

### 1. 运行代码与协议回归测试

修改代码后先运行完整 preflight：

```powershell
# Build realtime renderer，并运行 5 个 CTest
python .\PBR_PRTdemo\tools\test.py

# Build CPU offline renderer，并验证 PBR/one-bounce/SSAA alignment
python .\tools\build_offline_renderer.py
.\offline\build-auto-vs2022-ninja\prt_offline_reference.exe --self-test

# 验证评分公式、report comparison 和 render-state float round-trip
python -m unittest tests.test_render_score

# 验证子仓库不含 offline/reference/metric，并与 v3 contract 一致
python .\tools\test_realtime_isolation.py `
  --realtime-repository .\PBR_PRTdemo `
  --test-set .\test-set\cases.jsonl

# 验证父仓库与 realtime 子仓库的 tracked text 不暴露机器绝对路径
python .\tools\test_no_absolute_paths.py
```

全部命令返回 exit code `0` 才算通过。

Linux 使用相同 Python entry points，仅把 path separator 与 executable suffix 改为 POSIX 形式：

```bash
python3 ./PBR_PRTdemo/tools/test.py
python3 ./tools/build_offline_renderer.py
./offline/build-auto-linux-ninja/prt_offline_reference --self-test
python3 -m unittest tests.test_render_score
python3 ./tools/test_realtime_isolation.py \
  --realtime-repository ./PBR_PRTdemo \
  --test-set ./test-set/cases.jsonl
python3 ./tools/test_no_absolute_paths.py
```

### 无 GPU Linux 的 batch evaluation

纯 CPU/headless server 使用 Mesa llvmpipe 提供 OpenGL 3.3+ software rasterization，并由 replay script 在没有 `DISPLAY` 时自动通过 `xvfb-run` 重启。先验证 software OpenGL：

```bash
LIBGL_ALWAYS_SOFTWARE=true GALLIUM_DRIVER=llvmpipe \
  xvfb-run -a -s '-screen 0 1600x1200x24' glxinfo -B
```

然后对任意独立 candidate repository 批量生成 realtime 输出：

```bash
python3 ./tools/replay_render_dataset.py \
  --test-set ./test-set/cases.jsonl \
  --realtime-repository ../experiments/model-a \
  --output-root ./test-results/runs/model-a-v4/realtime \
  --software-rendering \
  --llvmpipe-threads 8

python3 ./tools/Score-RenderDataset.py \
  --test-set ./test-set/cases.jsonl \
  --realtime-root ./test-results/runs/model-a-v4/realtime \
  --reference-root ./test-results/references/official-4096-v4 \
  --output ./test-results/runs/model-a-v4/score-report.json \
  --min-reference-spp 4096 \
  --strict \
  --label model-a
```

`--software-rendering` 固定设置 `LIBGL_ALWAYS_SOFTWARE=true`、`GALLIUM_DRIVER=llvmpipe` 与 `LP_NUM_THREADS`。之后的 offline reference、FLIP/indirect/occlusion score 和 A/B comparison 都是 CPU/Python 工作负载，继续使用本文第 4～6 节的相同 entry points。此模式能量化 image correctness 和 coding model 的改进效果，但不能代表真实 GPU FPS、GPU driver 性能或 RenderDoc profile。

不同 OpenGL implementation 的 floating-point 与 edge rasterization 结果不保证 bit-identical。正式 A/B 实验必须为全部模型固定相同的 OS image、Mesa/llvmpipe version、Xvfb screen、`LP_NUM_THREADS`、test set、render contract 和 reference；baseline 与 candidate 不得跨 Windows GPU/Linux llvmpipe 比分。

如果只想在几分钟内验证一次完整的 capture → offline → score 流程，可以从官方测试集取第一条并使用低 SPP；该结果只用于 smoke test，不能用于模型排名：

```powershell
$SmokeTestSet = '.\test-results\smoke-case.jsonl'
$SmokeRoot = '.\test-results\runs\smoke-v3'
$SmokeReferenceRoot = '.\test-results\references\smoke-64-v3'

New-Item -ItemType Directory -Force .\test-results | Out-Null
Get-Content .\test-set\cases.jsonl -TotalCount 1 |
  Set-Content $SmokeTestSet -Encoding utf8

python .\tools\replay_render_dataset.py `
  --test-set $SmokeTestSet `
  --realtime-repository .\PBR_PRTdemo `
  --output-root "$SmokeRoot\realtime" `
  --skip-build

python .\tools\render_test_set_references.py `
  --test-set $SmokeTestSet `
  --output-root $SmokeReferenceRoot `
  --samples-per-pixel 64 `
  --skip-build

python .\tools\Score-RenderDataset.py `
  --test-set $SmokeTestSet `
  --realtime-root "$SmokeRoot\realtime" `
  --reference-root $SmokeReferenceRoot `
  --output "$SmokeRoot\score-report.json" `
  --min-reference-spp 64 `
  --strict `
  --label smoke
```

Smoke output 目录同样拒绝覆盖；重复运行时更换目录名。

### 2. 选择测试集与输出目录

官方完整测试集是 `test-set/cases.jsonl`，当前包含 200 条 render state。下面使用 repository 相邻的独立 agent workspace 作为待测 realtime repository：

```powershell
$TestSet = '.\test-set\cases.jsonl'
$RealtimeRepository = '..\experiments\model-a'
$RunRoot = '.\test-results\runs\baseline-v4'
$ReferenceRoot = '.\test-results\references\official-4096-v4'
```

输出脚本拒绝覆盖已有目录。重复测试时请更换 `$RunRoot`；只要 test set 和 protocol 未变化，`$ReferenceRoot` 可以在 baseline 与 candidate 之间复用。

### 3. 生成 realtime 图片

不确定待测仓库是否已经 build 时，不要传 `--skip-build`：

```powershell
python .\tools\replay_render_dataset.py `
  --test-set $TestSet `
  --realtime-repository $RealtimeRepository `
  --output-root "$RunRoot\realtime"
```

每条 case 生成：

```text
<RunRoot>/realtime/cases/case-xxxx/realtime.png
<RunRoot>/realtime/cases/case-xxxx/indirect-linear.pfm
<RunRoot>/realtime/cases/case-xxxx/state.json
```

已确认 executable 是最新 build 时，可以追加 `--skip-build`。

扩充 test set 时，可用 `--reuse-test-set <旧 cases.jsonl>` 与 `--reuse-realtime-root <旧 realtime root>` 按完整 render state 复用已有 raw capture；旧 `score.json` 和 error 图不会复制。中断后以相同参数追加 `--resume`，脚本会校验 test-set snapshot、保留完整 case 并重新采集不完整 case。

### 4. 生成 4096 SPP offline reference

仓库通过 Git LFS version-control 完整评分所需的 `test-results/references/official-4096-v4/`。正常 clone 后先确认 Git LFS object 已拉取，即可直接跳过本步骤：

```powershell
git lfs install
git lfs pull
```

只有 test set、scene 或 render contract 改变并需要建立新版 reference 时，才运行下面的 4096 SPP 生成命令。版本库保存 `offline.png`、`offline-indirect-linear.pfm`、`offline-occlusion-mask.pgm`、manifest 和指标说明图；评分不读取的 `offline-linear.pfm` 与 `offline-direct-linear.pfm` 不纳入 Git。

```powershell
python .\tools\render_test_set_references.py `
  --test-set $TestSet `
  --output-root $ReferenceRoot `
  --samples-per-pixel 4096 `
  --jobs 4 `
  --threads-per-render 4
```

`--jobs` 控制同时渲染的 case 数，`--threads-per-render` 控制每个 renderer 的 CPU threads；两者乘积不应明显超过机器的 logical CPU 数。每条新 reference 先写入 `.partial` 目录，文件齐全后再原子切换为正式 case；中断后可使用相同参数并追加 `--resume`，脚本会校验 test-set snapshot、清理半成品并保留已完成 case。扩充已有 reference 时还可以用 `--reuse-test-set` 与 `--reuse-reference-root` 按完整 render state 复用旧 case。

每条 case 的可视 reference 是 `offline.png`，linear AOV 使用 `offline-*.pfm`，遮挡 mask 是 `offline-occlusion-mask.pgm`。Reference 生成阶段还会提前准备 `offline-indirect.png` 和 `offline-occlusion-leak.png`，分别作为 indirect transport 与 occlusion leak 的 Offline 对照图。`4096 SPP` 是每个最终 pixel 的总 sample 数，平均分配给 2×2 SSAA 的四个 subpixel，每个 subpixel 为 1024 samples。

4096 SPP 的总耗时取决于 CPU、并行 case 数与每个 renderer 的 threads。当前 200-case 集合可从 v3 reference 复用原 72 条，只需新渲染 128 条；快速检查流程可以显式使用较低 SPP，但不能作为正式评分 reference。

### 5. 运行 Strict 评分

```powershell
python .\tools\Score-RenderDataset.py `
  --test-set $TestSet `
  --realtime-root "$RunRoot\realtime" `
  --reference-root $ReferenceRoot `
  --output "$RunRoot\score-report.json" `
  --min-reference-spp 4096 `
  --strict `
  --label baseline
```

成功时 console 应显示 `strictCases` 等于测试集条数、`excludedCases=0`、`errorCases=0`。结果位于：

```text
<RunRoot>/score-report.json   # 完整机器可读指标与逐 case 分数
<RunRoot>/score-report.md     # 方便人工阅读的报告
<RunRoot>/realtime/cases/case-xxxx/score.json  # 对应 realtime case 的独立评分指标
<RunRoot>/realtime/cases/case-xxxx/metrics-explained.png  # 计分指标与 diagnostics 的图解总览
```

每个 realtime case 还会生成 `realtime-indirect.png`、`realtime-occlusion-leak.png` 和三张 `error-*.png`。同一张 FLIP error map 会额外按 `32×32` tiles 聚合，取 tile mean 的 p95 得到 `worstPatchFlip` diagnostic。`score.json.metricImages` 只用相对文件名记录图片位于 reference case 还是 realtime case，不暴露绝对路径。

`strictScore` 是 FLIP `70%` 与 indirect transport `30%` 的 weighted geometric mean，范围 `0..1`；`1` 表示在本评测协议下与 offline reference 一致。Worst-patch FLIP 与 occlusion leak 保留为 diagnostics，不参与 case total。指标输入、公式、error map 色标、regression gates 和 case 示例见 [渲染评分指标说明](docs/render-score-metrics.html)。

如果只修改 `render-score-config.json` 中的 aggregation weights，可复用已有逐 case 指标，无需重新运行 FLIP 或生成指标图。旧 report 缺少新 diagnostic 时，脚本只补所需计算；需要同步刷新既有 `metrics-explained.png` 时显式追加 `--refresh-overviews`：

```powershell
python .\tools\Score-RenderDataset.py `
  --test-set $TestSet `
  --realtime-root "$RunRoot\realtime" `
  --reference-root $ReferenceRoot `
  --output "$RunRoot\score-report.json" `
  --reuse-metrics-from "$RunRoot\score-report.json" `
  --min-reference-spp 4096 `
  --strict
```

### 6. 评测 candidate 改进

Candidate 必须使用相同 `$TestSet`、同一 `$ReferenceRoot` 和完全一致的 scoring protocol fingerprint。为 candidate 选择新的 output root：

```powershell
$CandidateRunRoot = '.\test-results\runs\candidate-v4'

python .\tools\replay_render_dataset.py `
  --test-set $TestSet `
  --realtime-repository '..\experiments\model-b' `
  --output-root "$CandidateRunRoot\realtime"

python .\tools\Score-RenderDataset.py `
  --test-set $TestSet `
  --realtime-root "$CandidateRunRoot\realtime" `
  --reference-root $ReferenceRoot `
  --output "$CandidateRunRoot\score-report.json" `
  --min-reference-spp 4096 `
  --strict `
  --label candidate

python .\tools\Compare-RenderScores.py `
  --baseline "$RunRoot\score-report.json" `
  --candidate "$CandidateRunRoot\score-report.json" `
  --output "$CandidateRunRoot\improvement-report.json"
```

正式结果必须同时满足：平均 Strict improvement 为正、per-case FLIP improvement 的 median 为正、per-case worst-patch FLIP improvement 的 median 为正。平均值不为正时 decision 为 `failure`；平均值为正但任一 regression gate 失败时 decision 为 `failed-regression`，正式 `normalizedImprovementScore=0`，同时保留 `ungatedNormalizedImprovementScore` 供诊断。Reference、图片与 metric report 都留在父仓库 `test-results/`，不会写入 realtime 子仓库或 render-state test set。
