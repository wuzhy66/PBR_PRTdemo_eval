"""Render trusted offline references for every render-state case。"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from pathlib import Path

from _tooling import REPOSITORY_ROOT, load_contract, resolve_repo_path, run, validate_render_state
from render_dataset_case import render_case


REQUIRED_REFERENCE_FILES = (
    "manifest.json",
    "offline.png",
    "offline-indirect-linear.pfm",
    "offline-occlusion-mask.pgm",
    "offline-indirect.png",
    "offline-occlusion-leak.png",
)
RECONSTRUCTABLE_AOVS = ("offline-linear.pfm", "offline-direct-linear.pfm")


def main() -> int:
    parser = argparse.ArgumentParser(description="批量生成 offline reference")
    parser.add_argument("--test-set", default="test-set/cases.jsonl")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--samples-per-pixel", type=int, default=4096)
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--reuse-test-set")
    parser.add_argument("--reuse-reference-root")
    parser.add_argument(
        "--jobs",
        type=int,
        default=min(4, max(1, os.cpu_count() or 1)),
        help="并行渲染的 case 数；默认不超过 4",
    )
    parser.add_argument(
        "--threads-per-render",
        type=int,
        help="每个 offline renderer 的 CPU threads；默认按 logical CPUs/jobs 分配",
    )
    args = parser.parse_args()
    if args.jobs < 1:
        raise SystemExit("--jobs 必须大于 0")
    logical_cpus = max(1, os.cpu_count() or 1)
    threads_per_render = args.threads_per_render or max(1, logical_cpus // args.jobs)
    if threads_per_render < 1:
        raise SystemExit("--threads-per-render 必须大于 0")
    test_set = resolve_repo_path(args.test_set)
    output = resolve_repo_path(args.output_root)
    if output.exists() and not args.resume:
        raise SystemExit("reference run output 已存在，拒绝覆盖")
    lines = [line for line in test_set.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    if not lines:
        raise SystemExit("test set 为空")
    contract = load_contract(REPOSITORY_ROOT / "realtime-render-contract.json")
    for line in lines:
        validate_render_state(json.loads(line), contract)
    if bool(args.reuse_test_set) != bool(args.reuse_reference_root):
        raise SystemExit("--reuse-test-set 与 --reuse-reference-root 必须同时提供")

    reusable: dict[str, Path] = {}
    if args.reuse_test_set:
        reuse_test_set = resolve_repo_path(args.reuse_test_set)
        reuse_root = resolve_repo_path(args.reuse_reference_root)
        reuse_lines = [
            line
            for line in reuse_test_set.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()
        ]
        if len(reuse_lines) != len(set(reuse_lines)):
            raise SystemExit("reuse test set 含重复 render state")
        for index, line in enumerate(reuse_lines, 1):
            source = reuse_root / "cases" / f"case-{index:04d}"
            missing = [name for name in REQUIRED_REFERENCE_FILES if not (source / name).is_file()]
            if missing:
                raise SystemExit(f"reuse reference case-{index:04d} 缺少：{', '.join(missing)}")
            manifest = json.loads((source / "manifest.json").read_text(encoding="utf-8-sig"))
            if int(manifest.get("samplesPerPixel", 0)) != args.samples_per_pixel:
                raise SystemExit(f"reuse reference case-{index:04d} SPP 不匹配")
            reusable[line] = source

    new_case_count = sum(line not in reusable for line in lines)
    if not args.skip_build and new_case_count:
        run([sys.executable, REPOSITORY_ROOT / "tools" / "build_offline_renderer.py"])
    output.mkdir(parents=True, exist_ok=args.resume)
    test_set_snapshot = output / "test-set.jsonl"
    canonical_test_set = "\n".join(lines) + "\n"
    if args.resume:
        if not test_set_snapshot.is_file():
            raise SystemExit("resume output 缺少 test-set snapshot")
        if test_set_snapshot.read_text(encoding="utf-8-sig") != canonical_test_set:
            raise SystemExit("resume output 的 test set 与当前输入不一致")
    else:
        test_set_snapshot.write_text(canonical_test_set, encoding="utf-8")
    reused_case_count = 0
    completed_case_count = 0
    render_tasks: list[tuple[str, dict[str, object], Path]] = []
    for index, line in enumerate(lines, 1):
        state = json.loads(line)
        case_id = f"case-{index:04d}"
        destination = output / "cases" / case_id
        partial_destination = destination.with_name(f"{destination.name}.partial")
        if partial_destination.exists():
            if not args.resume:
                raise SystemExit(f"{case_id} 存在遗留 partial output，拒绝覆盖")
            shutil.rmtree(partial_destination)
            print(f"Removed incomplete reference {partial_destination.name}", flush=True)
        if destination.exists():
            missing = [
                name for name in REQUIRED_REFERENCE_FILES if not (destination / name).is_file()
            ]
            if missing:
                if not args.resume:
                    raise SystemExit(f"{case_id} 是不完整输出：{', '.join(missing)}")
                shutil.rmtree(destination)
                print(f"Removed incomplete reference {case_id}", flush=True)
            else:
                manifest = json.loads((destination / "manifest.json").read_text(encoding="utf-8-sig"))
                if int(manifest.get("samplesPerPixel", 0)) != args.samples_per_pixel:
                    raise SystemExit(f"resume {case_id} SPP 不匹配")
                completed_case_count += 1
                print(f"Kept completed reference {case_id}", flush=True)
                continue
        source = reusable.get(line)
        if source is not None:
            destination.mkdir(parents=True)
            for name in REQUIRED_REFERENCE_FILES:
                shutil.copy2(source / name, destination / name)
            reused_case_count += 1
            print(f"Reused reference {case_id}", flush=True)
        else:
            render_tasks.append((case_id, state, destination))

    def render_task(task: tuple[str, dict[str, object], Path]) -> str:
        case_id, state, destination = task
        partial_destination = destination.with_name(f"{destination.name}.partial")
        render_case(
            state,
            partial_destination,
            args.samples_per_pixel,
            skip_build=True,
            renderer_threads=threads_per_render,
        )
        for name in RECONSTRUCTABLE_AOVS:
            (partial_destination / name).unlink(missing_ok=True)
        missing = [
            name for name in REQUIRED_REFERENCE_FILES if not (partial_destination / name).is_file()
        ]
        if missing:
            raise RuntimeError(f"{case_id} render 缺少：{', '.join(missing)}")
        partial_destination.rename(destination)
        return case_id

    if render_tasks:
        worker_count = min(args.jobs, len(render_tasks))
        print(
            f"Rendering {len(render_tasks)} new cases：jobs={worker_count}, "
            f"threads-per-render={threads_per_render}, logical-cpus={logical_cpus}",
            flush=True,
        )
        with ThreadPoolExecutor(max_workers=worker_count) as executor:
            futures = {executor.submit(render_task, task): task[0] for task in render_tasks}
            for future in as_completed(futures):
                case_id = futures[future]
                future.result()
                print(f"Rendered reference {case_id}", flush=True)
    print(
        f"Reference run ready：{args.output_root} "
        f"(completed={completed_case_count}, reused={reused_case_count}, "
        f"rendered={len(render_tasks)})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
