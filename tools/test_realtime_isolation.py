"""Verify realtime repository isolation, public contract, and test-set schema。"""

from __future__ import annotations

import argparse
import json
import math
import re
import subprocess

from _tooling import REPOSITORY_ROOT, load_contract, resolve_repo_path, validate_render_state


FORBIDDEN_PATH = re.compile(
    r"(^|/)(offline|test-results|test-set)(/|$)|Score-|Compare-|render-score|test_render_score|dataset_capture",
    re.IGNORECASE,
)
FORBIDDEN_TOKENS = (
    "flip-evaluator",
    "perceptualFlip",
    "occlusionLeak",
    "weighted-geometric",
    "referenceFingerprint",
    "normalizedImprovement",
    "prt_offline_reference",
    "offline/custom",
)


def git_lines(repository, *arguments: str) -> list[str]:
    result = subprocess.run(
        ["git", "-C", str(repository), *arguments], check=True, capture_output=True, text=True
    )
    return result.stdout.splitlines()


def main() -> int:
    parser = argparse.ArgumentParser(description="验证 realtime-only repository isolation")
    parser.add_argument("--realtime-repository", default="PBR_PRTdemo")
    parser.add_argument("--test-set", default="test-set/cases.jsonl")
    args = parser.parse_args()
    realtime = resolve_repo_path(args.realtime_repository)
    test_set = resolve_repo_path(args.test_set)
    if not (realtime / ".git").exists():
        raise SystemExit("realtime repository 缺少独立 .git")
    actual_root = resolve_repo_path(git_lines(realtime, "rev-parse", "--show-toplevel")[0])
    if actual_root != realtime:
        raise SystemExit("realtime repository root 无效")
    trusted = load_contract(REPOSITORY_ROOT / "realtime-render-contract.json")
    public = load_contract(realtime / "realtime-render-contract.json")
    if trusted != public:
        raise SystemExit("realtime repository 的 public render contract 与 trusted contract 不一致")
    history_paths = []
    for line in git_lines(realtime, "rev-list", "--objects", "--all"):
        parts = line.split(" ", 1)
        if len(parts) == 2 and FORBIDDEN_PATH.search(parts[1]):
            history_paths.append(parts[1])
    if history_paths:
        raise SystemExit("realtime Git history 暴露 protected path：" + ", ".join(history_paths))
    source_extensions = {".cpp", ".h", ".fs", ".vs", ".gs", ".md", ".json", ".py", ".txt"}
    for relative in git_lines(realtime, "ls-files"):
        path = realtime / relative
        if relative.startswith(("includes/", "lib/")) or path.suffix not in source_extensions:
            continue
        content = path.read_text(encoding="utf-8", errors="ignore").lower()
        for token in FORBIDDEN_TOKENS:
            if token.lower() in content:
                raise SystemExit(f"realtime repository 暴露 protected token '{token}'：{relative}")
    case_count = 0
    for line in test_set.read_text(encoding="utf-8-sig").splitlines():
        if not line.strip():
            continue
        case_count += 1
        state = json.loads(line)
        validate_render_state(state, trusted)
    if case_count == 0:
        raise SystemExit("test set 为空")
    print(
        "PASS realtime isolation：history paths clean，render contract aligned，"
        f"render-state cases={case_count}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
