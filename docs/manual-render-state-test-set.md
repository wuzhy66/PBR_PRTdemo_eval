# 手动采集 render-state 渲染测试集

测试集只保存 camera position/yaw/pitch 与 point-light position/RGB intensity。它不保存任何 realtime/offline image、timestamp、采集时间、reference 参数或评分指标。

设置 official test set 输出位置并启动 realtime renderer：

```powershell
$env:PRT_TEST_SET_PATH = (Resolve-Path .\test-set\cases.jsonl).Path
.\PBR_PRTdemo\bin\getting_started\PRTdemo.exe --renderer PBR
```

Linux workstation：

```bash
PRT_TEST_SET_PATH="$PWD/test-set/cases.jsonl" \
  ./PBR_PRTdemo/bin/getting_started/PRTdemo --renderer PBR
```

手动移动 camera/light 需要可交互 display；纯 headless evaluator 负责 replay 已保存的 render state，不负责人工采集。

移动 camera 和 point light，用 `[`/`]` 降低/提高 intensity，等待 Probe coefficients 稳定后按 `F5`。重复 render state 会被忽略，记录会按完整状态 canonical sort，因此不保留采集顺序。Point light 没有 orientation，因此 test set 不记录 light orientation。

示例记录：

```json
{"camera":{"position":[9.4277277,7.3449464,9.2268810],"yawDegrees":-141.5998993,"pitchDegrees":-50.8999863},"light":{"position":[6.0000010,5.0000000,7.2000017],"intensity":[150.0000000,150.0000000,150.0000000]}}
```

测试时，trusted harness 按 test set 顺序分配 opaque case ID，分别生成 realtime 与 reference images，然后执行隐藏的 metric evaluator。所有图片与报告写入 `test-results/runs/`，不会修改测试集。

## 批量生成 official test set

需要重新生成当前 balanced test set 时运行：

```powershell
python .\tools\Generate-RenderTestSet.py
```

Linux 对应命令为 `python3 ./tools/Generate-RenderTestSet.py`。

当前 generator 固定生成 `200` 个 case：`72` 条 balanced core 保留 `24` 个 indoor camera pose × RGB intensity `80/150/250`；另有 `128` 条 targeted stress cases，使用 `64` 组不同 camera/light geometry × 两档既有 intensity `80/250`，重点覆盖 contact shadow、cube-to-cube occlusion、近墙/近地/近天花板光源、掠射视角和跨房间长阴影。Generator 会拒绝位于 room 外、离墙安全余量不足、落入 cube safety volume 或产生重复状态的配置，并以 canonical order 写入 JSONL。
