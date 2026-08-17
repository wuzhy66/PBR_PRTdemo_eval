#!/usr/bin/env python3
"""将 eval HTML archive 批量导出为 GitHub 可直接阅读的 Markdown。"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from generate_claude_execution_report import payload_from_report, render_markdown_report


def render_index(entries: list[tuple[Path, dict[str, Any]]]) -> str:
    lines = [
        "# Rendering evaluation reports",
        "",
        "本目录中的报告均为 GitHub 可直接渲染的 Markdown。",
        "",
        "最终排名查看 `Normalized improvement`，不是单个 renderer 的 `Strict score`。",
        "",
        "| Test | Model | Decision | Normalized improvement | Strict score | Mean B−A | Cases | Report |",
        "|---|---|---|---:|---:|---:|---:|---|",
    ]
    for markdown_path, payload in sorted(entries, key=lambda item: item[0].name.lower()):
        profile = payload.get("profile", {})
        execution = payload.get("execution", {})
        evaluation = payload.get("evaluation", {})
        complete = evaluation.get("status") == "complete"
        decision = evaluation.get("decision", "pending") if complete else "pending"
        normalized = f"{float(evaluation.get('normalizedImprovementScore', 0)):.8f}" if complete else "—"
        strict = f"{float(evaluation.get('averageScoreB', 0)):.8f}" if complete else "—"
        mean = f"{float(evaluation.get('averageImprovement', 0)):+.8f}" if complete else "—"
        cases = evaluation.get("caseCount", "—") if complete else "—"
        lines.append(
            f"| {profile.get('testId', '')} | {execution.get('mainModel', 'unknown')} | {decision} | {normalized} | {strict} | {mean} | {cases} | [Markdown]({markdown_path.as_posix()}) |"
        )
    lines.extend(
        [
            "",
            "## 目录约定",
            "",
            "- `eval_md/`：GitHub 可直接渲染的报告，包含指标、过程分析、阶段与 tool-call 摘要。",
            "- 报告不包含具体执行日期、时长或机器绝对路径。",
            "",
        ]
    )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-root", type=Path, default=Path("eval_docs/eval_html"))
    parser.add_argument("--output-root", type=Path, default=Path("eval_docs/eval_md"))
    parser.add_argument("--index", type=Path, default=Path("eval_docs/README.md"))
    arguments = parser.parse_args()

    arguments.output_root.mkdir(parents=True, exist_ok=True)
    entries: list[tuple[Path, dict[str, Any]]] = []
    for html_path in sorted(arguments.input_root.glob("*.html")):
        payload = payload_from_report(html_path)
        markdown_path = arguments.output_root / f"{html_path.stem}.md"
        markdown_path.write_text(
            render_markdown_report(payload),
            encoding="utf-8",
            newline="\n",
        )
        entries.append((Path("eval_md") / markdown_path.name, payload))
        print(f"生成 Markdown：{markdown_path}")

    arguments.index.parent.mkdir(parents=True, exist_ok=True)
    arguments.index.write_text(render_index(entries), encoding="utf-8", newline="\n")
    print(f"生成索引：{arguments.index}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
