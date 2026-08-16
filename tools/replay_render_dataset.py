"""Replay render-state JSONL through a realtime-only repository。"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

from _tooling import (
    REPOSITORY_ROOT,
    format_number,
    format_vector,
    load_contract,
    read_json,
    realtime_renderer_executable,
    resolve_repo_path,
    run,
    validate_render_state,
)


XVFB_REEXEC_MARKER = "PRT_EVALUATOR_XVFB_ACTIVE"
REQUIRED_REALTIME_FILES = ("realtime.png", "indirect-linear.pfm", "state.json")


def reexec_with_xvfb_if_needed(software_rendering: bool) -> int | None:
    """Linux 无 DISPLAY 时在一个 Xvfb session 中重新运行整个 dataset replay。"""

    if os.name != "posix" or os.environ.get("DISPLAY") or os.environ.get(XVFB_REEXEC_MARKER):
        return None
    xvfb_run = shutil.which("xvfb-run")
    if xvfb_run is None:
        raise SystemExit("Linux headless replay 缺少 xvfb-run；请安装 xvfb。")
    environment = os.environ.copy()
    environment[XVFB_REEXEC_MARKER] = "1"
    if software_rendering:
        environment.setdefault("LIBGL_ALWAYS_SOFTWARE", "true")
        environment.setdefault("GALLIUM_DRIVER", "llvmpipe")
    command = [
        xvfb_run,
        "-a",
        "-s",
        "-screen 0 1600x1200x24",
        sys.executable,
        str(Path(__file__).resolve()),
        *sys.argv[1:],
    ]
    return subprocess.run(command, cwd=REPOSITORY_ROOT, env=environment).returncode


def main() -> int:
    parser = argparse.ArgumentParser(description="批量生成 realtime evaluation images")
    parser.add_argument("--test-set", default="test-set/cases.jsonl")
    parser.add_argument("--realtime-repository", default="PBR_PRTdemo")
    parser.add_argument("--output-root", required=True)
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--reuse-test-set")
    parser.add_argument("--reuse-realtime-root")
    parser.add_argument(
        "--software-rendering",
        action="store_true",
        help="Linux 上强制使用 Mesa llvmpipe；无 DISPLAY 时自动启动 Xvfb",
    )
    parser.add_argument(
        "--llvmpipe-threads",
        type=int,
        default=8,
        help="--software-rendering 下使用的 llvmpipe worker 数，默认 8",
    )
    args = parser.parse_args()
    if args.llvmpipe_threads < 1:
        raise SystemExit("llvmpipe-threads 必须大于 0")
    xvfb_result = reexec_with_xvfb_if_needed(args.software_rendering)
    if xvfb_result is not None:
        return xvfb_result
    test_set = resolve_repo_path(args.test_set)
    realtime_root = resolve_repo_path(args.realtime_repository)
    output = resolve_repo_path(args.output_root)
    if output.exists() and not args.resume:
        raise SystemExit("realtime run output 已存在，拒绝覆盖")
    trusted = load_contract(REPOSITORY_ROOT / "realtime-render-contract.json")
    public = load_contract(realtime_root / "realtime-render-contract.json")
    if trusted != public:
        raise SystemExit("realtime repository 的 public render contract 与 trusted contract 不一致")
    lines = [line for line in test_set.read_text(encoding="utf-8-sig").splitlines() if line.strip()]
    cases = [json.loads(line) for line in lines]
    if not cases:
        raise SystemExit("test set 为空")
    for state in cases:
        validate_render_state(state, trusted)
    if bool(args.reuse_test_set) != bool(args.reuse_realtime_root):
        raise SystemExit("--reuse-test-set 与 --reuse-realtime-root 必须同时提供")

    reusable: dict[str, Path] = {}
    if args.reuse_test_set:
        reuse_test_set = resolve_repo_path(args.reuse_test_set)
        reuse_root = resolve_repo_path(args.reuse_realtime_root)
        reuse_lines = [
            line
            for line in reuse_test_set.read_text(encoding="utf-8-sig").splitlines()
            if line.strip()
        ]
        if len(reuse_lines) != len(set(reuse_lines)):
            raise SystemExit("reuse test set 含重复 render state")
        for index, line in enumerate(reuse_lines, 1):
            source = reuse_root / "cases" / f"case-{index:04d}"
            missing = [name for name in REQUIRED_REALTIME_FILES if not (source / name).is_file()]
            if missing:
                raise SystemExit(f"reuse realtime case-{index:04d} 缺少：{', '.join(missing)}")
            reusable[line] = source

    new_case_count = sum(line not in reusable for line in lines)
    if not args.skip_build and new_case_count:
        run([sys.executable, realtime_root / "tools" / "build.py", "--renderer", "pbr"], cwd=realtime_root)
    executable = realtime_renderer_executable(realtime_root)
    if not executable.is_file():
        raise SystemExit("未找到 realtime renderer executable")
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
    application_directory = realtime_root / "src" / "getting_started" / "GIApplication"
    lighting = trusted["lighting"]
    material = trusted["material"]
    reused_count = 0
    completed_count = 0
    captured_count = 0
    for index, (line, state) in enumerate(zip(lines, cases), 1):
        case_id = f"case-{index:04d}"
        case_directory = output / "cases" / case_id
        if case_directory.exists():
            missing = [name for name in REQUIRED_REALTIME_FILES if not (case_directory / name).is_file()]
            if missing:
                if not args.resume:
                    raise SystemExit(f"{case_id} 是不完整 realtime output：{', '.join(missing)}")
                shutil.rmtree(case_directory)
                print(f"Removed incomplete realtime {case_id}", flush=True)
            else:
                completed_count += 1
                print(f"Kept completed realtime {case_id}", flush=True)
                continue
        source = reusable.get(line)
        if source is not None:
            case_directory.mkdir(parents=True)
            shutil.copy2(source / "realtime.png", case_directory / "realtime.png")
            shutil.copy2(source / "indirect-linear.pfm", case_directory / "indirect-linear.pfm")
            captured_state = {"id": case_id, **state}
            (case_directory / "state.json").write_text(
                json.dumps(captured_state, ensure_ascii=False, separators=(",", ":")) + "\n",
                encoding="utf-8",
            )
            reused_count += 1
            print(f"Reused realtime {case_id}", flush=True)
            continue
        camera = state["camera"]
        light = state["light"]
        environment = os.environ.copy()
        if args.software_rendering:
            environment.update(
                {
                    "LIBGL_ALWAYS_SOFTWARE": "true",
                    "GALLIUM_DRIVER": "llvmpipe",
                    "LP_NUM_THREADS": str(args.llvmpipe_threads),
                }
            )
        environment.update(
            {
                "PRT_VISUAL_TEST": "1",
                "PRT_RENDERER": "PBR",
                "PRT_TEST_MODE": "combined",
                "PRT_DYNAMIC": "1" if lighting["dynamic"] else "0",
                "PRT_DIRECT_SHADOW": "1" if lighting["directShadow"] else "0",
                "PRT_PROBE_SHADOW": "1" if lighting["probeShadow"] else "0",
                "PRT_BANDS": str(int(lighting["prtBands"])),
                "PRT_TEST_CAMERA_POSITION": format_vector(camera["position"]),
                "PRT_TEST_CAMERA_YAW": format_number(camera["yawDegrees"]),
                "PRT_TEST_CAMERA_PITCH": format_number(camera["pitchDegrees"]),
                "PRT_TEST_CAMERA_FOV": format_number(trusted["camera"]["verticalFovDegrees"]),
                "PRT_TEST_LIGHT_POSITION": format_vector(light["position"]),
                "PRT_TEST_LIGHT_INTENSITY": format_vector(light["intensity"]),
                "PRT_TEST_MATERIAL_METALLIC": format_number(material["metallic"]),
                "PRT_TEST_MATERIAL_ROUGHNESS": format_number(material["roughness"]),
                "PRT_TEST_MATERIAL_IOR": format_number(material["ior"]),
                "PRT_TEST_MATERIAL_AO": format_number(material["ao"]),
                "PRT_REALTIME_CAPTURE_ONCE": "1",
                "PRT_REALTIME_OUTPUT_ROOT": str(output),
                "PRT_REALTIME_CASE_ID": case_id,
            }
        )
        print(f"Capturing realtime {case_id}")
        completed = subprocess.run(
            [str(executable), "--renderer", "PBR"], cwd=application_directory, env=environment
        )
        if completed.returncode != 0:
            raise SystemExit(f"{case_id} realtime capture 失败，exit code={completed.returncode}")
        missing = [
            name
            for name in REQUIRED_REALTIME_FILES
            if not (case_directory / name).is_file()
        ]
        if missing:
            raise SystemExit(f"{case_id} 缺少 realtime output：{', '.join(missing)}")
        captured_count += 1
    print(
        f"Realtime run ready：{args.output_root} "
        f"(completed={completed_count}, reused={reused_count}, captured={captured_count})"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
