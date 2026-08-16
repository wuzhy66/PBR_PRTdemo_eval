"""Render built-in offline snapshots with configurable development settings。"""

from __future__ import annotations

import argparse
import datetime as dt
import os
import sys

from _tooling import REPOSITORY_ROOT, offline_renderer_executable, resolve_repo_path, run


def bounded_int(minimum: int, maximum: int):
    def parse(value: str) -> int:
        parsed = int(value)
        if parsed < minimum or parsed > maximum:
            raise argparse.ArgumentTypeError(f"必须在 {minimum}..{maximum}")
        return parsed
    return parse


def main() -> int:
    parser = argparse.ArgumentParser(description="运行 CPU offline renderer")
    parser.add_argument("--width", type=bounded_int(64, 4096), default=800)
    parser.add_argument("--height", type=bounded_int(64, 4096), default=600)
    parser.add_argument("--samples-per-pixel", type=bounded_int(1, 65536), default=4096)
    parser.add_argument("--max-bounces", type=bounded_int(1, 64), default=2)
    parser.add_argument("--threads", type=bounded_int(1, 1024), default=os.cpu_count() or 1)
    parser.add_argument("--seed", type=int, default=20260812)
    parser.add_argument("--only")
    parser.add_argument("--output-directory")
    parser.add_argument("--skip-build", action="store_true")
    args = parser.parse_args()
    if args.samples_per_pixel % 4 != 0:
        raise SystemExit("samples-per-pixel 必须能被 4 整除")
    output_value = args.output_directory or (
        "test-results/offline-reference/" + dt.datetime.now().strftime("%Y%m%d-%H%M%S")
    )
    output = resolve_repo_path(output_value)
    if not args.skip_build:
        run([sys.executable, REPOSITORY_ROOT / "tools" / "build_offline_renderer.py"])
    executable = offline_renderer_executable()
    command: list[str | os.PathLike[str]] = [
        executable,
        "--output",
        output,
        "--width",
        str(args.width),
        "--height",
        str(args.height),
        "--spp",
        str(args.samples_per_pixel),
        "--bounces",
        str(args.max_bounces),
        "--threads",
        str(args.threads),
        "--seed",
        str(args.seed),
    ]
    if args.only:
        command.extend(("--only", args.only))
    run(command)
    print(output_value)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
