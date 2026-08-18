#!/usr/bin/env python3
"""从 Claude Code JSONL 和 candidate Git diff 生成脱敏的交互式执行报告。"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import subprocess
from collections import Counter
from pathlib import Path
from typing import Any


DATE_PATTERNS = (
    re.compile(r"\b20\d{6}(?:[-_]\d{6})?\b"),
    re.compile(r"\b20\d{2}[-/]\d{1,2}[-/]\d{1,2}(?:[T\s]\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?(?:Z|[+-]\d{2}:?\d{2})?)?\b"),
    re.compile(r"\b20\d{2}年\d{1,2}月\d{1,2}日(?:\s*\d{1,2}时\d{1,2}分(?:\d{1,2}秒)?)?"),
    re.compile(
        r"\b(?:Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec)\s+"
        r"\d{1,2}\s+(?:\d{2}:\d{2}|20\d{2})\b",
        re.I,
    ),
    re.compile(r"\b\d{1,2}:\d{2}:\d{2}(?:\.\d+)?\b"),
)
DURATION_PATTERNS = (
    re.compile(r"\b\d+(?:\.\d+)?\s*(?:ms|milliseconds?|secs?|seconds?|mins?|minutes?|hrs?|hours?)\b", re.I),
    re.compile(r"\b\d+h\d+m(?:\d+s)?\b|\b\d+m\d+s\b", re.I),
    re.compile(r'(["\']?(?:timeout|timeout_ms|durationMs|elapsed)["\']?\s*[:=]\s*)\d+', re.I),
)


def run_git(repository: Path, *arguments: str, check: bool = True) -> str:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments],
        check=False,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    if check and result.returncode != 0:
        raise RuntimeError(result.stderr.strip() or result.stdout.strip())
    return result.stdout


def message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if not isinstance(content, list):
        return ""
    return "\n".join(
        str(block.get("text", ""))
        for block in content
        if isinstance(block, dict) and block.get("type") == "text"
    )


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as stream:
        for line_number, line in enumerate(stream, 1):
            try:
                value = json.loads(line)
            except json.JSONDecodeError as error:
                raise ValueError(f"JSONL 第 {line_number} 行无效：{error}") from error
            if isinstance(value, dict):
                records.append(value)
    return records


def sanitize(value: Any, replacements: list[tuple[re.Pattern[str], str]]) -> Any:
    if isinstance(value, dict):
        sanitized: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if re.search(r"(?:^|_)(?:date|timestamp|duration|elapsed|timeout)(?:_?ms)?$", key_text, re.I):
                continue
            sanitized[key_text] = sanitize(item, replacements)
        return sanitized
    if isinstance(value, list):
        return [sanitize(item, replacements) for item in value]
    if not isinstance(value, str):
        return value

    text = value
    for pattern, replacement in replacements:
        text = pattern.sub(replacement, text)
    for pattern in DATE_PATTERNS:
        text = pattern.sub("[timing omitted]", text)
    for pattern in DURATION_PATTERNS:
        if pattern.groups:
            text = pattern.sub(r"\1[omitted]", text)
        else:
            text = pattern.sub("[timing omitted]", text)
    text = re.sub(
        r"(?im)^(\s*(?:date|timestamp|lastwritetime|start(?:ed)?|end(?:ed)?)\s*[:=]).*$",
        r"\1 [timing omitted]",
        text,
    )
    return text


def compact_tool_summary(name: str, tool_input: dict[str, Any]) -> str:
    for key in ("description", "command", "file_path", "path", "pattern", "query"):
        value = tool_input.get(key)
        if value:
            return str(value).replace("\r", " ").replace("\n", " ")[:240]
    if name == "TodoWrite":
        return "更新任务列表"
    return json.dumps(tool_input, ensure_ascii=False, separators=(",", ":"))[:240]


def public_model_identifier(model: str) -> str:
    """移除 provider/gateway 的内部 deployment suffix，只保留公开 model ID。"""
    return re.sub(r"-jibao\b", "", str(model), flags=re.IGNORECASE)


def parse_execution(records: list[dict[str, Any]]) -> dict[str, Any]:
    prompt = ""
    final_response = ""
    models: Counter[str] = Counter()
    versions: Counter[str] = Counter()
    tools: list[dict[str, Any]] = []
    tool_by_id: dict[str, dict[str, Any]] = {}

    for record in records:
        version = record.get("version")
        if version:
            versions[str(version)] += 1
        record_type = record.get("type")
        message = record.get("message")

        if record_type == "user" and isinstance(message, dict):
            content = message.get("content")
            candidate = message_text(content)
            if candidate and not prompt and "请自主、持续地改进" in candidate:
                prompt = candidate
            if isinstance(content, list):
                for block in content:
                    if not isinstance(block, dict) or block.get("type") != "tool_result":
                        continue
                    tool = tool_by_id.get(str(block.get("tool_use_id", "")))
                    if tool is None:
                        continue
                    tool["result"] = block.get("content", "")
                    if block.get("is_error"):
                        tool["status"] = "error"
                    elif re.search(r"\b(?:warning|failed|failure|refusing|error)\b", str(block.get("content", "")), re.I):
                        tool["status"] = "warning"

        if record_type != "assistant" or not isinstance(message, dict):
            continue
        model = message.get("model")
        if model:
            models[public_model_identifier(str(model))] += 1
        for block in message.get("content", []):
            if not isinstance(block, dict):
                continue
            if block.get("type") == "text" and block.get("text"):
                final_response = str(block["text"])
            if block.get("type") != "tool_use":
                continue
            tool_input = block.get("input") if isinstance(block.get("input"), dict) else {}
            tool = {
                "index": len(tools) + 1,
                "id": str(block.get("id", "")),
                "name": str(block.get("name", "unknown")),
                "summary": compact_tool_summary(str(block.get("name", "unknown")), tool_input),
                "input": tool_input,
                "result": "",
                "status": "ok",
            }
            tools.append(tool)
            tool_by_id[tool["id"]] = tool

    if not prompt:
        for record in records:
            message = record.get("message")
            if record.get("type") == "user" and isinstance(message, dict):
                candidate = message_text(message.get("content"))
                if candidate and not candidate.startswith("<local-command"):
                    prompt = candidate
                    break

    return {
        "prompt": prompt,
        "finalResponse": final_response,
        "mainModel": models.most_common(1)[0][0] if models else "unknown",
        "modelCounts": dict(models),
        "claudeVersion": versions.most_common(1)[0][0] if versions else "unknown",
        "tools": tools,
    }


def parse_subagents(transcript: Path) -> list[dict[str, Any]]:
    directory = transcript.with_suffix("") / "subagents"
    if not directory.is_dir():
        return []
    subagents: list[dict[str, Any]] = []
    for meta_path in sorted(directory.glob("*.meta.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        session_path = meta_path.with_name(meta_path.name.replace(".meta.json", ".jsonl"))
        actual_models: Counter[str] = Counter()
        if session_path.is_file():
            for record in load_jsonl(session_path):
                message = record.get("message")
                if record.get("type") == "assistant" and isinstance(message, dict) and message.get("model"):
                    actual_models[public_model_identifier(str(message["model"]))] += 1
        subagents.append(
            {
                "toolUseId": meta.get("toolUseId", ""),
                "description": meta.get("description", ""),
                "requestedModel": meta.get("model", ""),
                "actualModel": actual_models.most_common(1)[0][0] if actual_models else "unknown",
                "status": "success",
            }
        )
    return subagents


def apply_subagent_actual_model_overrides(
    subagents: list[dict[str, Any]],
    overrides: dict[str, Any],
) -> None:
    """按 requested model 或 tool-use ID 修正已知的 backend model 归属。"""
    if not isinstance(overrides, dict):
        raise ValueError("profile override subagentActualModelOverrides 必须是 object")
    for subagent in subagents:
        selector = str(subagent.get("toolUseId", ""))
        requested_model = str(subagent.get("requestedModel", ""))
        actual_model = overrides.get(selector, overrides.get(requested_model))
        if actual_model is not None:
            subagent["actualModel"] = public_model_identifier(str(actual_model))


def git_information(
    repository: Path,
    working_tree_candidate: bool = False,
    baseline_revision: str | None = None,
) -> dict[str, Any]:
    if working_tree_candidate:
        if baseline_revision is not None:
            raise ValueError("--baseline-revision 不能与 --working-tree-candidate 同时使用")
        baseline = run_git(repository, "rev-parse", "HEAD").strip()
        diff_arguments = (baseline,)
        diff = run_git(repository, "diff", "--no-ext-diff", baseline)
        candidate = f"worktree-{hashlib.sha256(diff.encode('utf-8')).hexdigest()[:12]}"
    else:
        candidate = run_git(repository, "rev-parse", "HEAD").strip()
        baseline = run_git(
            repository,
            "rev-parse",
            baseline_revision if baseline_revision is not None else "HEAD^",
        ).strip()
        diff_arguments = (baseline, candidate)
        diff = run_git(repository, "diff", "--no-ext-diff", *diff_arguments)
    numstat = run_git(repository, "diff", "--numstat", *diff_arguments)
    files: list[dict[str, Any]] = []
    for line in numstat.splitlines():
        added, deleted, name = line.split("\t", 2)
        files.append({"file": name, "added": added, "deleted": deleted})
    diff_check = subprocess.run(
        ["git", "-C", str(repository), "diff", "--check", *diff_arguments],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
    )
    return {
        "candidate": candidate,
        "baseline": baseline,
        "files": files,
        "stat": run_git(repository, "diff", "--stat", *diff_arguments).strip(),
        "diff": diff,
        "diffCheck": "PASS" if diff_check.returncode == 0 else "FAIL",
        "diffCheckOutput": (diff_check.stdout + diff_check.stderr).strip(),
        "worktreeStatus": run_git(repository, "status", "--short", check=False).strip(),
    }


def payload_from_report(path: Path) -> dict[str, Any]:
    html = path.read_text(encoding="utf-8")
    prefix = "const DATA="
    suffix = ";\nconst esc="
    start = html.find(prefix)
    end = html.find(suffix, start + len(prefix))
    if start < 0 or end < 0:
        raise ValueError(f"无法从 existing report 提取 payload：{path}")
    payload = json.loads(html[start + len(prefix) : end])
    if not isinstance(payload, dict):
        raise ValueError(f"existing report 的 payload 无效：{path}")
    return payload


def profile_from_report(path: Path) -> dict[str, Any]:
    payload = payload_from_report(path)
    profile = payload.get("profile")
    if not isinstance(profile, dict):
        raise ValueError(f"existing report 不含 profile：{path}")
    return profile


def markdown_cell(value: Any) -> str:
    """将值安全压缩为 GitHub Markdown table cell。"""
    return str(value).replace("|", "\\|").replace("\r", "").replace("\n", "<br>")


def markdown_signed(value: Any) -> str:
    return f"{float(value):+.8f}"


def render_markdown_report(payload: dict[str, Any]) -> str:
    """生成适合 GitHub 直接渲染的精简但完整 evaluation report。"""
    profile = payload.get("profile", {})
    execution = payload.get("execution", {})
    git = payload.get("git", {})
    evaluation = payload.get("evaluation", {})
    tools = execution.get("tools", [])
    subagents = payload.get("subagents", [])

    candidate = str(git.get("candidate", "unknown"))
    candidate_label = candidate if candidate.startswith("worktree-") else candidate[:7]
    baseline_label = str(git.get("baseline", "unknown"))[:7]
    status_counts = Counter(str(tool.get("status", "ok")) for tool in tools)
    tool_counts = Counter(str(tool.get("name", "unknown")) for tool in tools)
    agent_attempts = sum(1 for tool in tools if tool.get("name") == "Agent")
    added = sum(int(item["added"]) for item in git.get("files", []) if str(item.get("added", "")).isdigit())
    deleted = sum(int(item["deleted"]) for item in git.get("files", []) if str(item.get("deleted", "")).isdigit())

    lines = [
        f"# {profile.get('title', 'Rendering evaluation report')}",
        "",
        "> GitHub-readable evaluation report。本文件保留指标、过程分析和 tool-call 摘要，不嵌入体积过大的 tool input/output 或完整 Git diff。",
        "",
    ]

    if evaluation.get("status") == "complete":
        normalized = float(evaluation.get("normalizedImprovementScore", 0.0))
        decision = str(evaluation.get("decision", "unknown"))
        lines.extend(
            [
                "## 最终结果",
                "",
                f"**Normalized improvement：`{normalized:.8f}` · Decision：`{decision}`**",
                "",
                "| Baseline A | Candidate B / Strict | Mean B−A | Cases | Strict / Excluded / Errors |",
                "|---:|---:|---:|---:|---:|",
                (
                    f"| {float(evaluation.get('averageScoreA', 0)):.8f} "
                    f"| {float(evaluation.get('averageScoreB', 0)):.8f} "
                    f"| {markdown_signed(evaluation.get('averageImprovement', 0))} "
                    f"| {evaluation.get('caseCount', 0)} "
                    f"| {evaluation.get('strictCases', 0)} / {evaluation.get('excludedCases', 0)} / {evaluation.get('errorCases', 0)} |"
                ),
                "",
                "`Normalized improvement` 是最终 coding improvement 分数；`Strict score` 是单个 renderer 对 offline reference 的绝对分数。",
                "",
                "### 指标变化",
                "",
                "| 指标 | 权重 | Baseline | Candidate | 变化 | 改善 | 退化 | 不变 |",
                "|---|---:|---:|---:|---:|---:|---:|---:|",
            ]
        )
        for metric in evaluation.get("metricChanges", []):
            lines.append(
                "| {label} | {weight} | {a:.8f} | {b:.8f} | {delta} | {improved} | {worse} | {same} |".format(
                    label=markdown_cell(metric.get("label", metric.get("key", ""))),
                    weight=markdown_cell(metric.get("weight", "")),
                    a=float(metric.get("scoreA", 0)),
                    b=float(metric.get("scoreB", 0)),
                    delta=markdown_signed(metric.get("change", 0)),
                    improved=metric.get("improvedCases", 0),
                    worse=metric.get("worseCases", 0),
                    same=metric.get("unchangedCases", 0),
                )
            )
        lines.extend(
            [
                "",
                "### Regression gates",
                "",
                "| Gate | Required | Median delta | 改善 | 退化 | 不变 | 结果 |",
                "|---|---:|---:|---:|---:|---:|---|",
            ]
        )
        gate_labels = {
            "perceptualFlipMedian": "Median FLIP delta",
            "worstPatchFlipMedian": "Median worst-patch FLIP delta",
        }
        for key, gate in evaluation.get("regressionGates", {}).items():
            lines.append(
                "| {label} | {required} | {median} | {improved} | {worse} | {same} | {result} |".format(
                    label=gate_labels.get(key, key),
                    required="yes" if gate.get("required") else "no",
                    median=markdown_signed(gate.get("medianDelta", 0)),
                    improved=gate.get("improvedCases", 0),
                    worse=gate.get("worseCases", 0),
                    same=gate.get("unchangedCases", 0),
                    result="PASS" if gate.get("passed") else "FAIL",
                )
            )
        lines.append("")
    else:
        lines.extend(["## 最终结果", "", "该报告尚未接入正式 evaluation result。", ""])

    lines.extend(["## 总体判断", "", str(profile.get("overall", "")), "", "## 改动与实测评价", ""])
    for change in profile.get("changes", []):
        lines.extend(
            [
                f"### `{change.get('file', '')}`",
                "",
                f"- 改动：{change.get('change', '')}",
                f"- 目标：{change.get('goal', '')}",
                f"- 评测：{change.get('assessment', '')}",
                "",
            ]
        )

    lines.extend(["## 做得好的地方", ""])
    lines.extend(f"- {item}" for item in profile.get("good", []))
    lines.extend(["", "## 风险与不足", ""])
    lines.extend(f"- {item}" for item in profile.get("risks", []))
    lines.extend(["", "## 分项结论", "", "| 维度 | 评价 | 说明 |", "|---|---|---|"])
    for verdict in profile.get("verdicts", []):
        lines.append(
            f"| {markdown_cell(verdict.get('dimension', ''))} | {markdown_cell(verdict.get('rating', ''))} | {markdown_cell(verdict.get('detail', ''))} |"
        )

    lines.extend(
        [
            "",
            "## 执行概览",
            "",
            f"- Test：`{profile.get('testId', '')}`",
            f"- Main model：`{execution.get('mainModel', 'unknown')}`",
            f"- Claude Code：`{execution.get('claudeVersion', 'unknown')}`",
            f"- Candidate / Baseline：`{candidate_label}` / `{baseline_label}`",
            f"- Tool calls：{len(tools)}（{status_counts.get('error', 0)} errors，{status_counts.get('warning', 0)} warnings）",
            f"- Subagents：{len(subagents)} success / {agent_attempts} attempts",
            f"- Git diff：{len(git.get('files', []))} files，+{added} / -{deleted}，diff check `{git.get('diffCheck', 'unknown')}`",
            "",
            "### Tool 类型",
            "",
            "| Tool | Calls |",
            "|---|---:|",
        ]
    )
    for name, count in tool_counts.most_common():
        lines.append(f"| {markdown_cell(name)} | {count} |")

    lines.extend(["", "## 执行阶段", ""])
    phases = profile.get("phases", [])
    for phase in phases:
        lines.extend(
            [
                f"### #{phase.get('start')}–#{phase.get('end')} · {phase.get('name', '')}",
                "",
                f"- 动作：{phase.get('action', '')}",
                f"- 分析：{phase.get('analysis', '')}",
                f"- 证据：{phase.get('evidence', '')}",
                "",
            ]
        )

    lines.extend(["## Subagent", ""])
    if subagents:
        lines.extend(["| 任务 | Requested | Actual | 状态 |", "|---|---|---|---|"])
        for subagent in subagents:
            lines.append(
                f"| {markdown_cell(subagent.get('description', ''))} | {markdown_cell(subagent.get('requestedModel', ''))} | {markdown_cell(subagent.get('actualModel', ''))} | {markdown_cell(subagent.get('status', ''))} |"
            )
    else:
        lines.append("没有成功返回的 subagent。")

    lines.extend(["", "## Git 文件变化", "", "| File | Added | Deleted |", "|---|---:|---:|"])
    for item in git.get("files", []):
        lines.append(
            f"| `{markdown_cell(item.get('file', ''))}` | {markdown_cell(item.get('added', ''))} | {markdown_cell(item.get('deleted', ''))} |"
        )
    lines.extend(["", f"Worktree status：`{markdown_cell(git.get('worktreeStatus') or 'clean')}`", ""])

    phase_by_index: dict[int, str] = {}
    for phase in phases:
        for index in range(int(phase.get("start", 0)), int(phase.get("end", -1)) + 1):
            phase_by_index[index] = str(phase.get("name", ""))
    lines.extend(
        [
            "<details>",
            "<summary><strong>Tool-call 流程摘要</strong></summary>",
            "",
            "| # | 阶段 | Tool | 状态 | 摘要 |",
            "|---:|---|---|---|---|",
        ]
    )
    for tool in tools:
        index = int(tool.get("index", 0))
        lines.append(
            f"| {index} | {markdown_cell(phase_by_index.get(index, ''))} | {markdown_cell(tool.get('name', ''))} | {markdown_cell(tool.get('status', ''))} | {markdown_cell(tool.get('summary', ''))} |"
        )
    lines.extend(["", "</details>", ""])

    lines.extend(
        [
            "<details>",
            "<summary><strong>Agent 最终回复</strong></summary>",
            "",
            f"<pre>{html.escape(str(execution.get('finalResponse', '')))}</pre>",
            "",
            "</details>",
            "",
        ]
    )
    return "\n".join(lines)


def evaluation_summary(
    baseline_score_path: Path | None,
    score_path: Path | None,
    improvement_path: Path | None,
) -> dict[str, Any]:
    if baseline_score_path is None and score_path is None and improvement_path is None:
        return {"status": "pending"}
    if baseline_score_path is None or score_path is None or improvement_path is None:
        raise ValueError(
            "--baseline-score-report、--score-report 与 --improvement-report 必须同时提供"
        )
    baseline = json.loads(baseline_score_path.read_text(encoding="utf-8-sig"))
    score = json.loads(score_path.read_text(encoding="utf-8-sig"))
    improvement = json.loads(improvement_path.read_text(encoding="utf-8-sig"))
    fingerprints = {
        baseline.get("protocolFingerprint"),
        score.get("protocolFingerprint"),
        improvement.get("protocolFingerprint"),
    }
    evaluation_sets = {
        baseline.get("evaluationSetFingerprint"),
        score.get("evaluationSetFingerprint"),
        improvement.get("evaluationSetFingerprint"),
    }
    if len(fingerprints) != 1 or len(evaluation_sets) != 1:
        raise ValueError("baseline/candidate/improvement report fingerprint 不一致")

    baseline_cases = {case["id"]: case for case in baseline["cases"]}
    candidate_cases = {case["id"]: case for case in score["cases"]}
    if set(baseline_cases) != set(candidate_cases):
        raise ValueError("baseline 与 candidate 的 case 集合不一致")
    metric_definitions = (
        ("perceptualFlip", "FLIP perceptual score", "70%"),
        ("worstPatchFlip", "Worst-patch FLIP", "diagnostic"),
        ("indirectTransport", "Indirect transport", "30%"),
        ("occlusionLeak", "Occlusion leak", "diagnostic"),
        ("totalScore", "Strict score", "aggregate"),
    )
    metric_changes: list[dict[str, Any]] = []
    for key, label, weight in metric_definitions:
        pairs: list[tuple[float, float]] = []
        for case_id in sorted(baseline_cases):
            before_case = baseline_cases[case_id]
            after_case = candidate_cases[case_id]
            if key == "totalScore":
                before = before_case["totalScore"]
                after = after_case["totalScore"]
            elif key == "worstPatchFlip":
                before = before_case["diagnosticScores"][key]
                after = after_case["diagnosticScores"][key]
            else:
                before = before_case["scores"][key]
                after = after_case["scores"][key]
            pairs.append((float(before), float(after)))
        average_a = sum(pair[0] for pair in pairs) / len(pairs)
        average_b = sum(pair[1] for pair in pairs) / len(pairs)
        metric_changes.append(
            {
                "key": key,
                "label": label,
                "weight": weight,
                "scoreA": average_a,
                "scoreB": average_b,
                "change": average_b - average_a,
                "improvedCases": sum(after > before for before, after in pairs),
                "worseCases": sum(after < before for before, after in pairs),
                "unchangedCases": sum(after == before for before, after in pairs),
            }
        )
    aggregate = score.get("aggregate", {})
    return {
        "status": "complete",
        "decision": improvement["decision"],
        "caseCount": improvement["caseCount"],
        "averageScoreA": improvement["averageScoreA"],
        "averageScoreB": improvement["averageScoreB"],
        "averageImprovement": improvement["averageImprovement"],
        "ungatedNormalizedImprovementScore": improvement.get(
            "ungatedNormalizedImprovementScore",
            improvement["normalizedImprovementScore"],
        ),
        "normalizedImprovementScore": improvement["normalizedImprovementScore"],
        "regressionGates": improvement.get("regressionGates", {}),
        "strictCases": aggregate["strictCases"],
        "excludedCases": aggregate["excludedCases"],
        "errorCases": aggregate["errorCases"],
        "perceptualScore": aggregate["perceptualScore"],
        "metricChanges": metric_changes,
        "protocolFingerprint": score["protocolFingerprint"],
        "evaluationSetFingerprint": score["evaluationSetFingerprint"],
        "scoreReport": score_path.name,
        "baselineScoreReport": baseline_score_path.name,
        "improvementReport": improvement_path.name,
    }


HTML_TEMPLATE = r'''<!doctype html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title>
<style>
:root{color-scheme:light dark;--bg:#f6f7f9;--surface:#fff;--surface2:#eef1f5;--text:#18202b;--muted:#667080;--line:#d5dae1;--accent:#315efb;--green:#16794b;--red:#c33b3b;--orange:#b56a00;--shadow:0 10px 30px rgba(20,30,45,.08)}
@media(prefers-color-scheme:dark){:root{--bg:#111419;--surface:#181d24;--surface2:#202731;--text:#edf1f7;--muted:#a4adba;--line:#323b48;--accent:#82a1ff;--green:#59c995;--red:#ff8585;--orange:#ffc069;--shadow:0 10px 30px rgba(0,0,0,.25)}}
*{box-sizing:border-box}html,body{max-width:100%;overflow-x:hidden}body{margin:0;background:var(--bg);color:var(--text);font:14px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}button,input,select{font:inherit}code,pre{font-family:"Cascadia Code",Consolas,monospace}a{color:var(--accent)}
.shell{max-width:1440px;margin:auto;padding:24px}.hero{display:grid;gap:12px;margin-bottom:20px}.hero h1{font-size:28px;margin:0}.meta{display:flex;gap:10px 18px;flex-wrap:wrap;color:var(--muted)}.badge{display:inline-flex;padding:2px 9px;border-radius:999px;background:var(--surface2);color:var(--text)}.pending-badge{background:var(--orange);color:#fff;font-weight:700}
.nav{display:flex;gap:8px;flex-wrap:wrap;margin:18px 0 22px}.nav button{border:1px solid var(--line);background:var(--surface);color:var(--text);padding:8px 13px;border-radius:8px;cursor:pointer}.nav button.active{background:var(--accent);border-color:var(--accent);color:#fff}.view{display:none}.view.active{display:block}
.grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:12px}.card{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:16px;box-shadow:var(--shadow)}.score{display:grid;grid-template-columns:minmax(260px,.75fr) minmax(0,1.25fr);gap:20px;align-items:center;margin-bottom:14px;border:2px solid var(--orange)}.score-label{font-weight:700;color:var(--orange);letter-spacing:.04em}.score-value{font-size:43px;line-height:1.1;font-weight:800;margin:8px 0}.stat-label,.small{color:var(--muted)}.stat-value{font-size:24px;font-weight:700;margin-top:3px}.positive{color:var(--green)}.negative{color:var(--red)}.warning{color:var(--orange)}
h2{font-size:21px;margin:26px 0 12px}h3{font-size:16px;margin:18px 0 8px}.prompt{white-space:pre-wrap;background:var(--surface);border:1px solid var(--line);padding:14px;border-radius:10px}.analysis-lead{border-left:5px solid var(--accent);font-size:15px}.analysis-columns{display:grid;grid-template-columns:1fr 1fr;gap:12px}.analysis-columns h3{margin-top:0}.analysis-columns ul{margin:8px 0 0;padding-left:20px}.analysis-columns li+li{margin-top:7px}
.phase-track{height:36px;display:flex;background:var(--surface2);overflow:hidden;border-radius:8px}.phase{min-width:4px;display:flex;align-items:center;justify-content:center;color:#fff;font-size:11px;overflow:hidden;white-space:nowrap}.phase:nth-child(6n+1){background:#315efb}.phase:nth-child(6n+2){background:#db7c25}.phase:nth-child(6n+3){background:#22966f}.phase:nth-child(6n+4){background:#8b62d3}.phase:nth-child(6n+5){background:#d04f7c}.phase:nth-child(6n){background:#2386a8}.phase-legend{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px 16px;margin-top:10px}.phase-legend div{display:flex;justify-content:space-between;gap:8px;color:var(--muted)}
.table-wrap{overflow:auto;background:var(--surface);border:1px solid var(--line);border-radius:10px}table{width:100%;border-collapse:collapse}th,td{padding:9px 11px;text-align:left;border-bottom:1px solid var(--line);vertical-align:top}th{position:sticky;top:0;background:var(--surface2);z-index:1;white-space:nowrap}tr:last-child td{border-bottom:0}.num{text-align:right;font-variant-numeric:tabular-nums;white-space:nowrap}.process-table td:first-child{font-weight:700;white-space:nowrap}
.controls{display:flex;gap:10px;flex-wrap:wrap;margin:10px 0}.controls input,.controls select{background:var(--surface);color:var(--text);border:1px solid var(--line);border-radius:8px;padding:8px 10px}.tool-list{display:grid;gap:8px}.tool{background:var(--surface);border:1px solid var(--line);border-radius:9px}.tool summary{cursor:pointer;padding:11px 13px;display:grid;grid-template-columns:65px 115px 1fr auto;gap:10px;align-items:center}.tool.error{border-left:4px solid var(--red)}.tool.warning{border-left:4px solid var(--orange)}.tool.ok{border-left:4px solid var(--green)}.tool-body{padding:0 13px 13px;display:grid;gap:8px}.tool pre,.raw pre{margin:0;background:var(--surface2);padding:12px;border-radius:7px;white-space:pre-wrap;overflow-wrap:anywhere;max-height:520px;overflow:auto}.status{font-weight:700}.status.ok{color:var(--green)}.status.error{color:var(--red)}.status.warning{color:var(--orange)}.raw details{background:var(--surface);border:1px solid var(--line);border-radius:9px;padding:10px 12px;margin-bottom:10px}.raw summary{cursor:pointer;font-weight:700}
@media(max-width:1000px){.grid{grid-template-columns:repeat(2,minmax(0,1fr))}.analysis-columns,.score{grid-template-columns:1fr}.phase-legend{grid-template-columns:repeat(2,minmax(0,1fr))}}@media(max-width:600px){.shell{padding:14px}.grid{grid-template-columns:1fr}.tool summary{grid-template-columns:55px 90px 1fr}.tool summary .phase-name{display:none}.phase-legend{grid-template-columns:1fr}.hero h1{font-size:23px}}
</style>
</head>
<body><main class="shell">
<header class="hero"><h1 id="title"></h1><div class="meta" id="meta"></div><div class="small">报告保留执行顺序、Tool I/O、代码 diff 与 provenance；执行时间信息和机器绝对路径均已脱敏。</div></header>
<nav class="nav"><button class="active" data-view="overview">总览</button><button data-view="execution">执行全流程</button><button data-view="changes">代码改动</button><button data-view="records">原始记录</button></nav>
<section id="overview" class="view active"><div class="card score"><div><div class="score-label">最终得分 · Normalized improvement</div><div class="score-value warning" id="normalized-score">待 trusted evaluation</div><div id="score-summary">当前没有本轮 A/B improvement report。</div></div><div id="score-details"><strong>Public tests 不是最终成绩。</strong><p>只有使用同一 baseline、test set、4096 SPP reference 和评分协议得到 Candidate B，才能计算 gated Normalized improvement。本报告不以代码审查预测替代最终分数。</p></div></div><h2>评测指标变化</h2><div class="table-wrap"><table><thead><tr><th>指标</th><th>权重/类型</th><th class="num">Baseline A</th><th class="num">Candidate B</th><th class="num">B−A</th><th class="num">改善 cases</th><th class="num">退化 cases</th><th class="num">不变 cases</th></tr></thead><tbody id="metric-changes"><tr><td colspan="8">等待 trusted evaluation。</td></tr></tbody></table></div><p class="small">FLIP、Worst-patch FLIP、Indirect transport、Occlusion leak 和 Strict score 都是相似度分数，越高越接近 offline reference。Strict score 是 FLIP 70% / Indirect transport 30% 的加权几何聚合；Worst-patch FLIP 与 Occlusion leak 是 diagnostics，不进入 case total。</p><h2>跨 case Regression gates</h2><div class="table-wrap"><table><thead><tr><th>Gate</th><th class="num">Median B−A</th><th class="num">改善 cases</th><th class="num">退化 cases</th><th>结果</th></tr></thead><tbody id="regression-gates"><tr><td colspan="5">等待 trusted evaluation。</td></tr></tbody></table></div><p class="small">正式分数要求 mean Strict improvement 为正，同时 FLIP 与 Worst-patch FLIP 的 per-case median improvement 均为正；任一 gate 失败，Normalized improvement 为 0。</p><div class="grid" id="stats"></div><h2>模型实施内容</h2><div class="table-wrap"><table><thead><tr><th>文件/模块</th><th>改动</th><th>目标</th><th>审查判断</th></tr></thead><tbody id="changes-summary"></tbody></table></div><h2>执行过程分析</h2><div class="card analysis-lead" id="overall"></div><div class="analysis-columns"><div class="card"><h3>执行得好的地方</h3><ul id="good"></ul></div><div class="card"><h3>不足与剩余风险</h3><ul id="risks"></ul></div></div><h2>过程质量结论</h2><div class="table-wrap"><table><thead><tr><th>维度</th><th>判断</th><th>依据</th></tr></thead><tbody id="verdicts"></tbody></table></div></section>
<section id="execution" class="view"><h2>输入任务</h2><div class="prompt" id="prompt"></div><h2>阶段分布</h2><div class="phase-track" id="phase-track"></div><div class="phase-legend" id="phase-legend"></div><div class="small">宽度按各阶段 Tool Call 数量计算，不表示执行时间。</div><h2>决策链、证据与结果</h2><div class="table-wrap"><table class="process-table"><thead><tr><th>阶段</th><th>Tool 范围</th><th>执行行为</th><th>过程分析</th><th>证据/结果</th></tr></thead><tbody id="phases"></tbody></table></div><h2>Subagent provenance</h2><div class="table-wrap"><table><thead><tr><th>任务</th><th>请求 model</th><th>实际 model</th><th>状态</th></tr></thead><tbody id="subagents"></tbody></table></div><h2>Tool Call</h2><div class="controls"><select id="tool-phase"><option value="all">全部阶段</option></select><select id="tool-kind"><option value="all">全部 Tool</option></select><select id="tool-status"><option value="all">全部状态</option><option value="ok">成功</option><option value="warning">Warning</option><option value="error">Error</option></select><input id="tool-search" placeholder="搜索 summary/input/output"></div><div class="tool-list" id="tools"></div></section>
<section id="changes" class="view"><h2>Git diff 统计</h2><div class="table-wrap"><table><thead><tr><th>文件</th><th class="num">新增</th><th class="num">删除</th></tr></thead><tbody id="diff-files"></tbody></table></div><h2>完整 diff</h2><div class="raw"><details open><summary>Candidate 相对 baseline</summary><pre id="diff"></pre></details></div><h2>模型最终回复</h2><div class="prompt" id="final-response"></div></section>
<section id="records" class="view"><h2>执行 provenance</h2><div class="raw"><details open><summary>脱敏后的结构化信息</summary><pre id="provenance"></pre></details><details><summary>Git diff --stat</summary><pre id="diff-stat"></pre></details><details><summary>工作树状态</summary><pre id="worktree-status"></pre></details></div><p class="small">为满足报告约束，不内嵌原始 JSONL；上方 Tool Call 已按原始顺序保留并脱敏。</p></section>
</main><script>
const DATA=__DATA__;
const esc=v=>String(v??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const rows=(items,fn)=>items.map(fn).join('');
const phaseFor=i=>DATA.profile.phases.find(p=>i>=p.start&&i<=p.end);
document.title=DATA.profile.title;document.getElementById('title').textContent=DATA.profile.title;
const evaluation=DATA.evaluation||{status:'pending'},evaluated=evaluation.status==='complete',normalized=evaluated?Number(evaluation.normalizedImprovementScore):null;
const candidateLabel=DATA.git.candidate.startsWith('worktree-')?DATA.git.candidate:DATA.git.candidate.slice(0,7);document.getElementById('meta').innerHTML=`<span class="badge pending-badge">Normalized improvement · ${evaluated?normalized.toFixed(8):'待评测'}</span><span class="badge">${esc(DATA.profile.testId)}</span><span>Candidate ${esc(candidateLabel)}</span><span>Baseline ${esc(DATA.git.baseline.slice(0,7))}</span><span>Main model ${esc(DATA.execution.mainModel)}</span><span>Claude Code ${esc(DATA.execution.claudeVersion)}</span>`;
if(evaluated){const scoreNode=document.getElementById('normalized-score');scoreNode.textContent=normalized.toFixed(8);scoreNode.classList.remove('warning');scoreNode.classList.add(evaluation.decision==='success'?'positive':'negative');document.getElementById('score-summary').textContent=`${evaluation.caseCount} cases · ${evaluation.decision.toUpperCase()} · mean(B−A) ${Number(evaluation.averageImprovement)>=0?'+':''}${Number(evaluation.averageImprovement).toFixed(8)}`;document.getElementById('score-details').innerHTML=`<strong>这是最终 coding improvement 分数。</strong><p>Baseline A <code>${Number(evaluation.averageScoreA).toFixed(8)}</code> → Candidate B / Strict score <code>${Number(evaluation.averageScoreB).toFixed(8)}</code>；ungated normalized 为 <code>${Number(evaluation.ungatedNormalizedImprovementScore).toFixed(8)}</code>，通过全部 regression gates 后才成为正式分数。Strict score 是单个 renderer 对 reference 的绝对分数，不是本实验的最终排名分数。</p><p class="small">Strict cases ${evaluation.strictCases} · excluded ${evaluation.excludedCases} · errors ${evaluation.errorCases} · perceptual ${Number(evaluation.perceptualScore).toFixed(8)}</p>`;}
const signed=value=>`${Number(value)>=0?'+':''}${Number(value).toFixed(8)}`;if(evaluated){document.getElementById('metric-changes').innerHTML=rows(evaluation.metricChanges,m=>`<tr><td><strong>${esc(m.label)}</strong></td><td>${esc(m.weight)}</td><td class="num">${Number(m.scoreA).toFixed(8)}</td><td class="num">${Number(m.scoreB).toFixed(8)}</td><td class="num ${Number(m.change)>0?'positive':Number(m.change)<0?'negative':''}"><strong>${signed(m.change)}</strong></td><td class="num positive">${m.improvedCases}</td><td class="num negative">${m.worseCases}</td><td class="num">${m.unchangedCases}</td></tr>`);}
if(evaluated){const gateLabels={perceptualFlipMedian:'Median FLIP delta',worstPatchFlipMedian:'Median worst-patch FLIP delta'};document.getElementById('regression-gates').innerHTML=rows(Object.entries(evaluation.regressionGates||{}),([key,g])=>`<tr><td><strong>${esc(gateLabels[key]||key)}</strong></td><td class="num ${Number(g.medianDelta)>0?'positive':'negative'}">${signed(g.medianDelta)}</td><td class="num positive">${g.improvedCases}</td><td class="num negative">${g.worseCases}</td><td class="${g.passed?'positive':'negative'}"><strong>${g.passed?'PASS':'FAIL'}</strong></td></tr>`);}
const errorCount=DATA.execution.tools.filter(t=>t.status==='error').length,warningCount=DATA.execution.tools.filter(t=>t.status==='warning').length,added=DATA.git.files.reduce((n,f)=>n+(Number(f.added)||0),0),deleted=DATA.git.files.reduce((n,f)=>n+(Number(f.deleted)||0),0),agentAttempts=DATA.execution.tools.filter(t=>t.name==='Agent').length;
document.getElementById('stats').innerHTML=[['Tool 调用',DATA.execution.tools.length,'按原始 session 顺序'],['代码规模',`${DATA.git.files.length} files`, `+${added} / -${deleted}`],['Tool 异常',`${errorCount} error`,`${warningCount} warning`],['Subagent',`${DATA.subagents.length} success`,`${agentAttempts} attempts`]].map(x=>`<div class="card"><div class="stat-label">${esc(x[0])}</div><div class="stat-value">${esc(x[1])}</div><div class="small">${esc(x[2])}</div></div>`).join('');
document.getElementById('changes-summary').innerHTML=rows(DATA.profile.changes,c=>`<tr><td><code>${esc(c.file)}</code></td><td>${esc(c.change)}</td><td>${esc(c.goal)}</td><td>${esc(c.assessment)}</td></tr>`);
document.getElementById('overall').innerHTML=`<strong>总体判断</strong><p>${esc(DATA.profile.overall)}</p>`;document.getElementById('good').innerHTML=rows(DATA.profile.good,x=>`<li>${esc(x)}</li>`);document.getElementById('risks').innerHTML=rows(DATA.profile.risks,x=>`<li>${esc(x)}</li>`);document.getElementById('verdicts').innerHTML=rows(DATA.profile.verdicts,v=>`<tr><td>${esc(v.dimension)}</td><td><strong>${esc(v.rating)}</strong></td><td>${esc(v.detail)}</td></tr>`);
document.getElementById('prompt').textContent=DATA.execution.prompt;
const totalPhaseCalls=DATA.profile.phases.reduce((n,p)=>n+p.end-p.start+1,0);document.getElementById('phase-track').innerHTML=rows(DATA.profile.phases,p=>`<div class="phase" style="width:${100*(p.end-p.start+1)/totalPhaseCalls}%">${esc(p.name)}</div>`);document.getElementById('phase-legend').innerHTML=rows(DATA.profile.phases,p=>`<div><span>${esc(p.name)}</span><span>#${p.start}–#${p.end}</span></div>`);document.getElementById('phases').innerHTML=rows(DATA.profile.phases,p=>`<tr><td>${esc(p.name)}</td><td class="num">#${p.start}–#${p.end}</td><td>${esc(p.action)}</td><td>${esc(p.analysis)}</td><td>${esc(p.evidence)}</td></tr>`);
const agentCalls=DATA.execution.tools.filter(t=>t.name==='Agent'),successfulIds=new Set(DATA.subagents.map(s=>s.toolUseId));const agentRows=[...DATA.subagents,...agentCalls.filter(t=>!successfulIds.has(t.id)).map(t=>({description:t.input.description||t.summary,requestedModel:t.input.model||'default',actualModel:'未启动',status:t.status==='error'?'failed':'unknown'}))];document.getElementById('subagents').innerHTML=agentRows.length?rows(agentRows,a=>`<tr><td>${esc(a.description)}</td><td>${esc(a.requestedModel)}</td><td>${esc(a.actualModel)}</td><td class="status ${a.status==='success'?'ok':'error'}">${esc(a.status)}</td></tr>`):'<tr><td colspan="4">未调用 subagent</td></tr>';
const kinds=[...new Set(DATA.execution.tools.map(t=>t.name))].sort();document.getElementById('tool-kind').innerHTML+=kinds.map(k=>`<option value="${esc(k)}">${esc(k)}</option>`).join('');document.getElementById('tool-phase').innerHTML+=DATA.profile.phases.map(p=>`<option value="${esc(p.name)}">${esc(p.name)}</option>`).join('');
function renderTools(){const phase=document.getElementById('tool-phase').value,kind=document.getElementById('tool-kind').value,status=document.getElementById('tool-status').value,q=document.getElementById('tool-search').value.toLowerCase();const filtered=DATA.execution.tools.filter(t=>{const p=phaseFor(t.index);return(phase==='all'||p?.name===phase)&&(kind==='all'||t.name===kind)&&(status==='all'||t.status===status)&&(!q||JSON.stringify(t).toLowerCase().includes(q))});document.getElementById('tools').innerHTML=rows(filtered,t=>{const p=phaseFor(t.index);return`<details class="tool ${esc(t.status)}"><summary><span>#${t.index}</span><strong>${esc(t.name)}</strong><span>${esc(t.summary)}</span><span class="phase-name">${esc(p?.name||'')}</span></summary><div class="tool-body"><div class="status ${esc(t.status)}">${esc(t.status.toUpperCase())}</div><strong>Input</strong><pre>${esc(JSON.stringify(t.input,null,2))}</pre><strong>Output</strong><pre>${esc(typeof t.result==='string'?t.result:JSON.stringify(t.result,null,2))}</pre></div></details>`})||'<div class="card">没有匹配的 Tool Call。</div>'}
['tool-phase','tool-kind','tool-status','tool-search'].forEach(id=>document.getElementById(id).addEventListener(id==='tool-search'?'input':'change',renderTools));renderTools();
document.getElementById('diff-files').innerHTML=rows(DATA.git.files,f=>`<tr><td><code>${esc(f.file)}</code></td><td class="num">${esc(f.added)}</td><td class="num">${esc(f.deleted)}</td></tr>`);document.getElementById('diff').textContent=DATA.git.diff;document.getElementById('final-response').textContent=DATA.execution.finalResponse;document.getElementById('diff-stat').textContent=DATA.git.stat;document.getElementById('worktree-status').textContent=DATA.git.worktreeStatus||'clean';document.getElementById('provenance').textContent=JSON.stringify({testId:DATA.profile.testId,displayModel:DATA.profile.displayModel,mainModel:DATA.execution.mainModel,modelCounts:DATA.execution.modelCounts,claudeVersion:DATA.execution.claudeVersion,candidate:DATA.git.candidate,baseline:DATA.git.baseline,diffCheck:DATA.git.diffCheck,toolCalls:DATA.execution.tools.length,subagentAttempts:agentAttempts,subagentSuccesses:DATA.subagents.length,evaluation:DATA.evaluation},null,2);
document.querySelectorAll('.nav button').forEach(button=>button.addEventListener('click',()=>{document.querySelectorAll('.nav button').forEach(b=>b.classList.toggle('active',b===button));document.querySelectorAll('.view').forEach(v=>v.classList.toggle('active',v.id===button.dataset.view))}));
</script></body></html>'''


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--transcript", required=True, type=Path)
    parser.add_argument("--repository", required=True, type=Path)
    profile_source = parser.add_mutually_exclusive_group(required=True)
    profile_source.add_argument("--profile", type=Path)
    profile_source.add_argument("--existing-report", type=Path)
    parser.add_argument(
        "--profile-overrides",
        type=Path,
        help="覆盖 profile 顶层字段；changeAssessments 可按 file 更新 change assessment",
    )
    parser.add_argument("--baseline-score-report", type=Path)
    parser.add_argument("--score-report", type=Path)
    parser.add_argument("--improvement-report", type=Path)
    parser.add_argument(
        "--working-tree-candidate",
        action="store_true",
        help="将 repository 的 staged/unstaged diff 作为 candidate，HEAD 作为 baseline",
    )
    parser.add_argument(
        "--baseline-revision",
        help="committed candidate 的显式 Git baseline revision；默认使用 HEAD^",
    )
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument(
        "--markdown-output",
        type=Path,
        help="同时生成 GitHub 可直接阅读的 Markdown report",
    )
    arguments = parser.parse_args()

    transcript = arguments.transcript.resolve()
    repository = arguments.repository.resolve()
    profile = (
        json.loads(arguments.profile.read_text(encoding="utf-8"))
        if arguments.profile is not None
        else profile_from_report(arguments.existing_report)
    )
    subagent_actual_model_overrides: dict[str, Any] = {}
    if arguments.profile_overrides is not None:
        overrides = json.loads(arguments.profile_overrides.read_text(encoding="utf-8"))
        change_assessments = overrides.pop("changeAssessments", {})
        subagent_actual_model_overrides = overrides.pop("subagentActualModelOverrides", {})
        if not isinstance(change_assessments, dict):
            raise ValueError("profile override changeAssessments 必须是 object")
        for change in profile.get("changes", []):
            if change.get("file") in change_assessments:
                change["assessment"] = str(change_assessments[change["file"]])
        profile.update(overrides)
    execution = parse_execution(load_jsonl(transcript))
    subagents = parse_subagents(transcript)
    apply_subagent_actual_model_overrides(subagents, subagent_actual_model_overrides)
    git = git_information(
        repository,
        arguments.working_tree_candidate,
        arguments.baseline_revision,
    )
    evaluation = evaluation_summary(
        arguments.baseline_score_report,
        arguments.score_report,
        arguments.improvement_report,
    )

    replacements = [
        (re.compile(re.escape(str(repository)), re.I), "<candidate-repository>"),
        (re.compile(re.escape(str(repository).replace("\\", "/")), re.I), "<candidate-repository>"),
        (re.compile(re.escape(str(transcript.parent)), re.I), "<claude-project>"),
        (re.compile(re.escape(str(transcript.parent).replace("\\", "/")), re.I), "<claude-project>"),
        (re.compile(r"[A-Z]:" + r"\\Users\\[^\\\s]+", re.I), "<user-home>"),
        (re.compile(r"/[A-Z]/Users/[^/\s]+", re.I), "<user-home>"),
        (re.compile(r"([dl-][rwx-]{9}\s+\d+\s+)\S+"), r"\1<user>"),
        (re.compile(r"[A-Z]:[\\/][^\s\"']*PBR_PRTdemo_TEST\d+", re.I), "<candidate-repository>"),
        (re.compile(r"\b[A-Z]:(?:\\+|/)[^\r\n\"'<>|;&]*", re.I), "<absolute-path>"),
    ]
    payload = sanitize(
        {
            "profile": profile,
            "execution": execution,
            "subagents": subagents,
            "git": git,
            "evaluation": evaluation,
        },
        replacements,
    )
    encoded = json.dumps(payload, ensure_ascii=False, separators=(",", ":")).replace("</script", "<\\/script")
    html = HTML_TEMPLATE.replace("__TITLE__", str(profile["title"])).replace("__DATA__", encoded)
    arguments.output.parent.mkdir(parents=True, exist_ok=True)
    arguments.output.write_text(html, encoding="utf-8", newline="\n")
    print(f"生成报告：{arguments.output}")
    if arguments.markdown_output is not None:
        arguments.markdown_output.parent.mkdir(parents=True, exist_ok=True)
        arguments.markdown_output.write_text(
            render_markdown_report(payload),
            encoding="utf-8",
            newline="\n",
        )
        print(f"生成 Markdown：{arguments.markdown_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
