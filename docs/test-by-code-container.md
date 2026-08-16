# `test_by_code.py` 容器评测布局

`test_by_code.py` 是 standalone trusted evaluator。它固定读取 `/workspace` 与
`/test_files`，只在 `/eval` 中构建、采集和评分，最终原子写入
`/eval/code_result.json`。

本文档描述正式 container 评测环境的完整复现方法。这里的“只访问”指任务数据
只能来自 `/workspace` 与 `/test_files`；Python runtime、compiler、CMake、Xvfb
等只作为系统 executable/dependency 使用。

## 已验证环境

当前协议已在以下组合完成 200-case candidate/baseline 评测：

- x86-64 Ubuntu 24.04
- Python 3.12.3
- GCC/G++ 13.3.0
- CMake 3.28.3、Ninja 1.11.1
- GLFW 3.3.10、Assimp 5.3.0
- Mesa 25.2.8，renderer 为 `llvmpipe (LLVM 20.1.2, 256 bits)`
- OpenGL 4.5 Compatibility Profile
- Xvfb screen：`1600x1200x24`
- `flip-evaluator==1.7`、`numpy==2.5.2`、`Pillow==12.3.0`

这些是已验证版本，不表示所有 package 的最低版本。正式模型横向比较应冻结同一个
container image，最好使用 image digest，而不是让不同 rollout 分别执行系统升级。
尤其不能混用 Windows GPU baseline 与 Linux llvmpipe candidate。

## 安装系统依赖

Ubuntu 24.04 container/VM 执行：

```bash
sudo apt-get update
sudo apt-get install -y --no-install-recommends \
  build-essential cmake ninja-build pkg-config \
  libgl1-mesa-dev libgl1-mesa-dri mesa-utils \
  libglfw3-dev libassimp-dev \
  libx11-dev libxrandr-dev libxinerama-dev libxi-dev libxcursor-dev libxxf86vm-dev \
  xvfb xauth python3 python3-venv python3-pip
```

项目自带 GLM 与 GLAD；Linux build 使用 system GLFW、Assimp、OpenGL/X11
development packages。Build 和 evaluation 过程不应联网下载 C++ dependency。

安装 exact Python dependencies：

该 lock 要求 Python 3.11+；正式已验证环境使用 Python 3.12.3。

```bash
python3 -m venv /eval/.venv
/eval/.venv/bin/python -m pip install --disable-pip-version-check \
  -r requirements-test-by-code.txt
```

`requirements.txt` 是整个 trusted harness 的兼容范围；正式复现 `test_by_code.py`
时使用仓库中的 `requirements-test-by-code.txt` exact lock。

## 环境 preflight

先确认 build/runtime executable 可见：

```bash
command -v cmake ninja ctest g++ Xvfb glxinfo
pkg-config --modversion glfw3 assimp
/eval/.venv/bin/python -c \
  'import flip_evaluator, numpy, PIL; print(numpy.__version__, PIL.__version__)'
```

确认没有 GPU 的环境确实使用 llvmpipe：

```bash
LIBGL_ALWAYS_SOFTWARE=true GALLIUM_DRIVER=llvmpipe \
  xvfb-run -a -s '-screen 0 1600x1200x24' glxinfo -B
```

输出必须包含 `OpenGL renderer string: llvmpipe`，OpenGL version 不低于项目要求的
3.3。不要在同一批 A/B 评测中改变 Mesa、LLVM、Xvfb screen 或 CPU thread 配置。

## 输入目录

`/workspace/` 放置 coding model 修改后的 realtime-only 仓库快照。脚本不会调用
其中的 Python helper，而是把源码复制到 `/eval` 后直接使用 CMake/Ninja 构建，
再运行 public CTest 和 deterministic capture。

`/test_files/` 必须包含：

```text
/test_files/
  cases.jsonl
  realtime-render-contract.json
  render-score-config.json
  baseline_workspace/
    CMakeLists.txt
    realtime-render-contract.json
    ...
  references/
    cases/
      case-0001/
        manifest.json
        offline.png
        offline-indirect-linear.pfm
        offline-occlusion-mask.pgm
      ...
```

三个固定 root 的权限要求：

- `/workspace`：只需可读；保存 coding model rollout 后的完整 realtime 仓库。
- `/test_files`：只需可读；保存隐藏 state、协议、baseline 和 offline references。
- `/eval`：必须可写；保存临时 source/build/capture 与最终 JSON。

若平台尚未创建 mount point，可在挂载数据前创建：

```bash
sudo install -d -m 0755 /workspace /test_files
sudo install -d -m 0775 -o "$(id -un)" -g "$(id -gn)" /eval
```

也可以把 `references/` 的内容压缩为 `/test_files/references.zip`；ZIP 根目录必须
直接包含 `cases/`，或只包含一个内部目录且该目录包含 `cases/`。脚本拒绝 absolute
path、`..`、symbolic link 和超过 4 GiB 的解压 payload。

推荐提供隐藏的 `baseline_workspace/`。脚本会在同一容器中分别构建 baseline A 与
candidate B，并使用相同的 Xvfb、Mesa/llvmpipe、test set 和 reference 现场采集，
从根本上避免跨 backend 比较。

若评测平台对时长有严格限制，也可以不提供 `baseline_workspace/`，改为提供
`baseline-score-report.json`。该报告必须由与评测容器完全相同的 OS image、
Mesa/llvmpipe version、test set、4096 SPP reference 和评分协议生成；不得把
Windows GPU baseline 与 Linux llvmpipe candidate 混合比较。

## Build compatibility 与固定 runtime

脚本把 candidate 和 baseline 分别复制到 `/eval/test_by_code_runtime/` 后构建，不会
修改 `/workspace` 或 `/test_files`。在 POSIX 环境中，两次 build 都统一追加
`CXXFLAGS=-include unistd.h`，用于补齐以 Windows/VS2022 为主要开发目标的 snapshot
可能遗漏的 POSIX declaration。该 compatibility layer 不修改 candidate source、shader、
rendering algorithm 或评分数据，并且对 baseline/candidate 完全一致。

Capture 阶段会清除外部 `PRT_*` environment variable，并固定：

```text
LIBGL_ALWAYS_SOFTWARE=true
GALLIUM_DRIVER=llvmpipe
LP_NUM_THREADS=min(8, available CPU count)
Xvfb screen=1600x1200x24
```

若正式平台可能分配不同 CPU 数量，应把 rollout 固定在不少于 8 个可用 CPU，确保
`LP_NUM_THREADS` 始终为 8。candidate 和 baseline 在同一次 script execution 中依次
capture，从而共享完全相同的 software-rendering backend。

## 执行完整评测

确认 `/workspace`、`/test_files` 已挂载且 `/eval` 可写后，在 trusted harness
repository root 执行：

```bash
test -r /workspace/CMakeLists.txt
test -r /test_files/cases.jsonl
test -r /test_files/realtime-render-contract.json
test -r /test_files/render-score-config.json
test -w /eval
/eval/.venv/bin/python ./test_by_code.py
```

脚本成功启动不等于 `resolved=true`；它会尽量把 build/capture/score failure 也编码到
结果 JSON。因此必须读取结果，而不能只检查 process exit code：

```bash
/eval/.venv/bin/python -m json.tool /eval/code_result.json
```

一次完整 same-container 运行包含：candidate build 与 public CTest、200-case candidate
capture、baseline build、200-case baseline capture、两组指标计算与 regression gates。
运行期间没有逐 case stdout 属于正常行为。

## 输出语义

`/eval/code_result.json` 包含且只包含：

```json
{"resolved":true,"score":0.43651812655512257,"reason":"success; ..."}
```

- `score` 是当前正式协议的 gated Normalized improvement，范围为 `0..1`。
- 主分仍为 FLIP `70%` / Indirect `30%` 的 weighted geometric mean。
- `median(FLIP B-A)` 与 `median(worst-patch FLIP B-A)` 必须都大于 `0`；否则
  `score=0`。
- `resolved=true` 还要求 candidate public CTest 全部通过。若图像 gates 通过但
  public tests 失败，脚本保留图像 improvement score，但将 `resolved` 设为 `false`。
- `score<=0` 时 `resolved` 强制为 `false`，包括输出层的防御性校验。
- Build、capture、输入完整性或 dependency 失败时，输出 `resolved=false`、
  `score=0`，并在 `reason` 中给出脱敏原因。

## 复现检查清单

归档或比较两次模型评测前，至少确认：

1. 使用相同 container image/digest 和 x86-64 architecture。
2. 使用同一 `/test_files/cases.jsonl`、render contract、score config 和 references。
3. `baseline_workspace` 内容完全一致，且不是跨 backend 预计算分数。
4. `glxinfo -B` 均报告 llvmpipe，Mesa/LLVM version 相同。
5. Xvfb screen、可用 CPU count 和 `LP_NUM_THREADS` 相同。
6. Python packages 与 `requirements-test-by-code.txt` 一致。
7. 保存原始 `/eval/code_result.json`；不要把 `strict` 误当作最终分数，最终模型分数是
   `score` 字段中的 gated Normalized improvement。
