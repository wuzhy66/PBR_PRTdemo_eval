# PRT GI Realtime rendering 模型评测总结

## 编程任务场景

在已经实现的 PRT 实时全局光照 [PBR_PRTdemo](https://github.com/wuzhy66/PBR_PRTdemo) 中继续探索效果改进。

## 主 agent

Claude Code（`effort: high`）+评测模型。

## 子 agent 固定设置

Opus=`gpt-5.6-sol`，Sonnet=`deepseek-v4-pro`，Haiku=`deepseek-v4-flash`。

## 提示词

请自主、持续地改进本项目的完整 realtime rendering（光源动态变化，静态场景），使其在 public render contract 下尽可能物理真实（尽可能和离线渲染效果一样），包括但不限于 GI 本身的效果。尽量不向用户提问，不要在发现有效改进后就提前结束，充分反复检查本项目还存在的可改进实时渲染的效果优化，直到收敛到已经无法发现可改进实时渲染效果的点才结束。

## 指标评估

取 demo 场景中不同灯光和相机位置的 200 个快照 case，以 path tracing 离线渲染图为答案。先计算 FLIP 与 Indirect 的 0～1 similarity score，再按 `FLIP^0.7 × Indirect^0.3` 得到 Strict score。仅当全 case 平均 B−A 大于 0，且 FLIP、worst-patch FLIP 的 median regression gates 均通过时，才按 baseline 剩余提升空间归一化到 0～1，否则判定失败。开发阶段模型无法看到隐藏测试集；该评测检查静态快照，不检查光源运动时的 temporal stability。
各轮详细评测结果见 [eval_rollout](./eval_rollout/)。

## 模型优劣

整体无法可靠排序：各模型在该任务场景中效果方差较大，每个模型仅评测了 2～4 次；本批实验的最高分、平均分和成功次数只能说明这些具体 rollout，不能代表模型的稳定能力。以下按主 agent 模型归类，使用过 subagent 的结果不能完全归因于主模型。

在同为 4 次实验的 gpt-5.6-sol 与 gpt-5.6-luna 之间，现有结果表现为 **sol > luna**：sol 修改范围更广，覆盖 Probe、SH、PBR、shadow、visibility 和 capture 等完整 rendering pipeline，仍保持 4/4 通过；luna 的修改更少、更保守，却只有 2/4 通过。

在同为 2 次实验的 deepseek-v4-pro 与 deepseek-v4-flash 之间，现有结果表现为 **Pro > Flash**：Pro 2/2 通过，得分为 0.5201、0.2066，两轮都集中于 PRT Probe sampling、SH convolution 和 shadow map；Flash 只有 1/2 通过，成功轮得分 0.3767，失败轮同时大改 SH projection、Indirect specular 和 capture orientation，合并结果中 Indirect 明显恶化，最终得分为 0。

claude-opus-4.8 取得过本批最高分，但失败轮同时采用激进的 shadow bias、20-tap PCF 等改动，出现大量阴影失真，稳定性不足。

## 各模型完成状态

### deepseek-v4-pro（成功）

2/2 轮通过。两轮都围绕 PRT Probe sampling 和 point-light shadow map 展开：提高间接光采样精度，并修复 shadow coverage/shadow bias。最佳轮还使用解析 SH convolution，FLIP 和综合分数在 200/200 个画面中全部改善，最终分数 0.5201。另一轮增加 Probe rays/grid density，并使用 slope-scaled shadow bias，Indirect 明显改善，但部分遮挡区域退化，最终分数只有 0.2066。

### deepseek-v4-flash（部分完成）

1/2 轮通过。两轮都修改了 Probe transport/reconstruction 和 point-light shadow map，希望同时改善间接光与阴影。成功轮采用较克制的 Probe sampling、shadow range/bias 和 invalid Probe reconstruction（无效 Probe 周围的光照补全），187/200 个画面的综合分数改善，最终得分 0.3767。失败轮大幅重构 SH projection、间接高光和 capture orientation；虽然整图 FLIP 与 worst-patch FLIP 变好，但 Indirect 大幅下降约 0.269，最终总分下降并判定失败。

### gpt-5.6-sol（成功）

4/4 轮全部通过，是目前重复结果最稳定的一组。四轮的共同点是先审查完整 rendering pipeline，再系统修改 deterministic Probe sampling、SH convolution、point-light shadow map、GGX PBR 和 capture correctness；部分轮还加入 BVH visibility，以更快判断物体遮挡。最佳轮最终得分 0.4365，181/200 个画面改善。较弱轮得分约 0.286，虽然总体通过，但一轮仍有 73 个画面退化，而且 Indirect 只改善了一点，说明大规模修改的收益并不均匀。

### gpt-5.6-luna（部分完成）

2/4 轮通过。四轮共同尝试 deterministic Probe sampling、point-light shadow coverage/shadow bias 和 PBR numerical stability，但通常只保留少量、较保守的修改。两个成功轮分别有 183/200、177/200 个画面改善，最终得分 0.4179、0.4023。一个失败轮没有在结束前进行 offline image-space A/B 检查，虽然 Indirect 光照效果确实得到改善，平均分提高，但 FLIP 与 worst-patch regression gates 均失败，因为新的 shadow bias 参数没调好使多数画面的阴影退化；另一个失败轮修改大多没有改变最终画面，少量 shadow bias 变化还带来轻微负收益。

### claude-opus-4.8（部分完成）

1/2 轮通过。两轮尝试都通过增加 Probe 采样、扩大 shadow cubemap coverage、调整 shadow bias 并加入 PCF 来改善间接光和阴影。成功轮调整点光源 shadow cubemap coverage，让六个方向上的近处物体和远处墙面都能被正确记录，使用基于 shadow texel 大小的 shadow bias 和 5-tap PCF，同时增加 Probe rays/grid density，FLIP 在 200/200 个画面中改善，Indirect 在 189/200 个画面中改善，最终分数 0.5671，为本批最高。失败轮使用 20-tap PCF 和过大的 shadow bias，产生不真实的软阴影、阴影悬浮和漏光，导致 144 个画面的 FLIP 退化。

## 表现观察

gpt-5.6-sol 和 gpt-5.6-luna 倾向先调用 EnterPlanMode 规划，过程中多次调用 subagent 做审查和梳理；部分 subagent 因 Claude Code local worktree isolation 被 Git 状态触发安全拒绝，未能成功启动，可能影响最终效果。deepseek-v4-pro、deepseek-v4-flash、claude-opus-4.8 均未调用 EnterPlanMode 和 subagent。由于多次实验触发了超出 context 的自动压缩，调用 subagent 可能有利于该任务。

## 模型变强后调整评测

加大场景复杂度，接入多种复杂 3D 模型；加入对 realtime rendering 性能的评测；接入游戏引擎。

## 案例价值

虽然本案例中同一模型的执行结果方差较大，当前无法可靠评测不同模型的优劣，但该闭环能够产生可验证 reward，理论上可以用于 agentic RL 后训练，提升模型完成渲染效果改进任务的能力。

## 迁移到评测平台

Linux 评测机器没有 GPU，可用 Mesa llvmpipe（CPU 软光栅）运行 OpenGL 3.3 并复用同一套代码和评测流程，但其 FPS 不能代表 GPU 实时渲染性能。
