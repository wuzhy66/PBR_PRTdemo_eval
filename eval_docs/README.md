# Rendering evaluation reports

最终排名查看 `Normalized improvement`，不是单个 renderer 的 `Strict score`。

[Realtime rendering 模型评测总结](model-evaluation-summary.md)。

| Test | Model | Decision | Normalized improvement | Strict score | Mean B−A | Cases | Report |
|---|---|---|---:|---:|---:|---:|---|
| TEST01 | gpt-5.6-luna | failed-regression | 0.00000000 | 0.83486219 | +0.01621316 | 200 | [Markdown](eval_rollout/test01-gpt-5.6-luna-evaluation.md) |
| TEST02 | deepseek-v4-flash | success | 0.37673252 | 0.88696984 | +0.06832081 | 200 | [Markdown](eval_rollout/test02-deepseek-v4-flash-evaluation.md) |
| TEST03 | gpt-5.6-sol | success | 0.28633464 | 0.87057609 | +0.05192707 | 200 | [Markdown](eval_rollout/test03-gpt-5.6-sol-evaluation.md) |
| TEST04 | gpt-5.6-luna | success | 0.41786051 | 0.89442844 | +0.07577941 | 200 | [Markdown](eval_rollout/test04-gpt-5.6-luna-evaluation.md) |
| TEST05 | deepseek-v4-pro | success | 0.52008568 | 0.91296707 | +0.09431804 | 200 | [Markdown](eval_rollout/test05-deepseek-v4-pro-evaluation.md) |
| TEST06 | gpt-5.6-sol | success | 0.28570883 | 0.87046260 | +0.05181357 | 200 | [Markdown](eval_rollout/test06-gpt-5.6-sol-evaluation.md) |
| TEST07 | deepseek-v4-pro | success | 0.20662320 | 0.85612035 | +0.03747132 | 200 | [Markdown](eval_rollout/test07-deepseek-v4-pro-evaluation.md) |
| TEST08 | deepseek-v4-flash | failure | 0.00000000 | 0.78000862 | -0.03864041 | 200 | [Markdown](eval_rollout/test08-deepseek-v4-flash-evaluation.md) |
| TEST10 | gpt-5.6-luna | success | 0.40233022 | 0.89161200 | +0.07296298 | 200 | [Markdown](eval_rollout/test10-gpt-5.6-luna-evaluation.md) |
| TEST11 | gpt-5.6-sol | success | 0.43651813 | 0.89781202 | +0.07916299 | 200 | [Markdown](eval_rollout/test11-gpt-5.6-sol-evaluation.md) |
| TEST13 | gpt-5.6-sol | success | 0.42710169 | 0.89610433 | +0.07745531 | 200 | [Markdown](eval_rollout/test13-gpt-5.6-sol-evaluation.md) |
| TEST14 | gpt-5.6-luna | failure | 0.00000000 | 0.81858219 | -0.00006684 | 200 | [Markdown](eval_rollout/test14-gpt-5.6-luna-evaluation.md) |
| TEST20 | claude-opus-4-8 | failure | 0.00000000 | 0.81444750 | -0.00420153 | 200 | [Markdown](eval_rollout/test20-claude-opus-4-8-evaluation.md) |
| TEST21 | claude-opus-4-8 | success | 0.56714054 | 0.92150052 | +0.10285149 | 200 | [Markdown](eval_rollout/test21-claude-opus-4-8-evaluation.md) |
