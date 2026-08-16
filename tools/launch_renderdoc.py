"""Launch the nested realtime renderer through RenderDoc。"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from _tooling import REPOSITORY_ROOT, run


def main() -> int:
    parser = argparse.ArgumentParser(description="通过 RenderDoc 启动 PRTdemo")
    parser.add_argument("--renderer", choices=("pbr", "phong"), default="pbr", type=str.lower)
    parser.add_argument("--skip-build", action="store_true")
    parser.add_argument("--renderdoc-cmd", type=Path)
    args = parser.parse_args()
    command: list[str | Path] = [
        sys.executable,
        REPOSITORY_ROOT / "PBR_PRTdemo" / "tools" / "launch_renderdoc.py",
        "--renderer",
        args.renderer,
        "--capture-directory",
        REPOSITORY_ROOT / "test-results" / "renderdoc",
    ]
    if args.skip_build:
        command.append("--skip-build")
    if args.renderdoc_cmd is not None:
        command.extend(("--renderdoc-cmd", args.renderdoc_cmd))
    run(command)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
