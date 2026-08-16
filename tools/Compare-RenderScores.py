"""比较同一 strict render dataset 的 baseline A 与 candidate B。"""

from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from typing import Any


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="计算 coding agent 的 0~1 归一化改进分数")
    parser.add_argument("--baseline", type=Path, required=True, help="改动前 strict score report")
    parser.add_argument("--candidate", type=Path, required=True, help="改动后 strict score report")
    parser.add_argument("--output", type=Path, help="改进报告；默认写在 candidate report 旁")
    return parser.parse_args()


def read_json(path: Path) -> dict[str, Any]:
    with path.open("r", encoding="utf-8-sig") as stream:
        return json.load(stream)


def strict_cases(report: dict[str, Any], label: str) -> dict[str, dict[str, Any]]:
    aggregate = report.get("aggregate", {})
    if aggregate.get("errorCases", 0) != 0:
        raise ValueError(f"{label} report 含 error case")
    cases = report.get("cases", [])
    if not cases:
        raise ValueError(f"{label} report 没有 case")
    if any(case.get("mode") != "strict" or "totalScore" not in case for case in cases):
        raise ValueError(f"{label} report 含 provisional case，不能用于 coding improvement")
    by_id = {str(case["id"]): case for case in cases}
    if len(by_id) != len(cases):
        raise ValueError(f"{label} report 含重复 case id")
    return by_id


def calculate_improvement(
    baseline: dict[str, Any], candidate: dict[str, Any]
) -> dict[str, Any]:
    if baseline.get("protocolFingerprint") != candidate.get("protocolFingerprint"):
        raise ValueError("A/B scoring protocol 不一致")
    if baseline.get("evaluationSetFingerprint") != candidate.get("evaluationSetFingerprint"):
        raise ValueError("A/B case definition 或 offline reference 不一致")
    gate_policy = baseline.get("regressionGates", {})
    if gate_policy != candidate.get("regressionGates", {}):
        raise ValueError("A/B regression gate policy 不一致")

    baseline_cases = strict_cases(baseline, "baseline")
    candidate_cases = strict_cases(candidate, "candidate")
    if set(baseline_cases) != set(candidate_cases):
        raise ValueError("A/B case id 集合不一致")

    rows: list[dict[str, Any]] = []
    for case_id in sorted(baseline_cases):
        before = baseline_cases[case_id]
        after = candidate_cases[case_id]
        for fingerprint in ("definitionFingerprint", "referenceFingerprint"):
            if before.get(fingerprint) != after.get(fingerprint):
                raise ValueError(f"case {case_id} 的 {fingerprint} 不一致")
        score_a = float(before["totalScore"])
        score_b = float(after["totalScore"])
        if not 0.0 <= score_a <= 1.0 or not 0.0 <= score_b <= 1.0:
            raise ValueError(f"case {case_id} 的 A/B score 超出 [0,1]")
        try:
            flip_a = float(before["scores"]["perceptualFlip"])
            flip_b = float(after["scores"]["perceptualFlip"])
            worst_patch_a = float(before["diagnosticScores"]["worstPatchFlip"])
            worst_patch_b = float(after["diagnosticScores"]["worstPatchFlip"])
        except KeyError as error:
            raise ValueError(f"case {case_id} 缺少 regression gate 指标：{error}") from error
        if not all(
            0.0 <= value <= 1.0
            for value in (flip_a, flip_b, worst_patch_a, worst_patch_b)
        ):
            raise ValueError(f"case {case_id} 的 regression gate 指标超出 [0,1]")
        rows.append(
            {
                "id": case_id,
                "scoreA": score_a,
                "scoreB": score_b,
                "improvement": score_b - score_a,
                "baselineHeadroom": 1.0 - score_a,
                "perceptualFlipA": flip_a,
                "perceptualFlipB": flip_b,
                "perceptualFlipImprovement": flip_b - flip_a,
                "worstPatchFlipA": worst_patch_a,
                "worstPatchFlipB": worst_patch_b,
                "worstPatchFlipImprovement": worst_patch_b - worst_patch_a,
            }
        )

    count = len(rows)
    average_a = sum(row["scoreA"] for row in rows) / count
    average_b = sum(row["scoreB"] for row in rows) / count
    average_improvement = sum(row["improvement"] for row in rows) / count
    average_headroom = sum(row["baselineHeadroom"] for row in rows) / count
    positive_mean = average_improvement > 0.0
    ungated_normalized = 0.0
    if positive_mean and average_headroom > 0.0:
        ungated_normalized = max(
            0.0, min(1.0, average_improvement / average_headroom)
        )

    def median_gate(metric: str, required: bool) -> dict[str, Any]:
        deltas = [float(row[metric]) for row in rows]
        median_delta = float(statistics.median(deltas))
        return {
            "required": required,
            "passed": not required or median_delta > 0.0,
            "medianDelta": median_delta,
            "improvedCases": sum(delta > 0.0 for delta in deltas),
            "worseCases": sum(delta < 0.0 for delta in deltas),
            "unchangedCases": sum(delta == 0.0 for delta in deltas),
        }

    gate_results = {
        "perceptualFlipMedian": median_gate(
            "perceptualFlipImprovement",
            bool(gate_policy.get("requirePositiveMedianPerceptualFlipDelta", False)),
        ),
        "worstPatchFlipMedian": median_gate(
            "worstPatchFlipImprovement",
            bool(gate_policy.get("requirePositiveMedianWorstPatchFlipDelta", False)),
        ),
    }
    gates_passed = all(gate["passed"] for gate in gate_results.values())
    if not positive_mean:
        decision = "failure"
    elif not gates_passed:
        decision = "failed-regression"
    else:
        decision = "success"
    normalized = ungated_normalized if decision == "success" else 0.0

    return {
        "schemaVersion": 2,
        "baselineLabel": baseline.get("label", ""),
        "candidateLabel": candidate.get("label", ""),
        "protocolFingerprint": baseline.get("protocolFingerprint"),
        "evaluationSetFingerprint": baseline.get("evaluationSetFingerprint"),
        "caseCount": count,
        "decision": decision,
        "averageScoreA": average_a,
        "averageScoreB": average_b,
        "averageImprovement": average_improvement,
        "averageBaselineHeadroom": average_headroom,
        "ungatedNormalizedImprovementScore": ungated_normalized,
        "normalizedImprovementScore": normalized,
        "normalization": "gates_pass ? max(0, mean(B-A) / mean(1-A)) : 0",
        "regressionGatePolicy": gate_policy,
        "regressionGates": gate_results,
        "cases": rows,
    }


def write_markdown(path: Path, report: dict[str, Any]) -> None:
    lines = [
        "# Coding improvement report",
        "",
        f"- Decision: `{report['decision']}`",
        f"- Average A: `{report['averageScoreA']:.8f}`",
        f"- Average B: `{report['averageScoreB']:.8f}`",
        f"- Average B-A: `{report['averageImprovement']:.8f}`",
        f"- Ungated normalized improvement: `{report['ungatedNormalizedImprovementScore']:.8f}`",
        f"- Normalized improvement: `{report['normalizedImprovementScore']:.8f}`",
        "",
        "| Regression gate | Median delta | Improved | Worse | Passed |",
        "|---|---:|---:|---:|---:|",
    ]
    for name, gate in report["regressionGates"].items():
        lines.append(
            f"| {name} | {gate['medianDelta']:.8f} | {gate['improvedCases']} | "
            f"{gate['worseCases']} | {gate['passed']} |"
        )
    lines.extend([
        "",
        "| Case | A | B | B-A | FLIP B-A | Worst patch B-A | Headroom |",
        "|---|---:|---:|---:|---:|---:|---:|",
    ])
    for row in report["cases"]:
        lines.append(
            f"| {row['id']} | {row['scoreA']:.8f} | {row['scoreB']:.8f} | "
            f"{row['improvement']:.8f} | {row['perceptualFlipImprovement']:.8f} | "
            f"{row['worstPatchFlipImprovement']:.8f} | {row['baselineHeadroom']:.8f} |"
        )
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    args = parse_args()
    baseline = read_json(args.baseline)
    candidate = read_json(args.candidate)
    try:
        report = calculate_improvement(baseline, candidate)
    except ValueError as error:
        print(f"Improvement comparison failed: {error}", file=sys.stderr)
        return 2
    output = (args.output or args.candidate.with_name("improvement-report.json")).resolve()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    write_markdown(output.with_suffix(".md"), report)
    print(json.dumps({key: report[key] for key in (
        "decision", "caseCount", "averageImprovement", "normalizedImprovementScore"
    )}, ensure_ascii=False, indent=2))
    print(f"Report: {output}")
    return 0 if report["decision"] == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
